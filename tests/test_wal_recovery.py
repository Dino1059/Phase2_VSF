"""WAL recovery must never unlink the main DuckDB file."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import duckdb
import pytest


def test_wal_recovery_does_not_unlink_db(tmp_path, monkeypatch):
    db_path = tmp_path / "keep.db"
    db_path.write_bytes(b"duck")
    wal_path = Path(str(db_path) + ".wal")
    wal_path.write_bytes(b"bad-wal")

    unlinked: list[str] = []
    real_remove = os.remove

    def spy_remove(path, *args, **kwargs):
        unlinked.append(os.path.abspath(path))
        if os.path.abspath(path) == os.path.abspath(db_path):
            raise AssertionError("WAL recovery must not unlink the main .db")
        return real_remove(path)

    monkeypatch.setattr(os, "remove", spy_remove)

    calls = {"n": 0}

    def fake_connect(path, read_only=False):
        calls["n"] += 1
        if calls["n"] == 1:
            raise duckdb.Error("Can't open database: WAL file is invalid / GetDefaultDatabase")
        conn = MagicMock()
        conn.execute.side_effect = Exception("no quality_rules yet")
        conn.cursor.return_value = conn
        return conn

    monkeypatch.setattr(duckdb, "connect", fake_connect)

    from src.db import connection as conn_mod

    conn_mod.DuckDBManager._instance = None
    conn_mod._db_manager = None
    mgr = conn_mod.DuckDBManager(str(db_path))
    mgr._get_master_conn()

    assert db_path.exists()
    assert os.path.abspath(db_path) not in unlinked
    assert any(p.endswith(".wal") for p in unlinked)
    src = Path(conn_mod.__file__).read_text(encoding="utf-8")
    assert "os.remove(self.db_path)" not in src


def test_lock_conflict_checked_before_wal_delete(tmp_path, monkeypatch):
    db_path = tmp_path / "locked.db"
    db_path.write_bytes(b"duck")
    (tmp_path / "locked.db.wal").write_bytes(b"wal")

    removed: list[str] = []
    monkeypatch.setattr(os, "remove", lambda p, *a, **k: removed.append(str(p)))

    n = {"i": 0}

    def fake_connect(path, read_only=False):
        n["i"] += 1
        if n["i"] < 5:
            raise duckdb.Error("Could not set lock on file / WAL file also mentioned")
        conn = MagicMock()
        conn.execute.side_effect = Exception("skip")
        return conn

    monkeypatch.setattr(duckdb, "connect", fake_connect)
    monkeypatch.setattr("time.sleep", lambda *_: None)

    from src.db import connection as conn_mod

    conn_mod.DuckDBManager._instance = None
    conn_mod._db_manager = None
    mgr = conn_mod.DuckDBManager(str(db_path))
    mgr._get_master_conn()
    assert removed == []
    assert db_path.exists()
