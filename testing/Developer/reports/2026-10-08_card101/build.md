# Card 101 last slices: build

Builder, 2026-10-08 overnight, branch `fix/card101-last-slices` in its own worktree. Base `c916cfa30f59802dfd85c81ef7ba39bdcfc2b263` (develop at #211). The card in the user's words: "A sentence the writer reworded never reaches the screen without passing the sentence check." It builds the three slices `testing/Developer/reports/2026-10-08_overnight/card101_diagnosis.md` (in the overnight documents folder) left open: J5-101-01, A4-101-01 and A4-101-02. No model call, no spend.

## Table of contents

- [Verdict](#verdict)
- [The change in the reader's words](#the-change-in-the-readers-words)
- [Commits](#commits)
- [What changed](#what-changed)
- [Tests, red then green](#tests-red-then-green)
- [Mutations](#mutations)
- [Faithful sentences dropped](#faithful-sentences-dropped)
- [Gates](#gates)
- [Deviations and choices for the lead](#deviations-and-choices-for-the-lead)
- [Learnings](#learnings)

## Verdict

| Slice | Finding | Status |
|---|---|---|
| 1 | J5-101-01: a writer quoting its own copied words beside a record whose sentences run past 600 characters had the check read the cut as its own source | Fixed: the clause is held, never sent |
| 2 | A4-101-01: "S. Typhimurium", "U.S. FDA" split one record sentence in two, and the tail showed with no check | Fixed: the tail is a cut and the check reads the whole sentence |
| 3 | A4-101-02: a sentence inside a quotation or bracket counted as whole and showed with no check | Fixed: a copy of it is a cut and the check reads the whole quoted unit |
| Replay | 168 recorded drafts, check approving nothing and everything | 0 sentences develop shows are dropped; 0 shown that develop does not show |

Every slice fails closed: each only turns a sentence that showed unchecked into one the check reads, or one that is held. None can add text.

## The change in the reader's words

- A paper saying "No isolates of S. Typhimurium carried the gene" can no longer appear as "Typhimurium carried the gene", cited to that paper, without the check reading the paper's whole sentence, "No" included.
- A paper that quotes a claim to reject it ('Advertisers claimed that "... Drug X cures cancer ..."') or brackets a retracted one ("(since retracted. Ribavirin cured every infant. ...)") can no longer have that claim shown as its finding without the check reading the whole quotation or bracket.
- A sentence copied from a long abstract, where the writer also quoted its own copied words, is left out when the check cannot read the whole of the paper's sentence around it.

## Commits

| Slice | Commit | Subject |
|---|---|---|
| 1 | fdc30a5d | fix(grounding): Hold a quoted copied cut whose record sentences the check cannot read |
| 2 | 1c05a2b4 | fix(grounding): Do not end a record sentence after an abbreviation-shaped token |
| 3 | 07169e94 | fix(grounding): Check a sentence inside a quotation or bracket as the whole unit |

## What changed

All in `src/system_03_search_agent/synthesis/grounding.py`, tests in `tests/system_03_search_agent/synthesis/test_copied_cuts.py`.

| Slice | Change |
|---|---|
| 1 | `_copied_clause_candidate`, quoted branch: uses `record_sentence_run(quote, ...)` and returns None when it is None, as the unquoted branch already did. The caller already holds a clause whose candidate is None, and since round 5 the whole sentence with it. |
| 2 | New `_ABBREVIATION_SHAPE` (one capital letter, or letters with an inner full stop, then a full stop) and `_ends_on_abbreviation`. New `_record_sentence_breaks`, the one boundary `record_sentence_run` (the widener) and `_record_sentences` (the whole-sentence test) now share: `_RECORD_SENTENCE_BOUNDARY` less any break after such a token. A shape, not a list. |
| 3 | New `_open_marks` and `_still_open`: round and square brackets and curly double quotes by depth (a closing mark with no opening one opens nothing), straight double quotes by parity, single quotes not counted (an apostrophe looks the same). `_record_sentence_breaks` skips any break while a mark opened before it is still open, counted in one pass over the value. The round 4 comment block above `_record_sentences` is updated for both slices (slice 3's commit also corrects slice 2's wording there on which abbreviations still break). |

## Tests, red then green

Each test was written first and run on the code before its slice.

| Slice | Test | Red before | Green after |
|---|---|---|---|
| 1 | `test_a_quoted_cut_the_widener_cannot_place_is_held_not_sent_as_its_own_quote`, the judge's two reproductions (the 740-character "There was no evidence that ..." run and the 606-character single sentence) | 2 of 2: "2 failed, 71 deselected" | Yes |
| 2 | `test_a_copy_after_an_abbreviation_and_a_capital_goes_to_the_check` ("S. Typhimurium", "U.S. FDA") | 2 of 2 | Yes |
| 2 | `test_a_faithful_copy_across_an_abbreviation_never_shows_its_tail_unchecked`, the diagnosis's reproduction: the tail goes to the check with the whole record sentence as its quote, nothing shown on the first pass | 2 of 2 | Yes |
| 2 | `test_the_widener_gives_the_check_the_whole_sentence_across_an_abbreviation` | 1 of 1 | Yes |
| 3 | `test_a_sentence_inside_a_quotation_or_bracket_goes_to_the_check_as_the_whole_unit`: straight quotes and round brackets (the diagnosis's two reproductions), curly quotes, square brackets | 4 of 4 | Yes |
| 3 | `test_a_bracket_that_never_closes_holds_the_rest_of_the_record`: a stray "(" holds every later sentence; a ")" with no "(" opens nothing | 1 of 1 | Yes |

Slice 2's red run on the code before it, from output: "5 failed, 73 passed". Slice 3's: "5 failed, 78 passed".

Pass counts after all three slices, from output:

- `test_copied_cuts.py`: "83 passed in 2.23s".
- `tests/system_03_search_agent/synthesis`, run once: "750 passed, 10 skipped, 1 xfailed in 4.57s".

## Mutations

One property broken by hand at a time, the test file run, the file restored and its sha256 compared.

| Mutation | Result, from output |
|---|---|
| Slice 1: the quoted branch falls back to the quote (`run = quote` when the run is None) | "2 failed, 71 passed": both quoted-cut cases |
| Slice 2: `_ends_on_abbreviation` returns False | "5 failed, 73 passed": every slice 2 case |
| Slice 3: `_still_open` returns False | "5 failed, 78 passed": every slice 3 case |
| Slice 3: straight double quotes not counted | "1 failed, 82 passed": the straight quotes case |
| Slice 3: no clamp at zero for a closing mark with no opening one | "1 failed, 82 passed": the stray bracket test's ")" half |

Every run ended "restored, sha256 matches".

## Faithful sentences dropped

The number asked for: 0 on every offline corpus available.

| Corpus | What was measured | Result |
|---|---|---|
| The 168 recorded first drafts of rounds 4 and 5 (`raw/replay_r6.py`, the round 5 draft selection over the same trace folders), develop c916cfa3 against each slice | Sentences develop shows that the slice drops, check approving nothing and approving every item sent | 0 and 0 on every slice; 0 shown that develop does not show; 0 drafts emptied; 34 items on every tree |
| The 55 distinct record values in those traces (`raw/exposure.py`) | Record sentence breaks the new boundary removes; sentences newly past 600 characters | 0 of 77 breaks removed; 0 newly past 600 |
| The 33 distinct record values over 150 characters in the repository's recorded JSON (`raw/corpus_records.py`) | Develop record sentences no longer whole | 0 of 179 |

What this does not cover, stated rather than left for a reviewer to find:

- The replay passes no writer quotes, as round 5's did, so slice 1's quoted path is measured only by its tests.
- The corpora are small and carry no "S." or "U.S." before a capital, and no multi-sentence quotation. The cost slice 2 accepts is real but unmeasured: a record sentence that truly ends on one capital letter ("... vitamin C. Then ...") is read joined to the next, so a faithful copy of either half becomes a cut the check must approve, and is held if it says no.

## Gates

- `ruff check` on the two touched Python files: "All checks passed!" after each slice.
- `isort --check-only` on the same files: clean after each slice.
- The pre-commit hook ran on each commit: "PASS: no local references found."

## Deviations and choices for the lead

| Item | What I did | Why, and the cost |
|---|---|---|
| The writer's splitter (`_split_sentences`, `_SENTENCE_BOUNDARY`) | Left unchanged. I built and measured the join (the same abbreviation shape applied to the writer's reply, the question licence kept on the old split) and reverted it | It turned `test_required_paths.py::test_a_framing_prefix_cannot_smuggle_an_uncited_claim` red: "vitamin C. Note: ..." joined two stripped sentences into one, so the strip count fell from 4 to 3, a disclosure undercount. It also needs a separate question splitter, or a closed question after "the U.S." rides inside an open one and licenses its words (R-01). The record fix alone closes the hole. Cost: a faithful writer copy across "S. Typhimurium" now reaches the check as its tail and is likely held, where the join would show it whole. On the 168 drafts the join changes nothing either way. |
| The code-built record list | Not changed: `findings.build_structured_fallback_narrative` splits a value with the writer's splitter, outside this fence | The record list shown when the writer's answer fails can still print "No isolates of S." and "Typhimurium carried the blaCTX-M gene." as two rows of one record. Both rows show, so nothing is hidden, but the second reads as a claim. A writer-side join would fix it; the lead's call. |
| `_starts_inside_record_sentence` | Not changed, though the diagnosis named it as a user of the boundary | It does not read `_RECORD_SENTENCE_BOUNDARY`: it tests normalized, lowercased text for a sentence-ending mark, and only a lowercase-opening sentence reaches it. A copied tail after "S." opens on a capital and never reaches it. |
| The reworded path in `run_grounding_pass` (`widen_to_record_sentences(pair_quote, ...)`, line 1783) | Not changed | By card 89's design it still falls back to the writer's quote when the run is past 600 characters, so a reworded sentence on a long run is checked against the quote alone. It is checked, so it is outside this card's statement, but it is the same shape as J5-101-01. Slices 2 and 3 can only lengthen runs; the corpora show 0 newly past 600. |
| "Dr. Smith", "et al. Smith" | Still break | No shape tells a two-letter word from a sentence's last word without a list, which Rule 2 forbids. The comment says so. |

## Learnings

- The scratchpad is shared by every agent of the lead's session: my mutation script there was overwritten by another agent mid-build. The mutations had already run and their outputs are above; the replay trees were then exported into a folder only this builder used. Cost about five minutes. For the next builder: put scratch work in a subfolder named for the card and the role.
- The writer-side join cost about ten minutes to build, measure and revert. The signal that it was out of scope came from a neighbouring security test's strip count, not from the card's own tests: run the grounding test files that pin `stripped_count` before widening any splitter.
