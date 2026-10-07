"""
DataTrust OS: Central AI Multi-Agent Orchestrator
Coordinates:
- ProfilerAgent (Data structural profiling & PII discovery)
- AnomalyAgent (L2-L4 statistical drift detection)
- DiagnosisAgent (4-Tier root-cause causal analysis for Quarantine records)
- RuleProposerAgent (HITL rule proposals & Dry-run simulation)
- PreventiveGuardAgent (Real-time early warning drift monitoring)
- Real-time ReAct thought streaming over WebSockets
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime, timezone

from backend.ai.services.llm_adapter import UnifiedLLMAdapter
from backend.ai.services.realtime_tracer import RealtimeTracer
from backend.ai.engine.react_engine import ReActEngine
from backend.ai.agents.profiler_agent import ProfilerAgent
from backend.ai.agents.anomaly_agent import AnomalyAgent
from backend.ai.agents.diagnosis_agent import DiagnosisAgent
from backend.ai.agents.rule_proposer_agent import RuleProposerAgent
from backend.ai.agents.preventive_guard_agent import PreventiveGuardAgent
from backend.database.models import QuarantineRecordModel, AgentTraceModel, ProposedRuleModel

logger = logging.getLogger("DataTrust.Orchestrator")


class DataTrustAgentOrchestrator:
    """Central orchestrator managing specialized agents and live execution streams."""

    def __init__(self, llm_adapter: Optional[UnifiedLLMAdapter] = None):
        self.llm_adapter = llm_adapter or UnifiedLLMAdapter()
        self.tracer = RealtimeTracer()
        self.react_engine = ReActEngine(llm_adapter=self.llm_adapter)

        # Initialize sub-agents
        self.profiler_agent = ProfilerAgent(react_engine=self.react_engine)
        self.anomaly_agent = AnomalyAgent(react_engine=self.react_engine)
        self.diagnosis_agent = DiagnosisAgent(react_engine=self.react_engine, tracer=self.tracer)
        self.rule_proposer_agent = RuleProposerAgent(react_engine=self.react_engine)
        self.preventive_guard_agent = PreventiveGuardAgent(react_engine=self.react_engine)

        self._active_listeners: List[Callable[[AgentTraceModel], Awaitable[None]]] = []

    def register_step_listener(self, listener: Callable[[AgentTraceModel], Awaitable[None]]):
        self._active_listeners.append(listener)

    def unregister_step_listener(self, listener: Callable[[AgentTraceModel], Awaitable[None]]):
        if listener in self._active_listeners:
            self._active_listeners.remove(listener)

    async def _broadcast_step(self, trace: AgentTraceModel):
        for listener in list(self._active_listeners):
            try:
                await listener(trace)
            except Exception as e:
                logger.warning(f"Error broadcasting step trace to listener: {e}")

    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Processes general user dialogue, routing to relevant agents or executing ReAct.
        """
        msg_lower = message.lower()
        context = context or {}

        # If question is about profiling
        if "profile" in msg_lower or "thống kê" in msg_lower:
            dataset_id = context.get("dataset_id", "trips")
            res = await self.profiler_agent.profile_dataset(dataset_id)
            return {
                "response": f"Đã hoàn thành phân tích profiling cho {dataset_id}.",
                "session_id": res.get("session_id"),
                "data": res.get("profile_data"),
                "traces": res.get("traces", [])
            }

        # If question is about anomalies or drift
        if "drift" in msg_lower or "dị biệt" in msg_lower or "lệch" in msg_lower:
            dataset_id = context.get("dataset_id", "trips")
            col = context.get("column_name", "fare_amount")
            res = await self.anomaly_agent.detect_anomalies(dataset_id, col)
            return {
                "response": f"Đã kiểm tra dị biệt và độ trôi phân phối cho cột {col}.",
                "session_id": res.get("session_id"),
                "data": res.get("anomaly_data"),
                "traces": res.get("traces", [])
            }

        # General conversational assistant via ReAct engine
        tools = {"profiler": self.profiler_agent.tools["profiler"]}
        res = await self.react_engine.run(
            goal=message,
            agent_type="AssistantAgent",
            tools=tools,
            context=context,
            session_id=session_id,
            step_callback=self._broadcast_step
        )

        return {
            "response": res.get("final_answer") or "Hệ thống đã phân tích và phản hồi yêu cầu.",
            "session_id": res.get("session_id"),
            "traces": res.get("traces", [])
        }

    async def diagnose_quarantine(
        self,
        record: QuarantineRecordModel,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Runs 4-tier root-cause diagnosis on a quarantine record."""
        return await self.diagnosis_agent.diagnose_quarantine_record(record, session_id=session_id)

    def scan_preventive_alerts(self, dataset_id: str, columns: List[str]):
        """Runs preventive early-warning drift check."""
        return self.preventive_guard_agent.scan_for_preventive_risks(dataset_id, columns)
