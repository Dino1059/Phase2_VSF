import duckdb, os, threading, logging, time

logger = logging.getLogger(__name__)



class DuckDBManager:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls, db_path: str = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DuckDBManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, db_path: str = None):
        if getattr(self, "_initialized", False):
            if db_path is not None and db_path != self.db_path:
                self.close()
                self.db_path = db_path
            return

        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        if db_path is None:
            env_db = os.environ.get("DUCKDB_PATH")
            if env_db:
                db_path = env_db if os.path.isabs(env_db) else os.path.join(project_root, env_db)
            else:
                pilot_db = os.path.join(project_root, "data_new", "db", "vingroup_pilot.db")
                if os.path.exists(pilot_db):
                    db_path = pilot_db
                else:
                    db_path = os.path.join(project_root, "data", "datatrust_v4.duckdb")


        self.db_path = db_path
        self.project_root = project_root
        self._master_conn = None
        self._conn_lock = threading.RLock()
        self._initialized = True

    def _get_master_conn(self) -> duckdb.DuckDBPyConnection:
        with self._conn_lock:
            if self._master_conn is None:
                dir_name = os.path.dirname(self.db_path)
                if dir_name:
                    os.makedirs(dir_name, exist_ok=True)
                for attempt in range(5):
                    try:
                        self._master_conn = duckdb.connect(self.db_path)
                        break
                    except duckdb.Error as e:
                        err_str = str(e).lower()
                        is_lock_conflict = any(
                            k in err_str for k in
                            ["could not set lock", "used by another process", "already open", "lock", "conflicting lock"]
                        )
                        if is_lock_conflict:
                            # Never touch any file here — another process may
                            # be actively using this database. Checked before
                            # the WAL-corruption branch on purpose: a message
                            # that mentions both must be treated as a lock
                            # conflict, not WAL corruption.
                            if attempt < 4:
                                logger.warning(
                                    "DuckDB lock conflict on %s (attempt %d/5): %s",
                                    self.db_path, attempt + 1, e,
                                )
                                time.sleep(0.3)
                                continue
                            logger.warning(
                                "DuckDB still locked after 5 attempts on %s, falling back to read-only: %s",
                                self.db_path, e,
                            )
                            try:
                                self._master_conn = duckdb.connect(self.db_path, read_only=True)
                                break
                            except Exception:
                                raise e
                        elif "wal file" in err_str or "getdefaultdatabase" in err_str:
                            # Corrupted WAL: remove only .wal. NEVER delete
                            # db_path — that is the actual database.
                            wal_path = self.db_path + ".wal"
                            if os.path.exists(wal_path):
                                logger.warning(
                                    "Corrupted DuckDB WAL for %s, removing %s (main DB file is kept): %s",
                                    self.db_path, wal_path, e,
                                )
                                try:
                                    os.remove(wal_path)
                                except OSError as remove_err:
                                    logger.error("Failed to remove corrupted WAL %s: %s", wal_path, remove_err)
                            if attempt < 4:
                                continue
                            raise
                        else:
                            if attempt < 4:
                                logger.warning(
                                    "Unexpected DuckDB error opening %s (attempt %d/5), retrying: %s",
                                    self.db_path, attempt + 1, e,
                                )
                                time.sleep(0.2)
                                continue
                            raise

                if self._master_conn is None:
                    raise RuntimeError(f"Could not open DuckDB database at '{self.db_path}'. Database may be locked by another process.")

                try:
                    self._master_conn.execute("SELECT 1 FROM quality_rules LIMIT 1")
                except Exception:
                    pass
                try:
                    self._ensure_quarantine_schema(self._master_conn)
                    self._ensure_audit_schema(self._master_conn)
                    self._ensure_scheduler_tables(self._master_conn)
                    self._ensure_pipeline_runs_schema(self._master_conn)
                    self._ensure_snapshots_schema(self._master_conn)
                    self._ensure_reliability_tables(self._master_conn)
                    self._ensure_quality_rules_dataset_key(self._master_conn)
                    self._ensure_incidents_feedback_columns(self._master_conn)
                    self._ensure_demo_ingestion_schema(self._master_conn)
                except Exception:
                    pass
            return self._master_conn

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        master = self._get_master_conn()
        try:
            return master.cursor()
        except Exception:
            return master


    def init_schema(self) -> None:
        schema_path = os.path.join(self.project_root, "src", "db", "schema.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn = self.get_connection()
        conn.execute(schema_sql)
        self._ensure_quarantine_schema(conn)
        self._ensure_audit_schema(conn)
        self._ensure_scheduler_tables(conn)
        self._ensure_pipeline_runs_schema(conn)
        self._ensure_snapshots_schema(conn)
        self._ensure_reliability_tables(conn)
        self._ensure_quality_rules_dataset_key(conn)
        self._ensure_incidents_feedback_columns(conn)

    def _ensure_quality_rules_dataset_key(self, conn) -> None:
        try:
            cols = [
                row[0].lower()
                for row in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='quality_rules'"
                ).fetchall()
            ]
            if cols:
                if "dataset_key" not in cols:
                    conn.execute("ALTER TABLE quality_rules ADD COLUMN dataset_key VARCHAR")
                if "reject_reason" not in cols:
                    conn.execute("ALTER TABLE quality_rules ADD COLUMN reject_reason VARCHAR")
                if "feedback_by" not in cols:
                    conn.execute("ALTER TABLE quality_rules ADD COLUMN feedback_by VARCHAR")
                if "feedback_at" not in cols:
                    conn.execute("ALTER TABLE quality_rules ADD COLUMN feedback_at TIMESTAMP")
        except Exception:
            pass

    def _ensure_incidents_feedback_columns(self, conn) -> None:
        try:
            cols = [
                row[0].lower()
                for row in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='incidents'"
                ).fetchall()
            ]
            if cols:
                if "feedback_type" not in cols:
                    conn.execute("ALTER TABLE incidents ADD COLUMN feedback_type VARCHAR")
                if "feedback_reason" not in cols:
                    conn.execute("ALTER TABLE incidents ADD COLUMN feedback_reason VARCHAR")
                if "feedback_by" not in cols:
                    conn.execute("ALTER TABLE incidents ADD COLUMN feedback_by VARCHAR")
                if "feedback_at" not in cols:
                    conn.execute("ALTER TABLE incidents ADD COLUMN feedback_at TIMESTAMP")
        except Exception:
            pass

    def _ensure_reliability_tables(self, conn) -> None:
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id VARCHAR PRIMARY KEY,
                    project_id VARCHAR NOT NULL,
                    status VARCHAR NOT NULL,
                    entity_ids JSON,
                    signal_ids JSON,
                    admission_reason VARCHAR,
                    supporting_layers JSON,
                    severity VARCHAR,
                    time_window JSON,
                    confirmed_facts JSON,
                    evidence_refs JSON,
                    owner VARCHAR,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id VARCHAR PRIMARY KEY,
                    source_type VARCHAR,
                    source_id VARCHAR,
                    time_range JSON,
                    entity_ids JSON,
                    content_hash VARCHAR,
                    summary VARCHAR,
                    provenance VARCHAR
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hypotheses (
                    hypothesis_id VARCHAR PRIMARY KEY,
                    incident_id VARCHAR NOT NULL,
                    claim VARCHAR NOT NULL,
                    classification VARCHAR,
                    supporting_evidence JSON,
                    contradicting_evidence JSON,
                    missing_evidence JSON,
                    confidence DOUBLE,
                    status VARCHAR
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id VARCHAR PRIMARY KEY,
                    incident_id VARCHAR NOT NULL,
                    hypothesis_id VARCHAR,
                    recommendation_id VARCHAR,
                    action VARCHAR NOT NULL,
                    actor VARCHAR,
                    rationale VARCHAR,
                    details JSON,
                    created_at TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    recommendation_id VARCHAR PRIMARY KEY,
                    incident_id VARCHAR NOT NULL,
                    cause_type VARCHAR,
                    action_type VARCHAR,
                    summary VARCHAR,
                    details JSON,
                    requires_hitl_approval BOOLEAN
                );
            """)
        except Exception:
            pass

    def _ensure_scheduler_tables(self, conn) -> None:
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id VARCHAR PRIMARY KEY,
                    dataset_key VARCHAR,
                    cron_expression VARCHAR,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    next_run_at TIMESTAMP,
                    name VARCHAR,
                    schedule_type VARCHAR,
                    interval_seconds INT,
                    action VARCHAR
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_runs (
                    id VARCHAR PRIMARY KEY,
                    schedule_id VARCHAR,
                    dataset_key VARCHAR,
                    status VARCHAR,
                    result_summary JSON,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                );
            """)
            conn.execute("""
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_authorizations (
                    id VARCHAR PRIMARY KEY,
                    dataset_key VARCHAR,
                    rule_ids JSON,
                    actor VARCHAR,
                    payload_hash VARCHAR,
                    authorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_key VARCHAR PRIMARY KEY,
                    file_path VARCHAR,
                    provenance VARCHAR,
                    tag VARCHAR,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, timestamp);")
        except Exception:
            pass

    def _ensure_pipeline_runs_schema(self, conn) -> None:
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    run_id VARCHAR PRIMARY KEY,
                    project_id VARCHAR NOT NULL,
                    dataset_key VARCHAR NOT NULL,
                    status VARCHAR NOT NULL,
                    result_json JSON,
                    error_message VARCHAR,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                );
            """)
        except Exception:
            pass

    def _ensure_snapshots_schema(self, conn) -> None:
        try:
            cols = [
                row[0].lower()
                for row in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='raw_snapshots'"
                ).fetchall()
            ]
            if cols:
                if "provenance" not in cols:
                    conn.execute("ALTER TABLE raw_snapshots ADD COLUMN provenance VARCHAR")
                if "tag" not in cols:
                    conn.execute("ALTER TABLE raw_snapshots ADD COLUMN tag VARCHAR")

            ds_cols = [
                row[0].lower()
                for row in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='datasets'"
                ).fetchall()
            ]
            if ds_cols:
                if "provenance" not in ds_cols:
                    conn.execute("ALTER TABLE datasets ADD COLUMN provenance VARCHAR")
                if "tag" not in ds_cols:
                    conn.execute("ALTER TABLE datasets ADD COLUMN tag VARCHAR")
        except Exception:
            pass

    def _ensure_quarantine_schema(self, conn) -> None:
        try:
            cols = [
                row[0].lower()
                for row in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='quarantine'"
                ).fetchall()
            ]
            if cols:
                if "snapshot_id" not in cols:
                    conn.execute("ALTER TABLE quarantine ADD COLUMN snapshot_id VARCHAR")
                if "rule_version_id" not in cols:
                    conn.execute("ALTER TABLE quarantine ADD COLUMN rule_version_id VARCHAR")
                if "status" not in cols:
                    conn.execute("ALTER TABLE quarantine ADD COLUMN status VARCHAR DEFAULT 'QUARANTINED'")
                if "user_action" not in cols:
                    conn.execute("ALTER TABLE quarantine ADD COLUMN user_action VARCHAR DEFAULT 'NONE'")
                if "action_at" not in cols:
                    conn.execute("ALTER TABLE quarantine ADD COLUMN action_at TIMESTAMP")
                if "action_by" not in cols:
                    conn.execute("ALTER TABLE quarantine ADD COLUMN action_by VARCHAR")
        except Exception:
            pass

    def _ensure_audit_schema(self, conn) -> None:
        try:
            cols = [
                row[0].lower()
                for row in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='audit_log'"
                ).fetchall()
            ]
            if cols:
                if "previous_event_hash" not in cols:
                    conn.execute("ALTER TABLE audit_log ADD COLUMN previous_event_hash VARCHAR")
                if "event_hash" not in cols:
                    conn.execute("ALTER TABLE audit_log ADD COLUMN event_hash VARCHAR")
        except Exception:
            pass

    def _ensure_demo_ingestion_schema(self, conn) -> None:
        """Apply migration 0002: clean, quarantine, demo_ops schemas + additive columns."""
        migration_path = os.path.join(self.project_root, "src", "db", "migrations", "0002_demo_landing_zones.sql")
        if os.path.exists(migration_path):
            try:
                with open(migration_path, "r", encoding="utf-8") as f:
                    sql = f.read()
                statements = [stmt.strip() for stmt in sql.split(";") if stmt.strip()]
                for stmt in statements:
                    try:
                        conn.execute(stmt)
                    except Exception as e:
                        logger.warning(f"Error executing statement in migration 0002: {e}")

                # Ensure baseline rows in demo_ops
                conn.execute("""
                    INSERT INTO demo_ops.demo_state (id, current_day_idx, warmup_completed, realtime_running)
                    SELECT 1, -1, FALSE, FALSE
                    WHERE NOT EXISTS (SELECT 1 FROM demo_ops.demo_state);
                """)
                conn.execute("""
                    INSERT INTO demo_ops.landing_day_snapshots (snapshot_id, source_file, day_idx, is_activated, row_count)
                    SELECT 'SNAP_' || LPAD(CAST(i AS VARCHAR), 3, '0'), 'day_' || CAST(i AS VARCHAR) || '.csv', i, FALSE, 0
                    FROM range(0, 15) t(i)
                    WHERE NOT EXISTS (SELECT 1 FROM demo_ops.landing_day_snapshots);
                """)
            except Exception as e:
                logger.error(f"Error executing migration 0002: {e}")

    def fetch_df(self, query: str, params: list = None):
        """Run a SELECT and return a DataFrame. Caller must not hold this across pandas work."""
        import pandas as pd
        conn = self._get_master_conn()
        with self._conn_lock:
            res = conn.execute(query, params) if params is not None else conn.execute(query)
            try:
                return res.fetchdf()
            except Exception:
                return pd.DataFrame()

    def execute(self, query: str, params: list = None) -> list:
        conn = self._get_master_conn()
        with self._conn_lock:
            if params is not None:
                res = conn.execute(query, params)
            else:
                res = conn.execute(query)
            q_lower = query.strip().lower()
            if any(q_lower.startswith(kw) for kw in ("update", "insert", "delete", "alter", "create", "drop")):
                try:
                    conn.commit()
                except Exception:
                    pass
            try:
                return res.fetchall()
            except Exception:
                return []

    def execute_many(self, query: str, data: list) -> None:
        conn = self._get_master_conn()
        with self._conn_lock:
            conn.executemany(query, data)
            try:
                conn.commit()
            except Exception:
                pass

    def close(self) -> None:
        with self._conn_lock:
            if self._master_conn is not None:
                try:
                    self._master_conn.close()
                except Exception:
                    pass
                self._master_conn = None


_db_manager = None


def get_db(db_path: str = None) -> DuckDBManager:
    global _db_manager
    target_path = db_path or os.environ.get("DUCKDB_PATH")
    if target_path:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        resolved_path = target_path if os.path.isabs(target_path) else os.path.join(project_root, target_path)
        if _db_manager is not None and _db_manager.db_path != resolved_path:
            try:
                _db_manager.close()
            except Exception:
                pass
            _db_manager = None
        if _db_manager is None:
            _db_manager = DuckDBManager(resolved_path)
        return _db_manager

    if _db_manager is None:
        _db_manager = DuckDBManager(db_path)
    return _db_manager
