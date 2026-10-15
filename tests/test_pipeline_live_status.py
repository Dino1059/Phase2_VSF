"""Regression tests for reporting the real failed Airflow task."""

import json
from urllib.error import URLError

from backend.api import main as api_main


RUN_ID = "run_bf713073f291"
DAG_RUN_ID = f"app_{RUN_ID}"


class _Cursor:
    def __init__(self, row, steps):
        self.row = row
        self.steps = steps

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args, **_kwargs):
        return None

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.steps


class _Connection:
    def __init__(self, row, steps):
        self.cursor_instance = _Cursor(row, steps)
        self.closed = False

    def cursor(self, cursor_factory=None):
        return self.cursor_instance

    def commit(self):
        return None

    def close(self):
        self.closed = True


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def _run_row():
    return {
        "run_id": RUN_ID,
        "airflow_dag_run_id": DAG_RUN_ID,
        "status": "FAILED",
        "scanned_count": 6902,
        "silver_count": 0,
        "quarantine_count": 0,
        "warning_count": 0,
        "not_evaluated_count": 0,
        # This stale coarse step was the reason the old implementation blamed Lane B.
        "current_step": "EVALUATION",
        "current_step_progress": 60,
    }


def _steps(*, silver_status="RUNNING"):
    return [
        {"step_name": "INGEST", "status": "COMPLETED", "started_at": None, "ended_at": None, "error_message": None},
        {"step_name": "BRONZE", "status": "COMPLETED", "started_at": None, "ended_at": None, "error_message": None},
        {"step_name": "EVALUATION", "status": "COMPLETED", "started_at": None, "ended_at": None, "error_message": None},
        {"step_name": "SILVER", "status": silver_status, "started_at": None, "ended_at": None, "error_message": "Lane C failed" if silver_status == "FAILED" else None},
        {"step_name": "EVIDENCE", "status": "PENDING", "started_at": None, "ended_at": None, "error_message": None},
    ]


def _install_db(monkeypatch, steps):
    connection = _Connection(_run_row(), steps)
    monkeypatch.setattr("database.profiler_engine.get_db_connection", lambda: connection)
    return connection


def test_failed_run_uses_airflow_task_instances_instead_of_stale_current_step(monkeypatch):
    connection = _install_db(monkeypatch, _steps())
    requested_urls = []

    task_instances = {
        "task_instances": [
            {"task_id": "task_1_truncate_and_ingest_bronze", "state": "success"},
            {"task_id": "task_2_data_profiling", "state": "success"},
            {"task_id": "task_3_parallel_evaluation.lane_a_l1_l4_detectors", "state": "success"},
            {"task_id": "task_3_parallel_evaluation.lane_b_hierarchical_policy", "state": "success"},
            {"task_id": "task_3_parallel_evaluation.lane_c_merge_verdicts_and_route", "state": "failed"},
            {"task_id": "task_4_emit_audit_evidence", "state": "upstream_failed"},
        ]
    }

    def fake_urlopen(request, timeout):
        requested_urls.append(request.full_url)
        assert timeout == 1.5
        assert request.full_url.endswith(f"/dagRuns/{DAG_RUN_ID}/taskInstances")
        return _Response(task_instances)

    monkeypatch.setattr(api_main, "urlopen", fake_urlopen)

    payload = api_main.get_pipeline_live_status(RUN_ID)

    assert requested_urls
    assert payload["status"] == "FAILED"
    assert payload["current_step"] == "EVALUATION"
    assert payload["tasks"]["lane_a_l1_l4_detectors"] == "success"
    assert payload["tasks"]["lane_b_hierarchical_policy"] == "success"
    assert payload["tasks"]["lane_c_merge_verdicts_and_route"] == "failed"
    assert payload["tasks"]["task_4_emit_audit_evidence"] != "failed"
    assert connection.closed


def test_failed_run_falls_back_to_persisted_failed_step_when_airflow_is_unavailable(monkeypatch):
    connection = _install_db(monkeypatch, _steps(silver_status="FAILED"))

    def unavailable(*_args, **_kwargs):
        raise URLError("Airflow unavailable")

    monkeypatch.setattr(api_main, "urlopen", unavailable)

    payload = api_main.get_pipeline_live_status(RUN_ID)

    assert payload["status"] == "FAILED"
    assert payload["tasks"]["lane_b_hierarchical_policy"] == "success"
    assert payload["tasks"]["lane_c_merge_verdicts_and_route"] == "failed"
    assert connection.closed
