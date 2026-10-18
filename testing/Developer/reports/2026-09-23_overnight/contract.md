# The overnight run: wire contract, pinned before any worker starts

Night of 2026-09-22 into 2026-09-23. The product owner approved the plan and
went to sleep. This file is the contract five parallel workers build against.
It is pinned before any of them starts and none of them edits it.

Method is the one that closed G-035 the same night: measure first, pin the wire
contract, fan out on non-overlapping files, verify live, fix what only the live
run shows.

## What lands by morning

| Item | What a person notices | Owner |
|---|---|---|
| 11.30 fix B | The MCP address the Integrations page prints never redirects an HTTPS request to plaintext | Planner writes, worker A checks |
| 10.2 | Clicking a past search shows the answer it gave at once, with a Run again button | Workers B1 and B2 |
| D4 | The developer's quick check before a push can be trusted | Worker C |
| 11.29 | A measured scoping document on hard and soft edges, for the product owner to read, NOT a build | Worker D |

## The standing rules every worker runs under

- Fixes land on develop directly, no branch, no judge round. The product
  owner's retest is the verification. Anything under `.claude/` is OUT OF SCOPE
  for every worker tonight; it needs a branch and a pull request.
- No co-author trailers on commits.
- Decide from the user's chair (`.claude/rules/decide-from-the-users-chair.md`)
  and report the decision in the words the person typing the question would use.
- An arm that cannot distinguish the control holding from nothing happening is
  not an arm. Every bound test carries a populate check.
- Write a finding the moment it is established, before doing anything else with
  it (`.claude/rules/self-eval-loop.md`). Findings go in
  `testing/Developer/reports/2026-09-23_overnight/findings.md`, appended, never
  rewritten.
- BLOCKED-STOP: any worker that would cross the v1 scope boundary, change a
  locked document, or needs a product-owner decision STOPS, writes the finding,
  and reports. A blocked stop is a clean end state, not a failure.

## Worker A: the MCP scheme downgrade (11.30 fix B)

Owns: `tests/system_03_search_agent/adapters/web_sse/test_proxy_scheme.py` (new),
`railway.json`. READS `src/system_03_search_agent/adapters/web_sse/proxy_scheme.py`
and `app.py` and NEVER edits either; a defect found in them is a finding, not an edit.

The mechanism, established before the build rather than guessed. Railway
terminates TLS at its edge and forwards plain HTTP to the app with
`X-Forwarded-Proto: https`. Uvicorn's proxy-header handling is on by default but
`--forwarded-allow-ips` defaults to `127.0.0.1`, and Railway's proxy is not
127.0.0.1, so the header is ignored, the ASGI scope keeps `scheme: "http"`, and
Starlette's mount redirect builds an absolute `Location` from that scheme. A
POST to `/mcp` therefore answers `307` with `location: http://...`.

THE DECISION THE PLANNER TOOK, and why it is narrower than the obvious fix.
The obvious fix is `--forwarded-allow-ips='*'`, and it is REJECTED. That switch
also makes uvicorn rewrite the client address from `X-Forwarded-For`, and
uvicorn takes the LEFTMOST entry, which the caller controls. `auth/router.py`
lines 284 and 314 hash the client address for the sign-in rate limit, and
`data/guest_sessions.py` binds a guest session to it. So the one-flag fix would
hand any caller a way to forge their address and walk past the sign-in rate
limit. Fixing a plaintext redirect is not worth opening a rate-limit bypass.

So the scheme is trusted and the address is NOT. `proxy_scheme.py` is a pure
ASGI middleware that reads `x-forwarded-proto`, accepts only the exact values
`http` and `https`, takes the FIRST entry when the header is a comma-separated
list, sets `scope["scheme"]`, and touches `scope["client"]` never.

A separate finding, recorded and NOT acted on tonight because it is the product
owner's call: because the address is not rewritten, every caller behind the
proxy shares one address today, so the per-address sign-in rate limit is
effectively global rather than per person. That is pre-existing, unchanged by
tonight's fix, and fixing it properly needs the trusted-hop count, which is a
deployment fact to confirm rather than a value to guess.

