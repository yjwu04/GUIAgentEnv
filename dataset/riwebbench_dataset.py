import os
import json
from typing import Dict, Any, Iterator, List
from .base_dataset import BaseDataset

class RiWebBenchDataset(BaseDataset):
    """
    Loads website scenarios for RiWebBench benchmark.
    Each scenario is a dict with metadata and content.
    """
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.scenario_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
        self.scenarios = [self._load_scenario(f) for f in self.scenario_files]

    def _load_scenario(self, filename: str) -> Dict[str, Any]:
        with open(os.path.join(self.data_dir, filename), 'r') as f:
            return json.load(f)

    def __len__(self) -> int:
        return len(self.scenarios)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        return self.scenarios[idx]

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        return iter(self.scenarios)

    def list_scenarios(self) -> List[str]:
        return self.scenario_files
