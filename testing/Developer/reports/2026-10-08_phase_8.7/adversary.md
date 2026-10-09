
## Adversary round, build phase 8.7 (answers sooner)

Base: 72ab2cd9f85745e91c9ea839a04fd2c773b65bb4 (origin/phase/8.7-answers-sooner). Findings appended as established.

### F-8.7-A01: An older command-line client fails every answered question once the server sends `placement`
- Severity: major (unsure how many pre-8.7 command-line installs exist; the web screen ships with the server and is not affected)
- What: every token the phase's server sends now carries `placement` (`_with_placement` sets it on every token, summary ones included, and `model_dump()` serialises the default too). The develop-era `TokenPayload` is `extra="forbid"` and has no such field, so a develop-era `Event.model_validate` rejects every token frame. The develop-era command-line client treats a known event type whose payload fails to decode as a DEFECT and synthesises a fatal `error` (its `_decode_stream_event`, F-4.2-RR-03), so it ends the stream at the first listing token. The field is described as "additive per Section 2.6", but under `extra="forbid"` it is not additive for any client built before it.
- Reproduction: the develop contract unpacked with `git archive origin/develop src`, then three frames validated with `Event.model_validate` (version "v1", type "token", payload `{"text": ..., "marker_ids": [...], "kind": ..., "placement": X}`).
  - develop contract: `REJECTED listing`, `REJECTED summary`, `REJECTED sidebar`, each "1 validation error for Event".
  - phase contract: `ACCEPTED listing`, `ACCEPTED summary`, `REJECTED sidebar`.
- What a person sees: someone running a command-line client installed before this phase asks a question and gets "run failed" at about 8 seconds (the first listing token), no records and no summary, with a non-zero exit, on every question that has records. A refusal still prints, because it fails on the same token.
- Also: an unknown future value ("sidebar") is rejected by the phase's own contract and by `isTokenPayload` in `frontend/src/lib/events.ts`, while `contracts/token_order.py` says an unknown value "counts as the summary". The two rules disagree; the one that runs drops the text.
- NOT FIXED

### F-8.7-A02: The opening line says the records give no clinical features when the search that carries them did not finish
- Severity: major
- What: `records_lack_field` (synthesis/answer_layout.py) decides the honest-gap clause only from the findings that reached Write. It does not read `failed_searches`. When the MedGen fetch that would carry the clinical features failed or timed out, there are no feature findings, so the opening line states as fact that the records do not give clinical features, and the failed-search note below the records says the opposite may be true. The same holds when a record's features could not be read (`_medgen_feature_rows` writes no row for an unreadable record "because nothing is known") and when the display cap left the feature findings out: absence of a finding is read as absence in the record.
- Reproduction: offline write step, `_write_state` (five graph Disease rows, each citing a MedGen page), `_clinical_features_asked` returning True, plus `state["failed_searches"] = [{"tool": "ncbi_efetch", "layer": "layer_2_ncbi", "reason": "search: timed out", "kind": "timeout", "source": "medgen"}]`. Output, Researcher:
  - summary claim: `Found 5 disease records: disease name number 1 [1], ... and disease name number 5 [5], none of which gives clinical features.`
  - listing note: `The background search of MedGen did not finish, so this answer may be missing sources from it. Ask again to retry.`
  - Plain language: `I found 5 conditions on this topic [1][2][3][4][5], none of which gives clinical features.` with the same note.
- What a person sees: they ask what the features of a condition are, and the first, emphasised sentence tells them the records do not give any. Each [n] opens a MedGen page that may list the features. The note that contradicts it is at the bottom, under the records. A confident wrong statement in the one sentence the phase made the answer.
- Also, Plain language: "I found 5 conditions ..., none of which gives clinical features" can be read by a reader with no technical background as "these conditions have no symptoms". The clause states an absence in records, but the Plain wording does not say "records".
- NOT FIXED

### F-8.7-A03: The opening line says no record gives clinical features directly above a record row that gives them
- Severity: major
- What: the honest-gap check (`records_lack_field`) looks only for the one field name `clinical_features`. A record that states the features under any other field (a description, a summary, an abstract) does not count, so the opening line says "none of which gives clinical features" while the listing under it shows a record that does.
- Reproduction: offline write step, two graph rows in one `cypher_query` finding: Disease `MedGen:C0024796` with `name: Marfan syndrome`; Gene `NCBIGene:2200` with `description: Marfan syndrome features include tall stature and lens dislocation`. Question "What are the clinical features of Marfan syndrome?", `_clinical_features_asked` returning True, writer reply "Marfan syndrome features include tall stature and lens dislocation [2]." Output, Researcher:
  - listing table_row: `Gene NCBIGene:2200, description: Marfan syndrome features include tall stature and lens dislocation [2].`
  - summary claim, emphasised: `Found 1 disease record and 1 gene record: Marfan syndrome [1] and NCBIGene:2200 [2], none of which gives clinical features.`
  - Plain language: `I found 1 condition and 1 gene on this topic [1][2], none of which gives clinical features.` above `Gene NCBIGene:2200, description: Marfan syndrome features include tall stature and lens dislocation [2].`
