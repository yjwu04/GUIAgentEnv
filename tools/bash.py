from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import shlex
import subprocess
import json

from .base import Tool, ToolContext, ToolCallResponse, text_block, register_tool


def _run_cmd(cmd: str, timeout: int, cwd: Optional[str] = None) -> Dict[str, Any]:
    try:
        res = subprocess.run(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            cwd=cwd,
            text=True,
            check=False,
        )
        return {
            "returncode": res.returncode,
            "stdout": res.stdout[-10000:],
            "stderr": res.stderr[-10000:],
        }
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


@register_tool("bash")
@dataclass
class BashTool(Tool):
    version: Optional[str] = None
    name: str = "bash"

    def execute(self, arguments: Dict[str, Any], ctx: ToolContext) -> ToolCallResponse:
        cmd = arguments.get("command") or arguments.get("cmd") or ""
        if not cmd:
            return ToolCallResponse(tool_use_id="", content=[text_block("no command")], is_error=True)

        timeout = int(arguments.get("timeout", ctx.bash_timeout_sec))
        cwd = arguments.get("cwd") or ctx.safe_root
        out = _run_cmd(cmd, timeout=timeout, cwd=cwd)
        return ToolCallResponse(tool_use_id="", content=[text_block(json.dumps(out))], is_error=("error" in out))

    def to_anthropic_decl(self, ctx: ToolContext) -> Dict[str, Any]:
        tname = f"{self.name}_{self.version}" if self.version else self.name
        return {"type": tname, "name": "bash"}
