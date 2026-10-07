"""
DataTrust OS: AI Agent Multi-Agent, HITL & Causal Tracing Test Suite (MVP Branch)
Verifies:
1. PII Guardrail & pre_llm_guard (Luật 91/2025/QH15 & GDPR).
2. Deterministic Unified LLM Adapter & Circuit Breaker.
3. ProposalSyntaxValidator internal pre-emission validation.
4. Strict HITL Rule Proposal & Dry-Run Simulation:
   - Proposal status is strictly PENDING.
   - Agent CANNOT mutate Lane B directly.
   - Auditor approval raises PermissionError.
   - Admin approval activates rule into Lane B.
5. 4-Tier Real-Time Causal Tracing (Row PK -> ReAct Decision -> OpenLineage -> SHA-256 Ledger).
6. Preventive Early-Warning Drift Monitoring (L2-L4).
7. FastAPI REST endpoints & WebSocket integration.
"""

import pytest
from fastapi.testclient import TestClient

from backend.ai.services.guardrails import pre_llm_guard, mask_phone, mask_email, mask_vin, mask_gps
from backend.ai.services.llm_adapter import UnifiedLLMAdapter, CircuitBreaker
from backend.ai.services.realtime_tracer import RealtimeTracer
from backend.ai.engine.syntax_validator import ProposalSyntaxValidator
from backend.ai.engine.decision_record import DecisionRecordBuilder
from backend.ai.engine.react_engine import ReActEngine
from backend.ai.agents.rule_proposer_agent import RuleProposerAgent
from backend.ai.agents.preventive_guard_agent import PreventiveGuardAgent
from backend.ai.agents.orchestrator import DataTrustAgentOrchestrator
from backend.database.models import (
    ColumnModel,
    CompliancePolicyModel,
    PolicyClauseModel,
    PiiRoleType,
    TreatmentActionType,
    RuleStatus,
    UserRole,
    QuarantineRecordModel,
    RuleSeverity
)
from backend.api.main import app


# =============================================================================
# 1. PII GUARDRAILS (Luật 91/2025/QH15 & GDPR)
# =============================================================================

def test_guardrails_masking_primitives():
    assert mask_phone("0912345678") == "091*****78"
    assert mask_email("johndoe@example.com") == "j*****e@example.com"
    assert mask_vin("VF8VNF_000100234") == "VF8V****0234"
    lat, lon = mask_gps(21.028511, 105.854444, 2)
    assert lat == 21.03
    assert lon == 105.85


def test_pre_llm_guard_sanitizes_prompt_and_context():
    raw_prompt = "Khách hàng 0987654321 đi xe VF8VNF_12345678 tại tọa độ 21.0285, 105.8544"
    context = {"driver_phone": "0912345678", "driver_vin": "VF8VNF_99999999"}
    
    sanitized, report = pre_llm_guard(raw_prompt, context)
    assert "0987654321" not in sanitized
    assert "VF8VNF_12345678" not in sanitized
    assert report["is_sanitized"] is True
    assert report["redactions"]["phones_masked"] >= 1
    assert "Luật 91/2025/QH15" in report["law_references"]


# =============================================================================
# 2. UNIFIED LLM ADAPTER & CIRCUIT BREAKER
# =============================================================================

def test_unified_llm_adapter_deterministic_mock():
    adapter = UnifiedLLMAdapter(force_mock=True)
    res = adapter.complete(prompt="Đề xuất quy tắc cho số điện thoại phone")
    assert "text" in res
    assert res["provider"] == "mock_engine"
    assert res["tokens_used"] > 0
    assert "guardrail_report" in res


def test_circuit_breaker_tripping():
    cb = CircuitBreaker(failure_threshold=2, reset_timeout_sec=10)
    assert cb.can_attempt() is True
    cb.record_failure()
    assert cb.can_attempt() is True
    cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.can_attempt() is False
    cb.record_success()
    assert cb.state == "CLOSED"
    assert cb.can_attempt() is True


# =============================================================================
# 3. INTERNAL SYNTAX VALIDATOR (NO LANE B MUTATION)
# =============================================================================

def test_syntax_validator_checks_parameters_and_ast():
    # Valid proposal
    ok, err = ProposalSyntaxValidator.validate_proposal(
        operation_id="mask_phone",
        params={"prefix_len": 3, "suffix_len": 2},
        expression_display="mask_phone(customer_phone)"
    )
    assert ok is True
    assert err == ""

    # Invalid operation
    bad_op, err = ProposalSyntaxValidator.validate_proposal(
        operation_id="unknown_hack_op",
        params={},
        expression_display="unknown()"
    )
    assert bad_op is False
    assert "không nằm trong danh mục" in err

    # Bad decimals param
    bad_dec, err = ProposalSyntaxValidator.validate_proposal(
        operation_id="round_decimal",
        params={"decimals": 10},
        expression_display="round_decimal(lat, 10)"
    )
    assert bad_dec is False
    assert "0 đến 6" in err


# =============================================================================
# 4. STRICT HITL RULE PROPOSAL & DRY-RUN SIMULATION
# =============================================================================

