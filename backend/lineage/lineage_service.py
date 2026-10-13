"""Read model for run-scoped, evidence-backed data lineage.

The service deliberately does not invent a pipeline topology.  New runs are read
from :class:`RunLineageStore`; the small SQL fallback is only for old runs and
contains facts that can be verified in Airflow/audit tables.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

DB_URL = os.getenv("DATABASE_URL", "postgresql://airflow:airflow@localhost:5432/airflow")


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _empty_run(run_id: Optional[str], errors: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "scope": "FULL_RUN", "runId": run_id, "dagVersion": None,
        "lifecycleStatus": "BUILDING", "dataStatus": "UNAVAILABLE",
        "revision": None, "asOf": now, "finalizedAt": None,
        "nodes": [], "edges": [], "totalNodes": 0, "totalEdges": 0,
        "transformations": [], "schemaDiff": [], "metrics": {},
        "sources": [], "missingMetadata": ["RUN_LINEAGE_NOT_CAPTURED"],
        "sourceErrors": errors or [],
    }


class LineageService:
    @staticmethod
    def _task_stages(logical_tasks: List[Any], dependencies: List[Dict[str, Any]]) -> Dict[str, int]:
        """Return deterministic ranks for the logical DAG (roots are stage 1).

        Cycles are collapsed into a single component.  This keeps malformed or
        legacy cyclic snapshots renderable while still placing every component
        after all of its non-cyclic upstream components.
        """
        task_ids = {
            str(task.get("taskId") or task.get("task_id") or task.get("id"))
            if isinstance(task, dict) else str(task)
            for task in logical_tasks
        }
        task_ids.discard("")
        adjacency: Dict[str, set[str]] = {task_id: set() for task_id in task_ids}
        for dep in dependencies:
            source = dep.get("from") or dep.get("source") or dep.get("upstreamTaskId") or dep.get("upstream_task_id")
            target = dep.get("to") or dep.get("target") or dep.get("downstreamTaskId") or dep.get("downstream_task_id")
            source, target = str(source or ""), str(target or "")
            if source in task_ids and target in task_ids:
                adjacency[source].add(target)

        # Tarjan SCC traversal is sorted so identical snapshots always receive
        # identical ranks regardless of JSON/DB row order.
        index = 0
        stack: List[str] = []
        on_stack: set[str] = set()
        indices: Dict[str, int] = {}
        lowlinks: Dict[str, int] = {}
        components: List[List[str]] = []

        def visit(node: str) -> None:
            nonlocal index
            indices[node] = lowlinks[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)
            for downstream in sorted(adjacency[node]):
                if downstream not in indices:
                    visit(downstream)
                    lowlinks[node] = min(lowlinks[node], lowlinks[downstream])
                elif downstream in on_stack:
                    lowlinks[node] = min(lowlinks[node], indices[downstream])
            if lowlinks[node] == indices[node]:
                component: List[str] = []
                while True:
                    member = stack.pop()
                    on_stack.remove(member)
                    component.append(member)
                    if member == node:
                        break
                components.append(sorted(component))

        for task_id in sorted(task_ids):
            if task_id not in indices:
                visit(task_id)

        component_of = {task_id: component_id for component_id, members in enumerate(components) for task_id in members}
        upstream_components: Dict[int, set[int]] = {component_id: set() for component_id in range(len(components))}
        for source, targets in adjacency.items():
            for target in targets:
                source_component, target_component = component_of[source], component_of[target]
                if source_component != target_component:
                    upstream_components[target_component].add(source_component)

        component_stages: Dict[int, int] = {}

        def rank(component_id: int) -> int:
            if component_id not in component_stages:
                parents = upstream_components[component_id]
                component_stages[component_id] = 1 + max((rank(parent) for parent in parents), default=0)
            return component_stages[component_id]

        return {task_id: rank(component_of[task_id]) for task_id in sorted(task_ids)}

    @staticmethod
    def _store() -> Any:
        from src.lineage.run_lineage_store import RunLineageStore
        return RunLineageStore()

    @staticmethod
    def get_status() -> Dict[str, Any]:
        result = {
            "isConnected": False, "mode": "RUN_SNAPSHOT", "modeDescription": "Run-scoped lineage snapshots",
            "totalDatasets": 0, "totalJobs": 0,
            "checkedAt": datetime.now(timezone.utc).isoformat(),
        }
        try:
            import psycopg2
            with psycopg2.connect(DB_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema IN ('bronze','silver')")
                    result["totalDatasets"] = int(cur.fetchone()[0])
                    cur.execute("SELECT COUNT(DISTINCT task_id) FROM task_instance")
                    result["totalJobs"] = int(cur.fetchone()[0])
            result["isConnected"] = True
        except Exception as exc:
            result["sourceErrors"] = [{"source": "postgresql", "code": "SOURCE_UNAVAILABLE", "message": str(exc), "retryable": True, "observedAt": result["checkedAt"]}]
        return result

    @staticmethod
    def get_lineage(run_id: Optional[str] = None, finding_id: Optional[str] = None,
                    record_id: Optional[str] = None, column: Optional[str] = None,
                    dataset_id: Optional[str] = None, revision: Optional[int] = None) -> Dict[str, Any]:
        if finding_id:
            return LineageService._build_finding_lineage(finding_id)
        return LineageService._build_run_lineage(run_id, column, dataset_id, revision)

    @staticmethod
    def _load_snapshot(run_id: str, revision: Optional[int]) -> Optional[Dict[str, Any]]:
        store = LineageService._store()
        for name in ("load_snapshot", "get_snapshot", "get"):
            method = getattr(store, name, None)
            if method:
                try:
                    value = method(run_id, revision=revision)
                except TypeError:
                    value = method(run_id, revision) if revision is not None else method(run_id)
                if hasattr(value, "ok"):
                    if not value.ok:
                        raise RuntimeError(value.error or "snapshot store unavailable")
                    value = value.snapshot
                if value:
                    return dict(value)
        return None

    @staticmethod
    def _build_run_lineage(run_id: Optional[str], column: Optional[str], dataset_id: Optional[str],
                           revision: Optional[int] = None) -> Dict[str, Any]:
        if not run_id and dataset_id:
            clean_ds = dataset_id.replace('.csv', '')
            try:
                import psycopg2
                with psycopg2.connect(DB_URL) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT run_id FROM audit.run_lineage_snapshots
                            WHERE (snapshot_json->>'datasetId' = %s OR snapshot_json->>'datasetId' = %s
                                   OR snapshot_json->>'datasetId' = %s OR snapshot_json->>'datasetId' = %s)
                            ORDER BY updated_at DESC LIMIT 1
                        """, (dataset_id, f"{dataset_id}.csv", clean_ds, f"{clean_ds}.csv"))
                        row = cur.fetchone()
                        if row:
                            run_id = row[0]
                        else:
                            cur.execute("""
                                SELECT run_id FROM orchestration.pipeline_runs
                                WHERE (dataset_id = %s OR dataset_id = %s)
                                ORDER BY started_at DESC LIMIT 1
                            """, (clean_ds, f"{clean_ds}.csv"))
                            row = cur.fetchone()
                            if row:
                                run_id = row[0]
            except Exception:
                pass
        if not run_id:
            return _empty_run(None)
        try:
            # Read-time reconciliation is the safety net for terminal runs whose
            # Airflow callback was lost (hard kill/cancel). It is idempotent.
            store = LineageService._store()
            store.sync_task_instances(run_id, revision)
            store.reconcile_terminal_runs()
            snapshot = LineageService._load_snapshot(run_id, revision)
        except Exception as exc:
            snapshot = None
            store_error = {"source": "lineage_snapshot", "code": "SOURCE_UNAVAILABLE", "message": str(exc), "retryable": True, "observedAt": datetime.now(timezone.utc).isoformat()}
        else:
            store_error = None
        if snapshot:
            return LineageService._snapshot_graph(snapshot, run_id, column)
        return LineageService._legacy_graph(run_id, dataset_id, column, store_error)

    @staticmethod
    def _snapshot_graph(s: Dict[str, Any], run_id: str, column: Optional[str]) -> Dict[str, Any]:
        payload = s.get("payload") or s.get("snapshot") or s
        logical = payload.get("logicalTopology") or payload.get("logical_topology") or {}
        logical_tasks = logical.get("tasks") or payload.get("logicalTasks") or payload.get("logical_tasks") or []
        dependencies = logical.get("dependencies") or payload.get("logicalDependencies") or payload.get("logical_dependencies") or []
        task_stages = LineageService._task_stages(logical_tasks, dependencies)
        instances = payload.get("taskInstances") or payload.get("task_instances") or []
        if isinstance(instances, dict): instances = list(instances.values())
        attempts = payload.get("attempts") or []
        if isinstance(attempts, dict): attempts = list(attempts.values())
        by_instance: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
        for attempt in attempts:
            key = (str(attempt.get("taskId") or attempt.get("task_id")), int(attempt.get("mapIndex", attempt.get("map_index", -1))))
            by_instance.setdefault(key, []).append(attempt)
        nodes: List[Dict[str, Any]] = []
        runtime_nodes_by_task: Dict[str, List[str]] = {}
        instance_links: List[Dict[str, Any]] = []
        for instance in instances:
            task_id = str(instance.get("taskId") or instance.get("task_id"))
            map_index = int(instance.get("mapIndex", instance.get("map_index", -1)))
            task_attempts = instance.get("attempts") or by_instance.get((task_id, map_index), [])
            if isinstance(task_attempts, dict): task_attempts = list(task_attempts.values())
            task_attempts = sorted(task_attempts, key=lambda a: int(a.get("tryNumber", a.get("try_number", 0))))
            task_attempts = [{
                **attempt,
                "tryNumber": int(attempt.get("tryNumber", attempt.get("try_number", 0))),
                "status": str(attempt.get("status") or attempt.get("state") or "NONE").upper(),
                "eventTime": attempt.get("eventTime") or attempt.get("lastEventTime"),
                "sourceSequence": attempt.get("sourceSequence", attempt.get("lastSourceSequence")),
            } for attempt in task_attempts]
            duration = sum(float(a.get("duration") or 0) for a in task_attempts)
            latest = task_attempts[-1] if task_attempts else {}
            status = instance.get("status") or instance.get("state") or latest.get("status") or latest.get("state") or "NONE"
            node_id = f"job:{task_id}:{map_index}"
            runtime_nodes_by_task.setdefault(task_id, []).append(node_id)
            instance_links.append({"from": node_id, "to": f"logical-job:{task_id}",
                                   "relationType": "INSTANCE_OF", "isHighlighted": True})
            nodes.append({"id": node_id, "name": task_id, "label": task_id, "type": "job", "layer": "TASK", "taskId": task_id,
                          "stage": task_stages.get(task_id, 1),
                          "status": str(status).upper(), "mapIndex": map_index, "attempts": task_attempts,
                          "finalTryNumber": latest.get("tryNumber", latest.get("try_number")),
                          "totalDuration": round(duration, 3), "isHighlighted": True})
        # Logical topology and runtime instances are distinct: mapped instances
        # may expand while the DAG-version dependency graph stays fixed.
        for task in logical_tasks:
            task_id = str(task.get("taskId") or task.get("task_id") or task.get("id")) if isinstance(task, dict) else str(task)
            if task_id:
                nodes.append({"id": f"logical-job:{task_id}", "name": task_id, "label": task_id, "type": "logicalJob", "layer": "TASK",
                              "stage": task_stages.get(task_id, 1),
                              "status": "DECLARED", "isHighlighted": True})
        edges: List[Dict[str, Any]] = list(instance_links)
        for dep in dependencies:
            source = dep.get("from") or dep.get("source") or dep.get("upstreamTaskId") or dep.get("upstream_task_id")
            target = dep.get("to") or dep.get("target") or dep.get("downstreamTaskId") or dep.get("downstream_task_id")
            if source and target:
                edges.append({"from": f"logical-job:{source}", "to": f"logical-job:{target}", "relationType": "LOGICAL_DEPENDENCY", "isHighlighted": True})
        declared_io = payload.get("declaredIO") or []
        observed_io = payload.get("observedIO") or []
        if isinstance(observed_io, dict): observed_io = list(observed_io.values())
        io_items = ([{**item, "relationType": "DECLARED"} for item in declared_io] +
                    [{**item, "relationType": "OBSERVED"} for item in observed_io])
        io_items += payload.get("datasetIO") or payload.get("dataset_io") or payload.get("ioEvents") or []
        dataset_nodes: Dict[str, Dict[str, Any]] = {}
        dataset_stage_hints: Dict[str, Dict[str, List[int]]] = {}
        for item in io_items:
            relation = str(item.get("relationType") or item.get("relation_type") or item.get("kind") or "DECLARED").upper()
            if relation not in {"DECLARED", "OBSERVED"}: relation = "DECLARED"
            dataset = item.get("dataset") or item.get("datasetId") or item.get("dataset_id")
            task_id = item.get("taskId") or item.get("task_id")
            if not dataset or not task_id: continue
            did = f"dataset:{dataset}"
            dataset_nodes[did] = {"id": did, "name": dataset, "label": dataset, "type": "dataset", "layer": item.get("layer") or "DATASET", "status": "OBSERVED" if relation == "OBSERVED" else "DECLARED", "isHighlighted": True}
            direction = str(item.get("direction") or "INPUT").upper()
            hints = dataset_stage_hints.setdefault(did, {"producers": [], "consumers": []})
            if direction == "INPUT":
                hints["consumers"].append(task_stages.get(str(task_id), 1))
            else:
                hints["producers"].append(task_stages.get(str(task_id), 1))
            # Declared I/O belongs to the immutable logical task. Observed I/O
            # belongs to the concrete mapped task instance that performed it.
            jid = (f"logical-job:{task_id}" if relation == "DECLARED" else
                   f"job:{task_id}:{int(item.get('mapIndex', item.get('map_index', -1)))}")
            edges.append({"from": did if direction == "INPUT" else jid, "to": jid if direction == "INPUT" else did, "relationType": relation, "isHighlighted": True})
        for did, node in dataset_nodes.items():
            hints = dataset_stage_hints[did]
            producers, consumers = hints["producers"], hints["consumers"]
            if producers:
                dataset_stage = max(producers) + 1
                if consumers:
                    dataset_stage = min(dataset_stage, min(consumers))
            else:
                dataset_stage = max(1, min(consumers, default=2) - 1)
            node["stage"] = dataset_stage
        nodes.extend(dataset_nodes.values())
        transformations = payload.get("columnLineage") or payload.get("column_lineage") or []
        if isinstance(transformations, dict): transformations = list(transformations.values())
        if column:
            transformations = [t for t in transformations if column in (str(t.get("source_column", "")), str(t.get("target_column", "")))]
        missing = list(s.get("missingMetadata") or payload.get("missingMetadata") or [])
        source_errors = list(s.get("sourceErrors") or payload.get("sourceErrors") or [])
        try:
            from src.lineage.run_lineage_store import assess_data_status
            assessed = assess_data_status(payload)
        except Exception:
            assessed = {}
        missing = sorted(set(missing + list(assessed.get("missingMetadata") or [])))
        data_status = s.get("dataStatus") or payload.get("dataStatus") or assessed.get("dataStatus") or ("PARTIAL" if missing or source_errors else "COMPLETE")
        lifecycle = s.get("lifecycleStatus") or s.get("lifecycle_status") or payload.get("lifecycleStatus") or "BUILDING"
        evidence = payload.get("evidence") or {}
        result = {"scope": "FULL_RUN", "runId": run_id, "datasetId": payload.get("datasetId"),
                  "dagVersion": s.get("dagVersion") or s.get("dag_version") or payload.get("dagVersion"),
                  "lifecycleStatus": lifecycle, "dataStatus": data_status,
                  "runState": payload.get("runState"),
                  "revision": s.get("revision", payload.get("revision")),
                  "asOf": _iso(s.get("updatedAt") or s.get("updated_at") or payload.get("asOf")) or datetime.now(timezone.utc).isoformat(),
                  "finalizedAt": _iso(s.get("finalizedAt") or s.get("finalized_at")),
                  "nodes": nodes, "edges": edges, "totalNodes": len(nodes), "totalEdges": len(edges),
                  "transformations": transformations, "schemaDiff": [],
                  "metrics": evidence.get("metrics") or payload.get("metrics") or {},
                  "digitalSignature": evidence.get("digitalSignature") or payload.get("digitalSignature"),
                  "evidenceHash": evidence.get("evidenceHash") or payload.get("evidenceHash"),
                  "sources": s.get("sources") or payload.get("sources") or [{"source": "lineage_snapshot", "status": "AVAILABLE"}],
                  "missingMetadata": missing, "sourceErrors": source_errors}
        return result

    @staticmethod
    def _legacy_graph(run_id: str, dataset_id: Optional[str], column: Optional[str], store_error: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        result = _empty_run(run_id, [store_error] if store_error else [])
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            with psycopg2.connect(DB_URL) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT task_id, map_index, try_number, state, duration, start_date, end_date FROM task_instance WHERE run_id IN (%s,%s) ORDER BY task_id,map_index,try_number", (run_id, f"app_{run_id}"))
                    rows = [dict(r) for r in cur.fetchall()]
            grouped: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
            for row in rows: grouped.setdefault((row["task_id"], int(row.get("map_index", -1))), []).append(row)
            for (task_id, map_index), attempts in grouped.items():
                latest = attempts[-1]
                clean = [{**a, "start_date": _iso(a.get("start_date")), "end_date": _iso(a.get("end_date"))} for a in attempts]
                result["nodes"].append({"id": f"job:{task_id}:{map_index}", "name": task_id, "label": task_id, "type": "job", "layer": "TASK", "status": str(latest.get("state") or "NONE").upper(), "mapIndex": map_index, "attempts": clean, "finalTryNumber": latest.get("try_number"), "totalDuration": round(sum(float(a.get("duration") or 0) for a in attempts), 3), "isHighlighted": True})
            result["totalNodes"] = len(result["nodes"])
            result["sources"].append({"source": "airflow_task_instance", "status": "AVAILABLE", "observedAt": datetime.now(timezone.utc).isoformat()})
            if result["nodes"]:
                result["dataStatus"] = "PARTIAL"
                result["missingMetadata"] = ["DAG_VERSION_TOPOLOGY_NOT_CAPTURED", "DATASET_IO_NOT_CAPTURED", "COLUMN_LINEAGE_NOT_CAPTURED"]
        except Exception as exc:
            result["sourceErrors"].append({"source": "airflow_db", "code": "SOURCE_UNAVAILABLE", "message": str(exc), "retryable": True, "observedAt": datetime.now(timezone.utc).isoformat()})
        return result

    @staticmethod
    def _build_finding_lineage(finding_id: str) -> Dict[str, Any]:
        # Finding hashes are evidence identifiers, not permission to invent a path.
        base = {"scope": "FINDING_TARGETED", "findingId": finding_id, "nodes": [], "edges": [],
                "transformations": [], "dataStatus": "UNAVAILABLE", "missingMetadata": [], "sourceErrors": []}
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            with psycopg2.connect(DB_URL) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT finding_id,run_id,dataset_id,rule_id,column_name,severity,status,reason,failed_record_count,detected_at FROM audit.findings WHERE finding_id=%s", (finding_id,))
                    finding = cur.fetchone()
                    if finding:
                        cur.execute("""SELECT q.quarantine_id,q.lineage_hash FROM audit.finding_quarantine_records f
                            JOIN quarantine.records q ON q.quarantine_id=f.quarantine_id WHERE f.finding_id=%s""", (finding_id,))
                        records = [dict(row) for row in cur.fetchall()]
            if not finding:
                base["missingMetadata"] = ["FINDING_NOT_FOUND"]
            else:
                finding = dict(finding)
                base.update({"runId": finding.get("run_id"), "datasetId": finding.get("dataset_id"),
                             "focusedColumn": finding.get("column_name"), "ruleId": finding.get("rule_id")})
                base["nodes"].append({"id": f"finding:{finding_id}", "name": finding_id, "type": "finding",
                                      "status": finding.get("status"), "severity": finding.get("severity"),
                                      "failedRecords": finding.get("failed_record_count"), "reason": finding.get("reason")})
                for record in records:
                    node_id = f"quarantine:{record['quarantine_id']}"
                    base["nodes"].append({"id": node_id, "name": str(record["quarantine_id"]), "type": "quarantine",
                                          "lineageHash": record.get("lineage_hash"), "status": "OBSERVED"})
                    base["edges"].append({"from": f"finding:{finding_id}", "to": node_id, "relationType": "OBSERVED"})
                base["dataStatus"] = "PARTIAL"
                base["missingMetadata"] = ["FINDING_EXECUTION_PATH_NOT_CAPTURED"]
        except Exception as exc:
            base["sourceErrors"] = [{"source": "audit_db", "code": "SOURCE_UNAVAILABLE", "message": str(exc),
                                     "retryable": True, "observedAt": datetime.now(timezone.utc).isoformat()}]
        base["totalNodes"] = len(base["nodes"]); base["totalEdges"] = len(base["edges"])
        return base

    @staticmethod
    def get_graph(dataset_id: Optional[str] = None, run_id: Optional[str] = None, revision: Optional[int] = None) -> Dict[str, Any]:
        return LineageService.get_lineage(run_id=run_id, dataset_id=dataset_id, revision=revision)

    @staticmethod
    def get_column_lineage(dataset_id: str, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return LineageService.get_lineage(run_id=run_id, dataset_id=dataset_id).get("transformations", [])

    @staticmethod
    def get_lineage_runs(dataset_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            from src.lineage.run_lineage_store import assess_data_status
            store = LineageService._store()
            method = getattr(store, "list_snapshots", None) or getattr(store, "list_runs", None)
            try:
                value = method(dataset_id=dataset_id) if method else []
            except TypeError:
                value = method() if method else []
            if hasattr(value, "ok"):
                value = list(value.snapshot or []) if value.ok else []
            runs = []
            for snapshot in list(value):
                declared = snapshot.get("declaredIO") or []
                inputs = [item.get("dataset") for item in declared
                          if str(item.get("direction", "")).upper() == "INPUT" and item.get("dataset")]
                snap_dataset = snapshot.get("datasetId") or (inputs[0] if inputs else None)
                if dataset_id:
                    clean_target = dataset_id.replace(".csv", "")
                    clean_snap = (snap_dataset or "").replace(".csv", "")
                    if clean_target != clean_snap:
                        continue
                runs.append({
                    "runId": snapshot.get("runId"),
                    "dagId": snapshot.get("dagId"),
                    "datasetId": snap_dataset,
                    "createdAt": snapshot.get("createdAt") or snapshot.get("asOf"),
                    "lifecycleStatus": snapshot.get("lifecycleStatus"),
                    "dataStatus": assess_data_status(snapshot).get("dataStatus"),
                    "revision": snapshot.get("revision"),
                    "asOf": snapshot.get("asOf"),
                    "hasOpenLineage": bool(snapshot.get("logicalTasks")),
                })
            valid_runs = [item for item in runs if item.get("runId")]
            valid_runs.sort(key=lambda r: str(r.get("createdAt") or r.get("asOf") or ""), reverse=True)
            if dataset_id:
                return valid_runs[:1]
            latest_per_ds = {}
            for r in valid_runs:
                ds = (r.get("datasetId") or "unknown").replace(".csv", "")
                if ds not in latest_per_ds:
                    latest_per_ds[ds] = r
            return list(latest_per_ds.values())
        except Exception:
            return []
