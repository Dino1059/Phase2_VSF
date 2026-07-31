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
