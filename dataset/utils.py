import os
import json
from typing import List, Dict, Any

def load_json_scenarios(data_dir: str) -> List[Dict[str, Any]]:
    """
    Loads all .json scenario files from a directory.
    """
    scenarios = []
    for filename in os.listdir(data_dir):
        if filename.endswith('.json'):
            with open(os.path.join(data_dir, filename), 'r') as f:
                scenarios.append(json.load(f))
    return scenarios
