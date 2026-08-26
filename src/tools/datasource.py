import abc
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import pandas as pd


class DataSource(abc.ABC):
    """Abstract Base Class for Data Sources in DataTrust OS."""

    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path)

    @abc.abstractmethod
    def get_checksum(self) -> str:
        """Compute SHA-256 checksum of the source file."""
        pass

    @abc.abstractmethod
    def load_data(
        self,
        sample_size: Optional[int] = None,
        table_name: Optional[str] = None,
        day_idx: Optional[int] = None,
    ) -> Any:
        """Load data from the source file into memory or DataFrame representation."""
        pass

    @abc.abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Extract metadata details from the source file."""
        pass


class StructuredSource(DataSource):
    """
    DataSource implementation for structured tabular formats (CSV, Parquet, JSON, JSONL, DuckDB).
    Supports automatic format inference based on file extension or explicit format hint.
    """

    def __init__(self, file_path: Union[str, Path], format_hint: Optional[str] = None):
        super().__init__(file_path)
        self.file_format = self._infer_format(format_hint)

    def _infer_format(self, format_hint: Optional[str] = None) -> str:
        if format_hint:
            fmt = format_hint.lower().strip(".")
            if fmt in ["csv", "parquet", "pq", "json", "jsonl", "ndjson", "db", "duckdb"]:
                if fmt in ["db", "duckdb"]:
                    return "duckdb"
                return "parquet" if fmt == "pq" else ("jsonl" if fmt == "ndjson" else fmt)
            return fmt

        ext = self.file_path.suffix.lower()
        if ext == ".csv":
            return "csv"
        elif ext in [".parquet", ".pq"]:
            return "parquet"
        elif ext == ".json":
            return "json"
        elif ext in [".jsonl", ".ndjson"]:
            return "jsonl"
        elif ext in [".db", ".duckdb"]:
            return "duckdb"
        else:
            return "csv"

    def get_checksum(self) -> str:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Source file not found: {self.file_path}")
        sha256 = hashlib.sha256()
        with open(self.file_path, "rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _get_duckdb_connection(self) -> tuple[Any, bool]:
        import duckdb
        import os
        from src.db.connection import get_db

        try:
            db_mgr = get_db()
            p1 = os.path.normcase(os.path.normpath(os.path.abspath(str(self.file_path))))
            p2 = os.path.normcase(os.path.normpath(os.path.abspath(str(db_mgr.db_path))))
            if p1 == p2:
                return db_mgr._get_master_conn(), False
        except Exception:
            pass

        try:
            conn = duckdb.connect(str(self.file_path), read_only=True)
            return conn, True
        except Exception:
            try:
                conn = duckdb.connect(str(self.file_path))
                return conn, True
            except Exception:
                from src.db.connection import get_db
                return get_db()._get_master_conn(), False

    def load_data(
        self,
        sample_size: Optional[int] = None,
        table_name: Optional[str] = None,
        day_idx: Optional[int] = None,
    ) -> pd.DataFrame:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Source file not found: {self.file_path}")

        fmt = self.file_format
        if fmt == "csv":
            return pd.read_csv(self.file_path, nrows=sample_size) if sample_size else pd.read_csv(self.file_path)
        elif fmt == "parquet":
            if sample_size:
                try:
                    import pyarrow.parquet as pq
                    import pyarrow as pa
                    pf = pq.ParquetFile(self.file_path)
                    rg_tables = []
                    curr_rows = 0
                    for i in range(pf.num_row_groups):
                        rg = pf.read_row_group(i)
                        rg_tables.append(rg)
                        curr_rows += rg.num_rows
                        if curr_rows >= sample_size:
                            break
                    if rg_tables:
                        table = pa.concat_tables(rg_tables)
                        df = table.to_pandas()
                        if len(df) > sample_size:
                            df = df.head(sample_size)
                        return df
                except Exception:
                    pass
            return pd.read_parquet(self.file_path)
        elif fmt == "json":
            try:
                df = pd.read_json(self.file_path)
                if sample_size and len(df) > sample_size:
                    df = df.head(sample_size)
                return df
            except Exception:
                return pd.read_json(self.file_path, lines=True, nrows=sample_size) if sample_size else pd.read_json(self.file_path, lines=True)
        elif fmt == "jsonl":
            return pd.read_json(self.file_path, lines=True, nrows=sample_size) if sample_size else pd.read_json(self.file_path, lines=True)
        elif fmt == "duckdb":
            conn, should_close = self._get_duckdb_connection()

            try:
                candidate_tables = self._get_user_tables(conn)
                if not candidate_tables:
                    raise ValueError(f"DuckDB file contains no tables: {self.file_path}")

                # Use explicit table_name if provided, otherwise pick largest
                if table_name:
                    target = table_name
                else:
                    target = candidate_tables[0]
                    max_rows = -1
                    for t in candidate_tables:
                        try:
                            safe_name = StructuredSource._quote_identifier(t)
                            cnt = conn.execute(f'SELECT COUNT(*) FROM {safe_name}').fetchone()[0]
                            if cnt > max_rows:
                                max_rows = cnt
                                target = t
                        except Exception:
                            continue

                safe_target = StructuredSource._quote_identifier(target)
                query = f'SELECT * FROM {safe_target}'
                if day_idx is not None:
                    columns_info = conn.execute(f"PRAGMA table_info('{safe_target}')").fetchall()
                    column_names = {c[1] for c in columns_info}
                    if "day_idx" in column_names:
                        query += f" WHERE day_idx = {int(day_idx)}"
                    elif "assigned_day_index" in column_names:
                        query += f" WHERE assigned_day_index = {int(day_idx)}"

                if sample_size:
                    query += f" LIMIT {int(sample_size)}"
                return conn.execute(query).fetchdf()
            finally:
                if should_close:
                    try:
                        conn.close()
                    except Exception:
                        pass
        else:
            try:
                return pd.read_csv(self.file_path, nrows=sample_size) if sample_size else pd.read_csv(self.file_path)
            except Exception as e:
                raise ValueError(f"Unsupported structured format '{fmt}' for file {self.file_path}: {e}")

    _SYSTEM_TABLES = {
        "agent_traces", "audit_log", "datasets", "decisions",
        "evidence", "execution_authorizations", "hypotheses",
        "incidents", "incident_metadata", "job_runs", "messages",
        "profile_results", "quality_rules", "quarantine", "raw_snapshots",
        "recommendations", "schedules", "sqlite_master",
        "sqlite_sequence", "duckdb_tables", "duckdb_columns"
    }

    @staticmethod
    def _quote_identifier(name: str) -> str:
        parts = name.split(".")
        return ".".join(f'"{p.replace(chr(34), chr(34)+chr(34))}"' for p in parts)

    @staticmethod
    def _get_user_tables(conn) -> List[str]:
        # Fetch tables ONLY from the 'raw' schema
        query = "SELECT table_schema || '.' || table_name FROM information_schema.tables WHERE table_schema = 'raw'"
        
        # Hardcoded allowlist per user request to only profile operational tables
        allowed_tables = {
            'ev_telemetry',
            'trips',
            'charging_sessions',
            'synthetic_feedback'
        }
        
        try:
            tables = [row[0] for row in conn.execute(query).fetchall()]
            if not tables:
                # Fallback to all tables in non-system schemas (e.g. main)
                fallback_query = "SELECT table_schema || '.' || table_name FROM information_schema.tables WHERE table_schema NOT IN ('information_schema', 'pg_catalog')"
                tables = [row[0] for row in conn.execute(fallback_query).fetchall()]
            user = []
            for t in tables:
                schema, name = t.split('.', 1) if '.' in t else ('raw', t)
                if name.lower() in allowed_tables:
                    user.append(t)
            return user if user else tables
        except Exception:
            return []

    def list_tables(self) -> List[str]:
        """List user tables in a DuckDB file."""
        if self.file_format != "duckdb":
            return []
        conn, should_close = self._get_duckdb_connection()
        try:
            return self._get_user_tables(conn)
        finally:
            if should_close:
                try:
                    conn.close()
                except Exception:
                    pass

    def load_all_tables(self, sample_size: Optional[int] = None) -> Dict[str, pd.DataFrame]:
        """Load all user tables from a DuckDB file as {table_name: DataFrame}."""
        if self.file_format != "duckdb":
            return {"default": self.load_data(sample_size=sample_size)}
        conn, should_close = self._get_duckdb_connection()
        try:
            result = {}
            for t in self._get_user_tables(conn):
                safe = StructuredSource._quote_identifier(t)
                q = f'SELECT * FROM {safe}'
                if sample_size:
                    q += f" LIMIT {int(sample_size)}"
                result[t] = conn.execute(q).fetchdf()
            return result
        finally:
            if should_close:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_metadata(self) -> Dict[str, Any]:
        checksum = self.get_checksum()
        file_size = self.file_path.stat().st_size if self.file_path.exists() else 0

        # Fast metadata extraction without loading full file into memory
        row_count = 0
        if self.file_format == "parquet" and self.file_path.exists():
            try:
                import pyarrow.parquet as pq
                meta = pq.read_metadata(self.file_path)
                row_count = meta.num_rows
            except Exception:
                row_count = 0
        elif self.file_format == "duckdb" and self.file_path.exists():
            try:
                conn, should_close = self._get_duckdb_connection()

                try:
                    tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
                    system_tables = {
                        "agent_traces", "audit_log", "datasets", "decisions",
                        "evidence", "execution_authorizations", "hypotheses",
                        "incidents", "job_runs", "messages", "profile_results",
                        "quality_rules", "quarantine", "raw_snapshots",
                        "recommendations", "schedules", "sqlite_master",
                        "sqlite_sequence", "duckdb_tables", "duckdb_columns"
                    }
                    user_tables = [t for t in tables if t.lower() not in system_tables]
                    candidate_tables = user_tables if user_tables else tables
                    for t in candidate_tables:
                        safe_name = StructuredSource._quote_identifier(t)
                        cnt = conn.execute(f'SELECT COUNT(*) FROM {safe_name}').fetchone()[0]
                        if cnt > row_count:
                            row_count = cnt
                finally:
                    if should_close:
                        try:
                            conn.close()
                        except Exception:
                            pass
            except Exception:
                pass

        # Load small sample for schema info
        df_sample = self.load_data(sample_size=100)
        if row_count == 0:
            row_count = len(df_sample)

        schema_info: List[Dict[str, Any]] = [
            {"column": str(col), "dtype": str(dtype)}
            for col, dtype in zip(df_sample.columns, df_sample.dtypes)
        ]

        return {
            "checksum_sha256": checksum,
            "file_path": str(self.file_path.resolve()),
            "file_format": self.file_format,
            "source_type": "structured",
            "file_size": file_size,
            "row_count": row_count,
            "column_count": len(df_sample.columns),
            "schema_info": schema_info,
        }


class UnstructuredSource(DataSource, abc.ABC):
    """
    Abstract base class for unstructured data sources (PDF, Log, Image, etc.).
    """

    def __init__(self, file_path: Union[str, Path], format_hint: Optional[str] = None):
        super().__init__(file_path)
        self.file_format = format_hint or self._infer_format()

    def _infer_format(self) -> str:
        ext = self.file_path.suffix.lower().strip(".")
        return ext or "unstructured"

    def get_checksum(self) -> str:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Source file not found: {self.file_path}")
        sha256 = hashlib.sha256()
        with open(self.file_path, "rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        return sha256.hexdigest()

    def get_metadata(self) -> Dict[str, Any]:
        checksum = self.get_checksum()
        file_size = self.file_path.stat().st_size if self.file_path.exists() else 0
        return {
            "checksum_sha256": checksum,
            "file_path": str(self.file_path.resolve()),
            "file_format": self.file_format,
            "source_type": "unstructured",
            "file_size": file_size,
            "row_count": 0,
            "column_count": 0,
            "schema_info": [],
        }


class PDFSource(UnstructuredSource):
    """
    DataSource stub for PDF document ingestion.
    Extracts text, metadata, and tables from PDF documents when implemented.
    """

    def __init__(self, file_path: Union[str, Path]):
        super().__init__(file_path, format_hint="pdf")

    def load_data(self) -> Any:
        raise NotImplementedError("PDF parsing is not yet supported in this version.")


class LogSource(UnstructuredSource):
    """
    DataSource stub for system/application log file ingestion.
    Parses semi-structured log lines into structured log entries when implemented.
    """

    def __init__(self, file_path: Union[str, Path]):
        super().__init__(file_path, format_hint="log")

    def load_data(self) -> Any:
        raise NotImplementedError("Log parsing is not yet supported in this version.")


class ImageSource(UnstructuredSource):
    """
    DataSource stub for image file ingestion (PNG, JPEG, TIFF, etc.).
    Extracts visual features and metadata from image files when implemented.
    """

    def __init__(self, file_path: Union[str, Path]):
        super().__init__(file_path, format_hint="image")

    def load_data(self) -> Any:
        raise NotImplementedError("Image processing is not yet supported in this version.")
