"""
We have switched all of our code from langchain to openai.types.chat.chat_completion_message_param.

For easier transition we have
"""

from typing import TYPE_CHECKING

# Lightweight imports that are commonly used
from base import BaseChatModel
from messages import (
	AssistantMessage,
	BaseMessage,
	SystemMessage,
	UserMessage,
)
from messages import (
	ContentPartImageParam as ContentImage,
)
from messages import (
	ContentPartRefusalParam as ContentRefusal,
)
from messages import (
	ContentPartTextParam as ContentText,
)

# Type stubs for lazy imports
if TYPE_CHECKING:
	from Anthropic.chat import ChatAnthropic
	from deepseek.chat import ChatDeepSeek
	from Openai.chat import ChatOpenAI

# Lazy imports mapping for heavy chat models
_LAZY_IMPORTS = {
	'ChatAnthropic': ('browser_use.llm.anthropic.chat', 'ChatAnthropic'),
	'ChatDeepSeek': ('browser_use.llm.deepseek.chat', 'ChatDeepSeek'),
	'ChatOpenAI': ('browser_use.llm.openai.chat', 'ChatOpenAI'),
}


def __getattr__(name: str):
	"""Lazy import mechanism for heavy chat model imports."""
	if name in _LAZY_IMPORTS:
		module_path, attr_name = _LAZY_IMPORTS[name]
		try:
			from importlib import import_module

			module = import_module(module_path)
			attr = getattr(module, attr_name)
			# Cache the imported attribute in the module's globals
			globals()[name] = attr
			return attr
		except ImportError as e:
			raise ImportError(f'Failed to import {name} from {module_path}: {e}') from e

	raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
	# Message types -> for easier transition from langchain
	'BaseMessage',
	'UserMessage',
	'SystemMessage',
	'AssistantMessage',
	# Content parts with better names
	'ContentText',
	'ContentRefusal',
	'ContentImage',
	# Chat models
	'BaseChatModel',
	'ChatOpenAI',
	'ChatDeepSeek',
	'ChatAnthropic',
]
