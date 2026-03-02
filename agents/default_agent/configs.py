from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from .models.factory import ModelSettings


# ---------------------------------------------------------------------------
# ModelConfig
#   provider: "anthropic", "openai", or "deepseek"
#   name:     any model ID supported by that provider (e.g.
#             Claude 3.5 Sonnet, gpt-4o, gpt-3.5-turbo, deepseek-chat, etc.)
#   api_key_env: environment variable that stores the API key
#   base_url / timeout / extras: optional provider-specific overrides
# ---------------------------------------------------------------------------
@dataclass
class ModelConfig:
    provider: str = "deepseek"  # "anthropic", "openai", "deepseek"
    name: str = "deepseek-chat"
    api_key_env: str = "DEEPSEEK_API_KEY"
    base_url: str | None = None
    timeout: float | None = None
    extras: Dict[str, Any] = field(default_factory=dict)

    def resolve(self) -> ModelSettings:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"API key not found. Set the environment variable '{self.api_key_env}'."
            )

        provider = self.provider.lower()
        base_url = self.base_url
        if base_url is None and provider == "deepseek":
            base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

        return ModelSettings(
            provider=self.provider,  # type: ignore[arg-type]
            name=self.name,
            api_key=api_key,
            base_url=base_url,
            timeout=self.timeout,
            extras=self.extras,
        )


# ---------------------------------------------------------------------------
# ToolConfig
#   group options: "default_desktop" / "default_tools" / "default"
#                  "anthropic_tools"  -> Anthropic computer-use suite
#                  "openmanus_tools"  -> OpenManus automation suite
#   workspace_root: base path for file/screenshot operations
#   extras: optional per-group overrides (e.g. max_steps, img_save_path)
# ---------------------------------------------------------------------------
@dataclass
class ToolConfig:
    group: str = "default_desktop"  # or "default", "default_tools", "anthropic_tools", "openmanus_tools"
    workspace_root: str = "."
    extras: Dict[str, Any] = field(default_factory=dict)

    def resolve_workspace(self) -> Path:
        return Path(self.workspace_root).resolve()


MODEL = ModelConfig()
TOOLS = ToolConfig()
