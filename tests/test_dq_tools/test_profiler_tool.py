from src.tools.dq.common import ErrorCode
from src.tools.dq.profiler_tool import ProfilerInput, run_profiler


def test_happy_path_profiles_all_tables(temp_db):
    result = run_profiler(ProfilerInput(db_path=str(temp_db)))

    assert result.status == "success"
    assert result.error_code == ErrorCode.NONE
    assert len(result.tables) == 1

    trips = result.tables[0]
    assert trips.table == "trips"
    assert trips.row_count == 4
    assert trips.column_count == 4
    assert trips.primary_key == ["trip_id"]
    # No column-level or row-level anomaly fields exist on TableProfile/ColumnMetadata:
    # the Profiler contract is schema + aggregate metadata only.
    assert set(type(trips).model_fields) == {
        "table",
        "row_count",
        "column_count",
        "primary_key",
        "duplicate_count",
        "columns",
    }
    col_names = {c.column for c in trips.columns}
    assert col_names == {"trip_id", "fare_amount", "status", "pickup_datetime"}


def test_happy_path_filters_to_requested_tables(temp_db):
    result = run_profiler(ProfilerInput(db_path=str(temp_db), tables=["trips"]))
    assert result.status == "success"
    assert [t.table for t in result.tables] == ["trips"]


def test_failure_db_not_found(tmp_path):
    result = run_profiler(ProfilerInput(db_path=str(tmp_path / "missing.db")))
    assert result.status == "error"
    assert result.error_code == ErrorCode.DB_NOT_FOUND


def test_failure_table_not_found(temp_db):
    result = run_profiler(ProfilerInput(db_path=str(temp_db), tables=["no_such_table"]))
    assert result.status == "error"
    assert result.error_code == ErrorCode.TABLE_NOT_FOUND


def test_failure_invalid_input_type():
    # tables must be a list[str] | None, not a plain string
    result = run_profiler({"db_path": "data/source.db", "tables": "not_a_list"})
    assert result.status == "error"
    assert result.error_code == ErrorCode.INVALID_INPUT


def test_failure_timeout(temp_db, monkeypatch):
    """A near-zero timeout against real (fast) work is racy, so force the
    work to be slow instead of relying on an arbitrarily tiny timeout."""
    import time as time_module

    from src.tools.dq import profiler_tool as pt

    original_profile_table = pt.profile_table

    def slow_profile_table(conn, table):
        time_module.sleep(0.5)
        return original_profile_table(conn, table)

    monkeypatch.setattr(pt, "profile_table", slow_profile_table)

    result = run_profiler(ProfilerInput(db_path=str(temp_db), timeout_seconds=0.05))
    assert result.status == "error"
    assert result.error_code == ErrorCode.TIMEOUT
