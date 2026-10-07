"""
DataTrust OS: Profiler Sub-Agent
Analyzes data catalog columns, detects PII attributes, and measures quality distributions.
"""

from typing import Dict, Any, List, Optional
from backend.ai.engine.react_engine import ReActEngine
from backend.ai.tools.profiler_tool import ProfilerTool
from backend.ai.tools.db_query_tool import DBQueryTool


class ProfilerAgent:
    def __init__(self, react_engine: Optional[ReActEngine] = None):
        self.react_engine = react_engine or ReActEngine()
        self.tools = {
            "profiler": ProfilerTool(),
            "db_query": DBQueryTool()
        }

    async def profile_dataset(self, dataset_id: str, sample_size: int = 500) -> Dict[str, Any]:
        """Runs profiling on a dataset using ReAct reasoning."""
        goal = f"Phân tích cấu trúc dữ liệu và đo lường phân bố chất lượng cho dataset '{dataset_id}'"
        context = {"dataset_id": dataset_id, "sample_size": sample_size}
        
        result = await self.react_engine.run(
            goal=goal,
            agent_type="ProfilerAgent",
            tools=self.tools,
            context=context
        )
        # Direct tool execution for structured output
        profile_data = self.tools["profiler"].execute(context)
        result["profile_data"] = profile_data
        return result
