"""
DataTrust OS: Reset & Ingest Bronze Data + Data Catalog Metadata Initializer
Delegates directly to canonical database.reset_and_ingest_bronze to maintain single source of truth.
"""

from database.reset_and_ingest_bronze import (
    DATASET_METADATA,
    EXPECTED_SCHEMA_CONTRACT,
    DataContractValidationError,
    normalize_opt_out_sharing,
    validate_dataset_contract,
    get_db_connection,
    resolve_data_dir,
    truncate_and_ingest_all,
    run_task_1,
)

__all__ = [
    "DATASET_METADATA",
    "EXPECTED_SCHEMA_CONTRACT",
    "DataContractValidationError",
    "normalize_opt_out_sharing",
    "validate_dataset_contract",
    "get_db_connection",
    "resolve_data_dir",
    "truncate_and_ingest_all",
    "run_task_1",
]

if __name__ == "__main__":
    run_task_1()
