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

# Prefer these when present — never force Orchestrator over a real actor.
_EXPLICIT_ACTORS = (
    ("DATA_STEWARD", "DATA_STEWARD"),
    ("DATA STEWARD", "DATA_STEWARD"),
    ("EXECUTOR", "EXECUTOR"),
    ("L4", "L4_DETECTOR"),
    ("L3", "L3_DETECTOR"),
    ("L2", "L2_DETECTOR"),
    ("L1", "L1_DETECTOR"),
    ("C1", "C1_AI"),
    ("A1", "A1_AI"),
    ("R0", "R0"),
)


def _redact_thought(text: str) -> str:
    """Apply course AI LOG redaction; never invent a thought."""
    try:
        import importlib.util
        from pathlib import Path

        script = Path(__file__).resolve().parents[2] / "scripts" / "ai_log_redact.py"
        spec = importlib.util.spec_from_file_location("ai_log_redact", script)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.redact_text(text)
    except Exception:
        pass
    import re

    return re.sub(r"\bsk-[A-Za-z0-9_-]{20,}", "[REDACTED:api_key]", text)


def _pass_through_thought(value: Any) -> str | None:
    """Keep stored thought if present; never invent; never coerce empty to a fake."""
    if value is None:
        return None
    text = str(value).strip()
    return _redact_thought(text) if text else None


def _human_tool_title(name: str | None) -> str:
    return (name or "").replace("_", " ").strip().capitalize()


def _tool_catalog() -> dict[str, tuple[str, str]]:
    """tool_name → (title, about) from real BaseTool.description class attrs."""
    classes: list[type] = []
    try:
        from src.tools.chat_tools import (
            CleanDatabaseTool,
            ListDatasetsTool,
            ProfileDatasetTool,
            ProposeQualityRulesTool,
        )
        classes.extend([ListDatasetsTool, ProfileDatasetTool, ProposeQualityRulesTool, CleanDatabaseTool])
    except Exception:
        pass
    try:
        from src.tools.profiler import DataProfilerTool
        classes.append(DataProfilerTool)
    except Exception:
        pass
    try:
        from src.tools.anomaly_detector import AnomalyDetectorTool
        classes.append(AnomalyDetectorTool)
    except Exception:
        pass
    try:
        from src.tools.telemetry_query import TelemetryQueryTool
        classes.append(TelemetryQueryTool)
    except Exception:
        pass
    try:
        from src.tools.rule_proposer import RuleProposerTool
        classes.append(RuleProposerTool)
    except Exception:
        pass
    try:
        from src.tools.rule_executor import RuleExecutorTool
        classes.append(RuleExecutorTool)
    except Exception:
        pass
    try:
        from src.tools.algolia_tool import AlgoliaSearchTool
        classes.append(AlgoliaSearchTool)
    except Exception:
        pass
    try:
        from src.tools.nlp_extractor import NLPExtractorTool
        classes.append(NLPExtractorTool)
    except Exception:
        pass
    out: dict[str, tuple[str, str]] = {}
    for cls in classes:
        name = getattr(cls, "name", "") or ""
        desc = (getattr(cls, "description", "") or "").strip()
        if name:
            out[name] = (_human_tool_title(name), desc)
    return out


_TOOL_META = _tool_catalog()


def _tool_title_about(tool_name: str | None, stored_title: Any = None, stored_about: Any = None) -> tuple[str | None, str | None]:
    title = str(stored_title).strip() if stored_title else None
    about = str(stored_about).strip() if stored_about else None
    if tool_name and tool_name in _TOOL_META:
        cat_title, cat_about = _TOOL_META[tool_name]
        title = title or cat_title
        about = about or cat_about
    if not title and tool_name:
        title = _human_tool_title(tool_name)
    return title, about


def _actor_kind(action: str | None, tool: str | None, agent_type: str | None) -> str:
    blob = f"{action or ''} {tool or ''} {agent_type or ''}".lower()
    for needle, kind in _ACTOR_BY_ACTION:
        if needle in blob:
            return kind
    if agent_type and agent_type.lower() not in ("canonical_react_engine", "unknown", ""):
        return agent_type
    return "ORCHESTRATOR"


def _prefer_actor(action: str | None, tool: str | None, agent_type: str | None) -> str:
    blob = f"{agent_type or ''} {action or ''} {tool or ''}".upper()
    for needle, kind in _EXPLICIT_ACTORS:
        if needle in blob:
            return kind
    return _actor_kind(action, tool, agent_type)


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


def _num(src: dict, *keys: str) -> int | float | None:
    for key in keys:
        val = src.get(key)
        if isinstance(val, bool):
            continue
        if isinstance(val, (int, float)):
            return val
    return None


