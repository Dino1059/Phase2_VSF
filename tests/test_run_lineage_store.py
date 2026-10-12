from src.lineage.run_lineage_store import (
    RunLineageStore,
    apply_lineage_event,
    assess_data_status,
    new_snapshot,
)


def base_snapshot():
    return new_snapshot(
        "run-1", "pipeline", "v1", "abc",
        [{"taskId": "extract"}, {"taskId": "load", "isMapped": True}],
        [{"sourceTaskId": "extract", "targetTaskId": "load"}],
        [{"taskId": "extract", "dataset": "raw.orders", "direction": "INPUT"}],
        as_of="2026-01-01T00:00:00+00:00",
    )


def event(event_id, event_type, sequence, **payload):
    return {
        "eventId": event_id,
        "eventType": event_type,
        "eventTime": "2026-01-01T00:00:%02d+00:00" % sequence,
        "sourceSequence": sequence,
        "payload": payload,
    }


def test_mapped_instances_do_not_mutate_logical_topology():
    original = base_snapshot()
    projected, applied, _ = apply_lineage_event(
        original, event("instance-3", "TASK_INSTANCE", 1, taskId="load", mapIndex=3, state="RUNNING")
    )
    assert applied
    assert projected["logicalTasks"] == original["logicalTasks"]
    assert projected["logicalDependencies"] == original["logicalDependencies"]
    assert projected["taskInstances"]["load:3"]["state"] == "RUNNING"


def test_retry_attempts_are_distinct_and_duration_is_aggregated():
    snapshot = base_snapshot()
    snapshot, _, _ = apply_lineage_event(
        snapshot, event("try-1", "ATTEMPT", 1, taskId="load", mapIndex=0, tryNumber=1, duration=4.5)
    )
    snapshot, _, _ = apply_lineage_event(
        snapshot, event("try-2", "ATTEMPT", 2, taskId="load", mapIndex=0, tryNumber=2, duration=2)
    )
    instance = snapshot["taskInstances"]["load:0"]
    assert set(instance["attempts"]) == {"1", "2"}
    assert instance["finalTryNumber"] == 2
    assert instance["totalDuration"] == 6.5


def test_duplicate_and_stale_events_cannot_overwrite_projection():
    snapshot = base_snapshot()
    snapshot, _, _ = apply_lineage_event(
        snapshot, event("new", "TASK_INSTANCE", 5, taskId="extract", mapIndex=-1, state="SUCCESS")
    )
    duplicate, applied, reason = apply_lineage_event(
        snapshot, event("new", "TASK_INSTANCE", 5, taskId="extract", mapIndex=-1, state="FAILED")
    )
    assert not applied and reason == "DUPLICATE_EVENT"
    stale, applied, reason = apply_lineage_event(
        duplicate, event("old", "TASK_INSTANCE", 2, taskId="extract", mapIndex=-1, state="FAILED")
    )
    assert not applied and reason == "STALE_EVENT"
    assert stale["taskInstances"]["extract:-1"]["state"] == "SUCCESS"


def test_skipped_task_rejects_observed_io_but_keeps_declared_io():
    snapshot = base_snapshot()
    snapshot, _, _ = apply_lineage_event(
        snapshot, event("skip", "TASK_INSTANCE", 1, taskId="load", mapIndex=0, state="SKIPPED")
    )
    snapshot, applied, reason = apply_lineage_event(
        snapshot, event("io", "OBSERVED_IO", 2, taskId="load", mapIndex=0,
                        tryNumber=1, dataset="silver.orders", direction="OUTPUT")
    )
    assert not applied and reason == "SKIPPED_TASK_HAS_NO_OBSERVED_IO"
    assert snapshot["observedIO"] == {}
    assert snapshot["declaredIO"]


def test_column_lineage_is_only_created_by_instrumented_event():
    snapshot = base_snapshot()
    snapshot, _, _ = apply_lineage_event(
        snapshot, event("columns", "COLUMN_LINEAGE", 1, taskId="load", mapIndex=2,
                        tryNumber=1, sourceColumn="phone", targetColumn="phone_masked")
    )
    assert snapshot["columnLineage"]["columns"]["sourceColumn"] == "phone"
    assert snapshot["columnLineage"]["columns"]["mapIndex"] == 2


def test_lifecycle_and_quality_are_independent():
    snapshot = base_snapshot()
    assert snapshot["lifecycleStatus"] == "BUILDING"
    assert assess_data_status(snapshot)["dataStatus"] == "COMPLETE"
    snapshot, _, _ = apply_lineage_event(
        snapshot, event("done", "RUN_STATE", 9, state="FAILED")
    )
    assert snapshot["lifecycleStatus"] == "FINALIZED"
    assert snapshot["runState"] == "FAILED"
    snapshot["sourceErrors"].append({"source": "airflow", "code": "OFFLINE"})
    assert assess_data_status(snapshot)["dataStatus"] == "PARTIAL"


def test_store_gracefully_reports_connection_failure():
    def offline():
        raise OSError("database offline")

    result = RunLineageStore(offline).create(base_snapshot())
    assert not result.ok
    assert "database offline" in result.error


def test_finalized_revision_rejects_late_projection_updates():
    snapshot, applied, _ = apply_lineage_event(
        base_snapshot(), event("done", "RUN_STATE", 9, state="SUCCESS")
    )
    assert applied and snapshot["lifecycleStatus"] == "FINALIZED"
    unchanged, applied, reason = apply_lineage_event(
        snapshot, event("late", "TASK_INSTANCE", 10,
                        taskId="extract", mapIndex=-1, state="FAILED")
    )
    assert not applied and reason == "FINALIZED_REVISION_IMMUTABLE"
    assert unchanged == snapshot


def test_migration_defines_revision_event_and_repair_keys():
    from pathlib import Path

    sql = (Path(__file__).parents[1] / "database" / "migration_run_lineage_snapshots.sql").read_text("utf-8")
    assert "PRIMARY KEY (run_id, revision)" in sql
    assert "event_id VARCHAR(250) PRIMARY KEY" in sql
    assert "run_lineage_repair_audit" in sql
