# Card 19 judge, one round

Base: branch fix/card19-act-complete at 1d46377b, compared with origin/develop. Findings are written as they are established.

## Findings

### J-19-01: A start frame that arrives after another call's result now shows a false writing step
- Severity: minor (unsure whether the backend can send this order today)
- What: before the fix, once any planned id was on the wire every planned id had to close, so a late start was covered by the plan. After the fix only ids already seen count. A plan of c1 and c2 with frames `start c1, result c1` and c2's start still to come now reads Write. When c2's start lands it goes back to Act. This is the flicker card 19 names.
- Reproduction: judge probe in vitest, `useRunView([GUARD, THINK, plan(c1,c2), start c1, result c1])`, then the same events plus `start c2`. This branch: `P3a Write`, `P3b Act`. The same probe with `useRunView.ts` from `origin/develop`: `P3a Act`, `P3b Act`.
- Can the backend send this order: in the normal case, no. `act_node` writes every start (`core/graph.py:8828` to `8842`) before the first `_gather_planned_calls` (`core/graph.py:8865`). `run_streaming` deduplicates by seq but never sorts (`core/run.py:904` to `937`). `useAgentRun` and `usePacedEvents` do not reorder either. The one path I found is in `emit_live`: if the live writer raises for a single start frame (`core/graph.py:790` to `791`), that frame arrives only when the node returns, after the results. That path is meant for a writer that is missing for the whole run, not for one frame.
- Why it matters: the fix rests entirely on that one backend ordering guarantee, and nothing tests it from the frontend's side. The guarantee holds today, so this does not block the merge. It is a trade the old code did not have to make.
- NOT FIXED
### J-19-02: No test pins the backend ordering the fix relies on; the whole backend suite passes when it is broken
- Severity: major
- What: the fix is correct only because `act_node` writes every `tool_start` before any call runs (`core/graph.py:8828` to `8842`, ahead of the first `_gather_planned_calls` at `core/graph.py:8865`). I read that code and it holds today. But no backend test asserts it. The 4.16 premise test only checks that each call's own start comes before its own result (`tests/system_03_search_agent/core/test_phase_4_16_premise.py:351` to `352`). Before this fix, the plan-id check in `useRunView.ts` caught a call that started late. That check is gone. The branch adds no backend test to take its place.
- Reproduction: I mutated `act_node` so the follow-up calls (`_PlannedFollowUpCall`) write their start frames at the top of the second-stage loop, after the first-stage results, instead of with the others up front. Then I ran `pytest -q -m "not live" tests/system_03_search_agent`. Result: `6684 passed, 166 skipped, 1 xfailed`, so nothing went red. Under that mutation the frontend reads Write between the two stages: judge probe `P3a Write`, where develop's `useRunView.ts` gives `P3a Act`. The mutation was reverted with `git checkout HEAD -- src/system_03_search_agent/core/graph.py`, and `git diff --stat HEAD` came back empty.
- Why it matters: if anyone moves a start frame later (for example, writing follow-up starts when the follow-up is built, which looks natural), the very false writing step card 19 worries about comes back, and no test in either suite goes red. The code comment in `useRunView.ts:458` to `461` states the guarantee but nothing enforces it. Fix: add a backend test that every `tool_start` in a run comes before its first `tool_result`, run on a breadth question that has follow-ups, and check that it goes red under this mutation.
- NOT FIXED
### J-19-03: The "some calls skipped because the question is broad" case the ticket and test describe does not seem to happen; the common skip case starts no call at all and still stalls
- Severity: unsure (from reading the code, not from a run)
- What: the admission loop in `act_node` (`core/graph.py:8792` to `8821`) runs before any call is dispatched. It contains no `await`, and nothing inside it spends money or charges the call budget. The budget is charged per HTTP request in `tools/ncbi_transport.py:1605`. So `call_budget.calls_made()` and `check_per_query_cap` return the same value for every planned call. A plan with more than 20 live lookups is admitted in full: every lookup gets a start frame, and the ones past the limit are refused at the transport and closed with an error result. So none of them is "planned but never started". The skip at admission is all or nothing. The cost cap's `break` (`core/graph.py:8805`) skips every call. The 20-call `continue` (`core/graph.py:8820`) skips every Layer 2 and 3 call, and only when Think and Plan have already used 20 lookups.
- Consequences, each checked with a judge probe in vitest:
  - The one case the fix changes needs a graph (Layer 1) call admitted next to Layer 2 and 3 calls that are all skipped. The fix handles that: `P6d Write` on this branch, `P6d Act` on develop.
  - When every planned call is skipped, nothing starts. The steps then stay on Plan through the whole writing wait on both versions: `P5b ... Plan`. The fix does not reach this case, though it is the more likely of the two.
  - The new test line under query 98 in `testing/Test_queries_and_workflows.md:1161` asks the product owner to look for this on "a question so broad that some of the planned lookups are skipped at the 20-call limit". If my reading is right, no such question exists, and the line names no question to type. The owner cannot run it.
  - The comment in the test (`useRunView.writeState.test.tsx`, "act_node skipped it at the 20-call limit") describes a stream that the plan size alone cannot produce.
- Why it matters: the change is harmless, but the person waiting may never see what it promises. The likely stall, on Plan, is left as it was. A test line the owner cannot run counts as a pass that nobody can check.
- NOT FIXED
## Checklist

| Item | Result | How |
|---|---|---|
| Steps move to writing while a started call is still running | No. Plan c1 and c2, both started, c1 closed: `P1 Act`. 21 planned, 20 started, 19 closed: `P2a Act`. Once the 20th closes: `P2b Write` | Ran (judge probe) |
| Start frame that arrives late or out of order | A late start after another call's result now reads Write, then Act again (J-19-01). A result that arrives before its own start is fine: `P4a Act`, `P4b Write` | Ran |
| Run with zero calls | Plan with no tools: `P5a Write`, unchanged. Plan lists calls but none ever start: `P5b Plan`, unchanged and not fixed (J-19-03) | Ran |
| Refused, fatal or stopped run | Guard refusal `P6a null`, fatal error with a call open `P6b null`, fatal error after the results `P6c null`. A stopped run renders `activeStep={stopped ? null : step}` (`frontend/src/App.tsx:1746`, `1775`, `1818`), which this change does not touch | Ran (refusal, fatal). Read (stop) |
| Backend writes every start before any result | Holds today (`core/graph.py:8828` to `8842`, before `8865`), and no reordering happens downstream (`core/run.py:904` to `937`, `useAgentRun.ts`, `usePacedEvents.ts`). No test pins it: 6684 backend tests still pass when it is broken (J-19-02) | Read, then a mutation run |
| Break the condition | Develop's condition: the new test fails, `1 failed, 7 passed (8)`. `idsToClose = closedIds`: 2 existing tests fail. Both reverted, `git diff --stat HEAD` empty | Ran |
| `npx vitest run src/hooks` | `Test Files 11 passed (11)`, `Tests 80 passed (80)` | Ran |
| `npx tsc --noEmit -p .` | exit 0, no output | Ran |

Read but not run: the stop path in `App.tsx`, and the claim in J-19-03 that admission charges and spends nothing.

J-19-01 and J-19-02 sit inside this card's own change.

Verdict: FIX FIRST. The frontend change is correct against the backend as it is today, and its condition bites. Before merging, add a backend test that every `tool_start` comes before the first `tool_result`, and show it goes red under the late follow-up mutation (J-19-02). Then reword or remove the test line under query 98 so the owner has a question to type (J-19-03).
