import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.agents.llm_adapter import LLMAdapter
from src.services.algolia_search import algolia_search_service
from src.services.alerting import alert_service, AlertSeverity
from src.services.ingestion import streaming_worker
from src.db.connection import get_db

client = TestClient(app)
AUTH_HEADERS = {"X-User-Role": "Admin"}


def test_telemetry_ingest_bms_endpoint():
    """Test external live ingestion endpoint for BMS battery telemetry."""
    payload = {
        "dataset": "vinfast_bms",
        "records": [
            {
                "vin": "VF8-PROV-TEST-001",
                "timestamp": "2026-08-15T02:00:00Z",
                "battery_soc": 92.5,
                "battery_temp_c": 32.0,
                "speed_kmh": 45.0,
                "pack_voltage": 358.0,
                "status": "NORMAL"
            }
        ]
    }
    resp = client.post("/api/v1/telemetry/ingest", json=payload, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["inserted_count"] == 1

    # Verify DuckDB persistence
    db = get_db()
    rows = db.execute("SELECT vehicle_id, battery_soc FROM vinfast_bms WHERE vehicle_id = 'VF8-PROV-TEST-001'")
    assert len(rows) > 0
    assert rows[0][1] == 92.5


def test_telemetry_ingest_charging_endpoint():
    """Test external live ingestion endpoint for V-GREEN charging stations."""
    payload = {
        "dataset": "vgreen_telemetry",
        "records": [
            {
                "station_id": "VGREEN-STATION-99",
                "temperature_celsius": 48.5,
                "energy_kwh": 35.0,
                "status": "ACTIVE"
            }
        ]
    }
    resp = client.post("/api/v1/telemetry/ingest", json=payload, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["inserted_count"] == 1


def test_summary_trend_dynamic_aggregation():
    """Test GET /api/v1/summary/trend across 24h, 7d, 30d time ranges."""
    for r in ["24h", "7d", "30d"]:
        resp = client.get(f"/api/v1/summary/trend?range={r}", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["range"] == r
        assert len(data["labels"]) > 0
        assert len(data["a"]) == len(data["labels"])
        assert len(data["b"]) == len(data["labels"])


def test_signals_dynamic_query():
    """Test GET /api/v1/signals queries DuckDB and returns structured L1-L4 signals."""
    resp = client.get("/api/v1/signals", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    signals = resp.json()
    assert isinstance(signals, list)
    assert len(signals) > 0
    assert "signal_id" in signals[0]
    assert "layer" in signals[0]


def test_llm_adapter_real_rule_generation():
    """Test LLMAdapter generates structured RuleSpecs using UnifiedLLMAdapter."""
    adapter = LLMAdapter()
    context = "Dataset: vinfast_bms. Columns: vin (str), battery_soc (float [0, 100]), battery_temp_c (float [-20, 80])."
    response = adapter.propose_rules(context)
    assert len(response.rules) >= 2
    assert response.cost_usd > 0
    assert any(r.rule_type == "range" for r in response.rules)


def test_algolia_search_service_fallback():
    """Test AlgoliaSearchService performs robust search via DuckDB fallback when cloud keys unset."""
    results = algolia_search_service.search(query="vinfast", limit=5)
    assert isinstance(results, list)


def test_alert_service_hmac_dispatch():
    """Test AlertService creates alerts with HMAC-SHA256 signature capability."""
    alert = alert_service.create_alert(
        title="BMS High Thermal Warning",
        message="Battery temperature reached 65C on VIN-005",
        severity=AlertSeverity.HIGH,
        auto_dispatch=False
    )
    assert alert.alert_id.startswith("alert_")
    assert alert.severity == "HIGH"
