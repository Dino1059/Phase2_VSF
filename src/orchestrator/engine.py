from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from src.services.llm import GemmaLLMAdapter, LLMResponse
from src.tools.base import ToolRegistry, ToolCall
from src.db.connection import get_db
from src.schemas.evidence import EvidenceLedger, EvidenceItem, EvidenceTier, ConfidenceMethod


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


def json_preview(value, limit: int = 1500) -> str | None:
    """Store tool I/O as valid JSON so DuckDB JSON columns accept the row."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        try:
            value = json.dumps(value, default=str)
        except TypeError:
            value = json.dumps({"preview": str(value)[:limit], "truncated": True})
    try:
        parsed = json.loads(value)
        blob = json.dumps(parsed, default=str)
    except json.JSONDecodeError:
        blob = json.dumps({"preview": value[:limit], "truncated": True})
    if len(blob) <= limit:
        return blob
    return json.dumps({"preview": blob[:limit], "truncated": True})


def unwrap_tool_call(tc: dict | None) -> tuple[str, dict]:
    """Accept OpenAI/Gemini nested {function:{name,arguments}} or flat {name,arguments}."""
    if not isinstance(tc, dict):
        return "", {}
    fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
    name = str(tc.get("name") or fn.get("name") or "").replace("default_api:", "").strip()
    args = tc.get("arguments")
    if args in (None, "", {}):
        args = fn.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {"raw": args}
    if not isinstance(args, dict):
        args = {}
    return name, args


def _human_tool_title(name: str | None) -> str:
    return (name or "").replace("_", " ").strip().capitalize()


def _pass_thought(thought: str | None) -> str | None:
    """Keep the model thought if the step has one. Never write "" or invent."""
    if thought is None:
        return None
    text = str(thought).strip()
    return text or None


def _running_now(tool_name: str | None, action_input: dict | None) -> str:
    inp = action_input if isinstance(action_input, dict) else {}
    rows = inp.get("total_rows") or inp.get("sample_size") or inp.get("row_count")
    name = (tool_name or "").lower()
    if "profile" in name:
        if isinstance(rows, (int, float)):
            return f"Now: profiling {int(rows):,} rows…"
        return "Now: profiling dataset…"
    if "propose" in name or "rule_proposer" in name:
        return "Now: proposing quality rules…"
    if "clean" in name or name == "rule_executor":
        return "Now: applying approved rules…"
    if "anomal" in name:
        return "Now: scanning for anomalies…"
    if "list_dataset" in name:
        return "Now: listing datasets…"
    title = _human_tool_title(tool_name) or "tool"
    return f"Now: running {title}…"


def _measured_from_output(tool_name: str | None, output: object) -> str:
    data = output if isinstance(output, dict) else {}
    prof = data.get("profile") if isinstance(data.get("profile"), dict) else {}
    merged = {**prof, **data}
    exec_res = data.get("execution_result") if isinstance(data.get("execution_result"), dict) else {}
    merged.update(exec_res)
    parts: list[str] = []

    def _n(*keys: str):
        src = merged
        for key in keys:
            val = src.get(key)
            if isinstance(val, bool):
                continue
            if isinstance(val, (int, float)):
                return val
        return None

    rows = _n("total_rows", "sample_size", "row_count", "total_processed")
    soc = _n("warehouse_soc_below_zero")
    open_n = _n("warehouse_open_incidents")
    cols = _n("columns_count")
    health = _n("health_score", "data_health_score")
    if rows is not None:
        parts.append(f"{int(rows):,} rows")
    if soc:
        parts.append(f"{int(soc)} SoC<0")
    if open_n:
        parts.append(f"{int(open_n)} OPEN")
    if soc or open_n:
        parts.append("Critical")
    if cols is not None:
        parts.append(f"{int(cols)} columns")
    if health is not None and not soc and not open_n:
        parts.append(f"health {health}")
    proposals = data.get("proposals")
    if isinstance(proposals, list):
        parts.append(f"{len(proposals)} rules")
    if exec_res.get("quarantine_count") is not None:
        try:
            parts.append(f"{int(exec_res['quarantine_count']):,} quarantined")
        except (TypeError, ValueError):
            pass
    if exec_res.get("clean_count") is not None:
        try:
            parts.append(f"{int(exec_res['clean_count']):,} clean")
        except (TypeError, ValueError):
            pass
    if parts:
        return " · ".join(parts)
    title = _human_tool_title(tool_name) or "Tool"
    return f"{title} finished"



HITL_ALLOWED_TOOLS = frozenset({
    "profile_dataset",
    "detect_anomalies",
    "anomaly_detector",
    "propose_quality_rules",
    "quality_rule_proposer",
})
HITL_STOP_ALLOWED_TOOLS = HITL_ALLOWED_TOOLS
HITL_BOOTSTRAP_TOOLS = HITL_ALLOWED_TOOLS
HITL_REFUSED_TOOLS = frozenset({
    "clean_database",
    "algolia_search",
    "list_datasets",
})
HITL_BLOCKED_TOOLS = HITL_REFUSED_TOOLS
_HITL_STOP_MARKERS = (
    "stop for hitl",
    "stop at hitl",
    "hitl review",
    "do not clean, quarantine, or execute",
    "do not clean",
    "don't clean",
    "do not quarantine",
    "do not execute",
    "không làm sạch",
    "khong lam sach",
    "không cách ly",
    "khong cach ly",
    "không thực thi",
    "khong thuc thi",
    "không clean",
    "khong clean",
    "dừng hitl",
    "dung hitl",
    "dừng lại để steward",
    "dung lai de steward",
    "duyệt hitl",
    "duyet hitl",
)


def _is_hitl_stop(task: str, context: dict | None = None) -> bool:
    """True when the steward asked to stop at HITL (no clean / quarantine / execute)."""
    if isinstance(context, dict) and (context.get("stop_at_hitl") or context.get("hitl_stop")):
        return True
    blob = f"{task or ''}"
    if context:
        blob += " " + json.dumps(context, default=str)
    blob = blob.lower()
    return any(m in blob for m in _HITL_STOP_MARKERS)


def _allow_hitl_tool(name: str | None) -> bool:
    """HITL-stop allowlist: profile + propose only. Everything else is refused."""
    n = (name or "").replace("default_api:", "").strip().lower()
    return n in HITL_ALLOWED_TOOLS


def is_hitl_stop_prompt(*parts) -> bool:
    """True for Profile+Propose then stop (do not clean / quarantine / execute)."""
    task = ""
    context = None
    for part in parts:
        if isinstance(part, dict):
            context = part if context is None else {**context, **part}
        elif part:
            task = f"{task} {part}".strip()
    return _is_hitl_stop(task, context)


def is_hitl_blocked_tool(name: str | None) -> bool:
    """True when a HITL-stop run must not execute this tool (allowlist invert)."""
    n = (name or "").replace("default_api:", "").strip().lower()
    if not n or n in ("finish", "abstain", "finish_default"):
        return False
    if n in HITL_REFUSED_TOOLS:
        return True
    return not _allow_hitl_tool(n)


def is_propose_tool(name: str | None) -> bool:
    n = (name or "").replace("default_api:", "").strip().lower()
    return n in ("propose_quality_rules", "quality_rule_proposer")


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
        tool_allowlist: frozenset[str] | set[str] | list[str] | None = None,
        **kwargs,
    ):
        self.llm = llm if llm is not None else (llm_service if llm_service is not None else GemmaLLMAdapter())
        self.tools = tools if tools is not None else ToolRegistry()
        self.max_steps = min(max_steps, 10)
        self.token_budget = token_budget
        self.tool_allowlist = (
            frozenset(str(n).replace("default_api:", "").strip().lower() for n in tool_allowlist)
            if tool_allowlist is not None
            else None
        )

    def run(self, task: str, context: dict | None = None, session_id: str | None = None) -> ReActResult:
        """Execute a bounded dynamic ReAct loop."""
        start_time = time.time()
        result = ReActResult(task=task)
        if session_id:
            result.session_id = session_id
        elif context and "session_id" in context:
            result.session_id = context["session_id"]


        # Build system prompt with available tools
        tool_specs = self.tools.list_tools() if hasattr(self.tools, "list_tools") else []
        hitl_stop = _is_hitl_stop(task, context)
        if hitl_stop:
            # Allowlist: LLM must not even see clean / algolia / list / write tools.
            filtered = []
            for t in tool_specs:
                fn = t.get("function") if isinstance(t, dict) else None
                name = (fn or {}).get("name") if isinstance(fn, dict) else None
                if self._allow_hitl_tool(name):
                    filtered.append(t)
            tool_specs = filtered
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
            messages.append({"role": "user", "content": f"Context: {json.dumps(context, default=str)}"})

        # Pre-flight 10k cap. Word-count (memory narrative is inside context). Not len/4.
        prompt_words = sum(len(str(m.get("content") or "").split()) for m in messages)
        if prompt_words >= self.token_budget:
            result.total_tokens = prompt_words
            result.status = "token_budget_exceeded"
            result.final_answer = "Stopped: 10k token cap (memory block counted)."
            return result
        result.total_tokens = 0

        # Seed a running Profile beat before the LLM call so GET /traces is not empty
        # for ~30s. Later profile_dataset at step 0 upserts this same row. Do not invent Done.
        self._seed_running_profile(result, task, context)

        for step_idx in range(self.max_steps):
            if result.total_tokens >= self.token_budget:
                result.status = "token_budget_exceeded"
                if not result.final_answer:
                    result.final_answer = "Stopped: 10k token cap (memory block counted)."
                break

            step_start = time.time()

            # Get LLM response
            try:
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
                if not result.final_answer:
                    result.final_answer = "Stopped: 10k token cap (memory block counted)."
                break

            result.total_tokens += step.tokens_used

            # Check for tool calls from native LLM function calling
            if getattr(llm_response, "tool_calls", None):
                tc = llm_response.tool_calls[0]
                name, args = unwrap_tool_call(tc if isinstance(tc, dict) else {})
                # Keep text-parsed action if the provider nested name under function.*
                if name:
                    step.action = name
                    step.action_input = args
                elif isinstance(tc, dict) and not step.action:
                    step.action = str(tc.get("name") or "")
                    step.action_input = args
                if context and context.get("dataset_key") and isinstance(step.action_input, dict):
                    step.action_input.setdefault("dataset_key", context["dataset_key"])

                if not step.action:
                    # Empty native payload — do not write a nameless running row.
                    continue

                if _is_hitl_stop(task, context) and not _allow_hitl_tool(step.action):
                    messages.append({"role": "assistant", "content": llm_response.content or f"Calling {step.action}"})
                    messages.append({
                        "role": "user",
                        "content": "Observation: REFUSED — HITL stop. Only profile_dataset and propose_quality_rules. After Propose, FINISH. Do not call clean_database, list_datasets, algolia_search, or write tools.",
                    })
                    if self._hitl_already_proposed(result):
                        result.status = "completed"
                        result.final_answer = result.final_answer or "Stopping for HITL review."
                        break
                    continue

                if self._skip_duplicate_propose(result.session_id, step.action):
                    continue

                self._log_trace(result.session_id, step, status="running")
                try:
                    try:
                        import sentry_sdk
                        with sentry_sdk.start_span(op="tool.execute", description=f"Tool: {step.action}"):
                            tool_result = self.tools.execute(step.action, step.action_input)
                    except ImportError:
                        tool_result = self.tools.execute(step.action, step.action_input)
                except Exception as e:
                    tool_result = None
                    step.observation = f"Error: {e}"
                if tool_result is not None:
                    output_data = getattr(tool_result, "output_data", str(tool_result))
                    step.observation = json.dumps(output_data)

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
                if self._hitl_finish_after_propose(task, context, step.action, step.observation):
                    result.status = "completed"
                    if not result.final_answer:
                        result.final_answer = "Stopping for HITL review."
                    break
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
                if context and context.get("dataset_key") and isinstance(step.action_input, dict):
                    step.action_input.setdefault("dataset_key", context["dataset_key"])
                if _is_hitl_stop(task, context) and not _allow_hitl_tool(action_name):
                    messages.append({"role": "assistant", "content": llm_response.content})
                    messages.append({
                        "role": "user",
                        "content": "Observation: REFUSED — HITL stop. Only profile_dataset and propose_quality_rules. After Propose, FINISH. Do not call clean_database, list_datasets, algolia_search, or write tools.",
                    })
                    if self._hitl_already_proposed(result):
                        result.status = "completed"
                        result.final_answer = result.final_answer or "Stopping for HITL review."
                        break
                    continue
                if self._skip_duplicate_propose(result.session_id, action_name):
                    continue
                self._log_trace(result.session_id, step, status="running")
                try:
                    try:
                        import sentry_sdk
                        with sentry_sdk.start_span(op="tool.execute", description=f"Tool: {action_name}"):
                            tool_result = self.tools.execute(action_name, step.action_input)
                    except ImportError:
                        tool_result = self.tools.execute(action_name, step.action_input)
                except Exception as e:
                    tool_result = None
                    step.observation = f"Error: {e}"
                if tool_result is not None:
                    output_data = getattr(tool_result, "output_data", str(tool_result))
                    step.observation = json.dumps(output_data)

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
                if self._hitl_finish_after_propose(task, context, action_name, step.observation):
                    result.status = "completed"
                    if not result.final_answer:
                        result.final_answer = "Stopping for HITL review."
                    break
            else:
                # Fallback: treat response content as final answer
                result.final_answer = (
                    llm_response.content
                    if (llm_response.content and llm_response.content.strip())
                    else (step.thought if step.thought.strip() else "ReAct execution completed.")
                )
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

        if result.status == "token_budget_exceeded" and not result.final_answer:
            result.final_answer = "Stopped: 10k token cap (memory block counted)."
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
                cleaned = raw_action.replace("default_api:", "").strip()
                if "FINISH" in cleaned.upper():
                    action = "FINISH"
                elif "ABSTAIN" in cleaned.upper():
                    action = "ABSTAIN"
                elif cleaned.startswith("{"):
                    try:
                        parsed_json = json.loads(cleaned)
                        if isinstance(parsed_json, dict):
                            action = parsed_json.get("name", parsed_json.get("action", ""))
                            if "args" in parsed_json or "input" in parsed_json:
                                action_input = parsed_json.get("args") or parsed_json.get("input") or {}
                    except Exception:
                        action = ""
                else:
                    action = cleaned.split()[0] if cleaned.split() else ""
            elif line_str.startswith("Action Input:"):
                raw = line_str[len("Action Input:"):].strip()
                try:
                    action_input = json.loads(raw)
                except json.JSONDecodeError:
                    action_input = {"raw": raw}

        if action and action in ("{}", "{ }"):
            action = "FINISH"

        return ReActStep(
            step_index=step_idx,
            thought=thought,
            action=action,
            action_input=action_input
        )

    def _seed_running_profile(self, result: ReActResult, task: str, context: dict | None) -> None:
        """Write one running profile_dataset row at step 0 when the steward asked to profile."""
        blob = f"{task or ''} {json.dumps(context or {}, default=str)}".lower()
        if not any(k in blob for k in ("profile", "khảo sát", "khao sat", "scan")):
            return
        dataset_key = (context or {}).get("dataset_key")
        step = ReActStep(
            step_index=0,
            thought="",
            action="profile_dataset",
            action_input={"dataset_key": dataset_key} if dataset_key else {},
        )
        self._log_trace(result.session_id, step, status="running")

    def _resolve_tool_name(self, action: str | None) -> str:
        return (action or "").replace("default_api:", "").strip()

    def _normalize_tool_name(self, name: str | None) -> str:
        return (name or "").replace("default_api:", "").strip().lower()


    def _is_hitl_stop(self, task: str, context: dict | None = None) -> bool:
        return _is_hitl_stop(task, context)

    def _allow_hitl_tool(self, name: str | None) -> bool:
        n = self._normalize_tool_name(name)
        if getattr(self, "tool_allowlist", None) is not None:
            return n in self.tool_allowlist
        return _allow_hitl_tool(name)

    def _hitl_refuse(self, task: str, context: dict | None, action: str | None) -> bool:
        n = (action or "").replace("default_api:", "").strip().lower()
        if not n or n in ("finish", "abstain", "finish_default"):
            return False
        return self._is_hitl_stop(task, context) and not self._allow_hitl_tool(action)

    def _hitl_already_proposed(self, result: ReActResult) -> bool:
        if any(is_propose_tool(getattr(s, "action", None)) for s in result.steps):
            return True
        return self._has_tool_beat(result.session_id, "propose_quality_rules")

    def _hitl_finish_after_propose(self, task: str, context: dict | None, action: str | None, observation: str | None) -> bool:
        if not self._is_hitl_stop(task, context) or not is_propose_tool(action):
            return False
        obs = observation or ""
        return not obs.startswith("Error")


    def _has_tool_beat(self, session_id: str, tool_name: str) -> bool:
        """True when this session already persisted a named beat (alias-aware)."""
        want = self._normalize_tool_name(tool_name)
        if not session_id or not want:
            return False
        aliases = {want}
        if want in ("propose_quality_rules", "quality_rule_proposer"):
            aliases.update({"propose_quality_rules", "quality_rule_proposer"})
        try:
            rows = get_db().execute(
                "SELECT tool_name, action FROM agent_traces WHERE session_id = ?",
                [session_id],
            )
            return any(
                self._normalize_tool_name(tool) in aliases
                or self._normalize_tool_name(action) in aliases
                for tool, action in rows
            )
        except Exception:
            return False

    def _skip_duplicate_propose(self, session_id: str, action: str | None) -> bool:
        """Tab/remount must not re-run Propose. Profile-then-FINISH still force-runs once."""
        name = self._normalize_tool_name(self._resolve_tool_name(action) or action)
        if name not in ("propose_quality_rules", "quality_rule_proposer"):
            return False
        return self._has_tool_beat(session_id, name)

    def _tool_meta(self, tool_name: str) -> tuple[str, str]:
        """Attach tool_title / tool_about from BaseTool.description when the tool exists."""
        title = _human_tool_title(tool_name)
        about = ""
        if not tool_name or not hasattr(self.tools, "get"):
            return title, about
        try:
            tool = self.tools.get(tool_name)
        except Exception:
            return title, about
        if tool is None:
            return title, about
        if hasattr(tool, "steward_meta"):
            meta = tool.steward_meta()
            return meta.get("tool_title") or title, meta.get("tool_about") or about
        desc = (getattr(tool, "description", None) or "").strip()
        real_name = getattr(tool, "name", tool_name) or tool_name
        return _human_tool_title(real_name), desc

    def _ensure_steward_columns(self, db) -> None:
        for col, typ in (("status", "VARCHAR"), ("tool_title", "VARCHAR"), ("tool_about", "VARCHAR")):
            try:
                db.execute(f"ALTER TABLE agent_traces ADD COLUMN {col} {typ}")
            except Exception:
                pass

    def _actor_type(self, action: str | None) -> str:
        action_l = (action or "").lower()
        blob = action_l.upper()
        if "DATA_STEWARD" in blob or "DATA STEWARD" in blob:
            return "DATA_STEWARD"
        if "EXECUTOR" in blob:
            return "EXECUTOR"
        if "L4" in blob:
            return "L4_DETECTOR"
        if "L3" in blob:
            return "L3_DETECTOR"
        if "L2" in blob:
            return "L2_DETECTOR"
        if "L1" in blob:
            return "L1_DETECTOR"
        if "C1" in blob:
            return "C1_AI"
        if "A1" in blob:
            return "A1_AI"
        if "R0" in blob:
            return "R0"
        if "profile" in action_l or "propose" in action_l or "rule" in action_l:
            return "C1_AI"
        if "detect" in action_l or "anomaly" in action_l:
            return "L1_DETECTOR"
        if "clean" in action_l or "quarantine" in action_l:
            return "EXECUTOR"
        if "hitl" in action_l or "approv" in action_l or "govern" in action_l:
            return "DATA_STEWARD"
        if "register" in action_l or "ingest" in action_l:
            return "SYSTEM"
        return "ORCHESTRATOR"

    def _log_trace(self, session_id: str, step: ReActStep, status: str | None = None):
        """Log step execution trace. Keep thought / tool_about. Upsert running → done."""
        try:
            db = get_db()
            self._ensure_steward_columns(db)
            tool_name = self._resolve_tool_name(step.action) or (step.action or "")
            if not tool_name or tool_name in ("FINISH", "ABSTAIN", "FINISH_DEFAULT"):
                return
            tool_title, tool_about = self._tool_meta(tool_name)
            thought = _pass_thought(step.thought)
            agent_type = self._actor_type(step.action or tool_name)

            output_obj = None
            if step.observation:
                try:
                    output_obj = json.loads(step.observation)
                except (json.JSONDecodeError, TypeError):
                    output_obj = None

            if status is None:
                if (step.observation or "").startswith("Error"):
                    status = "failed"
                elif step.observation:
                    status = "done"
                else:
                    status = "running"

            if status in ("running", "in_progress"):
                summary = _running_now(tool_name or step.action, step.action_input)
                output_preview = None
                duration = None
            else:
                summary = _measured_from_output(tool_name or step.action, output_obj)
                output_preview = json_preview(step.observation, 1500)
                duration = step.duration_ms

            existing = db.execute(
                "SELECT id FROM agent_traces WHERE session_id = ? AND step_index = ? "
                "AND coalesce(tool_name, action, '') = ? ORDER BY timestamp DESC LIMIT 1",
                [session_id, step.step_index, tool_name],
            )
            if not existing and self._skip_duplicate_propose(session_id, tool_name):
                return
            params_core = [
                thought,
                step.action,
                tool_name,
                json_preview(step.action_input, 1500),
                output_preview,
                summary,
                step.tokens_used,
                duration,
                status,
                tool_title,
                tool_about,
                agent_type,
            ]
            if existing:
                # Never let FINISH/ABSTAIN clobber a real tool beat (seeded Profile).
                if (step.action or "") in ("FINISH", "ABSTAIN", "FINISH_DEFAULT", ""):
                    prev = db.execute(
                        "SELECT action, tool_name FROM agent_traces WHERE id = ?",
                        [existing[0][0]],
                    )
                    prev_action = (prev[0][0] or "") if prev else ""
                    if prev_action not in ("FINISH", "ABSTAIN", "FINISH_DEFAULT", ""):
                        return
                db.execute(
                    "UPDATE agent_traces SET thought = ?, action = ?, tool_name = ?, tool_input = ?, "
                    "tool_output = ?, observation = ?, tokens_used = ?, duration_ms = ?, "
                    "status = ?, tool_title = ?, tool_about = ?, agent_type = ? WHERE id = ?",
                    params_core + [existing[0][0]],
                )
            else:
                db.execute(
                    "INSERT INTO agent_traces (id, session_id, agent_type, step_index, thought, action, "
                    "tool_name, tool_input, tool_output, observation, tokens_used, duration_ms, "
                    "status, tool_title, tool_about) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        str(uuid.uuid4())[:8],
                        session_id,
                        agent_type,
                        step.step_index,
                        thought,
                        step.action,
                        tool_name,
                        json_preview(step.action_input, 1500),
                        output_preview,
                        summary,
                        step.tokens_used,
                        duration,
                        status,
                        tool_title,
                        tool_about,
                    ],
                )
        except Exception:
            logging.getLogger(__name__).exception("agent_traces insert failed")
            try:
                db = get_db()
                db.execute(
                    "INSERT INTO agent_traces (id, session_id, agent_type, step_index, thought, action, "
                    "tool_name, tool_input, tool_output, observation, tokens_used, duration_ms, "
                    "status, tool_title, tool_about) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        str(uuid.uuid4())[:8],
                        session_id,
                        self._actor_type(step.action or ""),
                        step.step_index,
                        _pass_thought(step.thought),
                        step.action,
                        self._resolve_tool_name(step.action) or (step.action or ""),
                        None,
                        None,
                        (str(step.observation)[:280] if step.observation else _running_now(step.action, step.action_input)),
                        step.tokens_used,
                        step.duration_ms if locals().get("status") not in ("running", "in_progress") else None,
                        locals().get("status") or "done",
                        _human_tool_title(step.action),
                        "",
                    ],
                )
            except Exception:
                logging.getLogger(__name__).exception("agent_traces fallback insert failed")

    def detect_anomalies(self, current_profile: dict, baseline_profile: dict | None = None) -> Any:
        from src.agents.sub_agents import AnomalyDetectorAgent
        agent = AnomalyDetectorAgent(llm_service=self.llm)
        return agent.run(current_profile=current_profile, baseline_profile=baseline_profile)

    def diagnose(self, data_profile: dict, anomaly_context: dict | None = None) -> Any:
        from src.agents.sub_agents import DiagnosisAgent
        agent = DiagnosisAgent(llm_service=self.llm)
        return agent.run(data_profile=data_profile, anomaly_context=anomaly_context)


BoundedReActEngine = ReActEngine

