import asyncio
import copy
import logging
import os
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Dict, List, Optional, cast

import httpx
from anthropic import RateLimitError
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
)

# Ensure the Anthropic reference implementation is on the path
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
anthropic_main_path = Path(__file__).parent / "anthropic_main"
sys.path.insert(0, str(anthropic_main_path))

from agent_base import AgentAdapter, AgentStepResult
from anthropic_main.computer_use_demo.loop import APIProvider, sampling_loop
from anthropic_main.computer_use_demo.tools import ToolResult, ToolVersion
from anthropic_main.computer_use_demo.tools.groups import ToolGroup, TOOL_GROUPS_BY_VERSION
from agents.utils import get_screenshot


logger = logging.getLogger(__name__)


LEGACY_MODEL = "claude-3-7-sonnet-20250219"


PROVIDER_TO_DEFAULT_MODEL_NAME: Dict[APIProvider, str] = {
    APIProvider.ANTHROPIC: "claude-sonnet-4-5-20250929",
    APIProvider.BEDROCK: "anthropic.claude-3-5-sonnet-20241022-v2:0",
    APIProvider.VERTEX: "claude-3-5-sonnet-v2@20241022",
}


@dataclass(kw_only=True, frozen=True)
class ModelConfig:
    tool_version: ToolVersion
    max_output_tokens: int
    default_output_tokens: int
    has_thinking: bool = False


SONNET_3_5_NEW = ModelConfig(
    tool_version="computer_use_20241022",
    max_output_tokens=1024 * 8,
    default_output_tokens=1024 * 4,
)

SONNET_3_7 = ModelConfig(
    tool_version="computer_use_20250124",
    max_output_tokens=128_000,
    default_output_tokens=1024 * 16,
    has_thinking=True,
)

CLAUDE_4 = ModelConfig(
    tool_version="computer_use_20250124",
    max_output_tokens=128_000,
    default_output_tokens=1024 * 16,
    has_thinking=True,
)

CLAUDE_4_5 = ModelConfig(
    tool_version="computer_use_20250124",
    max_output_tokens=128_000,
    default_output_tokens=1024 * 16,
    has_thinking=True,
)

HAIKU_4_5 = ModelConfig(
    tool_version="computer_use_20250124",
    max_output_tokens=1024 * 8,
    default_output_tokens=1024 * 4,
    has_thinking=False,
)

MODEL_TO_MODEL_CONF: Dict[str, ModelConfig] = {
    "claude-3-7-sonnet-20250219": SONNET_3_7,
    "claude-opus-4@20250508": CLAUDE_4,
    "claude-sonnet-4-20250514": CLAUDE_4,
    "claude-sonnet-4-5-20250929": CLAUDE_4_5,
    "claude-opus-4-20250514": CLAUDE_4,
    "claude-haiku-4-5-20251001": HAIKU_4_5,
    "anthropic.claude-haiku-4-5-20251001-v1:0": HAIKU_4_5,
    "claude-haiku-4-5@20251001": HAIKU_4_5,
}

INTERRUPT_TEXT = "(user stopped or interrupted and wrote the following)"
INTERRUPT_TOOL_ERROR = "human stopped or interrupted tool execution"


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
            return "Your Google Cloud credentials are not set up correctly."
    return None


