# Card 53 fix round, 2026-09-29

The single fix round after the judge (F-53-J01 to J06) and the adversary (F-53-A01 to A12), on branch `fix/card53-stale-facts`. One fix agent held every finding, since most of them touch the same three page files and the same two checker files (Review_rounds.md, Rule 1). The checker was fixed by category, not by the reviewers' examples (Rule 2). Nothing was pushed, and no deployed app was contacted.

The lead's decision, from the user's chair: a plainer sentence that is always true beats a detailed one that is sometimes false.

## Table of contents

- [Commits](#commits)
- [Findings, one by one](#findings-one-by-one)
- [How the checker was fixed by category](#how-the-checker-was-fixed-by-category)
- [Gate results](#gate-results)
- [The reviewers' break-it edits, re-run](#the-reviewers-break-it-edits-re-run)
- [Open, and why](#open-and-why)

## Commits

| Commit | Subject |
|--------|---------|
| `2e3b212d` | fix(web-ui): the Architecture and About pages say which questions get literature and trial evidence, and which do not |
| `c0aa05b9` | fix(harness): the tool catalogue says its timeouts come from the code's own budgets |
| `541d5a7c` | docs: the README no longer tells a developer to run Redis for a cache no code uses |
| `9fede690` | fix(kgx-export): the manifest's comment says which check makes its layer 1 only sentence true |
| `e0b4fbb2` | ci(verify): the facts checker fails a page whose guarded sentence gains a clause, a negation or a stray word |

## Findings, one by one

| Finding | Status | Commit | What changed | The check that now guards it |
|---------|--------|--------|--------------|------------------------------|
| F-53-J01 catalogue claims its timeouts are copied from the rule | Fixed | `c0aa05b9` | The docstring and comment say each `timeout_s` is the budget the tool's code enforces, name the three constants, and say the rule gives Pathogen Detection only a floor | `test_timeouts_match_the_budgets_the_code_enforces` compares every catalogued timeout with its constant; facts `budget.*` read the catalogue too |
| F-53-J02 "no decision gates layer 3", "every question that names a disease" | Fixed | `2e3b212d` | The layer 3 stop now says Plan decides, that not every question gets it, and names the paths that do not, including a no-gene question the classifier reads as asking for papers. The three code comments that said "no decision and no request gates them" are rewritten | `layers.l3_not_every_question` (plan_node reaches `_build_layer_tool_calls` only inside a branch), `layers.l3_other_ways` (plan reaches `_literature_choice`, which asks the classifier) |
| F-53-J03 the list readers pass a negation | Fixed by category | `e0b4fbb2` | Every list of names is read by `names_only`: each word must be a known name or one of a closed set of connectives, so "not", "never" and "excluded" fail | Self-test negation proof on every place; mutation test J03 edits, 3 of 3 caught |
| F-53-J04 README says Redis caches | Fixed | `541d5a7c` | Redis left the prerequisites; the stack table says caching is in-process only and that the Railway Redis service is not read by any code yet. Checked first: nothing under `src/` imports `redis` | New fact `stack.redis_unused` reads every module under `src/` |
| F-53-J05 always-loaded rules still name LitSense | Open | none | Not edited, see [Open, and why](#open-and-why) | none |
| F-53-J06 "no layer is read before another" | Fixed | `2e3b212d` | Both pages and the InfoScreens comment now say Act sends the first round out together and sends the calls that need a first-round result, such as a PubMed search's abstracts, in a second round | New facts `loop.act_second_round` (Act calls `_gather_planned_calls` twice) and `loop.pubmed_follow_ups` (the examples named are follow-ups `_BREADTH_FOLLOW_UPS` plans) |
| F-53-A01 a gene named by identifier gets no layer 3 | Fixed on the page | `2e3b212d` | The page says PubTator3 and ClinicalTrials.gov come for a gene named by its symbol, and that a gene named only by an identifier is searched another way | `layers.l3_triggers` reads the `":" not in mention` test and the symbol-or-disease search text; `layers.l3_other_ways` |
| F-53-A02 isolate questions get no layer 3 | Fixed on the page | `2e3b212d` | The page names a question about bacterial isolates among those searched another way | `layers.l3_other_ways` reads the isolate branch and that the layer 3 call sits inside a branch |
| F-53-A03 a false clause after a guarded span passes | Fixed by category | `e0b4fbb2` | A place must cover every sentence it touches, whole | Self-test extension proof on every place; M03, M04, M05, M06, M18 caught |
| F-53-A04 one card of five drops out silently | Fixed by category | `e0b4fbb2` | Every place states how many times it appears (`expect`); a different count, zero included, is a FAIL | Self-test removal proof on every place; M08 caught |
| F-53-A05 the true words in a comment or unused constant vouch for a false page | Fixed by category | `e0b4fbb2` | Places are read from the visible text: comments, docstrings and constants nothing uses are blanked first | Self-test comment and unused-constant proofs on every place where they apply; M12, M13 caught |
| F-53-A06 the layer 3 conditions and the KGX manifest had no check | Fixed | `e0b4fbb2`, `9fede690` | New facts for each condition in the rewritten layer 3 stop, and for both manifest sentences | `layers.l3_triggers`, `layers.l3_other_ways`, `layers.l3_modes`, `layers.l3_non_ncbi_host`, `export.layer1_only`, `layers.l2_apis` and `layers.l3_apis` on the whole manifest sentence; M14, M15, M16 caught |
| F-53-A07 "Seven stops", "One query", "Fetched while you wait" unchecked | Fixed | `e0b4fbb2` | All three sentences were true and stay; each is now guarded | `about.stop_count` counts the `<JourneyStop>` elements About renders; the "One query" sentence is read whole by `loop.layer_one_read_first`; the layer 2 walk entry is read whole by `layers.l2_tools`; M19 and both M20 edits caught |
| F-53-A08 "15 seconds for a live NCBI call" while Pathogen Detection has 120 | Fixed | `2e3b212d` | About stop 3 says each source has its own limit: 30 seconds for a graph query, 15 for a call to a live web API, and 120 for Pathogen Detection, the longest | `budget.pathogen_s` now reads the About sentence; new `budget.longest` compares the three budgets |
| F-53-A09 "one access path within it" | Fixed | `2e3b212d` | The claim is gone: the sentence now says each tool reaches exactly one layer | The sentence is read whole by `tools.count` and `layers.count` |
| F-53-A10 PubTator3 and LitVar2 said to return papers | Fixed | `2e3b212d` | The stop says PubTator3 looks the name up in its index of genes and diseases found in papers, and LitVar2 finds a named variant and counts the papers that mention it | New fact `layers.l3_modes` reads the `"mode"` each call is planned with (`entity_lookup`, `variant_search`) |
| F-53-A11 a failed MedGen lookup plans no layer 3 and says nothing | Open | none | Not edited, see [Open, and why](#open-and-why). The page no longer promises layer 3 for every disease question | none |
| F-53-A12 "at most 500 rows" | Fixed | `2e3b212d` | The Architecture page and the graph tool card say 100 rows, the most any planned graph call asks for. The test that asserted 500 now asserts 100 | New fact `budget.planned_rows` reads every `row_limit=` in `core/graph.py`; `budget.row_limit` keeps the schema's 500 for the diagram, which states the tool's own limit |

## How the checker was fixed by category

Each category the reviewers found is now a rule in the engine, `check_facts.py`, and each rule is proven on every place by `--self-test`, not only on the reviewers' examples.

| Category | Rule in the engine | Proof on every place (proven of tried) |
|----------|--------------------|-----------------------------------------|
| Words added to a guarded sentence (A03) | `sentence_problem`: a match must cover every sentence of a prose unit it touches | extension 238 of 238 |
| A negation or synonym inside a sentence (J03, A03) | The same rule, plus strict list readers (`names_only`, `snake_names`, `modes_named`, `pipeline_step_names`, `kgx_example_options`) | negation 264 of 264 |
| A statement that disappears or drops one card (A04) | `Where.expect`: the count must match exactly; zero or a wrong count is FAIL | removal 206 of 206 |
| True words kept in a comment (A05) | `visible`: comments and docstrings blanked before any pattern runs | comment 194 of 194 |
| True words kept in an unused constant (A05) | `_unused_constants`: a top-level constant nothing reads is blanked, for screens (a code copy keeps its constants) | unused 110 of 110 |

Two limits, stated so they can be argued with:

- A place marked `block` reads fields out of a structure (the two layer arrays, the guardrail banner's copy, a JSON sample, a model table row). It is exempt from the whole-sentence rule. The prose inside such a structure is guarded only where another place reads it, which now includes every layer 3 sentence and the layer 2 walk entry.
- Some guarded sentences are pinned word for word rather than computed, such as the tier cards' kinds. An edit to one fails the check and so reaches review, but the words themselves are not derived from code.

## Gate results

Every process was polled to its end.

| Gate | Command | Result |
|------|---------|--------|
| Facts checker, local files | `venv/bin/python .claude/skills/verify/scripts/check_facts.py` | `facts: 81 / stale 0 / not fully checked 0 / places: PASS 226, FAIL 0, GAP 0, ERROR 0 / PASS`, exit 0 |
| Facts checker self-test | `check_facts.py --self-test` | `226 of 226 comparisons proven to pass and to fail; 81 of 81 readers proven to follow a changed source; 14 parser cases; 0 failures`, and by category `extension 238 of 238; removal 206 of 206; comment 194 of 194; unused 110 of 110; negation 264 of 264` |
| Facts checker mutation test | `check_facts.py --mutation-test` | `30 of 30 break-it edits caught` |
| Frontend tests for the touched files | `npx vitest run` on the Architecture, About, Integrations, events and events.persona tests | `Test Files 5 passed (5)`, `Tests 63 passed (63)` |
| Frontend build | `npm run build` in `frontend/` | exit 0, one chunk size warning that predates this card |
| Unit suite | `pytest -m "not integration" -q -rs`, as `.github/gates/gate04_unit_suite.sh` runs it | `6501 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 272.40s`, exit 0 |
| Lint | `ruff check .` | `All checks passed!` |
| Import order | `isort --check-only --diff src tests services tracker alembic .claude .github`, as gate02 runs it | exit 0 |
| Doc drift | `python3 tracker/check_doc_drift.py --check` | `ok: 2 facts computed / 0 could not be computed / 0 stale / 0 structural` |

## The reviewers' break-it edits, re-run

Method: `git archive HEAD` into a scratch folder, then each edit written to the copy on disk, `check_facts.py --root <copy> --reference <data-engineering>` run as its own process, and the file restored. The unedited copy passed before and after (`PASS 226`, exit 0). The edits are the reviewers' own where their text still exists, and rewritten for the new page text where the page changed; the same list is `MUTATIONS` in `facts_registry.py`, which `--mutation-test` replays in memory.

| Edit | From | Before this round | Now |
|------|------|-------------------|-----|
| Manifest layer 2 list: "PubChem and dbSNP, not Pathogen Detection" | J03 | PASS, exit 0 | FAIL `layers.l2_apis`, the list says "not", exit 1 |
| CLAUDE.md layer 3 list: "never ClinicalTrials.gov" | J03 | PASS, exit 0 | FAIL `layers.l3_apis`, exit 1 |
| README layer 2 list: "(PubChem excluded)" | J03 | PASS, exit 0 | FAIL `layers.l2_apis`, exit 1 |
| "Every question gets them" | J02 | the old sentence was certified PASS | FAIL `layers.l3_not_every_question`, exit 1 |
| "for every gene" in place of "for a gene named by its symbol" | A01 | not checked | FAIL `layers.l3_triggers`, exit 1 |
| Isolates dropped from the questions searched another way | A02 | not checked | FAIL `layers.l3_other_ways`, exit 1 |
| M03 "20 live calls in each layer" | A03 | PASS, exit 0 | FAIL `budget.live_calls_per_question`, exit 1 |
| M04 "15 seconds, five retries" | A03 | PASS, exit 0 | FAIL `budget.live_call_s` and `budget.live_retries`, exit 1 |
| M04 "two calls" said to run "all at once" | A03 | PASS, exit 0 | FAIL `budget.live_call_s`, exit 1 |
| M05 a Researcher-only clause added | A03 | PASS, exit 0 | FAIL `layers.l3_triggers`, exit 1 |
| M06 "searched at the same time as each other, once the graph has answered" | A03 | PASS, exit 0 | FAIL `loop.layer_one_read_first`, exit 1 |
| M08 "15 minutes, one retry" | A04 | PASS 201, exit 0 | FAIL `budget.live_call_s` (said 4 times where 5 are read), exit 1 |
| M12 false layer 3 summary, true words in an unused constant | A05 | PASS, exit 0 | FAIL `layers.l3_not_every_question`, exit 1 |
| M13 "two minutes and up to 5,000 rows", true sentence in a JSX comment | A05 | PASS, exit 0 | FAIL `budget.graph_query_s` and `budget.planned_rows`, exit 1 |
| M14 conditions narrowed to diseases and ten rs ids | A06 | PASS, exit 0 | FAIL `layers.l3_triggers`, exit 1 |
| M14 PubTator3 named as the non-NCBI host | A06 | PASS, exit 0 | FAIL `layers.l3_non_ncbi_host`, exit 1 |
| M15 "covers Layers 1 and 2" | A06 | PASS, exit 0 | FAIL `export.layer1_only`, exit 1 |
| M15 "are present in this file" | A06 | PASS, exit 0 | FAIL `layers.l2_apis`, `layers.l3_apis` and `export.layer1_only`, exit 1 |
| M16 PubTator3 in the manifest's layer 2 list | A06 | FAIL, exit 1 | FAIL `layers.l2_apis`, exit 1 |
| M18 "except to choose every tool it plans" | A03 | PASS, exit 0 | FAIL `loop.plan_on_plan_tier`, exit 1 |
| M19 "Nine stops" | A07 | PASS, exit 0 | FAIL `about.stop_count`, exit 1 |
| M20 "Five queries return" | A07 | PASS, exit 0 | FAIL `loop.layer_one_read_first`, exit 1 |
| M20 "Fetched overnight, so they are a day old" | A07 | PASS, exit 0 | FAIL `layers.l2_tools`, exit 1 |
| Pathogen Detection's limit said to be 15 seconds | A08 | not checked | FAIL `budget.pathogen_s`, exit 1 |
| The graph query named the longest limit | A08 | not checked | FAIL `budget.longest`, exit 1 |
| "and one access path within it" put back | A09 | not checked | FAIL `tools.count` and `layers.count`, exit 1 |
| LitVar2 said to return the papers | A10 | not checked | FAIL `layers.l3_modes`, exit 1 |
| "at most 500 rows" | A12 | certified PASS against the schema's 500 | FAIL `budget.planned_rows`, exit 1 |
| The second round said to go out with the rest | J06 | not checked | FAIL `loop.act_second_round`, exit 1 |
| README says the code caches in Redis | J04 | not checked | FAIL `stack.redis_unused`, exit 1 |

Not reproducible from the reports: the adversary's M01, M02, M07, M09 to M11, M17 and M21 to M24 are named in its summary without their text, and the judge's first run of 15 names its files but not each edit. Of those, only M21 stayed PASS before this round, and its edit is not described anywhere in the report.

## Open, and why

- F-53-J05, the always-loaded rules `.claude/rules/ai-security-standards.md` and `.claude/rules/tool-call-budgets.md` still name LitSense and list the older layer 2 APIs. A rule edit needs the product owner's approval item by item, and it was outside this round's file list. What a reader of those rules is told: that the tools call LitSense and that the untrusted-content surface leaves out Datasets, PubChem and Pathogen Detection.
- F-53-A11, when the MedGen name lookup fails or times out, a disease question plans the graph call alone and the answer does not say a search was skipped. That is product behaviour in `core/graph.py`, not a stale fact, and it was outside this round's file list. The pages no longer promise layer 3 for every disease question, so they are true on that path; the silence on the answer is still there.
- `visualizations/System_3_deep_dive.md` row "Act | Run the chosen tools at once and record what each returned" describes the first round only. The document is outside this round's file list; the checker does not read that cell.
- One line of `judge.md`, its privacy scan, quoted the search terms it used, among them a home-directory prefix and the owner's name, which the repository's pre-commit check refuses. The fix round reworded that line to name the terms without quoting them; the finding itself is unchanged.
