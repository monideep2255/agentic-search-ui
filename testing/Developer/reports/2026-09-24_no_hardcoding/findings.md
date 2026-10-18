# No hardcoding, measured on 2026-09-24

Verdict: 12.9 met on all 12 full feedback questions, 12.3 asks back the bare short questions with choices a model writes for the subject, and the guardrail kept 68 of 68 verdicts right after losing its test-question example.

## Table of contents

- [What was measured](#what-was-measured)
- [Item 12.3, short questions](#item-123-short-questions)
- [Item 12.9, the two depths](#item-129-the-two-depths)
- [Item 12.16 part 1, the guardrail without its example](#item-1216-part-1-the-guardrail-without-its-example)
- [What is not fixed](#what-is-not-fixed)
- [Instruments](#instruments)

## What was measured

The merged code on develop (merges `5a25f72` and `84c2971`, plus `a565fd7` and `1cd5968`), run locally with live models and live NCBI calls, one question at a time.

## Item 12.3, short questions

After one tuning of the classifier's instruction, three runs each (`live_runs_short/`):

| Question | Asked back | Choices it wrote, one run |
|---|---|---|
| `reflux disease` | 3 of 3 | What is reflux disease? / What are the symptoms of reflux disease? / Which treatments are available for reflux disease? / Are there recent clinical trials on reflux disease? |
| `GERD` | 3 of 3 | What is GERD? / Which genes or variants are linked to GERD? / Are there clinical trials for GERD treatments? / What does recent research say about GERD? |
| `BRCA1` | 3 of 3 | What is the BRCA1 gene? / What diseases or conditions is BRCA1 linked to? / Are there clinical trials involving BRCA1 mutations? / What recent research is available on BRCA1? |
| `Marfan` | 3 of 3 | What is Marfan syndrome? / Which gene is linked to Marfan syndrome? / What are the symptoms of Marfan syndrome? / Are there clinical trials for Marfan syndrome? |
| `MeSH` | 2 of 3 | What is MeSH? / Which papers use MeSH terms for a specific disease? / How are MeSH terms assigned to articles? |
| `hello` | 1 of 3 | Answered as a greeting on the other two runs |
| `papers on caffeine` | searched | Answered with 10 citations |

The tuning, measured first (`live_runs/`): `MeSH` was searched 2 of 2, found nothing and refused. Two general principles were added to the instruction, no word list: a bare name of a database, vocabulary, method or tool is still only a subject; and when unsure, ask back.

## Item 12.9, the two depths

All 12 full questions from `fix-1` and `fix-2`, at both depths (`live_runs/`):

- Every one differs in its opening sentence and its list: plain language a list of titles, researcher a table with an identifier column.
- Where citation counts differed by one or two, both depths listed the same records; one depth's prose also cited a paper's abstract, which is a second citation of the same paper.
- One run in 24 refused at the think step: `is there a trial recruiting for melanoma` at researcher depth, recorded as 12.17.

## Item 12.16 part 1, the guardrail without its example

`probe_guard_ten_runs.py` and `guard_ten_runs.txt`: 68 checks, 0 wrong. The coffee question, whose own text used to be the prompt's example, was admitted 10 of 10.

## What is not fixed

- 12.17: a good question sometimes refuses at the think step with a schema error, twice in about forty live runs.
- 12.16 part 4's residual: the rule for a sentence that switches records is satisfied by any shared title word, and a generic one ("patients") is a weak anchor.
- 12.16 part 3: the literature-request routing is still a word list.
- A model deciding 12.3 is a judgement: a borderline word can go either way on a run.

## Instruments

- `live_check.py`: every feedback question, the short ones asked back or not, the full ones at both depths.
- `make_short_check.py` builds `live_check_short.py`, the short questions three times each; `summarise_short.py` prints its lines.
- `probe_guard_ten_runs.py`: the guardrail's verdicts, every should-admit question ten times.
- The raw log of the short run is not committed: it carries local file paths from a harmless local-only traceback when the probe saves history without a signed-in identity.
