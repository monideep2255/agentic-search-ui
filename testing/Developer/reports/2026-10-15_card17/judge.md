# Card 17 judge, round 1

Judge on fix/card17-name-the-paper at ec0349a7 against develop 7626fe85. Findings are appended as they are established. Worktrees: a detached one at ec0349a7 and one at 7626fe85, both in the session scratchpad.

## Findings

### J-17-01: a lead-in can quote an empty title, `From the paper "": ...`
- Severity: minor (unsure how often a blank label finding reaches the write step)
- What: `name_switched_records` takes the quoted title from the FIRST `LABEL_FIELDS` finding on the page (`title_by_page`), with no check that it has text, while the shared-word test reads every label on the page (`record_labels_by_page`). When the first label finding is blank, whitespace, or only punctuation and brackets ("[.]", "."), and a later label finding on the same page (a `name`) carries the one shared word, the pass fires and quotes nothing.
- Reproduction: judge probe, neutral records, branch src. Page 2 has a `title` finding with value "" (also tried "   ", "[.]", ".") and a `name` finding "Valleys of canyons"; previous sentence cites page 1; switched sentence "Valleys like these hold fine silt [2]." with an evidence quote. Output for all four: `named=1`, `'From the paper "": Valleys like these hold fine silt [2].'`
- Why it matters: the lead-in is the one piece of code-built text the card adds, and here it tells the reader nothing while looking like a defect. Checklist item 3 ("always the label of a page the sentence cites") holds only in the sense that "" is that finding's value.
- NOT FIXED

