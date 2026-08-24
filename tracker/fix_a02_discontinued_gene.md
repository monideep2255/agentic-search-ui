# Fix: F-4.7-A-02, a discontinued gene record answered as its successor

Dedicated fix, not a numbered build phase, per `tracker/BOARD.md`'s dated entry: a branch with a trigger, opening the moment build phase 4.7 merges. That merge happened 2026-08-23 as PR #56, so the trigger has fired. Follows the F-2.1-C15 precedent (`tracker/fix_c15_generation_bound.md`), a critical given its own branch rather than parked in a later phase, deliberately, because F-2.0-15 survived twelve phases with an owner field reading "unassigned".

Depends on: build phase 4.7 (done, merged as PR #56)
Branch: `fix/a02-discontinued-gene-record`
Source finding: `tracker/phase_4.7_adversary_report.md`, F-4.7-A-02, and `tracker/BOARD.md`'s Open flags row
Blocks: build phase 4.12, the demo deployment. A hard blocker before any public URL exists, together with F-4.7-A-01

## Table of contents

- [The done-when](#the-done-when)
- [The product decision](#the-product-decision)
- [A wrong premise in the ticket, corrected before any code was written](#a-wrong-premise-in-the-ticket-corrected-before-any-code-was-written)
- [The field types are inconsistent, and that is the trap](#the-field-types-are-inconsistent-and-that-is-the-trap)
- [What the live end-to-end run caught that the gate could not](#what-the-live-end-to-end-run-caught-that-the-gate-could-not)
- [What this fix does and does not claim](#what-this-fix-does-and-does-not-claim)
- [Acceptance criteria](#acceptance-criteria)
- [Evidence](#evidence)
- [History](#history)

## The done-when

A gene symbol that resolves to a discontinued NCBI gene record contributes no CURIE, so no answer about a substituted gene is reachable, and the refusal the user receives names the withdrawn record and its replacement. A live gene symbol still resolves and still answers.

Verify surface: `tests/system_03_search_agent/core/test_discontinued_gene_premise.py` (12 arms, live against NCBI), `tests/system_03_search_agent/core/test_discontinued_gene_mutation.py` (15 mutations, offline, one per control), a full-suite run against a baseline re-measured at the branch point, and a hand-run of the real question through `core.run.run()`.

## The product decision

Product owner, 2026-08-24: REFUSE, NAMING THE SUCCESSOR.

Two alternatives were put and rejected, recorded because the shape of the gate is otherwise arbitrary:

- Refuse silently: the resolver returns `None` and the existing "I could not identify that gene" fires unchanged. Smallest diff, no new plumbing. Rejected because it discards a successor id already in hand, and because the user cannot then tell a typo from a retired symbol.
- Answer about the successor with a disclosure: keep resolving to `NCBIGene:675` and force a substitution sentence into the answer. Rejected because it leaves the substitution in place, which is what the critical is about, and because the disclosure would depend on a Synth model actually emitting a sentence.

## A wrong premise in the ticket, corrected before any code was written

`tracker/BOARD.md` and the adversary report both state the fix is single-site, because "`status` and `currentid` are already inside the ESummary response the resolver retrieves and it reads only `name`".

That is true of the raw HTTP body and false of what the resolver can see. The `summary` action allowlists per-database field sets (`ncbi_eutils_actions._SUMMARY_FIELDS_BY_DB`), and the `gene` row named seven fields, none of them `status` or `currentid`. Measured against the live tool on 2026-08-24, before any change:

```
FIELDS THE RESOLVER CAN SEE:
  ['chromosome','description','genomicinfo','maplocation','mim','name','organism']
  name = 'BRCA3'   status = None   currentid = None
```

A fix that read `fields.get("status")` without widening that allowlist would have read `None` for every gene, live or withdrawn, refused nothing, and looked exactly like a working fix. This is the `goal-contracts` rule's own case: the premise is part of the verify surface, and a gate written on the ticket's stated premise would have been green and inert. P1 grades the allowlist directly, upstream of any resolver behaviour, so that specific failure cannot ship.

Widening the allowlist was checked for blast radius rather than assumed safe. `action="summary"` with `db="gene"` has exactly one production caller in the repository, this resolver (`core/graph.py`). `act_node`'s answer-bearing Layer 2 call uses `dataset_report`, a different action, so no citation a user ever sees is built from either field. Both are small scalars and pass through `_cap_value` like every other allowlisted field.

The `gene` row is now a stated deviation from Section 6.2's table, commented as such in place, rather than a silent edit to a row whose neighbours are all verbatim.

## The field types are inconsistent, and that is the trap

Probed live, 2026-08-24, three records:

| uid | symbol | state | `status` | `currentid` |
|-----|--------|-------|----------|-------------|
| 7157 | TP53 | live | `''` (str) | `''` (str) |
| 60500 | BRCA3 | withdrawn | `1` (int) | `675` (int) |
| 353129 | ADHD | withdrawn | `1` (int) | `1816` (int) |

A live record's `status` is the empty string. A withdrawn record's is the integer 1. The adversary report transcribed the same field as the string `'1'`, a third shape again.

So `status == 1` is correct against the live API and inert against the report's transcription, and `status == "1"` is inert against the live API. Inert here means the withdrawn record resolves and the confidently wrong answer ships. Every comparison is normalized through `str()`, and three mutations (M4a, M4b, M4c) feed all three shapes and require each to be classified correctly.

M4c is the one worth naming: a presence check (`if fields.get("status") is not None`) classifies every live gene as withdrawn, because a live record carries `status` as the empty string rather than omitting it. That mutation refuses the entire product, and it is caught.

A withdrawn record with no replacement is handled separately: `currentid` is `0` in the integer shape and `''` in the string shape, and both must yield "no replacement" rather than a fabricated `NCBIGene:0`. P7 and M7a/M7b grade it.

## What the live end-to-end run caught that the gate could not

Every arm was green, the mutation harness was green, and the fix was still incomplete.

The refusal reaches the user through two channels: `write_node` emits it as `token` events and as `TrustSignalPayload.message`, which is what a surface rendering the structured event shows instead of the stream. The first version of this fix rebuilt the token text and left the event pointed at the bare `_UNRESOLVED_ENTITY_REFUSAL_MESSAGE` constant. A live run produced:

```
[trust_signal] "I could not identify that gene. NCBI has no record matching
                the name in your question, so no graph query was attempted."
ANSWER TEXT    "BRCA3 is a discontinued NCBI gene record (NCBIGene:60500),
                replaced by NCBIGene:675. ..."
```

Two channels describing the same refusal, disagreeing on whether NCBI holds a record. That is worse than either being wrong alone, because whichever the consumer trusts is a coin flip.

P6 could not have caught it: P6 grades `_build_unresolved_entity_refusal_text`, and the defect was in a call site that never went through that function. Both channels are now built from one function, `_unresolved_entity_refusal_message`, and P8 and M8 grade it.

The transferable point is the same one build phase 4.8 recorded when two major layout defects survived 147 unit tests, a clean production build and a full WCAG pass: until a check exists that exercises the real path, running the thing and looking at the output is a real step, not a nicety.

## What this fix does and does not claim

Claims:

- A discontinued gene record contributes no CURIE, on the ESearch/ESummary leg, which is the only leg that can reach one.
- The refusal names the withdrawn record and its replacement, through both channels the user can receive it on.
- A live gene symbol is unaffected, proven by a control in the same run rather than argued.

Does not claim:

- That the Datasets leg is covered. It is not, because it cannot reach the defect: `gene/symbol/BRCA3/taxon/human` and `gene/symbol/ADHD/taxon/human` each return zero reports (probed live 2026-08-24), so a withdrawn symbol always falls through to ESearch. If Datasets ever starts returning withdrawn records, this gate will not notice. Stated as a known gap, not an oversight.
- That every withdrawn gene in NCBI is enumerated. Two are pinned, deliberately unrelated to each other.
- That the full loop is asserted against a real Synth model in CI. The end-to-end run is by hand, transcribed below; what is automated stops at the refusal text. That gap is not theoretical, and it is exactly what P8 exists because of.

## Acceptance criteria

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `status` and `currentid` survive the `summary` action for `db="gene"` | Met, P1, live |
| 2 | A withdrawn symbol contributes no CURIE, with a live control in the same run | Met, P2, live |
| 3 | The withdrawal is recorded with its successor, not merely dropped | Met, P3, live |
| 4 | `status` is read by value across all three real shapes | Met, P4, 5 cases |
| 5 | A second, unrelated withdrawn symbol behaves the same | Met, P5, live |
| 6 | The refusal text names the successor and is not phrased as an answer | Met, P6 |
| 7 | A withdrawal with no successor refuses without fabricating an id | Met, P7 |
| 8 | Both user-facing channels state the same fact | Met, P8 |
| 9 | Every arm proven capable of failing | Met, 15 mutations |
| 10 | No regression against a baseline re-measured at the branch point | Met |
| 11 | A live gene still resolves and still answers, end to end | Met |

## Evidence

Premise gate, live, `RUN_PREMISE_GATE=1`:

```
12 passed
```

None skipped, none open.

Mutation harness, offline:

```
15 passed
```

Every control broken in process, every corresponding arm proven to go red. Three of the fifteen did not reproduce on first run and each was a real defect in the harness rather than in the code, recorded rather than quietly fixed:

- The stub read `payload.action` on a `RootModel`, so three mutations raised `AttributeError` instead of exercising the arm. pytest reports that as "DID NOT RAISE", which reads exactly like a control that failed to break.
- The stub omitted `record_count` and `truncated`, both required with no default, so the same three raised `ValidationError` for the same misleading reason.
- M7a's "broken" version was written as `str(fields.get("currentid") or "")`, which already maps the integer `0` to `""` because `0` is falsy. A mutation that does not mutate is the same class of defect as an arm that cannot fail.

Suite, re-measured at the branch point rather than carried forward, in a throwaway worktree at `4d759da`:

| | Failed | Passed | Skipped | xfailed |
|--|--------|--------|---------|---------|
| Baseline, `develop` at `4d759da` | 6 | 3826 | 146 | 1 |
| This branch | 6 | 3849 | 150 | 1 |

The same six failures, all `LiveHttpCallInUnitSuiteError` in `test_citation_trust_full_premise.py`, which are blocked live Layer 2 and Layer 3 calls in the ordinary unit run. The delta of +23 passed and +4 skipped reconciles exactly with the 27 tests added.

Worth recording: `requirements/phase_6/Continuation_prompt.md` carried the baseline as 3813 passed, and the true figure at that commit is 3826. The recorded number was already 13 stale, which is the precise failure the repository's own "re-measure, never carry forward" rule exists to stop.

`ruff`: clean on all four changed files.

End to end, live, the defect question:

```
[think] resolved_entities: []
[plan]  no tool selected; unresolved gene symbol candidate(s): BRCA3
[trust_signal] outcome refuse, risk_tier unknown, grounded false, citation_id null
ANSWER TEXT >>>
I did not answer this question. BRCA3 is a discontinued NCBI gene record
(NCBIGene:60500), replaced by NCBIGene:675. No graph query was attempted, and
I have not substituted the replacement record for what you asked about. Re-ask
naming the replacement if that is what you want.
https://www.ncbi.nlm.nih.gov/search/all/?term=BRCA3
```

End to end, live, the control, because a fix that refuses everything passes every arm above:

```
[think] resolved_entities: [{"text":"BRCA1","curie":"NCBIGene:672","confidence":1.0}]
[plan]  selected cypher_query for a Layer 1 graph lookup and ncbi_efetch for a
        Layer 2 confirmation of NCBIGene:672
[done]  total_tool_calls 2, trust_outcome ask
```

Real citations, grounded claims, unchanged behaviour.

## History

- 2026-08-24: Branch opened. Preflight reported the graph down; diagnosed rather than escalated, and it was a cold-start false alarm, three consecutive probes returning HTTP 200 in roughly 350ms. The 4.11 process failure (a wrong blocker reported for a firewall that does not exist) is why this was checked before reporting anything.
- 2026-08-24: Ticket premise checked against the live tool before writing code, and found wrong. The fix is two-site, not one.
- 2026-08-24: Product-owner decision taken on refuse-versus-disclose before the gate was written, since the gate encodes it.
- 2026-08-24: Premise gate written first and watched fail, 11 arms, all red for the right reason.
- 2026-08-24: Implemented. Gate green 11 of 11 live.
- 2026-08-24: Mutation harness written. Three of its own mutations found not to mutate, all three fixed and recorded above.
- 2026-08-24: Live end-to-end run found the `trust_signal` channel still carrying the old message. P8 and M8 added; the gate is 12 arms and the harness 15.
- 2026-08-24: Committed as `012bba8`.
