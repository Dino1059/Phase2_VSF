from src.orchestrator.react_engine import ReActEngine, ReActResult
from src.services.llm import GemmaLLMAdapter
from src.tools.base import ToolRegistry
from src.tools.anomaly_detector import AnomalyDetectorTool
from src.tools.telemetry_query import TelemetryQueryTool


class AnomalyAgent:
    """Sub-agent specialized in anomaly detection across telemetry data."""
    name = "anomaly_detector"
    description = "Detects statistical anomalies in EV telemetry and feedback data."

    def __init__(self, llm: GemmaLLMAdapter):
        self.tools = ToolRegistry()
        self.tools.register(AnomalyDetectorTool())
        self.tools.register(TelemetryQueryTool())
        self.engine = ReActEngine(llm, self.tools, max_steps=8)

    def run(self, table_name: str, columns: list[str] | None = None) -> ReActResult:
        col_info = f" Focus on columns: {', '.join(columns)}." if columns else ""
        return self.engine.run(
            task=f"Detect anomalies in '{table_name}'.{col_info} Use both Z-score and IQR methods. Query telemetry for faults. Report all findings.",
            context={"table_name": table_name, "columns": columns or []}
        )
