from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Type


@dataclass
class ToolResult:
    """Normalized tool execution result."""

    output: str | None = None
    error: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }

    def __str__(self) -> str:
        if self.error:
            return f"error: {self.error}"
        return self.output or ""


class BaseTool(ABC):
    """Lightweight protocol every tool must implement."""

    name: str
    description: str
    parameters: Dict[str, Any]

    @abstractmethod
    async def __call__(self, **kwargs: Any) -> ToolResult:
        ...

    def to_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolDescriptor:
    cls: Type[BaseTool]
    kwargs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolGroup:
    name: str
    description: str
    tools: List[ToolDescriptor]


class ToolCollection:
    """Runtime container that can route calls to multiple tools."""

    def __init__(self, tools: Sequence[BaseTool]):
        self._tools = {tool.name: tool for tool in tools}

    @property
    def schemas(self) -> List[Dict[str, Any]]:
        return [tool.to_schema() for tool in self._tools.values()]

    def describe(self) -> str:
        return "\n".join(
            f"- {tool.name}: {tool.description}" for tool in self._tools.values()
        )

    async def execute(self, name: str, arguments: Any = None) -> ToolResult:
        if name not in self._tools:
            return ToolResult(error=f"Unknown tool '{name}'. Available: {', '.join(self._tools.keys())}")
        tool = self._tools[name]
        try:
            if arguments is None:
                payload: Dict[str, Any] = {}
            elif isinstance(arguments, dict):
                payload = arguments
            else:
                payload = {"input": arguments}
            return await tool(**payload)
        except Exception as exc:  # pylint: disable=broad-except
            return ToolResult(error=str(exc))
