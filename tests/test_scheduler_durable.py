import pytest
from src.db.connection import get_db
from src.services.scheduler import SchedulerService


@pytest.fixture(autouse=True)
def clean_scheduler_db():
    db = get_db()
    conn = db.get_connection()
    conn.execute("DELETE FROM job_runs")
    conn.execute("DELETE FROM schedules")
    yield
    conn.execute("DELETE FROM job_runs")
    conn.execute("DELETE FROM schedules")


def test_create_schedule_persists_to_duckdb():
    service = SchedulerService()
    service.start()

    sched = service.add_schedule(
        name="Durable Test Schedule",
        dataset_name="raw_taxi_trips.csv",
        schedule_type="interval",
        interval_seconds=1800,
        action="profile",
    )

    sched_id = sched["schedule_id"]
    assert sched_id is not None

    db = get_db()
    conn = db.get_connection()
    row = conn.execute("SELECT id, dataset_key, is_active FROM schedules WHERE id = ?", [sched_id]).fetchone()

    assert row is not None
    assert row[0] == sched_id
    assert row[1] == "raw_taxi_trips.csv"
    assert row[2] is True or row[2] == 1

    service.shutdown()


def test_reload_active_schedules_on_restart():
    # 1. Create a schedule using instance 1
    service1 = SchedulerService()
    service1.start()
    sched = service1.add_schedule(
        name="Reload Test Schedule",
        dataset_name="vgreen_telemetry",
        schedule_type="cron",
        cron_expression="0 12 * * *",
        action="quality_check",
    )
    sched_id = sched["schedule_id"]
    service1.shutdown()

    # 2. Instantiate instance 2 (simulating service restart)
    service2 = SchedulerService()
    service2.start()

    # Verify schedule reloaded
    schedules = service2.get_schedules()
    assert any(s["schedule_id"] == sched_id for s in schedules)

    # Verify job is active in APScheduler
    job = service2.scheduler.get_job(sched_id)
    assert job is not None
    assert job.id == sched_id

    service2.shutdown()


def test_record_job_run_execution():
    service = SchedulerService()
    service.start()

    sched = service.add_schedule(
        name="Job Run Test",
        dataset_name="vinfast_bms",
        schedule_type="interval",
        interval_seconds=3600,
        action="profile",
    )
    sched_id = sched["schedule_id"]

    # Trigger job run
    service.trigger_now(sched_id)

    db = get_db()
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT id, schedule_id, dataset_key, status, result_summary, started_at, completed_at FROM job_runs WHERE schedule_id = ?",
        [sched_id],
    ).fetchall()

    assert len(rows) >= 1
    run_row = rows[0]
    assert run_row[1] == sched_id
    assert run_row[2] == "vinfast_bms"
    assert run_row[3] == "COMPLETED"
    assert run_row[5] is not None  # started_at
    assert run_row[6] is not None  # completed_at

    runs = service.get_job_runs(sched_id)
    assert len(runs) >= 1
    assert runs[0]["status"] == "COMPLETED"

    service.shutdown()
