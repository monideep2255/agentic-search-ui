# Why abstracts reach the page cut mid-word: a blocked stop, not an answer

Investigated 2026-09-21. This is recorded as UNRESOLVED on purpose. Every
character cap in the codebase was ruled out by execution, and the remaining
hypothesis could not be reproduced, so no fix was written. A plausible fix in
the wrong place would have been worse than this file.

## Table of contents

- [The symptom](#the-symptom)
- [What was ruled out, by execution](#what-was-ruled-out-by-execution)
- [Where that text comes from](#where-that-text-comes-from)
- [The leading hypothesis, and where it breaks](#the-leading-hypothesis-and-where-it-breaks)
- [A separate defect found on the way](#a-separate-defect-found-on-the-way)
- [What closes this](#what-closes-this)

## The symptom

Live on develop at `46fff40`, in the answer's "Pubmed records found" section:

- "...or 'mutational signatures', wer [27]."        (should be "were")
- "...with inherited breast and/or ovarian c [29]." (should be "cancer")
- "Using single-cell RNA sequencing analysis of human preneoplas [31]."
- "...whether it functions in resection directly has been uncle [33]."
- "Here, we report that BRCA1 promotes ferroptosis s [35]."

The text before each marker is 132, 141, 61, 153 and 49 characters. The
lengths VARY, which is what rules out a single fixed cap on the rendered
line before any code is opened.

## What was ruled out, by execution

| Candidate | Why it is not the cause |
|---|---|
| `findings.py` `MAX_FIELD_VALUE_CHARS = 2000` via `_clip` | 10 to 40 times larger than the observed cuts, and it clips whole values |
| `ncbi_eutils_actions.py` `_MAX_FIELD_VALUE_CHARS = 4000` via `_cap_text` | Too large, and DEFINITIVE on a second ground: when it fires it appends the literal `" [truncated]"`, and no such string appears anywhere in the capture. The cut runs straight into the marker |
| `answer_layout.py` `record_label` and `table_second_cell` `[:500]`, `MAX_HEADING_CHARS = 60` | All larger than observed, and none applies to PubMed body text |
| `core/graph.py` `sentence_token`'s `[:1000]` | Larger than observed |
| Every numeric cap between 40 and 200 across `src/system_03_search_agent/` | Grepped exhaustively; none touches a PubMed title or abstract field |
| `grounding.py` `_SENTENCE_BOUNDARY` | `(?<=[.;?!])\s+` can only split after punctuation plus whitespace, never mid-word |
| `ground_claim` | A boolean containment check. It never slices or trims; what reaches display is exactly what entered the pass |

Executed rather than read: `run_grounding_pass` was driven over constructed
multi-sentence abstract findings. A finding whose body spans several
sentences either survives WHOLE or is dropped WHOLE. It never produces a
mid-word cut.

## Where that text comes from

`core/graph.py`'s `listing()` is fed either `fallback_sentences` or
`tail_sentences`, both built by `build_structured_fallback_narrative` through
`render_finding_body`, which renders the whole abstract verbatim. There is no
code-picked snippet anywhere in that path.

Since that path is whole-or-nothing, the five observed fragments most likely
reached the page through the ordinary MODEL-PROSE branch instead, not the
code-built tail.

## The leading hypothesis, and where it breaks

`SYNTH_SYSTEM_INSTRUCTION` rule 3 tells the model to quote a cited value "in
full and exactly", warning that a value not quoted whole is deleted. For a
multi-hundred-word abstract that collides with the depth directive's brevity.
A model attempting a long verbatim quote and placing its marker part-way
could leave exactly this shape, and `run_grounding_pass` deliberately treats
a strip at the END of a sentence as survivable rather than as a middle drop.

It breaks under direct test. `claim_introduces_no_new_content`, run against a
claim ending "...signatures', wer" versus a value containing
"...signatures', were", returns False: "wer" and "were" are different tokens,
so the fragment should have been stripped rather than shipped.

So either the real completion differs from the reconstruction, or there is a
genuine gap in how that check is reached for a claim ending exactly at a
mid-word marker. The capture holds only the final `answer_text`, not the raw
model completion or the raw retrieved abstract, so the two cannot be told
apart offline. That is the fork, and it is why this stops here.

## A separate defect found on the way

Unrelated to the truncation and worth its own ticket: in the code-built tail
and fallback listing, a multi-sentence abstract LOSES ITS CITATION entirely.
Both fragments are stripped and the marker is left orphaned on an empty
trailing "[27]." fragment.

## What closes this

Capture both of these on the next live reproduction, for the affected PMIDs:

- the raw extracted `abstract` value from `ncbi_eutils_actions.py`, before
  anything downstream touches it;
- the model's raw Synth completion, before `run_grounding_pass` runs.

Comparing those two against the rendered text resolves the fork in one run.

A defensive fix is available and was NOT applied, because applying it without
knowing the cause is the thing this investigation set out not to do: there is
no word-boundary safety net anywhere before a listed sentence becomes a
`TokenPayload`. One belongs in `sentence_token` inside `listing()` in
`core/graph.py`, trimming to the last complete word and appending an ellipsis
when a sentence does not end on a word boundary of its finding's own value.
