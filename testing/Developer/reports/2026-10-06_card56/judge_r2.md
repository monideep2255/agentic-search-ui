# Card 56 round 2 judge report

Judge: fresh context, one round, 2026-10-06. Branch `fix/card56-r2`, reviewed as the net diff against `origin/develop` for `src` and `tests`. Findings are appended as they are established; checklist verdicts follow at the end.

## Findings

### J2-56-01: the retry's "organism the question contains" check passes on any one organism span, while the organism actually searched may be a different span the person never typed

- Severity: blocking
- Regression of: A-56-05 (the round 2 fix `_second_reply_names_a_question_organism`, src/system_03_search_agent/core/graph.py:4186-4204 in the diff, used at 4292)
- In the user's words: a person asks "Find SRA runs from hospital samples sequenced on Illumina", naming no organism. If the second reply tags "hospital" as an organism (the habit the builder's own test `test_an_organism_span_taxonomy_rejects_is_asked_about` models) and adds "Homo sapiens", the person is shown every human SRA run with no question asked, the exact outcome A-56-05 was filed to stop.
- Evidence: the check is `any(entity.entity_type == "organism" and _span_is_in_question(...))`; the organism searched is chosen afterwards by `resolve_organism` (graph.py:3021-3053), which takes the one span Taxonomy knows, whichever it is. Probe through `think_node` with the test file's own fakes (Taxonomy fake extended with "homo sapiens" -> 9606), first reply `entities: [], record_type: sra`, second reply `[("hospital", "organism"), ("Homo sapiens", "organism")]`: printed `calls=2 resolved=['NCBITaxon:9606'] org=('Homo sapiens', '9606') clar=None`, log "asked once more, used the second reply".
- Suggested fix: accept the second reply only when every organism span it carries is text of the question, or drop the spans that are not before `resolve_organism` runs; add the two-span case to `test_a_second_reply_that_does_not_name_a_question_organism_keeps_the_first`.
- NOT FIXED

### J2-56-02: the question check is plain substring containment, so "human" is found in "nonhuman", "rat" in "respiratory", "cat" in "catheter"

