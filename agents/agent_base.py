from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional


@dataclass
class AgentStepResult:
    """
    A normalized per-step snapshot:
      - input:             textual instruction or synthesized subgoal
      - observation_*:     environment observations before/after the action
      - action:            coarse-grained action type ("tool" for generic tool-call)
      - action_result:     structured result payload (stdout, screenshot path, DOM hash, etc.)
      - output:            assistant surface text for this step (if any)
    This is intentionally generic enough to cover GUI (computer-use), DOM browser-use,
    and pure text reasoning steps.
    """
    # To be modified
    input: str = ""
    observation_before: Dict[str, Any] = field(default_factory=dict)
    action: ActionType = "none"
    action_result: Dict[str, Any] = field(default_factory=dict)
    observation_after: Dict[str, Any] = field(default_factory=dict)
    output: str = ""

    # Optional metadata for logging/metrics
    model: Optional[str] = None
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    status: Literal["ok", "fail", "terminated"] = "ok"
    unsafe_flags: list[str] = field(default_factory=list)
    t_start: Optional[float] = None
    t_end: Optional[float] = None

    def to_event(self, run_id: str, task_id: str, website: Optional[str] = None, noise: Optional[str] = None) -> Dict[str, Any]:
        """Convert to a unified JSONL event row used by our metrics/bench pipelines."""
        return {
            "run_id": run_id,
            "task_id": task_id,
            "website": website,
            "noisea_profile": noise,
            "t_start": self.t_start,
            "t_end": self.t_end,
            "action": self.action,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "status": self.status,
            "unsafe_flags": list(self.unsafe_flags),
            "input": self.input,
            "output": self.output,
            "observation_before": self.observation_before,
            "action_result": self.action_result,
            "observation_after": self.observation_after,
            "model": self.model,
        }


class AgentAdapter(ABC):
    """Interface-like base: multi-step agent wrapper."""

    def init(self) -> None:
        """Reset internal state for a new test case."""
        ...

    def step(self) -> AgentStepResult:
        ...

    def run(self) -> AgentStepResult:
        """High-level loop: until success/stop/timeout."""
        ...


ActionType = Literal["click", "swipe", "type", "tool", "none"]