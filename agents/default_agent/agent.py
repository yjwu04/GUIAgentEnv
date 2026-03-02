from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import sys

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
REPO_ROOT = PROJECT_ROOT.parent
BROWSER_USE_SOURCE = PROJECT_ROOT / "browser_use_agent" / "browser_use_main"
LOCAL_ANTHROPIC = PROJECT_ROOT / "anthropic_main"
MODELS = PROJECT_ROOT / "default_agent" / "models"

bootstrap_paths = [
    str(REPO_ROOT),
    str(PROJECT_ROOT),
    str(MODELS),
]
if LOCAL_ANTHROPIC.is_dir():
    bootstrap_paths.append(str(LOCAL_ANTHROPIC))

for path in bootstrap_paths:
    if path and path not in sys.path:
        sys.path.insert(0, path)

from agent_base import AgentAdapter, AgentStepResult
from agents.default_agent.configs import (  # type: ignore
    MODEL as DEFAULT_MODEL_CONFIG,
    TOOLS as DEFAULT_TOOL_CONFIG,
    ModelConfig,
    ToolConfig,
)
from agents.default_agent.models.factory import ModelSettings  # type: ignore
from agents.default_agent.strategies.anthropic_strategy import AnthropicComputerUseStrategy  # type: ignore
from agents.default_agent.strategies.base import BaseStrategy  # type: ignore
from agents.default_agent.strategies.json_strategy import JsonToolStrategy  # type: ignore
from agents.default_agent.strategies.openmanus_strategy import OpenManusStrategy  # type: ignore
from agents.default_agent.tools import available_tool_groups, build_tool_collection  # type: ignore

logger = logging.getLogger(__name__)

JSON_TOOL_GROUPS = {"default_tools", "default_desktop"}

DEFAULT_JSON_SYSTEM_PROMPT = """
You are a desktop automation agent that can only interact with the world through the provided tools.

Follow these rules for every reply:
1. Think step-by-step about whether you need to call a tool or can answer immediately.
2. Respond ONLY with a JSON object placed inside a fenced block exactly like this:

```json
{
  "action": "<tool-name or final>",
  "action_input": { "arg": "value" },
  "response": "<message for the human>"
}
```

3. "action" must be the exact tool name from the list below or "final" when you are done.
4. Provide only the arguments you need inside "action_input".
5. Use "response" to briefly explain what happened or what you will do next.
6. If a tool call fails, inspect the error, adjust, and try again instead of stopping.
7. When the user request is fulfilled, set "action" to "final" and summarize the outcome in "response".
"""


class DefaultAgent(AgentAdapter):
    """Flexible adapter that can execute multiple runtimes based on config."""

    def __init__(self) -> None:
        self.strategy: BaseStrategy | None = None
        self.tool_group: str = DEFAULT_TOOL_CONFIG.group
        self.model_settings: ModelSettings | None = None

    def init(
        self,
        model_config: Optional[ModelConfig | ModelSettings] = None,
        tool_config: Optional[ToolConfig] = None,
        *,
        max_steps: Optional[int] = None,
        system_prompt: Optional[str] = None,
        img_save_path: str = "screenshots",
    ) -> None:
        model_cfg = model_config or DEFAULT_MODEL_CONFIG
        tool_cfg = tool_config or DEFAULT_TOOL_CONFIG
        self.tool_group = tool_cfg.group
        workspace_root = tool_cfg.resolve_workspace()
        self.img_save_path = (workspace_root / img_save_path).resolve()
        self.img_save_path.mkdir(parents=True, exist_ok=True)

        def resolve_model_settings() -> ModelSettings:
            if self.model_settings is None:
                if isinstance(model_cfg, ModelConfig):
                    self.model_settings = model_cfg.resolve()
                else:
                    self.model_settings = model_cfg
            return self.model_settings


        if self.tool_group in JSON_TOOL_GROUPS:
            settings = resolve_model_settings()
            tool_collection = build_tool_collection(self.tool_group, workspace_root)
            prompt = system_prompt or DEFAULT_JSON_SYSTEM_PROMPT
            steps = max_steps or 6
            self.strategy = JsonToolStrategy(
                settings,
                tool_collection,
                system_prompt=prompt,
                max_steps=steps,
            )
        elif self.tool_group == "anthropic_tools":
            settings = resolve_model_settings()
            extras = dict(tool_cfg.extras)
            if max_steps is not None:
                extras["max_steps"] = max_steps
            if system_prompt:
                extras["system_prompt_suffix"] = system_prompt
            extras["img_save_path"] = str(self.img_save_path)
            self.strategy = AnthropicComputerUseStrategy(settings, extras)
        elif self.tool_group == "openmanus_tools":
            extras = dict(tool_cfg.extras)
            if max_steps is not None:
                extras["max_steps"] = max_steps
            if "img_save_path" not in extras:
                extras["img_save_path"] = str(self.img_save_path)
            self.strategy = OpenManusStrategy(extras)
        else:
            raise ValueError(
                f"Unsupported tool group '{self.tool_group}'. "
                f"Available groups: {', '.join(sorted(JSON_TOOL_GROUPS | set(available_tool_groups()) | {'anthropic_tools', 'openmanus_tools'}))}"
            )

        model_name = self.model_settings.name if self.model_settings else "N/A"
        logger.info("DefaultAgent ready. Tool group=%s, model=%s", self.tool_group, model_name)

    async def run(self, instruction: str) -> List[AgentStepResult]:
        if not self.strategy:
            raise RuntimeError("Call init() before run().")
        return await self.strategy.run(instruction)

    async def step(self) -> AgentStepResult:
        raise NotImplementedError("DefaultAgent uses run() for full interactions.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent = DefaultAgent()
    agent.init()
    import asyncio

    asyncio.run(agent.run("Open https://www.google.com in Chrome and search for cat pictures."))
