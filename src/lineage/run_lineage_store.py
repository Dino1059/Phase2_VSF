"""Persistence and pure projection helpers for run-scoped dynamic lineage.

Logical DAG topology is captured once per revision. Runtime events may add mapped
instances and execution evidence, but cannot rewrite that logical topology.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


TERMINAL_RUN_STATES = {"SUCCESS", "FAILED", "CANCELLED", "CANCELED"}
TERMINAL_TASK_STATES = {"SUCCESS", "FAILED", "SKIPPED", "UPSTREAM_FAILED", "REMOVED"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _order(event: Dict[str, Any]) -> Tuple[float, int]:
    raw = str(event.get("eventTime") or "")
    try:
        instant = datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        instant = float("-inf")
    return (instant, int(event.get("sourceSequence") or 0))


def new_snapshot(
    run_id: str,
    dag_id: str,
    dag_version: str,
    dag_hash: str,
    logical_tasks: Iterable[Dict[str, Any]],
    logical_dependencies: Iterable[Dict[str, Any]],
    declared_io: Iterable[Dict[str, Any]],
    revision: int = 1,
    schema_version: int = 1,
    as_of: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the initial immutable logical topology projection."""
    timestamp = as_of or utc_now()
    return {
        "runId": run_id,
        "revision": revision,
        "schemaVersion": schema_version,
        "dagId": dag_id,
        "dagVersion": dag_version,
        "dagHash": dag_hash,
        "lifecycleStatus": "BUILDING",
        "logicalTasks": list(copy.deepcopy(list(logical_tasks))),
        "logicalDependencies": list(copy.deepcopy(list(logical_dependencies))),
        "declaredIO": list(copy.deepcopy(list(declared_io))),
        "taskInstances": {},
        "observedIO": {},
        "columnLineage": {},
        "evidence": None,
        "missingMetadata": [],
        "sourceErrors": [],
        "processedEventIds": [],
        "runState": "RUNNING",
        "asOf": timestamp,
        "updatedAt": timestamp,
        "finalizedAt": None,
    }


def _newer(event: Dict[str, Any], current: Optional[Dict[str, Any]]) -> bool:
    if not current:
        return True
    return _order(event) > _order({
        "eventTime": current.get("lastEventTime"),
        "sourceSequence": current.get("lastSourceSequence"),
    })


def _event_value(event: Dict[str, Any], key: str, default: Any = None) -> Any:
    payload = event.get("payload") or {}
    return payload.get(key, event.get(key, default))