def _measured_summary(action: str | None, observation: str | None, output: Any, tool_title: str | None = None) -> str:
    if observation and str(observation).strip():
        text = str(observation).strip()
        if "completed" not in text.lower() or "SoC" in text or "rows" in text.lower():
            if not text.lower().endswith(" completed"):
                return text[:280]
    data = output if isinstance(output, dict) else {}
    prof = data.get("profile") if isinstance(data.get("profile"), dict) else {}
    merged = {**prof, **data}
    exec_res = data.get("execution_result") if isinstance(data.get("execution_result"), dict) else {}
    merged.update(exec_res)

    parts: list[str] = []
    rows = _num(merged, "total_rows", "sample_size", "row_count", "total_processed")
    soc = _num(merged, "warehouse_soc_below_zero")
    open_n = _num(merged, "warehouse_open_incidents")
    cols = _num(merged, "columns_count")
    health = _num(merged, "health_score", "data_health_score")
    if rows is not None:
        parts.append(f"{int(rows):,} rows")
    if soc is not None and soc:
        parts.append(f"{int(soc)} SoC<0")
    if open_n is not None and open_n:
        parts.append(f"{int(open_n)} OPEN")
    if cols is not None:
        parts.append(f"{int(cols)} columns")
    if health is not None and not soc and not open_n:
        parts.append(f"health {health}")
    proposals = data.get("proposals")
    if isinstance(proposals, list):
        parts.append(f"{len(proposals)} rules")
    elif _num(data, "count") is not None and "propose" in (action or "").lower():
        parts.append(f"{int(_num(data, 'count'))} rules")
    if _num(exec_res, "quarantine_count") is not None:
        parts.append(f"{int(exec_res['quarantine_count']):,} quarantined")
    if _num(exec_res, "clean_count") is not None:
        parts.append(f"{int(exec_res['clean_count']):,} clean")
    flags = data.get("quality_flags") or prof.get("quality_flags")
    if isinstance(flags, list) and flags:
        parts.append(f"{len(flags)} flags")
    if parts:
        return " · ".join(parts)
    label = tool_title or _human_tool_title(action) or "step"
    return f"{label} finished"


def _infer_status(stored: Any, output: Any, observation: str | None) -> str:
    if stored:
        raw = str(stored).strip().lower()
        if raw in ("running", "in_progress"):
            return "running"
        if raw in ("failed", "error"):
            return "failed"
        if raw in ("done", "completed", "success"):
            return "done"
    if observation and str(observation).lower().startswith("error"):
        return "failed"
    if output is None and not (observation and str(observation).strip()):
        return "running"
    return "done"


def _in_range(ts: Any, since: datetime | None) -> bool:
    if since is None or not ts:
        return True
    try:
        parsed = datetime.fromisoformat(str(ts).replace("Z", "+00:00").replace(" ", "T")[:26])
        return parsed.replace(tzinfo=None) >= since.replace(tzinfo=None)
    except ValueError:
        return True


def ensure_steward_trace_columns(db) -> None:
    for col, typ in (("status", "VARCHAR"), ("tool_title", "VARCHAR"), ("tool_about", "VARCHAR")):
        try:
            db.execute(f"ALTER TABLE agent_traces ADD COLUMN {col} {typ}")
        except Exception:
            pass


def normalize_trace_step(row: tuple, agent_type: str | None = None) -> dict:
    """Map agent_traces row → steward card fields (aliases + honest measured Done)."""
    step_index, thought, action, tool_name, tool_input, tool_output, observation, tokens, duration_ms, timestamp = row[:10]
    extra_agent = row[10] if len(row) > 10 else agent_type
    stored_status = row[11] if len(row) > 11 else None
    stored_title = row[12] if len(row) > 12 else None
    stored_about = row[13] if len(row) > 13 else None
    output = _parse_json(tool_output)
    tool = tool_name or action
    title, about = _tool_title_about(tool, stored_title, stored_about)
    status = _infer_status(stored_status, output, observation)
    return {
        "step": step_index,
        "action": action,
        "tool": tool,
        "tool_name": tool_name or action,
        "tool_title": title,
        "tool_about": about,
        "input": _parse_json(tool_input),
        "output": output,
        "observation": observation,
        "tokens": tokens,
        "tokens_used": tokens,
        "duration_ms": duration_ms,
        "timestamp": str(timestamp) if timestamp else None,
        "actor_kind": _prefer_actor(action, tool, extra_agent),
        "agent_type": extra_agent,
        "summary_done": _measured_summary(action, observation, output, title),
        "thought": _pass_through_thought(thought),
        "status": status,
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
    ensure_steward_trace_columns(db)
    steps = db.execute(
        "SELECT step_index, thought, action, tool_name, tool_input, tool_output, "
        "observation, tokens_used, duration_ms, timestamp, agent_type, "
        "status, tool_title, tool_about "
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
        if not include_thought:
            # Thought is still returned (steward Technical detail), never invented.
            pass
        if _in_range(card.get("timestamp"), since_dt):
            normalized.append(card)
    return {"session_id": session_id, "steps": normalized}
