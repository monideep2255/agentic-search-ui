# Build phase 6.0 judge report

Round: judge (independent, no Write/Edit tools; findings only, closes nothing).
Branch: `phase/6.0-rate-limit-concurrency`.
Started: 2026-08-31.

Findings are appended below as they are established. Each row states whether it
was established by EXECUTION or by READING.

### F-6.0-J-01: `act_node`'s mid-tool `CallBudgetExceededError` catch is DEAD CODE, because `ncbi_efetch` swallows the exception first

- Severity: major
- Established by: EXECUTION
- INSIDE THIS PHASE'S OWN NEW CODE (`core/graph.py`, commit 535e3e3). This is the branch the phase's own design section calls "the case Section 21.3 actually names".
- What: `core/graph.py:3165` adds `except call_budget.CallBudgetExceededError:` around
  `harness.enforce_timeout("act", ncbi_efetch(...))`. `ncbi_efetch` is documented "Never
  raises" and its dispatcher has a last-resort `except Exception` at
  `tools/ncbi_efetch.py:283` that converts ANY exception, including
  `CallBudgetExceededError`, into an `NcbiEfetchOutput(status="error")`. The exception
  therefore cannot reach `act_node`'s handler on the only dispatch path that handler
  guards. Three consequences follow:
  1. `cap_exceeded` is NOT set on the mid-tool path. If the exhausted call is the LAST
     planned call, the loop finishes normally and `write_node` never learns the run was
     degraded by the call ceiling.
  2. The user- and agent-facing error text is the WRONG instruction. It reads
     "Retry once; if this recurs, the 'search' action module has a defect that needs
     fixing before this action can be trusted", where the truth is "the query is out of
     budget, synthesize from what you have". `.claude/rules/tool-call-budgets.md` requires
     the error to say what to do next.
  3. The dead handler's own comment claims "A curated string, never `str(exc)`". On the
     path that actually runs, `str(exc)` is interpolated into the tool error verbatim by
     `_error_output`. The confident sentence describes a property of code that never runs.
- Reproduction (exact):
  ```
  cd <repo>; PYTHONPATH=src python scratchpad/probe_swallow.py
  ```
  where the probe opens `query_budget_scope("lookup")`, charges 20 calls, then awaits
  `ncbi_efetch(NcbiEfetchInput(action=search, db=gene, term=BRCA1, retmax=1))`.
  Exact output:
  ```
  calls_made: 20
  RETURNED, no exception. status= error
  error text: "ncbi_efetch's 'search' action raised an unexpected CallBudgetExceededError
  instead of returning a classified result: this query has already issued its 20 permitted
  Layer 2/3 API calls (Section 21.3); the call to ncbi_transport:eutils was refused rather
  than issued. Synthesize from the results already gathered, or re-ask with a narrower
  query. Retry once; if this recurs, the 'search' action module has a defect that needs
  fixing before this action can be trusted."
  calls_made after: 20
  ```
  No exception escaped. The `except call_budget.CallBudgetExceededError` block cannot be entered.
- Why it matters: the phase's central design claim is that the ceiling is enforced at the
  transport and the LOOP handles the control flow. Half of that loop half does not
  execute. The 21st request still never reaches the network (the transport charge is
  correct), so the safety property holds; what is broken is the degradation path, the
  `cap_exceeded` signal on the last-call case, and the actionability of the error.
- NOT FIXED

### F-6.0-J-02: gate arm A7 is VACUOUS. It never reads the comment it is named for, and passes with that comment deleted

- Severity: major
- Established by: EXECUTION
- INSIDE THIS PHASE'S OWN FIX. A7 is the arm the phase record cites as the pin for F-6.0-01
  ("Pinned by the gate's A7 arm", `tracker/phase_6.0.md` findings table). The fix for a
  confident-sentence finding is itself a confident sentence about a check that is not there.
  This is the SIXTH instance of that shape in this repository and the SECOND inside this
  phase (F-6.0-03 was the first).
