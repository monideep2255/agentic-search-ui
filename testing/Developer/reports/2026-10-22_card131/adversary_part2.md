# Card 131 part 2, adversary round (pull request #296)

Branch fix/card131-skip-repeated-count-line, commit 0ce8b7ab. Read and run only. Findings are filed as found, ids A-131b-NN.

## Findings

### A-131b-01: a lead whose number word is wrong now stands alone; the code-built count that contradicted it is the line removed
- Severity: major
- What: the grounding pass treats the number words "one" to "ten" as function words (`src/system_03_search_agent/synthesis/grounding.py:328`), so a written sentence saying "four diseases" while citing five records grounds. The lead decider reads the candidates with their markers removed (`src/system_03_search_agent/harness/decide.py:660`), so it cannot see the mismatch either. The subset test at `src/system_03_search_agent/core/graph.py:13830-13836` compares markers only, so it drops the one code-built sentence that stated the true count.
- Reproduction: real `_write_answer` with the `test_write_completeness` fixture, 5 MedGen Disease rows, Synth reply `NCBIGene:672 is associated with four diseases: disease name number 1 [1], disease name number 2 [2], disease name number 3 [3], disease name number 4 [4] and disease name number 5 [5].`, `_lead_sentence_choice` stubbed to 0 (probe `scratchpad/adv131b/probe_adv.py`, case lie5).
  - Branch, Researcher: tokens are the lead claim, `\n\n`, heading `Disease records found`, five table rows. `Found 5 disease records: ...` is not emitted. Call-site flag False.
  - Branch, Plain: the lead, `Where this answer comes from`, five list items, the medical-advice note. `I found 5 conditions on this topic [1][2][3][4][5].` is not emitted.
  - origin/develop, same inputs: both depths emit the count line straight after the lead (`Found 5 disease records: ...` / `I found 5 conditions on this topic [1][2][3][4][5].`).
- Why it matters: the answer's only stated count of diseases is now the model's wrong one, in bold as the main point. The reader sees "four diseases" over five rows; on develop the code-built "Found 5" sat right under it. A confident wrong number is worse than a repeated right one. Worse than develop.
- NOT FIXED

- A-131b-01 addendum, two more replies that ground and drop the count line, same probe, both depths, flag False, lead 0 (cases only1 and two):
  - `NCBIGene:672 is associated with one disease, disease name number 1 [1], and the records also list disease name number 2 [2], disease name number 3 [3] and disease name number 4 [4].` is the whole summary; develop would follow it with `Found 4 disease records: ...`.
  - `NCBIGene:672 is associated with two diseases: disease name number 1 [1] and disease name number 2 [2], disease name number 3 [3], disease name number 4 [4].` is the whole summary.
  - Negating leads (`None of ... is associated with NCBIGene:672.`, `NCBIGene:672 is not associated with ...`) are stripped by grounding, so the count line opens as before. The hole is the number words, not negation.

### A-131b-02: the call-site flag is True on every clinical-features question, even when the count line carries no gap clause, so the repeat is kept there
- Severity: minor
- What: `src/system_03_search_agent/core/graph.py:15521-15526` sets `summary_has_extra_clause` whenever `_asked_field(...)` returns an `AskedField`, which is whenever `think.asks_features` said yes (`graph.py:13037-13039`). The clause is only written when `records_lack_field` also holds (`answer_layout.py`, `finish()` in `answer_summary_sentence`). The same over-reach applies to the total: the flag is True whenever a truncated finding has a known total, while the line prints a total only when it exceeds the counted records. The flag predicts the inputs, not the clause, so it is not "told by the call site" whether the line says more.
- Reproduction: same probe, case feat, `_clinical_features_asked` stubbed True, 4 Disease rows, reply `NCBIGene:672 is associated with disease name number 1 [1], disease name number 2 [2], disease name number 3 [3] and disease name number 4 [4].`, lead 0. Flag True. Researcher tokens: the lead, then `Found 4 disease records: disease name number 1 [1], ... and disease name number 4 [4].` with no gap clause. Plain: the lead, then `I found 4 conditions on this topic [1][2][3][4].`
- Why it matters: on clinical-features questions the answer still says the same thing twice, which the card was meant to stop. Not worse than develop; the card's goal is missed on a whole question class.
- NOT FIXED

