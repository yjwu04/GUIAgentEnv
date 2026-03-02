import asyncio
from re import I, M
import sys
from typing import Any, Dict
import json
import openai
from openai import OpenAI
import os
import yaml
import asyncio
from mistralai import Mistral
import sensenova
import sys
from dotenv import load_dotenv
load_dotenv()
import anthropic

'''
Helper functions to call LLM with different models
'''

def call_llm(model_name: str, sys_prompt: str, user_prompt: str, parameters: Dict[str, Any], output_format: json, switch_model: bool) -> Dict[str, Any]:
    '''
    Calling llms by name, updating...
    '''
    if model_name == 'deepseek':
        print('ds is selected')
        return call_ds(sys_prompt, user_prompt, parameters, output_format, switch_model= switch_model)
    elif model_name == 'mistral':
        print('mistral is selected')
        return call_mistral(sys_prompt, user_prompt, parameters, output_format, switch_model= switch_model)
    elif model_name == 'gpt':
        print('gpt is selected')
        return call_gpt(sys_prompt, user_prompt, parameters, output_format, switch_model= switch_model)
    elif model_name == 'claude':
        print('claude is selected')
        return call_claude(sys_prompt, user_prompt, parameters, output_format, switch_model= switch_model)
    else:
        raise ValueError(f"Model name {model_name} not supported")

def call_mistral(sys_prompt: str, user_prompt: str, parameters: Dict[str, Any], output_format: json, switch_model: bool) -> str:
    os.environ['MISTRAL_API_KEY'] = os.getenv("MISTRAL_API_KEY")
    api_key = os.environ["MISTRAL_API_KEY"]
    model = "mistral-small-latest"
    if switch_model:
        model = "mistral-large-latest"
    client = Mistral(api_key=api_key)
    #transform parameters to str
    parameters_str = ''
    for key in parameters:
        parameters[key] = str(parameters[key])
        parameters_str += f'{key}: {parameters[key]}\n'

    chat_response = client.chat.complete(
        model = model,
        messages = [
            {
                "role": "user",
                "content": sys_prompt + user_prompt + parameters_str,
            },
        ],
        response_format = {
            "type": "text",
            "json_schema": output_format
        },
    )
    print('sucessfully called mistral')
    print(chat_response.choices[0].message.content)
    return chat_response.choices[0].message.content

def call_ds(sys_prompt: str, user_prompt: str, parameters: Dict[str, Any], output_format: json, switch_model: bool) -> str:  
    parameters_str = ''
    for key in parameters:
        parameters[key] = str(parameters[key])
        parameters_str += f'{key}: {parameters[key]}\n'
    
    sensenova.access_key_id = os.getenv("SENSETIME_ACCESS_KEY")     
    sensenova.secret_access_key = os.getenv("SENSETIME_SECRET_ACCESS_KEY")     
    #print(sensenova.access_key_id, sensenova.secret_access_key)   

    stream = False
    model_id = "DeepSeek-V3" 
    if switch_model:
        model_id = "DeepSeek-R1"

    resp = sensenova.ChatCompletion.create(
        messages=[
            {"role": "system", "content": sys_prompt + 'OUTPUT FORMAT IS AS FOLLOWS' + str(output_format)},
            {"role": "user", "content": user_prompt + parameters_str}
            ],
        model=model_id,
        stream=stream,
        max_new_tokens=1024,
        repetition_penalty=1.05,
        temperature=0.8,
        top_p=0.7,
        user="s",
    )
    '''    
        if not stream:
            resp = [resp]
        for part in resp:
            choices = part['data']["choices"]
            for c_idx, c in enumerate(choices):
                if len(choices) > 1:
                    sys.stdout.write("===== Chat Completion {} =====\n".format(c_idx))
                if stream:
                    delta = c.get("delta")
                    if delta:
                        sys.stdout.write(delta)
                else:
                    sys.stdout.write(c["message"])
                    if len(choices) > 1:
                        sys.stdout.write("\n")
                sys.stdout.flush()

        return resp
    '''
    raw_text = resp['data']['choices'][0]['message']
    json_data = None
    try:
        if '```json' in raw_text:
            start = raw_text.find('```json') + 7
            end = raw_text.find('```', start)
            json_str = raw_text[start:end].strip()
            json_data = json.loads(json_str)
            json_data = json.loads(raw_text)
    except:
        pass
    
    return raw_text, json_data

def call_claude( sys_prompt: str, user_prompt: str, parameters: Dict[str, Any], output_format: json, switch_model: bool) -> str:
    client = anthropic.Anthropic()

    parameters_str = ''
    for key in parameters:
        parameters[key] = str(parameters[key])
        parameters_str += f'{key}: {parameters[key]}\n'

    model_name = "claude-sonnet-3-5"
    if switch_model:
        model_name = "claude-sonnet-4-5"

    response = client.messages.create(
        model = model_name,
        max_tokens = 1024,
        system = [
            {
                "type": text,
                "text": sys_prompt,
            },
            {
                "type": text,
                "text": parameters_str,
            }
        ],
        messages = [{"role": "user", "content": user_prompt + "output in this format" + str(output_format)}]
    )
    json_data = response.usage.model_dump_json()
    raw_text = str(json_data)
    return raw_text, json_data
    

def call_gpt(sys_prompt: str, user_prompt: str, parameters: Dict[str, Any], output_format: json, switch_model: bool) -> str:
    '''
    Calling GPT-4.5 with different parameters
    
    openai.api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI()
    response = client.chatcompletion.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content
    '''
