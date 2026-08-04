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
            db_path = os.path.join(project_root, "data", "datatrust_v4.duckdb")

        self.db_path = db_path
        self.project_root = project_root
        self._local = threading.local()
        self._connections = []
        self._conn_lock = threading.Lock()
        self._initialized = True

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        if not hasattr(self._local, "connection") or self._local.connection is None:
            dir_name = os.path.dirname(self.db_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            if os.path.exists(self.db_path) and os.path.getsize(self.db_path) == 0:
                os.remove(self.db_path)
            conn = duckdb.connect(self.db_path)
            self._local.connection = conn
            with self._conn_lock:
                self._connections.append(conn)
        return self._local.connection

    def init_schema(self) -> None:
        schema_path = os.path.join(self.project_root, "src", "db", "schema.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn = self.get_connection()
        conn.execute(schema_sql)

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
            for conn in self._connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._connections.clear()
        if hasattr(self._local, "connection"):
            self._local.connection = None


_db_manager = None


def get_db(db_path: str = None) -> DuckDBManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = DuckDBManager(db_path)
    return _db_manager
