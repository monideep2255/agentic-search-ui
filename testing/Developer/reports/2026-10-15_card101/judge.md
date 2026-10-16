# Judge round, Card 101 last slices (pull request #248)

Judge, dial position 2, one round. Change reviewed: `git diff 7626fe85...81550539`. Findings are appended as they are established.

## Findings

### J2-101-01: a curly apostrophe (category Pf) closes an open curly quotation, so a claim inside “...” that contains "X’s" before the break shows with no check, as on develop
- Severity: major. Inside slice 2, a fix made in this phase: slice 2 exists so that "a sentence a paper only quotes is never printed as the paper's finding without the check".
- What: `_mark_spans` treats every Pf character as a closer of the nearest open quote. U+2019 is both the curly closing single quote and the ordinary curly apostrophe ("X’s", "patient’s", "Crohn’s"), so the first apostrophe inside a quotation closes it, and the breaks after it are graded `hard`.
- Reproduction (offline `run_grounding_pass`, no model): value `Advertisers claimed “Drug X’s maker tested it. Drug X cures cancer. It is cheap.” Mortality was unchanged in the trial.`, narrative `Drug X cures cancer [1].` New tree units: `('Drug X cures cancer.', 'hard')`; items `[]`; shown with no approvals `['Drug X cures cancer [1].']`. Same value with `Drug X’s` replaced by `Drug X`: unit graded `mark`, one item sent carrying "Advertisers claimed “Drug X maker tested it. Drug X cures cancer. ...", shown with no approvals `[]`. Develop shows it in both.
- Why it matters: curly apostrophes are the normal typography in publisher-supplied abstracts; the slice-2 protection is off whenever the quoted passage has a possessive before its first full stop. Not worse than develop, but the slice's claim does not hold. No test covers a curly apostrophe (the apostrophe row uses straight `'`).
- NOT FIXED

### J2-101-02: one stray opener plus a later apostrophe turns every later whole copy into a cut, the A-101N-13 cost back through another door
- Severity: major. Inside slice 2 (a fix made in this phase). The design promised "A stray bracket or quote mark earlier in the abstract changes nothing".
- What: (a) a curly “ closed by a straight `"` (mixed typography) stays open, and a later curly apostrophe "patient’s" pairs with it; (b) a leading straight apostrophe ("the '90s") opens by shape and a plural possessive ("patients' ") closes by shape. Either pairing spans the abstract, so every break in between is `mark` and every whole copy develop showed with no check is now a cut sent to the check.
- Reproduction: (a) value `The sponsor called it “safe and effective," in a statement. Mortality was unchanged in the treated group. Infants improved by two days. Resistance was rare in the cohort. The patient’s doses were lower.`, narrative `Mortality was unchanged in the treated group [1]. Resistance was rare in the cohort [1].` New tree: the four later units graded `mark`; two items sent, each with a 202-character run; shown with no approvals `[]`. Develop: no items, shown `['Mortality was unchanged in the treated group [1].', 'Resistance was rare in the cohort [1].']`. (b) value `In the '90s rates rose. Mortality was unchanged in the treated group. Resistance was rare in the cohort. The patients' doses were lower.`, same narrative: new tree three units `mark`, two items of 136 characters, shown with no approvals `[]`; develop shows both with no items.
- Why it matters: true faithful sentences develop showed now cost a check item each and are lost whenever the check rejects, times out or cannot run; with a long abstract the glued run can pass 600 and the sentence is held outright. The fuzz cannot see this: it never measures what develop shows that the new tree drops (see J2-101-04), and its mark list has no apostrophes.
- NOT FIXED

### J2-101-03: slice 4 turns a faithful whole copy into a cut whenever the reply sentence before it is an unmarked faithful copy of the record sentence before it
- Severity: major (unsure whether the owner accepts it as cost). Inside slice 4, a fix made in this phase.
- What: `_joined_to_cut_head` tests only that head and copy are contiguous in the record. It does not ask whether the record breaks hard between them, so two ordinary consecutive record sentences, the first left unmarked by the writer, read as "the writer's splitter cut one sentence". The design's two controls (framing head, marked head) do not cover an unmarked faithful head.
- Reproduction: value `Mortality was unchanged in the treated group. Resistance was rare in the cohort. Infants improved by two days.`, narrative `Mortality was unchanged in the treated group. Resistance was rare in the cohort [1].` Develop: items `[]`, shown with no approvals `['Resistance was rare in the cohort [1].']`. New tree: one item with an 80-character run, shown with no approvals `[]`, shown with all approved `['Resistance was rare in the cohort [1].']`.
- Why it matters: a sentence develop showed now depends on the check. Writers do leave a sentence unmarked before a marked one; the replay of 69 drafts shows 0 cases, but the fuzz is one sentence per narrative and never reaches this branch.
- NOT FIXED

