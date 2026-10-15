# Card 17 build: option B replayed and not kept

Build report, 2026-10-09, branch `fix/card17-generic-title-word`, cut from `develop` at `b01dee92`. Paths are relative to `<repo-root>`. Diagnosis: `testing/Developer/reports/2026-10-08_overnight/card17_diagnosis.md`.

Verdict: not kept. Option B drops good sentences on the saved live replies, so it was reverted as the owner's choice required. No source or test file changes in this commit; only this report and its replay evidence.

## Table of contents

- [The ticket and the owner's condition](#the-ticket-and-the-owners-condition)
- [What was built](#what-was-built)
- [How the replay ran](#how-the-replay-ran)
- [Replay numbers](#replay-numbers)
- [The good sentences it drops](#the-good-sentences-it-drops)
- [Why option B cannot meet the condition](#why-option-b-cannot-meet-the-condition)
- [What is left on develop](#what-is-left-on-develop)
- [Files](#files)

## The ticket and the owner's condition

In the user's words: "A reworded sentence that switches papers never points at the wrong paper because the only word it shares with that paper's title is a generic one such as 'patients'."

The owner's choice of 2026-10-09: "the cheapest code rule (option B), replayed over saved live answers first, and kept only if it drops no good sentence."

## What was built

Option B, in `synthesis/grounding.py`, kept as `raw/option_b.patch`:

- `run_grounding_pass` passes `_names_its_record` the titles of the records the last shown sentence cited at a different page. A title and an abstract of one paper share a page, so they count as one record.
- `_names_its_record` counts a shared title word only when none of those left titles carries it.
- Short forms a record defines (card 88) were left unchanged.

## How the replay ran

No model call and no network. `raw/replay_option_b.py` reads saved live traces of the card 88 bench family (`local_write_trace.py`'s spies, plus each finding's page and the sentence check's items). It runs the grounding pass twice per writer draft:

- Before: the option B code with the left titles forced empty, which is exactly the code before the change.
- After: the option B code.

Each draft runs in two approval modes:

- Live: the approvals the sentence check gave in that run.
- All: every reworded candidate approved, the widest test of the switch rule.

The three `.log` files beside `local_write_trace.py` (`testing/Developer/reports/2026-10-05_card88/raw/`) carry the writer's reply but not each finding's page, so the rule cannot be judged on them. The replay used the traces of the same bench that do carry pages:

| Folder | Runs | Question |
|---|---|---|
| `2026-10-05_wave3/sentence_check_raw` | gp1 to gp5 (Plain language), gr1 to gr5 (Researcher), md1 to md5 | GERD, and the Mediterranean variants question |
| `2026-10-05_wave3/sentence_check_raw/develop_control` | cp1 to cp5, cr1, cr3 to cr5, cm1 to cm5 (cr2 stopped with an error before writing) | The same |
| `2026-10-05_sentence_check/raw` | gerd1 to gerd3, med1 to med3 | The same |

These traces were recorded on 2026-10-05 code; the replay runs today's grounding pass over them, so absolute counts are today's, and only the before and after difference is the measure.

## Replay numbers

From `raw/replay_option_b.txt`: 35 runs, 67 writer drafts.

| Approval mode | Sentences shown before and dropped after |
|---|---|
| Live | 2 |
| All | 12 |

The card 88 bar, two or more written sentences on 5 of 5 GERD runs at each depth, live approvals, the last draft the check saw:

| Set | Before | After | Runs with 2 or more, before and after |
|---|---|---|---|
| Plain language, gp1 to gp5 | 2, 3, 4, 2, 5 | 2, 3, 4, 2, 5 | 5 of 5, 5 of 5 |
| Researcher, gr1 to gr5 | 5, 2, 5, 4, 2 | 4, 2, 5, 4, 2 | 5 of 5, 5 of 5 |
| Plain language, cp1 to cp5 | 1, 3, 3, 4, 1 | 1, 3, 3, 4, 1 | 3 of 5, 3 of 5 |
| Researcher, cr1, cr3 to cr5 | 2, 0, 2, 2 | 2, 0, 2, 2 | 3 of 4, 3 of 4 |

The bar's run counts do not move, but the owner's condition is stricter: no good sentence dropped. Two are dropped with the live approvals, so the change fails it.

## The good sentences it drops

Each one is true to its quote and cites a paper on the same subject as the paper just left. None of them is a wrong-paper link.

| Run | Sentence dropped | Switch | Why it fell |
|---|---|---|---|
| gr1, live | "Long-term use of proton-pump inhibitors, the most effective treatment, is associated with bone fractures, chronic renal disease, ..." | From a paper titled "Gastroesophageal reflux disease in children: What's new right now?" to one titled "Gastroesophageal Reflux Disease." | Its one shared title word, "disease", is in the left title too |
| gr4, live | The same sentence | The same kind of switch | The same |
| cm5, all | "Studies of Turkish patients have identified the most common MEFV variant as R202Q, found in about 39% of tested alleles." | From "Clinical and molecular evaluation of MEFV gene variants in the Turkish population ..." to "Molecular analyses of MEFV gene mutation variants in Turkish population." | "MEFV", "variants" and "Turkish" are all in the left title |
| gp4, all | "Reflux symptoms are among the most common reasons people visit their primary care doctor." | From one paper titled "Gastroesophageal Reflux Disease." to another with the same title | "Reflux" is in both titles |

The other eight drops in the all mode are the same proton-pump inhibitor sentence in other runs (gp1, gp3, gr3, gr5, gerd3) and two more Turkish MEFV sentences (cm2, med3).

## Why option B cannot meet the condition

Answers draw several papers on one subject, and their titles share the subject's own words: "gastroesophageal reflux disease", "MEFV", "Turkish". Option B treats a word the left paper shares as no anchor, so a sentence moving between two papers on the same disease loses its anchor exactly when the move is harmless. The Tay-Sachs case it targets, a switch to a paper on a different subject, is the rarer one. Code reading title words cannot tell the two apart; a reader of the sentence in context can.

## What is left on develop

Nothing changed on the answer path. The switch rule is as `044f834b` left it: one shared stemmed title word, or a defined short form, names the record.

The remaining options in the diagnosis that do not lose sentences this way are D (ask the sentence check whether the sentence still says what its quote says when read after the one before) and E (keep the sentence and name its paper in a code-built lead-in). Both are the owner's to choose.

## Files

| File | What it is |
|---|---|
| `raw/option_b.patch` | The reverted option B diff, for the record and to rerun the replay |
| `raw/replay_option_b.py` | The replay; runs against a tree with the patch applied: `python -I replay_option_b.py <src> <out.txt> <trace-folder>...` |
| `raw/replay_option_b.txt` | Its output, every dropped sentence and the per-run counts |
