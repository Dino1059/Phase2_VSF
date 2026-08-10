from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field

from src.services.llm import GemmaLLMAdapter, LLMResponse
from src.tools.base import ToolRegistry, ToolCall
from src.db.connection import get_db


@dataclass
class DecisionRecord:
    """Structured decision log record for ReAct step execution."""
    selected_action: str
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    claim: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    contradicting_evidence_refs: list[str] = field(default_factory=list)
    source_query_hashes: list[str] = field(default_factory=list)
    confidence_method: str = "heuristic_grounding"
    confidence: float = 1.0
    alternative_considered: str | None = None
    stop_continue_reason: str = ""


@dataclass
class ReActStep:
    step_index: int
    thought: str
    action: str  # tool name or 'FINISH' or 'ABSTAIN'
    action_input: dict = field(default_factory=dict)
    observation: str = ""
    duration_ms: int = 0
    tokens_used: int = 0
    decision: DecisionRecord | None = None


@dataclass
class ReActResult:
    task: str
    steps: list[ReActStep] = field(default_factory=list)
    final_answer: str = ""
    status: str = ""  # 'completed', 'max_steps', 'abstained', 'token_budget_exceeded', 'error'
    total_tokens: int = 0
    total_duration_ms: int = 0
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    decision_records: list[DecisionRecord] = field(default_factory=list)


SYSTEM_PROMPT = """You are DataTrust OS Agent — an AI-powered data quality analyst for the VinGroup EV ecosystem.

You have access to the following tools:
{tool_list}

For each step, respond in this EXACT format:
Thought: [Your reasoning about what to do next]
Action: [tool_name OR FINISH OR ABSTAIN]
Action Input: [JSON arguments for the tool, or {{}} for FINISH/ABSTAIN]

Rules:
1. Always start with a Thought explaining your reasoning.
2. Use tools to gather data before making conclusions.
3. Use FINISH when you have enough information to answer.
4. Use ABSTAIN if the task is outside your capabilities.
5. Maximum {max_steps} steps allowed.
6. Always provide evidence-based conclusions.
"""


