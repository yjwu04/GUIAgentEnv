import os
import json
import base64
from typing import Dict, Any, List
from openai import OpenAI
import httpx

class QwenVLCaller:
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.client_available = False
        
        if not self.api_key:
            print("api_key not configured, please double check")
            return
            
        try:
            http_client = httpx.Client()
            client = OpenAI(
                api_key=self.api_key,
                base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
                #base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                http_client=http_client
            )
            self.client = client
            self.client_available = True
            return
        
        except Exception as e:
            print(f"❌ OpenAI client initialization failed: {e}")
            return
    
    def call_multimodal(self, messages: List[Dict[str, Any]], 
                       model: str = "qwen-vl-plus", # use basic qwen model first
                       temperature: float = 0.1) -> Dict[str, Any]:

        if not self.client_available:
            return None
        
        try:
            completion = self.client.chat.completions.create(
                    model= model,
                    messages= messages
                )
            print(completion)
            # Return the full completion object for compatibility
            return completion
            
        except Exception as e:
            print("❌ API call failed:", repr(e))
            return None
    def format_multimodal_message(self, text: str, images: List[str] = None) -> Dict[str, Any]:
        content = [{"type": "text", "text": text}]
        
        if images:
            for img_path in images:
                if os.path.exists(img_path):
                    with open(img_path, "rb") as f:
                        img_base64 = base64.b64encode(f.read()).decode()
                    content.append({
                        "type": "image_url", 
                        "image_url": {"url": f"data:image/png;base64,{img_base64}"}
                    })
        
        return {"role": "user", "content": content}
    
    def extract_json_from_response(self, response) -> Dict[str, Any]:
        print(response)
        if response is None:
            return {"error": "No response from API"}
        if hasattr(response, 'choices') and response.choices:
            content = response.choices[0].message.content
        print(content)
        if isinstance(content, str):
            content = content.strip()
            if content.startswith("{"):
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {"error": "Invalid JSON response", "raw_content": content}
            elif "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                try:
                    return json.loads(content[start:end].strip())
                except json.JSONDecodeError:
                    return {"error": "Invalid JSON in code block", "raw_content": content}
        return {"error": "No valid JSON found", "raw_content": str(content)}

def call_qwen_vl(sys_prompt: str, user_prompt: str, parameters: Dict[str, Any], 
                 output_format: Dict[str, Any], images: List[str] = None,
                 switch_model: bool = False) -> tuple[str, Dict[str, Any]]:

    caller = QwenVLCaller(api_key=os.getenv("DASHSCOPE_API_KEY", ""))
    param_text = "\n".join([f"{k}: {v}" for k, v in parameters.items()])
    full_prompt = f"{sys_prompt}\n\n{user_prompt}\n\nParameters:\n{param_text}\n\nOutput format:({output_format})"
    messages = [
        {"role": "system", "content": "You are an expert evaluator. Respond in the exact JSON format specified."},
        caller.format_multimodal_message(full_prompt, images)
    ]
    model = "qwen-vl-plus"
    response = caller.call_multimodal(messages, model=model)
    json_result = caller.extract_json_from_response(response)
    return json.dumps(json_result, indent=2), json_result
