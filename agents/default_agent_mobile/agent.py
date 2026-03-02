import os
import re
import cv2
import json
import time
import argparse
import datetime
import importlib
import pyshine as ps

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
default_agent_path = Path(__file__).parent
sys.path.insert(0, str(default_agent_path))

import prompts
from agent_base import AgentAdapter, AgentStepResult
from utils_mobile import get_screenshot as get_screenshot_utils
from model import get_model, parse_rsp
from android_controller import AndroidController

class DefaultAgent(AgentAdapter):

    def draw_grid(self, img_path, output_path):
        def get_unit_len(n):
            for i in range(1, n + 1):
                if n % i == 0 and 120 <= i <= 180:
                    return i
            return -1

        image = cv2.imread(img_path)
        height, width, _ = image.shape
        color = (255, 116, 113)
        unit_height = get_unit_len(height)
        if unit_height < 0:
            unit_height = 120
        unit_width = get_unit_len(width)
        if unit_width < 0:
            unit_width = 120
        thick = int(unit_width // 50)
        rows = height // unit_height
        cols = width // unit_width
        for i in range(rows):
            for j in range(cols):
                label = i * cols + j + 1
                left = int(j * unit_width)
                top = int(i * unit_height)
                right = int((j + 1) * unit_width)
                bottom = int((i + 1) * unit_height)
                cv2.rectangle(image, (left, top), (right, bottom), color, thick // 2)
                cv2.putText(image, str(label), (left + int(unit_width * 0.05) + 3, top + int(unit_height * 0.3) + 3), 0, int(0.01 * unit_width), (0, 0, 0), thick)
                cv2.putText(image, str(label), (left + int(unit_width * 0.05), top + int(unit_height * 0.3)), 0, int(0.01 * unit_width), color, thick)
        cv2.imwrite(output_path, image)
        return rows, cols


    def draw_bbox_multi(self, img_path, output_path, elem_list):
        imgcv = cv2.imread(img_path)
        count = 1
        for elem in elem_list:
            try:
                top_left = elem.bbox[0]
                bottom_right = elem.bbox[1]
                left, top = top_left[0], top_left[1]
                right, bottom = bottom_right[0], bottom_right[1]
                label = str(count)
                text_color = (255, 250, 250)
                bg_color = (10, 10, 10)
                imgcv = ps.putBText(
                    imgcv,
                    label, 
                    alpha = 0.5,
                    hspace = 10, 
                    vspace = 10, 
                    thickness = 2, 
                    font_scale = 1, 
                    text_RGB = text_color, 
                    background_RGB = bg_color,
                    text_offset_x = (left + right) // 2 + 10, 
                    text_offset_y = (top + bottom) // 2 + 10,
                )
            except Exception as e:
                print(f"ERROR: An exception occurs while labeling the image\n{e}", "red")
            count += 1
        cv2.imwrite(output_path, imgcv)
        return imgcv


    def parse_action(self, path):
        module_name = os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        BaseAction = module.BaseAction
        classes = [cls for name, cls in module.__dict__.items() if isinstance(cls, type) and issubclass(cls, BaseAction)]
        descriptions = []
        for i, cls in enumerate(classes):
            descriptions.append(f"{i}. {cls.description.strip()}\n")
        return ''.join(descriptions)


    def init(self, model_args, action_list, adb_path = "adb", grid_mode = False, log_dir = "./logs/default_agent/", max_iter = 10, max_retry = 3):
        try:
            self.model = get_model(
                model_name = model_args["model_name"],
                base_url = model_args["base_url"],
                api_key = model_args["api_key"]
            )
        except:
            raise Exception("No requested model")

        self.log_dir = log_dir
        self.adb_path = adb_path
        self.max_iter = max_iter
        self.max_retry = max_retry
        self.grid_mode = grid_mode
        self.action_list = action_list


    def step(self, iter):
        print(f"[Step {iter}] Processing task...")

        try:
            screenshot_path = self.android_controller.get_screenshot(f"step_{iter}")
        except Exception as e:
            raise e
        
        try:
            xml_path = self.android_controller.get_xml(f"step_{iter}")
        except Exception as e:
            xml_path = "ERROR"

        if self.grid_mode or xml_path == "ERROR":
            rows, cols = self.draw_grid(screenshot_path, os.path.join(self.log_dir, f"{iter}_grid.png"))
            image = os.path.join(self.log_dir, f"{iter}_grid.png")
            prompt = prompts.task_template_grid
            elem_list = None
        else:
            elem_list = self.android_controller.get_element_list(xml_path)
            self.draw_bbox_multi(screenshot_path, os.path.join(self.log_dir, f"{iter}_labeled.png"), elem_list)
            image = os.path.join(self.log_dir, f"{iter}_labeled.png")
            prompt = re.sub(r"<ui_document>", "", prompts.task_template)
            rows, cols = None, None
        
        prompt = re.sub(r"<task_description>", self.task, prompt)
        prompt = re.sub(r"<last_act>", self.last_action, prompt)
        prompt = re.sub(r"<action_list>", self.parse_action(self.action_list), prompt)
        print("Thinking about what to do in the next step...")
        status, response = self.model.get_model_response(prompt, [image])

        if status:
            # with open(self.log_dir, "a") as logfile:
            #     log_item = {"step": iter, "prompt": prompt, "image": f"{self.log_dir}_{iter}_labeled.png", "response": response}
            #     logfile.write(json.dumps(log_item) + "\n")
            res = parse_rsp(response)
            print(res)

            img_path_before = f"screenshots/default_agent_mobile/{self.task_id}_{iter}_before.png"
            get_screenshot_utils(img_path_before, self.adb_path)
            try:
                action, action_result, self.last_action = self.android_controller.execute_action(res, rows, cols, elem_list, self.action_list)
                if action["name"] == "grid":
                    self.grid_mode = True
                if action["name"] == "FINISH":
                    print(1)
                    return AgentStepResult(
                        input = prompt,
                        observation_before = img_path_before,
                        action = action,
                        action_result = action_result,
                        observation_after = img_path_after,
                        output = response
                    )
            except e:
                action, action_result = res[0], "Error"
            img_path_after = f"screenshots/default_agent_mobile/{self.task_id}_{iter}_after.png"
            get_screenshot_utils(img_path_after, self.adb_path) 
        else:
            img_path_before = f"screenshots/default_agent_mobile/{self.task_id}_{iter}_before.png"
            get_screenshot_utils(img_path_before, self.adb_path)
            action, action_result = None, None
            img_path_after = f"screenshots/default_agent_mobile/{self.task_id}_{iter}_after.png"
            get_screenshot_utils(img_path_after, self.adb_path) 

        return AgentStepResult(
            input = prompt,
            observation_before = img_path_before,
            action = action,
            action_result = action_result,
            observation_after = img_path_after,
            output = response
        )


    def run(self, task, task_id = None):
        self.task = task
        self.last_action = "None"
        self.task_id = datetime.datetime.fromtimestamp(int(time.time())).strftime(f"%Y-%m-%d_%H-%M-%S") if task_id is None else task_id
        self.log_dir = Path(self.log_dir) / self.task_id
        
        self.android_controller = AndroidController(
            log_dir = self.log_dir
        )

        iter = 1
        results = []
        while iter <= self.max_iter:
            attempt = 1
            result = None
            while attempt <= self.max_retry:
                try:
                    result = self.step(iter)
                    break
                except Exception as e:
                    attempt += 1
                    print(f"Step {iter} failed after {attempt} attempts.")
                
            if result is None:
                raise Exception(f"Step {iter} finally failed after maximum attempts")
            else:
                iter += 1
                results.append(result)
    
                if result.action["name"] == "FINISH":
                    break

        return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_file", required=True)
    args = parser.parse_args()

    with open(args.task_file, "r", encoding="utf-8") as f:
        params = json.load(f)
    print(params)

    agent = DefaultAgent()

    # agent.init(
    #     {
    #         "model_name": "gpt-4o",
    #         "base_url": "https://api.openai.com/v1/chat/completions",
    #         "api_key": "YOUR_API_KEY",
    #     },
    #     "D:/Project/Noisy Benchmark/agents/default_agent_mobile/actionlist.py"
    # )

    # agent.init(
    #     {
    #         "model_name": "qwen-vl-plus",
    #         "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    #         "api_key": "YOUR_API_KEY"
    #     },
    #     "D:/Project/Noisy Benchmark/agents/default_agent_mobile/actionlist.py"
    # )
    
    agent.init(
        {
            "model_name": params["model_name"],
            "base_url": params["base_url"],
            "api_key": params["api_key"]
        },
        params["action_list"]
    )
    
    agent.run(params["task"])
