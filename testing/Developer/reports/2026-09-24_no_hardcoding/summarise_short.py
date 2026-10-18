"""Prints one line per short-question run from live_check_short's log lines."""
import json
import sys

for line in sys.stdin:
    if not line.startswith("{"):
        continue
    record = json.loads(line)
    if "attempt" in record:
        options = record.get("options") or []
        print(record["question"], record["attempt"], "asked_back=", record["asked_back"], "|", options[:4])
    else:
        print("SHORT", record)