### J2-101-04: the held path now fires on ordinary abstracts: a mark span past 600 characters (a long parenthesis, or the J2-101-02 apostrophe pairing) holds a reworded sentence develop sent to the check
- Severity: major. Inside slices 1 and 2 (fixes made in this phase). Checklist item 3.
- What: `record_sentence_run` glues across every `mark` break with no bound short of 600, then returns None, and the reworded path holds the sentence. The quote's own unit is 77 characters; develop sent it with that unit.
- Reproduction (first pass, no model): quote `azithromycin shortened the illness in infants with bronchiolitis by two days`, narrative `Azithromycin shortened the illness in infants with bronchiolitis by two days in the study [1: "<quote>"].` (a) value `Results (see the appendix. Azithromycin shortened ... by two days. ` + eight sentences `Arm a enrolled forty patients over two years of follow up in the region.` ... + `) were mixed. Mortality was unchanged.` (726 characters, nine `mark` breaks): develop items 1 (run 77 characters), new tree items `[]`. (b) value `In the '90s rates rose. Azithromycin shortened ... by two days. ` + the same eight + ` The patients' doses were lower.` (717 characters, every break `mark` through the '90s ... patients' pairing): develop items 1, new tree items `[]`.
- Why it matters: when that sentence is the answer's only claim, develop could show it after the check approves; the new tree can never show it, so the answer refuses or empties. The build reports the 600 hold "fired 0 times on every corpus and in the fuzz", but the fuzz's records are 2 to 9 short sentences and its marks never span 600 characters, so 0 is what a broken and a working tree both produce. Caveat, stated plainly: my approve-all second pass did not show the reworded sentence on either tree even on a short control record (a harness gap I did not resolve in time), so "emptied" is shown here by the item develop sends and the new tree does not, not by a final shown list.
- NOT FIXED

### J2-101-05: the two slow GERD runs are the two GERD runs that ended "ask"; the grounding pass itself costs milliseconds, so the seconds come from what the answer path does after it, not from network noise as stated
- Severity: unsure (major if the link holds). Checklist item 4.
- What: timed offline, the grounding pass cannot add seconds a person notices. The live rows show the slow runs are not random: both are the new tree's only GERD runs with outcome `ask`, and both sent 16 items, the most of any GERD run on either tree. Develop's five GERD runs all ended `answer` in 9.5 to 10.8 s.
- Reproduction, offline (my timing script over the 104 grounding narratives in the three trace folders, both passes, three repetitions, run twice): develop total 0.286 s and 0.307 s, worst draft 5.5 and 5.7 ms; new tree 0.330 s and 0.510 s, worst draft 11.2 and 16.8 ms. A 2,000-character value dense with curly quotes, apostrophes and brackets, 20 cited copies, first pass: develop 0.013 s, new 0.035 s. Live, from `raw/live_new.jsonl` and `raw/live_develop.jsonl`: new GERD runs (seconds, outcome, items sent) `53.6 ask 16`, `9.2 answer 13`, `8.1 answer 12`, `38.7 ask 16`, `10.3 answer 14`; develop `9.5 answer 13`, `9.6 answer 13`, `9.9 answer 13`, `10.8 answer 10`, `10.4 answer 11`.
- Why it matters: if more held or cut sentences push a Plain language answer under its floor and into the ask path, a person waits 40 to 54 s for a question instead of 10 s for an answer, against the 20 s rule. Two of five is too few to prove; the build attributes it to "tool calls" or the network without showing the ask outcome. Needs the lead to read those two traces before merge.
- NOT FIXED

### J2-101-06: the fuzz cannot see a lost sentence, and never reaches slices 4 or 5, so "0 develop sentences dropped" rests on the 69-draft replay alone
- Severity: minor (measurement, not product)
- What: `raw/fuzz.py` counts "new tree shows more", quote text lost and items held; it never counts sentences develop shows that the new tree does not. Each fuzz narrative is one sentence with no writer quote, so slice 4 (needs a previous unmarked sentence) and slice 5 (needs a writer quote) never run. Its mark list has no apostrophes and no record past about 600 characters. J2-101-02, 03 and 04 each lose or hold a sentence develop showed or sent, and the fuzz reports 0 for all of them.
- Reproduction: I reran the fuzz, seed 101: `unit count (and unit texts) equal to develop's on 4000 of 4000`, `new tree shows more than develop: 0`, `items both send 2138; items whose quotes lost text develop's carried: 0`, `items develop sends that the new tree holds: 0`; seed 7: 4000 of 4000, 0, 2111 and 0, 0. Those numbers match the build. My probes for J2-101-02 to 04 still lose or hold sentences.
- Why it matters: the build's bar table reads as proof that no develop sentence is lost. It covers the real traces (0 exposure) and a fuzz that cannot count a loss.
- NOT FIXED

## Checklist evidence