- A-131b-01 addendum, no gate would catch it (read, not run): the test-queries gate's `count_matches_list` (`testing/Developer/reports/2026-09-26_test_queries_gate/run_test_queries.py:1320-1350`) reads only the FIRST claim and matches `\b[Ff]ound (\d[\d,]*)\b`. With a lead picked the first claim is the lead, so a lead saying "four diseases" in words returns NA ("the opening states no count"), on develop and on the branch alike. Before this change the true count still sat in the second claim for the reader; after it, nothing on screen or in the gate checks the lead's number.
- Saved answer and command line, probed (case lie5, `ADV_SURFACES=1`, `answer_markdown_from` and `adapters/cli/render.Renderer` fed the run's events): both show the lead and then the list, with no count line, matching the live tokens token for token. So the A-131b-01 answer reopens and prints the same way; the surfaces agree, which also means none of them restores the count.

### A-131b-03: on a follow-up that says "it", the count line was the only place naming the subject the answer is about; skipping it leaves the subject unnamed
- Severity: unsure (the reproduction forces the lead pick; a live lead decider is told not to pick a sentence that only names records)
- What: the count line carries `_summary_subject(state)` (`graph.py:12785-12800`), which on a follow-up is the remembered subject (`next_step_entity_label`). The subset test (`graph.py:13830-13836`) does not consider whether the lead names a subject, so when the lead cites every record but names none, the remembered subject leaves the screen with the count line. The Researcher table rows and the Plain list name the diseases, never the gene.
- Reproduction: same probe, case followup3: question `And which diseases is it linked to?`, `next_step_entity_label="BRCA1"`, 4 Disease rows, reply `Disease name number 1 [1], disease name number 2 [2], disease name number 3 [3] and disease name number 4 [4] are the diseases it is linked to.`; grounding keeps `Disease name number 1 [1], disease name number 2 [2], disease name number 3 [3] and disease name number 4 [4].`, lead stubbed 0, flag False.
  - Branch, both depths: the summary is that bare list, then the records. "BRCA1" appears in no token.
  - origin/develop: the bare list is followed by `Found 4 disease records for BRCA1: ...` (Researcher) or `I found 4 conditions related to BRCA1 [1][2][3][4].` (Plain).
- Why it matters: on a follow-up the reader cannot see which gene "it" was resolved to, the one check that the memory picked the right subject. A wrong remembered subject (a known follow-up failure class) would then be invisible. I could not make a realistic subject-free lead ground with this fixture (`It is linked to ...` and `Four diseases are linked: ...` grounded nothing), so how often a live lead lacks the subject is unmeasured.
- NOT FIXED

### A-131b-04: in Plain language the count line was the only place saying which records are of which kind; skipping it leaves a list of bare titles
- Severity: minor
- What: for records of two or more types, the Plain count line splits the count by kind ("I found 2 conditions and 2 genes on this topic [1][2][3][4]."), and the Plain listing under "Where this answer comes from" shows titles only, with no type and no per-type heading. The subset test (`graph.py:13830-13836`) drops the line once the lead cites all four, so nothing in a Plain answer tells a condition from a gene. Researcher keeps per-type headings ("Disease records found", "Gene records found"), so only Plain loses it.
- Reproduction: same probe, case mixed: rows MedGen:C1, MedGen:C2 (Disease) and NCBIGene:3, NCBIGene:4 (Gene), reply `NCBIGene:672 is associated with disease name number 1 [1], disease name number 2 [2], gene name number 3 [3] and gene name number 4 [4].`, lead 0, flag False. Plain tokens: the lead, heading `Where this answer comes from`, four list items, the medical-advice note. The saved answer reopens as `## Where this answer comes from` then `- disease name number 1[1]`, `- disease name number 2[2]`, `- gene name number 3[3]`, `- gene name number 4[4]`. The skipped line was `I found 2 conditions and 2 genes on this topic [1][2][3][4].`
- Why it matters: a Plain reader, the one with no technical background, sees four names under one heading with nothing saying two are genes and two are conditions, while the lead says the subject is "associated with" all four. With real names (a gene symbol next to a syndrome) a lay reader can read a gene as a disease. Worse than develop for this reader.
- NOT FIXED

### Checked and not filed
- Ordering, probed by reading the call order and by the end-to-end runs: the sentence check (`_ground_with_sentence_check`, `graph.py:14573`, `14732`) and the completeness repair run before the lead pick; card 17's `name_switched_records` runs after the pick but never on the lead; card 111's echo drop excludes `lead_index`. In every run above the lead token was emitted whenever the count line was skipped. No path found where the count line goes and the lead then goes too.
- `_answer_tokens`, the one other caller that could carry a lead, is called only by tests (`grep "_answer_tokens(" src` finds none), and no existing test outside the new file passes a `lead_index`, so the default `summary_has_extra_clause=True` hides nothing on a live path.
- Negating leads ("None of ...", "... is not associated with ...") are stripped by grounding before the lead pick.
- Surfaces: no frontend or adapter code reads the second summary claim by position (`grep` of `frontend/src`, `adapters/mcp/server.py`, `adapters/web_sse/app.py`); the saved answer and the command line rebuild from the same tokens (probed, A-131b-01 addendum).
- A lead picked in one depth and not the other changes whether the count line shows by depth; that follows from the writer's different prose per depth, not from this change, and the line's records are the same at both depths.

## Verdict

FAIL against the card's acceptance and the bar of nothing worse than develop.

- Verified by my own probes (real `_write_answer`, stubbed Synth reply, lead pick stubbed, scratch develop copy from `git archive origin/develop` for comparison):
  - A-131b-01 (major, worse than develop): a lead with a wrong number word ("four diseases" over five cited, also "one disease" and "two diseases" over four) now stands alone in both depths; develop printed the code-built true count beneath it. Saved answer and command line match the live tokens.
  - A-131b-02 (minor): on every clinical-features question the flag is True and the repeat stays, with no gap clause printed.
  - A-131b-03 (unsure): on a follow-up the remembered subject's name leaves the screen with the count line, shown only with a forced pick of a bare-names lead.
  - A-131b-04 (minor, worse than develop for Plain readers): with mixed record types, Plain loses the only statement of which records are genes and which are conditions.
- Read only, not probed: the test-queries gate's `count_matches_list` behaviour (reads the first claim only, so NA with any lead, on both branches); the frontend pager and `mainPointFor`; GraphQL and MCP replay.
- Not inside a fix made during this phase: this is card 131 part 2's first build, so the review loop's stop condition does not fire on these findings.
- Worktree left clean: `git diff HEAD --stat` empty, `git status --short` shows only `?? frontend/node_modules`. Probes and the develop copy live in `scratchpad/adv131b/`.
