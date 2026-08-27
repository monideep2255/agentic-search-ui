# Build phase 4.13: durable cross-reload search history

Branch: `phase/4.13-durable-history`
Depends on: 4.6 (the `interactions` substrate), merged 2026-08-21 as PR #54
Opened: 2026-08-27
Status: OPEN

Inserted on the board 2026-08-21 by product-owner decision to settle a scope conflict rather than leave it: `frontend/src/stubs/registry.ts` named build phase 4.6 as history's owner in two notes written by build phases 4.8 and 4.10, while Section 25's row for 4.6 never named history as a deliverable. Section 25 does not contain this phase.

## Table of contents

- [What this phase is for](#what-this-phase-is-for)
- [What the substrate already provides](#what-the-substrate-already-provides)
- [The scope boundary, decided before any ticket](#the-scope-boundary-decided-before-any-ticket)
- [The critical this phase can ship, named before it is written](#the-critical-this-phase-can-ship-named-before-it-is-written)
- [Tickets](#tickets)
- [Findings](#findings)
- [Coverage: what this phase does not cover](#coverage-what-this-phase-does-not-cover)
- [History](#history)

## What this phase is for

A person asks a question, closes the browser, comes back, and their searches are gone. Today the rail's items are React state in `frontend/src/App.tsx` (`const [history, setHistory] = useState(...)`, line 166) and nothing reads them back. Build phase 4.6 built the substrate that makes them durable and stopped there: rows exist, they are owner-scoped, and nothing queries them.

This phase adds the read path and the UI that renders it.

## What the substrate already provides

Read rather than assumed, before any ticket was written:

- `interactions` carries `owner_id`, the exact namespaced principal (`user:<uuid>` or `guest:<uuid>`), added by alembic 0008 for F-4.6-01. It is `NULL` on any row written before that column existed.
- `feedback/writer.py`'s `_caller_owns_row` is the ownership check this phase copies: one direct `row.owner_id == owner_id` compare, plus a `is not None` guard so a pre-migration row is refused rather than guessed at. It reads the fact, not a proxy for it.
- `reassign_interaction_owner` already re-points a guest's captured rows to an account on sign-in, so "your searches move with you" needs no new mechanism here.
- `Principal.owner_id` is already on every authenticated request (`get_caller`), and `GET /v1/allowance` is the shape a new owner-scoped GET follows.

## The scope boundary, decided before any ticket

The `interactions` row stores no answer narrative. It carries `query_text`, `citations`, `trust_signal`, `rubric_outcome`, `query_class`, timings and cost, and no synthesised text (`feedback/contracts.py`, `InteractionRow`).

So this phase makes the LIST of past questions durable, not the answers. Clicking a restored item re-asks the question, which is exactly what the rail already does for a live item today. Persisting answer text is a new column, a new migration and a retention decision about storing generated biomedical prose, none of which this phase's board row asked for. Recorded as decision D-4.13-01 rather than silently narrowed.

## The critical this phase can ship, named before it is written

Build phase 4.5 already shipped this exact defect once: every guest shared one ownership identity because `user_id` is `NULL` for a caller with no account, so any anonymous caller could read and overwrite any other guest's session memory. A read path over `interactions` is the same shape with a wider blast radius, because it returns a list of other people's questions rather than one memory envelope.

The rule for every ticket here: scope by `owner_id`, exact string equality, in the SQL. Never by `user_id`, never by `session_id`, never by a derived or "equivalent" identity.

## Tickets

| Ticket | Deliverable | Files it may touch | Acceptance criteria | Status | Owner |
|--------|-------------|--------------------|---------------------|--------|-------|
| T-4.13-01 | The owner-scoped read function over `interactions` | `src/system_03_search_agent/feedback/history.py` (new), `tests/system_03_search_agent/feedback/test_history.py` (new) | `list_history(owner_id, limit)` filters on `Interaction.owner_id == owner_id` in the SQL with a real `LIMIT`, never a Python slice; orders `created_at DESC, id DESC` so the order is total and stable; refuses an empty or over-long `owner_id` rather than querying; a `NULL`-`owner_id` row is never returned; no f-string or `.format()` in any query; type hints on every signature | todo | |
| T-4.13-02 | `GET /v1/history`, the endpoint | `src/system_03_search_agent/adapters/web_sse/app.py`, its response model beside the other adapter models, `tests/system_03_search_agent/adapters/` | Pydantic response model with `max_length` on every string and `max_items` on the list, per the multi-agent pipeline gate; `limit` validated `ge=1, le=50`, default 20; 401 with no token; accepted for both a guest and an account principal; two principals in one database never see each other's rows; the error message on a rejected limit says what to send instead | todo | |
| T-4.13-03 | The frontend read and render | `frontend/src/lib/api.ts`, `frontend/src/App.tsx`, `frontend/src/components/answer/FollowUp.tsx` | `fetchHistory` typed like its siblings; the rail is seeded once a principal exists and again after sign-in; a run taken this session is not duplicated by its own captured row on the next fetch; clicking a restored item re-asks it; the empty state no longer claims searches only last "in this session"; a failed or 401 fetch leaves the live list on screen rather than blanking the rail | todo | |
| T-4.13-04 | The premise gate, written before the builders and watched failing | `tests/system_03_search_agent/adapters/test_phase_4_13_premise.py` (new) | Every arm carries a populate-check that can tell the control holding from nothing having happened; arms cover cross-principal isolation for two guests and two accounts, the `NULL`-`owner_id` refusal, durability across a fresh client with the same token, the guest-to-account handover, and the limit bound; the file states its own coverage and what it deliberately omits | todo | lead |
| T-4.13-05 | Tests for what shipped | `frontend/src/*.test.tsx`, `frontend/e2e/` | Vitest covers seed, merge-without-duplicate, and the degraded-fetch path; a browser test proves the reload path if the e2e mock can reach it, and says so explicitly if it cannot rather than asserting a weaker thing quietly | todo | |
| T-4.13-06 | Docs and the record | `frontend/src/stubs/registry.ts`, `DECISIONS.md`, `tracker/BOARD.md`, `LEARNINGS.md` | The `history` stub entry becomes real, with the answer-not-restored boundary stated rather than dropped; both decisions logged; the board row closed with evidence | todo | |

## Findings

| ID | Raised by | Severity | Description | State | Reason | History |
|----|-----------|----------|-------------|-------|--------|---------|

## Coverage: what this phase does not cover

Stated here so a gap is arguable rather than invisible:

- Answers are not restored, only questions. See the scope boundary above.
- No pagination. The rail in `docs/build/design/design-system/prototype/app.html` is a flat scrolling list with no "load more" control, so the read path is capped at 50 rows and a person with more than 50 searches sees their 50 most recent. A cursor is a UI change first and a backend change second.
- Capture is best-effort by Section 16's own requirement, so a run whose capture row failed to write will not appear after a reload. This phase does not change that and does not disclose it in the UI.
- The rail is only rendered for a signed-in account (`railAvailable = signedIn && ...`, `frontend/src/App.tsx`), matching the prototype. The endpoint is still scoped for a guest principal, because the isolation property must hold whether or not any UI calls it.

## History

- 2026-08-27: phase opened, branch cut, six tickets decomposed. Substrate read first: `interactions.owner_id`, `_caller_owns_row`, `reassign_interaction_owner`, `get_caller`.