class ReActEngine:
    """Canonical Dynamic ReAct Orchestrator Engine.

    Accepts GemmaLLMAdapter, ToolRegistry, and max_steps (<= 10).
    Supports step loop: Thought -> Action -> Observation -> Conclusion / FINISH / ABSTAIN.
    Enforces token budget and step limit (<= 10).
    Logs step traces to agent_traces table.
    Provides structured decision logging via DecisionRecord.
    """

    def __init__(
        self,
        llm: GemmaLLMAdapter | None = None,
        tools: ToolRegistry | None = None,
        max_steps: int = 10,
        token_budget: int = 10000,
        llm_service: GemmaLLMAdapter | None = None,
        **kwargs,
    ):
        self.llm = llm if llm is not None else (llm_service if llm_service is not None else GemmaLLMAdapter())
        self.tools = tools if tools is not None else ToolRegistry()
        self.max_steps = min(max_steps, 10)
        self.token_budget = token_budget

    def run(self, task: str, context: dict | None = None) -> ReActResult:
        """Execute a bounded dynamic ReAct loop."""
        start_time = time.time()
        result = ReActResult(task=task)

        # Build system prompt with available tools
        tool_specs = self.tools.list_tools() if hasattr(self.tools, "list_tools") else []
        tool_desc = "\n".join(
            f"- {t['function']['name']}: {t['function']['description']}"
            for t in tool_specs
        ) if tool_specs else "No tools registered."
        system_msg = SYSTEM_PROMPT.format(tool_list=tool_desc, max_steps=self.max_steps)

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"Task: {task}"}
        ]

        if context:
            messages.append({"role": "user", "content": f"Context: {json.dumps(context)}"})

        for step_idx in range(self.max_steps):
            if result.total_tokens >= self.token_budget:
                result.status = "token_budget_exceeded"
                break

            step_start = time.time()

            # Get LLM response
            try:
                import sentry_sdk
                with sentry_sdk.start_span(op="llm.chat", description="Gemma LLM Generation"):
                    llm_response = self.llm.chat(messages, tools=tool_specs)
            except Exception as e:
                result.status = "error"
                result.final_answer = f"LLM error: {e}"
                break

            # Parse response into step structure
            step = self._parse_response(step_idx, llm_response)
            step.tokens_used = getattr(llm_response, "tokens_used", 0)
            step.duration_ms = int((time.time() - step_start) * 1000)

            if result.total_tokens + step.tokens_used > self.token_budget and step_idx > 0:
                result.status = "token_budget_exceeded"
                result.total_tokens += step.tokens_used
                break

            result.total_tokens += step.tokens_used

            # Check for tool calls from native LLM function calling
            if getattr(llm_response, "tool_calls", None):
                tc = llm_response.tool_calls[0]
                step.action = tc.get("name", "")
                step.action_input = tc.get("arguments", {})

                try:
                    import sentry_sdk
                    with sentry_sdk.start_span(op="tool.execute", description=f"Tool: {step.action}"):
                        tool_result = self.tools.execute(step.action, step.action_input)
                    output_data = getattr(tool_result, "output_data", str(tool_result))
                    step.observation = json.dumps(output_data)
                except Exception as e:
                    step.observation = f"Error: {e}"

                decision = DecisionRecord(
                    selected_action=step.action,
                    evidence_refs=[f"step_{step_idx}"],
                    confidence=0.9,
                    stop_continue_reason=f"Invoking tool '{step.action}'"
                )
                step.decision = decision
                result.decision_records.append(decision)
                result.steps.append(step)

                # Add to conversation history
                messages.append({"role": "assistant", "content": llm_response.content or f"Calling {step.action}"})
                messages.append({"role": "user", "content": f"Observation: {step.observation}"})

                self._log_trace(result.session_id, step)
                continue

            # Text-based action parsing branch
            if step.action == "FINISH":
                result.final_answer = step.thought
                result.status = "completed"
                decision = DecisionRecord(
                    selected_action="FINISH",
                    evidence_refs=[f"step_{step_idx}"],
                    confidence=1.0,
                    stop_continue_reason="Sufficient information gathered to conclude task."
                )
                step.decision = decision
                result.decision_records.append(decision)
                result.steps.append(step)
                self._log_trace(result.session_id, step)
                break
            elif step.action == "ABSTAIN":
                result.final_answer = step.thought
                result.status = "abstained"
                decision = DecisionRecord(
                    selected_action="ABSTAIN",
                    evidence_refs=[f"step_{step_idx}"],
                    confidence=0.8,
                    stop_continue_reason="Task outside capability boundaries or unresolvable."
                )
                step.decision = decision
                result.decision_records.append(decision)
                result.steps.append(step)
                self._log_trace(result.session_id, step)
                break
            elif step.action and hasattr(self.tools, "tool_names") and (
                step.action in self.tools.tool_names
                or step.action.replace("default_api:", "") in self.tools.tool_names
            ):
                action_name = step.action.replace("default_api:", "")
                try:
                    import sentry_sdk
                    with sentry_sdk.start_span(op="tool.execute", description=f"Tool: {action_name}"):
                        tool_result = self.tools.execute(action_name, step.action_input)
                    output_data = getattr(tool_result, "output_data", str(tool_result))
                    step.observation = json.dumps(output_data)
                except Exception as e:
                    step.observation = f"Error: {e}"

                decision = DecisionRecord(
                    selected_action=action_name,
                    evidence_refs=[f"step_{step_idx}"],
                    confidence=0.9,
                    stop_continue_reason=f"Executing tool '{action_name}'"
                )
                step.decision = decision
                result.decision_records.append(decision)
                result.steps.append(step)

                messages.append({"role": "assistant", "content": llm_response.content})
                messages.append({"role": "user", "content": f"Observation: {step.observation}"})
                self._log_trace(result.session_id, step)
            else:
                # Fallback: treat response content as final answer
                result.final_answer = llm_response.content or step.thought
                result.status = "completed"
                decision = DecisionRecord(
                    selected_action="FINISH_DEFAULT",
                    evidence_refs=[f"step_{step_idx}"],
                    confidence=0.7,
                    stop_continue_reason="LLM produced final response text."
                )
                step.decision = decision
                result.decision_records.append(decision)
                result.steps.append(step)
                self._log_trace(result.session_id, step)
                break
        else:
            if not result.status:
                result.status = "max_steps"

        result.total_duration_ms = int((time.time() - start_time) * 1000)
        return result

    def _parse_response(self, step_idx: int, response: LLMResponse) -> ReActStep:
        """Parse LLM text response into structured ReActStep."""
        content = response.content or ""
        thought = ""
        action = ""
        action_input = {}

        lines = content.split("\n")
        for line in lines:
            line_str = line.strip()
            if line_str.startswith("Thought:"):
                thought = line_str[len("Thought:"):].strip()
            elif line_str.startswith("Action:"):
                raw_action = line_str[len("Action:"):].strip()
                action = raw_action.replace("default_api:", "").strip()
            elif line_str.startswith("Action Input:"):
                raw = line_str[len("Action Input:"):].strip()
                try:
                    action_input = json.loads(raw)
                except json.JSONDecodeError:
                    action_input = {"raw": raw}

        return ReActStep(
            step_index=step_idx,
            thought=thought or content[:200],
            action=action,
            action_input=action_input
        )

    def _log_trace(self, session_id: str, step: ReActStep):
        """Log step execution trace to agent_traces table."""
        try:
            db = get_db()
            trace_id = str(uuid.uuid4())[:8]
            db.execute(
                "INSERT INTO agent_traces (id, session_id, agent_type, step_index, thought, action, tool_name, tool_input, tool_output, observation, tokens_used, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    trace_id,
                    session_id,
                    "canonical_react_engine",
                    step.step_index,
                    step.thought[:500],
                    step.action,
                    step.action,
                    json.dumps(step.action_input)[:500],
                    step.observation[:500] if step.observation else None,
                    step.observation[:500] if step.observation else None,
                    step.tokens_used,
                    step.duration_ms,
                ],
            )
        except Exception:
            pass

    def detect_anomalies(self, current_profile: dict, baseline_profile: dict | None = None) -> Any:
        from src.agents.sub_agents import AnomalyDetectorAgent
        agent = AnomalyDetectorAgent(llm_service=self.llm)
        return agent.run(current_profile=current_profile, baseline_profile=baseline_profile)

    def diagnose(self, data_profile: dict, anomaly_context: dict | None = None) -> Any:
        from src.agents.sub_agents import DiagnosisAgent
        agent = DiagnosisAgent(llm_service=self.llm)
        return agent.run(data_profile=data_profile, anomaly_context=anomaly_context)
