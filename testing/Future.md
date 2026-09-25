# Future work

Every piece of remaining work that is not on the board. The board, `testing/UI_fix_plan.md`, holds the UI fix loop's work. This file holds the rest, gathered from two places the product owner does not read day to day:

- Phase 7: `requirements/Plan.md`, section "Phase 7: iteration and new information", both of its tables.
- Archive: `requirements/phase_6/Continuation_prompt-archive.md`, section "Open items", its table and the "Unowned" bullets under it.

Each row of both sources was checked against the code, the tracker and the done file before it was listed. A row the evidence showed closed is under "Checked and closed" with that evidence. A row that could not be settled is listed as open with "Check first" in its card. The detail stays in the source each card names; this file only points to it. Code paths are under `src/system_03_search_agent/` and test paths under `tests/system_03_search_agent/` unless written in full.

Last updated: 2026-09-24.

## Table of contents

- [To do](#to-do)
- [Checked and closed](#checked-and-closed)
- [How this file is kept](#how-this-file-is-kept)

## To do

Ordered from the chair of the person using the product: what they notice first (cards 1 to 15), then security and safety (16 to 29), then evaluation and model work (30 to 36), then internal engineering (37 to 46).

| # | Feature or fix, in plain words | Source | Waiting on |
|---|---|---|---|
| 1 | The account menu tells a signed-in person "no search limit in effect yet", while the daily limit of 100 searches does refuse them | Archive: "Account menu overclaims". The text is at `frontend/src/lib/guestSession.ts:153` | Nobody on it |
| 2 | Check first: a Think step that times out shows a refusal for a question the product answers on other runs. The JSON half was fixed as item 2.11. Board card 2 (12.17) names only the schema failure, so check whether it covers the timeout too | Archive: "Think step retry, and a remaining transient timeout". Detail in `testing/UI_fixes_done.md`, item 2.11 | Nobody on it |
| 3 | Check first: when the model writes a graph search itself, about one run in ten the search is malformed, the graph rejects it, and the question fails. Generation now carries one repair retry, and board card 23 may remove the path entirely | Archive: F-2.2-01. Detail in `tracker/phase_2.2.md`; the retry is described in `tools/cypher_generation.py:1` | Nobody on it |
| 4 | Check first: a literature walk from a gene over `mentioned_in` took 27 seconds forward and the whole time budget in reverse. Not measured again since build phase 2.1 | Archive: F-2.1-A5-05. Detail in `tracker/phase_2.1.md` | Nobody on it |
| 5 | Check first: a listing answer cut short says more records exist but never how many, so a reader cannot tell 5 missing from 15,000 missing. The test is still marked expected to fail | Archive: F-2.2-06. Detail in `tracker/phase_2.2.md`; test at `core/test_write_grounding_premise.py:827` | Nobody on it |
| 6 | A graph fact that has gone stale is never checked against live NCBI, because the graph's records carry no field the freshness check knows. Once it can fire, its note must also tell "never checked" apart from "check failed". Needs a richer graph ingest from the data repository | Archive: F-3.4-T06-01 and F-3.4-A-05. Detail in `tracker/phase_3.4.md` | Nobody on it |
| 7 | A clinical trials search on a vague word such as "the" or "5" returns generic trials cited with confidence, and the reader is not told the match is weak. The API returns no relevance score to disclose | Archive: F-3.5-A-07. Detail in `tracker/phase_3.5.md` | Nobody on it |
| 8 | Apply the rule that anything dropped or shortened is disclosed: a trial's condition name over the cap is cut short and can read as a different term, and PubTator drops an unreadable row without saying so | Archive: F-3.3-J-04, which says it also settles F-3.5-10. Detail in `tools/clinicaltrials_search.py:239`, `tracker/phase_3.5.md`, and F-3.3-RR2-04 in `tracker/phase_3.3.md` | Nobody on it |
| 9 | A LitVar citation for a variant with no rs number points at a search page, using an internal identifier as the search term | Archive: F-3.3-A-10. Detail in `tracker/phase_3.3.md` | Your decision |
| 10 | One malformed PubMed id in a batch discards the whole batch, real papers included, and never says which id was wrong | Archive: F-3.3-A-13. Detail in `tracker/phase_3.3.md` | Your decision |
| 11 | An isolate neighbour search spends part of its tight time budget on a file read whose result is thrown away, so it runs out of time sooner | Archive: F-3.5-A-10. Detail in `tracker/phase_3.5.md`; code at `tools/pathogen_detection.py:979` | Your decision |
| 12 | A clinical trials search containing a stray bracket fails with a message that never mentions punctuation | Archive: F-3.5-A-14. Detail in `tracker/phase_3.5.md` | Your decision |
| 13 | Relations between genes, diseases and chemicals from PubTator3 are not offered, because the relations endpoint's path and fields were never checked live | Archive: "PubTator3 relations endpoint" | Nobody on it |
| 14 | A reasonable-effort accessibility pass, for people using a screen reader or a keyboard. The full audit stays outside v1 | Phase 7: "Build phase 6.1, hardening and release" | Nobody on it |
| 15 | The NCBI design system's own components, stages 2 and 3, cannot be installed from outside the NCBI network. Needs someone with that access | Archive: "NCBI design system stages 2 and 3 blocked". Detail in `docs/build/design/NCBI_design_system_migration_assessment.md` | Nobody on it |
| 16 | A security scan of the whole codebase. The only one ran on 2026-07-25, before any build phase. It was dropped for the prototype on 2026-08-24 with the note that production would need it, and v0.2.0 is on production now | Archive: "Whole-repository security scan". Phase 7: "Build phase 6.1". `DECISIONS.md`, 2026-08-24 | Your decision |
| 17 | Whether security scan results are ever committed. The `security/` folder is ignored today, at `.gitignore:64` | Archive: the line above the Open items table | Your decision |
| 18 | Signing up with an email that already has an account answers "email already registered", so anyone can test which emails are registered. The response time differs too | Archive: F-1.2-04, and F-1.1-10 under "Unowned". Code at `auth/router.py:559`; detail in `tracker/phase_1.1.md` | Nobody on it |
| 19 | An agent calling this product over MCP cannot tell text relayed from a PubMed abstract apart from the product's own words, a prompt-injection path into that agent. You decided on 2026-08-15 to mark relayed text; it is not built | Archive: F-4.1-A-10. Detail in `tracker/phase_4.1.md` | Nobody on it |
| 20 | When a question hits the 20-call ceiling, six tools swallow the budget error, so the answer loses its partial-result path and the error loses its next step | Phase 7: F-6.0-J-04. Detail in `tracker/phase_6.0.md` | Nobody on it |
| 21 | The guardrail's pre-filter misses injection phrases written in non-Latin scripts and some write verbs. The guard model still covers both | Archive: ADV-03 and ADV-06. Detail in `tracker/phase_3.0.md:404` | Nobody on it |
| 22 | An instruction slipped into a question as a comma-separated clause can still feed its own words to the answer check | Archive: F-2.2-T-01-residual. Pinned by a strict expected failure at `synthesis/test_grounding_hardening.py:569` | Nobody on it |
| 23 | The efetch citation link rule checks how a link starts but not how it ends. The main citation link rule was closed; this one was not | Archive: F-3.4-A-06. Code at `tools/ncbi_efetch_schemas.py:141`; detail in `tracker/phase_3.4.md` | Nobody on it |
| 24 | A NUL byte in the User-Agent header at sign-in returns a server error rather than a clean refusal | Archive, "Unowned": F-1.1-11's User-Agent half. Detail in `tracker/phase_1.1.md` | Nobody on it |
| 25 | One account's sign-in token accepts five spellings of its user id | Archive, "Unowned": F-1.1-18. Detail in `tracker/phase_1.1.md`; code at `auth/dependencies.py:104` | Nobody on it |
| 26 | A replayed sign-in token revokes the whole session family without writing a log line, so an attack leaves no trace | Archive, "Unowned": auth-path logging. Code at `auth/router.py:375` | Nobody on it |
| 27 | A guardrail that checks meaning as well as shape: validate facts against MeSH, Gene Ontology and NCBI taxonomy between Act and Write, to catch a variant linked to the wrong organism. No trigger is defined | Archive, "Unowned": new-intake semantic guardrail layer | Your decision |
| 28 | The coordinate-overlap tool's text cap does not reach into nested records. No caller builds one today | Archive: F-3.1-46. Code at `tools/ncbi_coordinate_overlap.py:229`; detail in `tracker/phase_3.1.md` | Your decision |
| 29 | The injection test on the live graph is still marked expected to fail. Clearing it needs five clean live runs, possible since build phase 4.11 replaced the tunnel | Archive: F-2.1-J4-02, with T-3.0-07. Marker at `tools/test_cypher_query_premise.py:371` | Nobody on it |
| 30 | An expert review of the 50 golden questions and their expected answers. No new golden question is written until it happens | Archive: "The golden 50 are a v1" and "Golden fixture domain sign-off". Phase 7, first table | Your decision |
| 31 | The grading harness does not work: it compares an answer against its own citations, so a fabricated answer citing a record that does not exist scored 16 of 16 | Phase 7: "The grading harness". Detail in `tracker/phase_5.2.md` | Nobody on it |
| 32 | No golden question checks that an answer reached all three layers, the `must_reach` and `live_only` fields. Follows card 30 | Phase 7: "Golden rows using must_reach and live_only". F-5.3-A to F-5.3-E in `tracker/BOARD.md` | Nobody on it |
| 33 | No golden question needs `litvar2_lookup` or `pubtator_annotate`, so neither tool is measured. Follows card 30 | Phase 7: "Per-tool coverage" | Nobody on it |
| 34 | Pick each tier's model by its score on the golden set. Needs card 31 first, and sits next to board card 10 | Phase 7: "Model-bench per tier, formerly build phase 7.0" | Nobody on it |
| 35 | Randomized A and B routing between model choices on real traffic. Needs card 34 and enough traffic | Phase 7: "The A and B randomized-routing mechanism, formerly build phase 7.1" | Nobody on it |
| 36 | OpenRouter's Auto Router, judged three ways: a benchmark candidate, a routing arm, or a fallback when a pinned model is down | Archive: new-intake "OpenRouter Auto Router". `DECISIONS.md`, 2026-08-30 | Your decision |
| 37 | Build phase 6.0's tests do not prove the rate and call limits are wired into the real query path. Three of its nine judge findings are critical. Its premise gate was deleted on 2026-09-24, and the unit test that replaced it pins the ceiling alone | Phase 7: build phase 6.0's nine judge findings. Detail in `tracker/phase_6.0.md` and `tracker/BOARD.md`; test at `harness/test_call_budget_ceiling.py` | Nobody on it |
| 38 | Build phase 6.0's adversary round, never run | Phase 7: "The adversary round for 6.0" | Your decision |
| 39 | The CI gates advise but do not block a merge. Blocking needs GitHub Pro or a public repository | Phase 7: "Build phase 6.1". F-4.14-A-04 in `tracker/BOARD.md` | Your decision |
| 40 | The `dev-standards` six-lens production review | Phase 7: "Build phase 6.1" | Nobody on it |
| 41 | Whether the harness should retry a model error classed "unexpected". Today only a transient failure retries, once | Archive: F-3.4-A-07. Code at `harness/harness.py:536`; detail in `tracker/phase_3.4.md` | Nobody on it |
| 42 | The model call that writes a graph search does not reuse the cached prompt prefix, so it bills at the uncached rate | Archive: F-06. Code at `tools/cypher_query.py:69` and `tools/cypher_generation.py:306` | Nobody on it |
| 43 | Frontend tests fail under machine load rather than from a defect. Re-run a failing spec alone before trusting it | Archive: "Load-dependent test flakiness (D4)". F-4.10-R-10 in `tracker/BOARD.md` | Nobody on it |
| 44 | PubTator and LitVar hand each other variant ids in different shapes. No code chains the two today | Archive: F-3.3-A-11. Detail in `tracker/phase_3.3.md` | Nobody on it |
| 45 | A LitVar row with no identity can ship as an empty but successful match. Not seen on live data | Archive: F-3.3-RR-02. Detail in `tracker/phase_3.3.md` | Nobody on it |
| 46 | The isolate distance lookup can fall back to a different metric. Not seen firing on about 9,400 rows | Archive: F-3.5-A-11. Code at `tools/pathogen_detection.py:376`; detail in `tracker/phase_3.5.md` | Nobody on it |
| 47 | At the locked specification's next reconciliation, add two NCBI fields the code reads beyond Section 6.2's table: the gene record's `summary` (item 11.31, kept by the product owner on 2026-09-25) and the MedGen record's clinical features parsed from `conceptmeta` (phase 8.1, card 1) | DECISIONS.md, 2026-09-25, card 36; `tracker/phase_8.1.md`, F-8.1-V03 | The next reconciliation |

Already on the board, so not repeated here:

- Archive, "NCBI design system stage 1 dependency": board card 35.
- Archive, "Four type value mismatches": board card 34.
- Archive, "Python lockfile": board card 18.

## Checked and closed

Every source row found closed, with the evidence that closed it.

| Item | Source | Evidence |
|---|---|---|
| Consistency baseline, paused | Archive | Rerun as item 10.3 on 2026-09-22: `testing/UI_fixes_done.md:107`, evidence in `testing/Developer/reports/2026-09-22_10.3_consistency/` |
| Only 2 of 7 tools run | Archive | All seven tools are dispatched, `core/graph.py:2806`. The remaining L-01 work is board cards 7 and 23 |
| MCP rejects every request, "Invalid Host header" | Archive | The row says RESOLVED by fix set 5, item 5.3. Its scheme-downgrade residual is Retest card 11 on the board, item 11.30 |
| Think step retry, the JSON half | Archive | Item 2.11 approved, `testing/UI_fixes_done.md:67`. The timeout half is card 2 above |
| `GCK` refused on the deployed API | Archive | Item 11.19, "Variants in GCK causing MODY should answer every time", live and approved: `testing/UI_fixes_done.md:125` |
| F-3.1-41, stopword list against gene symbols | Archive | Dissolved by build phase 4.7, which retired `plan_node`'s capitalized-token guess: `CLAUDE.md`, Build phase history, row 4.7 |
| F-3.1-42, lowercase gene mentions | Archive | Dissolved by build phase 4.7, same evidence |
| F-3.1-50 and F-3.1-51 | Archive | The row says RESOLVED at Step 6.2, 2026-08-10 |
| F-3.4-A-04, premise gate coverage overclaim | Archive | Coverage statement corrected at Step 6.2: `synthesis/test_citation_trust_full_premise.py:58` |
| F-3.4-A-06, the main citation link rule | Archive | `NCBI_SOURCE_URL_PATTERN` now ends in an end anchor, commit `e8b6942` (`contracts/events.py:116`). The efetch rule is card 23 above |
| F-3.4-T03-01 | Archive | The row says RESOLVED at Step 6.2 |
| F-3.4-A-07, the diagnostic half | Archive | The provider's error text reaches the internal message, `harness/harness.py:600`. The retry question is card 41 above |
| Section 8.2 matching rule | Archive | The row says RESOLVED at Step 6.2 |
| Section 23 offline gate | Archive | Resolved as a decision for build phase 5.1, which merged as PR #85. The grader it needs is card 31 above |
| `release-workflow` dispatch gap | Archive | The row says RESOLVED at Step 6.2 |
| F-2.1-02 | Archive | The row says RESOLVED at Step 6.2 |
| F-2.1-01 | Archive | The row says RESOLVED at Step 6.2 |
| F-2.1-16 | Archive | The row says RESOLVED at Step 6.2 |
| Env var name divergence | Archive | The row says RESOLVED at Step 6.2 |
| F-3.0-01 | Archive | The row says RESOLVED at Step 6.2 |
| ADV-07, the unescaped `</query>` delimiter | Archive | Closed as F-4.7-A-05 by a fresh tag per request: `guardrail/classifier.py:330`. ADV-03 and ADV-06 are card 21 above |
| ADV-02-residual, a German question refused | Archive | "Closed after the judge round": `tracker/phase_3.0.md:347` |
| F-2.1-07, one-entry gene table | Archive | Replaced by T-3.1-11 in build phase 3.1; the table now survives only in comments, `core/graph.py:307` and `:3800`. Build phase 4.7 then made resolution live-confirmed |
| F-2.1-B10, unresolvable symbol errors | Archive | Same cause and same fix as F-2.1-07 |
| F-3.3-J-04, disclosure-policy asymmetry | Archive | Closed in fix round 4: `tracker/phase_3.3.md:110`. Its F-3.5-10 residual is card 8 above |
| F-3.3-J-06 | Archive | The row says RESOLVED at Step 6.2 |
| F-3.3-A-05 | Archive | The row says RESOLVED at Step 6.2 |
| F-3.3-A-12, undisclosed truncation | Archive | Closed in fix round 4 with companion totals: `tracker/phase_3.3.md:125`, `tools/pubtator_annotate.py:187` |
| F-3.5-A-03 | Archive | The row says RESOLVED at Step 6.2, by disclosure |
| F-3.5-A-09 | Archive | The row says RESOLVED at Step 6.2 |
| F-3.5-A-12 | Archive | The row says RESOLVED at Step 6.2 |
| F-1.2-01, F-1.2-02 and F-1.2-03 | Archive | Resolved by build phase 4.0, PR #39: `tracker/BOARD.md`, Open flags |
| F-4.1-A-15, session_id unbound to the caller | Archive | Closed by build phase 4.5: `tracker/phase_4.5.md:132`, and `CLAUDE.md`, Build phase history, row 4.5 |
| New-intake: a stateless MCP server | Archive | The row says RESOLVED by build phase 4.1 |
| F-2.0-04, nothing writes `interactions` rows | Archive | Closed by build phase 4.6: `CLAUDE.md`, Build phase history, row 4.6 |
| F-2.0-10, client-supplied `trace_id` | Archive | Closed by build phase 4.6, same evidence |
| New-intake: signal-based sampling for review | Archive | The weekly review picks rows by signal, a failed rubric, a flag or refusal, or a thumbs-down: `docs/build/Feedback_review_ritual.md:46` |
| Curate `LEARNINGS.md` into the golden dataset | Archive | Done as T-5.1-02: `tracker/phase_5.1.md:125`, `docs/build/Golden_dataset_method.md:133` |
| Stand up CI | Archive | Build phase 4.14, PR #68: `.github/workflows/ci.yml` |
| Fix `pip install .` | Archive | F-4.14-CI-01: `tracker/phase_4.14.md:159`, `pyproject.toml:160` |
| The disease-name defect, "what stays ahead of all of this" | Phase 7 | Build phase 6.2, PR #92: `requirements/Plan.md:889`. The graph side, no disease names in the graph, is board card 29 |
| Build phase 6.1's CI and CD gates | Phase 7 | The row itself says they shipped in build phases 4.14, 4.12 and 4.15. The merge-blocking question left over is card 39 above |

Phase 7's three method subsections, "How new information enters the system", "Hard stop rule" and "Post-v1 iteration cycle", describe how work is done rather than work to do, so they are not listed.

## How this file is kept

- `/phase-checkpoint` keeps this file current at every session boundary.
- A card leaves this file when the product owner schedules it: into the board's To do for the UI fix loop, or into a bossman build phase.
- A card found closed moves to "Checked and closed" with its evidence, never deleted.
