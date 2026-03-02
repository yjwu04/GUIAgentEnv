import asyncio
import os
import platform
import sys
import time
from typing import Tuple

from agent_base import AgentAdapter, AgentStepResult

from prompt_toolkit.shortcuts import message_dialog
from prompt_toolkit import prompt

from operate.exceptions import ModelNotRecognizedException
from operate.models.prompts import USER_QUESTION, get_system_prompt
from operate.config import Config
from operate.utils.style import (
    ANSI_GREEN, ANSI_RESET, ANSI_YELLOW, ANSI_RED,
    ANSI_BRIGHT_MAGENTA, ANSI_BLUE, style,
)
from operate.utils.operating_system import OperatingSystem
from operate.utils.screenshot import capture_screen_with_cursor
from operate.models.apis import get_next_action

class SelfOperatingComputer(AgentAdapter):
    
    def init(self, model, max_steps = 10, verbose: bool = True, img_save_path: str = "screenshots") -> None:
        """Reset agent state for a new test case."""
        self.model = model
        self.max_steps = max_steps
        self.config = Config()
        self.operating_system = OperatingSystem()
        self.config.verbose = verbose
        self.img_save_path = img_save_path
        img_dir = os.path.dirname(self.img_save_path)
        if img_dir and not os.path.exists(img_dir):
            os.makedirs(img_dir, exist_ok = True)

        # agent state
        self.messages = []
        self.session_id = None


    def operate(self, operations) -> bool:
        """Execute a sequence of operations returned by the model."""
        if self.config.verbose:
            print("[SOC][operate]")
        for operation in operations:
            if self.config.verbose:
                print("[SOC][operate] operation", operation)

            time.sleep(1)  # simulate delay
            operate_type = operation.get("operation", "").lower()
            operate_thought = operation.get("thought", "")
            operate_detail = ""

            if operate_type in ("press", "hotkey"):
                keys = operation.get("keys")
                operate_detail = keys
                self.operating_system.press(keys)
            elif operate_type == "write":
                content = operation.get("content")
                operate_detail = content
                self.operating_system.write(content)
            elif operate_type == "click":
                x, y = operation.get("x"), operation.get("y")
                click_detail = {"x": x, "y": y}
                operate_detail = click_detail
                self.operating_system.mouse(click_detail)
            elif operate_type == "done":
                summary = operation.get("summary", "")
                print(f"[SOC | {self.model}]")
                print(f"{ANSI_BLUE}Objective Complete: {ANSI_RESET}{summary}\n")
                return True
            else:
                print(f"[SOC]{ANSI_RED}[Error] unknown operation {operate_type}{ANSI_RESET}")
                print(f"[SOC]{ANSI_RED}[Error] full response {ANSI_RESET}{operation}")
                return True

            # print step log
            print(f"[SOC | {self.model}]")
            print(f"{operate_thought}")
            print(f"{ANSI_BLUE}Action: {ANSI_RESET}{operate_type} {operate_detail}\n")

        return False


    def step(self, objective: str, iter: int) -> Tuple[bool, AgentStepResult]:
        """Given input (prompt / UI state / etc.), produce one step result."""
        try:
            capture_screen_with_cursor(f"./{self.img_save_path}/screenshot_{iter}_before.png")
            observation_before = f"./{self.img_save_path}/screenshot_{iter}_before.png"
            operations, self.session_id = asyncio.run(
                get_next_action(self.model, self.messages, objective, self.session_id)
            )
            stop = self.operate(operations)
            capture_screen_with_cursor(f"./{self.img_save_path}/screenshot_{iter}_after.png")
            observation_after = f"./{self.img_save_path}/screenshot_{iter}_after.png"         
            return stop, AgentStepResult(
                input=objective,
                observation_before=observation_before,
                action=operations,
                action_result="SUCCESS",
                observation_after=observation_after,
                output=operations
            )
        except ModelNotRecognizedException as e:
            print(f"{ANSI_GREEN}[SOC]{ANSI_RED}[Error] -> {e}{ANSI_RESET}")
            return {"stop": True, "error": str(e)}
        except Exception as e:
            print(f"{ANSI_GREEN}[SOC]{ANSI_RED}[Error] -> {e}{ANSI_RESET}")
            return {"stop": True, "error": str(e)}


    def run(self, terminal_prompt: str = None) -> None:
        """High-level execution for a full task."""
        # --- clear screen ---
        if platform.system() == "Windows":
            os.system("cls")
        else:
            print("\033c", end="")

        # --- get objective ---
        if terminal_prompt:
            print("Running direct prompt...")
            objective = terminal_prompt
        else:
            message_dialog(
                title="Self-Operating Computer",
                text="An experimental framework to enable multimodal models to operate computers",
                style=style,
            ).run()
            print(f"[{ANSI_GREEN}Self-Operating Computer {ANSI_RESET}|{ANSI_BRIGHT_MAGENTA} {self.model}{ANSI_RESET}]\n{USER_QUESTION}")
            print(f"{ANSI_YELLOW}[User]{ANSI_RESET}")
            objective = prompt(style=style)

        # --- prepare system message ---
        system_prompt = get_system_prompt(self.model, objective)
        system_message = {"role": "system", "content": system_prompt}
        self.messages = [system_message]

        # --- main loop ---
        results = []
        for _ in range(self.max_steps):
            stop, result = self.step(objective, _)
            results.append(result)
            if stop:
                break
        
        return results


if __name__ == "__main__":
    agent = SelfOperatingComputer()
    agent.init(
        max_steps = 10,
        model = "qwen-vl" 
    )

    agent.run("Find a picture of cats")
    