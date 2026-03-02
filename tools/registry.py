from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type

from .base import Tool, ToolContext, get_tool_class


@dataclass
class ToolConfig:
    """Declarative item to instantiate a tool from registry."""
    name: str                 # "computer" | "bash" | "text_editor" | "browser"
    version: Optional[str] = None
    params: Optional[Dict[str, Any]] = None  # constructor kwargs


class ToolRegistry:
    """
    Keep instantiated tool objects by (name,version).
    """
    def __init__(self, ctx: Optional[ToolContext] = None):
        self.ctx = ctx or ToolContext()
        self._tools: Dict[str, Tool] = {}

    def load(self, items: List[ToolConfig]) -> None:
        for it in items:
            cls = get_tool_class(it.name)
            if not cls:
                raise ValueError(f"Tool '{it.name}' not registered")
            obj: Tool = cls(version=it.version, **(it.params or {}))
            key = self._key(it.name, it.version)
            self._tools[key] = obj

    def get(self, name: str, version: Optional[str] = None) -> Tool:
        key = self._key(name, version)
        if key not in self._tools:
            raise KeyError(f"Tool '{name}' (version={version}) is not loaded")
        return self._tools[key]

    def all(self) -> List[Tool]:
        return list(self._tools.values())

    @staticmethod
    def _key(name: str, version: Optional[str]) -> str:
        return f"{name}:{version or ''}"


# ---------- helpers to build adapter-native tool declarations ----------

def build_tools_for_anthropic(reg: ToolRegistry) -> List[Dict[str, Any]]:
    """
    Convert loaded tools to Anthropic 'messages.create' tools array.
    """
    return [t.to_anthropic_decl(reg.ctx) for t in reg.all()]


def build_tools_for_openai_preview(reg: ToolRegistry) -> List[Dict[str, Any]]:
    """
    For OpenAI Computer Use Preview we typically only need one declaration:
      {"type":"computer_use_preview", "display_width":..., "display_height":..., "environment":"browser|mac|windows|ubuntu"}
    If a 'computer' tool exists we produce that record; otherwise return [].
    """
    try:
        t = reg.get("computer")
    except Exception:
        return []
    ctx = reg.ctx
    env = t.environment if hasattr(t, "environment") else "browser"
    return [{
        "type": "computer_use_preview",
        "display_width": ctx.display_width_px,
        "display_height": ctx.display_height_px,
        "environment": env,
    }]