def apply_lineage_event(snapshot: Dict[str, Any], event: Dict[str, Any]) -> Tuple[Dict[str, Any], bool, str]:
    """Apply one event idempotently and in order; returns projection/applied/reason."""
    result = copy.deepcopy(snapshot)
    event_id = str(event.get("eventId") or "")
    if not event_id:
        raise ValueError("eventId is required")
    if not event.get("eventTime"):
        raise ValueError("eventTime is required")
    if event_id in result.get("processedEventIds", []):
        return result, False, "DUPLICATE_EVENT"
    if result.get("lifecycleStatus") == "FINALIZED":
        return result, False, "FINALIZED_REVISION_IMMUTABLE"

    event_type = str(event.get("eventType") or "").upper()
    applied, reason = True, "APPLIED"
    task_id = _event_value(event, "taskId")
    map_index = int(_event_value(event, "mapIndex", -1))
    instance_key = "%s:%s" % (task_id, map_index)

    if event_type == "TASK_INSTANCE":
        instances = result.setdefault("taskInstances", {})
        current = instances.get(instance_key)
        if not _newer(event, current):
            applied, reason = False, "STALE_EVENT"
        else:
            attempts = (current or {}).get("attempts", {})
            instances[instance_key] = {
                **(current or {}),
                "taskId": task_id,
                "mapIndex": map_index,
                "state": _event_value(event, "state", (current or {}).get("state", "NONE")),
                "attempts": attempts,
                "lastEventTime": event["eventTime"],
                "lastSourceSequence": int(event.get("sourceSequence") or 0),
            }
    elif event_type == "ATTEMPT":
        instances = result.setdefault("taskInstances", {})
        instance = instances.setdefault(instance_key, {
            "taskId": task_id, "mapIndex": map_index, "state": "NONE", "attempts": {}
        })
        try_number = int(_event_value(event, "tryNumber"))
        attempt_key = str(try_number)
        current = instance.setdefault("attempts", {}).get(attempt_key)
        if not _newer(event, current):
            applied, reason = False, "STALE_EVENT"
        else:
            payload = copy.deepcopy(event.get("payload") or {})
            payload.update({
                "tryNumber": try_number,
                "lastEventTime": event["eventTime"],
                "lastSourceSequence": int(event.get("sourceSequence") or 0),
            })
            instance["attempts"][attempt_key] = payload
            instance["finalTryNumber"] = max(int(k) for k in instance["attempts"])
            instance["totalDuration"] = sum(
                float(item.get("duration") or 0) for item in instance["attempts"].values()
            )
    elif event_type in {"OBSERVED_IO", "COLUMN_LINEAGE"}:
        # Instrumented evidence only. SKIPPED tasks can never claim observed reads/writes.
        instance = result.get("taskInstances", {}).get(instance_key, {})
        if instance.get("state") == "SKIPPED":
            applied, reason = False, "SKIPPED_TASK_HAS_NO_OBSERVED_IO"
        else:
            bucket_name = "observedIO" if event_type == "OBSERVED_IO" else "columnLineage"
            bucket = result.setdefault(bucket_name, {})
            current = bucket.get(event_id)
            if not _newer(event, current):
                applied, reason = False, "STALE_EVENT"
            else:
                bucket[event_id] = {
                    **copy.deepcopy(event.get("payload") or {}),
                    "eventId": event_id,
                    "taskId": task_id,
                    "mapIndex": map_index,
                    "tryNumber": int(_event_value(event, "tryNumber", 0)),
                    "lastEventTime": event["eventTime"],
                    "lastSourceSequence": int(event.get("sourceSequence") or 0),
                }
    elif event_type == "EVIDENCE":
        current = result.get("evidence")
        if not _newer(event, current):
            applied, reason = False, "STALE_EVENT"
        else:
            result["evidence"] = {
                **copy.deepcopy(event.get("payload") or {}),
                "lastEventTime": event["eventTime"],
                "lastSourceSequence": int(event.get("sourceSequence") or 0),
            }
    elif event_type == "MISSING_METADATA":
        code = str(_event_value(event, "code") or "")
        if code and code not in result.setdefault("missingMetadata", []):
            result["missingMetadata"].append(code)
    elif event_type == "SOURCE_ERROR":
        error = copy.deepcopy(event.get("payload") or {})
        error.setdefault("observedAt", event["eventTime"])
        result.setdefault("sourceErrors", []).append(error)
    elif event_type == "RUN_STATE":
        state = str(_event_value(event, "state") or "").upper()
        current_order = result.get("runStateOrder")
        if current_order and _order(event) <= tuple(current_order):
            applied, reason = False, "STALE_EVENT"
        else:
            result["runState"] = state
            result["runStateOrder"] = list(_order(event))
            if state in TERMINAL_RUN_STATES:
                result["lifecycleStatus"] = "FINALIZED"
                result["finalizedAt"] = event["eventTime"]
    else:
        applied, reason = False, "UNKNOWN_EVENT_TYPE"

    result.setdefault("processedEventIds", []).append(event_id)
    result["asOf"] = max(str(result.get("asOf") or ""), str(event["eventTime"]))
    result["updatedAt"] = utc_now()
    return result, applied, reason