### J-17-02: the pass judges "the sentence above" on an order the reader never sees, so a switched sentence can still ship bare
- Severity: major (unsure how often it occurs live; it is the card's own failure shape)
- What: the design says reading order "is only final after" `drop_record_restatements`, and the pass runs there. It is not final. Two later steps in `core/graph.py` change which sentence sits above another: card 111's `_label_only_positions` (called in `_answer_parts`) removes a sentence that repeats one label cited to two records, and `_lead_sentence_choice` can pick position 1 to open the answer, skipping it in the prose. In both cases the pass compared a sentence against a sentence the reader does not see above it.
- Reproduction: judge probe on branch src, neutral records. s0 "Glacier melt feeds the high lakes [1]." (page 1); s1 "Valley floors [2] and Valley floors [4]." (pages 2 and 3, both titled "Valley floors."); s2 "Valleys like these hold fine silt [3]." (page 2 abstract, reworded, one shared title word). `name_switched_records` returns `named 0`, s2 bare, because s1 shares page 2. `_label_only_positions(sentences, citations, findings, listing=["Valley floors [2].", "Valley floors [4].", ...])` returns `{1}`, so the reader sees s0 (page 1) directly above a bare s2 (page 2). The same s0, s2 pair through the pass gives `named 1`, `From the paper "Valley floors": Valleys like these hold fine silt [3].` The lead case: `_lead_candidates` returns `[0, 1]`; when the decision picks 1, s2 follows s0 in the prose with no lead-in computed against s0.
- Why it matters: "never points at the wrong paper" is broken in exactly the case the card names, whenever card 111 or the lead pick reorders. Both later steps are themselves recent (card 111 narrowed in the fix round of 2026-10-15). This sits inside this phase's fix (the placement of the pass), not in older code.
- NOT FIXED

### J-17-03: no test fails when the write step stops calling the pass
- Severity: major (test gap on the only line that puts the change in front of a user)
- What: the single call `grounding, switches_named = name_switched_records(grounding, synth_findings)` in `core/graph.py` `_write_answer` is covered by no unit test. The new core test hand-builds a lead-in string and exercises card 111 and `_lead_candidates`; it never runs the write step.
- Reproduction: in a judge worktree at ec0349a7, replaced that line with `switches_named = 0 and name_switched_records`, then ran `pytest tests/system_03_search_agent/synthesis tests/system_03_search_agent/core -m "not integration" -q`: `2296 passed, 66 skipped, 1 deselected, 1 xfailed`, identical to the unmutated run. File restored with `git checkout`.
- Why it matters: a later merge or refactor of `_write_answer` can drop the call and every gate stays green; only a live run would notice. The live traces in raw/live show the call ran on 2026-10-15, which is evidence for this commit only.
- NOT FIXED

### J-17-04: three stated properties of the pass survive mutation, and one "mutation proof" is vacuous
- Severity: minor
- What: single-property mutations of `answer_layout.py`, each run against `test_answer_layout.py`, `test_sentence_check.py` and `test_summary_label_only_sentence.py` (213 tests), stayed green:
  - `any(claim.evidence_quote ...)` changed to `all(...)` (condition 2 for a sentence with one copied and one reworded claim): `213 passed`.
  - the quoted title taken from the LAST label finding on the page instead of the first (`and page not in title_by_page` removed): `213 passed`.
  - mixed record types in one lead-in ("the records") changed to "the paper": `213 passed`.
  For contrast, these went red: quote translation removed (1 failed), trailing full stop kept (3 failed), "the papers" plural removed (1 failed), "the record" fallback removed (1 failed), the short form's long-form check removed in `names_by_short_form` (1 failed).
  Separately, `test_card_17_a_one_word_switch_is_kept_and_names_its_paper` in `test_sentence_check.py` monkeypatches `name_switched_records` to `lambda g, f: (g, 0)` and then asserts that the lambda returns its input bare. That half asserts on the test's own stub and passes whatever the code does; the build report counts it as a mutation proof.
- Reproduction: the mutations above, applied one at a time with an exact-once string replace and restored with `git checkout`; outputs quoted inline.
- Why it matters: the mixed copied-and-reworded sentence and the mixed-type wording are both live shapes (a sentence citing a MedGen record and a paper), and nothing pins them.
- NOT FIXED

### J-17-05: a sentence citing a labelled paper and an unlabelled record is credited to the paper alone
- Severity: minor (unsure; no bench case, design condition 5 only says the record must have a label)
- What: `named_pages` keeps only pages with a label finding, so when a switched sentence cites one labelled page and one page without any `LABEL_FIELDS` finding, the lead-in names only the paper, in the singular, and reads as if the whole sentence came from it.
- Reproduction: judge probe, branch src. Previous sentence cites page 1. Sentence "Valleys like these hold fine silt and the variant is benign [2] [3]." citing a paper titled "Valley floors." (reworded) and a ClinVar variation page whose only finding is `clinical_significance` "Benign". Output: `1 From the paper "Valley floors": Valleys like these hold fine silt and the variant is benign [2] [3].`
- Why it matters: "From the paper X:" claims provenance for the whole sentence; the benign verdict comes from the variant record, not the paper. Small, but the lead-in is code-built text and code is asserting it.
- NOT FIXED

### J-17-06: the noun frame produces wording such as "the literature index entry record" and "the part of the cell record"
- Severity: minor (wording; owner decision 1 in the design covers the words)
- What: `_lead_in_noun` appends "record" to every `plain_noun` that is not a paper or a trial. Several existing nouns read badly in that frame, and noun choice depends on the case of `entity_type` (pre-existing `plain_noun` behaviour).
- Reproduction: `lead_in_for([("X", t)])` on branch src: "Literature entity" gives `From the literature index entry record "X": `; "Cellular component" gives `From the part of the cell record "X": `; "Biological process" gives `From the body process record "X": `; "OMIM" gives `From the genetics catalogue entry record "X": `; "pubmed" gives `From the paper`, "PubMed" gives `From the record`; "medgen" gives `From the condition record`, "MedGen" gives `From the record`. "Literature entity" is a live type on the GERD question (its PubTator record is named "Gastroesophageal Reflux"), so this frame is reachable today.
- Why it matters: the owner is asked to approve the lead-in's words from six live examples that are all "From the paper"; the other frames were never shown.
- NOT FIXED

### J-17-07: the replay's "expected" side calls the same helpers as the pass, so its 0 missing and 0 unexpected is weak evidence
- Severity: minor (evidence claim, not behaviour)
- What: build.md says the replay's expected walk is "a separate walk written in the script, not the pass itself, so the two agree by test and not by sharing code". `expected_fires` in raw/replay_option_e.py calls `gr.record_labels_by_page`, `gr.short_forms_by_page`, `gr.title_words_shared` and `gr.names_by_short_form`, the four helpers this change adds, and repeats the pass's cursor walk and condition list line for line. A defect inside any of the four helpers is invisible to it.
- Reproduction: read side by side, `expected_fires` against `name_switched_records`; the only independent parts are the cursor and the boolean composition. Judge's own cross-tree check (below, J-17-09) is what shows the rest of the output is unchanged against develop.
- Why it matters: the 20 and 45 counts agree with the design's probe, which used the same stems, so "expected 20, got 20" is not a second opinion.
- NOT FIXED

### J-17-08: the lead-in reaches the lead-sentence decision and the 1000-character token cap
- Severity: minor (unsure)
- What: two side effects outside the sentences the pass selects. (a) `_lead_candidates` offers position 1, which can carry a lead-in, so the classifier's input (`lead_sentence_state`) differs from develop's for the same draft, and the pick, which reorders the prose, can differ; if picked, the answer opens with `From the paper "...":` above the count line, where the sentence the lead-in was written against is no longer above it. Live, position 1 does lead: run gerd-res-4 in raw/live opens with "The hallmark symptoms ..." (position 1). (b) `sentence_token` cuts text at 1000 characters; a lead-in adds up to about 195 characters (160 title, "From the genetics catalogue entry record", quotes and colon), so a sentence of roughly 805 to 999 characters that rendered whole on develop now loses its end, including its printed marker. The bench's longest sentence is under 400, so (b) has not been observed.
- Reproduction: (a) `_lead_candidates` on the judge's three-sentence probe returns `[0, 1]`; lead-in sentences sit at position 1 in 10 of the 65 replay lead-ins (`sent1:` lines in raw/replay_option_e.txt). (b) arithmetic from `sentence_token`'s `[:1000]` and `LEAD_IN_MAX_TITLE_CHARS = 160`; not run.
- Why it matters: checklist item 1 asks that every other sentence render as on develop; (a) means placement of other sentences can differ, though their text does not.
- NOT FIXED

### J-17-09 (verified, not a defect): cross-tree replay shows nothing but the prefix changes, and `_names_its_record` is unchanged
- Severity: none; recorded as evidence for checklist items 1 and 2
- What: the judge's own script ran the 35 saved runs (201 draft and mode cases: live, all, none) once with develop's src and once with the branch's, each in its own process, and compared serialised output. `run_grounding_pass` output: 0 differences. After `drop_record_restatements`: 0 differences. Branch after `name_switched_records` against develop: claims, origins, `stripped_count`, `refused` identical in every case; every differing sentence is exactly `From the ... "<title>": ` plus develop's sentence; lead-ins live 20, all 45, none 0; none on a first sentence. `_names_its_record` called 39,888 times on every split sentence of every draft against every record's labels and short forms (with and without markers, with and without short forms, single and concatenated labels): identical results on both trees, 21,922 True, so both outcomes were exercised.
- Reproduction: `names equal: True 39888`; `first-pass diffs 0 before diffs 0 bad 0 leadins {'live': 20, 'all': 45, 'none': 0} on first sentence 0`. The builder's replay rerun on the branch reproduced raw/replay_option_e.txt byte for byte.

### J-17-10 (verified, not a defect of this change): five sequential GERD Researcher runs per tree, branch no slower than develop; develop itself breaks 20 s twice
- Severity: none for the change; unsure for develop (pre-existing, outside this card)
- What: sequential, alternating trees (br, dev, br, dev, ...), develop's settings (CLASSIFIER_PROVIDER=jev, guard and plan deepseek/deepseek-v4-flash, synth z-ai/glm-5.2, cap 0.25 USD), Researcher, `reads_placement=True`, runner in the session scratchpad, no Opus. The pass itself costs 0.41 ms mean, 1.05 ms worst over the 67 bench drafts (20 repetitions each).
- Reproduction (elapsed s, done event ms, outcome, cost USD, lead-ins):
  - develop: 37.12 (37111, ask, 0.0135, 0), 9.36 (9350, answer, 0.0115, 0), 10.62 (10613, answer, 0.0114, 0), 39.74 (39738, ask, 0.0129, 0), 8.35 (8325, answer, 0.0126, 0)
  - branch: 8.80 (8790, answer, 0.0121, 0), 8.81 (8805, answer, 0.0137, 0), 7.43 (7427, answer, 0.0140, 1), 7.59 (7588, answer, 0.0115, 1), 8.66 (8657, answer, 0.0119, 1)
  - total spend 0.1251 USD. Develop over 20 s: 2 of 5. Branch over 20 s: 0 of 5. dev-1 logged "sentence check: Jev made no verdict (unexpected_error)" and ended `ask`; dev-4 ended `ask` with no such line; br-1 logged the same Jev error and still finished in 8.8 s.
- Why it matters: the builder's four slow runs (44 to 47 s, all `ask`) match a develop behaviour, not this change. Five runs per side is a small sample; the honest reading is "no evidence the branch is slower", not "faster". Develop's 37 to 40 s `ask` runs break the owner's 20 s rule and deserve their own card.
- NOT FIXED (develop's slowness)

### J-17-11: addendum to J-17-10, the branch also produces a slow `ask` run
- Severity: unsure (same pre-existing behaviour as develop)
- What: an extra branch run made for J-17-12 (same question, Researcher, same settings, a spy on the pass) took 38.3 s, done event 38290 ms, outcome `ask`, cost 0.0147 USD. A second extra run (Mediterranean, Researcher) took 10.47 s. Counting every GERD Researcher run the judge made: develop 2 of 5 over 20 s, branch 1 of 6. The slow runs on both trees end `ask` and spend their time outside the pass (the pass measured at about 1 ms worst).
- Reproduction: raw run in the session scratchpad, `{'trust_outcome': 'ask', 'elapsed_ms': 38290, 'total_cost_usd': 0.0147}`.
- Why it matters: it keeps J-17-10 honest; the speed verdict is "no difference attributable to the change", with both trees breaking the 20 s rule on some `ask` runs.
- NOT FIXED

### J-17-12: a defined short form shared by every paper in the answer counts as naming one of them, so the switch ships bare (live)
- Severity: minor (unsure; condition 4 of the owner-approved design says a short form names its paper, so this is a gap in the design, not in the build)
- What: condition 4 suppresses the lead-in when the sentence writes a short form the cited record defines. On the GERD question four or five papers define "GERD", so "GERD" does not tell the reader which paper a sentence comes from any more than "disease" does.
- Reproduction: live branch run, GERD Researcher, spy on the pass. Shown in this order: "Symptoms potentially attributable to gastroesophageal reflux disease are among those most commonly reported ... [n]" (page pubmed 37516506, the adult review), then "Several factors contribute to GERD pathogenesis beyond abnormal transient relaxations of the lower esophageal sphincter [3]." (page pubmed 37034973, the children's review, reworded, 0 shared title stems, kept and not led in because of "GERD"). `named 0` for the run.
- Why it matters: the reader moves from an adult review to a children's review with nothing marking it, which is the card's failure shape on an acronym instead of a common word.
- NOT FIXED

### J-17-13 (verified, not a defect): titles, wording and word lists
- Severity: none; evidence for checklist items 3 and 4
- What and reproduction, judge probes on branch src, neutral records, one shared title word each:
  - inner straight quotes `The "valleys" hypothesis.` gives `From the paper "The 'valleys' hypothesis": ...`; curly quotes become single quotes the same way.
  - `[Valleys of the north].` gives `"Valleys of the north"`; `Effects of [18F]FDG in valleys.` gives `"Effects of 18F FDG in valleys"`; `Valleys [1] and [2]` gives `"Valleys 1 and 2"`, and the rendered sentence's markers stay `['2']` in every case.
  - trailing "?" kept (`"Do valleys matter?":`); inner "? " and ". " kept and, since prose is emitted per sentence through `sentence_token` (the regex splitter `_narrative_chunks` has no caller), they do not split the token.
  - over 160 characters: cut at a word with "…"; a 300-character unbroken word after "Valleys" gives `"Valleys…"`. A title ending "..." loses one dot (`"Valleys and more.."`), cosmetic.
  - braces in a title (`{0} {noun}`) pass through untouched; newlines and tabs collapse.
  - two papers: `From the papers "A" and "B": `; paper plus MedGen: `From the records "A" and "B": `; empty type: `From the record`.
  - in all 65 replay lead-ins and the 3 lead-ins of the judge's live branch runs, the quoted title is the children's review or another page the sentence cites (replay title check plus the spy's page list).
  - item 4: the source diff adds no word list and no test-question word; the only string comparisons are on `plain_noun`'s own outputs ("published paper", "clinical trial") to pick the frame's noun. The new unit tests use neutral records except the existing G6PD and FMF fixtures in test_sentence_check.py.

## Verdict

FIX FIRST.

Nothing in this change makes an answer worse than develop: the judge's cross-tree run shows only prefixes added, `_names_its_record` unchanged over 39,888 calls, all three gates green (ruff "All checks passed!", gate 2 exit 0, `2296 passed, 66 skipped, 1 deselected, 1 xfailed`), and no speed cost. Two major findings hold it back:

- J-17-02 sits inside this phase's fix: the pass decides "the sentence above" before card 111 and the lead pick change the order, so the card's own failure shape can still ship bare. Per the review loop's stop condition this goes to the product owner.
- J-17-03: the one line that wires the pass into the write step has no test; deleting it leaves every gate green.

Verified by the judge's own probes: checklist 1 (cross-tree replay, own edge cases), 2 (39,888-call equivalence over the saved traces, and the develop switch tests in the unchanged gate suite), 3 (title and wording probes, live spy), 5 (ten sequential live runs plus two spy runs, 0.157 USD in all), 6 (gates rerun, eleven single-property mutations). Read only, not probed: item 4 (source diff read for word lists), and J-17-08 (b), the 1000-character cut, which is arithmetic.

Correction to J-17-13, appended rather than edited: the three lead-ins in the judge's branch speed runs were not spied, so the judge did not check that their marker [14] opens the children's review; each names that review and sits on a sentence about young children or pathogenic factors, which matches it. The page check in J-17-13 rests on the 65 replay lead-ins only. Also confirmed: the branch removes no existing test line (the only removed line in tests/ is an import widened to a multi-line import).
