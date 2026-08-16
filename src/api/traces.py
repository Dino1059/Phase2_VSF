from fastapi import APIRouter
from src.db.connection import get_db

traces_router = APIRouter(prefix="/traces", tags=["Traces"])


@traces_router.get("/")
async def list_sessions(limit: int = 20):
    db = get_db()
    sessions = db.execute(f"SELECT session_id, agent_type, COUNT(*) as steps, SUM(tokens_used) as total_tokens, MIN(timestamp) as started FROM agent_traces GROUP BY session_id, agent_type ORDER BY started DESC LIMIT {limit}")
    return {"sessions": [
        {"session_id": s[0], "agent_type": s[1], "steps": s[2], "total_tokens": s[3], "started": str(s[4]) if s[4] else None}
        for s in sessions
    ]}


@traces_router.get("/{session_id}")
async def get_trace(session_id: str):
    db = get_db()
    steps = db.execute("SELECT step_index, thought, action, tool_name, tool_input, tool_output, tokens_used, duration_ms, timestamp FROM agent_traces WHERE session_id = ? ORDER BY step_index", [session_id])
    return {"session_id": session_id, "steps": [
        {"step": s[0], "thought": s[1], "action": s[2], "tool": s[3], "input": s[4], "output": s[5], "tokens": s[6], "duration_ms": s[7], "timestamp": str(s[8]) if s[8] else None}
        for s in steps
    ]}
