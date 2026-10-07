"""
DataTrust OS: Anomaly Sub-Agent
Monitors statistical drift, detects outliers, and flags distribution shifts across L2-L4.
"""

from typing import Dict, Any, List, Optional
from backend.ai.engine.react_engine import ReActEngine
from backend.ai.tools.anomaly_tool import AnomalyTool
from backend.ai.tools.db_query_tool import DBQueryTool


class AnomalyAgent:
    def __init__(self, react_engine: Optional[ReActEngine] = None):
        self.react_engine = react_engine or ReActEngine()
        self.tools = {
            "anomaly_detector": AnomalyTool(),
            "db_query": DBQueryTool()
        }

    async def detect_anomalies(self, dataset_id: str, column_name: str) -> Dict[str, Any]:
        """Runs anomaly and drift analysis using ReAct reasoning."""
        goal = f"Phát hiện dị biệt thống kê và độ trôi phân phối cho cột '{column_name}' trong dataset '{dataset_id}'"
        context = {"dataset_id": dataset_id, "column_name": column_name}

        result = await self.react_engine.run(
            goal=goal,
            agent_type="AnomalyAgent",
            tools=self.tools,
            context=context
        )
        anomaly_data = self.tools["anomaly_detector"].execute(context)
        result["anomaly_data"] = anomaly_data
        return result
