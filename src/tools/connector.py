import hashlib
import os
from typing import Any, Dict, List, Optional
import pandas as pd

from src.models.schemas import RawSnapshot
from src.tools.datasource import StructuredSource


class SourceConnector:
    """
    SourceConnector loads CSV, Parquet, JSON, or JSONL files, computes SHA-256 checksums,
    and produces an immutable RawSnapshot metadata object using StructuredSource.
    """

    @staticmethod
    def compute_sha256(file_path: str) -> str:
        """Compute SHA-256 hash of a file."""
        return StructuredSource(file_path).get_checksum()

    def read_dataframe(self, file_path: str) -> pd.DataFrame:
        """Load a structured data file into a Pandas DataFrame."""
        return StructuredSource(file_path).load_data()

    def load_source(self, file_path: str) -> RawSnapshot:
        """
        Loads the source file, calculates SHA-256 checksum, row count, and schema,
        and returns an immutable RawSnapshot.
        """
        source = StructuredSource(file_path)
        meta = source.get_metadata()

        snapshot = RawSnapshot(
            checksum_sha256=meta["checksum_sha256"],
            row_count=meta["row_count"],
            schema_info=meta["schema_info"],
            file_path=meta["file_path"],
            file_format=meta["file_format"],
            source_type=meta["source_type"],
            metadata=meta,
        )
        return snapshot
