# Card 36 diagnosis: a picked "How far back" window is lost after a restart

Base: develop at c916cfa3. Read-only diagnosis, no model calls made.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [The smallest fix](#the-smallest-fix)
- [Overlap](#overlap)
- [Needs the owner](#needs-the-owner)
- [Proposed test query](#proposed-test-query)

## Status today

Still happens. The record is unchanged since the fix round: `git log` on `src/system_03_search_agent/core/clarify.py` ends at fc1ba7bf, and no later commit touches `_OFFERED`.

## What a person sees

- They ask "recent papers on BRCA1" and are offered three windows (12 months, 5 years, 10 years).
- The service restarts (every Railway deploy does this), or an hour passes, or 1024 other sessions are offered windows.
- They click "Recent papers on BRCA1 from the last 10 years?"
- They get papers from any year under a heading that repeats "from the last 10 years". Nothing says the window was not applied.

## The cause

| Part | Evidence |
|---|---|
| Offers live only in process memory | `core/clarify.py:336`: `_OFFERED: OrderedDict[...]`, with `_OFFER_TTL_S = 3600.0` (line 333) and `_MAX_OFFER_SESSIONS = 1024` (line 334). The comment at lines 326 to 330 states a restart loses an offer. |
| A click is only the option text | The web client sends the option string and nothing else (comment, lines 314 to 320). |
| A lost offer reads as no pick | `picked_recent_window` (line 356) returns None when the entry is gone or expired. `_picked_publication_window` (`core/graph.py:3810`) then returns None, so no `[dp]` clause is sent. |
| Nothing is said | The only mention of a window is gated on `publication_window is not None` (`graph.py:6996`, `graph.py:7132`). |

## The smallest fix

Tell the person, honestly, when a click on our own option could not be applied. Keep the search broad, as the fix round chose.

- Add a small helper in `core/clarify.py` that reports whether a question is exactly the shape the product itself generates: it ends with " from " plus one of the three fixed phrases in `RECENT_WINDOW_PHRASES` plus "?". This verifies the product's own fixed strings. It does not classify free text.
- In `core/graph.py` `plan_node`, where the narrative is built (lines 6996 and 7132), when that helper is true and `_picked_publication_window` is None, add "the date range you chose could not be applied, so papers from any year were searched".

| Item | Value |
|---|---|
| File fence | `core/clarify.py` (one helper); `core/graph.py` `plan_node` narrative lines only (two sites). Tests in the clarify and plan tests. |
| Answer path | Yes, lightly: the plan narrative text. The search itself does not change. |
| Dial position | 2, runnable behaviour. |
| Size | S |
| Migration | No. |

Alternative, a design choice: apply the window again from the exact fixed suffix, which needs no stored offer and survives a restart. It would also apply a window a person typed in the same exact words. The fix round removed all text reading on purpose (F-8.2-A07, J01: "in 2000 patients" once limited a search to the year 2000), so this is the owner's call. A third option, storing offers in PostgreSQL, needs a new table and so a migration: owner only.

## Overlap

- `plan_node` narrative lines are near, not inside, phase 8.7's list. 8.7 rewrites `_answer_tokens`, `_write_answer`, `write_node`, `act_node`, `answer_layout.py`, `findings.py` and `decide.py`. No overlap with those.
- No overlap with the guardrail functions.
- Same file as 8.7 (`core/graph.py`), so a rebase may be needed.

## Needs the owner

No for the honest note. Yes only if the owner wants the window to survive a restart: the exact-suffix re-apply is a design choice, and a database table is a migration.

## Proposed test query

Add to section 2 of `testing/Test_queries_and_workflows.md`, after the ask-back "How far back" entry (find it with the phrase "How far back"):

### A picked window that could not be applied says so (card 36)

Queries to try:

- Ask `recent papers on BRCA1`, wait for the three "How far back" choices, then redeploy or restart the service (developer step: restart the local server), then click "from the last 10 years".

What you should see:

- The plan line says the chosen date range could not be applied and that papers from any year were searched.
- The answer heading does not claim a window that was not used.
- Without a restart, the same click still limits to the last 10 years and says so.
- Why it matters: a quiet change to what was searched is worse than an honest one.
