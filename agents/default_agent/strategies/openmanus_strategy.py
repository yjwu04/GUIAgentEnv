from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Dict, List

from loguru import logger

from agent_base import AgentStepResult

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OPEN_MANUS_PATH = os.path.join(PROJECT_ROOT, "open_manus_agent", "OpenManus")
import sys

sys.path.insert(0, OPEN_MANUS_PATH)

from app.agent.manus import Manus  # type: ignore
from app.sandbox.client import SANDBOX_CLIENT  # type: ignore
from app.schema import AgentState, Message  # type: ignore

from ..tools.default_tools.desktop import ScreenshotTool
from .base import BaseStrategy


class OpenManusStrategy(BaseStrategy):
    def __init__(self, extras: Dict[str, object] | None = None) -> None:
        extras = extras or {}
        self.max_steps = int(extras.get("max_steps", 10))
        self.img_save_path = str(extras.get("img_save_path", "screenshots"))
        img_dir = os.path.dirname(self.img_save_path)
        if img_dir and not os.path.exists(img_dir):
            os.makedirs(img_dir, exist_ok=True)
        self.agent = asyncio.run(Manus.create())
        self.screenshotter = ScreenshotTool(workspace_root=Path.cwd())  # type: ignore[arg-type]

    async def _capture(self, current_step: int, phase: str) -> str:
        filename = f"{self.img_save_path}/{current_step}_{phase}.png"
        await self.screenshotter(path=filename)
        return filename

    async def _step(self, current_step: int) -> AgentStepResult:
        payload = {
            "messages": self.agent.messages,
            "system_msgs": (
                [Message.system_message(self.agent.system_prompt)]
                if self.agent.system_prompt
                else None
            ),
            "tools": self.agent.available_tools.to_params(),
            "tool_choice": self.agent.tool_choices,
        }

        img_before = await self._capture(current_step, "before")
        think_result = await self.agent.think()
        if think_result:
            output = await self.agent.act()
            action = "act"
            action_result = {"result": output}
        else:
            output = self.agent.memory.get_recent_messages(1)
            action = "think"
            action_result = {"result": think_result}
        img_after = await self._capture(current_step, "after")

        return AgentStepResult(
            input=payload,
            observation_before=img_before,
            action=action,
            action_result=action_result,
            observation_after=img_after,
            output=output,
        )

    async def run(self, instruction: str) -> List[AgentStepResult]:
        try:
            if not instruction.strip():
                raise ValueError("Empty instruction.")

            logger.info("OpenManus processing input...")
            self.agent.update_memory("user", instruction)
            current_step = 0
            results: List[AgentStepResult] = []
            async with self.agent.state_context(AgentState.RUNNING):
                while current_step < self.max_steps and self.agent.state != AgentState.FINISHED:
                    current_step += 1
                    logger.info("Executing OpenManus step %s/%s", current_step, self.max_steps)
                    step_result = await self._step(current_step)
                    if self.agent.is_stuck():
                        self.agent.handle_stuck_state()
                    results.append(step_result)

                if current_step >= self.max_steps and self.agent.state != AgentState.FINISHED:
                    self.agent.state = AgentState.IDLE
                    results.append(
                        AgentStepResult(
                            input=instruction,
                            observation_before={},
                            action="terminated",
                            action_result={},
                            observation_after={},
                            output=f"Terminated: Reached max steps ({self.max_steps})",
                        )
                    )
            await SANDBOX_CLIENT.cleanup()
            return results
        finally:
            await self.agent.cleanup()
