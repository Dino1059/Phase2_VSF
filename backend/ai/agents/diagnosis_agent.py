"""
DataTrust OS: Quarantine Root Cause Diagnosis Sub-Agent
Executes 4-Tier Causal Tracing and ReAct reasoning to analyze why records failed validation.
"""

from typing import Dict, Any, List, Optional
from backend.ai.engine.react_engine import ReActEngine
from backend.ai.services.realtime_tracer import RealtimeTracer
from backend.ai.tools.db_query_tool import DBQueryTool
from backend.database.models import QuarantineRecordModel


class DiagnosisAgent:
    def __init__(
        self,
        react_engine: Optional[ReActEngine] = None,
        tracer: Optional[RealtimeTracer] = None
    ):
        self.react_engine = react_engine or ReActEngine()
        self.tracer = tracer or RealtimeTracer()
        self.tools = {
            "db_query": DBQueryTool()
        }

    async def diagnose_quarantine_record(
        self,
        record: QuarantineRecordModel,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Diagnoses root cause of a quarantine event across the 4 causal tiers.
        """
        goal = f"Chẩn đoán nguyên nhân gốc rễ bản ghi bị cách ly: ID={record.quarantine_id}, cột={record.violation_column}, lý do={record.violation_reason}"
        context = {
            "quarantine_id": record.quarantine_id,
            "dataset_id": record.dataset_id,
            "violation_column": record.violation_column,
            "violation_reason": record.violation_reason
        }

        # 1. Run ReAct engine reasoning loop
        react_result = await self.react_engine.run(
            goal=goal,
            agent_type="DiagnosisAgent",
            tools=self.tools,
            context=context,
            session_id=session_id
        )

        # 2. Extract agent traces and synthesize 4-tier trace report
        active_traces = self.react_engine.get_traces_for_session(react_result["session_id"])
        causal_report = self.tracer.trace_quarantine_record(record, traces=active_traces)

        return {
            "quarantine_id": record.quarantine_id,
            "session_id": react_result["session_id"],
            "react_summary": react_result["final_answer"],
            "total_steps": react_result["total_steps"],
            "causal_trace": causal_report,
            "traces": react_result["traces"]
        }
