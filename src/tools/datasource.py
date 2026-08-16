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
    def load_data(self) -> Any:
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

    def load_data(self, sample_size: Optional[int] = None) -> pd.DataFrame:
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
            import duckdb

            conn = duckdb.connect(str(self.file_path), read_only=True)
            try:
                tables = [row[0] for row in conn.execute("SHOW TABLES").fetchall()]
                if not tables:
                    raise ValueError(f"DuckDB file contains no tables: {self.file_path}")

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

                best_table = candidate_tables[0]
                max_rows = -1
                for t in candidate_tables:
                    try:
                        safe_name = t.replace('"', '""')
                        cnt = conn.execute(f'SELECT COUNT(*) FROM "{safe_name}"').fetchone()[0]
                        if cnt > max_rows:
                            max_rows = cnt
                            best_table = t
                    except Exception:
                        continue

                table_name = best_table.replace('"', '""')
                query = f'SELECT * FROM "{table_name}"'
                if sample_size:
                    query += f" LIMIT {int(sample_size)}"
                return conn.execute(query).fetchdf()
            finally:
                conn.close()
        else:
            try:
                return pd.read_csv(self.file_path, nrows=sample_size) if sample_size else pd.read_csv(self.file_path)
            except Exception as e:
                raise ValueError(f"Unsupported structured format '{fmt}' for file {self.file_path}: {e}")

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
                import duckdb
                conn = duckdb.connect(str(self.file_path), read_only=True)
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
                        safe_name = t.replace('"', '""')
                        cnt = conn.execute(f'SELECT COUNT(*) FROM "{safe_name}"').fetchone()[0]
                        if cnt > row_count:
                            row_count = cnt
                finally:
                    conn.close()
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
