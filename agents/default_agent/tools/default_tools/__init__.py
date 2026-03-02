from __future__ import annotations

from pathlib import Path
from typing import Sequence

from ..base import ToolCollection, ToolDescriptor, ToolGroup
from .desktop import (
    HotkeyTool,
    LaunchApplicationTool,
    MouseClickTool,
    OpenUrlTool,
    ScreenshotTool,
    TypeTextTool,
)
from .file_ops import ReadFileTool, SearchWorkspaceTool, WriteFileTool
from .python_exec import PythonExecuteTool


DEFAULT_TOOL_GROUP_NAME = "default_desktop"


def build_default_tools(workspace_root: Path) -> ToolCollection:
    descriptors: Sequence[ToolDescriptor] = [
        ToolDescriptor(ReadFileTool, {"workspace_root": workspace_root}),
        ToolDescriptor(WriteFileTool, {"workspace_root": workspace_root}),
        ToolDescriptor(SearchWorkspaceTool, {"workspace_root": workspace_root}),
        ToolDescriptor(ScreenshotTool, {"workspace_root": workspace_root}),
        ToolDescriptor(MouseClickTool, {}),
        ToolDescriptor(TypeTextTool, {}),
        ToolDescriptor(HotkeyTool, {}),
        ToolDescriptor(LaunchApplicationTool, {}),
        ToolDescriptor(OpenUrlTool, {}),
        ToolDescriptor(PythonExecuteTool, {"context": {"workspace_root": str(workspace_root)}}),
    ]
    tools = [desc.cls(**desc.kwargs) for desc in descriptors]
    return ToolCollection(tools)


def describe_default_group() -> ToolGroup:
    return ToolGroup(
        name=DEFAULT_TOOL_GROUP_NAME,
        description="Generic desktop + workspace automation tools.",
        tools=[
            ToolDescriptor(ReadFileTool),
            ToolDescriptor(WriteFileTool),
            ToolDescriptor(SearchWorkspaceTool),
            ToolDescriptor(ScreenshotTool),
            ToolDescriptor(MouseClickTool),
            ToolDescriptor(TypeTextTool),
            ToolDescriptor(HotkeyTool),
            ToolDescriptor(LaunchApplicationTool),
            ToolDescriptor(OpenUrlTool),
            ToolDescriptor(PythonExecuteTool),
        ],
    )