- Severity: blocking (unsure on live rate; same family as J2-56-01, a guessed organism answered with confidence)
- Regression of: A-56-05 (round 2's `_span_is_in_question` and `_name_pattern`, graph.py:3527-3546)
- In the user's words: "Find SRA runs from nonhuman primate lung samples", the model names nothing, then names "human" on the retry: the person is shown every human SRA run, labelled as filed under "human", when they asked about non-human primates.
- Evidence: `_span_is_in_question` returns True for ("human", "Find SRA runs from nonhuman primate lung samples"), ("rat", "Find SRA runs from clinical respiratory samples"), ("cat", "SRA runs from catheter-associated infections"), ("pig", "SRA runs of pigmented skin lesions"), ("mouse", "SRA runs of mousepox virus"), and ("E", "SRA runs from clinical samples"). End to end through `think_node`, first reply empty, second `[("human", "organism")]`: `calls=2 resolved=['NCBITaxon:9606'] org=('human', '9606') clar=None`.
- The builder's stated reason for not using word boundaries is false: build_r2.md says "Word boundaries would refuse "SARS-CoV-2" inside "SARS-CoV-2's"", but `re.search(r"\bSARS-CoV-2\b", "SARS-CoV-2's runs")` matches (probe printed True), since the apostrophe is a word boundary.
- Suggested fix: anchor the pattern with `(?<![A-Za-z0-9])` and `(?![A-Za-z0-9])` (or `\b` where the span starts and ends with a word character); add "nonhuman" and "respiratory" cases to `test_a_span_is_in_the_question`.
- NOT FIXED

Line correction for J2-56-01 and J2-56-02 (exact lines on HEAD e72b66d1): `_second_reply_names_a_question_organism` is graph.py:4120-4138, used at 4226; `_name_pattern` is 3536 and `_span_is_in_question` 3552; `resolve_organism` 3021-3053.

### J2-56-03: a follow-up about SRA runs ("And its SRA runs?") is now asked which organism, where develop answered from the remembered subject

- Severity: blocking (the owner's "no question that works on develop today gets worse"; follow-up is a named shape)
- Inside this round's fix: yes, the which-organism gate at src/system_03_search_agent/core/graph.py:4807-4821 (no memory check), and the retry's question check at 4226 (rejects an organism the person named in an earlier turn)
- In the user's words: a person asks "Mycobacterium tuberculosis genome assemblies", then "And its SRA runs?". If Think names nothing for "its" (the habit this card measured on named questions; on a pronoun question the rate is unmeasured), the person is asked "which organism's SRA sequencing records do you want?" about the organism they just named. After a BRCA1 answer, "What SRA runs are there for it?" is asked the same question.
- Evidence: my probe (`think_node` then `plan_node`, all NCBI, model and classifier faked, same script run on this branch and on a copy of origin/develop's `src`), session memory holding one entity:
  - Memory BRCA1 (`NCBIGene:672`), "What SRA runs are there for it?", reply `entities: [], record_type: sra` every call: branch `calls 2, clar "One more detail is needed: which organism's SRA sequencing records do ...", plan_n 0`; develop `calls 1, clar None, plan_n 13, targets ['NCBIGene:672']`.
  - Memory Mycobacterium tuberculosis (`NCBITaxon:1773`), "And its SRA runs?", first reply empty, second reply `[("Mycobacterium tuberculosis", "organism")]`: branch `calls 2, clar "...which organism's SRA sequencing records do ...", plan_n 0` (the second reply is thrown away because the name is not text of this turn's question); develop `calls 1, clar None, plan_n 1, targets ['NCBITaxon:1773']`.
  - Same memory, empty reply twice: branch asks, develop plans on `NCBITaxon:1773`.
- Why the existing gate misses it: `_needs_clarification` (graph.py:6760-6787) returns False when `_antecedent_curie(_memory_curies(state))` binds, which is how develop answers a follow-up; the new gate sets `clarification` unconditionally after it, without that check. No test in either file uses session memory.
- Suggested fix: do not ask which organism when a remembered antecedent binds; and on a follow-up turn either accept a second-reply organism that matches a remembered entity's mention, or do not offer the retry when memory supplies the subject. Add a follow-up test for each.
- NOT FIXED

### J2-56-04: an SRA or assembly question about a disease, with nothing tagged, is now asked which organism where develop answered about the disease or ran a topic search

- Severity: non-blocking (it follows the owner's design part 3 as written; it is still a question that answered on develop and now asks back, so the owner should see it)
- Inside this round's fix: yes, the disease fallback gate at graph.py:4687 and the which-organism gate at 4807-4821
- In the user's words: "Find SRA runs from MODY patients" and "SRA runs from COVID-19 patients", when Think's reply names nothing twice, now get "which organism's SRA sequencing records do you want?"; on develop they were answered from the MODY or COVID-19 disease records. "Genome assemblies linked to CF" now asks which organism; develop planned three searches.
- Evidence: same probe, both trees, reply `entities: []` every call, MedGen fake binding one record for "MODY[title]", "COVID[title]", "CF[title]":
  - "Find SRA runs from MODY patients": branch `calls 2, resolved [], clar which-organism, plan_n 0`; develop `calls 1, resolved ['MedGen:C0342276'], plan_n 1`.
  - "SRA runs from COVID-19 patients": branch asks; develop `resolved ['MedGen:C5203670'], plan_n 1`.
  - "Genome assemblies linked to CF", record type assembly: branch asks; develop `plan_n 3` (`_PlannedNcbiEfetchToolCall` and two follow-ups).
  - Control that held: "SRA runs from ALS patients" with ALS tagged as a disease resolves `MedGen:C0002736` and plans on both trees, so the change bites only when the model names nothing.
- Whether develop's disease answer to an SRA question "worked" is a judgement for the owner: it showed disease records, not runs. Recorded so the trade is chosen, not discovered.
- Suggested fix: none required by the design; if the owner wants develop's behaviour kept, let the disease fallback run on an SRA question when no organism-shaped token was claimed, and ask only when it binds nothing.
- NOT FIXED

### J2-56-05: the "not applied" note is not shown when the organism search ends in Write's refusal

- Severity: non-blocking (minor; the refusal makes no false claim, but it is a path where a span was set aside and the person is not told)
- Inside this round's fix: yes, the note is added only to the answer branch's notes list (src/system_03_search_agent/core/graph.py:14113-14129); the refusal branch (about 14020-14090), the write-call failure (13349-13362) and the cap paths (13318, 13346, 13651) do not carry it
- In the user's words: if the SRA search for SARS-CoV-2 returns rows nothing grounds, the person reads "I could not find grounded evidence for this. Try NCBI's cross-database search" with a link built from their whole question, Illumina included, and no sentence that Illumina was never part of the search.
- Evidence: my probe calling `_write_answer` with the test helpers' fake answer model, `organism_records` carrying `conditions_not_applied=("Illumina",)`: with a graph finding of zero rows, tokens were `[None | "I could not find grounded evidence for this. Try NCBI's cross-database search: https://www.ncbi.nlm.nih.gov/search/all/?term=Find%20SRA%20runs%20of%20SARS-CoV-2%20sequenced%20on%20Illumina..."]` and trust `refuse`, no note. A side observation, not new code: with `findings=[]` and no planned calls, the only token was the note itself, with no refusal and no trust signal, which is the item 12.7 "no_tool" hole the code comment at 13380-13387 already names for organism-shaped paths.
- Suggested fix: append `_organism_conditions_note(state)` after the refusal token as a note, or state in build_r2.md that the refusal path is out of scope.
- NOT FIXED

### J2-56-06: Think's narrative still loses "not applied" when the code's own clause is over 500 characters

- Severity: non-blocking (the answer note survives; the Show work text does not)
- Regression of: J-56-12 and A-56-02 (round 2's `_narrative_with_clauses`, graph.py:4327-4346, which cuts the clause at its end when the clause alone exceeds the limit)
- In the user's words: with three long conditions set aside (for example a sample description, a platform description and a patient description, each typed as a long phrase) the progress log and Show work end "... and any other condition the" and never say "not applied".
- Evidence: probe of the pure functions, organism mention of 93 characters (Taxonomy accepts up to 100), three condition spans of about 95 characters each, bounded by `_condition_span_text` to 60 plus the elision note: `_organism_records_disclosure` returned 544 characters; `_narrative_with_clauses(model_sentence, [disclosure])` returned 500 characters, `'not applied' in narrative` False, ending `'... [34 more characters elided] and any other condition the'`. The answer note for the same records was 472 characters and complete (TokenPayload allows 1000). The organism mention in the narrative clause is not bounded (`_organism_records_disclosure` uses `organism.mention` raw), while the note bounds it to 60.
- Suggested fix: build the clause so "not applied to the search" comes before the list of names, or cut the names list, never the verb; bound the mention as the note does.
- NOT FIXED

### J2-56-07: a condition span's markup and a model-written organism mention reach the answer note unfiltered

- Severity: non-blocking (minor; the frontend renders note text as escaped React text, so no script runs)
- Inside this round's fix: yes, `_organism_conditions_note` (graph.py:10029-10052) and `_condition_span_text` (graph.py:3088 area)
- What: `_bounded_one_line` removes control characters and newlines and bounds the length; it does not strip Markdown or HTML. The span is the model's tagged text and is not checked against the question (only the retry's organism is). A span such as `**Illumina**`, `<b>Illumina</b>` or `[Illumina](https://example.org)` is emitted verbatim inside a note under the answer, and through `feedback/capture.py::answer_markdown_from` into a saved answer's Markdown, whose renderer's header says that text is "never by a model and never from arbitrary user or external text".
- Evidence: read, not probed end to end. `_bounded_one_line` (graph.py:2698-2713) is the only filter between the span and the note. `useRunView.ts:710-714` pushes `event.payload.text` into notes; `savedAnswerMarkdown.tsx` renders every block as React text (no `dangerouslySetInnerHTML`).
- Suggested fix: accept a released span only when it is text of the question (`_span_is_in_question`, once J2-56-02 is fixed), which bounds it to the person's own words.
- NOT FIXED

### J2-56-08: a second reply that switches "sra" to "assembly" is used, so a person who asked for SRA runs is shown genome assemblies

- Severity: blocking (it contradicts the owner's design as written, "the second reply is used only if it keeps the record type", and it is a confident wrong kind of record; live rate unmeasured, fix is one comparison)
- Regression of: J-56-07 and A-56-04 (round 2's `_second_reply_names_a_question_organism`, src/system_03_search_agent/core/graph.py:4120-4138, checks `second.record_type in breadth_plan.ORGANISM_RECORD_DBS`, not `second.record_type == first.record_type`)
- In the user's words: "Find SRA runs of SARS-CoV-2 sequenced on Illumina": Think's first reply asks for SRA runs and names nothing; asked again, it names SARS-CoV-2 and says "assembly". The person is shown SARS-CoV-2 genome assemblies, with Think's narrative saying it searched genome assemblies, under a question that asked for sequencing runs.
- Evidence: probe through `think_node` (my fakes, no network), first reply `entities: [], record_type: sra`, second `[("SARS-CoV-2", "organism")], record_type: assembly`: printed `calls 2, resolved ['NCBITaxon:2697049'], org ('SARS-CoV-2', 'assembly'), clar None`. The test `test_a_second_reply_that_does_not_name_a_question_organism_keeps_the_first` covers "none" but no switch between the two record kinds. The retry message names the first record type, so the switch is not prompted, but nothing stops it.
- Suggested fix: pass the first classification into the check and require `second.record_type == first.record_type`; add the "assembly" case to that test.
- NOT FIXED

### J2-56-09: the lint gate fails in the worktree today, on the round 2 adversary's untracked probes

- Severity: non-blocking for the builder's commits; blocking for any commit that adds those files as they stand
- Location: testing/Developer/reports/2026-10-06_card56/raw/adversary_r2/compare.py (10 errors) and offline_r2.py (3 errors), both untracked
- Evidence: `PATH=<main venv>/bin:$PATH bash .github/gates/gate03_lint.sh` exited 1, "Found 13 errors. [*] 7 fixable", every error in those two files (unused `noqa: E402` among them, the same kind as J-56-11). `ruff check src tests` printed "All checks passed!".
- Suggested fix: `ruff check --fix` on the adversary's probes before they are committed.
- NOT FIXED

## Checklist verdicts

| Item | Verdict | Evidence |
|---|---|---|
| 1. Round 1 findings fixed as build_r2.md claims | Mostly yes, with three regressions inside the fixes | Probed: J-56-01, J-56-02, A-56-01 (my `_gene_shaped_fallback_candidates` comparison on 15 questions, branch output identical to develop's, "type-2" and "phase-3" give `[]`, "TP53-mutant and KRAS-mutant and EGFR-mutant" gives `['TP53', 'KRAS', 'EGFR']`, "MERS-CoV" `['MERS']`, "BRAF-V600E" `['BRAF', 'V600E']`); J-56-03, A-56-08 (accession and GCF questions 1 call, window 1 call, BRCA1 tagged 1 call); J-56-04 (parse retry message ends `"query_class", "narrative", "entities", "record_type"`, then the SRA route resolved `NCBITaxon:2697049` in 3 calls); J-56-05 (BRCA1 with nothing tagged resolves `NCBIGene:672`, BRCA9 tagged keeps `unresolved ['BRCA9']` and no organism question); J-56-06 (all five dashes claim the organism's tokens when the model tagged the span; a space still offers SARS, stated as residual); J-56-07, A-56-04 ("none" second reply keeps the first and asks which organism, no MedGen search); J-56-08, A-56-07 (mutant E, fresh 45 s budget, went red); J-56-12, A-56-02 (mutant C went red); A-56-03 (mutant F went red; note reaches `write_node` tokens). Regressions: J2-56-01 and J2-56-02 (inside A-56-05's fix), J2-56-08 (inside J-56-07's fix), J2-56-06 (inside J-56-12's fix). Read only: J-56-09 fake change, J-56-10 and J-56-13 bounds (the builder's span test; my J2-56-07 notes markup is not covered), A-56-10 criterion wording, A-56-11 |
| 2. Question shapes against develop | Fail | Traced on both trees with the same fakes (`think_node` then `plan_node`): gene ("What diseases are linked to BRCA1?", identical, 13 calls), disease ("What causes MODY?" with nothing tagged, identical), papers ("Recent papers on TP53 in breast cancer", identical), coordinate window (identical, assembly question asked), accession (1 call, identical outcome), isolate (Klebsiella blaKPC, identical, with and without record type sra), organism assembly (M. tuberculosis, identical), SRA with organism and gene (identical). Worse: follow-up (J2-56-03, blocking) and SRA or assembly questions about a disease with nothing tagged (J2-56-04, by design) |
| 3. The answer note | Pass with findings | Reaches the answer as a note token through `write_node` on the answer branch (builder's test, and mutant F red). Not on the refusal branch (J2-56-05). No path found where the note claims something untrue, except as a consequence of J2-56-01, J2-56-02 and J2-56-08, where the organism or record kind it names is not the one the person asked for. The Show work clause can still be cut (J2-56-06) |
| 4. Decision cap, event schema, cost cap, Think's time budget | Pass | No file under `contracts/` or `frontend/` in the diff (`git diff --stat` empty). `_done_decisions` slices to `_MAX_DONE_DECISIONS` (graph.py:1254), which equals `DonePayload.decisions` `max_length=16` (contracts/events.py:604); `gene_or_condition` is capped at `_MAX_LIVE_SYMBOL_LOOKUPS` (3) per run (graph.py:3151 area). The retry uses the same harness dispatch, so the per-query cap applies; `QueryCapExceededError` keeps the first reply (read; covered by the builder's test, not mutated by me). Budget: probe after a parse retry showed budgets `[45.0, 45.0, 45.0]` with an instant fake, the third being `deadline - now`; mutant E (fresh 45) went red |
| 5. Security | Pass with a minor finding | Retry message carries only `first.record_type` (a `Literal["sra", "assembly", "none"]`, graph.py:2439), the key list from the schema, and the first reply cut to 300 characters (graph.py:4200 area, captured echo in my probe). Decision state is the person's question plus one bounded one-line span (graph.py:3159-3163). The note is one line and bounded, but not stripped of markup (J2-56-07). Log lines carry the bounded error text only. No Cypher, SQL or URL is built from the new text |
| 6. Tests run and broken | Pass | `82 passed in 2.48s` for the two files. Six single-property mutants in the worktree, one at a time, each restored with `git checkout -- src/system_03_search_agent/core/graph.py`: A ("none" accepted) red, B (organism question despite a failed gene) red, C (narrative cut at the end) red, D (no question-text check) red, E (fresh 45 s budget) red, F (note left out of Write) red. `git status --short` after: only untracked report files (`judge_r2.md`, `adversary_r2.md`, `raw/adversary_r2/`). No test covers J2-56-01, J2-56-02, J2-56-03 or J2-56-08, so their mutants would have nothing to turn red |
| 7. Lint gate | Fails in the worktree, clean on the commits | J2-56-09: 13 errors, all in the round 2 adversary's untracked probes; `ruff check src tests` "All checks passed!" |

## Verified by my own probes, versus only read

- Probed (offline, faked model, classifier and NCBI, the same scripts run on this branch and on a copy of origin/develop's `src`): J2-56-01, J2-56-02 (including the word-boundary claim), J2-56-03, J2-56-04, J2-56-05, J2-56-06, J2-56-08, every shape in item 2, the round 1 fixes listed in item 1, the six mutants and the lint gate. Scripts are in the session scratchpad, not committed.
- Read only: J2-56-07 (markup path to the saved answer), the cost-cap branch of the retry, the A-56-10 criterion wording, the builder's live-run numbers in build_r2.md (not re-run: no live model calls in this round).
- Caution for the lead: my six mutants edited `graph.py` in this worktree for a few seconds each while the round 2 adversary's files were appearing beside them. If the adversary ran a probe during one of those windows, its result for that run may reflect a mutant. Each mutant was restored before the next and the tree was clean after.

## Not covered

- Live model behaviour: how often a second reply carries two organisms (J2-56-01), a substring organism (J2-56-02), a switched record kind (J2-56-08), or names nothing on a pronoun follow-up (J2-56-03).
- Act, and Write on real SRA or assembly findings; the note was seen only with the test helpers' graph findings.
- The frontend rendering of a note with markup, in a browser.
- The golden run and rubric, which build_r2.md leaves to the lead.

## Verdict

FAIL against the owner's design.

Blocking:

- J2-56-01 (Regression of A-56-05): a second reply's in-question organism lets a different, invented organism be searched.
- J2-56-02 (Regression of A-56-05): the in-question check is a substring match, so "human" passes inside "nonhuman".
- J2-56-03: a follow-up such as "And its SRA runs?" is asked which organism where develop answered from memory.
- J2-56-08 (Regression of J-56-07 and A-56-04): a second reply that switches "sra" to "assembly" is used, against the owner's "keeps the record type".

Three of the four sit inside fixes made in this round, which is Review rounds rule 4's stop condition: escalate to the owner rather than start another round.

Line confirmations on HEAD e72b66d1 (`grep -n`): the per-run span cap is graph.py:3151, the decision state 3159, the retry echo 4200, `_condition_span_text` 3088.
Correction to the line above: `_condition_span_text` is graph.py:3091, not 3088.
