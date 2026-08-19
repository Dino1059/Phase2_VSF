import duckdb, os, threading


class DuckDBManager:
    _instance = None
    _lock = threading.Lock()

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
                import time
                for attempt in range(5):
                    try:
                        self._master_conn = duckdb.connect(self.db_path)
                        break
                    except duckdb.IOException as e:
                        err_str = str(e).lower()
                        if any(k in err_str for k in ["could not set lock", "used by another process", "already open", "lock", "conflicting lock"]):
                            if attempt < 4:
                                time.sleep(0.3)
                            else:
                                try:
                                    self._master_conn = duckdb.connect(self.db_path, read_only=True)
                                    break
                                except Exception:
                                    raise e
                        else:
                            raise

                try:
                    self._master_conn.execute("SELECT 1 FROM quality_rules LIMIT 1")
                except Exception:
                    try:
                        self.init_schema()
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

    def _ensure_quality_rules_dataset_key(self, conn) -> None:
        try:
            cols = [
                row[0].lower()
                for row in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='quality_rules'"
                ).fetchall()
            ]
            if cols and "dataset_key" not in cols:
                conn.execute("ALTER TABLE quality_rules ADD COLUMN dataset_key VARCHAR")
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

    def execute(self, query: str, params: list = None) -> list:
        conn = self.get_connection()
        if params is not None:
            return conn.execute(query, params).fetchall()
        return conn.execute(query).fetchall()

    def execute_many(self, query: str, data: list) -> None:
        conn = self.get_connection()
        conn.executemany(query, data)

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
