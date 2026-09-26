"""Print which model-tier and transport environment names are set, never their secret values."""
import os

from dotenv import load_dotenv

load_dotenv("<repo-root>/.env")
for key in sorted(os.environ):
    if any(s in key for s in ("MODEL", "TIER", "GRAPH_QUERY_URL", "NCBI_API_KEY", "OPENROUTER", "LITELLM")):
        value = os.environ[key]
        if any(s in key for s in ("KEY", "TOKEN", "SECRET")):
            print(key, "= <set, redacted>" if value else "= <empty>")
        else:
            print(key, "=", value)
