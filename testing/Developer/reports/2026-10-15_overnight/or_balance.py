"""Print OpenRouter credit totals for the project's account, never the key."""

import json
import urllib.request
from pathlib import Path

env = {}
with open(Path(__file__).resolve().parents[4] / ".env") as fh:
    for line in fh:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
names = [k for k in env if "OPENROUTER" in k.upper()]
print("env names:", names)
value = env.get("OPENROUTER_API_KEY") or next((env[k] for k in names if env[k]), None)
req = urllib.request.Request("https://openrouter.ai/api/v1/credits", headers={"Authorization": "Bearer " + value})
with urllib.request.urlopen(req, timeout=20) as r:
    d = json.load(r)["data"]
total, used = float(d["total_credits"]), float(d["total_usage"])
print(f"total_credits={total:.4f} total_usage={used:.4f} remaining={total - used:.4f}")
