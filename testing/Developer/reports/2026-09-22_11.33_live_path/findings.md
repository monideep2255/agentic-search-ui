# Item 11.33 located: the 500-character cut is `_cap_scalar_string` in the coordinator-worker harness

Investigated 2026-09-22 against develop at `63ec316`. This is outcome (1), an
exact file and line, proven by execution offline. No live call was made, no
instrumented run is needed, and the blocked stop was not taken. No
`instrument.patch` is delivered, because none is needed.

## Table of contents

- [The verdict](#the-verdict)
- [The evidence chain](#the-evidence-chain)
- [Why the cut is exactly 500 and never 2000](#why-the-cut-is-exactly-500-and-never-2000)
- [What the local reconstruction missed](#what-the-local-reconstruction-missed)
- [A second defect found on the way](#a-second-defect-found-on-the-way)
- [What a fix has to touch](#what-a-fix-has-to-touch)
- [The fix, and the byte-ceiling measurement](#the-fix-and-the-byte-ceiling-measurement)

## The verdict

The cut happens at `src/system_03_search_agent/harness/coordinator_worker.py`,
lines 426 to 434:

```python
def _cap_scalar_string(value: str, depth: int) -> tuple[str, bool]:
    max_chars = _MAX_STRUCTURED_STRING_CHARS if depth == 0 else _MAX_STRUCTURED_NESTED_STRING_CHARS
    capped = value[:max_chars]
    return capped, len(value) > max_chars
```

with the constant at line 173:

    _MAX_STRUCTURED_NESTED_STRING_CHARS = 500

It is reached from `_structured_pass_through` (line 594, whose
`_cap_structured_fields` call is line 599), which `_process_one` runs for every
tool result carrying no untrusted free text, which `coordinator_worker_execute`
drives, which `act_node` calls unconditionally at `core/graph.py:5170`.

It is not live-only. It runs identically on a local run. No live-versus-local
divergence was needed to explain the defect, and the reason the earlier local
trace missed it is a skipped stage rather than an environment difference.

## The evidence chain

Step 1, the cut is server side. The `answer_text` in the smoke capture
(`scratchpad/smoke/raw/G-013_run1.json`, develop at `63ec316`) already carries
the fragment "This gene product associates with RNA polymerase II, and through
the C-terminal d [15]." The frontend, the render and the saved-history path are
therefore all downstream of a cut that has already happened.

Step 2, the cut is at offset 500 of the source value. In the real BRCA1 gene
summary, the substring "C-terminal d" ends at index 500 exactly.

Step 3, the tail render does not cut. Driving the real
`build_structured_fallback_narrative` plus `run_grounding_pass` over a
`SynthFinding` carrying the whole 1247-character summary returns all ten
sentences, 1288 characters joined, reporting claims 10 and stripped 0. Nothing
lands mid-word. So `SynthFinding.field_value` was already 500 on the live run.

Step 4, the cut reproduces exactly at the harness. Running the real
`_cap_structured_fields` over the real shape that
`_ncbi_efetch_output_to_structured_fields` produces gives:

| Measurement | Value |
|---|---|
| `rows[0].fields.summary` length before | 811, the fixture's prefix of the real summary |
| Length after | 500 |
| Last 40 characters after | ymerase II, and through the C-terminal d |
| `truncated` flag returned | True |

The rendered fragment and the capped value agree character for character. That
closes the chain.

## Why the cut is exactly 500 and never 2000

`_cap_value` counts `depth` from the `structured_fields` dict itself, which is
depth 0, and recurses with `depth + 1` into every dict value and every list
item. The `ncbi_efetch` pseudo-row shape puts a field value four levels down:

| Depth | Node |
|---|---|
| 0 | the `structured_fields` dict |
| 1 | the `rows` list |
| 2 | one row dict |
| 3 | that row's `fields` dict |
| 4 | the `summary` string |

`_cap_scalar_string` applies the 2000-character cap only at depth 0, and a
string at depth 0 would have to BE the whole `structured_fields` value, which is
always a dict. So every string in every structured tool result is capped at 500.

This is why the symptom looks like a fixed 500 with no exceptions, and why the
fragments observed on 2026-09-21 varied in visible length while the underlying
cut did not: each fragment began at the last sentence boundary inside the
500-character slice, so the fragment's own length says nothing about the cut.

## What the local reconstruction missed

One named stage, not an environment difference.

The 2026-09-21 trace followed `ncbi_eutils_actions.summary` at 1253 characters,
to `_ncbi_efetch_output_to_structured_fields` still at 1253, to the
`SynthFinding` still at 1253, and concluded the value was intact end to end.
Between the second and the third of those sits `act_node`'s single call to
`coordinator_worker_execute`, which is where `structured_fields` is copied onto
a `Finding` through `_cap_structured_fields`. The reconstruction shaped the tool
output and then built findings from it directly, so the capping stage was never
executed and therefore never measured.

Three things made that stage easy to step over, and each would hide the next
defect of the same shape:

- It is a security control, not a rendering step. A search framed as "where does
  the text get shortened for display" does not reach it. Its own docstring
  describes it as the multi-agent pipeline gate's maxLength discipline.
- It lives in `harness/`, while every other suspect lives in `synthesis/`,
  `core/` or `tools/`. The earlier sweep for character caps was scoped by where
  the text is rendered rather than by where the data flows.
- Its constant is not spelled 500 next to anything about summaries or abstracts.
  It is a generic nested-string bound, and the value only becomes a product
  defect because the field it bounds is prose a reader is shown verbatim.

The general form matches `attack-the-constraint`'s own rule, applied one layer
up from where it was applied last time. The assembly step feeding a component is
upstream of it and is therefore the constraint until proven otherwise. The
2026-09-21 round applied that correctly to the model's prompt and then stopped
one stage short of the pipeline that assembles what the prompt is built from.

A second, smaller miss: the cut is not silent at the data layer. It sets
`Finding.truncated` to True. Nothing between that flag and the reader says the
value continues, which is why it reads as a typo rather than as an excerpt.

## A second defect found on the way

Recorded separately rather than folded in, because it is a control gap rather
than a presentation one. `_MAX_STRUCTURED_STRING_CHARS = 2000` at
`coordinator_worker.py:172` is dead. No string ever reaches `_cap_scalar_string`
at depth 0, so the constant has never applied to anything. Verified by
execution: a top-level string value of 3000 characters comes back at 500, not
2000. Its comment and the module docstring both describe a two-tier cap that is
in practice one tier. That is a confident sentence describing a check that is
not there, the same shape build phase 4.15 recorded four times.

## What a fix has to touch

Stated as scope, not as a recommendation, since the fix itself is the product
owner's call.

The bound exists for a real reason and must not simply be removed: it is
defence in depth against a hostile tool payload, per `production-standards.md`'s
bounded-context-items requirement. The question is whether 500 characters is the
right bound for a retrieved prose field the product shows verbatim, given that
the tool layer already caps the same value at 4000
(`ncbi_eutils_actions._cap_text`) and `SynthFinding` caps it at 2000
(`findings.MAX_FIELD_VALUE_CHARS`). Today the tightest of the three is the one
furthest from the schema that documents it, and the only one nothing announces.

Whatever value is chosen, a cut that still happens should not land mid-word.
`answer_layout.clip_to_word` already exists and is the natural helper, and it is
what makes a cut legible to a reader rather than looking like a typo.

Five existing arms assert the current bound as an upper limit and go red if it
is raised:

| File | Line | Arm |
|---|---|---|
| `tests/system_03_search_agent/harness/test_coordinator_worker.py` | 438 | nested dict values at or under 500 |
| same file | 526 | a description field at or under 500 |
| same file | 546 | leaf string, commented "nested string cap" |
| same file | 567 | every item of an inner list at or under 500 |
| same file | 585 | a three-level nested inner string |

The byte-ceiling fixtures at lines 633 to 680 build their payload from
500-character values deliberately, and would need re-measuring if the per-string
cap moved, since the ceiling search is what those arms actually test.

## The fix, and the byte-ceiling measurement

Implemented 2026-09-22, after the verdict above was independently reproduced
from the main session.

What changed, in `src/system_03_search_agent/harness/coordinator_worker.py`:

- The two-tier string cap is DELETED, not repaired. One constant,
  `_MAX_STRUCTURED_STRING_CHARS`, applies at every depth. The dead depth-0
  tier is gone rather than made reachable, because a tier that never fires is
  a confident sentence describing a check that is not there.
- The value is 2000, the bound `SynthFinding.field_value` already enforces at
  `synthesis/findings.py` line 91, applied at line 643. The cap here can no
  longer undercut the finding's own bound, and it stays under the tool layer's
  4000 so it remains real defence in depth.
- It is written as a literal, not imported. `synthesis/findings.py` line 81
  imports `Finding` from `coordinator_worker`, so the dependency runs
  synthesis to harness and an import back would be circular.
- A cut now lands on a word boundary and appends one ellipsis, matching
  `answer_layout.clip_to_word`'s convention. A value with no whitespace at or
  before the cap is cut hard at the cap with no ellipsis, since appending one
  would push the result past the cap. `truncated` is True exactly when a cut
  happened.

The double-ellipsis question, checked rather than argued: it cannot occur.
When `clip_to_word` cuts a value that already ends in an ellipsis, it cuts
strictly before that character and discards it; when it does not cut, it
returns the value unchanged with the one ellipsis it had. Verified at four
limits, including at and above the value's own length, and pinned by an arm.

### The byte ceiling was measured and deliberately not changed

`_MAX_FINDING_TOTAL_BYTES` is 50,000. Quadrupling a per-field cap moves what
that ceiling binds, so it was measured against the largest realistic tool
shape: a `fetch` of 20 PubMed records, each carrying a 2000-character abstract
plus title, journal and author fields, in the shape
`_ncbi_efetch_output_to_structured_fields` produces.

| Rows | Serialized bytes after capping | Rows surviving |
|---|---|---|
| 20 | 45,841 | 20 of 20 |
| 21 | 48,129 | 21 of 21 |
| 22 or more | 48,129 | 21 |

The ceiling does NOT fire on the realistic shape. All 20 rows survive with
roughly 4,200 bytes of headroom, and the ceiling still bites past 21 rows, so
it has not become a no-op. The value is unchanged: whether 50,000 is right now
that one field may carry 2000 characters is a product decision, not one to
take inside a defect fix.

Two figures in the existing byte-ceiling fixtures were re-measured and their
comments corrected. One docstring claimed 118 surviving rows where the shipped
code keeps 3; that number is not reproducible against the fixture today. Its
assertion had always been a range rather than that number, so the arm was
measuring the right property while the prose beside it named a stale one, and
only the prose changed.
