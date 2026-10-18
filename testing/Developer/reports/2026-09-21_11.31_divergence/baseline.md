# Answer-mode divergence baseline, 2026-09-21

Table of contents
- [Why this exists](#why-this-exists)
- [How this was measured](#how-this-was-measured)
- [Results](#results)
- [How much of the page is identical](#how-much-of-the-page-is-identical)
- [What this baseline does and does not show](#what-this-baseline-does-and-does-not-show)

## Why this exists

A product decision requires `plain_language` and `researcher` answer depths to
diverge. Today they read alike. This file records the CURRENT state, measured
against the live develop API, before any fix is written, so a later fix can be
proven against this number rather than asserted against a feeling.

Commit live on develop at capture time: `46fff40961ed392dbb2eb0847a77b78bc9fddab8`
(2026-09-20 23:33:55 -0400, `docs: the late checkpoint, and what two green
gates failed to catch`). The deployed Railway build may lag this commit; this
report does not confirm the two are the same build, only that this was the
commit at the head of `develop` when the queries below were run.

## How this was measured

Instrument: `fetch_runs.py` in this folder, adapted from the working,
read-only instrument at
`testing/Developer/reports/2026-09-19_verification/fetch_answer_text.py`. Same
base URL (`https://search-agent-api-develop-43b3.up.railway.app`), same guest
auth flow (`POST /auth/guest`), same SSE token-stream reassembly
(`GET /v1/query/{run_id}/events`). The depth field sent on the request is
`audience_depth`, confirmed against `frontend/src/lib/api.ts` line 21 (`export
type AudienceDepth = "plain_language" | "researcher" | ...`) and line 26,
rather than assumed.

Four live runs, three seconds apart, one guest session per run:

| Question | Depth |
|----------|-------|
| Which diseases are associated with BRCA1? | plain_language |
| Which diseases are associated with BRCA1? | researcher |
| What diseases are caused by variants in the HNF1A gene? | plain_language |
| What diseases are caused by variants in the HNF1A gene? | researcher |

Raw captures: `raw/brca1_plain_language.json`, `raw/brca1_researcher.json`,
`raw/hnf1a_plain_language.json`, `raw/hnf1a_researcher.json`. Each holds the
question, the depth sent, the server's `trust_outcome`, the run id, and the
full reassembled `answer_text`.

All four runs returned `trust_outcome: ask`. The rendered answer in all four
is the harness's degraded fallback shape: a one-to-two sentence summary
followed by a section-by-section dump of every retrieved record (`Disease
records found`, `Gene records found`, `Clinvar records found`, and so on),
each with one line per record and a trailing `Note:` explaining that "the
written summary of these records could not be verified against them, so this
answer lists the records found instead." This is stated here because it
bears directly on the divergence measurement: what is being compared below is
two depths of this fallback mode, not two depths of the system's normal
synthesized prose.

Counts were computed, not eyeballed, by `capture.py` in this folder:

```
python3 capture.py
```

`capture.py` splits each `answer_text` on blank lines into blocks. A block
matching `<Label> records found` or equal to `Variant-to-disease mapping` is a
section header; the block immediately following a header is that section's
one dump of record rows (verified true for every header in all four
captures: never two headers in a row, never a dump with no header). A record
row is counted as one `[n]` citation bracket inside a dump block, since every
rendered row in this format ends with exactly one bracket. Every other block,
the opening summary sentence(s), the `Note:` lines, the placeholder-condition
sentence, and the closing disclaimer, counts as prose. Prose word count
strips `[n]` brackets before splitting on whitespace, so a citation marker is
never counted as a word. Full method and the block-by-block classification
are in `capture.py`'s module docstring.

## Results

| File | Depth | Prose words | Paragraphs | Record rows | Prose words / record row |
|------|-------|-------------|------------|--------------|---------------------------|
| `raw/brca1_plain_language.json` | plain_language | 89 | 4 | 66 | 1.3485 |
| `raw/brca1_researcher.json` | researcher | 164 | 4 | 66 | 2.4848 |
| `raw/hnf1a_plain_language.json` | plain_language | 135 | 6 | 92 | 1.4674 |
| `raw/hnf1a_researcher.json` | researcher | 127 | 5 | 91 | 1.3956 |

Full numbers, including run ids and character counts, are in `counts.json`.

## How much of the page is identical

BRCA1 (Which diseases are associated with BRCA1?):
- Record rows: 66 at plain_language, 66 at researcher. Identical count, and
  a line-by-line diff of the two dump sections shows the same 66 rows in the
  same order with the same content: the record dump does not vary by depth
  for this question.
- Prose: 89 words at plain_language versus 164 words at researcher, a word-
  level diff (`difflib.SequenceMatcher` over the prose word lists) puts
  roughly 98 of the words as inserted, deleted, or replaced between the two,
  similarity ratio 0.59. The researcher answer's summary sentence is longer
  and phrased differently ("Found 4 disease records for BRCA1 and diseases:
  ..." is absent from plain_language, which instead opens "Found 4 disease
  records for BRCA1: ..."), and researcher repeats the "BRCA1 is associated
  with four diseases" sentence with the gene symbol clause plain_language
  does not carry. This is the one place in the four captures where the two
  depths read as meaningfully different prose.

HNF1A (What diseases are caused by variants in the HNF1A gene?):
- Record rows: 92 at plain_language, 91 at researcher. NOT identical, but
  the difference is not depth-driven: the two dump sections are byte-
  identical except for one PubMed id (`36257325` shifts from the third slot
  to the second, and a different id, `35619319`, appears in the researcher
  capture) and one `Note:` count ("6 further pubmed records" versus "7
  further pubmed records"). Both runs hit the live NCBI PubMed endpoint
  independently, three seconds apart in the same batch; this reads as
  ordinary result-set drift between two separate live calls, not a
  depth-conditioned difference in what the record dump contains.
- Prose: 135 words at plain_language versus 127 words at researcher, a
  word-level diff shows only about 9 words differing, similarity ratio
  0.96. The near-complete overlap is not because the two prose sections are
  the same length by coincidence: the researcher capture is missing the
  closing sentence entirely, "This is a research summary, not medical
  advice.", which is present in the plain_language capture (visible as
  block 23 of 24 in plain_language versus 23 of 23 in researcher; see the
  block-by-block diff run during this measurement). Otherwise the two
  prose sections are word-for-word identical, including the opening summary
  sentence.

Summary: across the two questions, one (HNF1A) shows the two depths reading
almost identically, with the sole prose difference being a dropped closing
sentence at researcher depth and record rows that diverge only by ordinary
live-API drift, not by depth. The other (BRCA1) shows a real, measurable
prose difference between depths (98 of roughly 165 words differ), while the
record dump itself, which makes up the bulk of both pages (66 of the roughly
253 to 313 total prose+dump tokens), is byte-identical at both depths. In
neither case does the record dump vary by depth in a way traceable to the
depth parameter itself.

## What this baseline does and does not show

This baseline measures four runs of a fallback answer shape (`trust_outcome:
ask`), not the system's normal synthesized-prose answer path. All four runs
this session landed in that fallback, so no capture of the two depths in
normal synthesis mode exists in this file. Whether the two depths diverge
more, less, or differently once synthesis (rather than the record-dump
fallback) is producing the answer is not established here and would need a
separate capture. The instructions for this task named this exact question
pair as the repository's own recurring probes, and both landed in fallback
on every one of the four attempts, so this is reported as the honest result
rather than retried past the twelve-query budget this task was scoped to.
