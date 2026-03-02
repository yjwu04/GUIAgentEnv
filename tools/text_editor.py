from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from pathlib import Path
import json

from .base import Tool, ToolContext, ToolCallResponse, text_block, register_tool


def _safe_path(root: str, p: str) -> Path:
    base = Path(root).resolve()
    fp = (base / p.lstrip("/")).resolve()
    if not str(fp).startswith(str(base)):
        raise ValueError("path escapes safe_root")
    return fp


@register_tool("text_editor")
@dataclass
class TextEditorTool(Tool):
    version: Optional[str] = None
    name: str = "text_editor"

    def execute(self, arguments: Dict[str, Any], ctx: ToolContext) -> ToolCallResponse:
        path = arguments.get("path") or arguments.get("file_path") or "file.txt"
        find = arguments.get("find") or arguments.get("search") or ""
        replace = arguments.get("replace") or arguments.get("new_text") or ""
        try:
            fp = _safe_path(ctx.safe_root, path)
            data = fp.read_text(encoding="utf-8")
            count = data.count(find) if find else 0
            new_data = data.replace(find, replace) if find else data + replace
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(new_data, encoding="utf-8")
            res = {"path": str(fp), "replaced": count}
            return ToolCallResponse(tool_use_id="", content=[text_block(json.dumps(res))])
        except Exception as e:
            return ToolCallResponse(tool_use_id="", content=[text_block(f"error: {e}")], is_error=True)

    def to_anthropic_decl(self, ctx: ToolContext) -> Dict[str, Any]:
        tname = f"{self.name}_{self.version}" if self.version else self.name
        return {"type": tname, "name": "str_replace_editor"}
