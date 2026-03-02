from __future__ import annotations

import asyncio
import io
from typing import Any, Dict

from ..base import BaseTool, ToolResult


class PythonExecuteTool(BaseTool):
    name = "python_execute"
    description = "Execute a short Python snippet with access to 'result' variable."
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"},
        },
        "required": ["code"],
    }

    def __init__(self, context: Dict[str, Any] | None = None):
        self._context = context or {}

    async def __call__(self, code: str) -> ToolResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._execute_sync, code)

    def _execute_sync(self, code: str) -> ToolResult:
        buffer = io.StringIO()
        local_vars: Dict[str, Any] = dict(self._context)

        safe_builtins = {
            "range": range,
            "len": len,
            "min": min,
            "max": max,
            "sum": sum,
            "print": lambda *args, **kwargs: print(*args, **kwargs, file=buffer),
        }

        try:
            exec(  # pylint: disable=exec-used
                code,
                {"__builtins__": safe_builtins},
                local_vars,
            )
        except Exception as exc:  # pylint: disable=broad-except
            return ToolResult(error=f"Python error: {exc}")

        stdout_value = buffer.getvalue().strip()
        if "result" in local_vars:
            return ToolResult(
                output=f"{stdout_value}\nresult = {local_vars['result']}".strip(),
                metadata={"variables": list(local_vars.keys())},
            )
        return ToolResult(output=stdout_value or "Code executed.", metadata={"variables": list(local_vars.keys())})
