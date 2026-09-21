# Set 9 builder report, 2026-09-13

Live log, appended as findings are established. Final sections are filled at the end.

## Findings log (in order established)

- F9-01 (ownership gap). `plain_language` cannot reach the agent from the web UI by editing `contracts/query.py` alone. Two more files constrain the value and neither is in set 8's or set 9's list: `adapters/web_sse/app.py` (`CreateRunRequest.audience_depth` is a three-value Literal, so the POST would 422) and `auth/preferences.py` (`_ALLOWED`, so a saved preference would be discarded). Plan: one additive enum value in each, named here.
- F9-02 (notes rendered as claims, the 9.8 root cause). `useRunView.ts` `SYSTEM_NOTE_PREFIXES` lists five note prefixes; `write_node` emits at least three more notes that match none: `_build_incomplete_answer_note` ("Note: one further gene record was found ..."), `_build_structured_fallback_note`, and the partial-answer note is listed. So "one further gene record" rendered as an uncited grey claim. Prefix matching is the defect class; a typed `kind` on the token closes it.
- F9-03 (notes render first). `AnswerBody` renders `systemNotes` as amber `Notice` boxes ABOVE the claims grid, so every disclosure reads before the answer it qualifies.
- F9-04 (length targets vs the grounding gate). `claim_introduces_no_new_content` requires every content token of a claim to come from the cited finding, its field, CURIE, entity type or the open part of the question. A "what it means" or "first-principles background" sentence introduces words no finding carries, so the gate strips it. The directives can ask for 250 or 700 words; the gate, unchanged, decides how much survives. Measured counts are in the live-run table.
- F9-05 (screenshot table not expressible). The reference screenshot's "variant, associated disease" table cannot be built from this graph: `tools/cypher_templates.py` records that the graph has no variant-to-disease edge, and the variants template returns the variant records alone. What one SequenceVariant record carries beside its name is its own clinical significance, so the code-built table is "Variant | Clinical significance", with the second cell read verbatim from the record the row cites. It renders only when every record in the group carries that field; otherwise the group is a list.
- F9-06 (first-sentence defect mechanism). "BRCA1 (gene symbol BRCA1 [1]. These are ..." comes from the model writing "BRCA1 (gene symbol BRCA1 [1]) is associated with the following diseases." The unmarked tail ") is associated with ..." is stripped, and T-6.2-15's middle-strip rule does not fire for a strip at the END. The kept prefix keeps an open parenthesis and loses the verb. The next sentence opens on "These are" with its antecedent gone. Fixed in `run_grounding_pass` by two stricter whole-sentence drops (unbalanced parentheses; a bare-pronoun opener whose previous sentence did not survive). The findings tail re-lists what is dropped, so no source is lost.
- F9-07 (suite triage, first run after wiring). Of 10 failures in core, synthesis, contracts and eval: two are mine and were requirement changes (the tail-note tests used `researcher`, where the listing now replaces the tail note). One is set 8's think-node mutation arm (`test_p2_goes_red_when_the_flagship_resolves_nothing`). Seven (plan, act, run and trust tests in `test_graph.py` and `test_run.py`) pass when run alone, so they are order or concurrent-edit effects.
- F9-08 (vitest triage, first full run after the frontend edits). Most failures took about 15 seconds each: load timeouts under a machine shared with set 8. `railCollapsePremise.test.tsx` failed 15 of 20 in the full run and passed 20 of 20 alone. Two were real. (a) The depth group's accessible name came from its visible label, now "Answer mode", so the query `/depth/i` found nothing. The group now carries `aria-label="Answer mode, audience-level depth"`. (b) `AnswerScreen.thread.test.tsx` asserted that no claim renders while a run is in flight. Item 9.6 changes that requirement: the claims stream under the progress. The test is updated and named in the files list.
- F9-09 (design gap, named). No design-system card or prototype rule styles a bulleted list inside an answer. The Researcher list uses `.answer p` body text, the browser's own marker, and the 6px gap the refusal block already uses. Headings transcribe `.answer .ah`, the table transcribes `.rtab`, bold transcribes `.answer p strong`. The trust line reuses the pills' 12.5px and the refusal explanation's `inkMuted`. Notes use the refusal explanation's 13.5px `inkMuted`. The two info cards reuse `PersonaInfo`.
- F9-10 (Stop mid-stream, mutation-proven). New e2e arm `stop works while the answer is streaming in` in `e2e/query-stream-and-stop.spec.ts`: 6 of 6 in that spec passed. With App's streaming branch disabled (`if (false && ...)`), that arm went red on `getByTestId('streaming-answer')` not found. The mutation was reverted.
- F9-11 (trust line moved to `DonePayload.trust_line`). The first cut put the line on `TrustSignalPayload.summary`. The MCP surface types its output `trust_signal` as that model whole, under a pinned key allowlist, so the new key reached the MCP response. Set 8's full run caught it: `adapters/mcp/test_phase_4_1_premise.py::test_an_operator_allowlisted_caller_still_gets_no_cost_field`. The allowlist and the test are unchanged. The line now travels as optional `trust_line` on `DonePayload`, which MCP does not project and which already carries `trust_outcome`, the verdict the line puts into words. A structure test asserts `summary` is absent from the answer-scope signal.
- F9-12 (pre-existing lint, not set 9). `ruff check .` reports four findings in the committed `testing/Developer/scripts/local_loop_run.py`: three I001 and one BLE001. They predate this set and are left for the main agent. My sibling script's two RUF100 findings are fixed.
- F9-13 (MCP input enum is pinned by the locked specification). Adding `plain_language` to the MCP tool's `audience_depth` Literal failed `adapters/mcp/test_phase_4_1_premise.py::TestSchemaFidelity::test_input_schema_matches_section_13_2`. That test pins the enum to Section 13.2 of the locked technical specification. Reverted: MCP keeps the three specified values. `test_audience_depth_values.py` pins that. Widening MCP is a locked-spec decision for the main agent and the product owner. The web request model, preferences, GraphQL and the CLI accept `plain_language`.
- F9-14 (live runs: what they show).
  - The cited source set was identical on every run: all 6 BRCA1 runs across both modes (6 ids), and all 3 GCK Researcher runs (15 ids).
  - Every claim, list item and table row carried a marker in all 9 runs.
  - Plain language came to 108 to 117 words in 2 to 3 prose paragraphs, against a 250-word target. Researcher came to 162 to 228 words of prose plus an 11-item code-built listing, under 5 to 6 headings, against a 700-word target. This is F9-04 measured: the model writes the requested explanation paragraphs, and the grounding gate, unchanged, strips every sentence that introduces words no finding carries. Reaching the targets needs either a product decision on background text or more retrieved content per answer. The gate cannot be loosened to get there.
  - GCK in Researcher took the structured fallback in 2 of 3 runs (the model's prose grounded nothing), so the answer was the code-built listing alone.
  - GCK run 3's `trust_line` is null. That run started while I was moving the field from the trust signal to the done event (F9-11), so it is not a product result. A recheck run is below.
- F9-15 (seen in live runs, not set 9's to fix).
  - Layer 3 citations (clinical trials, literature) carry `source_id: "unknown"`. They go through the generic citation literal path, which is the Layer 3 branch set 8 is about to add to `_citations_from_grounded_claims`.
  - Some GCK variant findings have a URL as their representative value, so the listing shows "https://www.ncbi.nlm.nih.gov/clinvar/variation/1179956" as a list item. That value choice is `_pick_representative_field`'s.
  - Each live run logs `CallerIdentityRequired` from interaction capture, because the script passes no `owner_id`. This is a script artifact; the answer is unaffected.
- F9-16 (the table cannot fire on this graph). A live read of one SequenceVariant node (`MATCH (v:SequenceVariant) RETURN v LIMIT 1`, read-only) returned exactly `id`, `name`, `xrefs`, `source`, `agent_type`, `source_url` and `knowledge_level`, with no clinical significance. Together with F9-05 (no variant-to-disease edge), no two-column mapping exists in the variant records this graph returns. The table branch (`answer_layout.TABLE_COLUMNS`, the `table_header` and `table_row` kinds, and AnswerScreen's `.rtab` rendering) is built and fixture-tested but never renders live today. Variants render as a list. A real table needs a second retrieved field, from Layer 2 ClinVar or a graph re-ingest, which is outside set 9.
- F9-17 (frontend mutation proofs, run by script, each file byte-compared after restore). `set9AnswerStructure.test.tsx`:
  - M1, the note-kind branch removed: 4 arms red.
  - M3, `done.trust_line` ignored: the trust-line arm red.
  - M4, the notes block removed: the notes arm red.
  - M2, the 9.8 arm: removing the kind-less "Note:" fallback alone left it green, and removing the "Note: one further" prefix alone left it green. Removing both turned it red. Two independent controls guard it, and the docstring says so rather than claiming one.

  `DepthControl.test.tsx`:
  - D1, a third option added: red.
  - D2, `disabled={false}`: red.
  - D3, legacy mapping swapped: red.

  Both files pass again after restore.
- F9-18 (contradiction on one screen, found while reading hand-test 12, fixed). For an `ask` answer, the status strip still read "Single source, not independently confirmed" directly above the new trust line "Based on 4 sources, not yet confirmed". When the run carries a trust line, the status word for `ask` is now "Answered" in the same warn tone, and the caution is stated once, in the line. A run with no trust line keeps the old word. Pinned by a new arm in `set9AnswerStructure.test.tsx`. The "4 sources" is honest but worth a product-owner look: `ask` means a high-stakes claim rests on a single independent origin, while the answer as a whole draws on four databases.
- Note on F9-05: its "what one SequenceVariant record carries beside its name is its own clinical significance" was an assumption, corrected by F9-16's live read. The log is append-only, so it is left as written.

## Files changed

Backend, set 9's own:
- `src/system_03_search_agent/synthesis/answer_layout.py` (new): parses the model reply into paragraphs and `##` headings, maps survivors back to paragraphs, runs the deterministic heading check, picks bold terms, and holds the one table mapping.
- `src/system_03_search_agent/synthesis/grounding.py`: additive `sentences` and `sentence_origins` on `GroundingResult`, plus two stricter whole-sentence drops for item 9.7. Containment matching is unchanged.
- `src/system_03_search_agent/synthesis/findings.py`: the `plain_language` directive, the rewritten `researcher` directive, system rule 7 deferring length and headings to the depth line, and resolved disease names in reading order.
- `src/system_03_search_agent/synthesis/disease_names.py`: `readable_disease_name`, a closed-set deterministic reordering of inverted MedGen titles.
- `src/system_03_search_agent/synthesis/trust.py`: `answer_trust_line`.
- `src/system_03_search_agent/core/graph.py`, write side only: layout-aware grounding input; the Researcher listing over every prepared finding in place of the tail; marker renumbering keyed by citation id; `_answer_tokens`; the medical-advice note; `trust_line` on done.
- `src/system_03_search_agent/contracts/query.py`: `plain_language` added to `audience_depth`.

Backend, outside both lists, approved by the main agent:
- `adapters/web_sse/app.py`, `auth/preferences.py`, `adapters/graphql/types.py`, `adapters/cli/main.py`: each gains `plain_language`.
- `adapters/mcp/server.py` was widened and then reverted, because Section 13.2 pins it (F9-13). Net: unchanged.

Set 8's contract file, small additive edits:
- `contracts/events.py`: `TokenPayload.kind`, `.cells` and `.emphasis`; `DonePayload.trust_line`.

Frontend:
- `frontend/src/lib/events.ts`: optional `kind`, `cells` and `emphasis` on tokens and `trust_line` on done, with validators.
- `frontend/src/lib/api.ts`: the depth type gains `plain_language`.
- `frontend/src/hooks/useRunView.ts`: typed tokens become structured claims; notes are typed or recognised as notes and placed in position or after the answer; one trust line with high risk kept; the `ask` status word defers to the trust line.
- `frontend/src/components/screens/AnswerScreen.tsx`: paragraphs, headings, list, table and bold rendering; notes after the answer; one trust line with an info card; the streaming body under the progress.
- `frontend/src/components/controls/DepthControl.tsx`: Plain language (default) and Researcher, the info card, the lock line.
- `frontend/src/App.tsx`: Plain language default and reset, seeding accepts `plain_language`, one streaming render branch for a first run.

Tests, new:
- `tests/system_03_search_agent/synthesis/test_answer_layout.py`
- `tests/system_03_search_agent/core/test_write_answer_structure.py`
- `tests/system_03_search_agent/adapters/test_audience_depth_values.py`
- `frontend/src/set9AnswerStructure.test.tsx`
- `frontend/src/components/controls/DepthControl.test.tsx`

Tests, changed. Each is a requirement change, named here:
- `test_write_findings_tail.py` and `test_write_completeness.py`: fixture depth to `clinical_brief`, because the tail now lives on non-Researcher depths.
- `AnswerScreen.thread.test.tsx`: in-flight claims now stream (9.6).
- `personaIdentity.test.tsx`: two-mode buttons, with the same three properties pinned.
- `test_streaming_endpoints.py`: POST accepts all four depths and returns 422 on an unknown one. Database-gated.
- `e2e/query-stream-and-stop.spec.ts`: a new Stop-mid-stream arm.

Docs and tooling:
- `docs/build/Debugging_guide.md`: the `answer_layout.py` row, plus a clause each on the grounding and trust rows.
- `tests/system_03_search_agent/fixtures/debugging_guide_manifest.json`: regenerated by the coverage script.
- `testing/Developer/scripts/local_loop_run_depth.py` (new): the live measurement script.

## Wire mechanism for structure, and why

Structure travels as an optional `kind` on `TokenPayload` (`claim`, `note`, `heading`, `paragraph_break`, `list_item`, `table_header`, `table_row`), with `cells` for list and table values and `emphasis` for bold substrings.

- Why not markup in the text: the grounding pass accepts clauses by deterministic containment over sentences, so a heading or blank line inside the text is either stripped as an uncited assertion or fuses with a claim.
- How structure stays beside the text: the reply is parsed into paragraphs first, the pass receives the same joined prose it always did, and `sentence_origins` maps survivors back to paragraphs.
- Model headings are never grounded as claims. They are shown only when `heading_is_supported` passes.
- Lists and tables are built in code, one grounded sentence per record.
- Coverage is unchanged in meaning: heading, break and note tokens carry no marker and assert nothing, and every claim, list item and table row carries its grounded sentence and marker in `text`.
- Text-only surfaces (CLI, MCP, GraphQL, the eval grader) still read joined prose.
- The trust line is `DonePayload.trust_line` because MCP projects `TrustSignalPayload` whole under a pinned allowlist (F9-11).

## Live-run table

Script: `testing/Developer/scripts/local_loop_run_depth.py`, no session memory, real models and graph, preflight READY. Raw output: `live_runs.jsonl` and the `run_*.txt` files in this folder.

| Run | Mode | Question | Outcome | Words | Paragraphs | Headings | List items | Unmarked claims | Trust line | Sources |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | plain_language | BRCA1 diseases | ask | 111 | 2 | 0 | 0 | 0 | Based on 4 sources, not yet confirmed | set A (6) |
| 2 | plain_language | BRCA1 diseases | ask | 117 | 3 | 0 | 0 | 0 | Based on 4 sources, not yet confirmed | set A (6) |
| 3 | plain_language | BRCA1 diseases | ask | 108 | 2 | 0 | 0 | 0 | Based on 4 sources, not yet confirmed | set A (6) |
| 4 | researcher | BRCA1 diseases | ask | 198 | 2 | 5 | 11 | 0 | Based on 4 sources, not yet confirmed | set A (6) |
| 5 | researcher | BRCA1 diseases | ask | 228 | 5 | 5 | 11 | 0 | Based on 4 sources, not yet confirmed | set A (6) |
| 6 | researcher | BRCA1 diseases | ask | 162 | 4 | 6 | 11 | 0 | Based on 4 sources, not yet confirmed | set A (6) |
| 7 | researcher | GCK MODY variants | ask (fallback) | 89 | 0 | 4 | 20 | 0 | Based on 4 sources, not yet confirmed | set B (15) |
| 8 | researcher | GCK MODY variants | answer | 95 | 1 | 4 | 20 | 0 | Based on 4 sources | set B (15) |
| 9 | researcher | GCK MODY variants | ask (fallback) | 89 | 0 | 4 | 20 | 0 | null, mid-edit run (F9-14) | set B (15) |
| 9r | researcher | GCK MODY variants | answer | 134 | 1 | 4 | 20 | 0 | Based on 4 sources | set B (15) |

- Set A: `672`, `MedGen:C0346153`, `MedGen:C2676676`, `MedGen:C3280442`, `MedGen:C4554406`, `unknown`.
- Set B: `2645`, 13 ClinVar ids, `unknown`.
- GCK resolved on every run, so the CFTR substitute was not needed.
- Researcher headings include the code-built "... records found" group headings.
- Words count prose plus list display values, with markers, notes and headings excluded.
- Disease names read naturally in every run: "Familial breast-ovarian cancer susceptibility 1", "Pancreatic cancer susceptibility 4".
- The medical note ended every Plain language answer and no Researcher answer.
- No run hit the cost cap, so X8 was not triggered.

## Proposed DECISIONS.md rows

| Date | Decision | Alternatives considered | Why |
|------|----------|------------------------|-----|
| 2026-09-13 | Researcher answers take the reference screenshot's shape: a cited summary paragraph with bold key terms chosen in code, three to six topic headings with short prose, and the retrieved records as a code-built bulleted list (or a two-column table where a record carries a second field), one citation marker per row. This supersedes decision U2 for Researcher answers. Plain language keeps three paragraphs with no headings, lists or tables. Product-owner decision. | U2 as written (headings with prose only); model-written lists or tables | <details><summary>why</summary>The product owner compared the shapes and chose the screenshot. Lists and tables are built from the run's own findings and grounded one sentence per record, so the cited set stays the prepared set on every run (item 10.1). A model-written list would bypass the grounding pass. Bold terms come only from resolved entities and record names.</details> |
| 2026-09-13 | Answer structure travels as an optional `kind` on `TokenPayload` (plus `cells` and `emphasis`), with paragraph membership recovered through `GroundingResult.sentence_origins`. | Markdown inside token text; grounding each paragraph separately; a separate structure event | <details><summary>why</summary>The grounding pass accepts clauses by containment over sentences, so markup in the text is stripped or fuses with a claim. Grounding paragraphs separately breaks the dense display numbering. A typed field is additive in v1, and every text-only surface keeps reading prose.</details> |
| 2026-09-13 | A model-written heading is shown only when every content word is a fixed topic word or a word the findings or the open question carry (`heading_is_supported`). | Show all model headings; build every heading in code; ground headings as claims | <details><summary>why</summary>A heading is model text that cannot be cited. Unchecked, it could assert something nothing supports. Grounding it as a claim would strip almost every topic label. A closed vocabulary plus finding-supported words lets a heading label a topic and never state a fact.</details> |
| 2026-09-13 | The trust line travels as `DonePayload.trust_line`, built by `synthesis.trust.answer_trust_line`, counting independent origin databases. It says "Confirmed" only on concordant triangulation. When it is present, the status word for `ask` is "Answered". | A field on `TrustSignalPayload`; a line composed in the frontend; keeping both caution texts | <details><summary>why</summary>MCP projects `TrustSignalPayload` whole under a pinned allowlist, so a field there leaked into MCP. The done event already carries the verdict the line puts into words. Stating the caution twice put two contradicting signals on one screen.</details> |
| 2026-09-13 | Item 9.7 is fixed in the grounding pass by two stricter whole-sentence drops: unbalanced parentheses, and a bare-pronoun opener whose previous sentence did not survive. | Repairing the fragment into prose; leaving it to the prompt | <details><summary>why</summary>Repair means writing text after grounding, which lets unverified prose reach a reader. Both rules only remove, and the findings tail re-lists whatever they remove, so no source is lost.</details> |
| 2026-09-13 | A resolved MedGen title reads in natural order by a closed-set reordering (`readable_disease_name`). Any unrecognised part leaves the title unchanged. | Showing the inverted title; asking the model to reword it | <details><summary>why</summary>The brief allows a readable form only as a deterministic transformation of the record's own words. The grounding pass then checks prose against that form, so the claim still contains the finding's value.</details> |
| 2026-09-13 | The MCP tool's `audience_depth` stays at the three Section 13.2 values. `plain_language` is added to the web request, preferences, GraphQL and the CLI only. | Widening MCP too | <details><summary>why</summary>Section 13.2 of the locked specification pins the MCP input schema, and its fidelity test fails on a fourth value. A locked-spec change is for the product owner.</details> |

## Proposed changes to hand-tests 1, 7 and 12 (`testing/Product/Product_workflows.md`)

Test 1, Basic search. Replace the second Expected bullet with these:
- The answer builds on screen sentence by sentence under the progress steps, then settles into short paragraphs of prose, each sentence with its numbered citation chip, plus source cards.
- The answer never opens on a broken sentence (an unclosed bracket, or "These are ..." with nothing before it).
- Notes such as "Note: the records below were retrieved ..." read as grey notes, never as uncited sentences, and never appear above the first sentence.
- Disease names read naturally: "Familial breast-ovarian cancer susceptibility 1", never "susceptibility to, 1".

Test 7, Answer depth, renamed "Answer mode":
- Testing: the two modes change how the answer is written, not what it finds.
- Steps: on the home page, check that "Plain language" is selected, click the small "i" and read the explanation, then Search. Then New search, choose "Researcher", and Search.
- Expected:
  - Plain language: a short answer in about three paragraphs, everyday words, no headings, lists or tables. It ends with the grey line "This is a research summary, not medical advice."
  - Researcher: a longer answer with short topic headings, then the records found as a bulleted list under a heading. No medical-advice line.
  - The same sources appear in both modes (compare the Sources count and the list).
  - The mode cannot be changed while a search is running, and a change applies to the next question.
- Known limit, to note rather than fail: answers run shorter than the 250 and 700 word targets, because every sentence must be tied to a record (F9-04).

Test 12, Trust signals and sources:
- Under the answer, one plain line such as "Based on 4 sources, not yet confirmed" or "Confirmed by 2 independent sources", with an "i" that explains how sources are counted.
- A high-risk claim adds "High-risk claim" in red on the same line.
- No two trust signals contradict each other: the status strip says "Answered" when the line carries the caution.
- This replaces the "Single source, not independently confirmed" bullet.
- The grey-uncited and "Show work" bullets stay as they are.

## Verify commands (each on its own exit code)

- `python -m pytest tests/system_03_search_agent -q -p no:cacheprovider`: 2 failed, 4606 passed, 176 skipped, 1 xfailed (607.91s).
  - `adapters/graphql/test_types.py::test_audience_depth_has_exactly_querys_three_values` was a set 9 requirement change: the test pins GraphQL's enum to `Query`'s Literal, which now has four values. It is updated and renamed `test_audience_depth_has_exactly_querys_values`, and its file re-run passed 51 of 51.
  - `core/test_layer_handoff.py::test_two_slow_layer_calls_finish_in_about_one_delay` is set 8's new timing test, measured under a shared machine. Not set 9's.
- `ruff check .`: exit 0, clean.
- `isort --check-only src tests`: exit 0.
- `python3 tracker/check_doc_drift.py --check`: exit 1, 2 stale. AGENTS.md:32 and CLAUDE.md:32 say 4919 Python tests, and 4991 are computed. Not edited, per the brief.
- `npm run build`: exit 0.
- `npx vitest run`: 2 failed, 408 passed (410), 41 files.
  - `App.test.tsx` "the tour's 'Run it for me' ..." was a set 9 requirement change: the default mode is now `plain_language`. It is updated, and the file re-run alone passed 38 of 38.
  - `railCollapsePremise.test.tsx` failed on a 15-second load timeout. Re-run alone, it passed 20 of 20.
- `npx playwright test e2e/second-turn.spec.ts e2e/query-stream-and-stop.spec.ts e2e/trust-surface.spec.ts e2e/accessibility.spec.ts --workers=1`: exit 0, 29 passed (28 existing plus the new Stop-mid-stream arm).
- `python tests/system_03_search_agent/test_debugging_guide_coverage.py`: the manifest was regenerated. The pytest form passed 7 of 7.
- Focused runs:
  - `test_answer_layout.py`, `test_write_answer_structure.py` and `test_audience_depth_values.py`: all pass.
  - The MCP `TestSchemaFidelity` class and the operator allowlist test: pass.
  - `set9AnswerStructure.test.tsx`: 8 of 8. `DepthControl.test.tsx`: 5 of 5.

## Left open

1. Length targets are not met: Plain language measured 108 to 117 words, Researcher 162 to 228 (F9-04, F9-14). The gate is unchanged, so reaching them needs a product decision on background text, or more retrieved content per answer.
2. The table cannot render on live data today (F9-05, F9-16). It is kept and tested against a fixture.
3. MCP does not accept `plain_language` (F9-13), pending a locked-spec decision.
4. Layer 3 citations carry `source_id: "unknown"` (F9-15). This is set 8's `_citations_from_grounded_claims` branch. Set 9 did not edit that function.
5. A variant with a URL as its representative value lists the URL (F9-15), a `_pick_representative_field` choice.
6. `OnboardingTour.tsx` still titles its step "Answer depth", and `InfoScreens.tsx` describes three depths. Neither is in either set's list; both need a copy change.
7. Doc drift: AGENTS.md and CLAUDE.md state an older Python test count (see verify below). Not edited, per the brief.
8. Four pre-existing ruff findings in the committed `testing/Developer/scripts/local_loop_run.py` (F9-12).
9. The "4 sources, not yet confirmed" wording on an `ask` answer, for the product owner to confirm (F9-18).

## Follow-up round (2026-09-14)

### 1. Variant list rows showing a URL

- Root cause, measured on the real field shape of ClinVar:1179956 (GCK), read live with a parameterised read-only query. `core.graph._is_vocabulary_token_artifact` flags the name "NM_000162.5(GCK):c.363+318G>A" (an intronic HGVS name), the id "ClinVar:1179956", and the source "ClinVar". So `_pick_representative_field` returns `source_url` as the first clean field.
- A control name, "NM_000162.5(GCK):c.415A>T (p.Met139Leu)", picks `name`.
- The same URL is therefore also the finding's grounded value and its citation `claim_text`.
- Fix in my file: `synthesis/answer_layout.record_label(finding, row_fields)`. It takes the first non-blank name-like field of the record's own row (`name`, `title`, `symbol`, `preferred_name`), then the CURIE or record id, and never a URL.
- Tests on the real row:
  - A populate-check that `_pick_representative_field` still picks `source_url` on that row.
  - The label is the name.
  - With no name, the label is the id. With only URLs, the label is the citation id.
  - A clean name finding keeps its own value.
- BLOCKED at the call site. The list cell is built in `core/graph.py` `_answer_tokens` (`cells=[finding.field_value[:500]]`), and this round forbids editing graph.py. So the live list will still show the URL until set 8 or the main agent applies this one-line change, in both `listing` branches:
  - `list_item`: `cells=[record_label(finding, _row_fields_for(finding, findings))]`
  - `table_row` first cell: the same call.
  - Plus adding `record_label` to the `answer_layout` import.
- The deeper defect, the artifact check misfiring on HGVS names with `+`, lives in `_pick_representative_field` and `_is_vocabulary_token_artifact` (graph.py). It affects grounding and citation text too. It is recorded for the graph.py owner and not fixed here.

### 2. Tour and info copy

- `frontend/src/components/tour/OnboardingTour.tsx`: the step "Answer depth" (three depths) becomes "Answer mode". It describes Plain language (the default) and Researcher, in the info card's wording.
- `frontend/src/components/screens/InfoScreens.tsx`: the About journey line now reads "Plain language, the default, or Researcher".
- No test pinned the old copy: a grep of `src` and `e2e` test files for "answer depth", "clinical brief", "deep technical" and "how deep the answer" found none. No test changed.

### Verify (each on its own exit code)

- `python -m pytest tests/system_03_search_agent/synthesis -q -p no:cacheprovider`: exit 0, 274 passed, 9 skipped, 1 xfailed.
- `ruff check .`: exit 0.
- `npm run build`: exit 0.
- `npx vitest run src/components/tour/OnboardingTour.test.tsx src/components/screens/AboutScreen.test.tsx`: exit 0, 26 of 26. InfoScreens has no test file of its own; the About screen test renders the About journey.

### Live Researcher run: "Which clinically significant variants have been reported in CFTR?"

- Output: `run_followup_researcher_cftr.txt`. The run took the structured fallback, with 20 variant list rows, 4 headings, 0 unmarked claims, the trust line "Based on 4 sources, not yet confirmed", and 20 sources.
- 18 of the 20 variant rows read as HGVS names. The other 2 still read as URLs: ClinVar:1012571 and ClinVar:1012572. This is expected while the call site is unchanged: `graph.py` still builds the cell from `finding.field_value`. The live list does NOT yet show the fix.
- What `record_label` gives on those two exact rows, from their real fields (parameterised, read-only):
  - ClinVar:1012571: name "NM_000492.4(CFTR):c.744-9G>T", upstream pick `source_url`, `record_label` "NM_000492.4(CFTR):c.744-9G>T".
  - ClinVar:1012572: name "NM_000492.4(CFTR):c.744-7_744-4del", upstream pick `source_url`, `record_label` "NM_000492.4(CFTR):c.744-7_744-4del".
- The misfire covers intronic names with `-` as well as `+`.
- To finish item 1, the graph.py owner applies the one-line call-site change above. A one-shot rerun of this script then shows every row as a name.
