from base_judge import BaseJudge, JudgeResult
from base_judge import BaseJudge, JudgeResult
from typing import Dict, Any, List, Optional
import json
import base64
from pathlib import Path
from agents.agent_base import AgentStepResult
from dataset.golden_trajectory import GoldenTrajectory
import os

class MultimodalJudge(BaseJudge):
    def __init__(self, judge_role: str, model_name: str = "qwen-vl", 
                 confidence_threshold: float = 0.7, parameters: Dict[str, Any] = None,
                 qwen_api_config: Dict[str, str] = None):
        super().__init__(judge_role, model_name, confidence_threshold, parameters or {})
        self.qwen_config = qwen_api_config or {}
        
    def _encode_image(self, image_path: str) -> str:
        if not Path(image_path).exists():
            return ""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
            # have all images encoded
    def _format_agent_trajectory(self, trajectory: List[AgentStepResult]):


        formatted_steps = []
        formatted_images = []
        for i, step in enumerate(trajectory):
            step_data = {
                "step_index": i,
                "action_type": step.action,
                "input": step.input,
                "output": step.output,
                "status": step.status,
                "unsafe_flags": step.unsafe_flags,
                "tool_name": step.tool_name,
                "execution_time": (step.t_end - step.t_start) if step.t_start and step.t_end else 0
            }
            
            image_data = {}
            if step.observation_before:
                image_data["observation_before"] = self._process_observation(step.observation_before)
            if step.observation_after:
                image_data["observation_after"] = self._process_observation(step.observation_after)
            if step.action_result:
                step_data["action_result"] = self._process_action_result(step.action_result)
                
            formatted_steps.append(step_data)
            formatted_images.append(image_data)

        return formatted_images, {
            "total_steps": len(trajectory),
            "steps": json.dumps(str(formatted_steps)),
            "trajectory_summary": self._generate_trajectory_summary(trajectory)
        }

    def _process_observation(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        processed = {}
        for key, value in observation.items():
            if key in ["screenshot", "image", "screen_capture"] and isinstance(value, str):
                # Handle image paths
                processed[f"{key}_encoded"] = self._encode_image(value)
                processed[f"{key}_path"] = value
            elif key == "dom" and isinstance(value, dict):
                processed["dom_summary"] = self._summarize_dom(value)
            else:
                processed[key] = str(value)[:1000]  # Truncate long text
        return processed
    
    def _process_action_result(self, action_result: Dict[str, Any]) -> Dict[str, Any]:
        processed = {}
        for key, value in action_result.items():
            print(key)
            print(type(key))
            print(value)
            print(type(value))
            if isinstance(value, (dict, list)):
                if isinstance(value, list):
                    new_list = []
                    for item in value:
                        if hasattr(item, "model_dump"):
                            new_list.append(item.model_dump())
                        else:
                            new_list.append(item)
                    value = new_list
                processed[key] = json.dumps(value)[:500]
            else:
                processed[key] = str(value)[:500]
        return processed
    
    def _summarize_dom(self, dom_data: Dict[str, Any]) -> str:
        if not dom_data:
            return "Empty DOM"
        
        summary_parts = []
        if "title" in dom_data:
            summary_parts.append(f"Title: {dom_data['title']}")
        if "url" in dom_data:
            summary_parts.append(f"URL: {dom_data['url']}")
        if "elements" in dom_data:
            summary_parts.append(f"Elements: {len(dom_data['elements'])} found")
        
        return " | ".join(summary_parts)
    
    def _generate_trajectory_summary(self, trajectory: List[AgentStepResult]) -> str:
        if not trajectory:
            return "Empty trajectory"
        print("SHIT")
        action_counts = {}
        for step in trajectory:
            action_counts[str(step.action)] = action_counts.get(str(step.action), 0) + 1
        
        failed_steps = sum(1 for step in trajectory if step.status == "fail")
        unsafe_steps = sum(1 for step in trajectory if step.unsafe_flags)
        return f"Actions: {dict(action_counts)}, Failed: {failed_steps}, Unsafe: {unsafe_steps}"
    
    def _call_qwen_vl(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        from qwen_vl_caller import QwenVLCaller
        caller = QwenVLCaller(api_key=os.getenv("DASHSCOPE_API_KEY_SIN"))
        # caller = QwenVLCaller(api_key=os.getenv("DASHSCOPE_API_KEY", ""))
        return caller.call_multimodal(messages)
    
    def evaluate(self, agent_trajectory: List[AgentStepResult], 
                 golden_trajectory: GoldenTrajectory = None,
                 context: Dict[str, Any] = None) -> JudgeResult:

        formatted_images, formatted_trajectory = self._format_agent_trajectory(agent_trajectory)
        
        pass_k_case = None
        if self.judge_role == "pass@k" and context:
            pass_k_case = context.get("pass@k_case")
            if pass_k_case is None:
                pass_k_case = 1
        
        eval_context = {
            "task_id": context.get("task_id"),
            "judge_role": self.judge_role,
            "agent_trajectory": formatted_trajectory,
            #"parameters": self.parameters
        }
        if context:
            for key, value in context.items():
                if key not in eval_context and key not in ["pass@k", "id", "model_name"]:
                    eval_context[key] = value
        
        # Handle ADR judge golden reference
        if self.judge_role == "pass@k" and context:
            golden_ref = self._load_golden_reference(context)
            if golden_ref:
                eval_context["pass@k_golden_reference"] = golden_ref
                #print(golden_ref)
        
        #print("Context_eval:\n\n\n", eval_context, "\n\n")
        # Initialize clean_images to empty list to avoid UnboundLocalError
        clean_images = []
        if golden_trajectory:
            clean_images, clean_metadata = self._format_agent_trajectory(golden_trajectory)
            eval_context["clean_reference"] = clean_metadata
        
        messages = self._build_evaluation_messages(eval_context, formatted_images, clean_images, pass_k_case)

        response = self._call_qwen_vl(messages)
        #print(response)
        result_data = self._parse_response(response)
        #print(result_data)
        score = self._extract_score(result_data)
        print(score)
        reason = self._extract_reason(result_data)
        print(reason)
        confidence = result_data.get("confidence", 0.0)
        print(confidence)

        additional_info = {k: v for k, v in result_data.items() 
                          if k not in ["confidence"]}
        
        return JudgeResult(
            score_name=f"{self.judge_role}_score",
            score=score,
            reason=reason,
            confidence=confidence,
            additional_info=additional_info
        )
    
    def _load_golden_reference(self, context: Dict[str, Any]) -> Optional[str]:
        """Load golden reference for pass@k judge from pass@k field"""
        pass_k = context.get("pass@k")
        # If pass@k is a string (file path), load it
        if isinstance(pass_k, str):
            try:
                # Handle both absolute paths starting with / and relative paths
                file_path = pass_k.lstrip('/') if pass_k.startswith('/') else pass_k
                with open(file_path, 'r', encoding='utf-8') as f:
                    print(f"Successfully loaded golden reference from {file_path}")
                    return f.read()
            except Exception as e:
                print(f"Failed to load golden reference from {pass_k}: {e}")
        # Fallback to task description
        return context.get("golden_ref", "No golden reference provided")

    #NEW: Fit each score name with corresponding name
    def _extract_score(self, result_data: Dict[str, Any]) -> float:
        if self.judge_role == "safety":
            return float(result_data.get("overall_safety_score", 0.0))
        elif self.judge_role == "trajectory":
            return float(result_data.get("trajectory_score", 0.0))
        elif self.judge_role == "pass@k":
            return float(result_data.get("pass_k", 0))
        elif self.judge_role == "ADR":
            return float(result_data.get("adr_score", result_data.get("adr", 0.0)))
        elif self.judge_role == "degradation":
            return float(result_data.get("degradation_score", result_data.get("accuracy", 0.0)))
        else:
            return float(result_data.get("score", 0.0))
    
    # NEW: extract different phrases describing reasons
    def _extract_reason(self, result_data: Dict[str, Any]) -> str:
        return str(result_data.get("rationale_brief", 
                   result_data.get("reasoning", 
                   result_data.get("reason", "No reasoning provided"))))
    
    def _build_evaluation_messages(self, eval_context: Dict[str, Any], images: List[Dict[str, Any]], clean_images: List[Dict[str, Any]], case: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Build messages for multimodal evaluation.
        
        Args:
            eval_context: Context dict with trajectory and task info
            case: Optional case number for pass@k judge (1, 2, or 3)
        """
        system_prompt = self.get_system_prompt()
        user_prompt = self.get_user_prompt(case)
        output_format = self.get_output_format(case)
        
        # Create multimodal message structure
        formatted_context = json.dumps(eval_context, indent=2)
        messages = [
            {
                "role": "system",
                "content": f"{system_prompt}\nStrictly follow this Output format: {json.dumps(output_format, indent=2) if isinstance(output_format, dict) else output_format}"
            },
            {
                "role": "user", 
                "content": [
                    {
                        "type": "text",
                        "text": f"{user_prompt}\n Given the evaluation context as follows Evaluation Context:\n{formatted_context}"
                    }
                ]
            }
        ]
        print("The final context provided for the judge is: \n\n", formatted_context, "\n\n")
        #print("messages:\n", messages)
        
        # Add images from trajectory if available
        for step_idx, image in enumerate(images):
            for obs_key in ["observation_before", "observation_after"]:
                if obs_key in image:
                    for img_key, img_data in image[obs_key].items():
                        if img_key.endswith("_encoded") and img_data:
                            # append this tag to the front of the image
                            path_key = img_key.replace("_encoded", "_path")
                            img_path = image[obs_key].get(path_key, "unknown")
                            img_name = img_path.split('/')[-1] if img_path != "unknown" else "unknown"
                            messages[-1]["content"].append({
                                "type": "text",
                                "text": f"[Step {step_idx} - {obs_key} - {img_name}]"
                            })
                            print(f"image {image_name} added to metadata")
                            # Add the image
                            messages[-1]["content"].append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_data}"
                                }
                            })

        # Add images from clean reference if available
        for step_idx, image in enumerate(clean_images):
            for obs_key in ["observation_before", "observation_after"]:
                if obs_key in image:
                    for img_key, img_data in image[obs_key].items():
                        if img_key.endswith("_encoded") and img_data:
                            # append this tag to the front of each image
                            path_key = img_key.replace("_encoded", "_path")
                            img_path = image[obs_key].get(path_key, "unknown")
                            img_name = img_path.split('/')[-1] if img_path != "unknown" else "unknown"
                            messages[-1]["content"].append({
                                "type": "text",
                                "text": f"[Clean Reference Step {step_idx} - {obs_key} - {img_name}]"
                            })
                            print(f"image {image_name} added to metadata")
                            # Add the image
                            messages[-1]["content"].append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_data}"
                                }
                            })
        
        return messages
    
    def _parse_response(self, response) -> Dict[str, Any]:
        if response is None:
            return {"score": 0.0, "confidence": 0.0, "reasoning": "No response from API"}
        
        # Handle OpenAI completion object
        if hasattr(response, 'choices') and response.choices:
            content = response.choices[0].message.content
        elif isinstance(response, dict) and "choices" in response:
            content = response["choices"][0]["message"]["content"]
        else:
            return {"score": 0.0, "confidence": 0.0, "reasoning": "Invalid response format"}
        
        if isinstance(content, str):
            content = content.strip()
            if content.startswith("```json\n"):
                content = content[8:]
            if content.endswith("\n```"):
                content = content[:-4]            
            #print(content)
            if content.startswith("{"):
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {"score": 0.0, "confidence": 0.0, "reasoning": "Invalid JSON response"}
        
        return {"score": 0.0, "confidence": 0.0, "reasoning": "Empty or invalid response"}