Done when:
- Arms proving the redirect's `location` is `https` when `x-forwarded-proto:
  https` is present, and that it is unchanged when the header is absent.
- Arms proving `scope["client"]` is IDENTICAL with and without
  `x-forwarded-for` present, so the rate-limit identity provably did not move.
  This arm is the point of the whole design and must be red if the middleware
  ever starts trusting the address.
- Arms for the hostile shapes: `x-forwarded-proto: HTTPS` (case), a list
  (`https, http`), an unknown value (`ftp`, ignored), an empty header.
- Every arm carries a populate check.
- `railway.json`'s start command is UNCHANGED and the reason is written in the
  test module's docstring: the fix is in the app, deliberately, so it travels
  with the code rather than living in a deployment setting nobody reads.

## Workers B1 and B2: history shows the saved answer (10.2)

The product owner approved the data decision on 2026-09-22: store the answer
for SIGNED-IN ACCOUNTS ONLY, never for guests, and delete it with the account.

### The wire contract between B1 and B2, pinned so both can build at once

Additive within v1 per `system-design-patterns` pattern 10.

`GET /v1/history` keeps every field it has and gains ONE:

```
has_saved_answer: bool
```

New endpoint, `GET /v1/history/{trace_id}/answer`, owner-scoped exactly as the
list is:

```
200  {"trace_id": str, "question": str, "asked_at": ISO-8601 str,
      "depth": "plain" | "researcher", "answer_markdown": str,
      "citations": [ ...the citation shape the answer screen already renders... ],
      "trust_signal": str}
404  when the row is not the caller's, does not exist, or holds no saved answer.
     The three are INDISTINGUISHABLE to the caller, deliberately: a 403 for
     someone else's row confirms that row exists.