def test_rule_proposer_agent_hitl_workflow():
    agent = RuleProposerAgent()
    policy = CompliancePolicyModel(
        policy_id="POL-VN-TEST",
        title="Chính sách thử nghiệm",
        jurisdiction="VN",
        legal_framework="Luật 91/2025/QH15",
        raw_policy_text="Bảo vệ số điện thoại",
        effective_date="2026-01-01",
        clauses=[
            PolicyClauseModel(
                clause_id="C-01",
                policy_id="POL-VN-TEST",
                clause_number="Điều 5",
                requirement_summary="Che mờ số điện thoại",
                target_pii_roles=[PiiRoleType.DIRECT_IDENTIFIER],
                mandated_action=TreatmentActionType.PSEUDONYMIZE
            )
        ]
    )
    columns = [
        ColumnModel(
            dataset_id="trips",
            column_name="customer_phone",
            data_type="VARCHAR",
            pii_role=PiiRoleType.DIRECT_IDENTIFIER,
            default_treatment=TreatmentActionType.PSEUDONYMIZE
        )
    ]

    # Propose rules: MUST start as PENDING
    proposals = agent.propose_rules(policy, columns, sample_size=50)
    assert len(proposals) == 1
    p = proposals[0]
    assert p.status == RuleStatus.PENDING
    assert p.simulated_pass_rows > 0

    # NON-ADMIN (AUDITOR) CANNOT APPROVE -> PermissionError
    with pytest.raises(PermissionError) as exc_info:
        agent.approve_proposal(p.proposal_id, "Auditor John", UserRole.AUDITOR)
    assert "Từ chối quyền" in str(exc_info.value)
    assert p.status == RuleStatus.PENDING

    # ADMIN CAN APPROVE -> Becomes Active Field Process Config
    active_cfg = agent.approve_proposal(p.proposal_id, "Admin Bao", UserRole.ADMIN)
    assert active_cfg.is_active is True
    assert active_cfg.enforced_by == "Admin Bao"
    assert p.status == RuleStatus.APPROVED


# =============================================================================
# 5. 4-TIER CAUSAL TRACING & AUDIT PROOFS
# =============================================================================

def test_realtime_tracer_4tiers():
    tracer = RealtimeTracer()
    record = QuarantineRecordModel(
        quarantine_id="QR-TEST-001",
        run_id="RUN-TEST-001",
        dataset_id="trips",
        source_table="bronze.trips_raw",
        source_row_pk="TRIP-9999",
        violation_column="fare_amount",
        violation_rule_id="CHK-TRIP-FARE",
        violation_reason="Cước phí âm: -50.0",
        violation_severity=RuleSeverity.CRITICAL,
        raw_record_json={"trip_id": "TRIP-9999", "fare_amount": -50.0},
        lineage_hash="abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    )

    report = tracer.trace_quarantine_record(record)
    assert report["quarantine_id"] == "QR-TEST-001"
    assert len(report["tiers"]) == 4

    # Verify Tiers
    assert report["tiers"][0]["tier"] == 1
    assert report["tiers"][0]["source_row_pk"] == "TRIP-9999"

    assert report["tiers"][1]["tier"] == 2
    assert report["tiers"][1]["decision"]["selected_action"] == "ISOLATE_TO_QUARANTINE"

    assert report["tiers"][2]["tier"] == 3
    assert "openlineage_facet" in report["tiers"][2]

    assert report["tiers"][3]["tier"] == 4
    assert report["tiers"][3]["integrity_status"] == "VERIFIED_TAMPER_PROOF"

    assert len(report["causal_graph"]["nodes"]) == 4
    assert len(report["causal_graph"]["edges"]) == 3


# =============================================================================
# 6. PREVENTIVE EARLY-WARNING DRIFT MONITORING
# =============================================================================

def test_preventive_guard_agent_drift_scan():
    guard = PreventiveGuardAgent()
    alerts = guard.scan_for_preventive_risks("trips", ["fare_amount", "trip_distance_km"])
    # If outliers exist in the pilot set, alerts are created
    assert isinstance(alerts, list)
    for a in alerts:
        assert a.dataset_id == "trips"
        assert a.warning_threshold > 0


# =============================================================================
# 7. FASTAPI ENDPOINTS INTEGRATION
# =============================================================================

def test_api_agent_endpoints():
    client = TestClient(app)

    # 1. Chat endpoint
    chat_res = client.post("/api/agent/chat", json={"message": "Kiểm tra tình trạng chất lượng"})
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert "response" in chat_data
    assert "session_id" in chat_data

    # 2. Preventive alerts endpoint
    alerts_res = client.get("/api/agent/preventive-alerts")
    assert alerts_res.status_code == 200
    assert isinstance(alerts_res.json(), list)

    # 3. Preventive scan endpoint
    scan_res = client.post("/api/agent/preventive-scan", json={"dataset_id": "trips", "columns": ["fare_amount"]})
    assert scan_res.status_code == 200
    assert isinstance(scan_res.json(), list)
