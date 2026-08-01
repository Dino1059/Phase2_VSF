import numpy as np
import pandas as pd
import pytest

from src.tools.compiler import Compiler
from src.tools.executor import Executor
from src.tools.profiler import Profiler
from src.tools.transforms import (
    align_schema_transform,
    drop_duplicates_transform,
    fill_null_transform,
    quarantine_cross_field_transform,
    quarantine_range_transform,
)
from src.tools.validator import RuleSpec, Validator


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "trip_id": [1, 2, 2, 4, 5],
        "driver_pay": [10.0, 15.0, 15.0, -5.0, 100.0],
        "trip_miles": [5.0, 10.0, 10.0, 999.0, 0.0],
        "PULocationID": [10, 20, 20, 30, 40],
        "DOLocationID": [15, 25, 25, 35, 40],
    })


def test_profiler(sample_df):
    profiler = Profiler(snapshot_id="test_snap")
    report = profiler.profile(sample_df)

    assert report.snapshot_id == "test_snap"
    assert report.row_count == 5
    assert report.column_count == 5
    assert report.duplicate_count == 1
    assert len(report.columns) == 5

    driver_pay_prof = next(c for c in report.columns if c.name == "driver_pay" or c.column_name == "driver_pay")
    assert driver_pay_prof.min_val == -5.0 or driver_pay_prof.min == -5.0
    assert driver_pay_prof.max_val == 100.0 or driver_pay_prof.max == 100.0


def test_validator(sample_df):
    rules = [
        RuleSpec(
            rule_id="r1",
            rule_type="not_null",
            target_column="driver_pay",
            severity="medium",
            action="fill_null",
        ),
        RuleSpec(
            rule_id="r2",
            rule_type="range",
            target_column="trip_miles",
            parameters={"min": 0.0, "max": 100.0},
            severity="high",
            action="quarantine_range",
        ),
    ]

    validator = Validator(rules)
    result = validator.validate(sample_df)

    assert not result.is_valid
    assert result.total_rows == 5
    assert len(result.invalid_indices) > 0
    assert "r2" in result.error_summary


def test_compiler():
    compiler = Compiler()
    rules = [
        RuleSpec(
            rule_id="r1",
            rule_type="not_null",
            target_column="driver_pay",
            action="fill_null",
            parameters={"fill_value": 0.0},
        ),
        RuleSpec(
            rule_id="r2",
            rule_type="range",
            target_column="trip_miles",
            action="quarantine_range",
            parameters={"min": 0.0, "max": 100.0},
        ),
    ]

    plan = compiler.compile(rules)
    assert plan.compiled_successfully
    assert len(plan.instructions) == 2 or len(plan.steps) == 2


def test_transforms(sample_df):
    # Test drop duplicates
    clean_dup, q_dup = drop_duplicates_transform(sample_df)
    assert len(clean_dup) == 4
    assert len(q_dup) == 1

    # Test fill null
    df_with_null = sample_df.copy()
    df_with_null.at[1, "driver_pay"] = None
    filled = fill_null_transform(df_with_null, "driver_pay", 0.0)
    assert filled["driver_pay"].isnull().sum() == 0

    # Test range quarantine
    clean_range, q_range = quarantine_range_transform(sample_df, "trip_miles", min_val=0.0, max_val=100.0)
    assert len(clean_range) == 4
    assert len(q_range) == 1

    # Test cross field quarantine (PULocationID == DOLocationID but trip_miles > 0)
    df_cross_test = sample_df.copy()
    df_cross_test.at[4, "trip_miles"] = 10.0
    clean_c2, q_c2 = quarantine_cross_field_transform(
        df_cross_test, "PULocationID", "DOLocationID", rule_type="pickup_dropoff_miles", miles_col="trip_miles"
    )
    assert len(q_c2) == 1

    # Test schema alignment
    aligned = align_schema_transform(sample_df, ["trip_id", "driver_pay", "new_col"])
    assert "new_col" in aligned.columns
    assert len(aligned.columns) == 3


def test_executor(sample_df):
    compiler = Compiler()
    executor = Executor()

    rules = [
        RuleSpec(rule_id="r1", rule_type="unique", target_column=None, action="drop_duplicates"),
        RuleSpec(
            rule_id="r2",
            rule_type="not_null",
            target_column="driver_pay",
            action="fill_null",
            parameters={"fill_value": 0.0},
        ),
    ]

    plan = compiler.compile(rules)
    clean_df, q_df, manifest = executor.execute(sample_df, plan)

    assert manifest.initial_rows == 5
    assert manifest.clean_rows == 4
    assert manifest.quarantine_rows == 1
    assert manifest.execution_time_sec >= 0.0


