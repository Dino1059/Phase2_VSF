from src.orchestrator.react_engine import ReActEngine, ReActResult
from src.services.llm import GemmaLLMAdapter
from src.tools.base import ToolRegistry
from src.tools.profiler import DataProfilerTool


class ProfilerAgent:
    """Sub-agent specialized in data profiling."""
    name = "profiler"
    description = "Profiles DuckDB tables to compute column-level statistics."

    def __init__(self, llm: GemmaLLMAdapter):
        self.tools = ToolRegistry()
        self.tools.register(DataProfilerTool())
        self.engine = ReActEngine(llm, self.tools, max_steps=5)

    def run(self, table_name: str) -> ReActResult:
        return self.engine.run(
            task=f"Profile the '{table_name}' table. Report column statistics, null rates, and data quality observations.",
            context={"table_name": table_name}
        )
