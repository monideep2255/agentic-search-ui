# Card 110 redesign: judge round 2 (J2-110)

Judge, bossman dial 2, one round, closes nothing. Subject: pull request #242, `git diff 7626fe85...06d7b73d`. Worktrees: `<scratchpad>/j110b` at 06d7b73d, `<scratchpad>/j110bdev` at 7626fe85.

## Findings

### J2-110-01: `_lead_label_map` is not a pure refactor; card 111's left-out set changes when two citations share a display number
- Severity: minor (unreachable in every saved run I could load)
- What: develop built the map from `{c.display_index: c for c in citations}` (the last citation per display number wins, then it is labelled or not). The factored `_lead_label_map` iterates `citations` directly, so an earlier labelled citation keeps its label even when a later, unlabelled citation carries the same display number. `_label_only_positions` therefore differs between the trees on such input.
- Reproduction: `<scratchpad>/j2probe/min111.py`, run with each tree's `src` on the path. Citations display 1 -> "a", display 2 -> "b", display 2 -> "c"; findings a and b `name` = "Marfan syndrome", c `abstract`; sentence "Marfan syndrome [1] and Marfan syndrome [2]." listed [1] [2]. This tree: `positions [0]`. Develop 7626fe85: `positions []`. A 40,000-case differential fuzz (`<scratchpad>/j2probe/diff111.py`): `_is_label_only_sentence` 0 differences; `_label_only_positions` 50 differences, every one with a repeated display number. Across 48 saved live `_answer_parts` pickles (out/ and c110/), 0 have a repeated display number and 0 have two findings per citation id.
- Why it matters: the build report and design say card 111's behaviour does not change. It does on this input shape. Nobody sees it today, because the shape never appeared, but the claim "factored out, unchanged" is not exactly true, and the same map now also feeds the tier B title filter.
- NOT FIXED

