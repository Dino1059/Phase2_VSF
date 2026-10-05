"""
DataTrust OS: Tests for OpenLineage + Marquez Integration & Data Lineage Services
Verifies:
1. OpenLineage Custom Facet Specifications (Audit Assurance & Policy Treatment)
2. Run-Level Column Lineage Extraction & Recording
3. LineageService Connectivity, Graph Construction & Fallback Engine
4. FastAPI Lineage Endpoints (/api/lineage/*)
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
    """Verifies LineageService status method returns valid connectivity and URLs."""
    status = LineageService.get_status()
    assert "isConnected" in status
    assert "mode" in status
    assert status["mode"] in ("MARQUEZ_LIVE", "CATALOG_TOPOLOGY_FALLBACK")
    assert "marquezApiUrl" in status
    assert "marquezWebUrl" in status
    assert isinstance(status["totalDatasets"], int)
    assert isinstance(status["totalJobs"], int)


def test_lineage_service_graph():
    """Verifies LineageService graph construction with full 8 stages."""
    graph = LineageService.get_graph("ride_hailing_xanh_sm_trips")
    assert "nodes" in graph
    assert "edges" in graph
    assert graph["totalNodes"] >= 8
    assert graph["totalEdges"] >= 8

    # Verify key architectural layers exist in nodes
    layers = {n["layer"] for n in graph["nodes"]}
    assert "RAW" in layers
    assert "TASK" in layers
    assert "BRONZE" in layers
    assert "SILVER" in layers
    assert "QUARANTINE" in layers
    assert "WARNING" in layers
    assert "AUDIT" in layers


def test_api_lineage_status_endpoint():
    """Tests GET /api/lineage/status endpoint."""
    res = client.get("/api/lineage/status")
    assert res.status_code == 200
    data = res.json()
    assert "isConnected" in data
    assert "mode" in data
    assert "marquezWebUrl" in data


def test_api_lineage_graph_endpoint():
    """Tests GET /api/lineage/graph endpoint."""
    res = client.get("/api/lineage/graph?dataset_id=ride_hailing_xanh_sm_trips")
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) >= 8


def test_api_lineage_column_lineage_endpoint():
    """Tests GET /api/lineage/column-lineage/{dataset_id} endpoint."""
    res = client.get("/api/lineage/column-lineage/ride_hailing_xanh_sm_trips")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    assert any(c["source_column"] == "customer_phone" for c in data)


def test_api_lineage_runs_endpoint():
    """Tests GET /api/lineage/runs endpoint."""
    res = client.get("/api/lineage/runs")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
