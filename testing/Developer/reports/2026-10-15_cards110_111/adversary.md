# Adversary round on cards 110 and 111

Branch commit 409a0610, compared with develop cffdb8fd. Dial position 2, one round. Findings are appended as they are established.

## Findings

### A-110-01: The BRCA1 Plain language answer now opens on "Changes in this gene ...", a third sentence that leans on what came before, where develop opened on the count line
- Severity: major (inside this round's card 110 change)
- What: with four candidates, the lead pick reached sentence 3 of the writer's prose and put it first, emphasized. The sentence opens "Changes in this gene", so "this gene" points back at sentences that now come after it, and it answers only a side of the question (which share of inherited breast and ovarian cancer) while the four diseases asked for are not in it. The criteria's own "neither" text names "needs an earlier sentence to make sense"; the classifier did not apply it here. On develop the same grounded prose offers only sentences 1 and 2, and the count line leads.
- Reproduction, live on the branch (409a0610, develop's writer z-ai/glm-5.2, Jev, reads_placement=True), question "Which diseases are associated with BRCA1?", Plain language, run bbrca_2, cost $0.0197:
  - Grounded sentences, in order: "The gene, whose symbol is BRCA1, acts as a tumor suppressor that helps maintain genomic stability [5] [23]." / "Its protein participates in transcription, repair of DNA double-stranded breaks, and recombination [23]." / "Changes in this gene account for roughly 40% of inherited breast cancers and over 80% of inherited breast and ovarian cancers [23]."
  - Decision: `chosen='third', decided_by='jev', jev_confidence=0.93`, 225 ms.
  - Summary as sent: "Changes in this gene account for roughly 40% of inherited breast cancers and over 80% of inherited breast and ovarian cancers [23]." / "I found 4 conditions related to BRCA1 [1][2][3][4]." / "The gene, whose symbol is BRCA1, acts as a tumor suppressor ..." / "Its protein participates in ..."
- Replay of the lead decision only, live Jev, on that same saved grounding, three times per side:
  - develop cffdb8fd: `pick None ... -> COUNT LINE` 3 of 3 (216, 256, 261 ms), `candidates offered: 2`.
  - branch 409a0610: `pick 2 ... -> Changes in this gene account for roughly 40% ...` 3 of 3 (250, 218, 226 ms), `candidates offered: 3`.
- What a person sees: they ask which diseases BRCA1 is linked to; the bold opening line says "Changes in this gene account for roughly 40% of inherited breast cancers ...", "this gene" before any gene is named, then a count, then "The gene, whose symbol is BRCA1, ..." introducing the gene after the fact. The paragraph reads backwards. Develop showed the count line first and the prose in its written order.
- NOT FIXED

### A-111-01: A sentence that IS the answer, a cited list of the asked-for names, is cut from the summary whenever it does not lead
- Severity: major (inside this round's card 111 change)
- What: `_is_label_only_sentence` treats a sentence of cited record names as noise, whatever the question asked. When the question asks for names ("Which diseases are associated with BRCA1?"), the bare cited list of those names is the answer, and the branch removes it from the prose unless the lead pick happened to choose it. The only guard is "every model sentence is label-only"; one other sentence anywhere disables it. It does not lead when: it is the fifth grounded sentence or later (the pick sees four), Jev says "neither" or is late (1 s) or fails, or the classifier is the guard tier (`CLASSIFIER_PROVIDER` default "guard", where the lead is never asked).
- Reproduction (offline replay of `_answer_parts` on the saved kwargs of live run dbrca_1, its real citations and findings, writer sentences replaced; display labels [1] to [4] are the four MedGen `name` findings):
  - Prose: four ordinary sentences, then "Familial cancer of breast [1], Familial breast-ovarian cancer susceptibility 1 [2], Pancreatic cancer susceptibility 4 [3] and Fanconi anemia complementation group S [4]."
  - Live Jev lead decision on the branch, three runs: `pick None ... -> COUNT LINE` 3 of 3 (182, 409, 197 ms), `candidates offered: 4`.
  - develop summary: "I found 4 conditions related to BRCA1 [1][2][3][4]." / three sentences / "BRCA1-BARD1 promotes RAD51-mediated homologous DNA pairing [6]." / "Familial cancer of breast [1], Familial breast-ovarian cancer susceptibility 1 [2], Pancreatic cancer susceptibility 4 [3] and Fanconi anemia complementation group S [4]."
  - branch summary: "I found 4 conditions related to BRCA1 [1][2][3][4]." / the same three sentences, and nothing more. The disease names and the BRCA1-BARD1 finding are gone.
  - Same list as sentence 2 of 2 with no lead (the guard-tier path): develop keeps it, branch prints only the count line and sentence 1. When Jev is offered it in the first four it does pick it (`pick 1` 3 of 3), so the live Jev path survives only while the list sits in the first four.
- What a person sees: they ask which diseases BRCA1 is linked to; the summary says "I found 4 conditions" and never names one; the names are only in the record list below. A writer reply that named them is thrown away.
- NOT FIXED

### A-111-02: A paper title that states a finding is cut as "only a title"
- Severity: minor to major (unsure: depends how often the writer copies a title whole, which the grounding pass rewards because a whole title grounds exactly)
- What: a title is a claim in many papers ("BRCA1-BARD1 promotes RAD51-mediated homologous DNA pairing."). A sentence that is that title with its marker is dropped as label-only. The check cannot tell a title that names from a title that asserts. Also matched as label-only, from `_clean_claim`'s glue list: "FBN1 [1] or Loeys-Dietz syndrome [6].", "Marfan syndrome [2] but Loeys-Dietz syndrome [6].", "BRCA1 [7]: Breast cancer [8].", and a negating title "Not associated with cancer risk [9]." (unit probe of `_is_label_only_sentence`, all printed `True`).
- Reproduction (same offline replay, dbrca_1, lead none): prose "BRCA1 is a gene that ... tumor suppressor [23]." / "Targeting GPX4-mediated ferroptosis protection sensitizes BRCA1-deficient cancer cells to PARP inhibitors [20]." / "Preneoplastic stromal cells promote BRCA1-mediated breast tumorigenesis [14]."
  - develop: count line, then all three sentences.
  - branch: count line, then only "BRCA1 is a gene that ... tumor suppressor [23]." Both findings are gone from the prose.
- What a person sees: the summary that reported two research findings now reports none; the titles are among the record list, not said as findings.
- NOT FIXED

### A-110-02: A bare paper title can now open the answer, while the same kind of sentence is cut everywhere else
- Severity: minor (inside this round's changes, where cards 110 and 111 meet)
- What: the lead candidates are not filtered by the card 111 check, and a picked lead is exempt from it. With four candidates the pick reaches a title-only sentence that develop could not reach, and it opens the answer emphasized; the title-only sentence next to it is dropped. One rule for "a sentence that is only a title" in the body, the opposite rule for the opening.
- Reproduction (offline grounding from dbrca_1, prose as in A-111-02, question "Which diseases are associated with BRCA1?", live Jev decision only):
  - develop: `pick None ... -> COUNT LINE` 3 of 3, `candidates offered: 2`.
  - branch: `pick 2 ... -> Preneoplastic stromal cells promote BRCA1-mediated breast tumorigenesis [14].` 3 of 3, `candidates offered: 3`.
  - branch summary with that pick: "Preneoplastic stromal cells promote BRCA1-mediated breast tumorigenesis [14]." / "I found 4 conditions related to BRCA1 [1][2][3][4]." / "BRCA1 is a gene that ... tumor suppressor [23]." The GPX4 title sentence is dropped.
- What a person sees: asked which diseases BRCA1 is linked to, the bold first line is one paper's title.
- NOT FIXED

### A-110-03: The Marfan question still opens on the count line when the writer puts four sentences ahead of the features list
- Severity: minor (the card's own words say "one of the first few"; the person's complaint, PR-87-04, still recurs)
- What: the bound of four candidates is a fixed slice of the grounded prose. Develop's writer, live, put the features sentence fifth in 1 of 5 runs, and the branch's lead pick, given that same grounding, cannot reach it.
- Reproduction: live run d66_2 on develop (z-ai/glm-5.2, Jev), "What phenotypic features are associated with Marfan syndrome?", Plain language. Grounded sentences in order: "Marfan syndrome is a multisystem connective tissue disease ... [83]." / "It is mainly caused by FBN1 gene mutation ... [83]." / "There is still no radical treatment method for MFS ... [83]." / "The Ghent II Nosology of MFS criteria are crucial in MFS diagnosis ... [84]." / "MedGen lists these clinical features: Aortic regurgitation [3], ...". Replaying the branch's lead decision on that grounding, live Jev, three times: `pick None ... -> COUNT LINE` 3 of 3 (249, 195, 170 ms), `candidates offered: 4`. For contrast, develop run d66_5 (features third) replayed on the branch: `pick 2 -> MedGen lists these clinical features ...` 3 of 3, so the change does fix the third-place case.
- What a person sees: about one time in five on develop's writer, still "I found 5 published papers, 1 condition, 1 literature index entry and 5 clinical trials related to Marfan syndrome" first and the features fifth.
- NOT FIXED

### A-111-03: When the writer's whole prose is label-only, the summary still ends on "Marfan syndrome and Marfan syndrome."
- Severity: minor (a stated design choice in build.md, but the card's words are "never")
- What: the keep-everything guard (`lead_text is None and len(echo_positions) >= len(sentences)`) restores every label-only sentence when no other model sentence exists. The count line is always there in that case, so the summary would not be empty without them.
- Reproduction (offline replay on live run b66_1's kwargs, branch, lead none): prose "Marfan syndrome [80] and Marfan syndrome [82]." gives summary "I found 1 condition related to Marfan syndrome [1]." / "Marfan syndrome [80] and Marfan syndrome [82]."; prose of two label-only sentences gives the count line, "Marfan syndrome [80] and Marfan syndrome [82].", "What Is Marfan Syndrome? [78]".
- What a person sees: exactly the sentence the card names, at the end of the summary.
- NOT FIXED

### A-111-04: A marker placed before a "?" or "!" defeats the check
- Severity: minor
- What: the end test strips only " .,;:" after the last marker, so a title ending in "?" with the marker before it is kept, while the same title with the marker after it is dropped.
- Reproduction (unit probe, branch): `_is_label_only_sentence('What Is Marfan Syndrome? [78]', {78: 'What Is Marfan Syndrome?'})` printed `True`; `_is_label_only_sentence('What Is Marfan Syndrome [78]?', {78: 'What Is Marfan Syndrome?'})` printed `False`; "Marfan syndrome [2]!" printed `False`.
- What a person sees: a title-only sentence survives or not depending on where the writer put the marker.
- NOT FIXED

### A-110-04: Jev picks "One is ..." and "These include ..." as the opening line once they are offered in third or fourth place
- Severity: major (inside this round's card 110 change; the same shape as PR-19-06, now promoted to the bold first line)
- What: the "neither" criterion says a sentence that "needs an earlier sentence to make sense" must not lead, and the "third"/"fourth" criteria say "read on its own". Jev ignores that for a sentence that names the asked-for thing behind a pronoun. Develop never offered sentences 3 and 4, so this could not lead there. The writer produces this shape in Plain language (PR-19-06's live answer: "One is double-strand break repair via homologous recombination. Another is DNA repair. ...").
- Reproduction (live Jev, lead decision only, question "Which diseases are associated with BRCA1?", candidates in this order, markers are real display indices from run dbrca_1):
  - "The protein it produces joins with ... watches for DNA damage [23]." / "It plays a role in repairing double-stranded breaks in DNA and in recombination [23]." / "One is familial breast-ovarian cancer susceptibility 1 [2]." / "Another is Fanconi anemia complementation group S [4]."
  - branch: `pick 2 ... -> One is familial breast-ovarian cancer susceptibility 1 [2].` 4 of 4 (275, 256, 182, 253 ms), `candidates offered: 4`.
  - develop, same sentences: `pick None ... -> COUNT LINE` 2 of 2, `candidates offered: 2`.
  - branch summary with that pick: "One is familial breast-ovarian cancer susceptibility 1 [2]." / "I found 4 conditions related to BRCA1 [1][2][3][4]." / "The protein it produces joins with ..." / "It plays a role in ..." / "Another is Fanconi anemia complementation group S [4]." The pair "One is ... Another is ..." is split across the paragraph.
  - Second shape, fourth place: "These include familial cancer of breast [1] and pancreatic cancer susceptibility 4 [3]." after three gene sentences: branch `pick 3 -> These include familial cancer of breast ...` 4 of 4 (193, 198, 184, 204 ms).
- What a person sees: the answer opens in bold on "One is familial breast-ovarian cancer susceptibility 1." with nothing saying one of what; its partner "Another is ..." turns up four lines later.
- NOT FIXED

### A-110-05: A candidate sentence longer than 700 characters is now judged on its first 700 only
- Severity: minor, unsure (no live sentence of this length was seen in this round; the real features sentence opens with its answer)
- What: `_LEAD_CANDIDATE_MAX_CHARS` fell from 1200 to 700 so four candidates fit the state. A grounded sentence of 700 to 1200 characters whose answering clause comes late is now cut before that clause, so the classifier cannot see it; on develop it saw the whole sentence.
- Reproduction (`lead_sentence_state` on each side, one candidate of 856 characters whose last clause is "and its main features are ectopia lentis and aortic root aneurysm [3]."): develop printed `adev 856 ectopia in state: True`; branch printed `a110 856 ectopia in state: False`.
- What a person sees: a long sentence that answers at its end stops being chosen as the opening, and the count line leads instead.
- NOT FIXED

### A-110-01 addendum: develop opens on the same sentence when it sits second
- Later live runs: develop run dbrca_4 picked `chosen='second', jev_confidence=0.73` and opened on "Changes in this gene cause roughly 40% of inherited breast cancers and over 80% of inherited breast and ovarian cancers [23]."; branch run bbrca_4 did the same from second place (`jev_confidence=0.66`). So Jev's willingness to open on this "this gene" sentence is older than card 110. What card 110 adds is reach: on bbrca_2 the sentence sat third, and only the branch could open on it (the replay above, 3 of 3 against develop's count line 3 of 3). Across the seven live BRCA1 runs per side here, the branch opened on a "Changes in this gene" sentence 2 of 5 times it ran (bbrca_2, bbrca_4) and develop 1 of 5 (dbrca_4). Severity stays major for the class, with this context: the defect is not new, its frequency is raised by this change.

- Correction to the addendum: five live BRCA1 runs per side, not seven (bbrca_1 to bbrca_5, dbrca_1 to dbrca_5).

### A-111-01 and A-111-02 addendum: the real grounding pass accepts these sentences whole
- `run_grounding_pass` on the dbrca_1 synth findings (branch), writer text "Familial cancer of breast [1], Familial breast-ovarian cancer susceptibility 1 [2], Pancreatic cancer susceptibility 4 [3] and Fanconi anemia complementation group S [4]. Targeting GPX4-mediated ferroptosis protection sensitizes BRCA1-deficient cancer cells to PARP inhibitors [n]. BRCA1-BARD1 promotes RAD51-mediated homologous DNA pairing [m].", printed all three back as `GROUNDED:` with nothing stripped. So these are sentences the shipped pipeline lets through to `_answer_parts`, not inputs only a replay can make.

### A-110-06: A lead pick at confidence 0.04 still opens the answer (older than this change; more candidates give it more to pick from)
- Severity: minor (pre-existing on develop, not introduced by cards 110 or 111)
- What: `_lead_sentence_choice` takes Jev's choice whatever its confidence. On develop, live, Jev chose "first" at 0.04 for a sentence that leans on earlier ones ("A third trial ..."), and it opened the answer.
- Reproduction: live run dtrial_1 on develop cffdb8fd, "Which clinical trials have tested drugs for Marfan syndrome?", Plain language: `chosen='first', decided_by='jev', jev_choice='first', jev_confidence=0.04`, 170 ms; summary "A third trial tested angiotensin converting enzyme inhibitors in Marfan syndrome [3]." / "I found 5 clinical trials and 43 published papers related to Marfan syndrome [1]...[20]."
- What a person sees: the answer opens on "A third trial ..." with no first or second trial anywhere in the summary.
- NOT FIXED

## Live runs, branch against develop

Setup: `core/run.py` `run_streaming`, `reads_placement=True`, `CLASSIFIER_PROVIDER=jev`, `PER_QUERY_COST_CAP_USD=0.25`, `SYNTH_MODEL=z-ai/glm-5.2` (priced by a scratch-only fallback entry), guard and plan `deepseek/deepseek-v4-flash`, Plain language. Interaction capture and session memory were stubbed to no-ops, and the user database and Redis variables unset, so no run wrote to any database. Branch worktree at 409a0610, develop worktree at cffdb8fd. "Echo" means a "Marfan syndrome and Marfan syndrome." style sentence in the summary. Pick is Jev's choice and confidence, with the number of candidates offered in brackets. Latency is the whole lead decision in ms.

| Run | Side | Opens on | Echo | Pick (offered) | Latency | Cost USD |
|---|---|---|---|---|---|---|
| b66_1 | branch | features sentence | no | second 0.95 (2) | 168 | 0.0205 |
| b66_2 | branch | features sentence | no | second 0.95 (2) | 255 | 0.0195 |
| b66_3 | branch | features sentence | no | first 0.97 (3) | 237 | 0.0185 |
| b66_4 | branch | features sentence | no | third 0.97 (3) | 243 | 0.0196 |
| b66_5 | branch | features sentence | no | first 0.96 (1) | 175 | 0.0187 |
| d66_1 | develop | features sentence | no | first 0.98 (1) | 199 | 0.0186 |
| d66_2 | develop | count line | no | neither 0.97 (2) | 290 | 0.0190 |
| d66_3 | develop | features sentence | no | second 0.95 (2) | 266 | 0.0183 |
| d66_4 | develop | features sentence | no | second 0.95 (2) | 195 | 0.0192 |
| d66_5 | develop | count line | no | neither 0.98 (2) | 224 | 0.0202 |
| bbrca_1 | branch | "BRCA1 is linked to four diseases: ..." | no | first 0.99 (3) | 256 | 0.0195 |
| bbrca_2 | branch | "Changes in this gene account for roughly 40% ..." | no | third 0.93 (3) | 225 | 0.0197 |
| bbrca_3 | branch | count line | no | neither 0.98 (2) | 183 | 0.0218 |
| bbrca_4 | branch | "Changes in this gene account for roughly 40% ..." | no | second 0.66 (2) | 199 | 0.0200 |
| bbrca_5 | branch | "BRCA1 is associated with four diseases: ..." | no | first 1.0 (1) | 423 | 0.0199 |
| dbrca_1 | develop | "BRCA1 is associated with four diseases: ..." | no | first 1.0 (2) | 222 | 0.0214 |
| dbrca_2 | develop | "BRCA1 is associated with four diseases: ..." | no | first 1.0 (2) | 204 | 0.0197 |
| dbrca_3 | develop | "BRCA1 is associated with four diseases: ..." | no | first 1.0 (1) | 168 | 0.0209 |
| dbrca_4 | develop | "Changes in this gene cause roughly 40% ..." | no | second 0.73 (2) | 169 | 0.0203 |
| dbrca_5 | develop | "BRCA1 is associated with four diseases: ..." | no | first 1.0 (2) | 470 | 0.0205 |
| bgene_1, bgene_2 | branch | "The gene mutated in Marfan syndrome is fibrillin 1 ..." | no | first 1.0 (2), first 1.0 (2) | 171, 188 | 0.0192, 0.0195 |
| dgene_1, dgene_2 | develop | same sentence | no | first 1.0 (1), first 1.0 (1) | 206, 198 | 0.0197, 0.0202 |
| btrial_1, btrial_2 | branch | count line, no grounded prose | no | not asked (0) | none | 0.0183, 0.0191 |
| dtrial_1, dtrial_2 | develop | "A third trial ..." / "Another trial ..." | no | first 0.04 (1), first 0.18 (1) | 170, 176 | 0.0092, 0.0086 |

Questions: 66 is "What phenotypic features are associated with Marfan syndrome?"; brca is PR-19-06's "Which diseases are associated with BRCA1?"; gene is "Which gene is mutated in Marfan syndrome?"; trial is "Which clinical trials have tested drugs for Marfan syndrome?".

What the table shows:

- Query 66: branch opened on the features sentence 5 of 5, develop 3 of 5. Card 110 fired live once (b66_4, features third, picked "third"). Develop's two count-line openings had the features sentence fifth (d66_2) and third (d66_5); replayed on the branch, d66_5 is fixed (3 of 3) and d66_2 is not (A-110-03). Five runs per side is a small sample; the difference is consistent with the mechanism but not a measured rate.
- Card 111 never fired live: no echo sentence appeared in 28 runs, and replaying all 26 saved `_answer_parts` inputs through both sides' code, with the run's lead and with no lead, gave `compared 51 diffs 0`. The card 111 drop has no live proof from this round either; it is proved only by offline cases, and those offline cases show it also drops answers (A-111-01, A-111-02).
- The features directive's list shape: every features sentence on both sides, 10 of 10, already had "and" only once, before the last name. Develop's writer did not show the problem in this sample, so the directive change has no observed effect here.
- Lead latency: 168 to 470 ms on both sides live, and 155 to 409 ms in the four-candidate replays. No run neared the 1 s bound.
- Spend: live runs $0.5297, plus about 50 replayed lead decisions at about $0.00003 each, about $0.53 in total, under the $1.00 budget.

## Verified by my own probes, and only read

- Probed: every finding above; the live table; the zero-difference replay of all saved writer replies; `_is_label_only_sentence` on 21 hand cases; the 700-character state cut on both sides; the real grounding pass accepting the label-only sentences; the builder's four test files run green on the branch (166 passed, not counted as evidence).
- Only read: the builder's mutation table and gate results; the guard-tier and late-pick paths (no probe forced Jev to fail); whether the listing shows every record a dropped sentence cited in every depth (checked in one live q66 run only: every cited title appeared in the listing).

## Learnings

- None over five minutes. Two small ones: zsh does not split an unquoted `$4` into words, so a loop ran one run with a label of "2 3 4 5" and had to be rerun; and a probe script named `inspect.py` shadowed the standard library module.

## Verdict

FAIL: A-110-01, A-110-04 and A-111-01 (major, all inside this round's changes), with A-110-02, A-110-03, A-110-05, A-111-02, A-111-03, A-111-04 minor and A-110-06 minor and older than this change.

- Correction to "What the table shows": the replay covered all 28 saved `_answer_parts` inputs (one per live run), giving 51 comparisons because a run whose lead was already none is compared once.
