from validate_rules import validate_rule

SCHEMA = {
    "trips": {
        "trip_id": "TEXT",
        "fare_amount": "REAL",
        "status": "TEXT",
    }
}


def test_valid_rule_passes():
    rule = {"rule_id": "OK1", "table": "trips", "column": "fare_amount", "operator": "gte", "value": 0}
    assert validate_rule(rule, SCHEMA) == []


def test_schema_mismatch_unknown_table():
    rule = {"rule_id": "BAD1", "table": "no_such_table", "column": "x", "operator": "not_null"}
    errors = validate_rule(rule, SCHEMA)
    assert errors
    assert any("does not exist in the source schema" in e for e in errors)


def test_schema_mismatch_unknown_column():
    rule = {"rule_id": "BAD2", "table": "trips", "column": "no_such_column", "operator": "not_null"}
    errors = validate_rule(rule, SCHEMA)
    assert errors
    assert any("does not exist in table" in e for e in errors)


def test_invalid_type_operator_on_text_column():
    # 'between' requires a numeric column; 'status' is TEXT
    rule = {"rule_id": "BAD3", "table": "trips", "column": "status", "operator": "between", "value": [0, 1]}
    errors = validate_rule(rule, SCHEMA)
    assert errors
    assert any("requires a numeric column" in e for e in errors)


def test_invalid_type_value_shape():
    # gte on a numeric column but 'value' is a string, not a number
    rule = {"rule_id": "BAD4", "table": "trips", "column": "fare_amount", "operator": "gte", "value": "zero"}
    errors = validate_rule(rule, SCHEMA)
    assert errors
    assert any("requires a numeric 'value'" in e for e in errors)


def test_is_numeric_rejects_non_numeric_column():
    rule = {"rule_id": "BAD5", "table": "trips", "column": "status", "operator": "is_numeric"}
    errors = validate_rule(rule, SCHEMA)
    assert errors


def test_valid_date_requires_text_column():
    rule = {"rule_id": "BAD6", "table": "trips", "column": "fare_amount", "operator": "valid_date"}
    errors = validate_rule(rule, SCHEMA)
    assert errors


def test_unknown_operator_is_rejected():
    rule = {"rule_id": "BAD7", "table": "trips", "column": "fare_amount", "operator": "made_up_operator"}
    errors = validate_rule(rule, SCHEMA)
    assert errors
    assert any("unknown operator" in e for e in errors)
