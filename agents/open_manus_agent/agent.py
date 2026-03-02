import asyncio
import os
import sys
from loguru import logger


import sys
from pathlib import Path
agent_path = Path(__file__).parent / "OpenManus"
sys.path.insert(0, str(agent_path))
sys.path.insert(0, str(Path(__file__).parent.parent)) 


from agent_base import AgentAdapter, AgentStepResult
from utils import get_screenshot
from app.agent.manus import Manus
from app.sandbox.client import SANDBOX_CLIENT
from app.schema import AgentState, Message


class OpenManusAgent(AgentAdapter):

    def init(self, img_save_path: str = "screenshots", max_steps = 10):
        self.max_steps = max_steps
        self.agent = asyncio.run(Manus.create())
        
        self.img_save_path = img_save_path
        img_dir = os.path.dirname(self.img_save_path)
        if img_dir and not os.path.exists(img_dir):
            os.makedirs(img_dir, exist_ok = True)


    async def step(self, current_step):
        input = {
            "messages": self.agent.messages,
            "system_msgs": (
                [Message.system_message(self.agent.system_prompt)]
                if self.agent.system_prompt
                else None
            ),
            "tools": self.agent.available_tools.to_params(),
            "tool_choice": self.agent.tool_choices,
        }

        img_path_before = f"{self.img_save_path}/{current_step}_before.png"
        get_screenshot(img_path_before)

        think_result = await self.agent.think()
        if think_result:
            output = await self.agent.act()
            action = "act"
            action_result = {"action_result": output}
        else:
            output = self.agent.memory.get_recent_messages(1)
            action = "think"
            action_result = {"action_result": think_result}

        img_path_after = f"{self.img_save_path}/{current_step}_after.png"
        get_screenshot(img_path_after)

        input["messages"] = [
            msg.to_dict() if hasattr(msg, "to_dict") and msg.role != "tool" else msg
            for msg in input.get("messages", [])
        ]

        return AgentStepResult(
            input=input,
            observation_before={"image": img_path_before},
            action=action,
            action_result=action_result,
            observation_after={"image": img_path_after},
            output=output
        )


    async def work(self, input: str):
        try:
            if not input.strip():
                logger.warning("Empty prompt provided.")
                return None

            logger.warning("Processing your input...")
            self.agent.update_memory("user", input)
            current_step = 0
            results = []
            async with self.agent.state_context(AgentState.RUNNING):
                while (
                    current_step < self.max_steps and self.agent.state != AgentState.FINISHED
                ):
                    current_step += 1
                    logger.info(f"Executing step {current_step}/{self.max_steps}")
                    step_result = await self.step(current_step)

                    # Check for stuck state
                    if self.agent.is_stuck():
                        self.agent.handle_stuck_state()

                    results.append(step_result)

                if current_step >= self.max_steps:
                    current_step = 0
                    self.agent.state = AgentState.IDLE
                    results.append(
                        AgentStepResult(
                            input=None,
                            observation_before={"image": None},
                            action="terminate",
                            action_result={"action_result": f"Reached max steps ({self.max_steps})"},
                            observation_after={"image": None},
                            output=None,
                        )
                    )

            await SANDBOX_CLIENT.cleanup()

            return results
        finally:
            await self.agent.cleanup()


    def run(self, input):
        result = asyncio.run(self.work(input))
        return result

if __name__ == "__main__":
    agent = OpenManusAgent()
    agent.init(img_save_path = "./", max_steps = 10)

    asyncio.run(agent.run("find a picture of cat"))