def test_structured_source_csv(tmp_path, sample_df):
    from src.tools.datasource import StructuredSource

    csv_path = tmp_path / "test.csv"
    sample_df.to_csv(csv_path, index=False)

    source = StructuredSource(csv_path)
    assert source.file_format == "csv"

    checksum = source.get_checksum()
    assert len(checksum) == 64

    df = source.load_data()
    assert len(df) == 5
    assert list(df.columns) == list(sample_df.columns)

    meta = source.get_metadata()
    assert meta["source_type"] == "structured"
    assert meta["file_format"] == "csv"
    assert meta["row_count"] == 5
    assert meta["column_count"] == 5
    assert meta["checksum_sha256"] == checksum


def test_structured_source_json_and_jsonl(tmp_path):
    from src.tools.datasource import StructuredSource

    json_path = tmp_path / "data.json"
    json_path.write_text('[{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]')

    jsonl_path = tmp_path / "data.jsonl"
    jsonl_path.write_text('{"a": 1, "b": "x"}\n{"a": 2, "b": "y"}\n')

    # Test JSON
    s_json = StructuredSource(json_path)
    assert s_json.file_format == "json"
    df_json = s_json.load_data()
    assert len(df_json) == 2
    assert "a" in df_json.columns

    meta_json = s_json.get_metadata()
    assert meta_json["file_format"] == "json"
    assert meta_json["row_count"] == 2

    # Test JSONL
    s_jsonl = StructuredSource(jsonl_path)
    assert s_jsonl.file_format == "jsonl"
    df_jsonl = s_jsonl.load_data()
    assert len(df_jsonl) == 2
    assert "b" in df_jsonl.columns

    meta_jsonl = s_jsonl.get_metadata()
    assert meta_jsonl["file_format"] == "jsonl"
    assert meta_jsonl["row_count"] == 2


def test_structured_source_parquet(tmp_path, sample_df):
    from src.tools.datasource import StructuredSource

    pq_path = tmp_path / "data.parquet"
    sample_df.to_parquet(pq_path, index=False)

    source = StructuredSource(pq_path)
    assert source.file_format == "parquet"

    df = source.load_data()
    assert len(df) == 5
    meta = source.get_metadata()
    assert meta["file_format"] == "parquet"
    assert meta["row_count"] == 5


def test_unstructured_source_stubs(tmp_path):
    from src.tools.datasource import ImageSource, LogSource, PDFSource

    pdf_file = tmp_path / "sample.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 dummy pdf content")

    log_file = tmp_path / "app.log"
    log_file.write_text("2026-08-01 10:00:00 INFO System started\n")

    img_file = tmp_path / "image.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n dummy image content")

    # PDFSource
    pdf_src = PDFSource(pdf_file)
    assert pdf_src.file_format == "pdf"
    assert len(pdf_src.get_checksum()) == 64
    pdf_meta = pdf_src.get_metadata()
    assert pdf_meta["source_type"] == "unstructured"
    assert pdf_meta["file_format"] == "pdf"
    with pytest.raises(NotImplementedError, match="PDF parsing is not yet supported"):
        pdf_src.load_data()

    # LogSource
    log_src = LogSource(log_file)
    assert log_src.file_format == "log"
    assert len(log_src.get_checksum()) == 64
    log_meta = log_src.get_metadata()
    assert log_meta["source_type"] == "unstructured"
    assert log_meta["file_format"] == "log"
    with pytest.raises(NotImplementedError, match="Log parsing is not yet supported"):
        log_src.load_data()

    # ImageSource
    img_src = ImageSource(img_file)
    assert img_src.file_format == "image"
    assert len(img_src.get_checksum()) == 64
    img_meta = img_src.get_metadata()
    assert img_meta["source_type"] == "unstructured"
    assert img_meta["file_format"] == "image"
    with pytest.raises(NotImplementedError, match="Image processing is not yet supported"):
        img_src.load_data()


def test_profiler_with_datasource(tmp_path, sample_df):
    from src.models.schemas import ProfileResult
    from src.tools.datasource import PDFSource, StructuredSource
    from src.tools.profiler import Profiler

    csv_path = tmp_path / "data.csv"
    sample_df.to_csv(csv_path, index=False)

    pdf_path = tmp_path / "document.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy content")

    profiler = Profiler(snapshot_id="ds_snap")

    # Test structured profiling
    struct_src = StructuredSource(csv_path)
    res_struct = profiler.profile_source(struct_src)
    assert isinstance(res_struct, ProfileResult)
    assert res_struct.snapshot_id == "ds_snap"
    assert res_struct.source_type == "structured"
    assert res_struct.file_format == "csv"
    assert res_struct.row_count == 5
    assert len(res_struct.columns) == 5

    # Test unstructured profiling stub
    pdf_src = PDFSource(pdf_path)
    res_unstruct = profiler.profile_source(pdf_src)
    assert isinstance(res_unstruct, ProfileResult)
    assert res_unstruct.snapshot_id == "ds_snap"
    assert res_unstruct.source_type == "unstructured"
    assert res_unstruct.file_format == "pdf"
    assert res_unstruct.row_count == 0

