from __future__ import annotations

import copy
import logging
import os
import sys
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import httpx
from anthropic import RateLimitError
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
)

CURRENT_DIR = Path(__file__).resolve().parent  # strategies
PROJECT_ROOT = CURRENT_DIR.parent  # default_agent package root
local_anthropic = PROJECT_ROOT / "anthropic_main"
if local_anthropic.is_dir() and str(local_anthropic) not in sys.path:
    sys.path.insert(0, str(local_anthropic))

from anthropic_main.computer_use_demo.loop import APIProvider, sampling_loop
from anthropic_main.computer_use_demo.tools import ToolResult, ToolVersion
from anthropic_main.computer_use_demo.tools.groups import TOOL_GROUPS_BY_VERSION, ToolGroup

from agent_base import AgentStepResult
from agents.utils import get_screenshot

from ..models.factory import ModelSettings
from .base import BaseStrategy

logger = logging.getLogger(__name__)


PROVIDER_TO_API = {
    "anthropic": APIProvider.ANTHROPIC,
    "bedrock": APIProvider.BEDROCK,
    "vertex": APIProvider.VERTEX,
}


@dataclass(kw_only=True, frozen=True)
class ModelConfigShim:
    tool_version: ToolVersion
    max_output_tokens: int
    default_output_tokens: int
    has_thinking: bool = False


DEFAULT_MODEL_CONFIG = ModelConfigShim(
    tool_version="computer_use_20241022", max_output_tokens=4096, default_output_tokens=2048
)


MODEL_TO_CONF: Dict[str, ModelConfigShim] = {
    "claude-3-7-sonnet-20250219": ModelConfigShim(
        tool_version="computer_use_20250124", max_output_tokens=128_000, default_output_tokens=16384, has_thinking=True
    ),
    "claude-sonnet-4-5-20250929": ModelConfigShim(
        tool_version="computer_use_20250124", max_output_tokens=128_000, default_output_tokens=16384, has_thinking=True
    ),
    "claude-sonnet-4-20250514": ModelConfigShim(
        tool_version="computer_use_20250124", max_output_tokens=128_000, default_output_tokens=16384, has_thinking=True
    ),
    "claude-opus-4-20250514": ModelConfigShim(
        tool_version="computer_use_20250124", max_output_tokens=128_000, default_output_tokens=16384, has_thinking=True
    ),
    "claude-3-7-sonnet-20250219": ModelConfigShim(
        tool_version="computer_use_20250124", max_output_tokens=128_000, default_output_tokens=16384, has_thinking=True
    ),
}
LEGACY_MODEL = "claude-3-7-sonnet-20250219"


class Sender(StrEnum):
    USER = "user"
    BOT = "assistant"
    TOOL = "tool"


def validate_auth(provider: APIProvider, api_key: Optional[str]) -> Optional[str]:
    if provider == APIProvider.ANTHROPIC and not api_key:
        return "Enter your Claude API key to continue."
    if provider == APIProvider.BEDROCK:
        import boto3

        if not boto3.Session().get_credentials():
            return "You must have AWS credentials set up to use the Bedrock API."
    if provider == APIProvider.VERTEX:
        import google.auth
        from google.auth.exceptions import DefaultCredentialsError

        if not os.environ.get("CLOUD_ML_REGION"):
            return "Set the CLOUD_ML_REGION environment variable to use the Vertex API."
        try:
            google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        except DefaultCredentialsError:
            return "Your google cloud credentials are not set up correctly."
    return None


@dataclass
class _AnthropicState:
    messages: List[Dict[str, Any]] = field(default_factory=list)
    responses: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    tools: Dict[str, ToolResult] = field(default_factory=dict)
    current_tool_outputs: List[Dict[str, Any]] = field(default_factory=list)
    http_logs: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    last_user_input: str = ""
    in_sampling_loop: bool = False


