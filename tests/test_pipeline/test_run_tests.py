import sqlite3

from run_tests import check_date, check_duplicate, check_null, check_range, check_type


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (id TEXT PRIMARY KEY, amount REAL, ts TEXT)")
    rows = [
        ("A", 10.0, "2026-01-01T00:00:00"),
        ("B", -5.0, "2026-01-02T00:00:00"),  # range violation
        ("C", 20.0, "NOT_A_DATE"),  # date violation
        ("D", 30.0, "2026-01-04T00:00:00"),
    ]
    conn.executemany("INSERT INTO t VALUES (?, ?, ?)", rows)
    conn.commit()
    return conn


def test_check_range_detects_out_of_bounds_value():
    conn = make_conn()
    spec = {"table": "t", "violation_sql": "WHERE amount < 0"}
    count, samples = check_range(conn, spec)
    assert count == 1
    assert samples[0]["id"] == "B"


def test_check_date_detects_invalid_date():
    conn = make_conn()
    spec = {
        "table": "t",
        "violation_sql": (
            "WHERE ts IS NOT NULL AND ts NOT GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*'"
        ),
    }
    count, samples = check_date(conn, spec)
    assert count == 1
    assert samples[0]["id"] == "C"


def test_check_type_detects_non_numeric_value_in_numeric_column():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t2 (id TEXT PRIMARY KEY, amount REAL)")
    # SQLite has weak typing: a REAL-affinity column can still hold a text value.
    conn.execute("INSERT INTO t2 VALUES ('A', 10.0)")
    conn.execute("INSERT INTO t2 VALUES ('B', 'not_a_number')")
    conn.commit()
    spec = {"table": "t2", "violation_sql": "WHERE typeof(amount) = 'text'"}
    count, samples = check_type(conn, spec)
    assert count == 1
    assert samples[0]["id"] == "B"


def test_check_null_passes_when_no_nulls():
    conn = make_conn()
    spec = {"table": "t", "violation_sql": "WHERE amount IS NULL"}
    count, samples = check_null(conn, spec)
    assert count == 0
    assert samples == []


def test_check_duplicate_detects_duplicate_rows():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t3 (id INTEGER PRIMARY KEY, amount REAL, status TEXT)")
    conn.executemany(
        "INSERT INTO t3 (amount, status) VALUES (?, ?)",
        [(10.0, "OK"), (10.0, "OK"), (20.0, "OK")],
    )
    conn.commit()
    spec = {"table": "t3", "primary_key": ["id"]}
    count, samples = check_duplicate(conn, spec)
    assert count == 1
    assert len(samples) == 2
