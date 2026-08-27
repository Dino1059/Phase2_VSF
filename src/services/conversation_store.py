import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from src.db.connection import get_db


class ConversationStore:
    def __init__(self, db=None):
        self._db = db

    @property
    def db(self):
        if self._db is None:
            self._db = get_db()
        return self._db

    def save_message(self, message: Dict[str, Any], session_id: str = "default") -> Dict[str, Any]:
        msg_id = message.get("id") or f"msg_{int(datetime.now().timestamp()*1000)}"
        timestamp = message.get("timestamp") or datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(message.get("metadata") or {})

        conn = self.db.get_connection()
        values = [
            msg_id,
            session_id,
            message.get("type", "user"),
            message.get("agentId"),
            message.get("content", ""),
            metadata_json,
            timestamp
        ]
        existing = conn.execute("SELECT 1 FROM messages WHERE id = ? LIMIT 1", [msg_id]).fetchall()
        if existing:
            try:
                conn.execute(
                    """
                    UPDATE messages
                    SET session_id = ?, type = ?, agent_id = ?, content = ?, metadata_json = ?, timestamp = ?
                    WHERE id = ?
                    """,
                    [session_id, values[2], values[3], values[4], metadata_json, timestamp, msg_id],
                )
            except Exception:
                try:
                    conn.execute("DELETE FROM messages WHERE id = ?", [msg_id])
                except Exception:
                    pass
                try:
                    conn.execute(
                        """
                        INSERT INTO messages (id, session_id, type, agent_id, content, metadata_json, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        values,
                    )
                except Exception:
                    pass
        else:
            try:
                conn.execute(
                    """
                    INSERT INTO messages (id, session_id, type, agent_id, content, metadata_json, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
            except Exception:
                pass

        return {
            "id": msg_id,
            "session_id": session_id,
            "type": message.get("type", "user"),
            "agentId": message.get("agentId"),
            "content": message.get("content", ""),
            "metadata": message.get("metadata") or {},
            "timestamp": timestamp
        }

    def get_messages(self, session_id: str = "default", limit: int = 100) -> List[Dict[str, Any]]:
        conn = self.db.get_connection()
        rows = conn.execute("""
            SELECT id, session_id, type, agent_id, content, metadata_json, timestamp
            FROM messages
            WHERE session_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
        """, [session_id, limit]).fetchall()

        result = []
        for r in rows:
            meta = {}
            if r[5]:
                try:
                    meta = json.loads(r[5])
                except Exception:
                    meta = {}
            item = {
                "id": r[0],
                "type": r[2],
                "content": r[4],
                "timestamp": r[6]
            }
            if r[3]:
                item["agentId"] = r[3]
            if meta:
                item["metadata"] = meta
            result.append(item)
        return result

    def clear_messages(self, session_id: str = "default"):
        conn = self.db.get_connection()
        conn.execute("DELETE FROM messages WHERE session_id = ?", [session_id])

    def list_sessions(self) -> List[Dict[str, Any]]:
        conn = self.db.get_connection()
        rows = conn.execute("""
            SELECT session_id, COUNT(*) as msg_count, MAX(timestamp) as last_updated
            FROM messages
            GROUP BY session_id
            ORDER BY last_updated DESC
        """).fetchall()

        result = []
        for r in rows:
            sid = r[0]
            cnt = r[1]
            last_up = r[2]

            first_msg = conn.execute("""
                SELECT content FROM messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT 1
            """, [sid]).fetchone()
            raw_title = first_msg[0] if first_msg and first_msg[0] else "New Agent Chat"
            clean_title = raw_title.replace("\n", " ").strip()
            if len(clean_title) > 35:
                clean_title = clean_title[:32] + "..."
            result.append({
                "session_id": sid,
                "msg_count": cnt,
                "last_updated": last_up,
                "title": clean_title,
            })
        return result

    def clear_all(self):
        conn = self.db.get_connection()
        try:
            conn.execute("DROP TABLE IF EXISTS messages")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id VARCHAR PRIMARY KEY,
                    session_id VARCHAR,
                    type VARCHAR,
                    agent_id VARCHAR,
                    content TEXT,
                    metadata_json TEXT,
                    timestamp VARCHAR
                )
            """)
        except Exception:
            pass


conversation_store = ConversationStore()
