import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query

from src.db.connection import get_db

traces_router = APIRouter(prefix="/traces", tags=["Traces"])

_ACTOR_BY_ACTION = (
    ("profile", "C1_AI"),
    ("propose", "C1_AI"),
    ("rule", "C1_AI"),
    ("detect", "L1_DETECTOR"),
    ("anomaly", "L1_DETECTOR"),
    ("clean", "EXECUTOR"),
    ("quarantine", "EXECUTOR"),
    ("hitl", "DATA_STEWARD"),
    ("govern", "DATA_STEWARD"),
    ("approv", "DATA_STEWARD"),
    ("register", "SYSTEM"),
    ("ingest", "SYSTEM"),
)


def _actor_kind(action: str | None, tool: str | None, agent_type: str | None) -> str:
    blob = f"{action or ''} {tool or ''} {agent_type or ''}".lower()
    for needle, kind in _ACTOR_BY_ACTION:
        if needle in blob:
            return kind
    if agent_type and agent_type.lower() not in ("canonical_react_engine", "unknown", ""):
        return "ORCHESTRATOR"
    return "ORCHESTRATOR"


def _parse_json(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _summarize(action: str | None, observation: str | None, output: Any) -> str:
    if observation and str(observation).strip():
        return str(observation).strip()[:280]
    if isinstance(output, dict):
        parts = []
        for key in ("total_rows", "sample_size", "columns_count", "count", "health_score"):
            if output.get(key) is not None:
                parts.append(f"{key}={output[key]}")
        flags = output.get("profile", {}).get("quality_flags") if isinstance(output.get("profile"), dict) else output.get("quality_flags")
        if isinstance(flags, list) and flags:
            parts.append(f"flags={len(flags)}")
        proposals = output.get("proposals")
        if isinstance(proposals, list) and proposals:
            parts.append(f"proposals={len(proposals)}")
        if parts:
            return " · ".join(parts)
        status = output.get("status")
        if status:
            return f"{action or 'step'} {status}"
    if isinstance(output, str) and output.strip():
        return output.strip()[:280]
    return (action or "step") + " completed" if action else ""


def _in_range(ts: Any, since: datetime | None) -> bool:
    if since is None or not ts:
        return True
    try:
        parsed = datetime.fromisoformat(str(ts).replace("Z", "+00:00").replace(" ", "T")[:26])
        return parsed.replace(tzinfo=None) >= since.replace(tzinfo=None)
    except ValueError:
        return True


def normalize_trace_step(row: tuple, agent_type: str | None = None) -> dict:
    """Map agent_traces row → steward card fields (aliases + honest Done)."""
    step_index, thought, action, tool_name, tool_input, tool_output, observation, tokens, duration_ms, timestamp = row[:10]
    extra_agent = row[10] if len(row) > 10 else agent_type
    output = _parse_json(tool_output)
    tool = tool_name or action
    return {
        "step": step_index,
        "action": action,
        "tool": tool,
        "tool_name": tool_name,
        "input": _parse_json(tool_input),
        "output": output,
        "observation": observation,
        "tokens": tokens,
        "tokens_used": tokens,
        "duration_ms": duration_ms,
        "timestamp": str(timestamp) if timestamp else None,
        "actor_kind": _actor_kind(action, tool, extra_agent),
        "agent_type": extra_agent,
        "summary_done": _summarize(action, observation, output),
        "thought": None,
        "status": "COMPLETED",
    }


@traces_router.get("/")
async def list_sessions(limit: int = 20):
    db = get_db()
    sessions = db.execute(
        "SELECT session_id, agent_type, COUNT(*) as steps, SUM(tokens_used) as total_tokens, "
        "MIN(timestamp) as started FROM agent_traces GROUP BY session_id, agent_type "
        "ORDER BY started DESC LIMIT ?",
        [limit],
    )
    return {"sessions": [
        {"session_id": s[0], "agent_type": s[1], "steps": s[2], "total_tokens": s[3],
         "started": str(s[4]) if s[4] else None}
        for s in sessions
    ]}


@traces_router.get("/{session_id}")
async def get_trace(
    session_id: str,
    since: str | None = Query(default=None, description="ISO timestamp lower bound"),
    include_thought: bool = Query(default=False, description="Instructor-only raw thought"),
):
    db = get_db()
    steps = db.execute(
        "SELECT step_index, thought, action, tool_name, tool_input, tool_output, "
        "observation, tokens_used, duration_ms, timestamp, agent_type "
        "FROM agent_traces WHERE session_id = ? ORDER BY step_index",
        [session_id],
    )
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            since_dt = None
    normalized = []
    for row in steps:
        card = normalize_trace_step(row)
        if include_thought:
            card["thought"] = row[1]
        if _in_range(card.get("timestamp"), since_dt):
            normalized.append(card)
    return {"session_id": session_id, "steps": normalized}
