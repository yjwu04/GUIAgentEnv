from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator

class BaseDataset(ABC):
    """
    Abstract base class for all benchmark datasets.
    """
    @abstractmethod
    def __len__(self) -> int:
        pass

    @abstractmethod
    def __getitem__(self, idx: int) -> Dict[str, Any]:
        pass

    @abstractmethod
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        pass
