import os
import sys
from loguru import logger
from openai import OpenAI

from agent_base import AgentAdapter, AgentStepResult
from utils import get_screenshot
from codes.ui_tars.action_parser import parse_action_to_structure_output, parsing_response_to_pyautogui_code, add_box_token
from codes.ui_tars.prompt import COMPUTER_USE_DOUBAO

class UITarsAgent(AgentAdapter):
    def init(self, base_url, api_key, max_steps = 10, img_save_path: str = "screenshots"):
        self.max_steps = max_steps
        self.client = OpenAI(
            base_url = base_url,
            api_key = api_key
        )
        
        self.img_save_path = img_save_path
        img_dir = os.path.dirname(self.img_save_path)
        if img_dir and not os.path.exists(img_dir):
            os.makedirs(img_dir, exist_ok = True)


    def step(self, current_step, messages):
        for message in messages:
            if message["role"] == "assistant":
                message["content"] = add_box_token(message["content"])
        chat_completion = self.client.chat.completions.create(
            model="tgi",
            messages=messages,
            top_p=None,
            temperature=0.0,
            max_tokens=400,
            stream=True,
            seed=None,
            stop=None,
            frequency_penalty=None,
            presence_penalty=None
        )
        for message in chat_completion:
            response += message.choices[0].delta.content    
        print(response)    

        original_image_width, original_image_height = 1920, 1080
        parsed_dict = parse_action_to_structure_output(
            response,
            factor=1000,
            origin_resized_height=original_image_height,
            origin_resized_width=original_image_width,
            model_type="doubao"
        )
        print(parsed_dict)
        parsed_pyautogui_code = parsing_response_to_pyautogui_code(
            responses=parsed_dict,
            image_height=original_image_height,
            image_width=original_image_width
        )
        print(parsed_pyautogui_code)

        img_path_before = f"{self.img_save_path}/{current_step}_before.png"
        get_screenshot(img_path_before)
        action_result = "SUCCESS"
        try:
            exec(parsed_pyautogui_code)
        except:
            action_result = "ERROR"
        
        img_path_after = f"{self.img_save_path}/{current_step}_after.png"
        get_screenshot(img_path_after)

        return AgentStepResult(
            input=messages,
            observation_before=img_path_before,
            action=parsed_dict,
            action_result=action_result,
            observation_after=img_path_after,
            output=response
        )


    def run(self, input: str):
        try:
            if not input.strip():
                logger.warning("Empty prompt provided.")
                return None

            logger.warning("Processing your input...")

            current_step = 0
            results = []
            messages = [
                {
                    "role": "system",
                    "content": COMPUTER_USE_DOUBAO.format(
                        language = "English",
                        instruction = input
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": get_screenshot()
                            }
                        }
                    ]
                }
            ]
            
            while(current_step < self.max_steps):
                current_step += 1
                logger.info(f"Executing step {current_step}/{self.max_steps}")
                try:
                    step_result = self.step(current_step, messages)
                except Exception as e:
                    logger.error(e)
                    raise e

                results.append(step_result)
                messages.append(
                    {
                        "role": "assistant",
                        "content": step_result.output
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": step_result.observation_after
                                }
                            }
                        ]
                    }
                )

                if step_result.action.action_type == "finished":
                    break

            return results
        except Exception as e:
            logger.error(e)
            raise e


if __name__ == "__main__":
    agent = UITarsAgent()
    agent.init(
        base_url = "",
        api_key = "",
    )

    result = agent.run("find a picture of cat")