- What a person sees: the first sentence denies what the second row on the same screen says, and cites [2], the very record that carries the features, as one that does not. The written answer's own sentence was dropped as a restatement, so the denial is the whole summary.
- NOT FIXED

### F-8.7-A04: A chip under a summary sentence no longer shows the words that sentence was checked against (card 57 undone when the listing goes early)
- Severity: minor (major for a reworded sentence whose quote is the only support; the lead's tracker names "a listing citation's chip never gains the prose quote", filed here with the reproduction because it reverses card 57)
- What: with the listing sent early, `_write_answer` replaces every final citation whose id the listing already sent with the early payload (`citations = [sent_by_id.get(c.citation_id, c) ...]`), and never re-sends it. The early payload's `claim_text` holds only the listing row's words. Card 57 (2026-10-05) made `claim_text` join the record words EVERY claim on that citation was checked against, so the summary sentence's support is shown on its chip. That join is computed and then thrown away.
- Reproduction: offline write step, `_write_state("researcher")`, writer reply `ANSWERING` from `test_write_answers_sooner.py`; the citation events' `claim_text` with the early send on, and with `_contract_carries_placement` patched to False:
  - cq-completeness-1, on: `'Disease MedGen:C1, name: disease name number 1'`; off: `'Disease MedGen:C1, name: disease name number 1 NCBIGene:672 is associated with disease name number 1'`
  - cq-completeness-3, on: `'Disease MedGen:C3, name: disease name number 3'`; off: `'Disease MedGen:C3, name: disease name number 3 Disease name number 3 is also associated with NCBIGene:672'`
- What a person sees: they open the [1] chip under a summary sentence to check it, and the chip shows only the record's name row, not the words of the record that support the sentence they are checking. For a reworded sentence carrying a quote (items 12.9, 12.10), the quote that proves it is not on the chip when the cited record is also a listing row.
- NOT FIXED

### F-8.7-A05: Under the owner's 25-cent cap the second draft can never start beside the first, so option B's speed gain cannot happen
- Severity: minor (the lead's tracker already names it; filed because the goal contract still claims it)
- What: `_two_drafts_fit_cap` admits the side-by-side draft only when running cost + 2 x the synth estimate fits the cap. At Opus's price the synth estimate is $0.132, so two are $0.264, above $0.25 even at zero spend. The goal contract's third "Done when" line credits option B for the summary arriving sooner.
- Reproduction: `PER_QUERY_COST_CAP_USD=0.25`, a stand-in harness priced at (4e-6, 20e-6) with zero spend: `per synth call estimate 0.132`, `two drafts fit at zero spend under 0.25: False`.
- What a person sees: nothing changes for them from option B; the summary arrives no sooner on the questions it was built for. The code, its tests and the cancelled-draft metering ship as dead weight on the production configuration.
- NOT FIXED

### F-8.7-A06: A question can cost more than 25 cents, with no note, because the cap check prices a writer call below what one can cost
- Severity: major (the owner's acceptance is "a question never costs more than 25 cents")
- What: the pre-flight check prices a synth call at a fixed 23,000 prompt and 2,000 output tokens ($0.132 at Opus's price), the largest call one bench saw, not a bound. The synth tier's own output ceiling is 4,000 tokens (`_TIER_MAX_TOKENS["synth"]`), and nothing bounds the prompt at 23,000. A call admitted at $0.132 can cost up to $0.172 at 23,000 prompt tokens, more with a longer prompt, so the call that is admitted last can carry the question past the cap. The completeness draft, which asks the model to report every omitted finding, is the call most likely to write long.
- Reproduction: offline write step, `PER_QUERY_COST_CAP_USD=0.25`, `litellm.get_model_info` priced at (4e-6, 20e-6), the listing made unable to cite finding 4 (`_listing_cannot_cite(monkeypatch, 4)`), first draft `ANSWERING` with usage 20,000 prompt and 1,000 output, completeness draft with usage 23,000 prompt and 3,900 output. Output: `calls ['first', 'repair']`, `done.total_cost_usd 0.27 trust answer`, `notes []`. Control with the bench's largest call twice (22,839 and 1,869): `calls ['first']`, `done.total_cost_usd 0.128736`, repair refused with the cost-limit note.
- What a person sees: nothing; the answer looks normal. The owner sees a 27-cent question on a 25-cent cap, and the daily cap drains faster than the arithmetic in the phase says it can.
- NOT FIXED

### F-8.7-A07: The written summary now waits up to 3.5 seconds more on the lead-sentence decision, then shows the count line anyway
- Severity: minor
- What: `_lead_sentence_choice` runs after the writer and grounding and before any summary token is sent, and waits up to `min(4.0, budget - 0.5)` seconds for Jev (with the guard tier stepping in when Jev fails). A slow or failed pick falls back to the count line, so the person waits the full time and gets exactly what develop gave them. This is a new wait inside a phase whose purpose is "answers sooner".
- Reproduction: offline write step, `_write_state("researcher")`, `CLASSIFIER_PROVIDER=jev`, fake Jev picking "first" after a delay. Output: `jev delay 0.0s -> write step 0.00s, lead: 'NCBIGene:672 is associated with ...'`; `jev delay 3.9s -> write step 3.53s, lead: 'Found 5 disease records: ...'`; `jev delay 10.0s -> write step 3.51s, lead: 'Found 5 disease records: ...'`.
- What a person sees: when the classifier is slow (cards 72 and 84 name the guard model's slow bursts), the summary appears about 3.5 seconds later than it would have, opening with the same count line as before.
- NOT FIXED

### F-8.7-A08: "No answer waits more than 6 seconds on a literature search" holds for PubTator only; a PubMed search can still hold an answer 35 seconds
- Severity: minor (unsure: a scope-of-words question for the owner)
- What: only `pubtator_annotate` moved to 6 seconds. The PubMed search (`ncbi_efetch`, `_NCBI_EFETCH_ACT_TIMEOUT_SECONDS = 35.0`) and LitVar2 (`litvar2_lookup`, 20.0) keep their budgets. The acceptance sentence in the tracker and the brief says "a literature search".
- Reproduction: `_LAYER_TOOL_ACT_TIMEOUT_SECONDS` printed on the branch: `{'ncbi_dbsnp': 35.0, 'pubtator_annotate': 6.0, 'litvar2_lookup': 20.0, 'clinicaltrials_search': 20.0, 'pathogen_detection': 150.0}`; `_NCBI_EFETCH_ACT_TIMEOUT_SECONDS = 35.0` (core/graph.py line 6141). The PubTator cut does say so: `The background search of PubTator did not finish, so this answer may be missing sources from it. Ask again to retry.`
- What a person sees: a paper question whose PubMed search is slow still waits up to 35 seconds in silence before Write starts, although the phase says a literature search never holds an answer more than 6.
- NOT FIXED

### F-8.7-A09: `_prefetch_answer_names` and `_one_lookup_holds` ship as about 110 lines of never-called answer-path code
- Severity: minor
- What: step 8 removed the reader pass, and with it the only caller of `_prefetch_answer_names` (core/graph.py lines 8540 to 8650). Nothing calls it; `test_act_name_lookups.py` now asserts it does not run (it patches it with `raising=False`). Option H's gain is gone, as the tracker says, but the function, its long docstring describing when it runs, and `_one_lookup_holds` (which reads two private resolver internals, `disease_names._MAX_IDS_PER_CALL` and `mesh_terms._batch_for_one_term`) remain.
- Reproduction: `grep -n "_prefetch_answer_names" src/system_03_search_agent/core/graph.py` returns its definition (8562), its own docstring and one comment (8886); no call site.
- What a person sees: nothing. A later reader of `act_node` is told by a docstring that Act looks names up "while the reader pass runs", which no longer happens.
- NOT FIXED

### F-8.7-A10: If the cap setting is not raised in the same moment as the merge, every question loses its summary and is told it "reached its resource limit"
- Severity: major (unsure: depends on the deployment step the lead plans at merge; nothing in code enforces it)
- What: the synth default becomes Opus with no code change to the cap, which stays an environment value with no default. At any cap below $0.132 the pre-flight check refuses every first writer call. The code only logs an error; the person gets the early listing and the cap note, which blames this question's spend although nothing was spent on writing. The phase's own text (per_query_cost_cap_usd docstring) says a 10-cent cap "stops every question at Write". Nothing fails at start-up, and `SYNTH_MODEL` is not pinned on develop (tiers.py says "Develop sets no `SYNTH_MODEL`, so this default reaches develop when the phase merges").
- Reproduction: offline write step, `_write_state("plain_language")`, writer priced at Opus (4e-6, 20e-6).
  - `PER_QUERY_COST_CAP_USD=0.10`: `calls=[] trust=ask`; summary `I found 5 conditions on this topic [1][2][3][4][5].`; note `Note: this question reached its resource limit before it finished, so this answer lists the records gathered so far`; log `PER_QUERY_COST_CAP_USD is 0.1000, below the estimated cost of one synth-tier call ...`.
  - `PER_QUERY_COST_CAP_USD=0.25`: `calls=['first', 'first_done'] trust=answer`, with the written prose.
- What a person sees: every answer on develop is a list of records under "this question reached its resource limit", marked not yet confirmed, from the merge until someone changes a setting. The note is untrue for them: their question was not expensive, the setting was wrong.
- NOT FIXED

### F-8.7-A11: Records kept after Stop show with no trust marking at all, a high-risk record included
- Severity: minor (unsure: the owner's 2026-09-27 "keep them" says no trust line; this files what that leaves a reader with)
- What: the server sends a record's trust only after the summary (per-claim and answer `trust_signal`, then `done.trust_line`), never with the early listing. `whatStopLeavesOnScreen` (frontend/src/hooks/useAnswerReveal.ts) keeps the claims and sources and clears `trust`, so a run stopped after its records shows the rows with chips and none of: "High-risk claim", "Not verified · the run did not finish" (the label `useRunView` has for exactly an unfinished run), or a conflict flag. On develop a stopped run showed no records, so this state is new.
- Reproduction: read, not run: `withholdAnswer` returns `trust: []`; `whatStopLeavesOnScreen` returns `{...withholdAnswer(view), claims: shownBeforeStop.claims, sources: shownBeforeStop.sources}`. On the server, `trust_for_claims` over the listing's claims is first computed after the writer call (core/graph.py, the `claim_trusts` block after the listing merge), so no trust exists on the wire while the records are on screen. The integration fixer's S2 and B2 pin that nothing follows the `cancelled` error.
- What a person sees: they stop a question about a variant once its records appear; the ClinVar rows stay on screen under "No summary was written. The records found before you stopped are below." with no high-risk tag and no "not verified" mark, so a pathogenicity row reads exactly like a checked answer.
- NOT FIXED

### F-8.7-A12: The screen's listing-first and Stop tests pin a server shape the server never sends
- Severity: minor (test validity)
- What: `useRunView.placement.test.ts`, `AnswerScreen.listingFirst.test.tsx` and `App.stopUntilAnswer.test.tsx` all send the count line ("Found N disease records ...") as a `placement: "listing"` claim at the head of the early listing. The server puts the count line in the SUMMARY part (`_answer_parts`, summary_sentence before `listing_at`) and its early listing opens with `paragraph_break`, `heading`, `table_header`, then rows. The real early listing therefore holds no plain `claim` at all in Researcher, and the frontend tests that "Stop counts summary sentences only" and "the summary lands above the records" never see the real stream.
- Reproduction: the offline write step's early events, Researcher, printed from `_record_timeline` before the writer call: `listing paragraph_break '\n\n'`, `listing heading 'Gene records found\n\n'`, `listing table_header ''`, `listing table_row 'Gene NCBIGene:101, name: gene name number 1 [1]. '`, ...; after the writer, `summary claim 'Found 2 gene records and 2 disease records: ...'`. Frontend fixtures: `App.stopUntilAnswer.test.tsx` line 174 `["token", { text: "Found 2 disease records for BRCA1.", marker_ids: [], placement: "listing" }]`; `AnswerScreen.listingFirst.test.tsx` line 60; `useRunView.placement.test.ts` `listingTokens[0]`.
- What a person sees: nothing directly. The checks the phase relies on for the Stop and layout rules do not exercise the stream a person's browser receives.
- NOT FIXED

### F-8.7-A13: After "linked to 3 diseases", the gap clause reads as saying those diseases have no clinical features
- Severity: major (the opening line is the phase's deliverable; the Plain language reading is a false medical statement)
- What: `answer_summary_sentence` appends the gap clause to the END of the sentence (`finish(body + clause + ".")`), after the "linked to N diseases/conditions" clause, and sizes it by the counted records (`_gap_clause(len(counted))`). With one variant record linked to three conditions the clause lands on "3 diseases" and says "which does not give", so the nearest noun, the diseases, is what reads as lacking features.
- Reproduction: offline write step, one graph `SequenceVariant` row `dbSNP:rs80357906` with `clinvar_condition_ids` of three MedGen ids (names resolved by a stub), `_clinical_features_asked` returning True, writer reply that grounds nothing. Output:
  - Researcher: `Found 1 sequence variant record: NM_007294.4(BRCA1):c.5266dup (p.Gln1756fs) [1], linked to 3 diseases, which does not give clinical features.`
  - Plain language: `I found 1 genetic variant on this topic [1], linked to 3 conditions, which does not give clinical features.`
- What a person sees: someone asking what a BRCA1 variant's conditions look like is told, in plain words, that the three linked conditions do not give clinical features, about hereditary breast and ovarian cancer. What the code checked is only that the variant record carries no features field.
- NOT FIXED

### F-8.7-A14: A browser still holding the develop web bundle shows the records above the summary, with the count line under the table
- Severity: minor (unsure: read, not run; matters only while the API and the web service are deployed at different moments, or for a cached tab)
- What: develop's `isTokenPayload` ignores unknown keys, so a develop bundle accepts the new tokens and lays them out in arrival order with one structure state: the early listing (paragraph break, heading, table header, rows, the variant source note) first, then the count line and the prose after the records, then the notes. The develop bundle has no writing slot and no per-region state, which this phase added because a summary sentence arriving after a listing could be taken into the listing's structure.
- Reproduction: read. `git show origin/develop:frontend/src/lib/events.ts`, `isTokenPayload` lines 525 to 536: no check on extra keys. Arrival order from the offline write step (Researcher): listing tokens before the writer call, `summary claim 'Found 2 gene records and 2 disease records: ...'` after it.
- What a person sees: during a deploy, or in a tab opened before it, the answer reads upside down: the table of records, then "Found 5 disease records ..." and the written summary beneath it.
- NOT FIXED

### F-8.7-A15: In a Researcher answer with two record types the numbers do not run in the order the list shows them
- Severity: minor (the lead's tracker names it; filed with a reproduction because the phase's comments and test names state the opposite)
- What: the listing is numbered in grounding order (`build_structured_fallback_narrative` order), then `grouped_listing` regroups the rows by type under headings. The tracker and `_write_answer`'s comment say records "are numbered in the order the list shows them".
- Reproduction: offline write step, Researcher, four graph rows interleaved Gene, Disease, Gene, Disease. Early listing as sent: `heading 'Gene records found'`, `table_row '... gene name number 1 [1]. '`, `table_row '... gene name number 3 [3]. '`, `heading 'Disease records found'`, `table_row '... disease name number 2 [2]. '`, `table_row '... disease name number 4 [4]. '`. Plain language, same rows, one list: `[1] [2] [3] [4]` in order.
- What a person sees: the Researcher table reads 1, 3, then 2, 4; a reader looking for [2] from the summary looks under the wrong heading first. Numbers never change once shown, which holds.
- NOT FIXED

### Verdict: FAIL against the goal contract's first line and the owner's cost words

- Card 2, "the first sentence answers, or says the records do not give it": FAIL. The gap clause states an absence the code has not established: after a failed MedGen search (A02), beside a record row that gives the features (A03), and in Plain language worded as if the conditions had none (A13).
- Card 5, "a question never costs more than 25 cents": FAIL (A06, 27 cents with no note). It depends on a setting changed by hand at merge (A10).
- Card 50, records early and the summary placed above them: holds on the server for numbering, no duplicate rows and no taken-back records. The chip text regression (A04), the Researcher numbering order (A15), the new wait on the lead decision (A07) and option B being unreachable (A05) are the caveats.
- Contract compatibility: an older command-line client fails every answer (A01).

Checked with my own probes (offline write step, develop contract unpacked with `git archive`, the command-line renderer, cost arithmetic): A01, A02, A03, A04, A05, A06, A07, A10, A13, A15. Also these, which held: a number sent early is the number the answer ends with; no citation is sent twice; no listing row is sent twice; a writer failure after the listing keeps it with a note; the command line prints the stop line, the records, then "Not verified · the run did not finish".

Read only, not run: A08, A09, A11, A12, A14. Also read only: the reader-pass removal changes nothing that reaches the writer (only graph Article rows were quarantined, and their fields were already emptied); the lead-sentence and second-draft prompts put record text in data positions; the frontend Stop slice (`events.slice(0, stopPress.mark)`) and `whatStopLeavesOnScreen`; the server-side Stop arms (integration fixer's S1 to S8, not re-run).

None of these sits inside a fix made during a review round of this phase. A04, A06, A07, A13 and A15 sit inside the phase's own newest code: builder W's steps 5 and 6 and builder C's cost estimate.
