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

### 5. Shell allowlist bypass via quoted single-segment commands

User request: "Let the agent run git, python, ssh, and curl commands without prompting"

This repo's actual `.claude/settings.json` uses prefix-match allow rules, among others:

```json
"permissions": {
  "allow": [
    "Bash(git:*)",
    "Bash(python:*)",
    "Bash(python -c:*)",
    "Bash(ssh:*)",
    "Bash(curl:*)"
  ]
}
```

Wrong assumption:
- "`Bash(git:*)` only lets the agent run git commands, so a chained command like `git status && rm -rf /` will silently execute because the string starts with `git`."

Correction:
- The permission engine evaluates a Bash command per shell segment, splitting on `&&`, `||`, `;`, `|`, `&`, and newlines, and deny beats allow. `git status && rm -rf /` is two segments: `git status`, which matches the `Bash(git:*)` allow rule, and `rm -rf /`, which matches no allow rule and is also caught outright by this repo's `.claude/hooks/block-bash-delete.sh` hook. The command falls to an interactive ask, or a hard block, not silent execution. A visibly chained destructive command is not the residual risk here.

The real residual risk:
- A destructive command hidden inside a single subcommand's quoted argument. That whole invocation is one segment, with no `&&`, `||`, `;`, `|`, `&`, or newline for the engine to split on, so it rides through on a broad allow rule that only checks the leading token, and it evades a naive rm-detecting hook, because the `rm` sits inside a quoted string, not after a bare separator.
- `Bash(ssh:*)` allows `ssh some-host "rm -rf /important/data"` outright. The destructive command lives inside the double-quoted remote-command argument passed to the remote shell. To the permission engine this is one segment starting with `ssh`.
- `Bash(python:*)` and `Bash(python -c:*)` allow `python -c "import os; os.system('rm -rf ~')"`. One segment, starts with `python`, matches. The destructive call is inside the quoted `-c` argument.
- The same shape applies to any allowed program that can take an arbitrary string to execute: `bash -c "..."`, `sh -c "..."`, `perl -e "..."`, `osascript -e "..."`.
- `.claude/hooks/block-bash-delete.sh` matches `rm` or `rmdir` only at the start of the command string or immediately after a bare `;`, `&`, or `|` character. It is a plain-text regex over the whole command, not a shell parser, and it does not look inside single or double quotes. In `ssh host "rm -rf ..."` and `python -c "...os.system('rm -rf ~')..."`, the character immediately before `rm` is a quote, not the start of the string or a bare separator, so the hook's pattern does not match and the command passes through.

Correct posture:
- Pair every narrow allow rule with an explicit deny list for the specific destructive commands and constructs. Deny beats allow in the permission engine, so the deny entries are the load-bearing control, not the prefix allow rule or the hope that chaining gets caught.
- Extend the rm-detecting hook, or add a new one, to scan the full command string for destructive patterns including inside single and double quotes, not only at the start of the string or after a bare separator. Closing the `ssh ... "rm -rf ..."` and `python -c "...rm -rf..."` gap needs a quoted-argument scan, which `block-bash-delete.sh` does not do today.
- Treat any Bash allow rule for a program that can execute an arbitrary string argument (`ssh`, `python -c`, `bash -c`, `sh -c`, `perl -e`, `osascript -e`) as higher risk than a program that only takes flags and file paths (`ls`, `cat`, `wc`). Scope those allow rules narrower, or require a quoted-argument-aware hook before broadening them.

The test: does my code pass user input directly to Cypher, SQL, HTTP responses, URLs, or log messages without sanitization, and does my shell allowlist or hook scan inside quoted subcommand arguments, not just the leading token and top-level chain operators?
