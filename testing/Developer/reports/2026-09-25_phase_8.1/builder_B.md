# Builder B report, phase 8.1

Worktree branch: `worktree-agent-a59f787bb5867f966`. Note: the shared phase
branch `phase/8.1-good-questions-answer` in the main checkout is at a later
commit (0e273fa) that created `tracker/phase_8.1.md`; this worktree's own
history does not include that commit, so the ticket text was read from the
main checkout's copy of the file directly (not edited).

## Status log

- Started, read tracker/phase_8.1.md (main checkout copy).

## T-8.1-04: "What genes are associated with MODY?" citation check

Cause found. `grounding.py`'s strict cite-or-refuse check
(`run_grounding_pass`) checked a clause against only the FIRST marker's
finding. The Synth model's answer for this question routinely writes one
clause naming TWO facts (a gene's name and the disease it maps to) with
BOTH markers stacked at the clause's end, e.g. "Hepatocyte nuclear factor 4
alpha (NCBIGene:3172) is associated with Maturity-onset diabetes of the
young type 1 [5][6]." The trailing marker's own segment is empty text (the
existing `_asserts_something` guard drops it), so its finding was silently
dropped and the clause was checked ONLY against finding 5's own value
("hepatocyte nuclear factor 4 alpha"). `claim_introduces_no_new_content`
then rejects the disease half of the clause (words like "diabetes",
"young", "type" are not licensed by the gene finding alone), so the clause
fails on every run that uses this shape, `write_node` discards the whole
narrative, and the answer falls back to its code-built "could not be
verified" listing.

Reproduced live with `testing/Developer/reports/2026-09-25_phase_8.1/
diag_mody.py` (full logs: run1.log through run7.log in this folder), which
runs the real loop in-process against this worktree's own `src/` and
monkeypatches `run_grounding_pass` to print the exact narrative and result
of each grounding pass, without touching `core/graph.py`.

Fix (grounding.py only, no weakening): when a clause's own marker is
immediately followed by more markers with nothing asserted in between (the
same adjacency the existing quote-anchored `pairs` mechanism already uses
for a QUOTED trailing marker), the clause is now checked against the UNION
of every finding it actually cites, not just the first. Still exact
containment (`ground_claim_multi`, new function) and the same
content-token allowlist and number check as before, just evaluated over
the combined values, field names, curie and entity types of every stacked
finding. A single-marker clause is byte-for-byte unchanged (verified: the
assembled `supporting_text` for a stack of one matches the old string
exactly). Every claim accepted this way still cites only findings the
model itself marked in that same clause; nothing borrows content from a
finding the model never named there.

Live proof, 6 local live runs of the exact question at researcher depth,
post-fix (`run2.log` through `run7.log`; `run1.log` is the pre-fix baseline
showing the failure, not counted toward the 6):

| Run | Pass 1 (model) | Pass 2 (repair) | Result |
|-----|-----------------|-------------------|--------|
| run2 | claims=0, refused | claims=10, refused=False | answers, model's own prose grounded |
| run3 | claims=12, refused=False | (no repair needed) | answers |
| run4 | claims=0, refused | claims=0, refused | falls back (residual, see below) |
| run5 | claims=0, refused | claims=13, refused=False | answers |
| run6 | claims=12, refused=False | (no repair needed) | answers |
| run7 | claims=12, refused=False | (no repair needed) | answers |

5 of 6 post-fix runs answer with cited genes from the model's own
synthesized prose (not the fallback listing). Meets the ticket's "5 of 6"
bar.