1. Replay and fuzz, rerun by me on both trees (develop 7626fe85, new 81550539), three folders as separate arguments:
   - `replay_r6.py`: "69 distinct recorded writer drafts"; develop and new both "items 5, not sent for length 0; shown none 9, all 12"; new vs develop, approves none and approves all: "shown that develop does not show 0; develop sentences dropped 0; drafts emptied 0".
   - `reworded_replay.py`: "137 cases (69 quoted drafts, 68 reworded units)"; both "items 174; shown none 9, all 95"; "items whose quote lost text develop's carried 0; held where develop read only the bare quote or over 600 0; held where develop's run was within 600 0"; dropped 0 in both modes.
   - `fuzz.py` seeds 101 and 7: as J2-101-06. The builder's numbers reproduce exactly. Exposure on these corpora is still 0 (the build says so), so they show no harm on real traces and are not evidence about apostrophes, long spans or slice 4 (J2-101-02 to 04, 06).
2. The 8 October findings, rerun on both trees with my own probe (offline first pass):
   - J-101N-01 / A-101N-07 (bare writer quote on the reworded path): avoided. No fallback remains; a stray `(` gives the 92-character denial unit on both trees; past 600 the sentence is held (J2-101-04 is the cost).
   - J-101N-04 / A-101N-08 (abbreviation chain): avoided. Twelve "arm A." to "arm L." sentences: new tree's run is "Children were assigned to treatment arm L. There was no evidence that ..." (135 characters), one arm unit only.
   - J-101N-02 / A-101N-06 / A-101N-13 (stray mark drops later whole copies): avoided for an unclosed mark; reopened through an apostrophe pairing (J2-101-02).
   - J-101N-05 / A-101N-01 to 03 (quote styles): avoided for curly double, single, guillemets and the inch mark (tests and the mutation below); German and Swedish kept as develop by design (rerun: item sent on both trees, the run carries "The company claimed"); curly apostrophe bypass (J2-101-01).
   - J-101N-06 (St. Jude): avoided. New tree sends "Jude developed the infection" with "No children treated at St. Jude developed the infection." (56 characters); develop showed the tail unchecked.
   - A-101N-15 (vs. tail-only copy): unchanged from develop, a named residual in the design.
   - A-101N-10 (partial quote): read in the diff and the build's test; not probed by me.
   - J-101N-03 / A-101N-14 (corpora cannot see the change): still true; the fuzz was added, J2-101-06 is its limit.
   - J-101N-07 / A-101N-12 (code-built listing): deferred by design, not in this change.
3. Held path versus an answer develop filled: J2-101-04. Develop sends an item the new tree does not; a sole such sentence leaves the answer empty. Not observed on the real traces (0).
4. Time: J2-101-05. The grounding pass costs milliseconds on both trees; it cannot add seconds a person notices by itself. The slow live runs coincide with an `ask` outcome.
5. Mutation, one property: `_straight_quote_role` replaced by parity (the mutation the build did not run). sha256 before `c4e935ea765adde5`; result `1 failed, 786 passed, 10 skipped, 1 xfailed` in the synthesis folder, the failing test `test_a_copy_inside_a_quotation_or_bracket_is_a_cut_read_with_its_frame[A-101N-01 inch mark before the quotation]` ("Left contains one more item: 'Drug X is safe in children [1].'"); restored with `git checkout`, sha256 after `c4e935ea765adde5`, worktree clean.
6. Gates on the new tree: `ruff check` "All checks passed!" exit 0; `isort --check-only --diff src tests services tracker alembic .claude .github` exit 0 ("Skipped 2 files"); `pytest tests/system_03_search_agent/synthesis tests/system_03_search_agent/core -m "not integration" -q`: "2316 passed, 66 skipped, 1 deselected, 1 xfailed, 2 warnings in 78.92s", exit 0.

No live calls made; spend $0.

## Verified by my own probes versus only read

- Probed: the replay, the reworded replay and the fuzz on both trees; J2-101-01 to 05; the 8 October reproductions listed above except A-101N-10; timing; the parity mutation; all three gates.
- Only read: slice 5 (A-101N-10), the live runs' outcomes and timings (read from the committed jsonl rows, not rerun), and whether the live sentence check would approve the items J2-101-02 and 03 now send.
- Not resolved: my approve-all second pass did not show a reworded sentence on either tree even on a short control, so J2-101-04 shows the item develop sends and the new tree does not, not a final emptied answer.

## Verdict

FIX FIRST.

The safety direction holds in every probe: the new tree never showed a sentence develop does not show, and the bare-quote fallback is gone. The bar's second half, no sentence develop shows is lost, does not hold. J2-101-02 (an apostrophe pairs with a stray opener and turns later whole copies into cuts), J2-101-03 (slice 4 cuts a faithful copy after an unmarked faithful head) and J2-101-04 (mark glue past 600 holds a reworded sentence develop sent) each lose or hold a sentence develop showed or sent. J2-101-01 lets a quoted claim through, as develop does. J2-101-05 needs the two slow GERD traces read before merge.

J2-101-01, 02 and 04 sit inside slice 2 (with slice 1) and J2-101-03 inside slice 4, all fixes made in this phase: the review loop's stop condition fires and this goes to the product owner.
