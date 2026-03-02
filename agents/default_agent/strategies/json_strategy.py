from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from agent_base import AgentStepResult
from messages import (  # type: ignore
    AssistantMessage,
    BaseMessage,
    SystemMessage,
    UserMessage,
)

from ..models.base import BaseChatModel
from ..models.factory import ModelFactory, ModelSettings
from ..tools.base import ToolCollection, ToolResult
from .base import BaseStrategy


def _serialize_messages(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    return [msg.dict() for msg in messages]


def _extract_json_block(text: str) -> Dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None

    if "```" in text:
        idx = 0
        while True:
            start = text.find("```", idx)
            if start == -1:
                break
            end = text.find("```", start + 3)
            if end == -1:
                break
            snippet = text[start + 3 : end].strip()
            if snippet.lower().startswith("json"):
                snippet = snippet[4:].strip()
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                idx = end + 3
                continue

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        return None
    try:
        return json.loads(text[start_idx : end_idx + 1])
    except json.JSONDecodeError:
        return None


@dataclass
class _ConversationState:
    messages: List[BaseMessage] = field(default_factory=list)
    last_input: str = ""
    finished: bool = False
    final_response: str = ""


class JsonToolStrategy(BaseStrategy):
    """LLM + JSON tool invocation strategy."""

    def __init__(
        self,
        model_settings: ModelSettings,
        tool_collection: ToolCollection,
        *,
        system_prompt: str,
        max_steps: int,
    ) -> None:
        self.model: BaseChatModel = ModelFactory.create(model_settings)
        self.tool_collection = tool_collection
        self.system_prompt = system_prompt
        self.max_steps = max_steps
        self.state = _ConversationState()

        system_message = SystemMessage(
            content=f"{self.system_prompt}\n\nAvailable tools:\n{self.tool_collection.describe()}",
        )
        self.state.messages = [system_message]

    async def run(self, instruction: str) -> List[AgentStepResult]:
        if not instruction.strip():
            raise ValueError("Empty instruction.")
        self.state.last_input = instruction
        self.state.finished = False
        self.state.final_response = ""
        self.state.messages.append(UserMessage(content=instruction))

        results: List[AgentStepResult] = []
        for _ in range(self.max_steps):
            result = await self._step()
            results.append(result)
            if self.state.finished:
                break
        return results

    async def _step(self) -> AgentStepResult:
        before = _serialize_messages(self.state.messages)
        completion = await self.model.ainvoke(self.state.messages)
        assistant_reply = completion.completion if hasattr(completion, "completion") else str(completion)
        self.state.messages.append(AssistantMessage(content=assistant_reply))

        parsed = _extract_json_block(assistant_reply)
        action = "final"
        user_visible = assistant_reply
        tool_result: ToolResult | None = None

        if parsed:
            action = parsed.get("action", "final")
            user_visible = parsed.get("response", assistant_reply).strip()
            if action != "final":
                tool_input = parsed.get("action_input") or {}
                tool_result = await self.tool_collection.execute(action, tool_input)
                feedback = UserMessage(
                    content=(
                        f"Tool `{action}` returned:\n{tool_result}\n"
                        "If more work is needed continue planning, otherwise answer with action='final'."
                    )
                )
                self.state.messages.append(feedback)
            else:
                self.state.finished = True
                self.state.final_response = user_visible
        else:
            self.state.finished = True
            self.state.final_response = assistant_reply

        after = _serialize_messages(self.state.messages)
        return AgentStepResult(
            input=self.state.last_input,
            observation_before={"messages": before},
            action=action if parsed else "final",
            action_result={
                "model_reply": assistant_reply,
                "parsed": parsed,
                "tool_result": tool_result.to_dict() if tool_result else None,
            },
            observation_after={"messages": after},
            output=user_visible,
        )