class anthropicAgent(AgentAdapter):
    """
    Adapter that reuses the claude_computer_use_demo sampling loop without modifying
    the upstream logic. We mimic the streamlit session state so that the agent can run
    in our harness while preserving the official behavior.
    """

    def __init__(self) -> None:
        self.messages: List[Dict[str, Any]] = []
        self.responses: Dict[str, Dict[str, Any]] = {}
        self.tools: Dict[str, ToolResult] = {}
        self.current_tool_outputs: List[Dict[str, Any]] = []
        self.http_logs: List[Dict[str, Any]] = []
        self.errors: List[str] = []
        self.last_user_input: str = ""
        self.in_sampling_loop = False
        self.custom_system_prompt = ""
        self.only_n_most_recent_images = 3
        self.token_efficient_tools_beta = False
        self.provider: APIProvider = APIProvider.ANTHROPIC
        self.model: str = PROVIDER_TO_DEFAULT_MODEL_NAME[self.provider]
        self.tool_version: ToolVersion = "computer_use_20250124"
        self.output_tokens: int = SONNET_3_5_NEW.default_output_tokens
        self.max_output_tokens: int = SONNET_3_5_NEW.max_output_tokens
        self.thinking_enabled = False
        self.thinking_budget: Optional[int] = None
        self.api_key: str = ""
        self.img_save_path: Path = Path("screenshots")

    def init(
        self,
        *,
        api_key: Optional[str] = None,
        provider: APIProvider | str = APIProvider.ANTHROPIC,
        model: Optional[str] = None,
        system_prompt_suffix: str = "",
        tool_version: Optional[ToolVersion] = None,
        only_n_most_recent_images: int = 3,
        output_tokens: Optional[int] = None,
        thinking_enabled: bool = False,
        thinking_budget: Optional[int] = None,
        token_efficient_tools_beta: bool = False,
        img_save_path: str = "screenshots",
    ) -> None:
        self.img_save_path = Path(img_save_path)
        self.img_save_path.mkdir(parents=True, exist_ok=True)
        self.provider = provider if isinstance(provider, APIProvider) else APIProvider(provider)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")

        self.messages = []
        self.responses = {}
        self.tools = {}
        self.current_tool_outputs = []
        self.http_logs = []
        self.errors = []

        self.custom_system_prompt = system_prompt_suffix
        self.only_n_most_recent_images = only_n_most_recent_images
        self.token_efficient_tools_beta = token_efficient_tools_beta

        self.model = model or PROVIDER_TO_DEFAULT_MODEL_NAME[self.provider]
        model_conf = MODEL_TO_MODEL_CONF.get(self.model, SONNET_3_5_NEW)
        if tool_version:
            self.tool_version = tool_version
        else:
            if self.model == "claude-3-7-sonnet-20250219":
                self.tool_version = "computer_use_20250124"
            else:
                self.tool_version = model_conf.tool_version
        self.max_output_tokens = model_conf.max_output_tokens
        desired_tokens = output_tokens or model_conf.default_output_tokens
        self.output_tokens = min(desired_tokens, self.max_output_tokens)

        self.thinking_enabled = thinking_enabled and model_conf.has_thinking
        if self.thinking_enabled:
            default_thinking = model_conf.default_output_tokens // 2
            self.thinking_budget = thinking_budget or default_thinking
        else:
            self.thinking_budget = None

    def _append_user_message(self, text: str) -> None:
        payload = []
        payload.extend(self.maybe_add_interruption_blocks())
        payload.append(BetaTextBlockParam(type="text", text=text))
        self.messages.append({"role": Sender.USER, "content": payload})
        self.last_user_input = text

    async def step(self) -> AgentStepResult:
        if not self.messages or self.messages[-1]["role"] != Sender.USER:
            raise RuntimeError("Call step() after providing a user message via run().")

        auth_error = validate_auth(self.provider, self.api_key)
        if auth_error:
            raise RuntimeError(auth_error)

        observation_before = {"messages": copy.deepcopy(self.messages)}
        self.current_tool_outputs = []
        self.http_logs = []
        self.errors = []

        with self.track_sampling_loop(), self._legacy_tool_group_patch():
            self.messages = await sampling_loop(
                system_prompt_suffix=self.custom_system_prompt,
                model=self.model,
                provider=self.provider,
                messages=self.messages,
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
        observation_after = {"messages": copy.deepcopy(self.messages)}
        action = "tool" if self.current_tool_outputs else "none"
        output_text = self._summarize_assistant_output(assistant_message)

        return AgentStepResult(
            input=self.last_user_input,
            observation_before=observation_before,
            action=action,
            action_result={
                "tools": self.current_tool_outputs,
                "http_logs": self.http_logs,
                "errors": list(self.errors),
            },
            observation_after=observation_after,
            output=output_text,
        )

    async def run(self, input_text: str) -> List[AgentStepResult]:
        if not input_text.strip():
            logger.warning("Empty prompt provided.")
            return []

        self._append_user_message(input_text)
        results: List[AgentStepResult] = []
        step_idx = 0
        while True:
            before_path = self._capture_screenshot(step_idx, "before")
            step_result = await self.step()
            after_path = self._capture_screenshot(step_idx, "after")

            step_result.observation_before = {
                "messages": copy.deepcopy(self.messages),
                "screenshot": before_path,
            }
            step_result.observation_after = {"messages": copy.deepcopy(self.messages), "screenshot": after_path}
            if step_result.action_result is None:
                step_result.action_result = {}
            step_result.action_result.setdefault("screenshots", {"before": before_path, "after": after_path})

            results.append(step_result)
            tool_outputs = step_result.action_result.get("tools") if step_result.action_result else []
            step_idx += 1
            if not tool_outputs:
                break
        return results

    def _capture_screenshot(self, idx: int, phase: str) -> Optional[str]:
        try:
            path = self.img_save_path / f"{idx}_{phase}.png"
            get_screenshot(str(path))
            return str(path)
        except Exception as e:
            logger.warning("Failed to capture screenshot for step %s %s: %s", idx, phase, e)
            return None

    def maybe_add_interruption_blocks(self) -> List[BetaToolResultBlockParam | BetaTextBlockParam]:
        if not self.in_sampling_loop or not self.messages:
            return []

        last_message = self.messages[-1]
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
            self.tools[tool_use_id] = ToolResult(error=INTERRUPT_TOOL_ERROR)
            result.append(
                BetaToolResultBlockParam(
                    tool_use_id=tool_use_id,
                    type="tool_result",
                    content=INTERRUPT_TOOL_ERROR,
                    is_error=True,
                )
            )
        result.append(BetaTextBlockParam(type="text", text=INTERRUPT_TEXT))
        return result

    @contextmanager
    def track_sampling_loop(self):
        self.in_sampling_loop = True
        try:
            yield
        finally:
            self.in_sampling_loop = False

    def _handle_model_output(self, block: BetaContentBlockParam) -> None:
        # Store assistant block summaries for debugging/logging.
        if isinstance(block, dict) and block.get("type") == "text":
            logger.debug("Assistant: %s", block.get("text", ""))

    def _handle_tool_output(self, tool_output: ToolResult, tool_id: str) -> None:
        self.tools[tool_id] = tool_output
        payload = {
            "tool_use_id": tool_id,
            "output": tool_output.output,
            "error": tool_output.error,
            "system": tool_output.system,
            "base64_image": tool_output.base64_image,
        }
        self.current_tool_outputs.append(payload)

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
        self.http_logs.append(entry)

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
        self.errors.append(body)
        logger.error(body)
        return body

    def _extract_last_assistant_message(self) -> Optional[Dict[str, Any]]:
        for message in reversed(self.messages):
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

    def _needs_legacy_toolset(self) -> bool:
        return self.model == LEGACY_MODEL

    @contextmanager
    def _legacy_tool_group_patch(self):
        if not self._needs_legacy_toolset():
            yield
            return

        target_version = "computer_use_20250124"
        original_group = TOOL_GROUPS_BY_VERSION[target_version]

        # Only patch if the edit tool is the newer variant
        from anthropic_main.computer_use_demo.tools.bash import BashTool20250124
        from anthropic_main.computer_use_demo.tools.computer import ComputerTool20250124
        from anthropic_main.computer_use_demo.tools.edit import EditTool20250124

        if EditTool20250124 in original_group.tools:
            # Already patched
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    agent = anthropicAgent()
    # Fill in the parameters as needed, e.g. api_key and preferred model/provider.
    agent.init(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        model="claude-3-7-sonnet-20250219",
    )

    asyncio.run(agent.run("find a picture of cat"))
