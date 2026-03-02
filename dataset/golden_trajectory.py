from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from agents.agent_base import ActionType, AgentStepResult
import json

'''
这里定义了一个GoldenTrajectory类，用于辅助标注测试用例的黄金轨迹，其格式将持续更新。
'''


@dataclass
class GoldenTrajectory:
    """
    A class to store the golden trajectory for a test case (updating)
    """
    task_id: str
    website: str
    noise_type: str
    noise_name: str
    steps: List[AgentStepResult]
    
    # Optional fields for additional metadata
    golden_output: Optional[List[str]] = None
    unsafe_flags: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for serialization"""
        return {
            "task_id": self.task_id,
            "website": self.website,
            "noise_type": self.noise_type,
            "noise_name": self.noise_name,
            "steps": [step.__dict__ for step in self.steps],
            "golden_output": self.golden_output or [],
            "unsafe_flags": self.unsafe_flags or []
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GoldenTrajectory':
        """Create GoldenTrajectory from dictionary"""
        steps = []
        for step_data in data.get("steps", []):
            # Create AgentStepResult from dict
            step = AgentStepResult(**step_data)
            steps.append(step)
        
        return cls(
            task_id=data["task_id"],
            website=data["website"],
            noise_type=data["noise_type"],
            noise_name=data["noise_name"],
            steps=steps,
            golden_output=data.get("golden_output"),
            unsafe_flags=data.get("unsafe_flags")
        )
    
    @classmethod
    def from_json_file(cls, file_path: str) -> 'GoldenTrajectory':
        """Create GoldenTrajectory from JSON test case file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract website from instruction if not provided
        website = data.get("website", "unknown")
        if "[website]" in data.get("instruction", ""):
            # Try to infer website from filename or other context
            import os
            filename = os.path.basename(file_path)
            website = filename.replace(".json", "").lower()
        
        # Convert golden_trajectory steps if they exist
        steps = []
        for step_data in data.get("golden_trajectory", []):
            if isinstance(step_data, dict):
                # Ensure all required fields exist with defaults
                step_dict = {
                    "input": step_data.get("input", ""),
                    "action": step_data.get("action", "none"),
                    "output": step_data.get("output", ""),
                    "status": step_data.get("status", "ok"),
                    "observation_before": step_data.get("observation_before", {}),
                    "observation_after": step_data.get("observation_after", {}),
                    "action_result": step_data.get("action_result", {}),
                    "unsafe_flags": step_data.get("unsafe_flags", []),
                    "tool_name": step_data.get("tool_name"),
                    "t_start": step_data.get("t_start"),
                    "t_end": step_data.get("t_end")
                }
                step = AgentStepResult(**step_dict)
                steps.append(step)
        
        return cls(
            task_id=data.get("id", "unknown"),
            website=website,
            noise_type=data.get("noise_type", "none"),
            noise_name=data.get("noise_name", "clean"),
            steps=steps,
            golden_output=data.get("golden_output", []),
            unsafe_flags=data.get("unsafe_flags", [])
        )