### J2-110-02: Tier A is develop's call byte for byte only when card 111 leaves nothing out of the first two; otherwise the call changes (the declared V-111-01 departure), measured
- Severity: unsure (declared in design.md and DECISIONS.md 2026-10-15; filed so checklist item 1's scope is explicit)
- What: offline, with a recording fake `_decide_point` (every spec field and the state text captured) over 83 saved groundings (the bench's 63 plus the 20 live runs in c110), every skip set of up to two of the first three cited positions, and every scripted answer of tier A (first, second, neither, no record), tier B (first, second, neither) and the check (stands_alone, needs_earlier): with skip empty, tier A's call is identical to develop's in 1,992 of 1,992 runs, and whenever tier A picks a sentence the result is develop's in 822 of 822. With a non-empty skip, tier A's call differs from develop's in 3,024 of 6,888 runs (develop offers sentences 1 and 3 when sentence 2 is left out; this tree offers sentence 1 alone, or nothing, and sends sentence 3 to tier B with the check).
- Reproduction: `<scratchpad>/j2probe/tierA.py` run in each tree, compared by `<scratchpad>/j2probe/tierA_cmp.py`. Output: `('skip_empty', 'A_call_same') 1992`, `('skip_empty', 'A picks, same call: result equal') 822`, `('skip', 'A_call_differs') 3024`. The only skip-empty result differences are tier A "neither" or no record (47 and 47), which are the later path by design.
- Why it matters: "Tier A is byte-for-byte develop's call whenever it picks" holds exactly for skip-empty answers and is false when a repeated title sits first or second. There, a third sentence that develop would open on unchecked now needs the stand-alone check, so the change can only remove an opening, never add an unchecked one. Rare: 0 of 48 saved runs carry a repeated display number shape, and design.md says no live run in 38 produced a repeated title near the top.
- NOT FIXED

### J2-110-03: The run's `done.decisions` record later-path picks and checks the answer never acted on, in finish order
- Severity: minor (trace and audit only; no frontend consumer found)
- What: `_decide_point` appends every finished record to the run's decisions. Tier B and the checks start beside tier A, so when they finish before tier A picks, their records stay in `done.decisions` although tier A's pick decided the opening and the later path was never read. They land in finish order, so the unread later pick can sit before the pick that was used.
- Reproduction: the builder's saved live runs, `<scratchpad>/c110/live_new.jsonl`, field `done_lead` (the `done` event's `write.lead*` records): qbr_1 `['write.lead_later_sentence:first', 'write.lead_sentence:first']`, opened on tier A's pick; qbr_2 `['write.lead_stands_alone:stands_alone', 'write.lead_stands_alone:needs_earlier', 'write.lead_sentence:first']`, opened on tier A's pick; qbr_4 `['write.lead_stands_alone:needs_earlier', 'write.lead_later_sentence:first', 'write.lead_sentence:first']`. Develop records one lead decision per run. Up to four now count against `_MAX_DONE_DECISIONS` (16), whose comment still says a run makes at most six.
- Why it matters: whoever reads a trace to learn why an answer opened where it did (the owner, a reviewer, the eval track) sees "later sentence: first" and "stands_alone" for runs where neither mattered, and has to know the timing rules to tell. Nothing a person typing a question sees.
- NOT FIXED

### J2-110-04: The later pick tells the classifier its sentences are "the first one or two sentences of the written answer" when they are the third and later
- Severity: unsure (wording of a classifier description; the design chose to reuse it)
- What: tier B is built with `instructions=LEAD_SENTENCE_INSTRUCTIONS`, which says "then the first one or two sentences of the written answer". Tier B's state carries cited sentences 3 and 4 (or later, once titles are filtered), labelled "Sentence 1" and "Sentence 2".
- Reproduction: `core/graph.py` `_lead_sentence_choice`, the `LEAD_LATER_POINT` spec; `harness/decide.py` `LEAD_SENTENCE_INSTRUCTIONS`. Read, not run.
- Why it matters: the decision's description misstates what it is judging. The bench's gain numbers were measured with this wording, so changing it would need the same re-measurement; filed so the choice is explicit rather than accidental.
- NOT FIXED

### J2-110-05: Tier A is the same call but not the same wait: the sibling Jev calls slow develop's own pick by about 14 ms on average and nudge it past the 1 s bound slightly more often
- Severity: minor (no person would notice the average; the tail is bounded by develop's own 1 s cap)
- What: the later pick and its checks start at the same instant as tier A. Measured paired and interleaved (develop's function exec'd into the same process, the two run back to back on the same grounding, order alternating, cold first pair dropped), tier A's own call is slower on this tree, and more so the more siblings start with it. Tier A timeouts at the bound, which give the count line where develop would have opened on a sentence, were 8 against 6 here and 7 against 3 in the builder's bench.
- Reproduction: `<scratchpad>/j2probe/paired.py 6 paired_full.jsonl` in the PR tree (83 groundings, 497 pairs after the cold pair, live Jev, develop's settings), analysed by `<scratchpad>/j2probe/paired_an.py`. Pasted:
  - tier A call, finished: develop median 217 ms, p90 326, p95 405, p99 610; this tree median 230, p90 361, p95 449, p99 659
  - paired tier A new minus develop: median +14 ms, mean +13.8 ms, bootstrap 95% CI of the mean +2.3 to +25.2 ms; new slower in 292 pairs, faster in 191
  - by siblings started: 1 call (tier A alone) mean +7.4 ms (n 300); 3 calls mean +20.4 (n 94); 4 calls mean +28.3 (n 89)
  - whole lead decision: develop median 218, p95 426, p99 1002, max 1004, 6 at or over 1,000 ms; this tree median 239, p95 538, p99 1003, max 1033, 10 at or over 1,000 ms
  - when tier A picked (the answer opens on develop's own pick): develop median 220, p95 396; this tree median 230, p95 444; hold after tier A landed until return: median 0.3 ms, p99 6.5, max 11.4 (cancel and gather of the siblings cost nothing a person feels)
  - when tier A said "neither" and both trees showed the count line: this tree waited a median 34 ms longer, the five largest +313, +727, +732, +759, +786 ms
  - outcomes over 497 pairs: same opening 362; count line on both 96; later-path gain 33; develop opened and this tree showed the count line 6, of which 5 are this tree's tier A hitting the 1 s bound and 1 is tier A saying "neither" on adv dtrial_1 (Jev noise on the 0.04-confidence case)
  - pooled with the builder's bench, replays at or over 1,000 ms: this tree 17, develop 9, of 812 each; one-sided Fisher p = 0.083, not significant at 0.05 but the same direction twice
- Why it matters: the bar is nothing worse than develop. A person will not feel 14 to 28 ms. What they can meet, about one answer in 250 more than today if the direction is real, is a 1 s pause followed by the count line where develop would have opened on its pick, the very opening this card exists to protect. And the "same call returned at once" in design.md is true of the call, not of its latency. Starting tier B only after tier A says "neither" would remove the drag on develop's wins, at the price of the gain path's speed.
- NOT FIXED

### J2-110-06: A paper title in curly quotes passes the grounding pass, slips the title filter, and opens the answer in bold where develop shows the count line (inside this phase's new title filter)
- Severity: major (the card's own "never opens on a paper title"; unsure how often the writer quotes a title: 0 of 237 distinct saved grounded sentences carry a quote mark)
- What: `_repeats_one_label` strips only " .,;:?!" and casefolds before comparing a piece with the cited record's label. The grounding pass keeps a title wrapped in curly quotes, so the third cited sentence “Preneoplastic stromal cells promote BRCA1-mediated breast tumorigenesis” [14]. reaches tier B as an ordinary sentence. Tier B picks it as answering "Which diseases are associated with BRCA1?" and the stand-alone check says `stands_alone` (a title names everything it talks about, M3 in design.md), so it leads. Straight quotes and parentheses are stripped by the grounding pass, so those two forms do not reach the screen; doubled inner spaces and a non-breaking hyphen also slip the filter (offline, not run live).
- Reproduction:
  - Grounding, real pass: `run_grounding_pass('“Preneoplastic stromal cells promote BRCA1-mediated breast tumorigenesis” [N].', <dbrca_1 synth_findings>, core_ask_required=False, question=...)` kept `('“Preneoplastic stromal cells promote BRCA1-mediated breast tumorigenesis” [1].',)`, stripped 0. The straight-quoted and bracketed forms: kept (), stripped 1.
  - Filter: `_repeats_one_label` with dbrca_1's label map: plain title True; curly-quoted False.
  - Live, PR tree, `<scratchpad>/j2probe/titles_live_curly.py` (case A110_02's first two sentences, then the curly-quoted title as S3, dbrca_1's label map, develop's settings): opened on S3 “Preneoplastic stromal cells promote ...” in runs 2, 3 and 4 of 5, each with `lead_later_sentence: first` and `lead_stands_alone: stands_alone`; runs 0 and 1 the count line. Tier A said "neither" in 5 of 5, and tier A is develop's exact call, so develop shows the count line on all five. The control (plain title, `<scratchpad>/j2probe/titles_live.txt`): count line 5 of 5.
- Why it matters: the person asked which diseases go with BRCA1 and the answer opens, in bold, on the title of one paper. The card says that never happens, and on this input develop never did it. This is the defect class card 110's first attempt failed on (V-110-03), reached through a gap between the filter's normalisation and the grounding pass's.
- Inside a fix made during this phase: yes, the title filter is new in this pull request.
- NOT FIXED

### J2-110-07: A sentence made of two paper titles joined by "and" opens the answer 4 of 5 where develop shows the count line (by the filter's design, against the card's words)
- Severity: major (the card says the answer "never opens on a paper title"; unsure how often the writer joins titles: not seen in the saved runs)
- What: `_repeats_one_label` deliberately does not match a list of different labels, because a list of disease or gene names can answer "which". It cannot tell that the labels are paper titles (the `title` field) rather than names, although `_lead_label_map` has the field in hand when it builds the map. So "Title A [14] and Title B [10]." is a tier B candidate; tier B picks it and the stand-alone check passes it.
- Reproduction:
  - Grounding, real pass, dbrca_1's findings: "Preneoplastic stromal cells promote BRCA1-mediated breast tumorigenesis [a] and Germline BRCA1 and BRCA2 Mutations in Jewish Women Affected by Breast Cancer [b]." kept whole, stripped 0.
  - Live, PR tree, `<scratchpad>/j2probe/titles_live_two.py` (case A110_02's first two sentences, then that sentence as S3 with display markers [14] and [10], dbrca_1's label map, "Which diseases are associated with BRCA1?"): opened on S3 in runs 0, 1, 2 and 4 of 5, each `lead_later_sentence: first`, `lead_stands_alone: stands_alone`; run 3 the count line (tier A late). Tier A, develop's exact call, said "neither" in every run where it finished, so develop shows the count line.
- Why it matters: a person asking which diseases go with BRCA1 gets an answer whose bold first line is two paper titles. Develop never opened there. The design's reason for not matching lists (names answer "which") does not cover titles, and the field that would tell them apart is already read.
- Inside a fix made during this phase: yes, the title filter and the later path are new in this pull request.
- NOT FIXED

### J2-110-08: When a later sentence leads and a sentence follows it, the follower is left in the prose after a sentence it does not continue
- Severity: unsure (read, not run; every gain in the bench had the opened sentence last, so no saved run shows it)
- What: `_answer_parts` prints the lead first and then skips its position in the prose. Develop could only lift sentence 1 or 2. The later path lifts sentence 3 or 4 (or later, after titles), so a following sentence that continues it ("These mostly affect the eyes, heart and skeleton [n].") now follows sentence 2. The stand-alone check judges the lifted sentence, never the one left behind.
- Reproduction: code path only, `core/graph.py` `_answer_parts`, the `position == lead_index` skip. The five bench gains (adv b66_4, adv d66_5, case V_good3, fix f66_2, ver d66_1) all have the features or diseases sentence as the last sentence, so none exercises it.
- Why it matters: the opening gets better and the paragraph under it can read as a non sequitur. Filed for the fixer to judge against the card's "never ... a sentence that needs the one before it", which this does not literally break.
- NOT FIXED

## Checklist, with evidence

| Item | Result | How established |
|---|---|---|
| 1 Tier A is develop's call and result whenever it picks | Holds when card 111 leaves nothing out of the first two: 1,992 of 1,992 identical calls, 822 of 822 identical results; live, 362 of 497 pairs opened on the same sentence and 0 opened on a different one. Differs by design otherwise (J2-110-02). | Own probes: `tierA.py` and `tierA_cmp.py` (offline, recording fake seam, both trees); `paired.py` (live, interleaved) |
| 2 The later path | Only after tier A "neither" or no usable pick (offline matrix, both trees); 29 of 29 later openings had their own sentence's check say `stands_alone`, 0 mismatched; 0 openings on the listed pointer and title cases (A110_01, 02, 04a, 04b, bbrca_2, dbrca_1, dbrca_4, fbrca_4: same as develop, 6 of 6 each). Slice then filter verified in the offline skip matrix. But a curly-quoted title (J2-110-06) and a two-title sentence (J2-110-07) open the answer where develop does not. | Own probes, live and offline |
| 3 Card 111 unchanged | `_is_label_only_sentence`: 60,000 label-heavy fuzz cases (4,815 true) and 40,000 random cases, identical on both trees. `_label_only_positions`: differs only when two citations share a display number (J2-110-01), a shape absent from 48 saved runs. Card 111's tests pass on this tree. | Own differential fuzz, both trees |
| 4 Latency | Develop's pick slowed about 14 ms on average by its siblings (CI +2 to +25 ms), about 28 ms with four calls; hold after tier A lands under 12 ms; worst case 1,033 ms against develop's 1,004 ms; up to 0.79 s longer before the same count line when tier A says "neither"; timeouts 10 against 6 (pooled with the builder 17 against 9 of 812, p = 0.083). No case a person would notice on average; the tail is J2-110-05. | Own paired, interleaved live bench, 497 pairs |
| 5 No hardcoded decisions; 1,000-character limit | Instructions 319 characters, criteria 215 and 181, tier B's reuse of develop's texts 311, 327, 171, 179: all under `_DESCRIPTION_MAX_CHARS` 1,000. Stand-alone state at most 2,010 characters, under the 4,000 state cap. Scan of the new texts for Marfan, BRCA1, disease, gene, MedGen, These, One is, Another, They, feature, symptom, phenotype, syndrome, include, title, paper, study: none; "what" and "it" appear only as generic English. The title filter reads label fields, no word list. | Own scan and measurement |
| 6 Break it | Mutation: never cancel the sibling tasks in `finally` (the property the builder did not run red). Red: `test_a_first_or_second_pick_returns_at_once_and_never_waits_for_the_later_path` and `test_the_pick_and_the_check_share_one_bound`, 2 failed, 58 passed. Restored by `git checkout`: 60 passed. | Own mutation in a separate worktree |
| Gates | `ruff check` (no path): All checks passed. isort gate 2 command with the CI virtual environment's isort: exit 0 on both trees, identical output (the `EventResolvedEntity` failure did not reproduce with this isort on either tree). pytest harness, core, synthesis, not integration: this tree 2,870 passed, 66 skipped, 1 deselected, 1 xfailed; develop 2,857 passed, 66 skipped, 1 deselected, 1 xfailed. | Run on both trees |

Verified by my own probes: items 1 to 6 and the gates as above, J2-110-01, 02, 03 (from the builder's saved live rows, read), 05, 06, 07. Read only: J2-110-04, J2-110-08, and the claim that the grounding pass accepts what it accepted in the probes for other findings' shapes. Live spend: about 1,500 Jev calls (1,458 in the paired bench, 0 guard fallbacks, plus 40 in the title probes), roughly $0.03 at the design's per-call figure.

## Verdict

FIX FIRST.

The redesign keeps develop's pick exactly when it picks, closes every case the first attempt failed on, and costs a person no wait they would notice on average. But on two input shapes the answer now opens, in bold, on paper titles where develop shows the count line (J2-110-06, a curly-quoted title the grounding pass keeps; J2-110-07, two titles joined by "and"). Both are inside this pull request's new title filter, so this round's stop condition fires: the finding sits inside a fix made during this phase. Neither shape appears in the saved runs, which is why the bench was green.

Correction to J2-110-02, "Why it matters": the rarity figure should read: in 48 saved live runs (out/ and c110/), card 111 leaves out no sentence at all (0 of 48), so 0 of 48 hit the changed tier A call; and 0 of 48 carry a cited sentence that is a bare record title.
