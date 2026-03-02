from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, List

from ..base import BaseTool, ToolResult


def _resolve(root: Path, relative_path: str) -> Path:
    base = root.resolve()
    target = (base / relative_path).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError("Path escapes the workspace root.")
    return target


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read a UTF-8 text file from the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path to the file"},
            "max_bytes": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 8000},
        },
        "required": ["path"],
    }

    def __init__(self, workspace_root: Path):
        self._root = workspace_root

    async def __call__(self, path: str, max_bytes: int = 8000) -> ToolResult:
        full_path = _resolve(self._root, path)
        if not full_path.exists():
            return ToolResult(error=f"File '{path}' does not exist.")
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, full_path.read_text, "utf-8")
        return ToolResult(output=data[:max_bytes], metadata={"path": path})


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write UTF-8 text to a workspace file."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "overwrite": {"type": "boolean", "default": False},
        },
        "required": ["path", "content"],
    }

    def __init__(self, workspace_root: Path):
        self._root = workspace_root

    async def __call__(self, path: str, content: str, overwrite: bool = False) -> ToolResult:
        full_path = _resolve(self._root, path)
        if full_path.exists() and not overwrite:
            return ToolResult(error=f"File '{path}' already exists. Set overwrite=true to replace it.")
        full_path.parent.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, full_path.write_text, content, "utf-8")
        return ToolResult(output=f"Wrote {len(content)} characters to {path}.", metadata={"path": path})


class SearchWorkspaceTool(BaseTool):
    name = "search_workspace"
    description = "Search for a keyword inside workspace text files."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_hits": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
        },
        "required": ["query"],
    }

    TEXT_EXTENSIONS = {".md", ".txt", ".py", ".json", ".yaml", ".yml"}

    def __init__(self, workspace_root: Path):
        self._root = workspace_root

    async def __call__(self, query: str, max_hits: int = 5) -> ToolResult:
        loop = asyncio.get_running_loop()
        hits = await loop.run_in_executor(None, self._search_sync, query, max_hits)
        if not hits:
            return ToolResult(output=f"No matches found for '{query}'.")
        formatted = "\n".join(f"{hit['path']}:{hit['line']}: {hit['excerpt']}" for hit in hits)
        return ToolResult(output=formatted, metadata={"hits": hits})

    def _search_sync(self, query: str, max_hits: int) -> List[Dict[str, str]]:
        result: List[Dict[str, str]] = []
        for file_path in self._root.rglob("*"):
            if not file_path.is_file() or file_path.suffix not in self.TEXT_EXTENSIONS:
                continue
            try:
                lines = file_path.read_text("utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for idx, line in enumerate(lines, start=1):
                if query.lower() in line.lower():
                    result.append(
                        {
                            "path": str(file_path.relative_to(self._root)),
                            "line": str(idx),
                            "excerpt": line.strip(),
                        }
                    )
                    if len(result) >= max_hits:
                        return result
        return result
