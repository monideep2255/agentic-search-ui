# Item 12.9, the two answer depths return the same text

VERDICT: BLOCKED-STOP, NOTHING BUILT. Item 11.31 is BYPASSED, not broken. The
depth directive is assembled, differs by depth and reaches the model; the model
writes different prose at each depth; the grounding gate then deletes that prose,
often all of it, and what ships is the code-built summary sentence plus the
code-built record listing, neither of which takes an `audience_depth` argument by
deliberate design. Fixing this means changing what the grounding gate accepts or
what the code-built half does, which is the product owner's call, so this worker
stopped at the named blocked-stop rather than building a second answer writer.

## Table of contents

- [What a person typing the question sees today](#what-a-person-typing-the-question-sees-today)
- [The fresh measurement, on today's HEAD](#the-fresh-measurement-on-todays-head)
- [The layer that drops the depth, named by execution](#the-layer-that-drops-the-depth-named-by-execution)
- [Broken or bypassed](#broken-or-bypassed)
- [A second mechanism, and it points the wrong way](#a-second-mechanism-and-it-points-the-wrong-way)
- [Why this worker stopped](#why-this-worker-stopped)
- [What a fix would have to change, for whoever decides](#what-a-fix-would-have-to-change-for-whoever-decides)
- [Incidental observations, not this ticket](#incidental-observations-not-this-ticket)
- [Gates](#gates)
- [Evidence files](#evidence-files)

## What a person typing the question sees today

Ask `reflux disease` as a plain-language reader and as a researcher and you get
the same page. Not similar: the same, word for word, apart from one extra line at
the bottom of the plain-language version reading "This is a research summary, not
medical advice." Both pages open with one code-written sentence, "Found 8 disease
records for reflux disease", and then list the records. Nobody explains anything
to the plain-language reader, and nobody gives the researcher any specifics they
could not have read off the list themselves.

## The fresh measurement, on today's HEAD

Re-measured 2026-09-23 on `29c8687`, all seven questions at both depths, one at a
time. The table in the fix plan was taken before that commit and is superseded by
this one. `same?` compares the two RENDERED ANSWERS byte for byte, which the word
count could not do.

| key | question | plain words | researcher words | same? | sources pl / r |
|---|---|---|---|---|---|
| q1 | reflux disease | 142 | 142 | identical but for the medical-advice note | 20 / 20 |
| q2 | GERD | 148 | 108 | differs | 12 / 12 |
| q3 | Any trials for GERD? | 152 | 152 | identical but for the medical-advice note | 12 / 12 |
| q4 | papers on the effects of caffeine on exercise performance | 193 | 113 | differs | 5 / 5 |
| q5 | Does coffee help make exercise more effective? | 101 | 101 | identical but for two notes | 5 / 5 |
| q6 | Are there any beneficial variants typically found in people of mediterranean descent? | 129 | 125 | differs | 5 / 5 |
| q7 | What positive and negative genes do ashkenazi jewish people have? | 163 | 135 | differs | 5 / 5 |

WHAT MOVED SINCE THE STALE TABLE. The coffee question fell from 932 words to 101
at both depths, so `29c8687` did what it said. The defect did NOT move: three of
seven questions still return the same answer at both depths, and it is now
established as a byte comparison rather than as a word count. q7 answered at both
depths this time, so the plain-language think-schema failure recorded in the
brief did not reproduce.

The extra column the word count could not show, and the one that explains
everything: whether the run fell back to the code-built narrative because nothing
the model wrote survived the grounding gate.

| key | plain: structured fallback | researcher: structured fallback |
|---|---|---|
| q1 | YES | YES |
| q2 | no | no |
| q3 | YES | YES |
| q4 | no | YES |
| q5 | YES | no |
| q6 | no | no |
| q7 | no | no |

Every question where BOTH depths fell back (q1, q3) returned the same answer.
q5 returned the same answer with only one depth falling back, for the separate
reason in the section below. No question where neither fell back was identical.
The correlation is exact across fourteen runs.

## The layer that drops the depth, named by execution

Traced by running `reflux disease` at both depths with `build_synth_messages` and
every `run_grounding_pass` call wrapped, printing what each received and emitted.
Script and captures: `probe_depth_stages.py` and `probe_depth_stages/`.

plain_language:

| stage | in | out |
|---|---|---|
| `build_synth_messages` | depth `plain_language` | user prompt sha `6cad05decad3`, 2651 chars |
| `run_grounding_pass` (model prose) | sha `c98dffb14eb8`, 1507 chars | 8 claims, 8 stripped |
| `run_grounding_pass` | sha `af3d9c26b62b`, 679 chars | 9 claims |
| `build_synth_messages` (repair) | depth `plain_language` | sha `244ebc623ef9`, 3829 chars |
| `run_grounding_pass` (repaired prose) | sha `fbbe67f08ce1`, 2029 chars | 0 claims, 9 stripped, REFUSED |
| `run_grounding_pass` (code-built) | sha `9fc9180782ab`, 1469 chars | 20 claims, out sha `0e702bceb9da` |

researcher:

| stage | in | out |
|---|---|---|
| `build_synth_messages` | depth `researcher` | user prompt sha `fa96cdae3840`, 2537 chars |
| `run_grounding_pass` (model prose) | sha `d0093c355a04`, 1657 chars | 0 claims, 21 stripped, REFUSED |
| `build_synth_messages` (repair) | depth `researcher` | sha `a70dbab9fdb3`, 4107 chars |
| `run_grounding_pass` (repaired prose) | sha `baef0e5f702b`, 1578 chars | 0 claims, 11 stripped, REFUSED |
| `run_grounding_pass` (code-built) | sha `9fc9180782ab`, 1469 chars | 20 claims, out sha `0e702bceb9da` |

READ THE LAST ROW OF EACH TABLE. The final grounding pass receives the SAME BYTES
at both depths, `9fc9180782ab`, and returns the same 20 claims with the same
output, `0e702bceb9da`. Every earlier stage differs. That last row is the first
and only stage whose output does not change when the input depth changes, and it
is the stage that produces the answer the reader actually gets.

What that input is: `build_structured_fallback_narrative(tail_findings)` in
`core/graph.py`. Three producers build the shipped answer and none of them takes
a depth:

- `synthesis/findings.py:1006` `build_structured_fallback_narrative(synth_findings)`
- `synthesis/answer_layout.py:602` `answer_summary_sentence(answer_findings, display_slots, entity_label, total_available, row_for, condition_names)`
- `core/graph.py:9834` `tail_is_listing = True`, unconditional, with `tail_findings = synth_findings`

That is not an oversight. `core/graph.py:9828` records the product owner's
direction of 2026-09-14, "the beautiful format of the answer should be
irrespective of the plain language or researcher mode", and
`synthesis/findings.py:451` records that an arm fails loudly if anyone gives
`build_synth_findings` a depth argument, because Section 14.1's firewall forbids
depth from changing which findings are covered.

The depth-dependent half of the answer is the MODEL'S PROSE and nothing else.

## Broken or bypassed

BYPASSED. Three facts settle it, all by execution rather than by reading:

- The directive is assembled and differs. Plain language's user prompt is 2651
  chars and researcher's is 2537, with different digests, and each opens with its
  own `AUDIENCE DEPTH:` line.
- It reaches the model, on both the first call and the repair call.
- The model writes different prose at each depth: 1507 chars at plain language
  against 1657 at researcher, different digests.

The grounding gate then deletes it. On this run the researcher depth lost 21 of
21 sentences on the first pass and 11 of 11 on the repair, and plain language lost
9 of 9 on the repair. `grounding.ground_claim` accepts a claim only on contiguous
containment, which detail 11.31 already records: against long source text the gate
permits quoting and forbids explaining.

So item 11.31 did not regress and its version-5 directive is not at fault. The
depth never gets a chance to matter, because the only half of the answer that
carries depth is the half most likely to be deleted.

## A second mechanism, and it points the wrong way

Separate from the fallback, and it explains q5 and the shape of every researcher
answer measured today.

`core/graph.py:9851` to `9856` runs `drop_record_restatements` at RESEARCHER DEPTH ONLY. A
grounded researcher sentence that merely restates one record is dropped whole,
because the code-built list below carries every record anyway. Plain language
keeps those sentences.

Measured effect on today's runs: at researcher depth, six of the seven answers
contain no model prose at all. Everything before the first code-built heading is
the single code-written summary sentence. q6, q7 and q2 at researcher depth all
open with "Found 5 pubmed records: ..." and then go straight to the list. At plain
language, q6 carries three model sentences, q7 two and q2 two.

So on the questions that DO differ, plain language is longer than researcher. That
happens to be the direction item 11.31 asked for, and it is reached by the wrong
route: not because plain language explains more, but because researcher's prose is
deleted by a rule written for a different purpose. A researcher today gets strictly
less than a plain-language reader, which is the opposite of "researcher means
tables, specifics and depth".

## Why this worker stopped

The brief's blocked-stop: "IF THE CAUSE IS THAT THE CODE-BUILT LISTING IS CARRYING
THE ANSWER, STOP AND REPORT: that is a much larger change, it touches the
grounding gate, and it is the product owner's decision." That is exactly the cause,
established on fourteen live runs plus a stage trace, so this worker built nothing
and changed no source file.

The only edits made are three files under
`testing/Developer/reports/2026-09-23_set12/`: this report, `rerun_both_depths.py`
and `probe_depth_stages.py`, plus their captured output directories. No file under
`src/` or `tests/` was touched, and nothing belonging to item 12.8's worker was
read into or written from this work.

## What a fix would have to change, for whoever decides

Stated as options, not as a recommendation, since the choice is the product
owner's. None of them is small.

1. Let the code-built half read the depth. Today it is forbidden to, and the
   prohibition exists because a depth that changes which findings are covered has
   already shipped an answer reporting three of four pinned diseases while looking
   complete (`_DEPTH_DIRECTIVES` version 2). A depth-aware PRESENTATION of the same
   finding set would not breach that firewall, but the firewall as written and as
   tested does not distinguish the two.
2. Change what the grounding gate accepts, so a faithful plain-language
   explanation survives. Detail 11.31 already measured and rejected the obvious
   version of this: dropping contiguity and leaning on the content-token allowlist
   alone let three of four reorderings of an abstract's own words ship with the
   meaning wrong.
3. Keep changing the INPUT, which is the one route that has worked here before.
   Version 5 of the plain-language directive succeeded by retrieving NCBI's own
   plain-English gene summary so the model could explain by quoting prose that is
   already plain. Six of today's seven questions resolve to PubMed records with no
   equivalent plain-English field, so the same trick has nothing to reach for.
4. Reconsider `drop_record_restatements` firing at researcher depth only. On
   today's evidence it removes the researcher's entire narrative on six of seven
   questions.

## Incidental observations, not this ticket

- The think-classification schema failure named in the brief appeared ONCE more,
  on `Any trials for GERD?` at plain language, and RETRIED SUCCESSFULLY on attempt
  2 of 2. It did not reproduce on q7, which failed on it in the stale run. So it
  is intermittent and self-healing on retry, and it costs a whole extra plan-tier
  call when it fires. Recorded as asked; not chased.
- The q7 plain-language answer ships a sentence reading `P = 0.0083]" [1].` as its
  own claim. It is grounded, it is cited, and it is meaningless to a reader. That
  is a quoted fragment surviving the gate because it is a literal excerpt.
- No question lost a source between the two depths, in any of the seven pairs.
  Citation counts are identical across depths on all seven.

## Gates

`ruff check .`, no path, the whole repository: CLEAN, `All checks passed!`. It was
not clean on the first run: `rerun_both_depths.py` had its imports out of order,
which is `isort`'s rule and ruff's `I001`. Fixed in that file, then re-run clean.

`bash .github/gates/gate04_unit_suite.sh`: `1 failed, 5661 passed, 155 skipped,
23 deselected, 1 xfailed in 282.11s`.

THE ONE FAILURE IS NOT THIS WORKER'S AND IS REPORTED RATHER THAN ROUNDED OFF.
`tests/system_03_search_agent/core/test_write_answer_structure.py:344`,
`test_the_done_event_carries_one_trust_line`, fails on
`'Based on 3 sources'.startswith('Based on 1 source')`. That is the trust line's
source count, item 12.8, and the working tree at the time of the run carried
uncommitted edits to `src/system_03_search_agent/synthesis/trust.py` (46 lines
changed) and to that very test file (7 lines changed), neither of them made here.
This worker changed no file under `src/` or `tests/` at all. The failure belongs
to the concurrent 12.8 worker's in-flight state, so it is named here and left
alone rather than touched, per the brief's instruction not to edit the trust
line's counting or wording.

## Evidence files

- `both_depths_rerun/` : fourteen runs on `29c8687`, one JSON per question and
  depth, each carrying the rendered answer text as well as the counts.
- `both_depths_rerun/all.jsonl` : the same fourteen in one file.
- `rerun_both_depths.py` : the re-measure runner. Writes to a new directory so the
  original `both_depths/` evidence is untouched.
- `probe_depth_stages.py` and `probe_depth_stages/` : the stage trace. Note in the
  script's docstring why the async dispatcher is NOT wrapped: doing so crashed the
  run before any tool call, and the model's narrative is recoverable anyway as the
  first `run_grounding_pass` input.
