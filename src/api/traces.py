import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from src.db.connection import get_db


traces_router = APIRouter(prefix="/traces", tags=["Traces"])


class WorkflowTraceEvent(BaseModel):
    trace_id: str
    run_id: str | None = None
    session_id: str | None = None
    dataset_key: str | None = None
    incident_id: str | None = None
    stage: str
    actor: str
    action: str
    tool_name: str | None = None
    status: str
    started_at: str
    ended_at: str | None = None
    duration_ms: int | None = None
    input_ref_ids: list[str] = Field(default_factory=list)
    output_ref_ids: list[str] = Field(default_factory=list)
    input_tokens_estimated: int | None = None
    output_tokens: int | None = None
    provider: str | None = None
    model: str | None = None
    fallback_depth: int = 0
    context_items_included: int | None = None
    context_items_dropped: int | None = None
    validation_status: str | None = None
    error_code: str | None = None
    safe_summary: str


_ACTOR_BY_ACTION = (
    ("profile", "PROFILER"),
    ("propose", "PROPOSER"),
    ("rule", "PROPOSER"),
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
    for col, typ in (
        ("status", "VARCHAR"),
        ("tool_title", "VARCHAR"),
        ("tool_about", "VARCHAR"),
        ("safe_summary", "VARCHAR"),
        ("provider", "VARCHAR"),
        ("model", "VARCHAR"),
        ("fallback_depth", "INT"),
        ("input_tokens_estimated", "INT"),
        ("output_tokens", "INT"),
        ("context_items_included", "INT"),
        ("context_items_dropped", "INT"),
        ("validation_status", "VARCHAR"),
        ("stage", "VARCHAR"),
        ("actor", "VARCHAR"),
        ("error_code", "VARCHAR"),
    ):
        try:
            db.execute(f"ALTER TABLE agent_traces ADD COLUMN {col} {typ}")
        except Exception:
            pass


def _row_get(row: tuple, idx: int, default=None):
    return row[idx] if len(row) > idx else default


def normalize_trace_step(row: tuple, agent_type: str | None = None) -> dict:
    """Map agent_traces row → steward card fields (aliases + honest measured Done)."""
    # Flexible: base cols then optional steward/workflow cols
    step_index = _row_get(row, 0)
    thought = _row_get(row, 1)
    action = _row_get(row, 2)
    tool_name = _row_get(row, 3)
    tool_input = _row_get(row, 4)
    tool_output = _row_get(row, 5)
    observation = _row_get(row, 6)
    tokens = _row_get(row, 7)
    duration_ms = _row_get(row, 8)
    timestamp = _row_get(row, 9)
    extra_agent = _row_get(row, 10, agent_type)
    stored_status = _row_get(row, 11)
    stored_title = _row_get(row, 12)
    stored_about = _row_get(row, 13)
    safe_summary_col = _row_get(row, 14)
    provider = _row_get(row, 15)
    model = _row_get(row, 16)
    fallback_depth = _row_get(row, 17) or 0
    input_tokens_estimated = _row_get(row, 18)
    output_tokens = _row_get(row, 19)
    context_items_included = _row_get(row, 20)
    context_items_dropped = _row_get(row, 21)
    validation_status = _row_get(row, 22)
    stage = _row_get(row, 23)
    actor = _row_get(row, 24)
    error_code = _row_get(row, 25)

    output = _parse_json(tool_output)
    tool = tool_name or action
    title, about = _tool_title_about(tool, stored_title, stored_about)
    status = _infer_status(stored_status, output, observation)
    # Map legacy thought → safe_summary when new column is null
    legacy = _pass_through_thought(thought)
    safe_summary = _pass_through_thought(safe_summary_col) or legacy or ""
    if isinstance(output, dict):
        provider = provider or output.get("provider")
        model = model or output.get("model") or output.get("model_used")
        if output.get("fallback_depth") is not None and not fallback_depth:
            fallback_depth = output.get("fallback_depth") or 0
        validation_status = validation_status or output.get("validation_status")
        context_items_included = context_items_included if context_items_included is not None else output.get("context_items_included")
        context_items_dropped = context_items_dropped if context_items_dropped is not None else output.get("context_items_dropped")
        input_tokens_estimated = input_tokens_estimated if input_tokens_estimated is not None else output.get("input_tokens_estimated")
        output_tokens = output_tokens if output_tokens is not None else output.get("output_tokens")
    actor_kind = actor or _prefer_actor(action, tool, extra_agent)
    stage_val = stage or (action or tool or "workflow")
    return {
        "step": step_index,
        "action": action,
        "stage": stage_val,
        "tool": tool,
        "tool_name": tool_name or action,
        "tool_title": title,
        "tool_about": about,
        "input": _parse_json(tool_input),
        "output": output,
        "observation": observation,
        "tokens": tokens,
        "tokens_used": tokens,
        "input_tokens_estimated": input_tokens_estimated,
        "output_tokens": output_tokens if output_tokens is not None else tokens,
        "duration_ms": duration_ms,
        "timestamp": str(timestamp) if timestamp else None,
        "actor_kind": actor_kind,
        "actor": actor_kind,
        "agent_type": extra_agent,
        "summary_done": _measured_summary(action, observation, output, title),
        "safe_summary": safe_summary,
        "provider": provider,
        "model": model,
        "fallback_depth": int(fallback_depth or 0),
        "context_items_included": context_items_included,
        "context_items_dropped": context_items_dropped,
        "validation_status": validation_status,
        "error_code": error_code,
        "status": status,
    }


def to_workflow_trace_event(card: dict, *, trace_id: str | None = None, session_id: str | None = None) -> WorkflowTraceEvent:
    """Build a WorkflowTraceEvent from a normalized steward card."""
    started = str(card.get("timestamp") or datetime.utcnow().isoformat())
    return WorkflowTraceEvent(
        trace_id=trace_id or f"tr_{card.get('step')}_{started}",
        run_id=card.get("run_id"),
        session_id=session_id or card.get("session_id"),
        dataset_key=card.get("dataset_key"),
        incident_id=card.get("incident_id"),
        stage=str(card.get("stage") or card.get("action") or "workflow"),
        actor=str(card.get("actor") or card.get("actor_kind") or "ORCHESTRATOR"),
        action=str(card.get("action") or card.get("tool_name") or ""),
        tool_name=card.get("tool_name") or card.get("tool"),
        status=str(card.get("status") or "done"),
        started_at=started,
        ended_at=card.get("ended_at"),
        duration_ms=card.get("duration_ms"),
        input_ref_ids=list(card.get("input_ref_ids") or []),
        output_ref_ids=list(card.get("output_ref_ids") or []),
        input_tokens_estimated=card.get("input_tokens_estimated"),
        output_tokens=card.get("output_tokens") if card.get("output_tokens") is not None else card.get("tokens"),
        provider=card.get("provider"),
        model=card.get("model"),
        fallback_depth=int(card.get("fallback_depth") or 0),
        context_items_included=card.get("context_items_included"),
        context_items_dropped=card.get("context_items_dropped"),
        validation_status=card.get("validation_status"),
        error_code=card.get("error_code"),
        safe_summary=str(card.get("safe_summary") or ""),
    )


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


_TRACE_BASE_COLS = (
    "step_index, thought, action, tool_name, tool_input, tool_output, "
    "observation, tokens_used, duration_ms, timestamp, agent_type"
)

_TRACE_EXTRA_COLS = (
    "status, tool_title, tool_about, safe_summary, provider, model, fallback_depth, "
    "input_tokens_estimated, output_tokens, context_items_included, context_items_dropped, "
    "validation_status, stage, actor, error_code"
)


def workspace_trace_sessions(session_id: str) -> list[str]:
    """dataset:vingroup_pilot <-> vingroup_pilot. Keep the workspace id the run used."""
    sid = (session_id or "").strip()
    out: list[str] = []
    def add(value: str) -> None:
        value = (value or "").strip()
        if value and value not in out:
            out.append(value)
    add(sid)
    if sid.startswith("dataset:"):
        add(sid.split(":", 1)[1])
    elif sid:
        add(f"dataset:{sid}")
    return out


def _dataset_key_from_session(session_id: str) -> str | None:
    sid = (session_id or "").strip()
    if sid.startswith("dataset:"):
        key = sid.split(":", 1)[1].strip()
        return key or None
    if sid and ":" not in sid:
        return sid
    return None


def _fetch_trace_rows(db, session_id: str):
    ensure_steward_trace_columns(db)
    try:
        return db.execute(
            f"SELECT {_TRACE_BASE_COLS}, {_TRACE_EXTRA_COLS} "
            "FROM agent_traces WHERE session_id = ? ORDER BY step_index",
            [session_id],
        )
    except Exception:
        try:
            return db.execute(
                f"SELECT {_TRACE_BASE_COLS}, status, tool_title, tool_about "
                "FROM agent_traces WHERE session_id = ? ORDER BY step_index",
                [session_id],
            )
        except Exception:
            return db.execute(
                f"SELECT {_TRACE_BASE_COLS} FROM agent_traces WHERE session_id = ? ORDER BY step_index",
                [session_id],
            )


def _latest_session_for_dataset(db, dataset_key: str) -> str | None:
    if not dataset_key:
        return None
    try:
        rows = db.execute(
            "SELECT session_id FROM agent_traces "
            "WHERE session_id = ? OR session_id = ? OR session_id LIKE ? "
            "ORDER BY timestamp DESC LIMIT 1",
            [f"dataset:{dataset_key}", dataset_key, f"dataset:{dataset_key}%"],
        )
        return rows[0][0] if rows else None
    except Exception:
        return None


_PIPELINE_TRACE_TOOLS = frozenset({
    "profile_dataset", "detect_anomalies", "propose_quality_rules",
    "quality_rule_proposer", "anomaly_detector",
})


def _rows_have_pipeline_beat(rows) -> bool:
    for r in rows or []:
        action = str(r[2] or "").strip().lower()
        tool = str(r[3] or "").strip().lower()
        if tool in _PIPELINE_TRACE_TOOLS or action in _PIPELINE_TRACE_TOOLS:
            return True
    return False


def _drop_notify_skip_rows(rows):
    """Hide stale _notify skip beats when real detect/propose rows exist."""
    kept = []
    for r in rows or []:
        tool = str(r[3] or "").strip().lower()
        obs = str(r[6] or "")
        if tool == "anomaly_detect" and ("No signal config" in obs or "Skipping L1-L4" in obs):
            continue
        kept.append(r)
    return kept


def resolve_trace_rows(db, session_id: str):
    """Return (resolved_session_id, rows). Prefer real Run All beats over skip/notify rows."""
    notify_fallback = None
    for sid in workspace_trace_sessions(session_id):
        rows = _fetch_trace_rows(db, sid)
        if not rows:
            continue
        if _rows_have_pipeline_beat(rows):
            return sid, _drop_notify_skip_rows(rows) or rows
        if notify_fallback is None:
            notify_fallback = (sid, rows)
    key = _dataset_key_from_session(session_id)
    latest = _latest_session_for_dataset(db, key) if key else None
    if latest:
        rows = _fetch_trace_rows(db, latest)
        if rows and _rows_have_pipeline_beat(rows):
            return latest, _drop_notify_skip_rows(rows) or rows
    if notify_fallback:
        return notify_fallback
    return session_id, []



def attach_msg_ids(db, session_id: str, cards: list[dict]) -> list[dict]:
    """Stamp msgId from chat messages whose agent_id is the beat tool. Never invent ids."""
    if not cards:
        return cards
    ids = workspace_trace_sessions(session_id)
    rows = []
    for sid in ids:
        try:
            found = db.execute(
                "SELECT id, agent_id FROM messages WHERE session_id = ? ORDER BY timestamp",
                [sid],
            )
        except Exception:
            found = []
        rows.extend(found or [])
    by_tool: dict[str, str] = {}
    for mid, agent in rows:
        if mid and agent:
            by_tool[str(agent)] = str(mid)
    if not by_tool:
        return cards
    for card in cards:
        if card.get("msgId") or card.get("msg_id") or card.get("message_id"):
            continue
        tool = str(card.get("tool_name") or card.get("tool") or card.get("action") or "")
        if tool and tool in by_tool:
            card["msgId"] = by_tool[tool]
            card["msg_id"] = by_tool[tool]
    return cards


@traces_router.get("/{session_id}")
async def get_trace(
    session_id: str,
    since: str | None = Query(default=None, description="ISO timestamp lower bound"),
    include_thought: bool = Query(default=False, description="Instructor-only raw thought"),
):
    db = get_db()
    resolved, steps = resolve_trace_rows(db, session_id)
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            since_dt = None
    normalized = []
    unfiltered = []
    for row in steps:
        card = normalize_trace_step(row)
        if not include_thought:
            # Thought is still returned (steward Technical detail), never invented.
            pass
        action = (card.get("action") or card.get("tool_name") or card.get("tool") or "").strip()
        if action in ("FINISH", "ABSTAIN", "FINISH_DEFAULT") or not action:
            continue
        unfiltered.append(card)
        if _in_range(card.get("timestamp"), since_dt):
            normalized.append(card)
    # Clock/tz mismatch must not hide beats the workspace session already wrote.
    if since_dt and not normalized and unfiltered:
        normalized = unfiltered
    normalized = attach_msg_ids(db, resolved, normalized)
    return {"session_id": resolved, "steps": normalized}


@traces_router.get("/{session_id}/timeline")
async def session_timeline(
    session_id: str,
    since: str | None = Query(default=None),
):
    """Scoped session events. Never invent CoT. Execute off."""
    body = await get_trace(session_id, since=since, include_thought=False)
    events = []
    for card in body.get("steps") or []:
        events.append(
            {
                "session_id": body.get("session_id"),
                "action": card.get("action") or card.get("tool_name"),
                "actor_kind": card.get("actor_kind"),
                "summary": card.get("summary_done") or card.get("summary") or card.get("observation"),
                "status": card.get("status"),
                "timestamp": card.get("timestamp"),
                "safe_summary": card.get("safe_summary") or _pass_through_thought(card.get("thought")),
            }
        )
    return {
        "session_id": body.get("session_id"),
        "events": events,
        "cot": False,
        "execute": "off",
    }