def assess_data_status(snapshot: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Assess quality independently from BUILDING/FINALIZED lifecycle."""
    if not snapshot or not snapshot.get("runId") or not snapshot.get("dagVersion"):
        return {"dataStatus": "UNAVAILABLE", "missingMetadata": ["RUN_IDENTITY_OR_DAG_VERSION"]}
    missing = list(snapshot.get("missingMetadata") or [])
    if not snapshot.get("logicalTasks"):
        return {"dataStatus": "UNAVAILABLE",
                "missingMetadata": sorted(set(missing + ["LOGICAL_TASKS_NOT_CAPTURED"]))}
    if snapshot.get("logicalDependencies") is None:
        missing.append("LOGICAL_DEPENDENCIES_NOT_CAPTURED")
    if snapshot.get("declaredIO") is None:
        missing.append("DECLARED_IO_NOT_CAPTURED")
    tasks = {str(item.get("taskId")): item for item in (snapshot.get("logicalTasks") or [])}
    instances = snapshot.get("taskInstances") or {}
    instance_values = list(instances.values()) if isinstance(instances, dict) else list(instances)
    if snapshot.get("lifecycleStatus") == "FINALIZED":
        present_task_ids = {str(item.get("taskId") or "") for item in instance_values}
        for task_id, config in tasks.items():
            if not config.get("isMapped") and task_id not in present_task_ids:
                missing.append("TASK_INSTANCES_NOT_CAPTURED")
    observed = snapshot.get("observedIO") or {}
    columns = snapshot.get("columnLineage") or {}
    observed_values = list(observed.values()) if isinstance(observed, dict) else list(observed)
    column_values = list(columns.values()) if isinstance(columns, dict) else list(columns)
    for instance in instance_values:
        task_id = str(instance.get("taskId") or "")
        state = str(instance.get("state") or "").upper()
        if instance.get("mapIndex") is None or not state:
            missing.append("TASK_INSTANCE_IDENTITY_OR_STATE_MISSING")
        if not instance.get("attempts"):
            missing.append("TASK_ATTEMPTS_NOT_CAPTURED")
        for attempt in (instance.get("attempts") or {}).values():
            if attempt.get("tryNumber") is None or not attempt.get("lastEventTime"):
                missing.append("ATTEMPT_IDENTITY_OR_TIMESTAMP_MISSING")
        config = tasks.get(task_id) or {}
        if state == "SUCCESS" and config.get("ioInstrumentation"):
            has_observed = any(str(item.get("taskId")) == task_id and
                               int(item.get("mapIndex", -1)) == int(instance.get("mapIndex", -1))
                               for item in observed_values)
            if not has_observed:
                missing.append("OBSERVED_IO_NOT_CAPTURED")
        if state == "SUCCESS" and config.get("columnLineageInstrumentation"):
            has_columns = any(str(item.get("taskId")) == task_id and
                              int(item.get("mapIndex", -1)) == int(instance.get("mapIndex", -1))
                              for item in column_values)
            if not has_columns:
                missing.append("COLUMN_LINEAGE_NOT_CAPTURED")
        if state == "SUCCESS" and config.get("evidenceEmitter") and not snapshot.get("evidence"):
            missing.append("EVIDENCE_NOT_CAPTURED")
    status = "PARTIAL" if missing or snapshot.get("sourceErrors") else "COMPLETE"
    return {"dataStatus": status, "missingMetadata": sorted(set(missing))}


@dataclass
class StoreResult:
    ok: bool
    snapshot: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    applied: Optional[bool] = None
    reason: Optional[str] = None


class RunLineageStore:
    """Small psycopg2-compatible repository with graceful failure semantics."""

    def __init__(self, connection_factory: Optional[Callable[[], Any]] = None):
        self._connection_factory = connection_factory or self._default_connection

    @staticmethod
    def _default_connection() -> Any:
        from dags.parallel_evaluation_engine import get_db_connection
        return get_db_connection()

    def create(self, snapshot: Dict[str, Any]) -> StoreResult:
        sql = """INSERT INTO audit.run_lineage_snapshots
            (run_id, revision, schema_version, lifecycle_status, dag_id, dag_version, dag_hash, snapshot_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT (run_id, revision) DO NOTHING"""
        return self._write_snapshot(sql, snapshot)

    def get(self, run_id: str, revision: Optional[int] = None) -> StoreResult:
        conn = None
        try:
            conn = self._connection_factory()
            cur = conn.cursor()
            if revision is None:
                cur.execute("SELECT snapshot_json FROM audit.run_lineage_snapshots WHERE run_id=%s ORDER BY revision DESC LIMIT 1", (run_id,))
            else:
                cur.execute("SELECT snapshot_json FROM audit.run_lineage_snapshots WHERE run_id=%s AND revision=%s", (run_id, revision))
            row = cur.fetchone()
            cur.close()
            return StoreResult(True, snapshot=row[0] if row else None)
        except Exception as exc:
            return StoreResult(False, error=str(exc))
        finally:
            if conn is not None:
                try: conn.close()
                except Exception: pass

    def record_event(self, run_id: str, event: Dict[str, Any], revision: Optional[int] = None) -> StoreResult:
        conn = None
        try:
            conn = self._connection_factory()
            cur = conn.cursor()
            # Serialize projection updates per revision so concurrent callbacks
            # cannot overwrite one another after reading the same snapshot.
            if revision is None:
                cur.execute("""SELECT snapshot_json FROM audit.run_lineage_snapshots
                    WHERE run_id=%s ORDER BY revision DESC LIMIT 1 FOR UPDATE""", (run_id,))
            else:
                cur.execute("""SELECT snapshot_json FROM audit.run_lineage_snapshots
                    WHERE run_id=%s AND revision=%s FOR UPDATE""", (run_id, revision))
            row = cur.fetchone()
            if not row:
                conn.rollback(); cur.close()
                return StoreResult(False, error="snapshot not found")
            current_snapshot = row[0]
            if current_snapshot.get("lifecycleStatus") == "FINALIZED":
                current_revision = int(current_snapshot["revision"])
                cur.execute("""INSERT INTO audit.run_lineage_events
                    (event_id,run_id,revision,event_type,event_time,source_sequence,event_json,
                     projection_applied,ignored_reason)
                    VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,FALSE,'FINALIZED_REVISION_IMMUTABLE')
                    ON CONFLICT (event_id) DO NOTHING""",
                    (event["eventId"], run_id, current_revision, event.get("eventType"),
                     event["eventTime"], int(event.get("sourceSequence") or 0), json.dumps(event)))
                duplicate = cur.rowcount == 0
                conn.commit(); cur.close()
                return StoreResult(True, current_snapshot, applied=False,
                                   reason="DUPLICATE_EVENT" if duplicate else "FINALIZED_REVISION_IMMUTABLE")
            projected, applied, reason = apply_lineage_event(current_snapshot, event)
            rev = int(projected["revision"])
            cur.execute("""INSERT INTO audit.run_lineage_events
                (event_id,run_id,revision,event_type,event_time,source_sequence,event_json,projection_applied,ignored_reason)
                VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s) ON CONFLICT (event_id) DO NOTHING""",
                (event["eventId"], run_id, rev, event.get("eventType"), event["eventTime"],
                 int(event.get("sourceSequence") or 0), json.dumps(event), applied, None if applied else reason))
            if cur.rowcount == 0:
                conn.rollback()
                return StoreResult(True, current_snapshot, applied=False, reason="DUPLICATE_EVENT")
            cur.execute("""UPDATE audit.run_lineage_snapshots SET snapshot_json=%s::jsonb,
                lifecycle_status=%s, updated_at=CURRENT_TIMESTAMP,
                finalized_at=CASE WHEN %s='FINALIZED' THEN COALESCE(finalized_at, %s) ELSE finalized_at END
                WHERE run_id=%s AND revision=%s""",
                (json.dumps(projected), projected["lifecycleStatus"], projected["lifecycleStatus"],
                 projected.get("finalizedAt"), run_id, rev))
            conn.commit(); cur.close()
            return StoreResult(True, projected, applied=applied, reason=reason)
        except Exception as exc:
            if conn is not None:
                try: conn.rollback()
                except Exception: pass
            return StoreResult(False, error=str(exc))
        finally:
            if conn is not None:
                try: conn.close()
                except Exception: pass

    def finalize(self, run_id: str, state: str, event_id: str, event_time: Optional[str] = None,
                 source_sequence: int = 0) -> StoreResult:
        return self.record_event(run_id, {"eventId": event_id, "eventType": "RUN_STATE",
            "eventTime": event_time or utc_now(), "sourceSequence": source_sequence,
            "payload": {"state": state}})

    def list_runs(self) -> List[Dict[str, Any]]:
        """Return the latest factual snapshot for every run."""
        conn = None
        try:
            conn = self._connection_factory(); cur = conn.cursor()
            cur.execute("""SELECT DISTINCT ON (run_id) snapshot_json
                FROM audit.run_lineage_snapshots ORDER BY run_id, revision DESC""")
            rows = cur.fetchall(); cur.close()
            return [row[0] for row in rows if row and row[0]]
        except Exception:
            return []
        finally:
            if conn is not None:
                try: conn.close()
                except Exception: pass

    def sync_task_instances(self, run_id: str, revision: Optional[int] = None) -> List[StoreResult]:
        """Project current Airflow task instances, including SKIPPED tasks."""
        current = self.get(run_id, revision)
        if not current.ok or not current.snapshot:
            return [StoreResult(False, error=current.error or "snapshot not found")]
        if current.snapshot.get("lifecycleStatus") == "FINALIZED":
            return [StoreResult(True, current.snapshot, applied=False,
                                reason="FINALIZED_REVISION_IMMUTABLE")]
        rev = int(current.snapshot["revision"])
        conn = None
        try:
            conn = self._connection_factory(); cur = conn.cursor()
            cur.execute("""SELECT task_id,map_index,try_number,state,duration,start_date,end_date
                FROM task_instance WHERE run_id IN (%s,%s)
                ORDER BY task_id,map_index,try_number""", (run_id, f"app_{run_id}"))
            rows = cur.fetchall(); cur.close()
        except Exception as exc:
            observed = utc_now()
            return [self.record_event(run_id, {
                "eventId": "task-instance-source-error:%s:%s" % (run_id, rev),
                "eventType": "SOURCE_ERROR", "eventTime": observed, "sourceSequence": 80,
                "payload": {"source": "airflow_task_instance", "code": "SOURCE_UNAVAILABLE",
                            "message": str(exc), "retryable": True, "observedAt": observed},
            }, revision=rev)]
        finally:
            if conn is not None:
                try: conn.close()
                except Exception: pass

        results: List[StoreResult] = []
        for task_id, map_index, try_number, state, duration, started_at, ended_at in rows:
            event_value = ended_at or started_at
            event_time = event_value.isoformat() if hasattr(event_value, "isoformat") else utc_now()
            base = "%s:%s:%s:%s" % (run_id, task_id, map_index, try_number)
            results.append(self.record_event(run_id, {
                "eventId": "sync-task:%s:%s" % (base, state), "eventType": "TASK_INSTANCE",
                "eventTime": event_time, "sourceSequence": 80,
                "payload": {"taskId": task_id, "mapIndex": int(map_index),
                            "state": str(state or "NONE").upper()},
            }, revision=rev))
            results.append(self.record_event(run_id, {
                "eventId": "sync-attempt:%s:%s" % (base, state), "eventType": "ATTEMPT",
                "eventTime": event_time, "sourceSequence": 80,
                "payload": {"taskId": task_id, "mapIndex": int(map_index),
                            "tryNumber": int(try_number or 0),
                            "state": str(state or "NONE").upper(), "duration": float(duration or 0),
                            "startedAt": started_at.isoformat() if hasattr(started_at, "isoformat") else None,
                            "endedAt": ended_at.isoformat() if hasattr(ended_at, "isoformat") else None},
            }, revision=rev))
        return results

    def reconcile_terminal_runs(self) -> List[StoreResult]:
        """Finalize BUILDING snapshots whose canonical pipeline run is terminal.

        This is the safety net for missed DAG callbacks. The deterministic event
        id makes repeated reconciler passes harmless.
        """
        conn = None
        try:
            conn = self._connection_factory(); cur = conn.cursor()
            cur.execute("""SELECT DISTINCT ON (s.run_id)
                    s.run_id, s.revision, r.status, COALESCE(r.ended_at, CURRENT_TIMESTAMP)
                FROM audit.run_lineage_snapshots s
                JOIN orchestration.pipeline_runs r ON r.run_id = s.run_id
                WHERE s.lifecycle_status = 'BUILDING'
                  AND UPPER(r.status) IN ('SUCCESS','FAILED','CANCELLED','CANCELED')
                ORDER BY s.run_id, s.revision DESC""")
            candidates = cur.fetchall(); cur.close(); conn.close(); conn = None
        except Exception as exc:
            if conn is not None:
                try: conn.close()
                except Exception: pass
            return [StoreResult(False, error=str(exc))]

        results = []
        for run_id, revision, state, ended_at in candidates:
            event_time = ended_at.isoformat() if hasattr(ended_at, "isoformat") else str(ended_at)
            # Final sync captures SKIPPED/REMOVED instances and reports source
            # failures before freezing the revision.
            results.extend(self.sync_task_instances(run_id, revision=int(revision)))
            results.append(self.record_event(run_id, {
                "eventId": "reconcile:%s:%s:%s" % (run_id, revision, str(state).upper()),
                "eventType": "RUN_STATE", "eventTime": event_time,
                "sourceSequence": 0, "payload": {"state": str(state).upper()},
            }, revision=int(revision)))
        return results

    def repair(self, run_id: str, repaired_snapshot: Dict[str, Any], actor: str, reason: str) -> StoreResult:
        current = self.get(run_id)
        if not current.ok or not current.snapshot:
            return StoreResult(False, error=current.error or "snapshot not found")
        if current.snapshot.get("lifecycleStatus") != "FINALIZED":
            return StoreResult(False, error="only finalized snapshots may be repaired")
        old = current.snapshot
        new = copy.deepcopy(repaired_snapshot)
        new_revision = int(old["revision"]) + 1
        new.update({"runId": run_id, "revision": new_revision, "lifecycleStatus": "FINALIZED",
                    "repairedFromRevision": old["revision"], "updatedAt": utc_now()})
        diff = {"before": old, "after": new}
        sql = """INSERT INTO audit.run_lineage_snapshots
            (run_id,revision,schema_version,lifecycle_status,dag_id,dag_version,dag_hash,snapshot_json,
             repaired_from_revision,repair_reason,repair_actor,finalized_at)
            VALUES (%s,%s,%s,'FINALIZED',%s,%s,%s,%s::jsonb,%s,%s,%s,%s)"""
        conn = None
        try:
            conn = self._connection_factory(); cur = conn.cursor()
            cur.execute(sql, (run_id, new_revision, new.get("schemaVersion", 1), new["dagId"],
                new["dagVersion"], new["dagHash"], json.dumps(new), old["revision"], reason, actor,
                new.get("finalizedAt") or utc_now()))
            cur.execute("""INSERT INTO audit.run_lineage_repair_audit
                (run_id,revision,repaired_from_revision,actor,reason,diff_json)
                VALUES (%s,%s,%s,%s,%s,%s::jsonb)""",
                (run_id, new_revision, old["revision"], actor, reason, json.dumps(diff)))
            conn.commit(); cur.close()
            return StoreResult(True, new)
        except Exception as exc:
            if conn is not None:
                try: conn.rollback()
                except Exception: pass
            return StoreResult(False, error=str(exc))
        finally:
            if conn is not None:
                try: conn.close()
                except Exception: pass

    def _write_snapshot(self, sql: str, snapshot: Dict[str, Any]) -> StoreResult:
        conn = None
        try:
            conn = self._connection_factory(); cur = conn.cursor()
            cur.execute(sql, (snapshot["runId"], snapshot["revision"], snapshot["schemaVersion"],
                snapshot["lifecycleStatus"], snapshot["dagId"], snapshot["dagVersion"],
                snapshot["dagHash"], json.dumps(snapshot)))
            conn.commit(); cur.close()
            return StoreResult(True, copy.deepcopy(snapshot))
        except Exception as exc:
            if conn is not None:
                try: conn.rollback()
                except Exception: pass
            return StoreResult(False, error=str(exc))
        finally:
            if conn is not None:
                try: conn.close()
                except Exception: pass
