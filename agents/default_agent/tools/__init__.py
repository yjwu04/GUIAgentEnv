from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict

from .base import ToolCollection
from .default_tools import DEFAULT_TOOL_GROUP_NAME, build_default_tools


ToolBuilder = Callable[[Path], ToolCollection]

_BUILDERS: Dict[str, ToolBuilder] = {
    DEFAULT_TOOL_GROUP_NAME: build_default_tools,
    "default": build_default_tools,
    "default_tools": build_default_tools,
}


def available_tool_groups() -> list[str]:
    return list(_BUILDERS.keys())


def build_tool_collection(group_name: str, workspace_root: Path) -> ToolCollection:
    if group_name not in _BUILDERS:
        raise ValueError(
            f"Unsupported tool group '{group_name}'. Available: {', '.join(available_tool_groups())}"
        )
    return _BUILDERS[group_name](workspace_root)