```

### Worker B1, the backend. Opus.

Owns: `alembic/versions/0010_*.py` (new), `data/models.py`,
`feedback/contracts.py`, `feedback/capture.py`, `feedback/history.py`,
`adapters/web_sse/app.py`, and their tests. Owns `app.py` for the whole night;
no other worker edits it.

- Measure first: read `assemble_interaction` (`feedback/capture.py:195`) and
  establish from the EVENT LIST what the finished answer text and its citations
  actually are on a real run, before designing a column. Do not assume an event
  name. If the answer text cannot be reconstructed faithfully from the events,
  that is a blocked stop: write the finding and say so, do not store an
  approximation.
- Guests are excluded at the WRITE, not at the read. The row is written with
  answer text only when `owner_id` starts with `user:`. A read-side filter would
  leave guest answers on disk, which is not what the product owner approved.
- DELETED WITH THE ACCOUNT is a requirement, not a hope, and the existing
  foreign key does NOT deliver it: `interactions.user_id` is `ON DELETE SET
  NULL` (`data/models.py`), so a deleted account leaves its rows behind with a
  null user. Establish whether an account can be deleted at all today. If it
  can, the answer columns must be cleared on that path and an arm must prove it.
  If it cannot, write that finding plainly and leave a named, tested function
  that clears them, so the delete path cannot ship later without it.
- Bound the stored text the way every other string in this system is bounded,
  and say in the migration's docstring which bound and why.
- The migration carries a rollback plan and an expand-contract note, per
  `production-standards`.

Done when: the migration applies and rolls back cleanly on a real database, a
signed-in run stores its answer, a guest run provably stores NOTHING, the two
endpoints answer as the contract above says, the 404 is indistinguishable across
all three causes, and every arm carries a populate check.

### Worker B2, the frontend. Sonnet.

Owns: `frontend/src/App.tsx`, the history rail components it renders, and the
frontend tests for them. Touches NOTHING under `src/system_03_search_agent/`.

Today `onOpen` (`App.tsx:1879`) re-asks the question, and the comment above it
says re-asking is the only truthful option available. That comment becomes false
tonight and must be REPLACED, not left: it is exactly the confident sentence
that stops the next reader looking.

From the person's chair: they click a past search and the answer they already
got is there at once, with no wait and no second search charged to them. A "Run
again" button next to it asks fresh, which is the current behaviour, kept.

- Build against the pinned contract above. The endpoint may not exist yet while
  you work; that is expected. Do not wait for it and do not mock away the
  contract's shape.
- `has_saved_answer` false, or the fetch failing, falls back to today's
  behaviour exactly. Nobody loses a working control because a new one is absent.
- Say on screen that what is shown is the saved answer rather than a fresh one.
  A person who cannot tell the two apart cannot trust either.
- Run again must be reachable by keyboard and carry an accessible name.

Done when: clicking a history item renders the saved answer with no network
search, Run again performs a fresh search, the fallback path is proven by a
test, and the stale comment is gone.

## Worker C: the two test defects (D4). Sonnet.

Owns: `frontend/e2e/journeys/narrow-viewports.spec.ts`, the vitest config and
test setup files, and nothing else. Touches NO file under `frontend/src/`.

Two separate defects, and the second is the one that matters more.

- Journey 7 selects navigation items with `getByRole("link")` when they are
  buttons, inside a `.catch()`, so it has probably never navigated while
  reporting success (`Developer_workflows.md` defect 10). Fix the selector, and
  REMOVE the `.catch()` that hid the failure rather than keeping it with a
  better selector. A swallowed failure is the defect; the wrong role is how it
  got in.
- The suite's result depends on machine load: identical code gave 5 failed on a
  139-second run and 245 passed on a 50-second run (defect 12). DIAGNOSE BEFORE
  FIXING. Name the specific arms that flip and the specific mechanism (a fixed
  timeout, a real timer, an unawaited effect, a shared module-level fixture).
  Raising a timeout is the fix of last resort and every use of it must be named
  in the findings file, because a slower gate that still flips is worse than an
  honest red.

Done when: journey 7 provably navigates, proven by an arm that is RED against
the old selector; the flipping arms are named with their mechanism; and the
suite passes 10 consecutive runs, at least three of them under artificial load.
If the mechanism is in `frontend/src/` rather than in the tests, that is a
blocked stop: write the finding, do not cross into source.

## Worker D: hard and soft edges, the scoping document (11.29). Opus.

Owns `testing/Developer/reports/2026-09-23_overnight/soft_edges_scoping.md` and
no other file. THIS IS A DOCUMENT, NOT A BUILD. Writing code tonight against
this item is a scope violation; the product owner reclassified 11.29 on
2026-09-22 as a discussion that precedes a build.

The bar the product owner set, quoted in the fix plan: not "does it cite" but
"is it worth reading instead of a general chatbot".

Measure before proposing, from what this repository already holds:

- `testing/Developer/reports/2026-09-22_10.3_consistency/`, the 150-run
  consistency measurement over the 50 golden questions.
- `eval/golden/golden_dataset.json`, the 50 questions and what each pins.
- The live graph's own shape: 11 vertex labels and 14 edge predicates.

Answer, with numbers rather than opinion:

- How many of the 50 golden questions are answerable with HARD edges alone,
  that is one or more direct relationships already in the graph. Count them.
- How many genuinely need a path of two or more hops, and name them.
- How many need something the graph cannot express at all, and say what is
  missing rather than which technology is missing.
- Only then, and only for the shapes the counts actually justify, propose the
  mechanism. Vector embeddings, a hybrid model and a RAG pipeline are three
  ANSWERS; the document's job is to establish the QUESTION first. A proposal
  whose motivating count is zero is to be written down as costing nothing to
  skip.

Name what you did not check, per `.claude/rules/goal-contracts.md`: a verify
surface must state its own coverage. Recommend, do not decide; the architecture
call is the product owner's.

## What the planner does after the workers return

- Assemble, then run the gates exactly as CI runs them: `ruff check` with no
  path, `bash .github/gates/gate02_import_order.sh`, `bash
  .github/gates/gate04_unit_suite.sh`, `npm run build` in `frontend/`, and
  `python tracker/check_doc_drift.py --check`. Gate on each exit code, never
  through a pipe.
- Prove each item LIVE on develop after the deploy reaches SUCCESS, since a
  push is not a deploy and local green has never been enough in this repository.
- Write `testing/Shipped_2026-09-23.md` with one numbered retest item per thing
  shipped, each naming the exact query the product owner types and what they
  should see.
- `/phase-checkpoint`, then `/ship`.
