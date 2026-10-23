"""Print the local model key's usage in dollars, never the key itself.

Usage: ASU_ENV_FILE=<path to the .env> python key_usage.py
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

env: dict[str, str] = {}
for line in Path(os.environ["ASU_ENV_FILE"]).read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.strip().strip('"').strip("'")

request = urllib.request.Request(
    "https://openrouter.ai/api/v1/key",
    headers={"Authorization": "Bearer " + env["OPENROUTER_API_KEY"]},
)
with urllib.request.urlopen(request, timeout=20) as response:
    data = json.load(response)["data"]
print(json.dumps({"usage_usd": data.get("usage")}))
