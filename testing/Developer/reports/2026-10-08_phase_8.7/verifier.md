# Phase 8.7 fresh verifier

Base checked: HEAD 20a8e246 (origin/phase/8.7-answers-sooner merged with origin/develop). Results are written as each is established.

## Results

### Old client stream against develop (question 3, own probe)

Probe: the offline write step (`write_node` on the five-disease `_write_state` fixture, fake writer replying the `ANSWERING` text, fake Jev, `SYNTH_MODEL=z-ai/glm-5.2`, `CLASSIFIER_PROVIDER=jev`, `PER_QUERY_COST_CAP_USD=0.25`), run once on a `git archive` of origin/develop (599c6e67) and once on HEAD with `RequestContext(surface="rest_sse")` (no `reads_placement`), three depths by three scenarios (Jev picks neither, Jev picks a lead, writer raises). Every event dumped with `model_dump_json`, timestamps and elapsed fields removed.

- Writer failure: identical in all three depths (3 events each).
- Jev picks neither: the token sequence is identical; NOT byte-identical. Two differences, pasted from the diff (Researcher):
  - citation `claim_text` join order reversed. Develop: `"NCBIGene:672 is associated with disease name number 1 Disease MedGen:C1, name: disease name number 1"`. Branch: `"Disease MedGen:C1, name: disease name number 1 NCBIGene:672 is associated with disease name number 1"`. Same words, listing row first.
  - `done.decisions` now carries the `write.lead_sentence` record and the cost grows by the Jev call (`2.219e-05` to `4.219e-05` with the fake Jev cost).
