from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from agent_base import AgentStepResult


class BaseStrategy(ABC):
    """Runtime strategy interface for default agent."""

    @abstractmethod
    async def run(self, instruction: str) -> List[AgentStepResult]:
        ...
