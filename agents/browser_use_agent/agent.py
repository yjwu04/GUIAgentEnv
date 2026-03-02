# from __future__ import annotations
# from abc import ABC, abstractmethod
# from dataclasses import dataclass, field
# from typing import Any, Dict, Literal, Optional
import asyncio
import os
import time
import inspect


import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
browser_use_main_path = Path(__file__).parent / "browser_use_main"
sys.path.insert(0, str(browser_use_main_path))

# @dataclass
# class AgentStepResult:
#     """
#     A normalized per-step snapshot:
#       - input:             textual instruction or synthesized subgoal
#       - observation_*:     environment observations before/after the action
#       - action:            coarse-grained action type ("tool" for generic tool-call)
#       - action_result:     structured result payload (stdout, screenshot path, DOM hash, etc.)
#       - output:            assistant surface text for this step (if any)
#     This is intentionally generic enough to cover GUI (computer-use), DOM browser-use,
#     and pure text reasoning steps.
#     """
#     # To be modified
#     input: str = ""
#     observation_before: Dict[str, Any] = field(default_factory=dict)
#     action: ActionType = "none"
#     action_result: Dict[str, Any] = field(default_factory=dict)
#     observation_after: Dict[str, Any] = field(default_factory=dict)
#     output: str = ""

#     # Optional metadata for logging/metrics
#     model: Optional[str] = None
#     tool_name: Optional[str] = None
#     tool_call_id: Optional[str] = None
#     status: Literal["ok", "fail", "terminated"] = "ok"
#     unsafe_flags: list[str] = field(default_factory=list)
#     t_start: Optional[float] = None
#     t_end: Optional[float] = None

#     def to_event(self, run_id: str, task_id: str, website: Optional[str] = None, noise: Optional[str] = None) -> Dict[str, Any]:
#         """Convert to a unified JSONL event row used by our metrics/bench pipelines."""
#         return {
#             "run_id": run_id,
#             "task_id": task_id,
#             "website": website,
#             "noisea_profile": noise,
#             "t_start": self.t_start,
#             "t_end": self.t_end,
#             "action": self.action,
#             "tool_name": self.tool_name,
#             "tool_call_id": self.tool_call_id,
#             "status": self.status,
#             "unsafe_flags": list(self.unsafe_flags),
#             "input": self.input,
#             "output": self.output,
#             "observation_before": self.observation_before,
#             "action_result": self.action_result,
#             "observation_after": self.observation_after,
#             "model": self.model,
#         }


# class AgentAdapter(ABC):
#     """Interface-like base: multi-step agent wrapper."""

#     def init(self) -> None:
#         """Reset internal state for a new test case."""
#         ...

#     def step(self) -> AgentStepResult:
#         ...

#     def run(self) -> AgentStepResult:
#         """High-level loop: until success/stop/timeout."""
#         ...


# ActionType = Literal["click", "swipe", "type", "tool", "none"]

# import os
# import pyautogui

# def get_screenshot(img_path):
#     # os.makedirs(os.path.dirname(img_path), exist_ok=True)
#     # img = pyautogui.screenshot()
#     # img.save(img_path)
#     return

from agent_base import AgentAdapter, AgentStepResult
from utils import get_screenshot
from browser_use_main.browser_use.agent.service import Agent 
from browser_use_main.browser_use.agent.views import AgentStepInfo
from browser_use_main.browser_use.llm import ChatDeepSeek, ChatAnthropic, ChatOpenAI
from browser_use_main.browser_use.utils import SignalHandler
from browser_use_main.browser_use.agent.cloud_events import (
    CreateAgentOutputFileEvent,
    CreateAgentSessionEvent,
    CreateAgentTaskEvent,
    UpdateAgentTaskEvent,
)
from browser_use_main.browser_use.agent.views import (
    ActionResult,
    AgentHistory,
    AgentStepInfo,
    BrowserStateHistory,
)

