"""Contract tests for evidence-backed dynamic lineage (no live services)."""
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.lineage.lineage_service import LineageService
from src.lineage.datatrust_facets import (AUDIT_FACET_SCHEMA, PRODUCER_URL,
    build_audit_assurance_facet, build_policy_treatment_facet,
    get_actual_run_column_lineage)

client = TestClient(app)


def snapshot():
    return {
        "runId": "run-1", "revision": 2, "dagVersion": "sha256:old-dag",
        "lifecycleStatus": "BUILDING", "asOf": "2026-10-12T01:00:00+00:00",
        "logicalTasks": [{"taskId": "extract"}, {"taskId": "load"}],
        "logicalDependencies": [{"from": "extract", "to": "load"}],
        "declaredIO": [{"taskId": "extract", "dataset": "raw.trips", "direction": "INPUT"}],
        "taskInstances": {
            "extract:0": {"taskId": "extract", "mapIndex": 0, "state": "SUCCESS", "attempts": {
                "1": {"tryNumber": 1, "duration": 2.0, "state": "FAILED", "lastEventTime": "2026-10-12T00:58:00+00:00"},
                "2": {"tryNumber": 2, "duration": 3.5, "state": "SUCCESS", "lastEventTime": "2026-10-12T01:00:00+00:00"}}},
            "load:-1": {"taskId": "load", "mapIndex": -1, "state": "SKIPPED", "attempts": {
                "0": {"tryNumber": 0, "duration": 0, "state": "SKIPPED", "lastEventTime": "2026-10-12T01:00:00+00:00"}}}
        },
        "observedIO": {"io1": {"taskId": "extract", "mapIndex": 0, "dataset": "bronze.trips", "direction": "OUTPUT"}},
        "columnLineage": {"c1": {"taskId": "extract", "mapIndex": 0, "tryNumber": 2,
                                      "source_column": "phone", "target_column": "phone_masked",
                                      "transformation_type": "MASKING"}},
        "missingMetadata": [], "sourceErrors": []
    }


def fork_join_snapshot(*, shuffled=False):
    tasks = [
        {"taskId": "t1"},
        {"taskId": "t2"},
        {"taskId": "t3a"},
        {"taskId": "t3b"},
        {"taskId": "t3c"},
        {"taskId": "t4"},
    ]
    dependencies = [
        {"from": "t1", "to": "t2"},
        {"from": "t2", "to": "t3a"},
        {"from": "t2", "to": "t3b"},
        {"from": "t3a", "to": "t3c"},
        {"from": "t3b", "to": "t3c"},
        {"from": "t3c", "to": "t4"},
    ]
    if shuffled:
        tasks = [tasks[index] for index in (4, 1, 5, 2, 0, 3)]
        dependencies = [dependencies[index] for index in (4, 1, 5, 0, 3, 2)]
    return {
        "runId": "fork-join-run",
        "revision": 1,
        "dagVersion": "sha256:fork-join",
        "lifecycleStatus": "BUILDING",
        "logicalTasks": tasks,
        "logicalDependencies": dependencies,
        "taskInstances": {
            "t1:-1": {"taskId": "t1", "mapIndex": -1, "state": "SUCCESS"},
            "t2:-1": {"taskId": "t2", "mapIndex": -1, "state": "SUCCESS"},
            "t3a:0": {"taskId": "t3a", "mapIndex": 0, "state": "SUCCESS"},
            "t3a:1": {"taskId": "t3a", "mapIndex": 1, "state": "SUCCESS"},
            "t3b:-1": {"taskId": "t3b", "mapIndex": -1, "state": "SUCCESS"},
            "t3c:-1": {"taskId": "t3c", "mapIndex": -1, "state": "SUCCESS"},
            "t4:-1": {"taskId": "t4", "mapIndex": -1, "state": "SUCCESS"},
        },
        "declaredIO": [
            {"taskId": "t1", "dataset": "raw.input", "direction": "INPUT"},
        ],
        "observedIO": {
            "output": {
                "taskId": "t4", "mapIndex": -1,
                "dataset": "curated.output", "direction": "OUTPUT",
            },
        },
        "missingMetadata": [],
        "sourceErrors": [],
    }


def node_stages(graph, *, node_type):
    return {
        node["id"]: node["stage"]
        for node in graph["nodes"]
        if node["type"] == node_type
    }


def test_facets_conform():
    facet = build_audit_assurance_facet("hash", "prev", "sig", {"scanned": 3})
    assert facet["_producer"] == PRODUCER_URL
    assert facet["_schemaURL"] == AUDIT_FACET_SCHEMA
    assert facet["scannedCount"] == 3
    assert build_policy_treatment_facet([{"rule_id": "r"}])["rulesCount"] == 1


