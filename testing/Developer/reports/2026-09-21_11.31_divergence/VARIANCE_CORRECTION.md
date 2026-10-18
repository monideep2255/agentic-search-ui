# Correction: the single-run comparisons in this folder do not hold

Written 2026-09-21, after the product owner asked whether the day's work had
made the product worse. Answering that honestly required a measurement that
had not been taken, and taking it invalidated two earlier claims in this same
folder.

## The measurement

Three runs of "Which diseases are associated with BRCA1?" at `plain_language`
against develop at `3caf823`, back to back:

| Run | Prose words |
|---|---|
| 1 | 113 |
| 2 | 66 |
| 3 | 101 |

The same question, the same depth, the same code, in the space of a minute.

## What that invalidates

`baseline.md` and `after/results.md` both compare SINGLE runs and draw
conclusions from the difference. With a spread of 66 to 113 on one
configuration, those differences are inside the noise:

- The baseline's 89 prose words was one run. It sits in the middle of the
  range above.
- `after/results.md` reports "89 to 206, the ordering REVERSED" as the result
  of version 4. The 206 is genuinely outside the range, so version 4's padding
  was real. The REVERSAL claim, which compared it against a single 164-word
  researcher run, is not supported.
- `v5/results.md` calls 58 prose words "SHORTER than the 89-word baseline, not
  longer" and counts that as one of three failures. It is not a failure. It is
  the low end of ordinary variance.

Version 5 is therefore statistically indistinguishable from the pre-11.31
behaviour on prose length, rather than a regression.

## What does NOT change

The finding those reports exist to record is untouched, because it never
depended on a length comparison:

- The gene summary is retrieved, is a citeable finding, is inside the model's
  prompt slice, and is explicitly named to the model by marker.
- The model does not use it.
- Five directive versions have failed, each differently.
- `ground_claim` accepts a long free-text finding only as a verbatim
  contiguous excerpt, and explaining means rephrasing.

None of that is a measurement of length, so none of it moves.

## The lesson, which is the same one twice in one day

The product owner's correction was that words do not define an answer. This is
that correction arriving a second time from a different direction: not only was
word count the wrong PROPERTY to measure, a single run was never enough
SAMPLES to measure it with. The report that claimed success did so on one
observation per configuration, and it took a direct question to go and check.

Any future claim in this folder about an answer getting longer, shorter or more
readable needs at least three runs per configuration, and should say so.
