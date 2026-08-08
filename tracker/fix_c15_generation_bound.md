# Fix: F-2.1-C15 generation bound, and F-2.2-01

Dedicated fix, not a numbered build phase, per `tracker/BOARD.md`'s dated entry: immediately after build phase 3.1 merges, on branch `fix/c15-generation-bound`. Carries T-3.0-08's acceptance criteria, since that ticket is what named the scope when build phase 3.0 could not take it.

Depends on: build phase 3.1 (done, merged as PR #22, its re-review debt closed via PR #23)
Branch: `fix/c15-generation-bound`
Source finding: `tracker/phase_2.1.md`'s F-2.1-C15 writeup, and `DECISIONS.md`'s 2026-07-31 entry
Reference: `LEARNINGS.md`'s 2026-08-04 entry, the previous attempt at this same ticket, reverted for skipping analysis

## Table of contents

- [The done-when](#the-done-when)
- [Analysis, written first per the reverted attempt's lesson](#analysis-written-first-per-the-reverted-attempts-lesson)
- [What this fix does and does not claim](#what-this-fix-does-and-does-not-claim)
- [F-2.2-01 disposition](#f-22-01-disposition)
- [Acceptance criteria](#acceptance-criteria)
- [History](#history)

## The done-when

A generated Cypher query that would make AGE traverse an unbounded number of hops is rejected by `validate_cypher` before it ever reaches the graph, and a query with ordinary arithmetic in a property map value is never mistaken for one. Verify surface: `tests/system_03_search_agent/tools/test_cypher_validator.py`, plus a full-suite and premise-gate run to confirm nothing legitimate is newly rejected.

## Analysis, written first per the reverted attempt's lesson

The prior attempt at this exact ticket (`LEARNINGS.md`, 2026-08-04) skipped its required analysis, wrote 205 lines including a new validator rule, and left that rule rejecting `[:orthologous_to {weight: 2*3}]`, a legitimate query with arithmetic in a property map, as an unbounded traversal. This section is that analysis, done before any code changes in this branch.

What the evidence actually says happened:

- `DECISIONS.md`, 2026-07-31: "the real plan model... produced an unbounded `orthologous_to` traversal with DISTINCT." AGE ran it across four parallel workers and the kernel OOM killer killed the backend at roughly 3 GB resident.
- `tracker/phase_2.1.md`'s F-2.1-C15 section: "`LIMIT 100` was present, and DISTINCT materializes its input before the limit applies... memory was what ran out, and nothing bounded it."
- Both sources use the word "unbounded" to describe the traversal itself, not merely "large" or "wide." That word is not incidental. In openCypher, "unbounded" is the standard term for a variable-length relationship pattern with no upper hop count: `[:R*]`, `[:R*2..]`, or any range whose upper bound is missing. AGE has to consider paths of arbitrarily increasing depth for a pattern like that, and combined with `DISTINCT` materializing the full path set before `LIMIT` ever applies (confirmed by this exact incident), it is the textbook way a single query exhausts server memory.

Why this system's own design makes that the right diagnosis, not a guess:

- `schema_slice.py` expresses every multi-hop question as a fixed, small integer hop count (`single_hop` maps to 1, `multi_hop` maps to 2, `lookup` is floored at 1 while the classifier is a stub). Nothing in the schema-slicing design ever asks for or needs a variable-length range.
- `cypher_generation.py`'s system prompt (`_build_system_message`) gives the model eight numbered rules. None of them mentions, permits, or is written to constrain a `*` variable-length relationship spec, because the fixed-hop design never needed one.
- Given both of those, a variable-length relationship pattern is not a construct this system's generation was ever meant to produce. Rejecting it outright, unconditionally, cannot break a query the schema-slicing design intends to support, because no such query exists in that design.

Why the previous attempt's fix false-positived on `[:orthologous_to {weight: 2*3}]`:

- Cypher's grammar places a relationship hop's optional `*range` spec strictly between the label and the hop's optional `{properties}` map, never inside the property map. `2*3` is arithmetic inside a property value, a different part of the grammar entirely.
- This module already isolates exactly that boundary correctly, in `_extract_edge_labels`: `head = bracket_content.split("{", 1)[0]` takes only the portion before the first `{`, so a property map's contents never reach the label-parsing logic. `_split_label_spec` then strips a var-length spec from that same `head` via the existing `_VAR_LENGTH_SPEC_PATTERN`, before splitting on `:`/`|`, and that stripping already works correctly today; it is just silent rather than rejecting.
- The most plausible read of the reverted diff (not recoverable; the prior session's scratchpad is gone) is that it scanned the raw bracket interior text for a bare `*` character without first isolating the label-spec `head` the way `_extract_edge_labels` already does, so `2*3` inside the property map read as a var-length marker.
- The fix in this branch reuses the exact same `head = bracket_content.split("{", 1)[0]` isolation `_extract_edge_labels` already performs, so a property map's contents are structurally unreachable to the new check, not merely unlikely to match.

What was deliberately not built, and why: a rule requiring every MATCH pattern to anchor to a bound parameter (no unconstrained label scan). The evidence does not point at an unanchored scan as the mechanism; every query this pipeline generates is already forced through `entity_param_bindings` before generation even runs (`_run_pipeline` refuses outright when no entity was extracted, F-2.1-B10), so an unanchored top-level scan is not a shape this system can currently produce at all. Adding a rule for a shape that cannot occur would be exactly the over-reach the previous attempt is the cautionary tale for: a validator rule justified by no traced failure mode, added because it felt related. If a future finding shows an unanchored scan actually happening, that is a new, separately analyzed ticket, not folded into this one on a hunch.

## What this fix does and does not claim

- Closes: a generated variable-length relationship pattern (`*`, `*n`, `*n..m`, `*n..`, `*..m`, in any relationship hop, typed or untyped) is rejected before execution, with a message naming the finding and telling the caller to retry with fixed, chained hops instead.
- Does not weaken: the existing session-level `_MEMORY_GUARD_SQL` mitigation in `graph_connection.py` (`max_parallel_workers_per_gather = 0`, `work_mem = '32MB'`) stays in place unchanged. This fix adds a layer that stops the query before it runs; the memory guard remains the last line of defense for anything this layer does not catch.
- Does not claim: that every conceivable path to unbounded server-side work is now closed. A wide but fixed-hop fan-out (for example a hub node with an enormous number of `orthologous_to` edges at a single, legitimately-typed hop) is not addressed here, because nothing in the evidence points at that shape as the actual incident, and the row cap plus the memory guard already bound its blast radius. That is a different, untraced risk, not this ticket's scope.
- Does not claim, against the full Cypher grammar rather than against this system's actual generation contract: a list literal used for computation rather than as a relationship pattern, for example `RETURN [x * 2]`, matches the detection pattern and is wrongly rejected. Confirmed by the second review round below. Not closed, because closing it would need a nesting-aware parse of exactly the kind this fix's whole design avoids depending on, and neither `cypher_generation.py`'s system prompt nor `schema_slice.py`'s fixed-hop design ever produces a computed or arithmetic list element, only `$param` references or literal arrays. Recorded in `_has_variable_length_relationship`'s docstring.

## F-2.2-01 disposition

T-3.0-08's third acceptance criterion allows two outcomes: implement a retry on a graph-side parse rejection, or record the finding as still open with its measured rate. This fix takes the second option, deliberately, not by default.

`cypher_query.py`'s execute path (`_run_pipeline`, around the `execute_cypher` call) has no retry today: any `psycopg2.Error` other than `QueryCanceled` or `OperationalError` folds into a generic `GraphConnectionError`, and a graph-side `SyntaxError` on validator-accepted-but-malformed Cypher (the missing-parentheses shape `MATCH g:Gene {...}-[...]->d:Disease`) surfaces as `status: "error"` with no second attempt. Adding a graph-level retry would touch the same pipeline function this branch's C15 fix does not otherwise need to change, in a file with an exceptionally long history of findings specifically in its retry and error-handling logic (F-2.1-B02, C11, the whole repair-retry mechanism). Bundling a second, independently-risky change into the same branch as a critical safety fix, reviewed in the same single pass, is the composition risk `self-eval-loop`'s "review a fix harder than new code" section warns about, applied to scope rather than to a single function.

Measured rate, carried forward rather than re-measured: `tracker/phase_2.2.md`'s F-2.2-01 section recorded the flake at roughly 1 run in 10 (3 consecutive re-runs of the same test all passed, and the one failure was a single observation against a documented 9-of-9). This branch cannot re-measure it live: the premise gate needs the SSH tunnel to the graph, and `.claude/rules/sandbox-diagnosis.md` is explicit that the Layer-7 sandbox proxy cannot tunnel raw SSH, the same environment constraint T-3.0-07 already carries. F-2.2-01 remains open, at its last-measured rate, and is not touched by the code change in this branch.

## Acceptance criteria

From `tracker/phase_3.0.md`'s T-3.0-08:

- [ ] A generated traversal that is unbounded in the F-2.1-C15 sense is rejected before execution, not merely bounded by the session memory guard
- [ ] The existing `_MEMORY_GUARD_SQL` mitigation stays in place, since this ticket adds a layer rather than replacing one
- [ ] F-2.2-01's missing-parentheses generation flake either retries on a graph parse rejection or is recorded as still open with its measured rate
- [ ] Every one of build phase 2.1's premise-gate questions still passes, so the constraint does not block a legitimate query shape

The fourth criterion cannot be verified live in this environment (no SSH tunnel), the same constraint T-3.0-07 carries. It is verified instead by static review of all nine premise-gate questions' expected Cypher shapes (`tests/system_03_search_agent/tools/test_cypher_query_premise.py`): every one is a fixed-hop, entity-anchored lookup, aggregate, or listing question, none of which has any legitimate reason to use a variable-length relationship pattern. This is not a substitute for a live run; a live run remains the stronger evidence and should happen whenever the tunnel is next reachable.

## History

- 2026-08-07 lead: opened the branch, wrote this analysis before any code change, per the reverted attempt's own lesson.
- 2026-08-07 lead: implemented the first version of `_has_variable_length_spec`, sliced from `_RELATIONSHIP_HOP_PATTERN`'s captured bracket interior at its first `{`. 98 of 98 validator tests passed, including the exact reverted-regression string.
- 2026-08-07, first independent review (fresh-context, dispatched by the lead, same session): REJECT. Found a live bypass: `_RELATIONSHIP_HOP_PATTERN`'s non-nesting bracket capture never matches a hop carrying a nested bracket (a list-valued property) alongside a `*range` spec, so the check never ran on `[:orthologous_to*2 {tags: [$a, $b]}]` at all. Same defect class as F-2.1-A9, never generalized to relationship hops.
- 2026-08-07 lead: replaced the check with `_UNBOUNDED_TRAVERSAL_PATTERN`, a standalone, wildcard-free regex matched directly against the quote-masked query string, independent of `_RELATIONSHIP_HOP_PATTERN` and of finding a hop's true closing bracket. Added regression tests for the bypass and a matching anti-false-positive test. 103 of 103 validator tests passed, 1729 of 1729 full-suite tests passed (82 skipped, 1 xfailed, both pre-existing), `ruff check` clean except the one pre-existing, unrelated finding.
- 2026-08-07, second independent review (fresh-context, dispatched by the lead, same session): APPROVE WITH NOTES. Confirmed the specific bypass closed by direct execution, tried and failed to find a new bypass, timed the pattern against six adversarial inputs and found no ReDoS (linear scaling, no nested quantifier over the same class), confirmed the test suite and ruff counts independently, and confirmed the docstrings match the code. Found one non-blocking gap against Cypher's full grammar: a list literal used for computation rather than as a relationship pattern (`RETURN [x * 2]`) is wrongly rejected, unreachable by this system's actual generation contract. Documented in `_has_variable_length_relationship`'s docstring and in this file's "what this fix does and does not claim" section, per this codebase's own convention of recording a scoped gap rather than silently absorbing it.