def test_column_lineage_without_run_is_not_inferred():
    assert get_actual_run_column_lineage("trips") == []


def test_snapshot_graph_is_dynamic_and_keeps_attempts(monkeypatch):
    monkeypatch.setattr(LineageService, "_load_snapshot", staticmethod(lambda run_id, revision: snapshot()))
    graph = LineageService.get_lineage(run_id="run-1", revision=2)
    assert graph["revision"] == 2
    assert graph["dagVersion"] == "sha256:old-dag"
    assert graph["lifecycleStatus"] == "BUILDING"
    assert graph["dataStatus"] == "COMPLETE"
    mapped = next(n for n in graph["nodes"] if n["name"] == "extract")
    assert mapped["mapIndex"] == 0 and mapped["finalTryNumber"] == 2
    assert mapped["totalDuration"] == 5.5 and len(mapped["attempts"]) == 2
    assert {e["relationType"] for e in graph["edges"]} == {
        "LOGICAL_DEPENDENCY", "INSTANCE_OF", "DECLARED", "OBSERVED"
    }
    assert graph["transformations"][0]["tryNumber"] == 2


def test_fork_join_logical_tasks_use_topological_stages():
    graph = LineageService._snapshot_graph(fork_join_snapshot(), "fork-join-run", None)

    assert node_stages(graph, node_type="logicalJob") == {
        "logical-job:t1": 1,
        "logical-job:t2": 2,
        "logical-job:t3a": 3,
        "logical-job:t3b": 3,
        "logical-job:t3c": 4,
        "logical-job:t4": 5,
    }


def test_runtime_instances_inherit_logical_task_stage():
    graph = LineageService._snapshot_graph(fork_join_snapshot(), "fork-join-run", None)

    assert node_stages(graph, node_type="job") == {
        "job:t1:-1": 1,
        "job:t2:-1": 2,
        "job:t3a:0": 3,
        "job:t3a:1": 3,
        "job:t3b:-1": 3,
        "job:t3c:-1": 4,
        "job:t4:-1": 5,
    }


def test_topological_stages_are_deterministic_for_shuffled_snapshot_order():
    ordered = LineageService._snapshot_graph(fork_join_snapshot(), "fork-join-run", None)
    shuffled = LineageService._snapshot_graph(
        fork_join_snapshot(shuffled=True), "fork-join-run", None
    )

    ordered_stages = {node["id"]: node["stage"] for node in ordered["nodes"] if "stage" in node}
    shuffled_stages = {node["id"]: node["stage"] for node in shuffled["nodes"] if "stage" in node}
    assert shuffled_stages == ordered_stages
    assert {edge["relationType"] for edge in shuffled["edges"]} == {
        "LOGICAL_DEPENDENCY", "INSTANCE_OF", "DECLARED", "OBSERVED"
    }


def test_missing_snapshot_has_no_demo_graph(monkeypatch):
    monkeypatch.setattr(LineageService, "_load_snapshot", staticmethod(lambda run_id, revision: None))
    monkeypatch.setattr(LineageService, "_legacy_graph", staticmethod(
        lambda run_id, dataset_id, column, error: {**__import__('backend.lineage.lineage_service', fromlist=['_empty_run'])._empty_run(run_id)}))
    graph = LineageService.get_lineage(run_id="missing")
    assert graph["dataStatus"] == "UNAVAILABLE"
    assert graph["nodes"] == [] and graph["edges"] == []


def test_finding_without_verified_source_has_no_mock_evidence():
    graph = LineageService.get_lineage(finding_id="unknown")
    assert graph["dataStatus"] == "UNAVAILABLE"
    assert graph["nodes"] == []


def test_revision_is_forwarded_by_api(monkeypatch):
    seen = {}
    def fake(**kwargs):
        seen.update(kwargs)
        return LineageService._snapshot_graph(snapshot(), "run-1", None)
    monkeypatch.setattr(LineageService, "get_lineage", staticmethod(fake))
    response = client.get("/api/runs/run-1/lineage?revision=2")
    assert response.status_code == 200 and seen["revision"] == 2


def test_export_is_running_and_contains_real_graph(monkeypatch):
    monkeypatch.setattr(LineageService, "get_lineage", staticmethod(
        lambda **kwargs: LineageService._snapshot_graph(snapshot(), "run-1", None)))
    data = client.get("/api/runs/run-1/lineage/export-openlineage?revision=2").json()
    assert data["eventType"] == "RUNNING"
    assert data["run"]["facets"]["lineageQuality"]["revision"] == 2
    assert data["nodes"] and data["edges"]