- What: `test_a7_the_web_adapter_comment_no_longer_claims_an_absent_cap` performs exactly
  two assertions: `web_app._MAX_CITATIONS_PER_RUN > 0` and
  `call_budget.MAX_LAYER_2_3_CALLS_PER_QUERY == 20`. It never opens
  `adapters/web_sse/app.py`, never reads any comment text, and never asserts any relation
  between the citation cap and the call ceiling. Deleting the entire comment block, or
  reverting it to the original FALSE sentence, leaves the arm green. Its second assertion
  is also a verbatim duplicate of A1's, so A7 contributes no coverage A1 does not already have.
- Reproduction (exact): copied `src/` to the scratchpad, deleted the 19 comment/blank lines
  immediately above `_MAX_CITATIONS_PER_RUN = 50` in the copy, and ran A7's body verbatim
  against the mutated copy:
  ```
  python scratchpad/probe_a7.py
  app.py under test: .../scratchpad/srcmut1/system_03_search_agent/adapters/web_sse/app.py
  does the file still contain the cap sentence?  False
  does the file mention MAX_LAYER_2_3_CALLS_PER_QUERY? False
  A7's two assertions: BOTH PASS with the comment entirely deleted
  ```
  The repository tree itself was NOT modified; the mutation lives only in the scratchpad copy.
- Why it matters: F-6.0-01's stated repair is "the comment is corrected in the same edit that
  makes it true", held together by A7. A7 holds nothing together. If the ceiling is ever
  removed or the comment reverted, nothing goes red.
- NOT FIXED

### Interim note (no finding): ContextVar scope semantics and the wait-ceiling arithmetic both hold

Established by EXECUTION (`scratchpad/probe_ctx.py`, run with `PYTHONPATH=src`). Recorded so
the checks are visible rather than invisible.

- Task fan-out: 3 `asyncio.create_task` children charging 5 calls each inside one scope leave
  the parent reading `calls_made() == 15`. The mutable-object-in-a-ContextVar claim holds for
  created tasks, not only for directly awaited coroutines.
- Nesting: inner scope reads its own count (1) and its own ceiling (5.0); on exit the outer
  scope reads 1 and 1.5 again. No stranding.
- An exception escaping a scope leaves `calls_made() is None`. No leak.
- The bare `set_query_budget`/`reset_query_budget` pair (the `run_streaming` shape) restores
  `None`.
- Wait ceilings measured: lookup 1.5, single_hop 2.0, aggregate 3.0, multi_hop 3.0,
  exploratory 5.0 (12.0 derived, capped). These match `_QUERY_CLASS_BUDGET_S`
  (15/20/30/30/120) at 10%, match the docstring's stated figures, and `lookup` really is the
  smallest of the five, so `set_query_class`'s "conservative floor" claim holds.

### F-6.0-J-03: `act_node`'s pre-dispatch ceiling check refuses LAYER 1 `cypher_query` calls, which Section 21.3 does not bound