Residual, named rather than hidden: run4's failure is a DIFFERENT, narrower
defect this fix does not close. The model abbreviated the disease name
("MODY type 1" instead of the graph's stored "Maturity-onset diabetes of
the young type 1"), so the disease finding's exact value is not present in
the clause at all, stacked markers or not. That is a genuine paraphrase,
correctly rejected by the exact-match gate; closing it would need either
the model to use the quoted-marker reworded-sentence path (`[N: "..."]`)
for the disease name, or a Synth-prompt change to stop abbreviating,
neither of which is a grounding.py change and both are out of this
builder's fence (the Synth prompt lives in `core/graph.py`, owned by
another builder this phase). Named here as a finding rather than chased,
per the ticket's own "if the cause is upstream, write it down and stop"
instruction; this one is a narrower, correctly-behaving exact-match
rejection, not an upstream defect, so no further action is proposed beyond
naming it.

Unit test added, replaying the captured failing shape:
`tests/system_03_search_agent/synthesis/test_stacked_marker_grounding.py`
(10 tests, all passing): `ground_claim_multi` in isolation, the synthetic
two-fact stacked clause, an adversary check that stacking cannot license
an invented word or number, a regression check that a single bare marker
is untouched, and `test_replays_the_captured_mody_genes_failing_case`
which reconstructs the exact six gene-disease sentences from the live logs
and asserts all 12 claims ground, after first proving the OLD single-
finding check (`claim_introduces_no_new_content` against one finding)
still rejects the first clause on its own.

Files changed: `src/system_03_search_agent/synthesis/grounding.py`
(added `ground_claim_multi`; extended `run_grounding_pass`'s strict path
with `stack_findings` gathering and the union check; extended the claim-
commit step to attach extra stack findings the same way the existing
`synthesized` path already attaches extra quoted findings).

