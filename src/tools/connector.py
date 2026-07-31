import hashlib
import os
from typing import Any, Dict, List, Optional
import pandas as pd

from src.models.schemas import RawSnapshot


class SourceConnector:
    """
    SourceConnector loads CSV or Parquet files, computes SHA-256 checksums,
    and produces an immutable RawSnapshot metadata object.
    """

    @staticmethod
    def compute_sha256(file_path: str) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        return sha256.hexdigest()

    def read_dataframe(self, file_path: str) -> pd.DataFrame:
        """Load a CSV or Parquet file into a Pandas DataFrame."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Source file not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            return pd.read_csv(file_path)
        elif ext in [".parquet", ".pq"]:
            return pd.read_parquet(file_path)
        else:
            # Fallback attempt via CSV, or raise
            try:
                return pd.read_csv(file_path)
            except Exception as e:
                raise ValueError(f"Unsupported file format '{ext}' for file {file_path}: {e}")

    def load_source(self, file_path: str) -> RawSnapshot:
        """
        Loads the source file, calculates SHA-256 checksum, row count, and schema,
        and returns an immutable RawSnapshot.
        """
        checksum = self.compute_sha256(file_path)
        df = self.read_dataframe(file_path)

        schema_info: List[Dict[str, Any]] = [
            {"column": str(col), "dtype": str(dtype)}
            for col, dtype in zip(df.columns, df.dtypes)
        ]

        snapshot = RawSnapshot(
            checksum_sha256=checksum,
            row_count=len(df),
            schema_info=schema_info,
            file_path=os.path.abspath(file_path),
        )
        return snapshot