class AnthropicComputerUseStrategy(BaseStrategy):
    """
    Strategy that embeds the anthropic computer-use demo loop but accepts settings via ModelSettings.
    """

    def __init__(self, model_settings: ModelSettings, extras: Dict[str, Any] | None = None) -> None:
        extras = extras or {}
        if model_settings.provider not in PROVIDER_TO_API:
            raise ValueError("Anthropic computer-use tools require provider 'anthropic', 'bedrock', or 'vertex'.")

        self.provider = PROVIDER_TO_API[model_settings.provider]  # type: ignore[arg-type]
        self.api_key = model_settings.api_key
        self.custom_system_suffix = extras.get("system_prompt_suffix", "")
        self.only_n_most_recent_images = extras.get("only_n_most_recent_images", 3)
        self.token_efficient_tools_beta = extras.get("token_efficient_tools_beta", False)
        self.model_name = model_settings.name
        self.tool_version = extras.get("tool_version")
        self.img_save_path = Path(extras.get("img_save_path", "screenshots"))
        self.img_save_path.mkdir(parents=True, exist_ok=True)

        cfg = MODEL_TO_CONF.get(self.model_name, DEFAULT_MODEL_CONFIG)
        self.tool_version = self.tool_version or cfg.tool_version
        self.max_output_tokens = cfg.max_output_tokens
        desired_tokens = extras.get("output_tokens") or cfg.default_output_tokens
        self.output_tokens = min(desired_tokens, self.max_output_tokens)
        self.thinking_enabled = extras.get("thinking_enabled", False) and cfg.has_thinking
        if self.thinking_enabled:
            self.thinking_budget = extras.get("thinking_budget") or cfg.default_output_tokens // 2
        else:
            self.thinking_budget = None

        self.state = _AnthropicState()
        self.messages = self.state.messages

        system_prompt = extras.get("system_prompt", "")
        if system_prompt:
            self.custom_system_suffix = system_prompt + "\n" + self.custom_system_suffix

    def _needs_legacy_toolset(self) -> bool:
        return self.model_name == LEGACY_MODEL

    @contextmanager
    def _legacy_tool_group_patch(self):
        if not self._needs_legacy_toolset():
            yield
            return

        target_version = "computer_use_20250124"
        original_group = TOOL_GROUPS_BY_VERSION[target_version]

        from anthropic_main.computer_use_demo.tools.bash import BashTool20250124
        from anthropic_main.computer_use_demo.tools.computer import ComputerTool20250124
        from anthropic_main.computer_use_demo.tools.edit import EditTool20250124

        if EditTool20250124 in original_group.tools:
            yield
            return

        TOOL_GROUPS_BY_VERSION[target_version] = ToolGroup(
            version=target_version,
            tools=[ComputerTool20250124, EditTool20250124, BashTool20250124],
            beta_flag=original_group.beta_flag,
        )
        try:
            yield
        finally:
            TOOL_GROUPS_BY_VERSION[target_version] = original_group

    def _append_user_message(self, text: str) -> None:
        payload = []
        payload.extend(self.maybe_add_interruption_blocks())
        payload.append(BetaTextBlockParam(type="text", text=text))
        self.state.messages.append({"role": Sender.USER, "content": payload})
        self.state.last_user_input = text

    def maybe_add_interruption_blocks(self) -> List[BetaToolResultBlockParam | BetaTextBlockParam]:
        if not self.state.in_sampling_loop or not self.state.messages:
            return []

        last_message = self.state.messages[-1]
        content = last_message.get("content", [])
        if not isinstance(content, list):
            return []

        result: List[BetaToolResultBlockParam | BetaTextBlockParam] = []
        previous_tool_use_ids = [
            block["id"]
            for block in content
            if isinstance(block, dict) and block.get("type") == "tool_use"
        ]
        for tool_use_id in previous_tool_use_ids:
            self.state.tools[tool_use_id] = ToolResult(error="human stopped or interrupted tool execution")
            result.append(
                BetaToolResultBlockParam(
                    tool_use_id=tool_use_id,
                    type="tool_result",
                    content="human stopped or interrupted tool execution",
                    is_error=True,
                )
            )
        result.append(BetaTextBlockParam(type="text", text="(user stopped or interrupted and wrote the following)"))
        return result

    @contextmanager
    def track_sampling_loop(self):
        self.state.in_sampling_loop = True
        try:
            yield
        finally:
            self.state.in_sampling_loop = False

    def _handle_model_output(self, block: BetaContentBlockParam) -> None:
        if isinstance(block, dict) and block.get("type") == "text":
            logger.debug("Assistant: %s", block.get("text", ""))

    def _handle_tool_output(self, tool_output: ToolResult, tool_id: str) -> None:
        self.state.tools[tool_id] = tool_output
        payload = {
            "tool_use_id": tool_id,
            "output": tool_output.output,
            "error": tool_output.error,
            "system": tool_output.system,
            "base64_image": tool_output.base64_image,
        }
        self.state.current_tool_outputs.append(payload)

    def _handle_api_response(
        self,
        request: httpx.Request,
        response: httpx.Response | object | None,
        error: Exception | None,
    ) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "request": {"method": request.method, "url": str(request.url)},
        }
        if isinstance(response, httpx.Response):
            entry["response"] = {"status": response.status_code, "body": response.text}
        elif response is not None:
            entry["response"] = {"body": str(response)}
        if error:
            entry["error"] = self._render_error(error)
        self.state.http_logs.append(entry)

    def _render_error(self, error: Exception) -> str:
        if isinstance(error, RateLimitError):
            body = "You have been rate limited."
            if retry_after := error.response.headers.get("retry-after"):
                retry_ts = str(timedelta(seconds=int(retry_after)))
                body += f" Retry after {retry_ts} (HH:MM:SS)."
            body += f" {error.message}"
        else:
            body = f"{error.__class__.__name__}: {error}"
            lines = "\n".join(traceback.format_exception(error))
            body += f"\n{lines}"
        self.state.errors.append(body)
        logger.error(body)
        return body

    def _extract_last_assistant_message(self) -> Optional[Dict[str, Any]]:
        for message in reversed(self.state.messages):
            if message["role"] == Sender.BOT:
                return cast(Dict[str, Any], message)
        return None

    def _summarize_assistant_output(self, assistant_message: Optional[Dict[str, Any]]) -> str:
        if not assistant_message:
            return ""
        content = assistant_message.get("content", [])
        if not isinstance(content, list):
            return ""

        parts: List[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                parts.append(block.get("text", ""))
            elif block_type == "thinking":
                thinking_content = block.get("thinking", "")
                parts.append(f"[Thinking]\n{thinking_content}")
            elif block_type == "tool_use":
                name = block.get("name", "tool")
                parts.append(f"[Tool Use] {name}")
        return "\n\n".join(filter(None, parts))

    async def run(self, instruction: str) -> List[AgentStepResult]:
        if not instruction.strip():
            raise ValueError("Empty prompt provided.")

        auth_error = validate_auth(self.provider, self.api_key)
        if auth_error:
            raise RuntimeError(auth_error)

        self._append_user_message(instruction)

        results: List[AgentStepResult] = []
        step_idx = 0
        while True:
            before_path = self._capture_screenshot(step_idx, "before")
            snapshot_before = {
                "messages": copy.deepcopy(self.state.messages),
                "screenshot": before_path,
            }
            self.state.current_tool_outputs = []
            self.state.http_logs = []
            self.state.errors = []

            with self.track_sampling_loop(), self._legacy_tool_group_patch():
                self.state.messages = await sampling_loop(
                    system_prompt_suffix=(
                        self.custom_system_suffix
                        if self.custom_system_suffix
                        else "You are an assistant that can operate a computer via tools."
                    ),
                    model=self.model_name,
                    provider=self.provider,
                    messages=self.state.messages,
                    output_callback=self._handle_model_output,
                    tool_output_callback=self._handle_tool_output,
                    api_response_callback=self._handle_api_response,
                    api_key=self.api_key,
                    only_n_most_recent_images=self.only_n_most_recent_images,
                    tool_version=self.tool_version,
                    max_tokens=self.output_tokens,
                    thinking_budget=self.thinking_budget if self.thinking_enabled else None,
                    token_efficient_tools_beta=self.token_efficient_tools_beta,
                    max_tool_uses_per_call=1,
                )

            assistant_message = self._extract_last_assistant_message()
            after_path = self._capture_screenshot(step_idx, "after")
            snapshot_after = {"messages": copy.deepcopy(self.state.messages), "screenshot": after_path}
            action = "tool" if self.state.current_tool_outputs else "none"
            output_text = self._summarize_assistant_output(assistant_message)

            results.append(
                AgentStepResult(
                    input=self.state.last_user_input,
                    observation_before=snapshot_before,
                    action=action,
                    action_result={
                        "tools": self.state.current_tool_outputs,
                        "http_logs": self.state.http_logs,
                        "errors": list(self.state.errors),
                        "screenshots": {"before": before_path, "after": after_path},
                    },
                    observation_after=snapshot_after,
                    output=output_text,
                )
            )

            if not self.state.current_tool_outputs:
                break
            step_idx += 1

        return results

    def _capture_screenshot(self, idx: int, phase: str) -> Optional[str]:
        try:
            path = self.img_save_path / f"{idx}_{phase}.png"
            get_screenshot(str(path))
            return str(path)
        except Exception as e:
            logger.warning("Failed to capture screenshot for step %s %s: %s", idx, phase, e)
            return None
