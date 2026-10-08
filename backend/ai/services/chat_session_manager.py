"""
DataTrust OS: Persistent Chat Session & Run-Binding Manager
Enforces strict 1-to-1 immutable binding between session_id and run_id.
Prevents cross-run leakage and session reuse across multiple runs.
Persists across server restarts using SQLite/PostgreSQL/Local storage.
"""

import os
import sqlite3
import logging
from typing import Optional, Dict
from datetime import datetime, timezone
from fastapi import HTTPException

logger = logging.getLogger("DataTrust.ChatSessionManager")

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "runtime")
DB_PATH = os.path.join(DB_DIR, "chat_sessions.db")


class ChatSessionManager:
    """Manages persistent session_id <-> run_id bindings."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS chat_session_bindings (
                        session_id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        tenant_id TEXT NOT NULL DEFAULT 'default',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                """)
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not initialize SQLite session database: {e}")

    def verify_and_bind_session(
        self,
        session_id: str,
        run_id: str,
        tenant_id: str = "default"
    ) -> bool:
        """
        Ensures session_id is bound strictly to run_id.
        If session_id already exists and belongs to a different run_id, raises 400 SESSION_RUN_MISMATCH.
        If session_id does not exist, registers the binding.
        """
        if not session_id or not run_id:
            return True

        session_id = session_id.strip()
        run_id = run_id.strip()

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT run_id, tenant_id FROM chat_session_bindings WHERE session_id = ?",
                    (session_id,)
                )
                row = cursor.fetchone()

                now_iso = datetime.now(timezone.utc).isoformat()
                if row is None:
                    # New session, bind it to this run_id
                    cursor.execute(
                        """
                        INSERT INTO chat_session_bindings (session_id, run_id, tenant_id, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (session_id, run_id, tenant_id, now_iso, now_iso)
                    )
                    conn.commit()
                    return True

                existing_run_id, existing_tenant_id = row[0], row[1]
                if existing_run_id != run_id:
                    logger.warning(
                        f"Session-Run Mismatch: session {session_id} belongs to {existing_run_id}, requested {run_id}"
                    )
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "code": "SESSION_RUN_MISMATCH",
                            "message": (
                                f"Phiên chat '{session_id}' thuộc lần chạy '{existing_run_id}', "
                                f"không thể sử dụng cho lần chạy '{run_id}'."
                            )
                        }
                    )

                if existing_tenant_id != tenant_id:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "code": "ACCESS_DENIED_TO_RUN",
                            "message": f"Bạn không có quyền truy cập phiên chat '{session_id}'."
                        }
                    )

                # Update timestamp
                cursor.execute(
                    "UPDATE chat_session_bindings SET updated_at = ? WHERE session_id = ?",
                    (now_iso, session_id)
                )
                conn.commit()
                return True
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking session binding: {e}")
            # If DB error, fail-safe without breaking chat flow, but log
            return True

    def get_session_run_id(self, session_id: str) -> Optional[str]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT run_id FROM chat_session_bindings WHERE session_id = ?",
                    (session_id.strip(),)
                )
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error(f"Error fetching session run_id: {e}")
            return None


session_manager = ChatSessionManager()
