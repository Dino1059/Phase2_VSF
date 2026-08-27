"""Run All on ev_telemetry: canonical tables, no clean.*, propose finishes."""
import os
import time

import pandas as pd
import pytest

from src.utils.table_utils import (
    canonical_pipeline_table,
    pipeline_target_tables,
)
from src.tools.chat_tools import _resolve_table_target, ProposeQualityRulesTool
from src.tools.datasource import StructuredSource
from src.tools.rule_proposer import RuleProposerTool


def test_pipeline_tables_ev_telemetry_is_single_canonical():
    listed = [
        "clean.trips",
        "clean.ev_telemetry",
        "quarantine.trips",
        "main.ev_telemetry",
        "main.trips",
        "main.charging_sessions",
    ]
    assert pipeline_target_tables("ev_telemetry", listed=listed) == ["ev_telemetry"]
    assert canonical_pipeline_table("clean.trips") == "trips"
    assert canonical_pipeline_table("quarantine.ev_telemetry") == "ev_telemetry"


def test_pipeline_tables_drops_clean_and_quarantine_for_warehouse():
    listed = ["clean.trips", "quarantine.ev_telemetry", "main.trips", "main.ev_telemetry"]
    out = pipeline_target_tables("vingroup_pilot", listed=listed)
    assert out == ["trips", "ev_telemetry"]
    assert not any(t.startswith("clean.") or t.startswith("quarantine.") for t in out)


def test_resolve_ev_telemetry_sets_canonical_table():
    _path, table, base = _resolve_table_target("ev_telemetry")
    assert base == "ev_telemetry"
    assert table == "ev_telemetry"


def test_get_user_tables_skips_clean_quarantine():
    class _R:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

    class _Conn:
        def execute(self, q):
            if "IN ('main', 'raw')" in q or 'IN (\'main\', \'raw\')' in q:
                return _R([
                    ("clean", "trips"),
                    ("main", "ev_telemetry"),
                    ("quarantine", "ev_telemetry"),
                    ("main", "trips"),
                    ("raw", "synthetic_feedback"),
                ])
            return _R([])

    tables = StructuredSource._get_user_tables(_Conn())
    assert "ev_telemetry" in tables
    assert "trips" in tables
    assert "nlp_feedback" in tables
    assert not any("clean" in t or "quarantine" in t or "." in t for t in tables)


def test_detect_l1_uses_trips_config_for_clean_prefix(monkeypatch):
    from src.orchestrator import orchestrator as orch

    captured = []
    monkeypatch.setattr(orch, "_notify", lambda *a, **k: captured.append((a, k)))

    class _Empty:
        def detect_range_violations(self, **_k):
            return []
        def detect_null_violations(self, **_k):
            return []
        def detect_entity_anomalies(self, **_k):
            return []
        def detect_bivariate_residual_anomalies(self, **_k):
            return []
        def detect_cusum_shift(self, **_k):
            return []

    monkeypatch.setattr("src.reliability.detectors.l1_rules.L1ConstraintDetector", lambda *a, **k: _Empty())
    monkeypatch.setattr("src.reliability.detectors.l2_contextual.L2ContextualDetector", lambda *a, **k: _Empty())
    monkeypatch.setattr("src.reliability.detectors.l3_relational.L3RelationalDetector", lambda *a, **k: _Empty())
    monkeypatch.setattr("src.reliability.detectors.l4_changepoint.L4ChangepointDetector", lambda *a, **k: _Empty())
    df = pd.DataFrame({
        "vehicle_vin": ["V1"],
        "pickup_datetime": pd.to_datetime(["2026-01-01"]),
        "fare_amount": [12.0],
        "trip_distance_km": [3.0],
    })
    sigs = orch._detect_l1_l4_signals("clean.trips", df, "proj-test")
    skip = [c for c in captured if "No signal config" in str(c)]
    assert not skip
    assert set(sigs) == {"L1", "L2", "L3", "L4"}


def test_drop_notify_skip_rows_keeps_real_beats():
    from src.api.traces import _drop_notify_skip_rows

    skip = (
        0, None, "anomaly_detect", "anomaly_detect", None, None,
        "Table 'clean.trips': No signal config. Skipping L1-L4.", None, None, None, None,
    )
    real = (
        1, None, "detect_anomalies", "detect_anomalies", None, None,
        "Detect anomalies finished", None, None, None, None,
    )
    propose = (
        2, None, "propose_quality_rules", "propose_quality_rules", None, None,
        "11 rules", None, None, None, None,
    )
    kept = _drop_notify_skip_rows([skip, real, propose])
    assert kept == [real, propose]


def test_propose_does_not_rerun_detect(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("detect must not re-run inside propose")

    class Instant:
        def generate_structured(self, **_k):
            raise RuntimeError("llm off")

    monkeypatch.setattr("src.tools.chat_tools.DetectAnomaliesTool.execute", boom)
    monkeypatch.setattr("src.tools.chat_tools.persist_hitl_proposals", lambda *a, **k: [])
    monkeypatch.setattr("src.tools.rule_proposer.LLM_RULE_TIMEOUT", 0.2)
    monkeypatch.setattr(
        "src.tools.chat_tools.load_dataset",
        lambda **k: pd.DataFrame({"battery_soc": [1.0], "vehicle_vin": ["x"], "timestamp": ["2026-01-01"]}),
    )
    monkeypatch.setattr("src.tools.rule_proposer.GemmaLLMAdapter", lambda *a, **k: Instant())

    res = ProposeQualityRulesTool().execute({"dataset_key": "ev_telemetry"})
    assert res.status == "success"
    assert int(res.output_data.get("count") or 0) >= 1
    tables = res.output_data.get("tables_covered") or []
    assert "clean.trips" not in tables
    assert "ev_telemetry" in tables


def test_rule_proposer_timeout_falls_back_to_heuristic(monkeypatch):
    os.environ["RULE_PROPOSER_LLM_TIMEOUT"] = "0.25"

    class Hang:
        def generate_structured(self, **_k):
            time.sleep(8)
            return {"rules": []}

    monkeypatch.setattr("src.tools.rule_proposer.LLM_RULE_TIMEOUT", 0.25)
    monkeypatch.setattr(
        "src.tools.chat_tools.persist_hitl_proposals",
        lambda *a, **k: [],
        raising=False,
    )

    t0 = time.time()
    out = RuleProposerTool(llm=Hang()).execute({"target_table": "ev_telemetry"})
    elapsed = time.time() - t0
    assert elapsed < 3.0
    assert out["rule_count"] >= 1
    assert any("soc" in (r.get("rule_name") or "").lower() for r in out["proposed_rules"])
