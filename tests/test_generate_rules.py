import pytest
import pandas as pd
from src.services.dataset_engine import profile_rows, generate_rules_for_baseline

def test_schema_agnostic_rule_generation():
    # Build synthetic sample dataset with various column types and anomalies
    data = [
        {
            "user_id": "U101",
            "age": 25,
            "balance": -50.0,  # negative_count > 0
            "zero_col": 0,      # zero_count / total = 1.0 > 0.5
            "status": "active", # constant column unique_count == 1
            "notes": None,      # null_count > 0
            "pickup_time": "2026-08-01 10:00:00",
            "dropoff_time": "2026-08-01 10:30:00",
            "pickup_latitude": 10.77,
            "pickup_longitude": 106.69,
        },
        {
            "user_id": "U102",
            "age": 30,
            "balance": 150.0,
            "zero_col": 0,
            "status": "active",
            "notes": "some note",
            "pickup_time": "2026-08-01 11:00:00",
            "dropoff_time": "2026-08-01 11:45:00",
            "pickup_latitude": 10.82,
            "pickup_longitude": 106.63,
        }
    ]
    
    profile = profile_rows(data)
    
    # 1. C0: Only null checks
    c0_rules, c0_time = generate_rules_for_baseline("C0", profile)
    assert isinstance(c0_rules, list)
    assert isinstance(c0_time, float)
    for r in c0_rules:
        assert r["rule_type"] == "not_null"
        assert "expression" in r
        assert "description" in r
        assert "confidence" in r
        assert "column" in r

    # 2. C1: Null + range checks
    c1_rules, c1_time = generate_rules_for_baseline("C1", profile)
    c1_types = {r["rule_type"] for r in c1_rules}
    assert c1_types.issubset({"not_null", "range"})
    # Must include range rule for balance >= 0 and lat/lon checks
    range_cols = [r["column"] for r in c1_rules if r["rule_type"] == "range"]
    assert "balance" in range_cols
    assert "pickup_latitude" in range_cols
    assert "pickup_longitude" in range_cols

    # 3. A1: All rules (Null + Range + Cross-field + Semantic)
    a1_rules, a1_time = generate_rules_for_baseline("A1", profile)
    a1_types = {r["rule_type"] for r in a1_rules}
    assert "not_null" in a1_types
    assert "range" in a1_types
    assert "cross_field" in a1_types
    assert "semantic" in a1_types

    # Verify cross-field temporal rule
    cross_field_rules = [r for r in a1_rules if r["rule_type"] == "cross_field"]
    assert len(cross_field_rules) > 0
    assert any("dropoff_time >= pickup_time" in r["expression"] for r in cross_field_rules)

    # Verify zero prevalence semantic rule
    zero_rules = [r for r in a1_rules if r["rule_type"] == "semantic" and r["column"] == "zero_col"]
    assert len(zero_rules) > 0
    assert "zero_col != 0" in zero_rules[0]["expression"]

    # Verify constant column semantic rule
    const_rules = [r for r in a1_rules if r["rule_type"] == "semantic" and r["column"] == "status"]
    assert len(const_rules) > 0
