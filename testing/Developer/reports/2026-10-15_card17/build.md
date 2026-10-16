# Card 17 build: a sentence that switches papers names its paper (option E)

Built 2026-10-15 on branch `fix/card17-name-the-paper`, from `develop` at `7626fe85` plus the design commit (`3607d44f`). Paths are relative to `<repo-root>`. Nothing is committed. The design is `design.md` in this folder.

## Table of contents

- [What was built](#what-was-built)
- [Replay against the design's numbers](#replay-against-the-designs-numbers)
- [Mutation proofs](#mutation-proofs)
- [Live check](#live-check)
- [Gates](#gates)
- [Files](#files)
- [Learnings](#learnings)

## What was built

- `synthesis/grounding.py`: the anchor test factored out of `_names_its_record` into `title_words_shared`, `names_by_short_form`, `record_labels_by_page` and `short_forms_by_page`. `_names_its_record` is now `bool(title_words_shared(...)) or names_by_short_form(...)`, and `run_grounding_pass` calls the two map helpers. No behaviour change: the existing switch tests pass untouched.
- `synthesis/answer_layout.py`: `name_switched_records(grounding, synth_findings)`, with `lead_in_title`, `lead_in_for`, `LEAD_IN_MAX_TITLE_CHARS = 160` and `LEAD_IN_FRAME`. It runs the five conditions of the design on the sentences the reader sees.
- `core/graph.py`: one call after `drop_record_restatements`, inside the same `if`, plus an info log line with the count.
- The lead-in is `From the paper "<title>": ` then the approved sentence unchanged. Other record types read "the trial", "the <noun> record", and "the record" when the finding carries no record type (a bare "the record record" would be wrong). Several switched-to pages read `From the papers "A" and "B": `.

## Replay against the design's numbers

`raw/replay_option_e.py`, run over the same 35 runs and 67 writer drafts, no network. Full output with every lead-in added: `raw/replay_option_e.txt`.

| Measure | Design | Replay |
|---|---|---|
| Lead-ins, live approvals | 20 | 20 |
| Lead-ins, all candidates approved | 45 | 45 |
| Sentences dropped | 0 | 0 |
| Bodies, claims, origins or counts changed | 0 | 0 |
| Sentences meeting the five conditions with no lead-in | 0 | 0 |
| Lead-ins on sentences not meeting them | 0 | 0 |
| Quoted titles that are not the label of a page the sentence cites | 0 | 0 |
| Pass count disagreeing with sentences changed | 0 | 0 |
| GERD runs with two or more written sentences, live | unchanged by construction | 12 of 13 (the pass changes no count) |

The "expected" side of the replay is a separate walk written in the script, not the pass itself, so the two agree by test and not by sharing code. The 12 of 13 GERD figure is the shipped draft of the saved runs and is identical before and after the pass.

## Mutation proofs

Each mutation changes one property in the source, the named test goes red, the file is restored. Thirteen tests were added (12 in the design, plus one at the grounding-pass level). 12 mutations were run; the `==` and `<=` tests were found weak on the first pass and were rewritten so a single-property mutation turns them red.

| Mutation (one property) | Test that went red |
|---|---|
| Pass returns its input | the first test, and the sentence-check test |
| No "a sentence was shown before it" guard | first sentence of the prose |
| Page disjointness removed (title then abstract counts as a switch) | same page is no switch (first version was green; rewritten so the sentence shares one title word) |
| "At most one shared word" removed | two shared words (first version was green; a two-page case, one page anchored by two words and one by one, was added) |
| Short form test removed | defined short form |
| Evidence-quote condition removed | copied sentence |
| Bracket removal removed | translated title |
| Length cap removed | long title cut at a word |
| Markers not stripped before the title test | marker digit |
| "the trial" noun removed | trial and condition nouns |
| Only the first switched-to page named | two pages named |
| Card 111 test reads a substring instead of the whole piece | lead-in sentence stays in the prose and may lead |

## Live check

Five runs each through `core/run.py` `run_streaming` with `reads_placement=True`, develop's settings, no Opus. Runner `raw/live_check.py`; per-run traces in `raw/live/` (token text, and the sentences the pass received and returned). Four runs at a time. Total spend 0.35 USD of the 0.80 budget.

### Counts

| Question | Depth | Runs | Lead-ins shown | Sentences lost by the pass |
|---|---|---|---|---|
| GERD | Plain language | 5 | 0 | 0 |
| GERD | Researcher | 5 | 5 (in 4 runs) | 0 |
| Mediterranean | Plain language | 5 | 0 | 0 |
| Mediterranean | Researcher | 5 | 0 | 0 |
| Ashkenazi (held out) | Researcher | 3 | 0 | 0 |
| Ashkenazi (held out) | Plain language | 1 | 1 | 0 |

Every pass's input and output were compared: same sentence count, and every led-in sentence equals the input sentence after the lead-in is removed.

### Every lead-in shown

1. Ashkenazi, Plain language, run 1. The sentence above (a different paper, about recruiting carriers of a mutation for future trials). Shown: `From the paper "Molecular analyses of MEFV gene mutation variants in Turkish population": This condition primarily affects people of Turkish, Armenian, Arab, and non-Ashkenazi Jewish descent [3].` Names the right paper, and it is the card's own shape: "This condition" now resolves to the MEFV paper, not the sentence above.
2. GERD, Researcher, run 2. Shown: `From the paper "Gastroesophageal reflux disease in children: What's new right now?": In young children, clinical manifestations are varied and nonspecific, necessitating careful diagnostic evaluation [2].` Right paper (the children's review, cited as [2]).
3. GERD, Researcher, run 3. Shown: `From the paper "Gastroesophageal reflux disease in children: What's new right now?": Pathogenic factors include abnormal transient relaxations of the lower esophageal sphincter, defects in esophageal mucosal defense, ...` Right paper (the sentence cites that paper).
4. GERD, Researcher, run 4, first. Same children's review lead-in on "In young children, clinical manifestations ...". Right paper.
5. GERD, Researcher, run 4, second. Shown: `From the paper "Gastroesophageal Reflux Disease": Proton-pump inhibitors are the most effective treatment, but long-term use is associated with bone fractures, chronic and acute renal disease, community-acquired pneumonia, and Clostridium difficile intestinal infection [1].` Right paper (the adult review), and it tells the reader the sentence is not about children, which the sentence above was.
6. GERD, Researcher, run 5. Same children's review lead-in on "In young children, ...". Right paper.

All six name the paper the sentence's own citation opens. None names a paper the sentence is not about.

### Does Plain language read too heavy

Not on this evidence, with one wording note.

- Plain language shows a lead-in rarely: 1 in 11 Plain language runs here (none in five GERD runs, none in five Mediterranean runs, one in the single Ashkenazi run), against 4 of 5 GERD Researcher runs. The replay measured 20 live lead-ins in 35 saved runs, about one sentence in five in a GERD answer, so five runs is a thin sample on the Plain language side and the number could be higher.
- A lead-in is the paper's whole title: 11 words for the children's review, 12 for the MEFV paper. Read once in an answer, it does not crowd the sentence. Two in one answer (GERD Researcher run 4) is the heaviest case seen, and is Researcher.
- The one thing that reads awkwardly: a title that ends in a question mark puts `?":` before the sentence ("What's new right now?"). It is true and mechanical, so it was left. If the owner wants it lighter, the shorter form of the design's option 3 goes on top of this, never instead of it.

No shorter form was built.

### Other numbers from the check

- Elapsed: 20 of 24 runs finished in 10 to 17 s. Four took longer: 22.0 s (Ashkenazi Plain language), and 44.3, 46.1 and 46.8 s (GERD Researcher run 2 and GERD Plain language runs 2 and 5), each of which ended with trust outcome `ask`. The pass takes microseconds and these were four runs at once, so this is not attributed to the change, but the "within 20 s" bar of the design was not met on 4 of 24 and no control run was made to say whether develop does the same under four at a time.
- One Ashkenazi Researcher run (run 1) ended with trust outcome `ask` and one summary sentence, so no pass ran.
- Prose sentences reaching the pass in the GERD runs: Plain language 7, 3, 10, 4, 12 and Researcher 5, 4, 5, 4, 4, identical before and after the pass in all ten. The trace does not mark which are reworded, so the "two or more written sentences" bar is not separately counted here; the replay's 12 of 13 is that count on saved runs.

## Gates

- `ruff check` (no path): All checks passed.
- isort gate 2 command (`isort --check-only` over `src tests services tracker alembic .claude .github`): exit 0, nothing to change.
- `pytest tests/system_03_search_agent/synthesis tests/system_03_search_agent/core -m "not integration" -q`: 2296 passed, 66 skipped, 1 deselected, 1 xfailed.

## Files

| File | Change |
|---|---|
| `src/system_03_search_agent/synthesis/grounding.py` | Anchor test factored out, four helpers |
| `src/system_03_search_agent/synthesis/answer_layout.py` | `name_switched_records` and its lead-in helpers |
| `src/system_03_search_agent/core/graph.py` | One call and a log line |
| `tests/system_03_search_agent/synthesis/test_answer_layout.py` | 11 new tests |
| `tests/system_03_search_agent/synthesis/test_sentence_check.py` | 1 new test (mutation proof at the grounding level) |
| `tests/system_03_search_agent/core/test_summary_label_only_sentence.py` | 1 new test (card 111 rule and lead candidates) |
| `testing/Test_queries_and_workflows.md` | Query 113 and its card row. 112 is taken by card 29's branch, so this card takes 113 |
| `testing/Developer/reports/2026-10-15_card17/raw/replay_option_e.py`, `.txt` | Replay and its output |
| `testing/Developer/reports/2026-10-15_card17/raw/live_check.py`, `raw/live/` | Live runner and 24 traces |
| `testing/Developer/reports/2026-10-15_card17/raw/probe_switches.py` | Lint fixes only (unused suppressions, an unused variable, a dict literal); behaviour unchanged |

## Learnings

- Two of the first mutation checks stayed green: a test only proves a property if its fixture reaches that property alone. A sentence with no shared title word never fires, so it cannot show that a same-page check or an "at most one word" check exists. Build the fixture so the sentence shares exactly one word, and for a many-page rule use two pages with different counts.
- `isort` (gate 2) and `ruff`'s import sorter disagree on `from m import X as Y` beside `from m import (...)`. Import the module under another name instead of aliasing a name.
