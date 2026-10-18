# Version 5 measured live: a negative result

Four runs against develop at `14f7713`. Recorded as a failure, because it is
one, and because five versions of one directive failing the same way is the
finding rather than an embarrassment to bury.

## What version 5 produced

Plain language, BRCA1, 58 prose words:

```
Found 4 disease records for BRCA1: Familial cancer of breast [1], ...
BRCA1 is associated with four diseases: Familial cancer of breast [1], ...
```

Researcher, same question, 94 prose words, opening with the SAME two
sentences and then adding the symbol, the name and the ClinVar records.

## Why that is a failure on three counts

- It is SHORTER than the 89-word baseline, not longer. Version 4 was 206 and
  was padding; version 5 is 58 and is a bare restatement.
- The two depths still read alike, which is the entire defect 11.31 was raised
  about.
- It does not explain anything, which is what the product owner asked for.

## The explanation is retrieved, pointed at, and still unused

All three of these are true in the same run, which is what makes this
diagnostic rather than merely disappointing:

- NCBI's gene summary IS retrieved and IS a citeable finding, `[12]`.
- `[12]` is inside `_MAX_FINDINGS_FOR_MODEL_PROMPT`, so the model was shown it.
- `build_explanatory_directive` named it explicitly: "PLAIN DESCRIPTIONS: [12]
  are written-out descriptions of a record rather than a value. Use them to
  explain what the answer means, quoting their words exactly."

The model still did not use it.

## The most probable cause, consistent with everything measured today

`ground_claim` accepts a claim against a long free-text finding only when the
claim is a VERBATIM CONTIGUOUS EXCERPT of it. A model asked to explain does
what explaining is: it condenses and rephrases. Every such sentence fails the
match and is deleted silently, so the answer arrives looking merely thin
rather than censored.

That is the same mechanism this folder's `findings.md` established offline, now
reproduced end to end through the live product with the explanatory material
present and explicitly pointed at.

## What this rules out

Instructing the model. Five versions have now tried:

| Version | Instructed | Result |
|---|---|---|
| 1 | Do not print identifiers | Depth refused outright |
| 2 | Keep background to a minimum | Reported 3 of 4 findings, looked confident |
| 3 | State identifiers exactly, say less | Refused with an empty narrative |
| 4 | Give each finding its own sentence | 206 words of enumeration, no explanation |
| 5 | Explain, quote exactly, no length rule | 58 words, no explanation |

A sixth version is not the fix. The constraint is not what the model is told.

## The remaining lever

Stop asking the MODEL to reproduce the source text, and have the CODE place it.

The record tables under every answer are already built this way, and the
reasoning is written into `core/graph.py`: every cell is built in code
straight from a finding's own structured fields, so the hallucination risk the
grounding gate exists for does not apply to them. A gene summary rendered by
code from the finding's own `field_value`, cited to that finding, is the same
shape of object. It cannot hallucinate, because no model touches it, and it
cannot be stripped, because it IS the source text.

That would give a plain-language answer NCBI's own plain-English explanation,
verbatim and cited, with no change to the grounding gate and no relaxation of
cite-or-refuse.

It needs a product decision, because it changes what an answer is composed of
rather than how a model is instructed, and it is recorded here rather than
built on the strength of one session's reasoning.

## One defect that must be fixed either way

The summary's value arrives truncated MID-WORD, "through the C-terminal d",
and it is a middle slice rather than the opening, so the answer would quote
NCBI badly even once the composition is right. That is item 11.33, and it
blocks this regardless of which way the decision goes.