- Jev picks a lead: the lead sentence moves above the count line (the phase's intended change, card 2).
- Validated every branch frame against develop's own `contracts/events.py`: `accepted 167 rejected 0`. `grep -c '"placement"'` over every branch dump: 0 in each file.
- Verdict on the sub-question: an old client gets develop's stream shape and order, every frame valid under develop's contract, no `placement` key. It is not byte-identical: content changes the phase makes for every client (lead decision, chip word order) reach old clients too. None of these breaks or reorders an old client's layout. Not worse.

### Suites at HEAD 20a8e246 (own runs, one at a time, `-m "not integration"`)

- core: 1478 passed, 56 skipped, 1 deselected, 2 warnings in 58.52s
- synthesis: 753 passed, 10 skipped, 1 xfailed in 3.75s
- adapters: 866 passed, 2 warnings in 33.34s
- contracts: 214 passed in 0.27s
- harness: 448 passed in 23.32s
- guardrail: 347 passed in 58.23s

Green suites are part of what is under review, not evidence on their own.

### Frontend gates (own run)

- `npx vitest run src/hooks src/components/screens src/lib`: Test Files 39 passed (39), Tests 347 passed (347)
- `npx tsc --noEmit -p .`: exit 0

### F-8.7-A04 (open): worse than develop for the web app, confirmed by own probe
- Severity: minor (as filed), but it is a property develop has and this branch loses on the main surface
- What: for a client that sends `reads=placement` (the web bundle and the new command line), a citation the early listing sent keeps only the listing row's words; the summary sentence's checked words (card 57) never reach the chip. An old client and develop show both.
- Reproduction: the same offline write step as above, Researcher, Jev picks neither. Citation `cq-completeness-1`:
  - develop: `'NCBIGene:672 is associated with disease name number 1 Disease MedGen:C1, name: disease name number 1'`
  - branch, no `reads`: `'Disease MedGen:C1, name: disease name number 1 NCBIGene:672 is associated with disease name number 1'`
  - branch, `reads=placement`: `'Disease MedGen:C1, name: disease name number 1'`
  - Control, a Gene row whose whole summary is the listing row (card 57's own example): the chip is the same full summary on develop and on both branch clients, so the loss bites only where the listing row is shorter than what the sentence was checked against (a name row, a title row).
- Why it matters: a reader who opens [1] under a summary sentence on the web app sees the record's name row, not the words that sentence was checked against. Develop shows them. This is one item where the web app is worse than develop.
- NOT FIXED

### The gap clause (question 2, own loop-level probe)

Probe: `write_node` at HEAD over MedGen records built by the real row builder (`_ncbi_efetch_output_to_structured_fields`, "medgen_summary"), `_clinical_features_asked` True, fake writer, fake Jev, `reads_placement=True` unless said. Pasted summary lines:

| Case | Opening line |
|---|---|
| V1 one record read, lists none | `Found 1 medgen record: Malignant tumor of breast [1], and its MedGen record lists no clinical features.` |
| V1p same, Plain language | `I found 1 condition on this topic [1], and its MedGen record lists no clinical features.` |
| V2 an unrelated PubTator search timed out | `Found 1 medgen record: Malignant tumor of breast [1].` |
| V3 second record's features never read | `Found 2 medgen records: Malignant tumor of breast [1] and Breast carcinoma [3].` |
| V4 second record lists a feature | `Found 2 medgen records: ... [1] and Breast carcinoma [3].` (no clause; listing shows `Breast lump [4]`) |
| V5 a shown gene row's description gives features | `Found 1 medgen record and 1 gene record: ... [1] and BRCA1 [3].` |
| V6 a shown gene row with identity fields only | no clause (the gene has no "lists none" statement) |
| V7 the record carries a definition | `Found 1 medgen record: Malignant tumor of breast [1].` |
| V8 two records, both read, both list none | `..., and none of their MedGen records lists clinical features.` |
| V9 a "Finding"-typed record, read, none | no clause |
| V10 V1 with Jev picking a model lead | clause kept, true |
| V11 V1 for an old client | clause present, same words |
| V12 the MedGen search itself timed out | `Found 1 medgen record: Malignant tumor of breast [1].` |
| V13 total 3 but the feature list empty (partial read) | no clause |

Result: the opening line said "lists no clinical features" only in V1, V1p, V8, V10 and V11, each a state where every counted record was fetched, read and listed none, every search finished and nothing shown carries prose. With anything shown carrying a non-identity field (V5, V7), a search not finished (V2, V12) or a field never read (V3, V13), it was not said. Answer to question 2: no, not in any state I could build.

### Gap clause findings J01, J02, A02, A03, A13: own mutations (each restored, `cmp` clean)

Run over `synthesis/test_first_sentence_gap.py` and `core/test_write_answers_sooner.py` (58 tests):

| Mutation | Result |
|---|---|
| MA: `records_lack_field` ignores `every_search_finished` (A02) | 2 failed, 56 passed |
| MB: per-record "lists none" requirement removed (J02) | 3 failed, 55 passed |
| MC: every non-asked field treated as quiet (J01, A03) | 5 failed, 53 passed |
| MD: `_asked_field` passes `every_search_finished=True` (A02, the loop half) | 2 failed, 56 passed |
| ME: one-record clause back to ", which does not give clinical features" (A13) | 4 failed, 54 passed |
| MF: row fields not checked (J01 row half) | 3 failed (`test_j01_a_definition_on_the_record_row_keeps_the_clause_unsaid`, `test_a03_a_shown_record_that_is_not_counted_still_counts`, `test_a_definition_on_the_record_keeps_the_count_line_unchanged`) |
| MG: only counted findings checked | 5 failed |

Verdict: J01, J02, A02, A03, A13 fixed, each by the loop-level probe above and by a test that goes red when its property is broken.

### Option B is live under develop's writer (observation, own probe)

J03 and A05 call the side-by-side second draft dormant. That holds only at Opus's price. With `SYNTH_MODEL=z-ai/glm-5.2` and a 25-cent cap, each draft's bound is about $0.025 (own probe: `synth z-ai/glm-5.2 price (6.9e-08, 4.3e-06) estimate_no_prompt 0.025`), so two fit and the second draft starts beside the first on develop.

Probe: a paper question built through the real PubMed row builder (`pubmed_abstracts`, three titles with abstracts), glm price, cap 0.25. Call order:

- develop: `['first', 'first_done', 'second:CORRECTION'] cost 0.00626 trust answer`
- branch, old client and web: `['first', 'second:REQUIREMENT', 'first_done'] cost 0.00626 trust answer`

Same outcome and cost in this fixture, and the reply is the same. What changes on develop: the completeness draft is now the "COMPLETENESS REQUIREMENT" prompt written blind, beside the first, in place of develop's "COMPLETENESS CORRECTION" prompt written after it. The live check ran only with Opus, where this path never runs, so its answer quality with glm has no live measurement. A draft that turns out unneeded is cancelled and metered at the writer's 4,000-token output ceiling (about $0.017 at glm's price), which develop never spends. Filed as unsure, not as worse: nothing in my probes got worse.

### J04 and A06, the cap as a bound (own probe and mutations)

Probe: the five-disease write step with the listing unable to cite finding 4 (so a completeness draft is needed), cap 0.25, a fake provider that reports the prompt's default-encoder count times a ratio and the given completion tokens (an honest worst case, every call writing its whole 4,000-token ceiling).

| Setting | develop | branch |
|---|---|---|
| Opus, ratio 1.0, 4,000 out | `[first, second]`, total 0.2439, answer | `[first]`, total 0.1217, ask, repair cap note |
| Opus, ratio 1.3, 4,000 out | `[first, second]`, total 0.2690 (over the cap) | `[first]`, total 0.1342, ask, repair cap note |
| Opus, ratio 1.0, 1,000 out | total 0.1239, answer | total 0.1239, answer |
| Opus, ratio 1.3, 1,000 out | total 0.1490, answer | total 0.1490, answer |
| glm, ratio 1.0, 4,000 out | total 0.0358, answer | total 0.0358, answer |
| glm, ratio 1.3, 4,000 out | total 0.0363, answer | total 0.0363, answer |

Develop goes over 25 cents with Opus (0.2690); the branch never does, and says so with the repair cap note when it refuses. Under develop's glm writer the branch behaves exactly as develop. Bound per call at glm (own probe): synth 0.025, plan 0.0125 (0.0475 for a 120,000-character prompt), guard 0.01 (develop 0.003, the new Jev floor). A glm question here costs about 4 cents, so no glm question comes near a 25-cent cap.

Mutations (each restored, `cmp` clean), over harness plus the two write test files (529 tests):

| Mutation | Result |
|---|---|
| C1: the prompt bound ignored, tier estimate used | 2 failed |
| C2: the bound prices output at 2,000 tokens | 3 failed |
| C3: in-flight calls not counted | 1 failed |
| C4: no prompt margin (raw default-encoder count) | 1 failed |
| C5: `_dispatch_tier_call` checks without the prompt | 1 failed |

Caveat: the input side is still an estimate (default encoder plus 35 percent, floored at one token per three characters). No tokenizer for the answering model is installed, so "bound" is proven for the output side only. Calls checked without a prompt (Cypher generation, the coordinator reader, `harness.decide`) are priced by profile, not bound. Verdict: J04 and A06 fixed as far as an offline probe can show. Under develop's glm settings this changes nothing a person sees.

### A01 and A14, placement opt-in (own probe and mutations)

- Own probe (above): a request without `reads=placement` gets no `placement` key in any frame (0 in every dump), the listing after the summary, and every frame validates under develop's own contract (167 of 167). So an installed command line keeps working (A01) and an older web bundle reads the answer in develop's order (A14).
- Mutations (restored, `cmp` clean), over contracts, adapters/web_sse and `test_write_answers_sooner.py` (396 tests): P1 a None `placement` serialized: 16 failed. P2 every request treated as reading placement: 1 failed. P3 any `reads` value opts in: 1 failed.
- The web bundle declares it in one place (`frontend/src/lib/api.ts`, `READS_PLACEMENT_QUERY = "reads=placement"`); no other `POST /v1/query` call site in `frontend/src` outside tests.
- Verdict: A01 and A14 fixed.

### J05, J07, J09 (own mutations and reads)

- J05: removing `citations = [sent_by_id.get(c.citation_id, c) for c in citations]` (core/graph.py:14475): 1 failed (`test_the_answer_keeps_each_early_citation_exactly_as_it_was_sent`). Removing the `_MARKER_PATTERN.search(sentence)` filter (core/graph.py:12631): 1 failed (`test_a_sentence_without_a_marker_is_never_offered_to_lead`). Fixed. Note: the first protection is the line that causes A04.
- J07: read, documentation only. `contracts/events.py:435`, `frontend/src/lib/events.ts:200`, `AnswerScreen.tsx:1453` and `visualizations/Schema_visualization.md:233` now say the count line is "summary" and the notes are "listing", matching the stream my probe printed (`tok summary claim 'Found 5 disease records: ...'`, `tok listing note '...'`). Fixed.
- J09: the writer-failed note added to `HIDDEN_NOTE_PATTERNS`: `Tests 1 failed | 6 passed (7)` in `AnswerScreen.listingFirst.test.tsx` ("shows the writer-failed note under records sent early, with the count line above them"). Restored, `cmp` clean. Fixed. My server probe confirms the server order the arm feeds: listing rows, citations, `tok summary claim 'Found 5 disease records ...'`, `tok listing note 'Note: the written summary could not be finished ...'`, trust outcome `ask`.

### Citation numbers shown early (question 3, own probe)

Checker over every dumped stream (web client: five-disease fixture in two depths by three scenarios; a paper question built through the real PubMed row builder in two depths with option B firing; old client: three depths by two scenarios): each citation id sent once, each display number owned by exactly one citation id, every `[n]` in a token's text matches a citation with that number among the token's `marker_ids`, every marker id gets a citation. Result: `problems none` in all 16 streams. Example, paper question, web client: listing `[1] [2] [3]` sent with citations `ne-pm-1..3` before the writer; the summary's count line cites `['ne-pm-1', 'ne-pm-2', 'ne-pm-3']` as `[1] [2] [3]`; the prose's new abstract citation is `ne-pm-6` as `[4]`, sent after. Holds.

### Stop after records (question 3, tests plus own mutation)

- `test_run_registry_stop_mid_write.py` and `test_run_registry_stop_after_done.py`: 15 passed. S2 pins nothing after the `cancelled` error, S3 recorded as stopped (`refuse`), S4 and S8 charged once.
- Own mutation: `write_node`'s `finally` no longer drops the second draft. S8 goes red on the right assertion: `AssertionError: tasks still running after Stop: [<Task pending ... _dispatch_tier_call() ...>, <Task pending ... Harness.call_tier() ...>]`. Control mutation (a harmless `await asyncio.sleep(0)` before the early listing): 15 passed. Restored, `cmp` clean.
- This matters more on develop than the reports assumed: with glm the second draft does start (above), so S8's case is live there.
- Run-registry code is unchanged by the phase (`git diff --stat` lists no `run_registry.py`). Holds.

### Hidden instructions without the reader pass (question 3)

- Guardrail code is untouched (`git diff --stat origin/develop...HEAD -- src/system_03_search_agent/guardrail` is empty); guardrail suite 347 passed; live check: query 88 refused 2 of 2 (read, not re-run).
- On develop, the reader pass never refused anything. Its only outcomes are a parsed reader finding or `_degraded_reader_finding`, and no `raise` or refusal path exists in `coordinator_worker.py` beyond a JSON type check. So removing it cannot un-refuse a question. `_sanitized_citeable_row` is not in the diff. Holds, by read plus the unchanged-code check.

### F-8.7-A07 (open): the lead decision adds Jev's wait to every answer, worse than develop in time (own probe)

Offline write step, Researcher, old client, Jev faked with a delay, write step wall time:

| Jev delay | develop | branch |
|---|---|---|
| 0 s | 0.01 s | 0.02 s |
| 1 s | 0.01 s | 1.02 s |
| 3.9 s | 0.00 s | 3.52 s |
| 10 s | 0.00 s | 3.52 s |

Develop sets `CLASSIFIER_PROVIDER=jev`, so every answer with a count line and a grounded model sentence waits on one Jev decision before its summary is sent: about Jev's latency, at most 3.5 s, and on a slow or failed pick the count line leads exactly as on develop. For the web app the records are already on screen; for an old client, the whole answer waits. No live Jev latency for this decision is recorded in `live/streaming_runs.jsonl`. Offsetting gains on other questions (the 6 s PubTator cut, no reader pass on paper questions) do not cover non-paper questions. Worse than develop in time to summary, bounded at about 3.5 s.

### Items left open (question 4), each against develop

| Item | Against develop | How established |
|---|---|---|
| A04 chip loses the sentence's checked words | Worse, web app and new command line only | Own probe, section above |
| A05 / J03 option B unreachable at 25 cents | Not worse. At Opus it never runs; at develop's glm it runs (two drafts fit), and my probes show the same outcome and cost as develop | Own probe, section above |
| A07 wait on the lead decision | Worse in time: Jev's latency, at most about 3.5 s, on every answer with a count line and grounded prose | Own probe, section above |
| A08 PubMed search still 35 s | Same as develop: `_NCBI_EFETCH_ACT_TIMEOUT_SECONDS = 35.0` on both, `litvar2_lookup` 20.0 on both. PubTator 20.0 to 6.0 is the owner's option C; a PubTator call taking 6 to 20 s now yields its "did not finish" note in place of its sources | Own read of both trees |
| A09 / J06 dead `_prefetch_answer_names` | Not worse for a person: one definition at core/graph.py:8656, no call site (`grep -c "_prefetch_answer_names("` is 1); the comparison arms stay vacuous | Own grep |
| A11 records kept after Stop with no trust marks | New state, not a regression: develop shows no records after Stop. The screen says "No summary was written. The records found before you stopped are below." (RunProgress.tsx:553). Owner's 2026-09-27 rule. Unsure whether a high-risk row without its tag misleads | Read |
| A12 frontend fixtures send the count line as "listing" | Not worse for a person. Still true in `App.stopUntilAnswer.test.tsx:174` and `useRunView.placement.test.ts:72`; `AnswerScreen.listingFirst.test.tsx` was corrected. App stop and saved-answer tests: 3 files, 21 passed | Own grep and run |
| A15 Researcher numbers 1, 3 then 2, 4 | Same as develop: interleaved Gene and Disease rows print `[1] [3]` under genes and `[2] [4]` under diseases on both | Own probe on both trees |
| J08 repair refused at 25 cents | Not worse under glm: the repair is admitted (total 0.0358 and 0.0363, same as develop). At Opus it is refused with its note where develop went to 0.2690 | Own probe |

### Precondition the verdict rests on (could not verify)

The brief says develop sets `SYNTH_MODEL=z-ai/glm-5.2`. The code and the architecture document say the opposite: `harness/tiers.py` ("Develop sets no `SYNTH_MODEL`, so this default reaches develop when the phase merges") and `docs/architecture/Model_architecture.md:62` ("develop sets no override", settings read 2026-09-25). I did not read develop's environment. If develop has no `SYNTH_MODEL`, merging switches develop's writer to Opus before the owner's go, and with a cap below about $0.14 every question loses its summary (F-8.7-A10). The lead must confirm the variable on develop's API service before merging.

### Lint gates

`ruff check` (whole repository): "All checks passed!". `isort --check-only src tests`: exit 0. `git status --short` after every probe: only `?? frontend/node_modules`.

### F-8.7-V01: The token contract's serialization schema became empty
- Severity: minor (unsure it reaches anyone; no consumer found)
- Regression of: F-8.7-A01 (commit 95680687, the `_omit_absent_placement` wrap serializer on `TokenPayload`)
- What: `TokenPayload.model_json_schema(mode="serialization")` is `{}` on HEAD; on develop it is the full object schema (`{"additionalProperties": false, "properties": {"text": {"maxLength": 1000, ...`). The wrap `model_serializer` returns `Any`, so pydantic can no longer describe what a token serializes to. The validation schema is intact (`placement`: `anyOf [enum listing|summary, null]`, default null).
- Reproduction: `python -c "from system_03_search_agent.contracts.events import TokenPayload; print(TokenPayload.model_json_schema(mode='serialization'))"` prints `{}` on HEAD and the full schema on a `git archive` of origin/develop.
- Why it matters: the public contract (Schema_visualization.md calls it the contract for agents and the command line) can no longer be exported from the model for a token's serialized shape. I found no consumer today: the web API's OpenAPI document does not include `TokenPayload` (`TokenPayload in openapi: False`), `Event`'s payload is untyped in its schema, and nothing in `src` or `tests` calls the serialization schema. No person sees it.
- NOT FIXED

## What I verified versus what I only read

- Own probes or own mutations: J01, J02, A02, A03, A13 (loop-level probe, 7 mutations); J04, A06 (cap probe on both trees, 5 mutations); A01, A14 (old-client stream on both trees, develop-contract validation, 3 mutations); J05 (2 mutations); J09 (frontend mutation); citation numbering (checker over 16 streams); Stop (S1 to S8 run, 1 mutation plus a control); option B under glm (probe on both trees); A04, A07, A15, J08 against develop (probes on both trees); V01.
- Read only: J07 (comments), A11 (screen text), A08 and A09 (constants and grep), hidden instructions (guardrail untouched, reader pass never refused), develop's `SYNTH_MODEL` (not read; the brief and the code disagree).
- Not verified at all: any live model behaviour, Jev's live latency for the lead decision, glm's answer quality with the "COMPLETENESS REQUIREMENT" second draft.

## Verdict

DO NOT MERGE as the bar is worded. Two open items are worse than develop under develop's own settings:
- F-8.7-A04: a web-app chip under a summary sentence loses the words that sentence was checked against.
- F-8.7-A07: every answer with a count line and grounded prose now waits on one Jev decision, at most about 3.5 s, before its summary.

Neither has an owner decision in DECISIONS.md or the tracker. Both are minor and look like owner-level trade-offs: records arrive sooner and the first sentence can answer. If the owner accepts both trades, nothing else I found is worse than develop. Every fixed finding (J01, J02, J04, J05, J07, J09, A01, A02, A03, A06, A13, A14) is confirmed fixed. One minor finding sits inside a fix-round commit, F-8.7-V01, Regression of: F-8.7-A01. It has no effect a person can see, but it fires the review loop's stop condition. Before any merge, confirm `SYNTH_MODEL` on develop's API service.
