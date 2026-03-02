import re
import base64
import importlib
from typing import List
from http import HTTPStatus
from abc import abstractmethod

import requests
import dashscope

import os
os.environ["DASHSCOPE_DEFAULT_TIMEOUT"] = "60"

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


class BaseModel:
    def __init__(self):
        pass

    @abstractmethod
    def get_model_response(self, prompt: str, images: List[str]) -> (bool, str):
        pass


class OpenAIModel(BaseModel):
    def __init__(self, base_url: str, api_key: str, model: str, temperature: float = 0.0, max_tokens: int = 300):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def get_model_response(self, prompt: str, images: List[str]) -> (bool, str):
        content = [
            {
                "type": "text",
                "text": prompt
            }
        ]
        for img in images:
            base64_img = encode_image(img)
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_img}"
                }
            })
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        response = requests.post(self.base_url, headers=headers, json=payload).json()
        print(response)
        if "error" not in response:
            usage = response["usage"]
            prompt_tokens = usage["prompt_tokens"]
            completion_tokens = usage["completion_tokens"]
            print(f"Request cost is "f"${'{0:.2f}'.format(prompt_tokens / 1000 * 0.01 + completion_tokens / 1000 * 0.03)}")
        else:
            return False, response["error"]["message"]
        return True, response["choices"][0]["message"]["content"]


class QwenModel(BaseModel):
    def __init__(self, api_key: str, model: str):
        super().__init__()
        self.model = model
        dashscope.api_key = api_key

    def get_model_response(self, prompt: str, images: List[str]) -> (bool, str):
        content = [{
            "text": prompt
        }]
        for img in images:
            img_path = f"file://{img}"
            content.append({
                "image": img_path
            })
        messages = [
            {
                "role": "user",
                "content": content
            }
        ]
        try:
            response = dashscope.MultiModalConversation.call(model=self.model, messages=messages)
        except Exception as e:
            print(e)
        print(response)
        if response.status_code == HTTPStatus.OK:
            return True, response.output.choices[0].message.content[0]["text"]
        else:
            return False, response.message


openAI_model_list = [
    "gpt-4o"
]

qwen_model_list = [
    "qwen-vl-plus"
]


def get_model(model_name, base_url, api_key):
    if model_name in openAI_model_list:
        return OpenAIModel(base_url, api_key, model_name)
    if model_name in qwen_model_list:
        return QwenModel(api_key, model_name)


def load_actions_from_file(path):
    module_name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    actions = []
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        try:
            if issubclass(attr, module.BaseAction) and attr is not module.BaseAction:
                actions.append(attr)
        except TypeError:
            continue
    return actions


def parse_rsp(rsp):
    print(rsp)
    rsp = rsp.replace('`', '')
    try:
        observation = re.findall(r"Observation: (.*?)$", rsp, re.MULTILINE)[0]
        think = re.findall(r"Thought: (.*?)$", rsp, re.MULTILINE)[0]
        act = re.findall(r"Action: (.*?)$", rsp, re.MULTILINE)[0]
        try:
            summary = re.findall(r"Summary: (.*?)$", rsp, re.MULTILINE)[0]
        except:
            summary = "None"
        print("Observation:")
        print(observation)
        print("Thought:")
        print(think)
        print("Action:")
        print(act)
        print("Summary:")
        print(summary)
        if "FINISH" in act:
            return ["FINISH"]
        
        act_name = act.split("(")[0]
        
        if act_name == "grid":
            return [act_name]

        pattern = fr"{act_name}\((.*?)\)"
        params = re.findall(pattern, act)[0]
        print(params)
        if params.startswith('"') and params.endswith('"'):
            params = params[1:-1]

        return [act_name, params, summary]
    except Exception as e:
        print(f"ERROR: an exception occurs while parsing the model response: {e}")
        print(rsp)
        return ["ERROR"]

