# Card 111 alone: fresh verifier

Branch `fix/card111-repeated-title`. Bases: branch worktree `<scratchpad>/v111` at a30bebadb85cc89b87eb3bb330072d1187740248; develop worktree `<scratchpad>/v111dev` at cffdb8fd2d96968a62518d5eded1ecbefed34a15. Findings are appended as they are established.

## Findings

### Check 1, first facts (holds so far)
- `git diff cffdb8fd a30bebad -- src/system_03_search_agent/harness/decide.py | wc -l`: `0`. `MAX_LEAD_CANDIDATES` is still `len(LEAD_SENTENCE_PICKS)` with `LEAD_SENTENCE_PICKS = ("first", "second")`. Grep over `src` for `stands_alone|LEAD_STANDALONE|_shared_room|lead_stands`: no match.
- The only lead-pick code change is the `skip` argument on `_lead_candidates` and `_lead_sentence_choice`; the decision itself (one `_decide_point`, `wait_for` of `min(1.0, budget - 0.5)`) is develop's text.

### V-111-01: When a left-out sentence sits first or second, the lead pick is offered the writer's third cited sentence, which develop never offers
- Severity: minor (unsure on how often; inside this phase's fix-round code, the `skip` filter on `_lead_candidates`)
- What: `_lead_candidates` filters `skip` BEFORE it takes the first `MAX_LEAD_CANDIDATES` (2). So the change is not only "a left-out sentence is never offered": when the echo is sentence 1 or 2, the window slides and the third cited sentence of the writer's prose is offered, and can lead. Develop only ever offers the first two cited sentences. A-110-01 and A-110-04 showed that a third sentence ("Changes in this gene ...", "One is ...") can lean on what came before it, which is why card 110 (more candidates) was reverted. Slicing first and filtering after (`[i for i in develop_two if i not in skip]`) would also satisfy "never zero where develop had a non-left-out candidate" without offering anything develop does not.
- Reproduction: my end-to-end probe (`<scratchpad>/vprobes/test_zz_v111_probe.py`, case c18, fake Jev answering "second" to the lead decision), writer prose "Marfan syndrome [1] and Marfan syndrome [2]. NCBIGene:672 is associated with Ehlers-Danlos syndrome [6]. NCBIGene:672 is associated with Loeys-Dietz syndrome [3]."
  - branch lead state: `Sentence 1: NCBIGene:672 is associated with Ehlers-Danlos syndrome. / Sentence 2: NCBIGene:672 is associated with Loeys-Dietz syndrome.`; summary opens `NCBIGene:672 is associated with Loeys-Dietz syndrome [3].` (the writer's third sentence)
  - develop lead state: `Sentence 1: Marfan syndrome and Marfan syndrome. / Sentence 2: NCBIGene:672 is associated with Ehlers-Danlos syndrome.`; summary opens `NCBIGene:672 is associated with Ehlers-Danlos syndrome [6].`
- Why a person would care: in this probe the third sentence is fine on its own, so the person loses nothing. But if the third sentence were "Changes in this gene cause it [n].", it could open the answer in bold on the branch and never on develop, which is the exact A-110-01 shape the owner had reverted. It needs the writer to put a repeated title among its first two cited sentences, and the card says the echo usually comes last, so the rate is likely low. No test pins either behaviour (slice-then-filter would pass all branch tests; not run, unsure).
- NOT FIXED

### Check 2: the rule, 26 end-to-end cases on both trees (holds, with V-111-01 above)

Probe `<scratchpad>/vprobes/test_zz_v111_probe.py`, copied unchanged into each worktree's `tests/system_03_search_agent/core/` and run there; `graph.__file__` confirmed as `<scratchpad>/v111/src/...` (has `_label_only_positions`: True) and `<scratchpad>/v111dev/src/...` (False). Six Disease rows through `write_node`: [1] [2] "Marfan syndrome", [3] [4] "Loeys-Dietz syndrome", [5] "BRCA1-BARD1 promotes RAD51-mediated homologous DNA pairing" (a title that states a finding), [6] "Ehlers-Danlos syndrome". B = "NCBIGene:672 is associated with Ehlers-Danlos syndrome [6].", B2 = the same with Loeys-Dietz [3], E12 = "Marfan syndrome [1] and Marfan syndrome [2].", E34 = the Loeys-Dietz echo, T5 = "BRCA1-BARD1 promotes RAD51-mediated homologous DNA pairing [5]." "Summary" is the claims before the listing heading, count line omitted unless it moved. Both runs: `26 passed`.

| Case | Writer prose | Depth, listing, Jev | Branch summary (model sentences) | Develop summary |
|---|---|---|---|---|
| c01 | B E12 | researcher, yes, off | B | B, E12 |
| c02 | E12 B | researcher, yes, off | B | E12, B |
| c03 | B "Marfan [1], Loeys-Dietz [3] and Ehlers-Danlos [6]." | researcher, yes, off | B, list kept | B, list kept |
| c04 | B T5 | researcher, yes, off | B (T5 gone) | B (T5 gone): removed before Write on both trees |
| c05 | B "Marfan [1] and Marfan [2]?" | researcher, yes, off | B | B, echo |
| c06 | B "... Marfan [2]!" | researcher, yes, off | B | B, echo |
| c07 | E12 alone | researcher, yes, off | E12 (last model sentence kept) | E12 |
| c08 | E12 E34 (all echoes) | researcher, yes, off | E12, E34 (keep-all guard) | E12, E34 |
| c09 | B E12 E34 | researcher, yes, off | B | B, E12, E34 |
| c10 | B E12 | researcher, NO listing, off | B, E12 kept | B, E12 |
| c11 | B E12 | plain_language, yes, off | B | B, E12 |
| c12 | B E12 | clinical_brief, yes, off | B | B, E12 |
| c13 | B "Marfan [1] and Marfan [2] are listed separately." | researcher, yes, off | B (grounding cut it to E12, then left out) | B, "Marfan syndrome [1] and Marfan syndrome [2]." |
| c14 | B "Marfan [1], Marfan [2] and Loeys-Dietz [3]." | researcher, yes, off | B, kept | B, kept |
| c15 | B "Marfan [1]; Marfan [2]." | researcher, yes, off | B | B (stripped on both) |
| c16 | B "[1] Marfan syndrome and [2] Marfan syndrome." | researcher, yes, off | B | B (stripped on both) |
| c17 | B "Marfan [1] and Loeys-Dietz [4]." | researcher, yes, off | B, kept | B, kept |
| c18 | E12 B B2 | researcher, yes, Jev "second" | LEAD B2, count, B | LEAD B, count, E12, B2 (V-111-01) |
| c19 | E12 alone | researcher, yes, Jev "first" | count line opens, then E12 (no candidate, not asked) | LEAD E12, count line |
| c20 | B E12 | researcher, yes, Jev "first" | LEAD B, count | LEAD B, count, E12 |
| c21 | E12 T5 | researcher, yes, off | E12 (T5 removed before Write, so E12 is the last model sentence and stays) | E12 |
| c22 | B "Marfan [1] and Marfan [2]" (no stop) | researcher, yes, off | B | B, echo |
| c23 | E12 B | plain_language, NO listing, off | E12, B kept | E12, B |
| c24 | E12 B | researcher, yes, Jev "first" | LEAD B, count | LEAD E12, count, B |
| c25 | E12 E34 B | researcher, yes, Jev "second" | count opens (only B offered, "second" not an option, fake answers "neither"), B | LEAD E34, count, E12, B |
| c26 | T5 alone | researcher, yes, off | nothing beyond count | nothing beyond count (same) |

Reading against the brief:
- Never drops a cited list of distinct names: c03, c14, c17 kept on both.
- A single title (even stating a finding): T5 never reaches `_answer_parts` in this fixture on EITHER tree (c04, c21, c26 identical), so end to end it shows only "no worse than develop". At unit level `test_a_single_title_that_states_a_finding_is_kept` and my u-cases below cover it.
- A sentence citing a record the listing does not show: c10, c23 kept (no listing). Partial listing is unit-level below.
- The summary's last remaining model sentence: c07, c08, c19, c21 kept.
- Drops "X [a] and X [b]." when both listed: c01, c02, c09, c11, c12, c22; "?" c05 and "!" c06.
- Lead: c19 and c25, where the only cited sentences are left out, open on the count line, which is develop's fail-closed opening; develop with the same fake Jev opened on the echo in bold. Better than develop, not identical to it.
- Zero candidates: `_lead_candidates` filters then slices, so any develop candidate that is not left out is still among the branch's first two (c18, c24 show the non-left-out sentence is offered). Holds by construction; see V-111-01 for the cost of that construction.

### V-111-02: A paper title that states a finding is left out when the writer cites it to two records with the same title
- Severity: unsure (likely minor or not a defect: this is the card's own shape, and develop already removes the same title said once)
- What: the rule keys on "one label, two or more different listed records", not on whether the label is a name or a sentence-like title. When two listed records share a finding-stating title (a preprint and its journal version, a duplicate record), "T [5] and T [6]." is left out on the branch and printed on develop.
- Reproduction: `<scratchpad>/vprobes/test_zz_v111_probe2.py`, rows [5] and [6] both titled "BRCA1-BARD1 promotes RAD51-mediated homologous DNA pairing", writer prose B + "BRCA1-BARD1 promotes RAD51-mediated homologous DNA pairing [5] and BRCA1-BARD1 promotes RAD51-mediated homologous DNA pairing [6]."
  - branch t01 (researcher) and t03 (plain language): summary `NCBIGene:672 is associated with Ehlers-Danlos syndrome [7].` only
  - develop t01 and t03: `NCBIGene:672 is associated with Ehlers-Danlos syndrome [7]. | BRCA1-BARD1 promotes RAD51-mediated homologous DNA pairing [5] and BRCA1-BARD1 promotes RA...`
  - the same title said ONCE (t02) is gone on BOTH trees, removed before Write by develop's own restatement drop, so the branch is consistent with develop's treatment of a lone title.
- Why a person would care: the finding still shows in the listing as both records' titles, so the person can read it there; the summary loses a sentence that said the title twice. I file it only because the brief says a single title "even one stating a finding" is never dropped, and here one is.
- NOT FIXED

### Check 2, unit cases of my own on `_label_only_positions` (branch; develop has no rule, so all are kept there)

Probe `<scratchpad>/vprobes/unit_probe.py`. Labels: [1] [2] name "Marfan syndrome", [3] name "Loeys-Dietz syndrome", [4] [5] title "What Is Marfan Syndrome?", [6] description "Marfan syndrome", [7] [8] title "BRCA1-BARD1 promotes ...", [9] no citation, [10] name "  ", [11] symbol "FBN1".

| Case | Sentence | Listing markers | Branch |
|---|---|---|---|
| u01 | Marfan syndrome [1] and Marfan syndrome [2]. | all | DROPPED |
| u02 | same | [1] | kept |
| u03 | same | none | kept |
| u04 | Marfan syndrome [1] and [2]. | all | kept |
| u05 | ... [1] and ... [2] and Loeys-Dietz syndrome [3]. | all | kept |
| u06 | Marfan syndrome [1] and Marfan syndrome [6] (description field) | all | kept |
| u07 | ... [1] or ... [2]. | all | DROPPED |
| u08 | Marfan syndrome [1] and not Marfan syndrome [2]. | all | kept |
| u09 | BRCA1-BARD1 promotes ... [7]. | all | kept |
| u10 | BRCA1-BARD1 ... [7] and BRCA1-BARD1 ... [8]. | all | DROPPED (V-111-02) |
| u11 | What Is Marfan Syndrome? [4] and What Is Marfan Syndrome? [5] | all | DROPPED |
| u12 | What Is Marfan Syndrome [4] and What Is Marfan Syndrome [5]? | all | DROPPED |
| u13 | marfan SYNDROME [1] and Marfan syndrome [2]. | all | DROPPED |
| u14 | Marfan syndrome [1] and Marfan syndrome [1]. | all | kept |
| u15 | ... [1] and ... [9] (marker with no citation) | all | kept |
| u16 | ... [1] and ... [10] (blank label) | all | kept |
| u17 | Marfan syndrome [1], and Marfan syndrome [2]. | all | DROPPED |
| u18 | ... [1] and also Marfan syndrome [2]. | all | kept |
| u19 | [1] and Marfan syndrome [2]. | all | kept |
| u20 | FBN1 [11] and Marfan syndrome [1]. | all | kept |
| u21 | ... [1] and ... [2] differ. | all | kept |
| u22 | E12 with a trailing space | all | DROPPED |
| u23 | E12 | one listing line "Found 2 records [1][2]." | DROPPED (note only: "shown" is any marker on any listing line; real listing lines are one row per record) |
| u24 | Marfan syndrome [1][2]. | all | DROPPED (grounding strips this form before Write on both trees, prior verifier c11) |

### Check 3: the features directive (holds)
- The only `findings.py` change is inside `build_clinical_features_directive`'s returned string: one sentence added, "Write every feature in that one sentence as a single list: commas between the names, and the word "and" only before the last name, never between two names in the middle of the list." No word of any question, no feature name, no condition name.
- Run on both trees (`<scratchpad>/vprobes/prompt_probe.py`, `build_synth_messages` with a Marfan name finding and three feature findings): system block sha `0dcd6b744b74400a` on both (stable prefix byte-identical); user content with `clinical_features_asked=False` sha `c4bf9fe23c6bf955` on both (a question that did not ask about features gets develop's prompt exactly); with `clinical_features_asked=True` `86e47a17b619168a` (branch) against `6b9c50b92ee95709` (develop), the directive text above being the only difference. The directive is placed in `user_content` after FINDINGS, the dynamic suffix.

### V-111-03: The features-directive change has no develop baseline, so whether it fixes "and" in the middle of the list is unmeasured
- Severity: unsure (no evidence it is worse; filed because the claim rests on runs that a do-nothing change would also pass)
- What: the history build report's five live Marfan runs on 3cef7ae6 show the features sentence as one list with "and" only before the last name, 5 of 5. No develop runs of the same question are reported, and the build report for this branch adds no live run. A directive that changed nothing would produce the same 5 of 5 if develop's writer already did this most of the time. The new words also repeat "every feature in that one sentence": the directive itself says a word not in a finding deletes "the whole sentence with it", so one list carries all features on one sentence's fate. That was already develop's instruction ("in one sentence of this shape"), so this is a reinforcement, not a new risk; in the five runs every feature grounded.
- Reproduction: `git show 3cef7ae6:testing/Developer/reports/2026-10-15_cards110_111/build.md`, "Live runs": "The features sentence in every run read as one list with "and" only before the last name"; no develop arm in that table. I made no live call.
- Why a person would care: the second half of the card's promise ("reads as one list with 'and' only before the last name") is asserted by a unit test that checks the directive's words, and by five runs with no baseline. It does not make anything worse for the person that I could find.
- NOT FIXED

### Check 4 (break it): red, holds
- Mutation of my own: `_ECHO_END_PUNCTUATION` from `" .,;:?!"` to `" .,;:"` (the A-111-04 property: "?" and "!" handled).
- Output: `FAILED ...test_label_only_is_decided_from_structure[marfan syndrome [1] and Marfan syndrome [2]!-listed2-True]`, `FAILED ...[What Is Marfan Syndrome [4] and What Is Marfan Syndrome [5]?-listed4-True]`, `2 failed, 23 passed in 2.64s`. Restored with `git checkout -- src` in `<scratchpad>/v111`; `git status --short` shows only my two probe files.

### V-111-01 addendum: no test pins the window, slice-then-filter stays green
- Mutation: `_lead_candidates` takes develop's first two cited sentences, then removes the left-out ones (never offers anything develop did not).
- Output: `pytest test_summary_label_only_sentence.py test_write_answers_sooner.py harness/test_decide.py -m "not integration"`: `146 passed in 15.47s`. My probe under the mutation: c18 lead state `Sentence 1: NCBIGene:672 is associated with Ehlers-Danlos syndrome.` only, summary opens on the count line, then B, then B2 (no third sentence offered); c24 still leads B; c25 opens on the count line with no question asked. Restored, `git status --short` clean apart from my probe files.
- So both designs pass every test; the shipped one is the one that offers a third sentence. Still NOT FIXED, still minor and unsure.

### V-111-04: "Two different records" is counted on marker text, not marker number
- Severity: minor (unsure it can happen: grounding writes canonical markers, and I did not find a path that writes "[01]")
- What: `_is_label_only_sentence` tests `len(set(numbers)) < 2` on the marker strings, so "[01]" and "[1]" count as two records although `int()` makes them the same one.
- Reproduction: branch, `_is_label_only_sentence('x [01] and x [1].', {1: 'x', 2: 'Marfan syndrome'}, frozenset({1, 2}))` printed `True`; `'Marfan syndrome [1] and Marfan syndrome [1].'` (u14) is kept.
- Why a person would care: hardly at all; such a sentence would be a repeat of one record and saying nothing. Filed so the docstring's "two or more different records" is known to be text-level.
- NOT FIXED

### Check 5: gates in `<scratchpad>/v111` (holds)
- `ruff check` (no path), branch: `All checks passed!` (run after my probe files were moved out of the worktree).
- `isort --check-only` on the five touched files, branch: `ERROR: <scratchpad>/v111/src/system_03_search_agent/core/graph.py Imports are incorrectly sorted and/or formatted.` and nothing else. Develop, same check: `ERROR: <scratchpad>/v111dev/src/system_03_search_agent/core/graph.py Imports are incorrectly sorted and/or formatted.` The `isort --diff` hunks of the two `graph.py` files compared with `diff`: identical (`isort diffs identical`), the `contracts.events` `ResolvedEntity as EventResolvedEntity` reorder only.
- `pytest tests/system_03_search_agent/harness tests/system_03_search_agent/core tests/system_03_search_agent/synthesis -m "not integration" -q`, branch: `2 failed, 2846 passed, 66 skipped, 1 deselected, 1 xfailed, 2 warnings in 100.45s`. The two: `test_opus_writer.py::test_the_rollback_writer_glm_5_2_is_still_priced_by_the_installed_map` and `::test_the_old_writer_is_never_priced_below_the_static_estimate`. The same file on develop: the same two `FAILED`, `2 failed, 30 passed`.

## Verified by my own probes, and only read

| Claim | How |
|---|---|
| `harness/decide.py` identical to cffdb8fd | own probe: `git diff` line count 0 |
| Lead pick reads two candidates, one decision | read the code; own probe shows at most two sentences in every lead state (c18, c20, c24) |
| Left-out sentence never offered; zero-candidate safety | own probe c18, c19, c24, c25 on both trees; plus mutation (slice-then-filter) |
| Only cited sentences left out: opens like develop | own probe c19, c25: count line opens (develop's fail-closed opening); develop with the same fake Jev led on the echo |
| The rule's keep and drop cases | own probes: 26 + 4 end-to-end cases on both trees, 24 unit cases |
| Directive change: list shape only, dynamic suffix | own probe: prompt hashes on both trees; read the added sentence |
| Directive change fixes "and" mid-list live | only read (prior build report, no develop arm): V-111-03 |
| Mutation goes red | own mutation, own output |
| Gates | own runs |

## Learnings

- Nothing cost over five minutes. Small: the project's delete-blocking hook stops file deletion in the shell, so probe output went to fresh file names and probe files were moved out with `mv` before the ruff and pytest gates; and zsh does not split an unquoted variable of paths (isort read it as one settings path).

## Verdict

PASS: nothing on this branch is worse than develop for a person asking a question that I could find. Open findings: V-111-01 (minor, unsure; inside this phase's fix-round `skip` filter: the lead can be offered the writer's third cited sentence when an echo sits first or second, which develop never offers; no test pins it), V-111-02, V-111-03, V-111-04 (unsure or minor). None is a regression a person was shown to see.
