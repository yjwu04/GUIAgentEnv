from __future__ import annotations
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass
from abc import ABC, abstractmethod
import os
import pathlib
import yaml
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from agents.agent_base import AgentStepResult

@dataclass
class JudgeResult:
    score_name: str # e.g., Degradation Score
    score: float
    reason: str
    confidence: float # from 0-1 
    additional_info: Dict[str, Any]

@dataclass
class InputType:
    input: AgentStepResult
    # direct use of AgentStepResult

@dataclass
class Context:
    noise_type: str
    noise_name: str
    golden_trajectory: list[AgentStepResult]

class BaseJudge(ABC):
    """
    Abstract base class for all judge implementations.
    
    Judges evaluate agent performance on specific criteria (safety, trajectory, etc.)
    by loading prompts from YAML templates and calling LLM/multimodal APIs.
    """

    def __init__(self, judge_role: str, model_name: str, confidence_threshold:float, parameters: Dict[str, Any]):
        self.judge_role = judge_role
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.parameters = parameters
    
    def get_parameters(self) -> Dict[str, Any]:
        """
        Extract context parameters from YAML template that match provided parameters.
        
        Returns:
            Dict containing parameters that exist in both YAML template and self.parameters
        """
        current_dir = pathlib.Path(__file__).parent
        prompts_dir = current_dir / 'prompts'
        yaml_path = prompts_dir / f'{self.judge_role}_judge_prompt.yaml'
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f)
            context = {}
            if 'context' in content['template'] and content['template']['context'] is not None:
                for key, _ in content['template']['context'].items():
                    if key in self.parameters:
                        context[key] = self.parameters[key]
            return context

    def get_system_prompt(self) -> str:
        current_dir = pathlib.Path(__file__).parent
        prompts_dir = current_dir / 'prompts'
        yaml_path = prompts_dir / f'{self.judge_role}_judge_prompt.yaml'
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f)
            prompt = content['template']["system_prompt"]['role']
            return prompt

    def get_user_prompt(self, case: Optional[int] = None) -> str:
        """
        Get user prompt (rules) for the judge.
        For pass@k judge, case parameter selects which rule set to use.
        
        Args:
            case: Optional case number (1, 2, or 3) for pass@k judge
            
        Returns:
            Rules string for the judge
        """
        current_dir = pathlib.Path(__file__).parent
        prompts_dir = current_dir / 'prompts'
        yaml_path = prompts_dir / f'{self.judge_role}_judge_prompt.yaml'
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f)
            
            # Handle pass@k case selection
            if self.judge_role == "pass@k" and case is not None:
                # For pass@k, rules is a dict at template level
                rules_section = content['template'].get('rules', {})
                if isinstance(rules_section, dict):
                    #added new prompt assembly line 
                    if case == 4:
                        rules = "The judge should first select a certain case type out of the following 3 to decide its judgingc criteria and output format."
                        rules = rules + rules_section["case1"] + rules_section["case2"] + rules_section["case3"]
                        return rules
                    case_key = f'case{case}'
                    if case_key in rules_section:
                        return rules_section[case_key]
                    else:
                        # Fallback to case1 if specified case doesn't exist
                        return rules_section.get('case1', '')
            
            # Standard behavior for other judges - rules under system_prompt
            system_prompt = content['template'].get("system_prompt", {})
            if isinstance(system_prompt, dict):
                prompt = system_prompt.get('rules', '')
            else:
                prompt = ''
            return prompt



    def get_output_format(self, case: Optional[int] = None) -> Dict[str, Any]:
        """
        Get output format for the judge.
        For pass@k judge, case parameter selects which output format to use.
        
        Args:
            case: Optional case number (1, 2, or 3) for pass@k judge
            
        Returns:
            Output format dict or string for the judge
        """
        current_dir = pathlib.Path(__file__).parent
        prompts_dir = current_dir / 'prompts'
        yaml_path = prompts_dir / f'{self.judge_role}_judge_prompt.yaml'
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f)
            output_format = content['template']["output_format"]
            
            # Handle pass@k case selection
            if self.judge_role == "pass@k" and case is not None:
                if isinstance(output_format, dict):
                    case_key = f'case{case}'
                    if case_key in output_format:
                        return output_format[case_key]
                    else:
                        # Fallback to case1 if specified case doesn't exist
                        return output_format.get('case1', output_format)
            
            return output_format
        

    @abstractmethod
    def evaluate(self, input: InputType, context: Context) -> JudgeResult:
        """
        Evaluate agent performance and return a judge result.
        
        Args:
            input: Agent step result to evaluate
            context: Evaluation context with noise type, golden trajectory, etc.
            
        Returns:
            JudgeResult with score, confidence, reason, and additional info
        """
        pass

    def get_judge_role(self) -> str:
        """
        Return the role identifier for this judge.
        
        Returns:
            Judge role string (e.g., "safety", "trajectory")
        """
        return self.judge_role
