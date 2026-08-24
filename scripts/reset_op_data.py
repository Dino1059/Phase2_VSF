import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db.connection import get_db
from src.services.ingestion.reset_service import reset_demo

def run():
    print("Resetting demo state...")
    try:
        result = reset_demo()
        print("Reset demo result:", result)
    except Exception as e:
        print("Error resetting demo:", e)
    
    db = get_db()
    
    # DuckDB has a bug deleting from indexed tables that causes:
    # "Failed to delete all rows from index"
    # To bypass, we DROP and recreate the messages table.
    try:
        db.execute("DROP INDEX IF EXISTS idx_quarantine_idempotency")
        db.execute("DROP TABLE IF EXISTS messages")
        print("Dropped messages table to avoid index corruption.")
        
        # Recreate messages table
        db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id VARCHAR PRIMARY KEY,
                session_id VARCHAR NOT NULL,
                type VARCHAR NOT NULL,
                agent_id VARCHAR,
                content VARCHAR NOT NULL,
                metadata_json VARCHAR,
                timestamp VARCHAR NOT NULL
            );
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, timestamp);")
        print("Recreated messages table.")
    except Exception as e:
        print(f"Failed to recreate messages: {e}")

    tables_to_clear = [
        "quality_rules",
        "quarantine",
        "audit_log",
        "execution_authorizations",
        "decisions",
        "evidence",
        "hypotheses",
        "recommendations",
        "agent_traces",
        "incidents",
        "job_runs",
        "pipeline_runs"
    ]
    print("Clearing operational tables...")
    for tbl in tables_to_clear:
        try:
            db.execute(f"TRUNCATE TABLE {tbl}")
            print(f"Cleared {tbl}")
        except Exception as e:
            try:
                db.execute(f"DELETE FROM {tbl}")
                print(f"Cleared {tbl} via DELETE")
            except Exception as ex:
                print(f"Failed to clear {tbl}: {ex}")
            
    print("Done resetting operational data.")

if __name__ == "__main__":
    run()