- Severity: major
- Established by: EXECUTION
- INSIDE THIS PHASE'S OWN NEW CODE (`core/graph.py:3110-3116`, commit 535e3e3).
- What: the new pre-dispatch check sits ABOVE the `isinstance(planned, _PlannedNcbiEfetchToolCall)`
  branch, so it applies to every planned call regardless of layer. When a query's Layer 2/3
  budget is exhausted, the loop breaks before dispatching a planned `cypher_query`, which is a
  LAYER 1 call that never charges the budget and which this phase's own design section
  explicitly places out of scope ("`graph_http_transport` is Layer 1 and is out of scope by
  21.3's own wording"). The reachable path is not hypothetical: `think_node`'s entity
  resolution issues real Layer 2 calls before Act runs, and the phase's whole design argument
  rests on that fact. A query that spends its ceiling in Think therefore answers with ZERO
  graph rows, having never queried the graph, and is marked `cap_exceeded`.
- Reproduction (exact): `scratchpad/probe_act.py` drives the real `act_node` with one planned
  `cypher_query` call (`layer="layer_1_graph"`), a stub harness, `graph.cypher_query` replaced
  by a recorder, and a budget scope charged to 20 Layer 2 calls.
  ```
  PYTHONPATH=src python scratchpad/probe_act.py
  budget exhausted, calls_made = 20
    coordinator_worker got len(tool_calls)=0 len(results)=0
    cypher_query dispatched? False
    cap_exceeded in result? True
  ```
  The Layer 1 call was never issued.
- Scope, counted rather than assumed: ONE instance. `call_budget.calls_made()` appears exactly
  once in `src/` (`core/graph.py:3110`). This is a bug, not a class.
- Why it matters: the ceiling exists to stop a query burning its latency budget on third-party
  APIs. Refusing the free, in-house, unbounded graph query is the opposite of what 21.3 asks
  for, and it removes the one retrieval path that could still have grounded an answer. Under
  cite-or-refuse this converts a partially-degraded answer into a refusal.
- Side note established in the same run: `tool_calls` and `results` stay paired 1:1 on this
  path (0 and 0 above), because the `break` precedes `tool_calls.append`. The pairing
  invariant `coordinator_worker_execute` requires is NOT broken here.
- NOT FIXED

### F-6.0-J-04: SIX tool modules swallow `CallBudgetExceededError` into an ordinary tool error. This is a CLASS, not the single instance F-6.0-J-01 reports

- Severity: major
- Established by: EXECUTION for one instance (`ncbi_efetch`, see F-6.0-J-01), READING for the
  other five, with the count below taken by grep rather than assumed.
- What: every tool module that fronts a Layer 2/3 transport ends its dispatcher in an
  unconditional `except Exception as exc:` that converts ANY exception into an
  `..._error_output(...)`. `CallBudgetExceededError` is an ordinary `Exception` subclass
  (`harness/call_budget.py:132`), so the ceiling can never propagate to a caller through any
  of them. The phase added an exception type as its refusal signal and did not exempt it from
  any of the six catches.
- Scope, COUNTED: 6 of 6 tool dispatchers, one per tool module.
  ```
  tools/ncbi_efetch.py:283          except Exception as exc:  # the dispatcher's deliberate last-resort catch
  tools/clinicaltrials_search.py:597 except Exception as exc:  # the module's deliberate last-resort catch
  tools/litvar2_lookup.py:1015      except Exception as exc:  # the module's deliberate last-resort catch
  tools/ncbi_dbsnp.py:1575          except Exception as exc:  # the module's deliberate last-resort catch
  tools/pathogen_detection.py:1132  except Exception as exc:  # the module's deliberate last-resort catch
  tools/pubtator_annotate.py:911    except Exception as exc:  # the module's deliberate last-resort catch
  ```
  Only `ncbi_efetch` is wired into `act_node` today (the loop dispatches exactly two tools,
  `cypher_query` and `ncbi_efetch`), so only that one is reachable in the shipped product
  right now. The other five become reachable the moment their tools are wired, and the
  `except call_budget.CallBudgetExceededError` handler in `act_node` will be dead for every
  one of them too.
- Reproduction for the reachable instance: see F-6.0-J-01's exact output.
- Why it matters: the exception-based refusal design cannot work through the tool layer as it
  stands. Four of the six also interpolate `{exc}` into the error text they return, so the
  budget message reaches a sink as raw exception text, which is the thing `act_node`'s dead
  handler's own comment says never happens.
- NOT FIXED

### F-6.0-J-05: T-6.0-02's ENTIRE wiring can be deleted and all 20 of this phase's tests still pass

- Severity: critical
- Established by: EXECUTION (source mutation in a scratchpad COPY of the repository; the
  repository tree was not touched).
- What: Section 21.4's previously-unwired half is the phase's second deliverable. The single
  line that wires it is `effective_ceiling = call_budget.wait_ceiling_s()` in
  `tools/ncbi_transport.py:1306`. Removing that branch entirely, so `execute_get` falls
  straight back to `timeout_s` exactly as it did before this phase, leaves BOTH the premise
  gate and the mutation harness fully green. No arm in this phase pins the property the
  ticket exists to deliver.
  A6 asks `call_budget.wait_ceiling_s()` what it would return. A6b builds its OWN
  `RateLimiter` and passes those values to `acquire` by hand. Neither ever calls
  `execute_get`, so neither can see whether the transport consults the budget at all. The
  mutation named `test_a6b_mutation_transport_ignores_the_query_ceiling` does not test the
  transport either: it patches `RateLimiter.acquire`, which A6b calls directly, so it proves
  only that A6b's own hand-passed argument matters.
- Reproduction (exact):
  ```
  # copy pyproject.toml, src/ and tests/ to scratchpad/repo2, then:
  cd scratchpad/repo2 && python -m pytest <premise> <mutation> -q
  20 passed, 2 warnings in 6.11s          # baseline on the copy

  # delete the two lines that consult the query budget in execute_get:
  #   if effective_ceiling is None:
  #       effective_ceiling = call_budget.wait_ceiling_s()
  MUTATION M1 applied: execute_get no longer consults call_budget.wait_ceiling_s()
  cd scratchpad/repo2 && python -m pytest <premise> <mutation> -q
  20 passed, 2 warnings in 5.52s          # STILL GREEN with the deliverable removed
  ```
- Why it matters: this is precisely the "a value computed and never used" shape build phase
  4.15 shipped four times, and this phase's own mutation-harness docstring claims to guard
  against it by name ("An arm that only asked the budget what it would supply stays green
  here, which is exactly why A6b drives the pool"). A6b does not drive the transport. The
  claim is a confident sentence describing a check that is not there, and the phase's Evidence
  section rests the ticket on a TRANSIENT development observation instead
  ("T-6.0-02 is proven wired by A2's own failure rather than by reading the call site"), which
  is not a standing check and does not exist in the tree.
- Scope: one wiring line, one ticket. Reported as a bug in the verify surface, not a class.
  I did NOT run the whole suite against the mutation, so it is possible some unrelated test
  elsewhere catches it; see the coverage statement.
- NOT FIXED

### F-6.0-J-06: the FTP transport's two charge points are unpinned, and the ticket the gate names as owning that gap (T-6.0-03) is marked done without closing it

- Severity: major
- Established by: EXECUTION.
- What: A4's docstring states its own gap honestly ("It does NOT prove
  `pathogen_ftp_transport` actually calls it, which is this arm's known gap and T-6.0-03's job
  to close"). T-6.0-03 is marked `done` in `tracker/phase_6.0.md`'s ticket table, and the
  mutation harness it delivered contains no FTP arm at all. Deleting BOTH
  `charge_one_call(tool="pathogen_detection", layer=2)` lines from
  `tools/pathogen_ftp_transport.py` leaves the premise gate, the mutation harness and
  `test_pathogen_detection.py` all green: 48 passed.
- Reproduction (exact), in the scratchpad copy:
  ```
  MUTATION M3 applied: removed 2 FTP charge points
  cd scratchpad/repo2 && python -m pytest <premise> <mutation> tests/.../test_pathogen_detection.py -q
  48 passed, 2 warnings in 5.59s
  ```
- Second, related fact established by READING: `pathogen_ftp_transport` imports
  `charge_one_call` BY NAME (`from system_03_search_agent.harness.call_budget import
  charge_one_call`), whereas `ncbi_transport` imports the MODULE. A future mutation that
  monkeypatches `call_budget.charge_one_call`, which is exactly what the existing A2/A4/A5
  mutations do, cannot reach the FTP call sites at all. Any arm written that way for the FTP
  path would be vacuous by construction.
- Scope, COUNTED: 2 charge points, 1 module, 0 arms covering either.
- Why it matters: the phase's own design argument is that the Layer 2/3 surface is exactly two
  functions and both must charge. One of the two is entirely unpinned, and the ticket that was
  supposed to pin it was closed.
- NOT FIXED

### F-6.0-J-07: the Section 21.2 "measured rather than asserted" arm measures a limiter it built itself, and passes with private per-caller pools

- Severity: critical
- Established by: EXECUTION.
- INSIDE THIS PHASE'S OWN FIX. T-6.0-03's entire stated purpose is "Measure 21.2 rather than
  assert it", and the goal contract's third done-when line is "The process-wide sharing of each
  family's bucket is proven under real concurrency rather than asserted from the shape of the
  registry." This arm does not prove it.
- What: `test_one_familys_pool_is_shared_across_concurrent_queries`
  (`test_rate_limit_concurrency_mutation.py:262`) constructs its own limiter
  (`ncbi_transport.RateLimiter(requests_per_second=4.0, ...)`) and hands that ONE object to
  twelve concurrent tasks. Twelve callers sharing one object queue behind each other by
  construction. The arm never calls `get_rate_limiter`, which is the process-wide registry
  Section 21.2 is actually about, so the property under test ("one bucket per family across
  every concurrent query") is never exercised. This is the identical shape build phase 4.15
  recorded: an arm proving two apps hold different signing keys that only re-proved their
  databases differ.
- Reproduction (exact): in the scratchpad copy, mutate `get_rate_limiter` to return a FRESH
  `RateLimiter` on every call, which is exactly the private-pool-per-caller defect 21.2
  forbids:
  ```
  MUTATION M4 applied: get_rate_limiter returns a FRESH limiter every call
  cd scratchpad/repo2 && python -m pytest <mutation> <premise> -q
  20 passed, 2 warnings in 6.08s
  ```
  Every arm stays green with the requirement broken.
- Secondary: the `with call_budget.query_budget_scope("lookup")` inside that arm is decoration.
  Nothing in the arm's assertion depends on a budget being bound.
- Scope, COUNTED: 1 arm, and it is the only arm in the phase that claims to measure 21.2.
- Why it matters: `tracker/phase_6.0.md` records 21.2 as BUILT and the phase's evidence
  presents this arm as the measurement that upgraded it from a claim about the shape of a dict.
  The upgrade did not happen.
- NOT FIXED

### F-6.0-J-08: the retry-charging property, the one Section 21.3 names FIRST, is unpinned. Hoisting the charge out of the retry loop leaves 90 tests green

- Severity: major
- Established by: EXECUTION.
- What: the comment at `tools/ncbi_transport.py:1435` states the property confidently:
  "Charged here, inside the attempt loop, rather than once per `execute_get`, because 21.3
  names 'a retry' first in its own list of where a 21st call comes from. A charge hoisted out
  of this loop would let a query issue 40 requests against a 20-call ceiling and report 20."
  Nothing tests it. Moving the charge to immediately before `for attempt_index in range(2):`,
  which is exactly the 40-requests-reported-as-20 defect the comment describes, leaves the
  premise gate, the mutation harness and the full transport suite green.
- Reproduction (exact), in the scratchpad copy:
  ```
  MUTATION M5 applied: the charge is HOISTED OUT of the retry loop
  cd scratchpad/repo2 && python -m pytest <premise> <mutation> tests/.../test_ncbi_transport.py -q
  90 passed, 2 warnings in 5.98s
  ```
- Why it matters: the phase's design section names three sources of a 21st call ("a retry, a
  wider-than-expected fan-out, or an ELink traversal that returns more targets than planned")
  and rests the whole transport-not-act_node argument on them. None of the three is exercised
  by any arm: every arm issues plain, first-attempt, non-fanning calls. The gate proves the
  ceiling counts SEQUENTIAL calls, which is the case `act_node` could have counted too.
- Scope, COUNTED: 1 charge site, 0 arms covering the retry path. Related to F-6.0-J-05 and
  F-6.0-J-06 as a pattern: three separate properties this phase argues for in prose have no
  standing check.
- NOT FIXED

### F-6.0-J-09: removing BOTH production scope bindings in `core/run.py` leaves the entire `tests/.../core/` suite identical, so nothing pins that the ceiling is bound on the real query path

- Severity: critical
- Established by: EXECUTION.
- What: `core/run.py` is where the ceiling is attached to a real query, in two places: the
  `query_budget_scope("lookup")` in `run()`'s `with` statement and the
  `set_query_budget("lookup")` / `reset_query_budget(...)` pair in `run_streaming()`. Every
  shipped surface (web SSE, GraphQL, MCP, CLI) reaches the loop through
  `RunRegistry.create_run` -> `run_streaming`, so `run_streaming`'s binding is the ONLY thing
  that makes the ceiling exist for a real user. Deleting all three lines changes no test
  result anywhere in `tests/system_03_search_agent/core/`.
- Reproduction (exact), in the scratchpad copy:
  ```
  MUTATION M6 applied: neither run() nor run_streaming() binds a query budget scope
  cd scratchpad/repo2 && python -m pytest <premise> <mutation> -q
  20 passed, 2 warnings in 5.73s

  cd scratchpad/repo2 && python -m pytest tests/system_03_search_agent/core/ -q
  498 passed, 55 skipped, 2 warnings, 14 errors in 18.71s      # WITH the mutation
  498 passed, 55 skipped, 2 warnings, 14 errors in 17.76s      # baseline, run.py restored
  ```
  Identical counts. (The 14 errors are pre-existing database-dependent
  `test_feedback_capture_premise.py` errors present in both runs.)
- Why it matters: with this mutation applied, `charge_one_call` no-ops on every production
  path, because `_budget_var` is never bound; the ceiling is silently absent for every user on
  every surface while every arm in the phase stays green. The premise gate binds its own
  scopes by hand, so it can never see this. The gate's docstring argues at length that
  counting at `act_node` would be the wrong fix and that A2 exists to catch it, but the fix it
  did ship has no arm covering the step that turns the counter on.
- Scope, COUNTED: 3 lines in 1 file, 2 call sites, 0 arms covering either. I did NOT run the
  full 4500-test suite against this mutation; see the coverage statement.
- NOT FIXED

## Coverage statement: what this round did NOT check

Written before the round ended, so the gap is arguable rather than invisible.

- I did NOT run the full ~4543-test Python suite, nor `ruff check`, nor `isort --check-only`,
  nor `tracker/check_doc_drift.py --check`. The phase's Evidence section states results for all
  four and I took none of them as verified. Every mutation result above is scoped to the test
  files I named in that command, plus, for F-6.0-J-09, the whole of
  `tests/system_03_search_agent/core/`. As a partial scope check I grepped the entire `tests/`
  tree for `call_budget`, `query_budget_scope` and `MAX_LAYER_2_3`: the only matches are this
  phase's two files plus an unrelated per-call-timeout test in
  `tests/system_03_search_agent/export/test_kgx_traversal.py` and the debugging-guide manifest.
- I did NOT exercise anything against a live NCBI endpoint, a live graph, or a live model. All
  probes used fake clients and fake clocks.
- I did NOT drive a full `run_streaming` end to end, so I did not observe the ceiling working
  on a real production query path; F-6.0-J-09 shows nothing else does either.
- I did NOT test the FTP transport against an FTP server; F-6.0-J-06 is about the absence of
  any arm, not about whether the two charge lines are correct where they sit.
- I did NOT check the phase's untouched neighbours: the seven rate-limit families' pacing
  arithmetic, queue-depth caps, `retry_after` values, or `TransportRateLimitedError`'s
  contents, all of which shipped in build phases 3.1 to 3.5 and are outside this diff.
- I did NOT review the tracker or documentation edits for accuracy beyond the claims I quote,
  and I deliberately did not review commit `16eed62` or `212509e` (the product owner's UI
  documentation), which are out of scope.
- I did NOT assess F-6.0-02's product-owner decision (the rate ceiling binding before the call
  ceiling for `lookup` on E-utilities). It is recorded as decided and I treated it as settled.
- I did NOT check the GraphQL, MCP or CLI adapters' own code paths beyond establishing by grep
  that all four surfaces reach the loop through `RunRegistry.create_run` -> `run_streaming`,
  and therefore share the single binding F-6.0-J-09 shows is unpinned.
