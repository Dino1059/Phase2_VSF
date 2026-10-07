"""
DataTrust OS: AI Tool Base Class
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseTool(ABC):
    """Abstract base class for all AI Agent tools."""

    name: str = "base_tool"
    description: str = "Base tool description"

    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Any:
        """Executes the tool synchronously."""
        pass

    async def execute_async(self, input_data: Dict[str, Any]) -> Any:
        """Executes the tool asynchronously (default wrapper around execute)."""
        return self.execute(input_data)
