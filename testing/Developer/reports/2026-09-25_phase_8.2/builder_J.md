# Builder J, build phase 8.2 wave 2: wiring decide() into the loop

Scope: guardrail.relevancy, think.ask_back, think.recent_years, plan.literature, plan.resource, the done event's decisions, and golden row G-035. Findings were appended the moment they were established; the summary sections sit above the log.

## Table of contents

- [Commits, gates and fence](#commits-gates-and-fence)
- [Task 1, guardrail.relevancy: live evidence (commit 872cac7)](#task-1-guardrailrelevancy-live-evidence-commit-872cac7)
- [Live evidence on the final head, tasks 2, 3, 4 and 6](#live-evidence-on-the-final-head-tasks-2-3-4-and-6)
- [Tasks 2, 3, 4 and 6: what was built](#tasks-2-3-4-and-6-what-was-built)
- [Choices made, for the lead to log in DECISIONS.md (outside this fence)](#choices-made-for-the-lead-to-log-in-decisionsmd-outside-this-fence)
- [Task 5, plan.resource: nothing wired, by design](#task-5-planresource-nothing-wired-by-design)
- [Findings log](#findings-log)

## Commits, gates and fence

Branch `worktree-agent-a35ebdcc70d0abf87`, on top of `phase/8.2-classifier-seam` (0bd47c9), not pushed:

| Commit | What |
| --- | --- |
| 364e2b9 | Task 7: golden G-035's must-cite accepts `https://www.ncbi.nlm.nih.gov/taxonomy/562` |
| 52b6890 | Seam fix: both classifiers are told what each decision is (F-J-03) |
| 872cac7 | Task 1: guardrail.relevancy; the guard-reply parse fix (F-J-06) |
| 9f079ce | Task 2: think.ask_back through the seam; the writer only writes |
| 44f97dc | Task 3: think.recent_years and the publication-date limit |
| 4b32994 | Task 4: plan.literature; the literature word list removed |
| abead5a | Task 6: every done event carries its run's decisions |

Gates, on abead5a:

- `pytest tests/system_03_search_agent/core tests/system_03_search_agent/guardrail tests/system_03_search_agent/harness tests/system_03_search_agent/test_debugging_guide_coverage.py`: 1603 passed, 56 skipped. `tests/system_03_search_agent/eval` after the G-035 change: 45 passed, 1 skipped.
- `ruff check` and `isort --check-only` pass on every changed file (`core/graph.py` is in isort's `extend_skip` by repository config and is checked by ruff's I001 instead).

Files touched outside the listed fence, each for a stated reason:

- `src/system_03_search_agent/harness/jev_client.py`: two optional keyword arguments, defaults byte-identical (F-J-03).
- `docs/build/Debugging_guide.md` rows for clarify, prefilter, decide, jev_client and breadth_plan, and `tests/system_03_search_agent/fixtures/debugging_guide_manifest.json` (one hash): `core/clarify.py` was repurposed, and CLAUDE.md requires the guide to change in the same commit.
- Existing tests whose assertions pinned the old behaviour, all under `tests/system_03_search_agent/core`, `guardrail` and `harness`: the pre-filter's off-topic refusal arms now assert the allowlist never admits those questions; the loop's model-call counts exclude the seam's own decision calls and a new arm pins those calls; the personalization premise names `_think` as the Think step's body; `test_topic_search.py`'s literature arms stub the classifier instead of the word list.
- `src/system_03_search_agent/core/graph 2.py`, the stray copy (see the findings log), was moved to the scratchpad while the guide manifest was regenerated and then put back where it was, unchanged.

## Task 1, guardrail.relevancy: live evidence (commit 872cac7)

CLASSIFIER_PROVIDER=jev, this worktree's `src/`, runs closed at the `plan` event so no tool or answer call is paid for:

- `what is the best pizza in Chicago`: refused 3 of 3, category off_topic, today's wording unchanged, in 1.50, 2.63 and 5.02 s. Runs 2 and 3: the relevancy decision refused, Jev off_topic at 1.0 and the guard off_topic, agreed. Run 1: the injection classifier's own off-topic field refused first, so the relevancy decision still in flight was cancelled and is not on that run's `done` (F-J-02).
- `Tell me about the tree of life`: admitted (guard passed, category ok); Plan searched the literature for "tree, life".
- `does coffee help exercise performance`: admitted; Plan searched the literature for "coffee, exercise, performance".

What the person notices: a question about biology that happens to use none of the listed words is answered instead of being told this product does not cover it, and a question about pizza is still refused with the same sentence, now in one to five seconds instead of instantly.

## Live evidence on the final head, tasks 2, 3, 4 and 6

CLASSIFIER_PROVIDER=jev, this worktree's `src/` at abead5a, streamed through `core.run.run_streaming`. Every decision below agreed between Jev and the guard tier; no fallback fired.

Task 2, think.ask_back:

- `reflux disease`: asked back, "What would you like to know about reflux disease?", choices "What is reflux disease?", "Are there clinical trials for reflux disease treatment?", "What does recent research say about reflux disease?". No tool ran.
- `What is GERD?`: answered, 15 citations, 28.83 s; `think.ask_back` = proceed (Jev 0.92).
- `Any trials for GERD?`: answered, 14 citations, 18.03 s (four words, so ask_back is never asked).
- `What variants cause it?` with a BRCA1 session memory: answered, 58 citations, bound to NCBIGene:672; no ask_back decision (memory present).

Task 3, think.recent_years:

- `recent papers on statins`: asked "How far back should I search?", choices "Recent papers on statins from the last 12 months?", "... the last 5 years?", "... the last 10 years?". No tool ran.
- Picking `Recent papers on statins from the last 5 years?`: answered, 8 citations, 16.44 s; `think.recent_years` = not_applicable (Jev 0.99). ESearch term `statins AND ("2021/09/25"[dp] : "3000"[dp])`. All five papers searched and all five cited are inside the window, checked by ESummary: 35125240 (2022 Nov), 36103125 (2022 Sep 14), 36958647 (2023 Jul), 37795366 (2023), 38325336 (2024 Feb 6).
- `papers on statins since 2022`: not asked back; Plan searched "statins, published since 2022".

Task 4, plan.literature:

- `papers on caffeine`: wants_literature (Jev 1.0); the literature was searched ("caffeine"), answered with 10 citations, 27.25 s. On the base this question was refused after 15.05 s (a guard timeout).
- `what does the literature say about MTHFR`: wants_literature (Jev 1.0); MTHFR resolved as a gene, so the gene fan-out ran, its own PubMed leg `MTHFR[Title/Abstract]` included; 76 citations, 29.96 s (48.9 s on the base).
- `What is GERD?`: not_literature (Jev 0.99); the disease path ran.

Task 6, one `done` event's `decisions` array, verbatim, from `What is GERD?`:

```json
[
  {"name": "plan.literature", "options": ["wants_literature", "not_literature"], "chosen": "not_literature", "decided_by": "jev", "jev_choice": "not_literature", "jev_confidence": 0.99, "guard_choice": "not_literature", "agreed": true, "fallback_reason": null, "jev_latency_ms": 277},
  {"name": "think.recent_years", "options": ["recent_unbounded", "not_applicable"], "chosen": "not_applicable", "decided_by": "jev", "jev_choice": "not_applicable", "jev_confidence": 1.0, "guard_choice": "not_applicable", "agreed": true, "fallback_reason": null, "jev_latency_ms": 325},
  {"name": "think.ask_back", "options": ["ask_back", "proceed"], "chosen": "proceed", "decided_by": "jev", "jev_choice": "proceed", "jev_confidence": 0.92, "guard_choice": "proceed", "agreed": true, "fallback_reason": null, "jev_latency_ms": 304}
]
```

Latency, time to the `plan` event, the stretch every decision lives in (seconds):

| Question | Before, mean of passes | After, one pass | Change |
| --- | --- | --- | --- |
| What is GERD? | 4.58 | 7.03 | +2.45 |
| Any trials for GERD? | 2.38 | 3.79 | +1.41 |
| papers on caffeine | 8.74 | 6.91 | -1.83 |
| Which diseases are associated with BRCA1? | 4.04 | 4.02 | -0.02 |
| what does the literature say about MTHFR | 5.12 | 2.96 | -2.16 |
| Median | 4.58 | 4.02 | -0.02 (median change) |

The median added latency is -0.02 s by per-question change, and the median itself fell from 4.58 to 4.02 s: inside the one-second budget. Read with care: after-change is one pass each (the run cap), and the base's own passes varied by up to 1.1 s on one question. The one clear cost is the three-word opener (`What is GERD?`): its three opening calls are gathered, and `decide()` waits for the guard tier's pick as well as Jev's, so the slowest guard call sets the wait. Time to answer on the full runs: GERD 29.0 to 28.83 s, trials 27.55 to 18.03 s, MTHFR 48.9 to 29.96 s, caffeine refused at 15.05 s to answered at 27.25 s.

Runs spent: 30 in all. 11 full runs (5 before, 6 after) at about 2 cents each, and 19 runs closed at the `plan` event (10 before, 5 for task 1, 4 after), which pay for no tool or answer call.

Follow-up noticed, not changed: a question asked back through 12.3 or recent_years shows the plan narrative "no tool selected; the question refers to something no earlier turn resolved, so the answer asks which", written for item 7.5's case. It predates this phase for 12.3 and now also shows for "how far back".

## Tasks 2, 3, 4 and 6: what was built

- Task 2, think.ask_back (commit 9f079ce): a one-to-three-word opening question asks `decide(point="think.ask_back")` and, at the same moment, `core.clarify`'s guard-tier writer. The writer no longer decides anything: it always writes a question and 2 to 4 subject-tailored choices (`ClarifyChoices`), and they are shown only on a real `ask_back` pick. No usable pick, a seam failure, or choices that cannot be written (bad reply, failed call, cap hit) all search, the existing fail-open rule.
- Task 3, think.recent_years (commit 44f97dc): `decide(point="think.recent_years")` starts the moment Think starts and runs beside Think's own classification call; on `recent_unbounded` with no range stated, the person is asked "How far back should I search?" with their own question plus "from the last 12 months", "from the last 5 years", "from the last 10 years". Code verifies one value only: a question that states a range is never asked again. `core.breadth_plan.parse_publication_window` reads the range the clicked choice states and ANDs `("YYYY/MM/DD"[dp] : "3000"[dp])` onto every PubMed term the plan builds (topic path and gene or disease path; ClinVar, OMIM and GEO untouched), and the plan narrative names it ("published the last 5 years"). Words about recency ("recent", "latest") no longer become required search words.
- Task 4, plan.literature (commit 4b32994): `breadth_plan._LITERATURE_WORDS` and `asks_for_published_literature` are removed. Think starts `decide(point="plan.literature")` at entry; Plan reads it (it has usually finished) and uses it where it can change the plan, with no gene resolved. A question asked back, a cap hit or a step error cancels it.
- Task 6 (commit abead5a, with the guardrail refusal's done event in 872cac7): every `done` event but the daily-cap decline (which runs before any decision) carries the run's `DecisionRecord`s. The decisions at one step overlap: the guardrail's relevancy runs beside the injection classifier; Think's ask_back, writer and recent_years are gathered; recent_years and literature start at Think entry and run beside Think's classification. Tests pin the overlap by making a decision refuse to answer until the other call has started.
- Prompt-cache discipline: no decision call carries the Think, Plan or Write stable prefix; `decide()` builds its own two messages, and `test_decision_calls_are_separate_and_carry_no_stable_prefix` asserts it. The Think, Plan and Write prompts are unchanged byte for byte.
- A greeting or a question about the product (`_NO_TOOL_QUERY_TEXTS`) plans no search, so it is asked no Think or Plan decision.

## Choices made, for the lead to log in DECISIONS.md (outside this fence)

Each stated as the person using the product would notice it:

- Every decision is described to both models (fixed instruction plus one criterion per option), so a pizza question is judged as a question about pizza rather than by two option names. Alternative rejected: leave the seam as shipped (measured wrong on three of five shapes).
- The choices writer always writes and never decides, so a short question is never asked back on the writer's say-so and never searched because the writer disagreed. Alternative rejected: keep the writer's own ask_back and ask again when it disagrees with the classifier (a second call on the person's clock).
- A question that states its own range is never asked "how far back", even if the classifier says so. Alternative rejected: trust the classifier alone (it said "unbounded" for "papers on statins since 2022" before the decisions were described).
- The ask_back, recent_years and literature decisions run at the same moment as the calls they sit beside, so nobody waits for them in turn; the price is one or two extra guard-tier calls per question (plus Jev's) even when the answer is not needed. Alternative rejected: ask each only when its answer is needed (serial, about a second each).
- No usable pick always fails open: the question is searched, never refused or asked back on a decision nobody made.
- Decisions ride beside the run keyed by its Harness (F-J-01), because `core/state.py` is outside this fence.

## Task 5, plan.resource: nothing wired, by design

`plan_node` makes no runtime choice between the seven tools today. Every question shape gets a fixed plan, decided by what resolved, not by a pick:

- A gene: `cypher_query`, `ncbi_efetch` (gene record, summary, PubMed, ClinVar, OMIM), `pubtator_annotate`, `clinicaltrials_search`; an rs id in the text adds `ncbi_dbsnp` and `litvar2_lookup` (`_build_layer_tool_calls`, `_build_breadth_calls`).
- A disease with no gene: `cypher_query`, MedGen and PubMed through `ncbi_efetch`, `pubtator_annotate`, `clinicaltrials_search`.
- Nothing resolved: one PubMed search (the topic path).
- An accession: `ncbi_efetch` summaries. An isolate question: `pathogen_detection` and the Taxonomy record.

So there is no place where "which of these resources" is chosen at runtime, and per the brief none was invented. Where it would go if one is ever added: in `plan_node`, at the point `planned` is chosen (`_select_planned_tool_call` and the branches after it), as `decide(point="plan.resource", options=tools.catalogue.resource_options())` over the question text, with the chosen tool then verified against what resolved.

Two word rules found on the way that DO decide plan details, recorded for the owner rather than changed, since neither is a choice among the catalogue's tools and the brief forbids inventing a decision point: `breadth_plan.wants_dataset_search` (`_DATASET_WORDS`) decides whether GEO DataSets is searched, and `"recruit" in query_text` in `_build_layer_tool_calls` narrows trials to recruiting ones. Both are candidates for the same treatment `plan.literature` got.

## Findings log

- Base: `git merge --no-edit phase/8.2-classifier-seam` fast-forwarded this worktree to 0bd47c9.
- F-J-01, carrier for decisions across nodes. `core/state.py` is outside this builder's fence, and LangGraph 1.2.9 SILENTLY DROPS a key a node returns that `GraphState` does not declare (probed: a node returned `{"a": 1, "undeclared": [1, 2]}`, the next node saw only `{"a": 1}`, no error). So a new state key cannot carry the run's `DecisionRecord`s from guardrail and think to the done event. Chosen carrier: a `weakref.WeakKeyDictionary` in `core/graph.py` keyed by the run's `Harness` object. `core/run.py` builds a fresh `Harness(trace_id=...)` per run (lines 583 and 715) and every node receives that same instance through `state["harness"]`, so the entry lives exactly as long as the run and cannot leak (the reason `call_budget.py` gives for rejecting a trace-id dict). Follow-up for whoever owns `core/state.py`: a declared `decisions` field would be the plainer carrier.
- F-J-02, two relevancy judges. The guard-tier injection classifier (`guardrail/classifier.py`, left untouched per the brief) ALSO judges `is_off_topic` on every question. So after this change a question that fails the vocabulary allowlist is judged by `decide(guardrail.relevancy)` AND by the classifier's own off-topic field, and either can refuse. For a question that clears the allowlist, only the classifier's field judges, exactly as before.
- F-J-03 (the constraint for every task), the seam never tells either model WHAT is being decided. `decide()` gives the guard tier only "Answer with exactly one of the offered options. Options: ..." plus the question, and `jev_client._build_body` sends Jev a fixed "Read the state and answer with exactly one of the offered options" and a generic criterion per option. The meaning of a decision is carried only by the point key and option names. Measured with CLASSIFIER_PROVIDER=jev before any change, one call each (chosen / Jev / guard):
  - relevancy, `what is the best pizza in Chicago`: on_topic / on_topic (0.44) / off_topic. The pizza question would have been ADMITTED.
  - ask_back, `Any trials for GERD?`: ask_back / ask_back (0.33) / proceed. A full question would have been asked back.
  - ask_back, `What is GERD?`: proceed / proceed / guard reply unparseable.
  - recent_years, `papers on statins since 2022`: recent_unbounded / recent_unbounded (0.79) / not_applicable. A dated question would have been asked which years.
  - literature, `papers on caffeine`: wants_literature / wants_literature / not_literature.
  So the right answer was not expressible from what either model was given, and wiring the points as is would ship wrong decisions. Fix: each decision carries a fixed, code-authored instruction and one criterion per option, sent to the guard in its system message and to Jev in the endpoint's own `instructions` and `criteria` fields. `state` stays the person's bounded text only.
  - Measured after describing, Jev alone, bare question text in `state`, 21 calls: 21 of 21 correct, confidence 0.75 to 1.0. Pizza off_topic (1.0), tree of life on_topic (0.87), coffee on_topic (1.0), `Any trials for GERD?` proceed (0.97), `reflux disease` ask_back (1.0), `papers on statins since 2022` not_applicable (0.99), `recent papers on statins` recent_unbounded (1.0), `papers on caffeine` and the MTHFR question wants_literature (1.0), `What is GERD?` not_literature (0.99).
  - FENCE CROSSING, stated rather than hidden: Jev's `instructions` and `criteria` are built inside `harness/jev_client.py`, which is outside this builder's fence. The only in-fence alternatives were putting the decision's instruction into `state` (which breaks the brief's "state is bounded user text, never system instructions" and mixes instruction with data) or duplicating `call_jev`'s wire parsing inside `decide.py` (two copies of an undocumented wire shape). Chosen: one ADDITIVE change to `jev_client.py`, two optional keyword arguments on `call_jev` and `_build_body` whose defaults reproduce builder D's generic text byte for byte, so every existing caller and test is unchanged. The lead can reject it by reverting that one commit's jev_client hunk; the decisions then fall back to being undescribed to Jev.
- F-J-04, a trap in `decide()`'s record, handled in the caller rather than changed: when neither model produces a usable pick, `chosen` is the FIRST offered option, and when Jev failed first, `fallback_reason` carries Jev's reason (say "timeout") rather than "no_usable_pick". For `think.ask_back` the first option is `ask_back`, so a caller trusting `chosen` would ask EVERY short question back whenever both models were down, and the default guard-only mode in the unit-test stubs does exactly that. `core/graph.py`'s `_usable_choice` reads whether a pick exists from `jev_choice` and `guard_choice` and fails open when neither does.
- F-J-06, fixed in `decide.py`: `_parse_guard_choice`'s fallback was a bare substring test. Found by the guardrail node's own integration test: the test stub answers every guard call with the injection classifier's JSON, and the parse read "off_topic" out of `"is_off_topic": false`, so a question was refused as off topic on a reply that said the opposite. It also returned whichever option was listed first when a reply named two. Now it matches an option only as a whole token and only when exactly one offered option is named; anything else is no usable pick.
- Environment note: a file `src/system_03_search_agent/core/graph 2.py` (570,221 bytes, timestamp 03:28 today) appeared in this worktree while graph.py was being edited. It is a byte copy of an intermediate graph.py, the shape of a desktop sync conflict copy, git ignores it (not in `git status`), and nothing imports it. Left in place, not deleted, per the file-protection rule; the SessionStart duplicate-copy hook is the thing that clears these.
- Task 3, the publication-date limit verified live against ESearch before any code (2026-09-25): `statins` alone matched 76,272; `statins AND ("2021/09/25"[dp] : "3000"[dp])` matched 15,282 and ESearch's own `querytranslation` read it back as `... AND 2021/09/25:3000/12/31[Date - Publication]`. The `[Date - Publication]` spelling and the bare `2021/09/25:3000[dp]` spelling translate identically, and `BRCA1[Title/Abstract] AND ("2025/09/25"[dp] : "3000"[dp])` read back as `"BRCA1"[Title/Abstract] AND 2025/09/25:3000/12/31[Date - Publication]`, 1,625 hits. So the limit is a plain clause ANDed onto the term the planner already builds, and it works on the gene path and the topic path alike.
- BASELINE, the merged base 0bd47c9 before any change, runner `live_run.py` in the scratchpad (this worktree's `src/` first on `sys.path`, env loaded without printing, CLASSIFIER_PROVIDER=jev, which the base never reads).
  - Full runs through `core.run.run` (buffered), time to answer in seconds: `What is GERD?` 29.0, `Any trials for GERD?` 27.55, `Which diseases are associated with BRCA1?` 33.14, `what does the literature say about MTHFR` 48.9. `papers on caffeine` REFUSED after 15.05 s with no guard event at all: the guard tier's own call ran out its 15 s step budget. 5 live runs spent.
  - Time to the `plan` event through `core.run.run_streaming`, the run closed at that event so no tool or answer call is paid for, two passes each: GERD 4.58 (pass 1 was the guard 15 s timeout again, 15.06, not counted), trials 2.92 and 1.83, caffeine 8.59 and 8.88, BRCA1 4.39 and 3.69, MTHFR 4.51 and 5.73. Per-question means 4.58, 2.38, 8.74, 4.04, 5.12: MEDIAN 4.58 s. This is the stretch every decision in this change lives in (guardrail, think, plan), so it is the number the one-second budget is judged on; the full time to answer swings by tens of seconds with the tools and cannot resolve one second.
  - F-J-05, pre-existing and not caused by this change: 2 of 15 guard-tier classifier calls on the base hit the 15 s guard step budget and ended the run (one refusal, one step error). And the 12.3 guard clarifier asked `papers on caffeine` back on one of three passes and not on the others: the same three words got an answer or a question depending on the run.
- G-035 (task 7) verified live 2026-09-25: `https://www.ncbi.nlm.nih.gov/taxonomy/562` (the form `tools/ncbi_eutils_actions.py` line 507 cites) returns 200 with `<meta name="ncbi_uidlist" content="562">`, title "Escherichia coli - Taxonomy - NCBI", and its record title links to `/Taxonomy/Browser/wwwtax.cgi?id=562`. `https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=562` (the row's form) returns 200 with the focal node `<a title="species" href="?command=show&mode=node&id=562">` wrapping `<strong>Escherichia coli</strong>`, under genus id 561. Both are taxonomy id 562, the same record.
  - Changed G-035's must-cite to `https://www.ncbi.nlm.nih.gov/taxonomy/562`, that row only (commit 364e2b9). `rubric_grader.citation_satisfies` treats it as a record-level constraint, so only that exact record satisfies it. `tests/system_03_search_agent/eval`: 45 passed, 1 skipped.
  - Follow-up for the golden set's owner, not done here (outside the fence): `eval/golden/build_dataset.py` line 413 still mints the Browser form when a row is verified, so a rebuild of the set would put the old form back into G-035.
