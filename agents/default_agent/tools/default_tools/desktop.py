from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

import platform
import shutil
import subprocess
import webbrowser

from ..base import BaseTool, ToolResult


APPLICATION_ALIASES = {
	"chrome": "Google Chrome",
	"google chrome": "Google Chrome",
	"firefox": "Firefox",
	"mozilla firefox": "Firefox",
	"safari": "Safari",
	"edge": "Microsoft Edge",
	"microsoft edge": "Microsoft Edge",
}

try:
    import pyautogui

    pyautogui.FAILSAFE = False
except Exception:  # pylint: disable=broad-except
    pyautogui = None  # type: ignore


def _require_pyautogui() -> ToolResult | None:
    if pyautogui is None:
        return ToolResult(error="pyautogui is not available. Install it to use desktop tools.")
    return None


@dataclass
class ScreenshotTool(BaseTool):
    name: str = "take_screenshot"
    description: str = "Capture the current screen and save it as an image."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Where to store the screenshot", "default": "screenshots/shot.png"},
        },
    }

    workspace_root: Path = Path.cwd()

    async def __call__(self, path: str = "screenshots/shot.png") -> ToolResult:
        missing = _require_pyautogui()
        if missing:
            return missing
        full_path = (self.workspace_root / path).resolve()
        full_path.parent.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: pyautogui.screenshot(full_path))
        return ToolResult(output=f"Screenshot saved to {path}", metadata={"path": str(full_path)})


class MouseClickTool(BaseTool):
    name = "mouse_click"
    description = "Click at the given screen coordinates."
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "number"},
            "y": {"type": "number"},
            "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
        },
        "required": ["x", "y"],
    }

    async def __call__(self, x: float, y: float, button: str = "left") -> ToolResult:
        missing = _require_pyautogui()
        if missing:
            return missing
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: pyautogui.click(x=x, y=y, button=button))
        return ToolResult(output=f"Clicked {button} button at ({x}, {y}).")


class TypeTextTool(BaseTool):
    name = "type_text"
    description = "Type text into the active window."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "interval": {"type": "number", "default": 0.02},
        },
        "required": ["text"],
    }

    async def __call__(self, text: str, interval: float = 0.02) -> ToolResult:
        missing = _require_pyautogui()
        if missing:
            return missing
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: pyautogui.write(text, interval=interval))
        return ToolResult(output=f"Typed {len(text)} characters.")


class HotkeyTool(BaseTool):
    name = "press_hotkey"
    description = "Trigger a keyboard hotkey combination (e.g., ctrl+c)."
    parameters = {
        "type": "object",
        "properties": {
            "keys": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ordered list of keys, e.g., ['ctrl', 'c']",
            }
        },
        "required": ["keys"],
    }

    async def __call__(self, keys: list[str]) -> ToolResult:
        missing = _require_pyautogui()
        if missing:
            return missing
        if not keys:
            return ToolResult(error="No keys provided.")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: pyautogui.hotkey(*keys))
        return ToolResult(output=f"Pressed hotkey: {' + '.join(keys)}.")


class LaunchApplicationTool(BaseTool):
    name = "launch_application"
    description = "Launch or focus a desktop application directly (preferred over typing in random windows)."
    parameters = {
        "type": "object",
        "properties": {
            "application": {
                "type": "string",
                "description": "Name or path of the application, e.g., 'Google Chrome'.",
            },
            "target": {
                "type": "string",
                "description": "Optional file, URL, or workspace path to open with the application.",
            },
            "arguments": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional extra CLI arguments.",
            },
        },
        "required": ["application"],
    }

    async def __call__(self, application: str, target: str | None = None, arguments: List[str] | None = None) -> ToolResult:
        application = application.strip().strip("\"'")
        if not application:
            return ToolResult(error="'application' must be a non-empty string.")

        alias_key = application.lower()
        application = APPLICATION_ALIASES.get(alias_key, application)

        args = list(arguments or [])
        system = platform.system()

        if system == "Darwin":
            cmd = ["open", "-a", application]
            if target:
                cmd.append(target)
            cmd.extend(args)
        elif system == "Windows":
            cmd = ["powershell", "-Command", "Start-Process", "-FilePath", application]
            if target:
                cmd.extend(["-ArgumentList", target])
            if args:
                extra_args = " ".join(shlex_quote(a) for a in args)
                cmd.extend(["-ArgumentList", extra_args])
        else:  # Linux / other POSIX
            executable = shutil.which(application)
            if executable is None:
                return ToolResult(error=f"Could not locate executable '{application}'. Provide an absolute path?")
            cmd = [executable]
            if target:
                cmd.append(target)
            cmd.extend(args)

        loop = asyncio.get_running_loop()
        try:
            proc = await loop.run_in_executor(None, lambda: subprocess.run(cmd, check=False, capture_output=True, text=True))
        except Exception as exc:  # pylint: disable=broad-except
            return ToolResult(error=str(exc))

        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            return ToolResult(error=f"Failed to launch {application}: {stderr or 'unknown error'}")

        return ToolResult(output=f"Launched {application}.", metadata={"command": cmd, "target": target})


class OpenUrlTool(BaseTool):
    name = "open_url"
    description = "Open a URL in the default (or specified) web browser without disturbing the active window."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Full URL to open, e.g., https://example.com",
            },
            "browser": {
                "type": "string",
                "description": "Optional browser controller name passed to the Python webbrowser module.",
            },
            "new": {
                "type": "integer",
                "enum": [0, 1, 2],
                "default": 1,
                "description": "0=reuse window, 1=new window/tab, 2=new window if possible.",
            },
        },
        "required": ["url"],
    }

    async def __call__(self, url: str, browser: str | None = None, new: int = 1) -> ToolResult:
        url = url.strip()
        if not url:
            return ToolResult(error="URL must be provided.")

        def _open() -> bool:
            try:
                controller = webbrowser.get(browser) if browser else webbrowser
                return controller.open(url, new=new)
            except webbrowser.Error:
                return False

        loop = asyncio.get_running_loop()
        success = await loop.run_in_executor(None, _open)
        if not success:
            return ToolResult(error="Failed to open URL via webbrowser module.")

        return ToolResult(output=f"Opened {url} in browser.", metadata={"url": url, "browser": browser or "default", "new": new})


def shlex_quote(value: str) -> str:
    try:
        import shlex

        return shlex.quote(value)
    except Exception:  # pragma: no cover - fallback if shlex missing
        if not value or value.isalnum():
            return value
        escaped = value.replace('"', r'\"')
        return '"' + escaped + '"'
