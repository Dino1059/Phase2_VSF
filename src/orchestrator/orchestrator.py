from __future__ import annotations
import json
import time
import uuid
from dataclasses import dataclass, field

from src.services.llm import GemmaLLMAdapter
from src.agents.profiler_agent import ProfilerAgent
from src.agents.anomaly_agent import AnomalyAgent
from src.agents.diagnosis_agent import DiagnosisAgent
from src.agents.rule_proposer_agent import RuleProposerAgent
from src.agents.executor_agent import ExecutorAgent
from src.db.connection import get_db


@dataclass
class OrchestratorResult:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    stages: list[dict] = field(default_factory=list)
    proposed_rules: list[dict] = field(default_factory=list)
    pending_approval: list[dict] = field(default_factory=list)
    diagnosis: str = ""
    status: str = "pending"
    total_duration_ms: int = 0


class DataTrustOrchestrator:
    """Top-level orchestrator implementing the full pipeline:
    Profiler → Anomaly → Diagnosis → Rule Proposer → HITL queue → (approval) → Executor
    """

    def __init__(self, llm: GemmaLLMAdapter):
        self.llm = llm
        self.profiler = ProfilerAgent(llm)
        self.anomaly = AnomalyAgent(llm)
        self.diagnosis = DiagnosisAgent(llm)
        self.rule_proposer = RuleProposerAgent(llm)
        self.executor = ExecutorAgent(llm)

    def run_analysis(self, table_name: str, review_text: str | None = None) -> OrchestratorResult:
        """Run the full analysis pipeline on a table."""
        start = time.time()
        result = OrchestratorResult()

        # Stage 1: Profile
        profile_result = self.profiler.run(table_name)
        result.stages.append({
            "stage": "profiling",
            "agent": "profiler",
            "status": profile_result.status,
            "steps": len(profile_result.steps),
            "summary": profile_result.final_answer[:500]
        })

        # Stage 2: Anomaly Detection
        anomaly_result = self.anomaly.run(table_name)
        result.stages.append({
            "stage": "anomaly_detection",
            "agent": "anomaly_detector",
            "status": anomaly_result.status,
            "steps": len(anomaly_result.steps),
            "summary": anomaly_result.final_answer[:500]
        })

        # Stage 3: Diagnosis (if review text provided)
        if review_text:
            diag_result = self.diagnosis.run(review_text)
            result.diagnosis = diag_result.final_answer
            result.stages.append({
                "stage": "diagnosis",
                "agent": "diagnosis",
                "status": diag_result.status,
                "steps": len(diag_result.steps),
                "summary": diag_result.final_answer[:500]
            })

        # Stage 4: Rule Proposal
        rule_result = self.rule_proposer.run(
            table_name,
            profile_summary=profile_result.final_answer[:500],
            anomaly_findings={}
        )
        result.stages.append({
            "stage": "rule_proposal",
            "agent": "rule_proposer",
            "status": rule_result.status,
            "steps": len(rule_result.steps),
            "summary": rule_result.final_answer[:500]
        })

        # Stage 5: Queue rules for HITL approval
        # Rules are stored as 'proposed' and need human approval before execution
        result.status = "awaiting_approval"
        result.total_duration_ms = int((time.time() - start) * 1000)

        # Log orchestration
        self._log_orchestration(result)
        return result

    def execute_approved_rules(self, rule_ids: list[str], dry_run: bool = True) -> list[dict]:
        """Execute approved rules after HITL approval."""
        results = []
        for rule_id in rule_ids:
            exec_result = self.executor.run(rule_id, dry_run=dry_run)
            results.append({
                "rule_id": rule_id,
                "status": exec_result.status,
                "summary": exec_result.final_answer[:500]
            })
        return results

    def _log_orchestration(self, result: OrchestratorResult):
        try:
            from src.services.audit import AuditService
            AuditService.log(
                action="ORCHESTRATION_RUN",
                actor="orchestrator",
                target_table="",
                target_id="",
                details={"stages": len(result.stages), "status": result.status}
            )
        except Exception:
            pass
