"""Card 145 live runs: load the local environment file and read model spend.

The environment file's path comes from the ASU_ENV_FILE variable, so no
machine path is written here. Values are loaded into this process only and
never printed. Settings are pinned to develop's: Jev classifier, guard and
plan tier deepseek-v4-flash, synth tier glm-5.2, a 25-cent per-question cap.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def load_env() -> None:
    """Read the environment file into os.environ and pin develop's models."""
    for line in Path(os.environ["ASU_ENV_FILE"]).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))
    os.environ.update(
        {
            "LANGCHAIN_TRACING_V2": "false",
            "TOOL_AUDIT_LOG_ENABLED": "false",
            "CLASSIFIER_PROVIDER": "jev",
            "GUARD_MODEL": "deepseek/deepseek-v4-flash",
            "PLAN_MODEL": "deepseek/deepseek-v4-flash",
            "SYNTH_MODEL": "z-ai/glm-5.2",
            "PER_QUERY_COST_CAP_USD": "0.25",
        }
    )
    sys.path.insert(0, str(ROOT / "src"))


def key_usage() -> float:
    """The local key's usage to date in dollars (GET /api/v1/key, data.usage)."""
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"]},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return float(json.load(response)["data"]["usage"])
