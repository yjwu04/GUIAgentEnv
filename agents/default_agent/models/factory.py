from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Type

from .Anthropic.chat import ChatAnthropic
from .deepseek.chat import ChatDeepSeek
from .Openai.chat import ChatOpenAI
from .base import BaseChatModel


ModelProvider = Literal["anthropic", "openai", "deepseek"]


@dataclass
class ModelSettings:
    provider: ModelProvider
    name: str
    api_key: str
    base_url: str | None = None
    timeout: float | None = None
    extras: Dict[str, Any] = field(default_factory=dict)


class ModelFactory:
    """Instantiate chat models based on provider."""

    _REGISTRY: Dict[ModelProvider, Type[BaseChatModel]] = {
        "anthropic": ChatAnthropic,
        "openai": ChatOpenAI,
        "deepseek": ChatDeepSeek,
    }

    @classmethod
    def available_providers(cls) -> list[str]:
        return list(cls._REGISTRY)

    @classmethod
    def create(cls, settings: ModelSettings) -> BaseChatModel:
        if settings.provider not in cls._REGISTRY:
            raise ValueError(
                f"Unsupported model provider '{settings.provider}'. "
                f"Available: {', '.join(cls.available_providers())}"
            )

        kwargs: Dict[str, Any] = {
            "model": settings.name,
            "api_key": settings.api_key,
        }
        if settings.base_url:
            kwargs["base_url"] = settings.base_url
        if settings.timeout:
            kwargs["timeout"] = settings.timeout
        kwargs.update(settings.extras or {})

        model_cls = cls._REGISTRY[settings.provider]
        return model_cls(**kwargs)  # type: ignore[arg-type]
