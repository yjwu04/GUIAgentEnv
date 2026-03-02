from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, TypedDict, Callable, Type

# ---------- neutral content blocks ----------
# We intentionally use light dicts so both Anthropic and OpenAI adapters can pass them through.


class ImageSource(TypedDict, total=False):
    type: str                 # "base64" | "url"
    media_type: str           # e.g., "image/png" (for base64)
    data: str                 # base64 payload (no data: prefix)
    url: str                  # for URL images


class ContentBlock(TypedDict, total=False):
    type: str                 # "text" | "image"
    text: str                 # for text blocks
    source: ImageSource       # for image blocks


def image_block_from_png_bytes(png_bytes: bytes) -> ContentBlock:
    import base64
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(png_bytes).decode("ascii")},
    }


def text_block(s: str) -> ContentBlock:
    return {"type": "text", "text": s}


# ---------- Tool protocol ----------

@dataclass
class ToolContext:
    """
    Execution-time context that tools might need (display info, roots, timeouts).
    Agents can pass a shared instance into each execute() call.
    """
    display_width_px: int = 1280
    display_height_px: int = 800
    display_number: int = 1
    safe_root: str = "/workspace"         # sandbox root for file ops
    bash_timeout_sec: int = 30            # default command timeout
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolCallResponse:
    tool_use_id: str
    content: List[ContentBlock]
    is_error: bool = False


class Tool(Protocol):
    """
    Minimal tool contract:
      - name (e.g., "computer")
      - version (optional, e.g., "20250124" to build "computer_20250124")
      - execute(arguments, ctx) -> ToolCallResponse
      - to_anthropic_decl() -> dict (messages.create tools[] item)
    """

    name: str
    version: Optional[str]

    def execute(self, arguments: Dict[str, Any], ctx: ToolContext) -> ToolCallResponse: ...

    def to_anthropic_decl(self, ctx: ToolContext) -> Dict[str, Any]:
        """Return Anthropic messages.create tool declaration."""
        raise NotImplementedError("Tool must implement to_anthropic_decl")


# simple registry to support pluggability

_TOOL_REGISTRY: Dict[str, Type] = {}


def register_tool(name: str) -> Callable[[Type], Type]:
    def deco(cls: Type) -> Type:
        _TOOL_REGISTRY[name] = cls
        return cls
    return deco


def get_tool_class(name: str) -> Optional[Type]:
    return _TOOL_REGISTRY.get(name)
