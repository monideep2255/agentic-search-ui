# Phase 4.2: the CLI adapter, a thin client over the REST plus SSE API

Build phase 4.2 delivers `system3-cli`, command `s3`: a terminal client that constructs no `Query`, calls no `run()`, and contains no agent logic of its own. It speaks HTTP and SSE to the surface build phase 4.0 finalized, and renders the event stream into a terminal. Every guarantee it appears to make (grounding, cite-or-refuse, cost suppression, the trust signal) is already made by the server; this phase adds a renderer and a credential store, and must not add a second, weaker path to any of them.

Depends on: build phase 4.0 (done, PR #39, merged), the only dependency Section 25 names. Also reads build phase 4.10 (done, PR #46, merged), since the guest and allowance refusal shapes are on the wire this client parses.
Branch: `phase/4.2-cli-adapter`
Spec: `requirements/Technical_specification.md` Section 13.3 (the CLI), Section 13.1 (the REST plus SSE endpoints it calls), Section 13.5 (per-surface summary), Section 2.2 (the event envelope), Section 2.7 (the per-surface event table), Section 9.1 (`CitationPayload`, referenced not restated)
Reference: `docs/build/Build_workflow_cadence.md`, `LEARNINGS.md` filtered to adapter, SSE, and premise-gate territory (rows dated 2026-07-28 run lifecycle, 2026-08-01 verify surface, 2026-08-05 gate-bypasses-the-production-path, 2026-07-28 worktree venv)

## Two spec-versus-reality gaps, flagged rather than silently routed around

Both are recorded here before any code, per `.claude/rules/v1-scope-boundary.md`'s instruction to name a substitution rather than quietly make one.

### The "bearer API key" Section 13.3 names does not exist

Section 13.3 says the CLI is "authenticated with the caller's own bearer API key stored at `~/.system3/credentials` (file mode 600)". There is no API-key entity anywhere in the shipped code: no table, no model, no issuance route. Verified by direct read this session, and independently confirmed at build phase 4.1, which hit the identical line in Section 13.2 and recorded the same finding (`tracker/phase_4.1.md`, "Scope boundary, decided rather than asked"). Three credential families exist, all bearer JWTs:

| Credential | Mechanism | TTL | Where it comes from |
|------------|-----------|-----|---------------------|
| Access token | HS256 JWT signed with `AUTH_SECRET`, carries `user_id` | 15 minutes | `POST /auth/login`, `POST /auth/refresh` |
| Refresh token | Opaque `secrets.token_urlsafe(32)`, only its SHA-256 hash persisted | 30 days idle, 90-day absolute chain ceiling | Issued alongside every access token, single-use, rotates on every use |
| Guest token | HS256 JWT on a domain-separated derived key, carries `guest_id` | 7 days | `POST /auth/guest`, the anonymous path, not an authenticated-caller mechanism |

Read the same way build phase 4.1 read it: the caller's "own bearer API key" is the caller's own account authenticating with the bearer-JWT mechanism every other surface already uses. Building an API-key entity to satisfy the sentence literally would be new architecture invented mid-phase, which is exactly what the scope rule exists to stop, and no fast-follow trigger names it.

### `s3 login` is a substitution, not an addition

Section 13.3's command table lists `s3 ask` and `s3 stop` only. It lists no way to get a credential onto the machine, because it assumed an API key the user pastes into a file by hand. With no API-key entity, that path does not exist, and a CLI with no way to obtain a token is a CLI nobody can run. `s3 login` is therefore the substitution for "paste your key", not a new capability: it wraps the already-shipped `POST /auth/login` and writes the resulting token pair to the credential file. Flagged here, and logged to `DECISIONS.md`, rather than added silently.

The access token's 15-minute TTL is what forces the refresh half. A CLI that stored only an access token would stop working fifteen minutes after `s3 login` and require a re-login before nearly every question, so the credential file stores the refresh token and the CLI mints an access token from it. That is not an embellishment of the spec, it is the minimum that makes the stored-credential design in Section 13.3 function at all.

## Phase premise (the done-when)

A user with an account runs `s3 ask "<question>"` against a running server and gets the same cited answer the web UI gets, streamed to stdout as it is produced, with a references block after it naming `source` and `source_url` per marker, and exit code 0. The answer body carries the trust prefix (`[answer]`, `[flag]`, `[ask]`, `[refuse]`) and the inline `[n]` markers match the `marker_ids` the server actually sent, never a client-side renumbering.

The credential it uses is read from `~/.system3/credentials`. The CLI creates that file with mode 600, and REFUSES TO READ IT if the mode is wider than 600, rather than reading it and warning: a credential file another local account can read is already compromised, and continuing normalizes the state the mode exists to prevent.

An expired access token is refreshed transparently and the rotated refresh token is written back BEFORE the retried request is issued. Two concurrent `s3` invocations never both spend the same refresh token, because refresh is serialized by an exclusive lock on the credential file. This is a data-loss bound rather than a nicety: replaying an already-rotated refresh token revokes the user's entire session family server-side, so an unlocked implementation logs the user out of every surface as a routine consequence of running two commands at once.

The stream is opened immediately after run creation, inside the server's 30-second cumulative-unwatched abandonment budget, so the CLI never kills its own run by being slow to attach. Its SSE parser tolerates the wire as the server actually writes it: a `: ping` comment line every 15 seconds is skipped rather than parsed as data; a gap in the `id:` sequence is never treated as a dropped event, because the server strips `cost` events for a non-operator caller while `id:` continues to carry the real envelope `seq`; and `data:` is understood to carry the full `Event` envelope, not a bare payload.

The CLI's retry policy NEVER covers `POST /v1/query`. That endpoint carries no idempotency key, so retrying a timed-out create spends a second allowance slot against a run that may already exist. Retry is confined to the idempotent reads and to `stop`.

A guardrail refusal prints its explanation to stderr and exits nonzero. A fatal `error` prints to stderr and exits nonzero. A non-fatal `error` whose `error_class` is `transient` or `recoverable` does not exit; the retry policy gets its chance first. `done` exits 0 after the references block prints.

Ctrl-C sends `POST /v1/query/{run_id}/stop` before the process exits, so an interrupted session halts the server-side loop instead of leaving it running unseen. A second Ctrl-C during that stop exits immediately rather than hanging.

No cost figure is ever printed for a non-operator credential. The server already stripped `cost` events and zeroed `done.total_cost_usd` before the CLI saw them, so there is nothing left for the CLI to filter; the CLI's own suppression is the second layer, and it holds independently, so a future server-side regression cannot surface a dollar figure through this surface.

The verify surface is `tests/system_03_search_agent/adapters/cli/test_phase_4_2_premise.py`, never a suite total, per `tracker/phase_3.1.md`'s standing rule and LEARNINGS.md's 2026-08-01 row. It drives the real `main()` entry point, with real argument parsing, over the real FastAPI app in-process, and asserts on real captured stdout, stderr, and exit codes. Only `run_streaming` is faked, because the live graph is unreachable from this environment.

### What this gate deliberately does NOT cover

Stated per `.claude/rules/goal-contracts.md`'s coverage-declaration discipline, and per the correction `tracker/phase_4.10.md` recorded when a previous version of one of these sections excused a real gap instead of declaring it.

- Real terminal and TTY behavior: colour, width detection, whether the dim status lines actually render dim. The gate captures streams, not a terminal.
- Non-POSIX file-permission semantics. The mode-600 arms assert POSIX mode bits and are skipped on a platform without them. Windows is not covered and is not claimed.
- A real socket. Every arm runs over `ASGITransport` in-process, per `tests/conftest.py`'s live-HTTP block. Genuine network flakiness, TCP resets, and true mid-stream reconnect against a real server are NOT exercised; the `Last-Event-ID` resume arms drive the resume code path, not a real dropped connection.
- Multi-process concurrency at load. The refresh-lock arm proves the lock serializes two contending in-process attempts; it does not prove behavior across many simultaneous `s3` processes on a loaded machine. That is build phase 6.0's territory.
- Interactive password entry. `s3 login` reads the password from a non-TTY stream in the gate.

## Pre-build source read, done before any ticket

Per this repo's standing pre-build-probe pattern (phases 3.2, 3.3, 3.5, 4.0, 4.1) and `.claude/rules/attack-the-constraint.md`'s "read the input first". Two parallel read-only researchers mapped the surface before this file was written.

| Read | Finding that changes the build |
|------|-------------------------------|
| `adapters/web_sse/app.py` SSE loop | `data:` carries the FULL `Event` envelope (`{type, version, trace_id, seq, ts, payload}`), not the payload. `id:` is the envelope `seq`. `event:` is the event type |
| `sse_starlette` default ping | A comment line `: ping - <timestamp>` every 15 seconds, not a named event. A line-oriented parser must skip `:`-prefixed lines |
| `harness/cost_control.py` `sanitize_event_for_end_user` | `cost` events are DROPPED for a non-operator caller while `id:` keeps the real `seq`, so a non-operator's visible id sequence has gaps by design. A client treating a gap as a missed event would resume-loop forever |
| `app.py` `Last-Event-ID` validation | Must be a request HEADER, no query-param fallback. Strict `\d+` grammar; anything else is a hard 400 before the stream opens. A value above the run's highest `seq` is also a 400 |
| `core/run_registry.py` abandonment | A run with zero attached subscribers for a CUMULATIVE 30 seconds is cancelled server-side. Reconnect churn does not reset the budget. The CLI must attach immediately after create |
| `app.py` `POST /v1/query` | No idempotency key. A retried create spends a second guest or user allowance slot. Retry must never cover this call |
| `auth/router.py` refresh rotation | Single-use, rotating. Replaying a rotated refresh token revokes the ENTIRE session family. Two concurrent CLI refreshes are a full logout, so the credential file needs an exclusive lock, not only mode 600 |
| `app.py` error bodies | Mixed shapes: 429 bodies are structured (`detail: {reason, message}`), while 401/403/404/409 are bare strings (`detail: "..."`). One renderer must handle both without crashing on either |
| `app.py` stop semantics | A stopped run's terminal event is a fatal `error` with `error_class: "cancelled"`, NOT a `done`. Exit-code logic keyed only on `done` would hang on a stopped run |
| `app.py` citations endpoint | 409 if the run has not reached a terminal state. `X-Run-Cancelled` and `X-Citations-Export-Truncated` are response headers, not body fields |
| `tests/conftest.py` | A session-scoped autouse fixture raises on any genuine outbound socket call unless `RUN_PREMISE_GATE=1`. The CLI's HTTP client MUST be injectable so the gate can pass an `ASGITransport` and still exercise the real client code |
| `pyproject.toml` | `[project.scripts]` declares `search-agent = "system_03_search_agent.cli:main"`, a module that does not exist. `[tool.setuptools].packages` lists `.api`, `.agent`, `.models`, `.config`, none of which exist on disk. Both are stale and this phase corrects them |
| `adapters/mcp/server.py` | The auth and error-sanitization precedent: a fixed literal external-facing message per `error_class`, never an interpolated exception string (the F-4.1-A-09 defect). Its in-process `create_run` integration is deliberately NOT the precedent for this phase, which is an HTTP client by design |

## Ticket map

| Ticket | Slice | Files it may touch | Status |
|--------|-------|--------------------|--------|
| T-4.2-01 | The premise gate, blocking. Written and watched failing before any implementation exists, landed in its own commit | `tests/system_03_search_agent/adapters/cli/__init__.py` (new), `tests/system_03_search_agent/adapters/cli/test_phase_4_2_premise.py` (new) | in-review |
| T-4.2-02 | The credential store: read, write, mode-600 creation, refusal to read a wider mode, atomic replace, an exclusive lock around the refresh-and-write critical section, and the rotation write-back ordering | `src/system_03_search_agent/adapters/cli/credentials.py` (new) | in-progress |
| T-4.2-03 | The SSE frame parser and the HTTP client: comment-line skipping, `event:`/`data:`/`id:` assembly, envelope decode into `contracts.events.Event`, `Last-Event-ID` resume, and the four REST calls, each with a declared timeout | `src/system_03_search_agent/adapters/cli/sse.py` (new), `src/system_03_search_agent/adapters/cli/client.py` (new) | in-progress |
| T-4.2-04 | The renderer: all ten of Section 13.3's rendering rules, the stdout/stderr split, the trust prefix, the references block, the exit-code map, and the mixed error-body shapes | `src/system_03_search_agent/adapters/cli/render.py` (new) | in-progress |
| T-4.2-05 | The entry point: `argparse` wiring for `ask`, `stop`, `login`, the run lifecycle that attaches to the stream immediately after create, the Ctrl-C stop-then-exit path, and the retry policy that excludes run creation | `src/system_03_search_agent/adapters/cli/main.py` (new) | in-progress |
| T-4.2-06 | Packaging and records: the `s3` console entry point, correcting the stale `[project.scripts]` and `[tool.setuptools].packages` blocks, the package `__init__.py`, and the two `DECISIONS.md` rows this file's scope section names | `pyproject.toml`, `src/system_03_search_agent/adapters/cli/__init__.py` (new), `DECISIONS.md` | in-progress |

Depends-on chain: T-4.2-01 blocks everything and lands first, alone, per the corrected process F-4.0-J-02 named for future phases. T-4.2-02, T-4.2-03, T-4.2-04 and T-4.2-06 are mutually independent and own strictly disjoint files. T-4.2-05 consumes the three interfaces below and is written against them rather than against finished code, so it runs in parallel with them.

### The interfaces, fixed by the lead before dispatch

Builders write against these signatures. A builder that believes a signature is wrong reports the contradiction rather than changing it unilaterally, per the brief-can-be-wrong lesson build phase 4.10 recorded.

```python
# credentials.py  (T-4.2-02)
CREDENTIALS_PATH: Path                      # ~/.system3/credentials, overridable via S3_CREDENTIALS_PATH
class Credentials(NamedTuple):
    base_url: str
    access_token: str | None
    refresh_token: str
def load() -> Credentials                   # raises InsecureCredentialsError if mode is wider than 600
def store(creds: Credentials) -> None       # atomic replace, mode 600 from creation, never a widen-then-narrow
async def refresh_locked(client, creds) -> Credentials  # exclusive flock for the whole read-refresh-write critical section

# sse.py  (T-4.2-03)
def parse_sse_lines(lines: Iterable[str]) -> Iterator[tuple[str | None, str, str | None]]
    # yields (event_type, data, last_event_id); skips comment lines; never yields on a bare keepalive

# client.py  (T-4.2-03)
class CliClient:
    def __init__(self, http: httpx.AsyncClient, creds: Credentials) -> None
    async def create_run(self, text, session_id, audience_depth) -> tuple[str, str]   # NEVER retried
    async def stream_events(self, run_id, *, last_event_id=None) -> AsyncIterator[Event]
    async def stop(self, run_id) -> bool
    async def fetch_citations(self, run_id) -> list[CitationPayload]

# render.py  (T-4.2-04)
class Renderer:
    def __init__(self, out: TextIO, err: TextIO, *, operator: bool) -> None
    def handle(self, event: Event) -> None
    def finish(self) -> int                 # returns the process exit code

# main.py  (T-4.2-05)
async def async_main(
    argv: list[str],
    *,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    http_client: httpx.AsyncClient,
    interrupt_signals: asyncio.Queue[None] | None = None,
) -> int
def main() -> int                           # sync wrapper: real argv, real streams, real client, real SIGINT
```

`main.py`'s signature was missing from the first version of this table, found by T-4.2-01's builder while writing the gate and adopted here rather than left to a builder to invent. Two seams matter and both are deliberate. `http_client` is injected because `tests/conftest.py` forbids a real outbound socket, so the gate passes an `ASGITransport` and still exercises the real client code end to end. `interrupt_signals` is the Ctrl-C seam: one `put_nowait(None)` per simulated `SIGINT`, so the stop-before-exit path and the second-interrupt path are both testable without sending a real signal to the test runner. `main()` supplies the real argv, the real streams, a real network client and a real `SIGINT` handler, and is what the `s3` console entry point calls.

## Premise gate design

Written and watched failing first, every failure a `ModuleNotFoundError` rather than a network fault or a fixture bug, per LEARNINGS.md's discipline for this repo.

| Arm | What it pins |
|-----|--------------|
| Golden path | The real `main()` with real argv produces a streamed answer on stdout, a references block naming `source` and `source_url`, `[n]` markers matching the server's own `marker_ids`, and exit 0 |
| Refusal path | A zero-retrieval run prints the honest refusal, no fabricated citations, no empty references block presented as if complete, and exits nonzero. This surface never becomes a laxer path to a confident wrong answer |
| Credential mode | A file at 0644 is REFUSED, not read-with-a-warning. A file the CLI creates is 600 at creation, never widened first. Skipped, with a stated reason, on a platform with no POSIX mode bits |
| Refresh rotation | The rotated refresh token is persisted BEFORE the retried request is issued, proven by asserting the on-disk value changed at that ordering point, not merely by the end state |
| Refresh lock | Two contending refreshes serialize; exactly one rotation reaches the server. The mutation that must turn this red: remove the lock and watch both spend the token |
| Abandonment budget | The stream is attached within the server's cumulative-unwatched budget. Mutation: delay the attach past it and watch the run get cancelled underneath the CLI |
| Create is never retried | A create that times out is NOT re-issued. Mutation: add a retry and watch a second allowance slot get spent |
| SSE wire tolerance | A keepalive comment line yields no event. A gap in `id:` yields no resume loop and no "missed event" error. `data:` is decoded as the full envelope |
| Stopped run | A run whose terminal event is a fatal `error`/`cancelled` exits nonzero and does not hang waiting for a `done` that never comes |
| Ctrl-C | `SIGINT` sends stop before exit. A second `SIGINT` during the stop exits immediately |
| Error-body shapes | A structured 429 body and a bare-string 401 body both render without crashing, and both carry an actionable next step per `tool-call-budgets` |
| Never cost, two layers | A non-operator run prints no dollar figure. Separately, a hand-injected `cost` event and a non-zero `done.total_cost_usd` reaching the renderer with `operator=False` still print nothing, so the CLI's own suppression holds independently of the server's |
| `s3 stop` as its own command | The subcommand stops a run the caller owns and exits 0; stopping an already-finished run also exits 0, since the endpoint is idempotent by contract and a CLI that treated the second call as an error would contradict it; stopping a run owned by someone else renders the 403 and exits nonzero |
| `s3 login` | A successful login writes BOTH tokens to a file created at mode 600, and the password never appears in argv, in any rendered output, or in an error message on a failed attempt. A failed login leaves any pre-existing credential file byte-unchanged rather than truncating it |

The last two arms were absent from the first version of this table, found by T-4.2-01's builder when it observed that T-4.2-05 must build `stop` and `login` while no arm pinned either. Recorded as a correction rather than quietly added, because the omission is the same shape as the defect the gate exists to catch: a phase where every ticket is individually satisfied and the phase premise is not. The `login` arm's password clause is the one genuinely new risk this phase introduces, since no other surface in this repository ever handles a plaintext password outside the auth router itself.

Every clause is mutation-proven before it counts as green, per the five separate ways build phase 4.10 measured a green clause pinning nothing. For each, the mutation that turns it red is named in the test file beside the clause, run, and confirmed to have reached the code path.

## Findings

The adversary and judge rounds file here. Single writer per state: the finder files, the judge or a fix agent triages, only the designated closer closes, and the raiser never closes its own item.

| Finding | Severity | Raised by | State | Detail |
|---------|----------|-----------|-------|--------|
| F-4.2-01 | minor | lead, at merge | open | `stream_events` does not itself stop on a fatal `error`. It yields every event and ends when the HTTP response body ends, relying on the server's own `subscribe()` terminating the stream on `done` or a fatal error. That behaviour is real (`core/run_registry.py`), so the CLI does end on a stopped run today, and the 45-second stream read timeout is a second backstop. But the guarantee is now the SERVER's rather than the client's, where the brief asked for it locally, so a future server change that held the connection open past a fatal error would hang the CLI rather than fail it. The gate's `TestStoppedRun` arm is what decides whether this is acceptable as built; the judge must confirm that arm genuinely exercises a stopped run end to end rather than passing on a stream that happened to close for another reason |
| F-4.2-02 | minor | lead, at merge | open | The lead's fixed-interface table gave `refresh_locked` as synchronous when it issues an HTTP call and is invoked from async code, so it could never have been. Corrected in this file and pushed to T-4.2-05 before that builder consumed it. Recorded rather than quietly amended, because it is the second brief error this phase, after the missing `main()` signature, and two in one phase is a pattern about how the briefs were written rather than two unrelated slips |
| F-4.2-03 | minor | T-4.2-04 builder | open | Section 13.3 asks for the `think` and `plan` status lines to be "prefixed with the persona name", and there is no persona name to read. Neither `ThinkPayload` nor `PlanPayload` carries the field, and `RequestContext` does not either. `persona_name` is returned once by `POST /v1/query` and never repeated on an event. Section 12.7 of the technical specification ALREADY flags this same gap for the web UI and explicitly leaves it for Section 2 or 13 to resolve, so this is a second surface hitting a known unresolved contract question rather than a new defect. Rendered without the prefix. Closing it means either putting `persona_name` on the two payloads or threading the create-run response value down into the renderer, and both are contract decisions above this phase |
| F-4.2-04 | minor | T-4.2-04 builder | open | Section 13.3 asks for the trust signal as "a one-line prefix on the answer body" while also requiring `token` events to print live as the answer grows. Those cannot both hold: the answer-scope outcome is not known until the claims resolve, so a genuine prefix would mean buffering the entire answer and destroying the streaming the same section requires. Resolved by printing the outcome as its own stdout line when the answer-scope `trust_signal` arrives. A product-owner call on which of the two Section 13.3 sentences wins, not a defect to fix unilaterally |
| F-4.2-06 | MAJOR | the gate itself, first integrated run | fix dispatched | `TestGoldenPath` asserted `err.strip() == ""`, that stderr is EMPTY on a successful run. Section 13.3 REQUIRES the opposite: `think` and `plan` render as dim status lines to stderr, and `tool_start`/`tool_result` as one dim line per call. The renderer does exactly what the spec says and the clause demanded the reverse. The danger is not the red test, it is the repair a builder would reach for: satisfying this clause means DELETING the status lines Section 13.3 requires, which turns the gate green while making the product worse. Being replaced with a strictly stronger clause asserting the stream SPLIT, that stdout carries the answer, the trust line and the references and nothing else, and that the status lines are on stderr and absent from stdout, which is the property that actually makes `s3 ask > answer.txt` work |
| F-4.2-07 | MAJOR | the gate itself, first integrated run | fix dispatched | `TestStoppedRun` dies with `AttributeError: '_io.StringIO' object has no attribute 'strip'`, a call-site bug introduced when `_run_ask_main` was refactored into `_run_generic_main` while adding arms 13 and 14. The arm crashes before evaluating a single assertion, so IT HAS NEVER RUN. It is also the only thing that verifies F-4.2-01, so whether the CLI actually terminates on a stopped run rather than hanging is unverified as of this moment. The fix must bound the arm with an explicit timeout so a hang fails loudly and fast instead of stalling the suite, and must be mutation-proven to be capable of failing at all |
| F-4.2-08 | MAJOR | the gate itself, first integrated run | fix dispatched | A genuine ticket-boundary integration break, and the only one of these three that is a code defect. `render.render_client_error` (T-4.2-04) dispatches on `httpx.HTTPStatusError`, `httpx.TimeoutException` and `httpx.HTTPError`. `client.py` (T-4.2-03) raises its own typed hierarchy instead: `AuthExpiredError`, `ForbiddenError`, `NotFoundError`, `ConflictError`, `RateLimitedError`. None are `httpx` types, so every one falls through to the generic fallback and a rate-limited caller is told "the request failed unexpectedly. Try again." while the server had sent curated copy naming the actual remedy. Both builders satisfied their own ticket; the seam between them was never wired, which is the same shape as build phase 2.0's `build_stable_prefix()` shipping with zero callers. Violates `tool-call-budgets`'s actionable-error rule |
| F-4.2-05 | MAJOR | T-4.2-04 builder, about the gate | open | The gate's trust-prefix clause asserts SUBSTRING MEMBERSHIP, not position, so it passes whether the outcome line precedes the answer or follows it. The builder found this while resolving F-4.2-04 and said so plainly: "the premise gate only asserts substring membership, not position, so this satisfies it either way." That is a clause that cannot distinguish the two behaviours it exists to choose between, which is this repository's single most repeated failure class and the exact shape build phase 4.10 measured five separate ways. Whichever way F-4.2-04 is decided, this clause must be rewritten to assert POSITION and then mutation-proven by rendering the other order and watching it turn red. Raised by the builder; a different party fixes and closes it, per the finder-is-not-the-closer rule |

## History

- 2026-08-16: phase opened on `phase/4.2-cli-adapter`. Two parallel read-only researchers mapped the REST surface and the auth, packaging and test conventions before this file was written. Two spec-versus-reality gaps recorded rather than routed around.
- 2026-08-16: T-4.2-01 landed as its own commit (459f06a), 20 tests across twelve arms, every one failing with `ModuleNotFoundError` and nothing else. Its builder reported two gaps in the lead's brief rather than building around them: the missing `main()` signature and the two commands no arm pinned.
- 2026-08-16: T-4.2-01 expanded to 27 tests across fourteen arms (77c8201), adding `s3 stop` and `s3 login`, still failing with exactly one distinct error.
- 2026-08-16: T-4.2-06 merged. Two pre-existing packaging defects corrected: a console entry point that had never worked, and a package list carrying four phantom packages while omitting eight real ones including both existing adapters.
- 2026-08-16: T-4.2-02 merged. Its builder found and fixed a deadlock hazard during the build, an `fcntl.flock` acquired inline across an `await` blocking the event-loop thread against its own waiter, and reported the `refresh_locked` signature error (F-4.2-02).
- 2026-08-16: T-4.2-03 merged, 33 unit tests. Deviation from the brief on stream termination filed as F-4.2-01 rather than accepted silently.
