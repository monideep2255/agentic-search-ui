# Card 22: every total says what it counts

Build report for card 22, built on `fix/card22-name-every-total` from develop `d8179c4e`. The owner chose option B on 2026-10-06. Every number on an answer that says "sources" now counts distinct pages under one key, and two links to one page count once.

## Table of contents

- [What a person sees now](#what-a-person-sees-now)
- [What each total counts](#what-each-total-counts)
- [The page key](#the-page-key)
- [Choices and their alternatives](#choices-and-their-alternatives)
- [Tests and mutations](#tests-and-mutations)
- [Gates](#gates)
- [Not covered](#not-covered)

## What a person sees now

On the BRCA1 Researcher answer of 2026-09-27 (`testing/Developer/reports/2026-09-27_product_review_8.10/web_researcher.json`):

| Where on the screen | Before | After |
|---|---|---|
| Line under the question, and the live YOUR SEARCHES item | 13 tools · 18 sources from 3 layers | 13 tool calls · 16 sources cited from 3 layers |
| SOURCES heading | 17 | 16 |
| Trust line under the sources | Based on 17 sources, not yet confirmed | Based on 16 sources cited, not yet confirmed |
| Trust line on a corroborated answer | Confirmed by N independent sources | Confirmed by N independent databases (same N) |
| Trust line's info card | "Sources are counted by the database each record comes from ..." | "Sources cited counts the record pages this answer cites, the same pages listed under Sources; two links to one page count once ..." |
| Opening line | Found 4 disease records for BRCA1: ... | Unchanged, as the owner decided |
| Command line | prints the server's trust line | prints the new trust line; it shows no other total |

In the person's words: a number that says "sources" is the number of source cards you can open and count, wherever it appears. The BRCA1 gene record is one card even when the answer cites it through a link with and without a trailing slash.

Screenshots from the end-to-end check, taken with `CARD22_SHOTS=1`: `answer_1280.png` and `answer_390.png` (fake-model harness, sign-in email masked). They sit in this folder in the worktree but are not committed: the commit guard's leak scanner could not run on the two images, so the lead decides whether to add them.

## What each total counts

Line numbers are on this branch.

| Total | What it counts | Where it is built |
|---|---|---|
| Tool calls (meta line) | Distinct `call_id`s among `tool_start` and `tool_result` events: calls the run made. Unchanged; the word changed from "tools" to "tool calls". | `frontend/src/hooks/useRunView.ts:501-527`, worded at `:1175-1182` |
| Sources cited (meta line) | Before: one per citation event with a usable unique number, so two citations of one page counted twice (the 18). After: distinct pages, read off `groupSourcesByLayer` through `citedSourceCounts`. | `frontend/src/hooks/useRunView.ts:1175-1182`; `frontend/src/components/screens/AnswerScreen.tsx:515-521` |
| Layers (meta line) | Before: distinct layers among all citations. After: the number of layer groups the Sources list shows. These differ only when one page is cited from two layers, which the page key now makes reachable (graph gene link plus live Datasets gene link). | same as above |
| SOURCES heading | Cards in the grouped list, one per page key. | `frontend/src/components/screens/AnswerScreen.tsx:552-581` (grouping), `:1826` (heading) |
| "Based on S sources cited" | Distinct page keys among the grounded claims, falling back to the citation id for a claim without a link. | `src/system_03_search_agent/synthesis/trust.py:646-651`, worded at `:664-666` |
| "Confirmed by N independent databases" | Distinct origin databases (record id prefix), unchanged. Only the noun changed. | `src/system_03_search_agent/synthesis/trust.py:532-543`, `:652`, `:663` |
| "Found 4 disease records" | Records of the question's type that the answer cites, one per page. Not changed by this card. | `src/system_03_search_agent/synthesis/answer_layout.py:991-1100` |

The backend counts over the grounded claims (`core/graph.py`, the `answer_trust_line` call in the `done` event). The frontend counts over the citation events built from those same claims (`synthesis/grounding.py:1833`, `core/graph.py` around line 10693). Both now apply the same key, so on the evidence they agree at 16.

## The page key

One rule, written twice because the backend is Python and the frontend is TypeScript:

- `source_page_key` in `src/system_03_search_agent/synthesis/trust.py:546`
- `sourcePageKey` in `frontend/src/components/screens/AnswerScreen.tsx:506`

The rule drops surrounding whitespace and trailing slashes, nothing else. An empty result means "no page", and each caller falls back to its own id, so two citations without a link are never merged. Both implementations are tested against the same case list in `frontend/e2e/fixtures/card22_brca1_citations.json`.

Why a trailing slash: the graph's gene link has none (`tools/cypher_provenance.py:231`) and the live Datasets builder adds one (`tools/ncbi_datasets_actions.py:327`). `core/graph.py:11051` already strips the slash for its own same-record check, so the system already treated the two as one record elsewhere.

What it leaves alone:

- Case. `core/graph.py`'s helper also lowercases, but that serves an identity check, not a count, and no measured duplicate differed in case.
- Query strings and fragments. A query string can name a different record; PubTator links carry `?query=...`.

What the evidence shows: the 2026-09-27 answer cited 18 numbered citations on 17 exact links. The one duplicate under the new key is `https://www.ncbi.nlm.nih.gov/gene/672` beside `.../gene/672/`, so the count is 16, as the coordinator expected. The fixture rebuilds the 18 citations from the evidence's record table markers and `record_links`. Two details are reconstructed rather than recorded: the OMIM link, built with the code's own OMIM builder, and which gene marker carried the slash. The reconstruction is checked to give the evidence's old numbers (18, 17, and groups of 4, 8 and 5) before the new ones are asserted.

## Choices and their alternatives

| Choice | Alternatives considered | Why |
|---|---|---|
| Meta line counts pages, read off `groupSourcesByLayer` | Rename only, "18 citations" beside "17 sources cited" (option A) | The owner's choice, option B: one sources number everywhere. Reading the count off the list's own grouping means the two cannot drift. |
| "N tool calls" | "N searches run"; leave "N tools" | The number counts calls, one tool can be called many times, and "searches" would include tools that fetch rather than search. |
| "Confirmed by N independent databases" | Keep "independent sources"; add the page count beside it | The owner's rule: every number that says sources counts pages. This number counts databases, so its noun changed and its value did not. |
| Layers from the list's groups | Distinct layers over all citations | The meta line now describes the list, so a page cited from two layers, shown as one card under one layer, counts one layer, as the list shows. |
| A page cited from two layers files under the layer cited first | Show it under both layers | One page, one card. Section 8.3.2 already counts a graph snapshot and a live fetch of one database as one origin. |
| Strip trailing slashes only | Also lowercase, or drop query strings and fragments | The coordinator asked for a narrow rule. Only the slash was measured, and a broader rule could merge two different records. |
| Info card rewritten | Leave it | It said sources were counted by database, which has not been true of "Based on" since item 12.8 (2026-09-23). |
| New query numbered 107, placed after query 74 | Append after query 106 at the end of section 1 | Query 74 covers the same count. One section and one index row, as the brief asked, merge cleanly beside the readability pass. |

## Tests and mutations

New tests:

- `tests/system_03_search_agent/synthesis/test_trust_line_names_its_count.py`, 19 tests: the page key cases, the slash pair counting once, a query string not merged, link-less records not merged, the "cited" wording at both verdicts, "databases" on the confirmed line, and the evidence reconstruction plus agreement at 16.
- `frontend/src/components/screens/AnswerScreen.card22.test.tsx`, 19 tests: the same page key cases, the merged card carrying markers 1 and 2, link-less sources kept apart, the evidence rendered through `useRunView` and `AnswerScreen` (meta, heading and trust line all 16), the singular and empty wording, layers counted as the list groups them, and the info card text.
- `frontend/e2e/card22-name-every-total.spec.ts`: replays the 18 evidence citations through the real app at 1280 and 390, and asserts the meta line, the heading, the trust line, the unchanged opening line and one gene card. It saves screenshots only when `CARD22_SHOTS=1`.

Existing tests changed only where they pinned the old wording:

- `tests/system_03_search_agent/synthesis/test_answer_layout.py`: seven trust-line expectations gain "cited" or "databases".
- `frontend/e2e/rail-collapse.spec.ts`: the rail-count regex.
- `frontend/e2e/tool-chip.spec.ts`: "2 tools" became "2 tool calls".

Every mutation turned its tests red and was restored. The baseline was green before and after.

| Mutation | Caught by |
|---|---|
| B1 backend key keeps the trailing slash | backend tests |
| B2 backend key also lowercases | backend tests |
| B3 backend key drops the query string | backend tests |
| B4 backend link-less fallback removed | backend tests |
| B5 "cited" dropped from the not-yet-confirmed line | backend tests |
| B6 "cited" dropped from the plain line | backend tests |
| B7 confirmed line says "sources" again | backend tests |
| F1 frontend key keeps the trailing slash | unit tests; the end-to-end check also failed, reading "17 sources cited" |
| F2 frontend link-less fallback removed | unit tests |
| F3 meta line counts citations again | unit tests |
| F4 meta line says "tools" again | unit tests |
| F5 meta line drops "cited" | unit tests |
| F6 meta line counts layers over all citations | unit tests |
| F7 info card reverted | unit tests |

## Gates

Run with the main checkout's virtual environment first on PATH. The load average was 7.86 before gate04.

| Gate | Result |
|---|---|
| gate02, import order | pass |
| gate03, lint | pass |
| gate04, whole unit suite | pass: 7043 passed, 143 skipped, 24 deselected, 1 xfailed |
| `npm run build` | pass |
| `npm test` | pass: 59 files, 508 tests |
| `assert_license_notices.py dist` | pass |
| `CI=1 npx playwright test e2e/card22-name-every-total.spec.ts` | pass at 1280 and 390 |
| `CI=1 npx playwright test`, whole suite | 81 passed, 19 failed, 13 skipped. The failures are not this card's: with this card's code changes stashed, the same six spec files failed 20 of 35 on develop's code (`citation-host-allowlist`, `history-reload`, `second-turn`, `trust-surface`, and one test each in `query-stream-and-stop` and `rail-collapse`, which swap between runs). The two specs this card edited both passed: `rail-collapse.spec.ts:212`, whose rail counts must appear verbatim in the answer's line, and `tool-chip.spec.ts:173`. |

## Not covered

- The YOUR SEARCHES list after a reload. A restored search shows "N sources" from the stored citation count (`frontend/src/App.tsx`, `formatHistoryMeta`; `src/system_03_search_agent/feedback/history.py`, `_citation_count`; `core/run.py:499`). That count is citations, so it can be larger than the answer's sources cited, and its wording lacks "cited". It is outside this card's file fence. Fixing it means either counting distinct pages in `_citation_count` or rewording the label; noted in query 107 as known.
- The saved-answer screen lists one row per citation with no count, so a gene cited through two links still appears twice there. It states no total.
- Trust lines saved before this change keep their old wording when reopened.
- The backend counts over the grounded claims' finding links; the frontend counts over the citation events. A Layer 2 or Layer 3 citation whose builder fails is counted by the backend only. Not seen in the evidence; the shared key closes the one measured difference.
- Pre-existing, not this card: the reasoning log keys a tool chip by tool and result count, so two calls of one tool returning the same count raise a React duplicate-key warning. It showed in the first end-to-end run, and the scripted stream now uses distinct counts.
- No live screenshot of develop was taken, and nothing was spent on a model.
- The whole-suite end-to-end run rewrote screenshots in three older report folders. The tracked ones were restored with git. One untracked folder it created, `testing/Developer/reports/2026-09-14_bold_and_stagger/`, is left uncommitted in the worktree, because the deletion hook asks before removing files.
- About 20 end-to-end tests fail on develop's own code on this machine (the gates section lists them). That is outside this card; the lead may want a card for it.
- Query number 107 may collide with a number taken in a parallel worktree; renumber at merge if so.