class browserUseAgent(AgentAdapter):
    def get_model(self, model_name, api_key, base_url):
        if "claude" in model_name:
            return ChatAnthropic(
                model = model_name,
                api_key = api_key,
                base_url = base_url
            )
        elif "gpt" in model_name:
            return ChatOpenAI(
                model = model_name,
                api_key = api_key,
                base_url = base_url,
            )
        elif "deepseek" in model_name:
            print("deepseek")
            return ChatDeepSeek(
                model = model_name,
                api_key = api_key,
                base_url = base_url
            )
        else:
            raise Exception("Model not found")
            

    def init(self, model_name, api_key, base_url, max_steps = 2, img_save_path = "screenshots", task = ""):
        self.max_steps = max_steps
        model = self.get_model(model_name, api_key, base_url)
        print(model.api_key)
        self.agent = Agent(
            llm = model,
            task = task
        )
        self.img_save_path = img_save_path
        img_dir = os.path.dirname(self.img_save_path)
        if img_dir and not os.path.exists(img_dir):
            os.makedirs(img_dir, exist_ok = True)

    
    async def step(self, step_info):
        input = self.agent.state.last_plan
        
        img_path_before = f"{self.img_save_path}/{step_info.step_number}_before.png"
        get_screenshot(img_path_before)

        await self.agent.step(step_info)
        
        img_path_after = f"{self.img_save_path}/{step_info.step_number}_after.png"
        get_screenshot(img_path_after)

        return AgentStepResult(
            input = input,
            observation_before = {"image": img_path_before},
            action = self.agent.state.last_model_output.action,
            action_result = {"action_result": self.agent.state.last_result},
            observation_after = {"image": img_path_after},
            output = self.agent.state.last_model_output.next_goal
        )


    async def work(self, input):
        if not input.strip():
            print("Empty prompt provided.")
            return None
        
        self.agent.task = input
        self.agent._message_manager.task = input
        results = []
        loop = asyncio.get_event_loop()
        
        agent_run_error = None # Initialize error tracking variable
        self._force_exit_telemetry_logged = False # ADDED: Flag for custom telemetry on force exit

        # Set up the  signal handler with callbacks specific to this agent

        # Define the custom exit callback function for second CTRL+C
        def on_force_exit_log_telemetry():
            self.agent._log_agent_event(max_steps=self.max_steps, agent_run_error='SIGINT: Cancelled by user')
            # NEW: Call the flush method on the telemetry instance
            if hasattr(self.agent, 'telemetry') and self.agent.telemetry:
                self.agent.telemetry.flush()
            self.agent._force_exit_telemetry_logged = True  # Set the flag
        signal_handler = SignalHandler(
            loop=loop,
            pause_callback=self.agent.pause,
            resume_callback=self.agent.resume,
            custom_exit_callback=on_force_exit_log_telemetry,  # Pass the new telemetrycallback
            exit_on_second_int=True,
        )
        signal_handler.register()

        try:
            self.agent._log_agent_run()

            self.agent.logger.debug(
                f'🔧 Agent setup: Task ID {self.agent.task_id[-4:]}, Session ID {self.agent.session_id[-4:]}, Browser Session ID {self.agent.browser_session.id[-4:] if self.agent.browser_session else "None"}'
            )

            # Initialize timing for session and task
            self.agent._session_start_time = time.time()
            self.agent._task_start_time = self.agent._session_start_time  # Initialize task start time

            # Only dispatch session events if this is the first run
            if not self.agent.state.session_initialized:
                self.agent.logger.debug('📡 Dispatching CreateAgentSessionEvent...')
                # Emit CreateAgentSessionEvent at the START of run()
                self.agent.eventbus.dispatch(CreateAgentSessionEvent.from_agent(self.agent))

                self.agent.state.session_initialized = True

            self.agent.logger.debug('📡 Dispatching CreateAgentTaskEvent...')
            # Emit CreateAgentTaskEvent at the START of run()
            self.agent.eventbus.dispatch(CreateAgentTaskEvent.from_agent(self.agent))
            # Start browser session and attach watchdogs
            assert self.agent.browser_session is not None, 'Browser session must be initialized before starting'
            self.agent.logger.debug('🌐 Starting browser session...')
            from browser_use.browser.events import BrowserStartEvent

            event = self.agent.browser_session.event_bus.dispatch(BrowserStartEvent())
            await event
            self.agent.logger.debug('🔧 Browser session started with watchdogs attached')

            # Check if task contains a URL and add it as an initial action (only if preload is enabled)
            if self.agent.preload:
                initial_url = self.agent._extract_url_from_task(self.agent.task)
                if initial_url:
                    self.agent.logger.info(f'🔗 Found URL in task: {initial_url}, adding as initial action...')

                    # Create a go_to_url action for the initial URL
                    go_to_url_action = {
                        'go_to_url': {
                            'url': initial_url,
                            'new_tab': False,  # Navigate in current tab
                        }
                    }

                    # Add to initial_actions or create new list if none exist
                    if self.agent.initial_actions:
                        # Convert back to dict format, prepend URL navigation, then convert back
                        initial_actions_dicts = []
                        for action in self.agent.initial_actions:
                            action_data = action.model_dump(exclude_unset=True)
                            initial_actions_dicts.append(action_data)

                        # Prepend the go_to_url action
                        initial_actions_dicts = [go_to_url_action] + initial_actions_dicts

                        # Convert back to ActionModel instances
                        self.agent.initial_actions = self.agent._convert_initial_actions(initial_actions_dicts)
                    else:
                        # Create new initial_actions with just the go_to_url
                        self.agent.initial_actions = self.agent._convert_initial_actions([go_to_url_action])

                    self.agent.logger.debug(f'✅ Added navigation to {initial_url} as initial action')

            # Execute initial actions if provided
            if self.agent.initial_actions:
                print(self.agent.initial_actions)
                self.agent.logger.debug(f'⚡ Executing {len(self.agent.initial_actions)} initial actions...')
                result = await self.agent.multi_act(self.agent.initial_actions, check_for_new_elements=False)
                self.agent.state.last_result = result
                self.agent.logger.debug('✅ Initial actions completed')
            print("SHIT")
            self.agent.logger.debug(f'🔄 Starting main execution loop with max {self.max_steps} steps...')
            for step in range(self.max_steps):
                # Replace the polling with clean pause-wait
                if self.agent.state.paused:
                    self.agent.logger.debug(f'⏸️ Step {step}: Agent paused, waiting to resume...')
                    await self.agent.wait_until_resumed()
                    signal_handler.reset()

                # Check if we should stop due to too many failures
                if self.agent.state.consecutive_failures >= self.agent.settings.max_failures:
                    self.agent.logger.error(f'❌ Stopping due to {self.agent.settings.max_failures} consecutive failures')
                    agent_run_error = f'Stopped due to {self.agent.settings.max_failures} consecutive failures'
                    break

                # Check control flags before each step
                if self.agent.state.stopped:
                    self.agent.logger.info('🛑 Agent stopped')
                    agent_run_error = 'Agent stopped programmatically'
                    break

                while self.agent.state.paused:
                    await asyncio.sleep(0.2)  # Small delay to prevent CPU spinning
                    if self.agent.state.stopped:  # Allow stopping while paused
                        agent_run_error = 'Agent stopped programmatically while paused'
                        break

                self.agent.logger.debug(f'🚶 Starting step {step + 1}/{self.max_steps}...')
                step_info = AgentStepInfo(step_number=step, max_steps=self.max_steps)

                try:
                    results.append(
                        await asyncio.wait_for(
                            self.step(step_info),
                            timeout=self.agent.settings.step_timeout,
                        )
                    )
                    self.agent.logger.debug(f'✅ Completed step {step + 1}/{self.max_steps}')
                except TimeoutError:
                    # Handle step timeout gracefully
                    error_msg = f'Step {step + 1} timed out after {self.agent.settings.step_timeout} seconds'
                    self.agent.logger.error(f'⏰ {error_msg}')
                    self.agent.state.consecutive_failures += 1
                    self.agent.state.last_result = [ActionResult(error=error_msg)]

                if self.agent.history.is_done():
                    self.agent.logger.debug(f'🎯 Task completed after {step + 1} steps!')
                    await self.agent.log_completion()
                    print(1)
                    print(result)
                    # if self.agent.register_done_callback:
                    #     if inspect.iscoroutinefunction(self.agent.register_done_callback):
                    #         await self.agent.register_done_callback(self.agent.history)
                    #     else:
                    #         self.agent.register_done_callback(self.agent.history)

                    # Task completed
                    return results
                
            agent_run_error = 'Failed to complete task in maximum steps'

            self.agent.history.add_item(
                AgentHistory(
                    model_output=None,
                    result=[ActionResult(error=agent_run_error, include_in_memory=True)],
                    state=BrowserStateHistory(
                        url='',
                        title='',
                        tabs=[],
                        interacted_element=[],
                        screenshot_path=None,
                    ),
                    metadata=None,
                )
            )

            self.agent.logger.info(f'❌ {agent_run_error}')

            self.agent.logger.debug('📊 Collecting usage summary...')
            self.agent.history.usage = await self.agent.token_cost_service.get_usage_summary()

            # set the model output schema and call it on the fly
            if self.agent.history._output_model_schema is None and self.agent.output_model_schema is not None:
                self.agent.history._output_model_schema = self.agent.output_model_schema

            self.agent.logger.debug('🏁 Agent.run() completed successfully')
            return results

        finally:
            print("A")
            # Log token usage summary
            await self.agent.token_cost_service.log_usage_summary()
            print("B")
            # Unregister signal handlers before cleanup
            signal_handler.unregister()
            # print("C")
            # if not self.agent._force_exit_telemetry_logged:  # MODIFIED: Check the flag
            #     try:
            #         self.agent._log_agent_event(max_steps=self.max_steps, agent_run_error=agent_run_error)
            #     except Exception as log_e:  # Catch potential errors during logging itself
            #         self.agent.logger.error(f'Failed to log telemetry event: {log_e}', exc_info=True)
            # else:
            #     # ADDED: Info message when custom telemetry for SIGINT was already logged
            #     self.agent.logger.debug('Telemetry for force exit (SIGINT) was logged by custom exit callback.')

            # # NOTE: CreateAgentSessionEvent and CreateAgentTaskEvent are now emitted at the START of run()
            # # to match backend requirements for CREATE events to be fired when entities are created,
            # # not when they are completed
            # print("D")
            # # Emit UpdateAgentTaskEvent at the END of run() with final task state
            # self.agent.eventbus.dispatch(UpdateAgentTaskEvent.from_agent(self))
            # print("E")
            # # Generate GIF if needed before stopping event bus
            # if self.agent.settings.generate_gif:
            #     output_path: str = 'agent_history.gif'
            #     if isinstance(self.agent.settings.generate_gif, str):
            #         output_path = self.agent.settings.generate_gif

            #     # Lazy import gif module to avoid heavy startup cost
            #     from browser_use.agent.gif import create_history_gif

            #     create_history_gif(task=self.agent.task, history=self.agent.history, output_path=output_path)

            #     # Only emit output file event if GIF was actually created
            #     if Path(output_path).exists():
            #         output_event = await CreateAgentOutputFileEvent.from_agent_and_file(self.agent, output_path)
            #         self.agent.eventbus.dispatch(output_event)
            print("F")
            # Wait briefly for cloud auth to start and print the URL, but don't block for completion
            if self.agent.enable_cloud_sync and hasattr(self.agent, 'cloud_sync'):
                if self.agent.cloud_sync.auth_task and not self.agent.cloud_sync.auth_task.done():
                    try:
                        # Wait up to 1 second for auth to start and print URL
                        await asyncio.wait_for(self.agent.cloud_sync.auth_task, timeout=1.0)
                    except TimeoutError:
                        self.agent.logger.debug('Cloud authentication started - continuing in background')
                    except Exception as e:
                        self.agent.logger.debug(f'Cloud authentication error: {e}')

            # Stop the event bus gracefully, waiting for all events to be processed
            # Use longer timeout to avoid deadlocks in tests with multiple agents
            try:
                await asyncio.wait_for(self.agent.eventbus.stop(timeout=10.0), timeout=3.0)
            except Exception as e:
                print("eventbus.stop stuck:", e)

            try:
                await asyncio.wait_for(self.agent.close(), timeout=3.0)
            except Exception as e:
                print("close stuck:", e)


    def run(self, input):
        result = asyncio.run(self.work(input))
        print(result)
        return result


if __name__ == "__main__":
    agent = browserUseAgent()
    agent.init(model_name = "deepseek-chat", api_key = os.getenv("DEEPSEEK_API_KEY", ""), base_url = 'https://api.deepseek.com/v1')

    agent.run("Find the number of stars of the browser-use repo")
