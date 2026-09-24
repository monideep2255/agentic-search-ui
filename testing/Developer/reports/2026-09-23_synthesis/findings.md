# Items 12.9 to 12.12, measured on 2026-09-23

Verdict: code-only checking of a synthesis passed 0 of 53 model sentences across six live replies, so 12.10 is blocked on a product-owner decision; 12.11 and 12.12 ship, and researcher answers keep their prose again.

## Table of contents

- [What was built and measured](#what-was-built-and-measured)
- [Why code-only checking cannot pass a synthesis](#why-code-only-checking-cannot-pass-a-synthesis)
- [What ships](#what-ships)
- [The live run of what ships](#the-live-run-of-what-ships)
- [Instruments](#instruments)

## What was built and measured

The design recorded in `testing/UI_fix_plan.md` row 12.10: a sentence in the model's own words may stand when it carries the record's exact words as `[N: "words"]`, and four exact checks pass (quote in record, words, numbers, polarity).

- A new instruction told the model to answer the question and attach quotes. It did write the answer asked for: "GERD stands for gastroesophageal reflux disease ... The most common symptoms are heartburn and regurgitation."
- It attached quotes on five of six live replies and none on one.
- The code check passed 0 of 53 sentences across the six replies.
- Four rounds of widening the rule, each measured by replaying the captured replies offline, moved it from 0 to 0: several quotes per sentence, word endings, the paper's own title, grammatical glue words. So did an instruction to keep the paper's own terms.

## Why code-only checking cannot pass a synthesis

The model paraphrases, and a fixed rule cannot tell a synonym from an invention. Words it could not verify, from the per-clause replay:

- GERD: "mouth" for "oral cavity", "kidney" for "renal", "common" for "typical", "medication" for "PPIs"
- Ashkenazi: "change" for "mutation", "carry", "harmful" for "pathogenic"
- Coffee: "benefit", "lower", "avoid", "recommend"

Two quotes were rejected correctly: the model spliced two record sentences into one quote, and dropped a bracket (brackets are now ignored in quote matching).

The instruction alone was a REGRESSION: it made the model paraphrase, so GERD, which answered by quoting its abstract, dropped to a bare list. It was reverted and does not ship.

## What ships

- 12.11: "Based on N sources" counts distinct pages, the key the source list merges on. Arm proven red against the old count.
- 12.12: a sentence opening on a leftover lowercase connective ("however", "so") is dropped; a sentence whose quote marks do not pair is dropped; "Another", "A third", "The other" with nothing before it is dropped; any other lowercase opening is capitalised rather than dropped.
- 12.12: record restatements are dropped at every depth, compared against the row the list SHOWS rather than the whole cited record. This is also why researcher answers keep prose drawn from abstracts again.
- The quote support in the gate stays. It runs only after the strict path rejects a clause, so it can only accept more, and nothing reaches it without a quote.

## The live run of what ships

Seven questions, both depths, `runs/`. Words include the list.

| Question | Plain | Researcher | What changed |
|---|---|---|---|
| reflux disease | 142 | 196 | Researcher longer |
| GERD | 121 | 199 | Researcher has symptoms, complications, treatment and risks in prose, under a heading |
| Any trials for GERD? | 152 | 152 | Unchanged |
| caffeine papers | 113 | 143 | Still a list |
| Does coffee help ...? | 95 | refused | Refused at the think step, the classifier's schema error, not the write step |
| mediterranean | 125 | 147 | Still a list; papers are about Turkish and Hispanic populations |
| ashkenazi | 130 | 133 | Plain carries isolated quoted sentences that do not answer the question |

The restatement paragraph is gone from every answer, so a record now appears twice (opening sentence and list), not three times.

## Instruments

- `probe_gate_verdicts.py`: one live question, saves the keyed reply, the quotes and every finding.
- `replay_gate.py`: re-runs the current gate over saved replies offline, with per-clause reasons.
- `run_both_depths.py`: the seven questions at both depths.
