"""
Simple JSON persistence for a user's squad.

Owner: Member 1 (Data & Persistence)
"""

import json
import os
from models import Squad

DEFAULT_PATH = "squad.json"


def save_squad(squad: Squad, path: str = DEFAULT_PATH) -> None:
    with open(path, "w") as f:
        json.dump(squad.to_dict(), f, indent=2)


def load_squad(path: str = DEFAULT_PATH) -> Squad:
    if not os.path.exists(path):
        return Squad()  # empty squad, default £100m budget
    with open(path, "r") as f:
        data = json.load(f)
    return Squad.from_dict(data)
