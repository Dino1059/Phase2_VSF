import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "conversations.db")

class ConversationStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    agent_id TEXT,
                    content TEXT NOT NULL,
                    metadata_json TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, timestamp)
            """)
            conn.commit()

    def save_message(self, message: Dict[str, Any], session_id: str = "default") -> Dict[str, Any]:
        msg_id = message.get("id") or f"msg_{int(datetime.now().timestamp()*1000)}"
        timestamp = message.get("timestamp") or datetime.now().isoformat()
        metadata_json = json.dumps(message.get("metadata") or {})

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO messages (id, session_id, type, agent_id, content, metadata_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                msg_id,
                session_id,
                message.get("type", "user"),
                message.get("agentId"),
                message.get("content", ""),
                metadata_json,
                timestamp
            ))
            conn.commit()

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
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, session_id, type, agent_id, content, metadata_json, timestamp
                FROM messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
            """, (session_id, limit))
            rows = cursor.fetchall()

        result = []
        for r in rows:
            meta = {}
            if r["metadata_json"]:
                try:
                    meta = json.loads(r["metadata_json"])
                except Exception:
                    meta = {}
            item = {
                "id": r["id"],
                "type": r["type"],
                "content": r["content"],
                "timestamp": r["timestamp"]
            }
            if r["agent_id"]:
                item["agentId"] = r["agent_id"]
            if meta:
                item["metadata"] = meta
            result.append(item)
        return result

    def clear_messages(self, session_id: str = "default"):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.commit()

conversation_store = ConversationStore()
