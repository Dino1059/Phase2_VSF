from __future__ import annotations
import json
import time
import uuid
from dataclasses import dataclass, field

from src.services.llm import GemmaLLMAdapter, LLMResponse
from src.tools.base import ToolRegistry, ToolCall
from src.db.connection import get_db


@dataclass
class ReActStep:
    step_index: int
    thought: str
    action: str  # tool name or 'FINISH' or 'ABSTAIN'
    action_input: dict = field(default_factory=dict)
    observation: str = ""
    duration_ms: int = 0
    tokens_used: int = 0


@dataclass
class ReActResult:
    task: str
    steps: list[ReActStep] = field(default_factory=list)
    final_answer: str = ""
    status: str = ""  # 'completed', 'max_steps', 'abstained', 'error'
    total_tokens: int = 0
    total_duration_ms: int = 0
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


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
    def __init__(self, llm: GemmaLLMAdapter, tools: ToolRegistry, max_steps: int = 10):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps

    def run(self, task: str, context: dict | None = None) -> ReActResult:
        """Execute a bounded ReAct loop."""
        start_time = time.time()
        result = ReActResult(task=task)
        
        # Build system prompt with available tools
        tool_specs = self.tools.list_tools()
        tool_desc = "\n".join(
            f"- {t['function']['name']}: {t['function']['description']}"
            for t in tool_specs
        )
        system_msg = SYSTEM_PROMPT.format(tool_list=tool_desc, max_steps=self.max_steps)

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"Task: {task}"}
        ]
        
        if context:
            messages.append({"role": "user", "content": f"Context: {json.dumps(context)}"})

        for step_idx in range(self.max_steps):
            step_start = time.time()
            
            # Get LLM response
            llm_response = self.llm.chat(messages, tools=tool_specs)
            
            # Parse response
            step = self._parse_response(step_idx, llm_response)
            step.tokens_used = llm_response.tokens_used
            step.duration_ms = int((time.time() - step_start) * 1000)
            result.steps.append(step)
            result.total_tokens += step.tokens_used

            # Check for tool calls from function calling
            if llm_response.tool_calls:
                tc = llm_response.tool_calls[0]
                step.action = tc["name"]
                step.action_input = tc.get("arguments", {})
                
                # Execute tool
                tool_result = self.tools.execute(step.action, step.action_input)
                step.observation = json.dumps(tool_result.output_data)[:2000]
                
                # Add to conversation
                messages.append({"role": "assistant", "content": llm_response.content or f"Calling {step.action}"})
                messages.append({"role": "user", "content": f"Observation: {step.observation}"})
                
                # Log to DB
                self._log_trace(result.session_id, step)
                continue

            # Check for text-based action parsing
            if step.action == "FINISH":
                result.final_answer = step.thought
                result.status = "completed"
                self._log_trace(result.session_id, step)
                break
            elif step.action == "ABSTAIN":
                result.final_answer = step.thought
                result.status = "abstained"
                self._log_trace(result.session_id, step)
                break
            elif step.action and step.action in self.tools.tool_names:
                # Execute tool from text-parsed action
                try:
                    tool_result = self.tools.execute(step.action, step.action_input)
                    step.observation = json.dumps(tool_result.output_data)[:2000]
                except Exception as e:
                    step.observation = f"Error: {e}"
                
                messages.append({"role": "assistant", "content": llm_response.content})
                messages.append({"role": "user", "content": f"Observation: {step.observation}"})
                self._log_trace(result.session_id, step)
            else:
                # LLM didn't follow format, treat content as final answer
                result.final_answer = llm_response.content
                result.status = "completed"
                self._log_trace(result.session_id, step)
                break
        else:
            result.status = "max_steps"

        result.total_duration_ms = int((time.time() - start_time) * 1000)
        return result

    def _parse_response(self, step_idx: int, response: LLMResponse) -> ReActStep:
        """Parse LLM text response into structured ReActStep."""
        content = response.content
        thought = ""
        action = ""
        action_input = {}

        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("Thought:"):
                thought = line[len("Thought:"):].strip()
            elif line.startswith("Action:"):
                action = line[len("Action:"):].strip()
            elif line.startswith("Action Input:"):
                raw = line[len("Action Input:"):].strip()
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
        """Log step to agent_traces table."""
        try:
            db = get_db()
            trace_id = str(uuid.uuid4())[:8]
            db.execute(
                "INSERT INTO agent_traces (id, session_id, agent_type, step_index, thought, action, tool_name, tool_input, tool_output, tokens_used, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [trace_id, session_id, "react_engine", step.step_index,
                 step.thought[:500], step.action, step.action,
                 json.dumps(step.action_input)[:500],
                 step.observation[:500] if step.observation else None,
                 step.tokens_used, step.duration_ms]
            )
        except Exception:
            pass  # Don't fail the engine if logging fails
