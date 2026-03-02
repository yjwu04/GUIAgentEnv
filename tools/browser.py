from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .base import Tool, ToolContext, ToolCallResponse, text_block, register_tool

# Optional Playwright backend
try:
    from playwright.sync_api import sync_playwright
    _HAS_PW = True
except Exception:
    _HAS_PW = False


@register_tool("browser")
@dataclass
class BrowserTool(Tool):
    """
    Minimal headful browser actions (requires playwright):
      {"action":"open","url":"https://..."}
      {"action":"click","selector":"input[name=q]"}
      {"action":"type","selector":"input[name=q]","text":"hello"}
      {"action":"press","selector":"input[name=q]","key":"Enter"}
      {"action":"scroll","delta_y":800}
      {"action":"screenshot"}  # returns base64 image block (not full-fidelity if no page)
    """
    version: Optional[str] = None
    name: str = "browser"
    headless: bool = False

    def __post_init__(self):
        self._pw = None
        self._browser = None
        self._page = None
        if _HAS_PW:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=self.headless)
            self._page = self._browser.new_page(viewport={"width": 1280, "height": 800})

    def _ensure(self):
        if not _HAS_PW:
            raise RuntimeError("playwright not installed: pip install playwright && playwright install")
        if self._page is None:
            raise RuntimeError("browser not initialized")

    def execute(self, arguments: Dict[str, Any], ctx: ToolContext) -> ToolCallResponse:
        act = arguments.get("action")
        try:
            if act == "open":
                self._ensure()
                url = arguments.get("url") or "about:blank"
                self._page.goto(url)
                return ToolCallResponse(tool_use_id="", content=[text_block("ok")])

            if act == "click":
                self._ensure()
                sel = arguments.get("selector")
                self._page.click(sel)
                return ToolCallResponse(tool_use_id="", content=[text_block("ok")])

            if act == "type":
                self._ensure()
                sel = arguments.get("selector")
                txt = arguments.get("text", "")
                self._page.fill(sel, txt)
                return ToolCallResponse(tool_use_id="", content=[text_block("ok")])

            if act == "press":
                self._ensure()
                sel = arguments.get("selector")
                key = arguments.get("key", "Enter")
                self._page.press(sel, key)
                return ToolCallResponse(tool_use_id="", content=[text_block("ok")])

            if act == "scroll":
                self._ensure()
                dy = int(arguments.get("delta_y", 500))
                self._page.mouse.wheel(0, dy)
                return ToolCallResponse(tool_use_id="", content=[text_block("ok")])

            if act == "screenshot":
                if self._page is None:
                    return ToolCallResponse(tool_use_id="", content=[text_block("no page")], is_error=True)
                png = self._page.screenshot(type="png")
                from .base import image_block_from_png_bytes
                return ToolCallResponse(tool_use_id="", content=[image_block_from_png_bytes(png)])

            return ToolCallResponse(tool_use_id="", content=[text_block(f"unknown action: {act}")], is_error=True)

        except Exception as e:
            return ToolCallResponse(tool_use_id="", content=[text_block(f"error: {e}")], is_error=True)

    def to_anthropic_decl(self, ctx: ToolContext) -> Dict[str, Any]:
        # There is no official Anthropic "browser" tool type — treat it as a custom tool.
        tname = f"{self.name}_{self.version}" if self.version else self.name
        return {"type": tname, "name": "browser"}

    # Ensure cleanup
    def __del__(self):
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
