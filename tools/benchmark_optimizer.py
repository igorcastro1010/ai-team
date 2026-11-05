"""Run with the repository's Python venv. No credentials, models or remote services."""

import json

from ai_team.optimizer_benchmark import run_benchmark

if __name__ == "__main__":
    print(json.dumps(run_benchmark(), ensure_ascii=False, indent=2))
