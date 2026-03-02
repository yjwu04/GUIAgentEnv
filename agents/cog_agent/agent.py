import platform
import sys
import pyautogui
import re
import os
from PIL import Image
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import Dict, Any, Optional, Tuple

from app.register import agent
from agent_base import AgentAdapter, AgentStepResult
from utils import get_screenshot


class CogAgent(AgentAdapter):
    def identify_os(self) -> str:
        """
        Identifies the operating system based on the platform information.

        Returns:
        - str: "Mac" if the system is macOS, "WIN" if the system is Windows.

        Raises:
        - ValueError: If the operating system is not supported.
        """

        os_detail = platform.platform().lower()
        if "mac" in os_detail:
            return "Mac"
        elif "windows" in os_detail:
            return "WIN"
        else:
            raise ValueError(
                f"This {os_detail} operating system is not currently supported!"
            )


    def init(self, model_dir, max_steps, img_save_path = "screenshots", max_length = 4096, top_k = 1):
        self.model_dir = model_dir
        self.max_steps = max_steps
        self.platform = self.identify_os()
        self.max_length = max_length
        self.top_k = top_k
        
        self.img_save_path = img_save_path
        img_dir = os.path.dirname(self.img_save_path)
        if img_dir and not os.path.exists(img_dir):
            os.makedirs(img_dir, exist_ok = True)
        
        self.history_step = []
        self.history_action = [] 


    def is_balanced(self, s: str) -> bool:
        """
        Checks if the parentheses in a string are balanced.

        Parameters:
        - s (str): The string to check.

        Returns:
        - bool: True if parentheses are balanced, False otherwise.
        """
        stack = []
        mapping = {")": "(", "]": "[", "}": "{"}
        if "(" not in s:
            return False
        for char in s:
            if char in mapping.values():
                stack.append(char)
            elif char in mapping.keys():
                if not stack or mapping[char] != stack.pop():
                    return False
        return not stack


    def extract_operation(self, step: Optional[str]) -> Dict[str, Any]:
        """
        Extracts the operation and other details from the grounded operation step.

        Parameters:
        - step (Optional[str]): The grounded operation string.

        Returns:
        - Dict[str, Any]: A dictionary containing the operation details.
        """
        if step is None or not self.is_balanced(step):
            return {
                "box": [],
                "operation": "NO_ACTION"
            }

        op, detail = step.split("(", 1)
        detail = "(" + detail
        others_pattern = r"(\w+)\s*=\s*([^,)]+)"
        others = re.findall(others_pattern, detail)
        Grounded_Operation = dict(others)

        boxes_pattern = r"box=\[\[(.*?)\]\]"
        boxes = re.findall(boxes_pattern, detail)
        if boxes:
            Grounded_Operation["box"] = list(map(int, boxes[0].split(",")))
        Grounded_Operation["operation"] = op.strip()

        return Grounded_Operation


    def step(self, task, round_num, format_key = "action_op_sensitive"):
        """
        A continuous interactive demo using the CogAgent1.5 model with selectable format prompts.
        The output_image_path is interpreted as a directory. For each round of interaction,
        the annotated image will be saved in the directory with the filename:
        {original_image_name_without_extension}_{round_number}.png

        Example:
        python cli_demo.py --model_dir THUDM/cogagent-9b-20241220 --platform "Mac" --max_length 4096 --top_k 1 \
                        --output_image_path ./results --format_key status_action_op_sensitive
        """

        # Dictionary mapping format keys to format strings
        format_dict = {
            "action_op_sensitive": "(Answer in Action-Operation-Sensitive format.)",
            "status_plan_action_op": "(Answer in Status-Plan-Action-Operation format.)",
            "status_action_op_sensitive": "(Answer in Status-Action-Operation-Sensitive format.)",
            "status_action_op": "(Answer in Status-Action-Operation format.)",
            "action_op": "(Answer in Action-Operation format.)",
        }

        # Ensure the provided format_key is valid
        if format_key not in format_dict:
            raise ValueError(
                f"Invalid format_key. Available keys are: {list(format_dict.keys())}"
            )

        # Load the tokenizer and model
        tokenizer = AutoTokenizer.from_pretrained(self.model_dir, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            self.model_dir,
            torch_dtype=torch.bfloat16,
            trust_remote_code=True,
            device_map="auto",
            # quantization_config=BitsAndBytesConfig(load_in_8bit=True), # For INT8 quantization
            # quantization_config=BitsAndBytesConfig(load_in_4bit=True), # For INT4 quantization
        ).eval()
        # Initialize platform and selected format strings
        platform_str = f"(Platform: {platform})\n"
        format_str = format_dict[format_key]

        # Capture the current screen for the round
        img_path_before = f"{self.img_save_path}/{round_num}_before.png"
        get_screenshot(img_path_before)
        try:
            image = Image.open(img_path_before).convert("RGB")
        except Exception:
            print("Invalid image path. Please try again.")

        # Format history steps for output
        history_str = "\nHistory steps: "
        for index, (step, action) in enumerate(zip(self.history_step, self.history_action)):
            history_str += f"\n{index}. {step}\t{action}"

        # Compose the query with task, platform, and selected format instructions
        query = f"Task: {task}{history_str}\n{platform_str}{format_str}"
        print(f"query:{query}")

        inputs = tokenizer.apply_chat_template(
            [{"role": "user", "image": image, "content": query}],
            add_generation_prompt=True,
            tokenize=True,
            return_tensors="pt",
            return_dict=True,
        ).to(model.device)
        # Generation parameters
        gen_kwargs = {
            "max_length": self.max_length,
            "do_sample": True,
            "top_k": self.top_k,
        }

        # Generate response
        with torch.no_grad():
            outputs = model.generate(**inputs, **gen_kwargs)
            outputs = outputs[:, inputs["input_ids"].shape[1]:]
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            print(f"Model response:\n{response}")

        # Extract grounded operation and action
        grounded_pattern = r"Grounded Operation:\s*(.*)"
        action_pattern = r"Action:\s*(.*)"
        matches_history = re.search(grounded_pattern, response)
        matches_actions = re.search(action_pattern, response)

        if matches_history:
            step = matches_history.group(1)
            self.history_step.append(step)
        if matches_actions:
            action = matches_actions.group(1)
            self.history_action.append(action)

        # Process bounding boxes and operations
        grounded_operation = self.extract_operation(step)
        if grounded_operation["operation"] == "NO_ACTION":
            status = "SUCCESS"
        else:
            status = agent(grounded_operation)

        # Capture the current screen for the round
        img_path_after = f"{self.img_save_path}/{round_num}_after.png"
        get_screenshot(img_path_after)

        return AgentStepResult(
            input = query,
            observation_before = img_path_before,
            action = grounded_operation,
            action_result = status,
            observation_after = img_path_after,
            output = response
        )


    def run(self, task):
        """
        Main workflow for handling a chatbot interaction loop.

        Yields:
        - history (list): Updated history of the chatbot interaction.
        - output_image (str): Path to the generated output image.
        """

        round_num = 1
        results = []
        try:
            while True:
                print(f"\033[92m Round {round_num}: \033[0m")
                if round_num > self.max_steps:
                    break  # Exit the loop after 15 rounds

                result = self.step(task = task, round_num = round_num)
                results.append(result)
                round_num += 1
        except Exception as e:
            print(e)
            raise e
        
        return results


if __name__ == "__main__":
    agent = CogAgent()
    agent.init(
        model_dir = "",
        max_steps = 10,
    )

    result = agent.run("find a picture of cat")
