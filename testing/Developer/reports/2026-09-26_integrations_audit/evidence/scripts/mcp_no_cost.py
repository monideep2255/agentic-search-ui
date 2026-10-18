"""MCP checks that start no run: the printed config as-is, tool listing, and
argument rejection. Auth and argument validation both happen before a run is
created, so none of these spends a question."""
import json

import live_lib as L

# 1. Exactly the printed config: URL only, no headers. Initialize + list tools,
#    then one tool call, which must fail on auth before any run starts.
printed = L.mcp_session(None, [("ask_biomedical_question", {"query": "Which diseases are associated with BRCA1?"})])
L.save("mcp_01_printed_config_no_token", printed)
print("printed config:", json.dumps({k: printed[k] for k in ("server_info", "protocol_version", "prompts_resources")}))
print("tools:", [t["name"] for t in printed["tools"]])
print("input schema:", json.dumps(printed["tools"][0]["input_schema"])[:900])
print("call without token:", json.dumps(printed["calls"][0])[:600])

# 2. With a bearer token: plain_language (the web's default mode) and an
#    unknown argument. Both are argument validation, before a run.
tok = L.token("b")
rej = L.mcp_session(tok, [
    ("ask_biomedical_question", {"query": "Which diseases are associated with BRCA1?", "audience_depth": "plain_language"}),
])
L.save("mcp_02_plain_language_rejected", rej)
print("plain_language:", json.dumps(rej["calls"][0])[:600])
