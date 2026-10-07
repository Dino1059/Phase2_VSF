"""
DataTrust OS: Tool Registry
"""

from typing import Dict, Any, List, Optional
from backend.ai.tools.base import BaseTool


class ToolRegistry:
    """Central registry for discovering and managing agent tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, str]]:
        return [
            {"name": t.name, "description": t.description}
            for t in self._tools.values()
        ]

    def get_all(self) -> Dict[str, BaseTool]:
        return dict(self._tools)
