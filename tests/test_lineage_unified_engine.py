"""
DataTrust OS: Tests for Unified Lineage Engine
Verifies:
1. OpenLineage Custom Facet Specifications (Audit Assurance & Policy Treatment)
2. Run-Level Column Lineage Extraction & Recording
3. Unified Lineage Engine:
   - finding_id Targeted Root-Cause Slicing (5 nodes: Source -> Ingest -> Column -> Rule -> Quarantine)
   - run_id Dynamic Full Pipeline Graph & Schema Diff
   - column Filtering & Upstream/Downstream highlighting
4. FastAPI Endpoints:
   - GET /api/lineage (Unified)
   - GET /api/findings/{finding_id}/lineage
   - GET /api/runs/{run_id}/lineage
   - GET /api/runs/{run_id}/lineage/export-openlineage
"""

import pytest
from fastapi.testclient import TestClient
from backend.api.main import app
from src.lineage.datatrust_facets import (
    build_audit_assurance_facet,
    build_policy_treatment_facet,
    get_actual_run_column_lineage,
    record_run_column_transformations,
    PRODUCER_URL,
    AUDIT_FACET_SCHEMA,
    TREATMENT_FACET_SCHEMA,
)
from backend.lineage.lineage_service import LineageService


client = TestClient(app)


def test_custom_audit_assurance_facet_conformance():
    """Verifies that DataTrust custom audit facet conforms to OpenLineage custom facet spec."""
    facet = build_audit_assurance_facet(
        evidence_hash="test_evidence_hash_123",
        previous_hash="test_prev_hash_000",
        digital_signature="SIG-AIRFLOW-3LANE-GSM-IPO-2026",
        metrics={"scanned": 100, "silver": 95, "quarantine": 3, "warning": 2},
        jurisdiction_chain=["GLOBAL", "VN"]
    )

    assert facet["_producer"] == PRODUCER_URL
    assert facet["_schemaURL"] == AUDIT_FACET_SCHEMA
    assert facet["digitalSignature"] == "SIG-AIRFLOW-3LANE-GSM-IPO-2026"
    assert facet["evidenceHash"] == "test_evidence_hash_123"
    assert facet["previousHash"] == "test_prev_hash_000"
    assert facet["scannedCount"] == 100
    assert facet["silverCount"] == 95
    assert facet["quarantineCount"] == 3
    assert facet["warningCount"] == 2
    assert "emittedAt" in facet


def test_custom_policy_treatment_facet_conformance():
    """Verifies that policy treatment custom facet conforms to OpenLineage spec."""
    facet = build_policy_treatment_facet([
        {"rule_id": "VN_ND356_PHONE_01", "operation": "MASK_PHONE_MIDDLE_5"}
    ])

    assert facet["_producer"] == PRODUCER_URL
    assert facet["_schemaURL"] == TREATMENT_FACET_SCHEMA
    assert facet["rulesCount"] == 1
    assert len(facet["appliedRules"]) == 1


def test_actual_run_column_lineage_extraction():
    """Verifies actual column transformation extraction for ride_hailing_xanh_sm_trips."""
    cols = get_actual_run_column_lineage("ride_hailing_xanh_sm_trips")
    assert isinstance(cols, list)
    assert len(cols) >= 2

    # Check PII phone masking
    phone_col = next((c for c in cols if "customer_phone" in c.get("source_column", "")), None)
    assert phone_col is not None
    assert phone_col["treatment_operation"] == "MASK_PHONE_MIDDLE_5"
    assert phone_col["target_column"] == "customer_contact"
    assert "91/2025/QH15" in phone_col["legal_basis"]

    # Check driver pseudonymization
    driver_col = next((c for c in cols if c.get("source_column") == "driver_id"), None)
    assert driver_col is not None
    assert driver_col["treatment_operation"] == "PSEUDONYMIZE_SHA256"
    assert "GDPR" in driver_col["legal_basis"]


