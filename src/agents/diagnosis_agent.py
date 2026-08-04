from src.orchestrator.react_engine import ReActEngine, ReActResult
from src.services.llm import GemmaLLMAdapter
from src.tools.base import ToolRegistry
from src.tools.nlp_extractor import NLPExtractorTool
from src.tools.telemetry_query import TelemetryQueryTool
from src.tools.anomaly_detector import AnomalyDetectorTool


class DiagnosisAgent:
    """Sub-agent that cross-references NLP insights with telemetry to diagnose root causes."""
    name = "diagnosis"
    description = "Cross-domain root-cause diagnosis using NLP + telemetry + anomaly data."

    def __init__(self, llm: GemmaLLMAdapter):
        self.tools = ToolRegistry()
        self.tools.register(NLPExtractorTool())
        self.tools.register(TelemetryQueryTool())
        self.tools.register(AnomalyDetectorTool())
        self.engine = ReActEngine(llm, self.tools, max_steps=10)

    def run(self, review_text: str, station_id: str | None = None) -> ReActResult:
        ctx = {"review_text": review_text}
        if station_id:
            ctx["station_id"] = station_id
        return self.engine.run(
            task=f"Diagnose the root cause of this customer complaint: '{review_text}'. Cross-reference with telemetry data and anomalies. Provide structured diagnosis.",
            context=ctx
        )
