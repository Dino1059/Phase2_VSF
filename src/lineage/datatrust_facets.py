"""OpenLineage facets and instrumented column-lineage persistence."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

PRODUCER_URL = "https://github.com/datatrust-os/datatrust"
AUDIT_FACET_SCHEMA = "https://datatrust.org/spec/facets/1-0-0/DataTrustAuditAssuranceFacet.json"
TREATMENT_FACET_SCHEMA = "https://datatrust.org/spec/facets/1-0-0/DataTrustPolicyTreatmentFacet.json"


def build_audit_assurance_facet(evidence_hash: str, previous_hash: str, digital_signature: str,
                                metrics: Dict[str, Any], jurisdiction_chain: Optional[List[str]] = None) -> Dict[str, Any]:
    return {"_producer": PRODUCER_URL, "_schemaURL": AUDIT_FACET_SCHEMA,
            "digitalSignature": digital_signature, "evidenceHash": evidence_hash,
            "previousHash": previous_hash, "jurisdictionChain": jurisdiction_chain or ["GLOBAL", "VN"],
            "scannedCount": metrics.get("scanned", 0), "silverCount": metrics.get("silver", 0),
            "quarantineCount": metrics.get("quarantine", 0), "warningCount": metrics.get("warning", 0),
            "emittedAt": datetime.now(timezone.utc).isoformat()}


def build_policy_treatment_facet(applied_rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"_producer": PRODUCER_URL, "_schemaURL": TREATMENT_FACET_SCHEMA,
            "appliedRules": applied_rules, "rulesCount": len(applied_rules),
            "emittedAt": datetime.now(timezone.utc).isoformat()}


def record_run_column_transformations(run_id: str, dataset_id: str, transformations: List[Dict[str, Any]],
                                      task_id: str, map_index: int, try_number: int) -> None:
    """Persist transformations explicitly emitted by an instrumented task."""
    try:
        from dags.parallel_evaluation_engine import get_db_connection
        from psycopg2.extras import Json
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""INSERT INTO audit.run_column_lineage
            (run_id,dataset_id,task_id,map_index,try_number,transformations_json)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (run_id,dataset_id,task_id,map_index,try_number)
            DO UPDATE SET transformations_json=EXCLUDED.transformations_json,
                          recorded_at=CURRENT_TIMESTAMP""",
            (run_id, dataset_id, task_id, map_index, try_number, Json(transformations)))
        conn.commit(); cur.close(); conn.close()
    except Exception as exc:
        print(f"[Lineage] Failed to persist instrumented column lineage: {exc}")


def get_actual_run_column_lineage(dataset_id: str, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return only explicitly instrumented transformations; never infer from data."""
    if not run_id:
        return []
    try:
        from dags.parallel_evaluation_engine import get_db_connection
        conn = get_db_connection(); cur = conn.cursor()
        cur.execute("""SELECT transformations_json,task_id,map_index,try_number FROM audit.run_column_lineage
                       WHERE dataset_id LIKE %s AND run_id=%s
                         AND task_id <> 'LEGACY_UNATTRIBUTED'
                       ORDER BY recorded_at,task_id,map_index,try_number""",
                    (f"%{dataset_id}%", run_id))
        rows = cur.fetchall(); cur.close(); conn.close()
        return [{**item, "taskId": row[1], "mapIndex": row[2], "tryNumber": row[3]}
                for row in rows if row and row[0] for item in list(row[0])]
    except Exception as exc:
        print(f"[Lineage] Instrumented column lineage unavailable: {exc}")
        return []