def test_lineage_service_status():
    """Verifies LineageService status method returns valid connectivity and mode."""
    status = LineageService.get_status()
    assert "isConnected" in status
    assert status["isConnected"] is True
    assert "mode" in status
    assert status["mode"] in ("CATALOG_NATIVE", "CATALOG_TOPOLOGY", "CATALOG_TOPOLOGY_FALLBACK")
    assert isinstance(status["totalDatasets"], int)
    assert isinstance(status["totalJobs"], int)


def test_lineage_service_full_run_graph():
    """Verifies LineageService full run graph construction with all 8 stages."""
    graph = LineageService.get_lineage(run_id="run_5b320bf9b22d")
    assert graph["scope"] == "FULL_RUN"
    assert "nodes" in graph
    assert "edges" in graph
    assert graph["totalNodes"] >= 8
    assert graph["totalEdges"] >= 8
    assert "schemaDiff" in graph
    assert isinstance(graph["schemaDiff"], list)

    layers = {n["layer"] for n in graph["nodes"]}
    assert "RAW" in layers
    assert "TASK" in layers
    assert "BRONZE" in layers
    assert "SILVER" in layers
    assert "QUARANTINE" in layers
    assert "WARNING" in layers
    assert "AUDIT" in layers


def test_lineage_service_finding_targeted_graph():
    """Verifies LineageService targeted root-cause slicing for finding_id."""
    # Use real finding id if present, or fallback mock id
    lineage = LineageService.get_lineage(finding_id="F-4f5bbe1dd9")
    assert lineage["scope"] == "FINDING_TARGETED"
    assert lineage["findingId"] == "F-4f5bbe1dd9"
    assert "nodes" in lineage
    assert "edges" in lineage
    assert lineage["totalNodes"] == 5

    # Check the 5 targeted nodes
    roles = {n.get("role") for n in lineage["nodes"]}
    assert "UPSTREAM_ROOT" in roles
    assert "INGEST_STAGE" in roles
    assert "SUBJECT_COLUMN" in roles
    assert "VIOLATED_RULE" in roles
    assert "OUTCOME_TARGET" in roles

    # AI context provided
    assert "aiExplanationContext" in lineage
    assert "summary" in lineage["aiExplanationContext"]


def test_api_lineage_unified_endpoint():
    """Tests GET /api/lineage with finding_id and run_id query params."""
    # 1. With finding_id
    res_f = client.get("/api/lineage?finding_id=F-4f5bbe1dd9")
    assert res_f.status_code == 200
    data_f = res_f.json()
    assert data_f["scope"] == "FINDING_TARGETED"
    assert len(data_f["nodes"]) == 5

    # 2. With run_id
    res_r = client.get("/api/lineage?run_id=run_5b320bf9b22d")
    assert res_r.status_code == 200
    data_r = res_r.json()
    assert data_r["scope"] == "FULL_RUN"
    assert len(data_r["nodes"]) >= 8


def test_api_finding_lineage_endpoint():
    """Tests GET /api/findings/{finding_id}/lineage endpoint."""
    res = client.get("/api/findings/F-4f5bbe1dd9/lineage")
    assert res.status_code == 200
    data = res.json()
    assert data["scope"] == "FINDING_TARGETED"
    assert "nodes" in data


def test_api_run_lineage_endpoint():
    """Tests GET /api/runs/{run_id}/lineage endpoint."""
    res = client.get("/api/runs/run_5b320bf9b22d/lineage")
    assert res.status_code == 200
    data = res.json()
    assert data["scope"] == "FULL_RUN"
    assert "schemaDiff" in data


def test_api_export_openlineage_endpoint():
    """Tests GET /api/runs/{run_id}/lineage/export-openlineage endpoint."""
    res = client.get("/api/runs/run_5b320bf9b22d/lineage/export-openlineage")
    assert res.status_code == 200
    data = res.json()
    assert data["_producer"] == PRODUCER_URL
    assert "OpenLineage" in data["_schemaURL"]
    assert data["eventType"] == "COMPLETE"
    assert "run" in data
    assert "dataTrustAuditAssurance" in data["run"]["facets"]