Full suite for this ticket's module: `python3 -m pytest tests/
system_03_search_agent/synthesis -q` -> 461 passed, 10 skipped, 1 xfailed
(pre-existing skips/xfail, unrelated to this change).

STATUS: ticket meets acceptance. Evidence: this section, plus
`testing/Developer/reports/2026-09-25_phase_8.1/run1.log` through
`run7.log`.

## T-8.1-05: the trust line stays the same when the evidence is the same

Read `synthesis/trust.py` in full: `decide()`, `triangulate()`, `aggregate()`
and `trust_for_claims()` are all pure functions of their arguments. No
randomness, no wall-clock read, no model call, and no set or dict whose
ITERATION ORDER can change a result (`buckets = {...}` is used only for
membership and `len()`, `aggregate`'s `min()` picks by severity value, never
position). Confirmed by code reading, not assumed.

Reproduced live with `testing/Developer/reports/2026-09-25_phase_8.1/
diag_trust.py`, which monkeypatches `core.graph.trust_for_claims` (the one
real call site, `core/graph.py` line 10228) to print exactly what it
receives, without editing `core/graph.py`. Two live runs of "What diseases
are caused by variants in the HNF1A gene?" against the SAME develop code:

- `trust_run1.log`: 68 claims reached `trust_for_claims`, all `risk_tier:
  low`, `trust_outcome=answer`.
- `trust_run2.log`: a DIFFERENT claim set reached `trust_for_claims` (fewer
  claims, still all low risk this time), `trust_outcome=ask` (from one of
  `core/graph.py`'s own completeness/cap floors at lines 10245, 10275,
  10327 or 10346, not from a discordant claim).

CAUSE, named precisely: `trust_for_claims` and `aggregate` are deterministic
functions of their input, and their input is NOT stable across runs. The
input is `grounding.claims`, the set of claims the MODEL'S OWN SYNTHESIZED
PROSE happened to ground that run (`core/graph.py` line 10228:
`trust_for_claims(grounding.claims, synth_findings, row_types)`). The
underlying retrieval (`synth_findings`, the 63 Layer 1 rows the 2026-09-23
report calls "byte-identical evidence") is the same every run; WHICH of
those rows the model chose to cite, in which sentences, is not, because
sentence choice is itself a live model call and legitimately varies
run to run. That is a model call whose output legitimately varies, the
ticket's own named exception: I am stopping and reporting options rather
than picking one.

A second, separate mechanism can ALSO move the published `trust_outcome`
without touching `trust.py`: `_apply_conflict_flags_to_claim_trusts`
(`core/graph.py` line 8474) floors a claim's outcome to `flag` when a
Layer 1 and a Layer 2 finding for the SAME fact disagree, and which
Layer 1/Layer 2 PAIRS exist among the grounded claims is, again, a
function of which sentences the model wrote that run. This is the
mechanism that most plausibly explains the 2026-09-23 report's specific
"flag four times, ask once" shape (flag is not otherwise produced by any
of the completeness/cap floors, only by a discordant high-risk claim via
`aggregate()` inside `trust.py`, or by this conflict floor in
`core/graph.py`).

Both of these live entirely in `core/graph.py`, outside this ticket's file
fence (`synthesis/grounding.py`, `synthesis/trust.py`). Nothing in
`trust.py` itself needed changing, and nothing in it was changed for this
ticket; changing it would not fix the instability, since the instability
is upstream of it.

Options for whoever owns `core/graph.py` next (not chosen here, per the
ticket's own instruction to report options rather than pick one when the
cause is a legitimately varying model call):

1. Make the CITED SET deterministic before it reaches `trust_for_claims`,
   the same way retrieval was already made deterministic (UI fix set 10,
   item 10.1's "findings tail"): compute trust over every PREPARED finding
   the answer lists (the tail already renders all of them for Researcher
   depth), not only the subset the model's own prose happened to ground.
   This would make `trust_outcome` a function of retrieval alone, matching
   the product owner's own standard quoted in that item ("a user should
   get exact sources which must be consistent").
2. Accept the variance as inherent to citing model-chosen prose, and
   instead make the DOWNSTREAM floors (the conflict flag and the
   completeness/cap floors) insensitive to which subset was grounded, by
   computing them over `synth_findings` (the full retrieval) rather than
   over `grounding.claims`. Narrower than option 1, and leaves the
   underlying claim-level risk tiering as-is.
3. Do nothing: document that `trust_outcome` is a property of the SHOWN
   answer, not of the underlying evidence, and that the "same evidence,
   same verdict" expectation in the ticket's own title does not hold for
   any answer whose synthesis is model-written. This is the option this
   report does NOT recommend, since the product owner's own rule
   (`decide-from-the-users-chair.md`) treats an inconsistent trust badge on
   an identical question as exactly the kind of thing a reader would feel
   deceived by.

Unit tests added, proving the isolated claim: `tests/
system_03_search_agent/synthesis/test_trust_outcome_determinism.py` (4
tests, all passing). `TestFiveIdenticalRuns` computes `trust_for_claims`
then `aggregate` five times from one fixture (a discordant high-risk claim
plus a low-risk one) and asserts byte-identical output every time, then
asserts the answer floors at `flag` as Section 8.3.4 requires.
`TestSameClaimsIdenticalFindingsGiveSameTriangulation` computes `decide()`
five times on the same claim against the same peer finding (discordant,
floors to flag every time), then shows the ONE thing that legitimately
moves the verdict: removing the peer finding from the input (not
re-running the same input) changes the result to insufficient/ask. This is
the mechanism, made concrete: a different peer set in, a different verdict
out, and that difference is what the live report calls "instability" when
it happens between two runs of the same question rather than between two
deliberately different fixtures.

Files changed for this ticket: none in `src/`. `synthesis/trust.py` was
read in full and is not the cause; no change was made to it, per this
finding. Test file added: `tests/system_03_search_agent/synthesis/
test_trust_outcome_determinism.py`.

STATUS: ticket's own escape hatch applies ("if the cause is a model call
whose output legitimately varies, stop and report the options instead of
choosing one"). Cause named with evidence, unit test proves trust.py's own
logic is deterministic on identical input, three options handed to
whoever owns `core/graph.py` next. No fix landed in this ticket's fence,
because the fix belongs in a file outside it.
