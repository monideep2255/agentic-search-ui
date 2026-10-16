# Card 19 verifier report

Fresh verifier, 2026-10-09, branch fix/card19-act-complete at 9fa565cc against develop b01dee92. Findings are appended as established.

## Findings

### V-19-00: J-19-02 / A-19-02 confirmed done (not a defect)
- Severity: none, a record of a claim checked by my own run
- What: `test_every_tool_start_comes_before_the_first_tool_result` exists in `tests/system_03_search_agent/core/test_breadth_wiring.py`, runs through `run_streaming`, and bites.
- Reproduction: unmutated, `pytest -q tests/system_03_search_agent/core/test_breadth_wiring.py -k test_every_tool_start_comes_before_the_first_tool_result` gave `1 passed, 47 deselected`. I then wrapped act_node's start loop as `_emit_starts(group)` and called it as `_emit_starts(first_stage)` before the first `_gather_planned_calls` and `_emit_starts(follow_ups)` right after it (my own script, not the fix round's). The test went red with `assert 21 < 9`. The three-file set (breadth_wiring, premise, layer_handoff) gave `1 failed, 80 passed`, so this is the only test that sees it. Restored with `git checkout -- src/system_03_search_agent/core/graph.py`, diff empty, test green again.
- Only `act_node` writes `tool_start` or `tool_result` frames in `src/` (grep), and the graph has no edge back into `act`, so the test covers the one writer.

### V-19-01: The fix round's corrected test comment contradicts its own fixture
- Severity: minor (comment only; no user-visible effect). This sits inside a fix made in this card's fix round (the J-19-03 / A-19-07 wording fix).
- What: the comment on the new test in `frontend/src/hooks/useRunView.writeState.test.tsx` now says "Think and Plan had already used the 20-call budget, so act_node admitted only the graph (Layer 1) calls and skipped every Layer 2/3 call". The fixture it describes starts and closes `c1`, which is `ncbi_efetch` on `layer_2_api` (PLAN_TWO), and skips `c2` on `layer_3_enrichment`. Under the comment's own story `c1` would have been skipped too. The ceiling in act_node gates Layer 2 and Layer 3 together and the cost cap is all or nothing, so "Layer 2 started, Layer 3 skipped" is a stream the backend cannot produce.
- Reproduction: `sed -n 49,55p` and the new test body in that file at 9fa565cc; act_node admission loop in `src/system_03_search_agent/core/graph.py` (the `planned.tool_call.layer in ("layer_2_api", "layer_3_enrichment")` test).
- Why it matters: the hook rule the test pins is layer-blind, so the test still guards the right thing (my probe shows develop's hook gives Act on the same shape). The comment misleads the next reader about which shape is real, the same class of defect A-19-07 was filed for. Fix is a fixture change (c1 as a `layer_1_graph` call) or a comment that says the layers are illustrative.
- NOT FIXED

### V-19-02: Hook regression hunt, develop against branch, prefix by prefix (record, one known difference)
- Severity: minor for the one worse sequence, which is J-19-01; unreachable today as far as I can find
- What: I loaded develop's `useRunView.ts` (b01dee92) and the branch's side by side in an out-of-tree vitest probe and compared the whole view object (every field, JSON) after every prefix of 15 sequences: normal two and three calls (closing in reverse), a follow-up closed `empty` after its search errored, a non-fatal error mid-Act, a guard refusal, a clarifying question, a fatal error mid-Act and after Act, a cancelled run mid-Act, a plan with no calls, a late start, a partial skip, all calls skipped, start ids not in the plan, and a listing token mid-Act.
- Reproduction: 13 of 15 sequences identical at every prefix and in every field, including `stopEnabled`. Two differ, and only in `activeStep` and `reachedSteps`: `partial_skip` after `tool_result(c1)` dev=Act br=Write (the intended fix), and `late_start` (plan c1,c2; start c1; result c1; start c2) after `tool_result(c1)` dev=Act br=Write, then both Act on `tool_start(c2)`. That second one is the only place the branch shows something worse: Write lights, then goes back to Act.
- Can the live backend produce the late start today: only act_node writes `tool_start`/`tool_result` (grep of `src/`), the graph has no edge back into `act`, every start is written before the first `_gather_planned_calls`, a concrete follow-up keeps its admitted `call_id`, `usePacedEvents` releases prefixes and never reorders, and Stop slices a prefix. The one path is `emit_live`'s except branch failing for a single start frame, which delivers it at node return. I did not find a way to trigger that.
- NOT FIXED (accepted as unreachable by the brief; recorded for completeness)

### V-19-03: The card 19 test-queries line sits inside query 98's Stop list
- Severity: unsure (placement, not accuracy)
- What: the new line in `testing/Test_queries_and_workflows.md` (line 1161) is an instruction ("Type query 98's question ... and watch the progress steps") placed in query 98's "What you should see" list, between two Stop bullets ("No answer appears from the stopped search" and "Left alone, Stop turns grey"). Query 98 is the Stop card (card 58).
- Accuracy, checked against my probe: the line names something the owner can type (query 98's BRCA1 question) and see. On normal runs the Write step lights only on the last result and never goes back to Act (`normal_two`, `normal_three_reverse_close`, `followup_closed_empty` above, identical on develop and branch). It says plainly that the skipped-search case is checked only by the frontend test, which is honest and matches A-19-07.
- Why it matters: a retester reading the Stop card may skip or misread a progress-steps check filed under it. Low cost either way.
- NOT FIXED

## Checklist

| Item | Result | How |
|---|---|---|
| J-19-02 / A-19-02 backend test exists, passes, bites | Present; green unmutated; red under my late follow-up start mutation (`assert 21 < 9`), the only test of 81 in the three files to go red; restored, diff empty | Ran |
| A-19-04 block comment | Now says only started calls count and names the backend test; matches the code | Read |
| J-19-03 / A-19-07 test-queries line | Made, runnable, accurate for normal runs (V-19-03 is placement only) | Read, checked against probe |
| J-19-03 / A-19-07 test comment | Made, but contradicts its fixture's layers (V-19-01) | Read |
| Hook, develop against branch, 15 sequences, every prefix, every view field | Differs only in partial skip (intended) and late start (J-19-01, unreachable today) | Ran (out-of-tree vitest probe) |
| `npx vitest run` (whole frontend) | `Test Files 66 passed (66)`, `Tests 608 passed (608)` | Ran |
| `npx tsc --noEmit -p .` | exit 0, no output | Ran |
| `ruff check` | `All checks passed!`, exit 0 | Ran |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | exit 0, `Skipped 2 files` | Ran |
| pytest breadth_wiring, phase_4_16_premise, layer_handoff | `81 passed` | Ran |

Read only, not run: the stop path in `App.tsx` (`activeStep={stopped ? null : step}`), which this change does not touch; that `emit_live`'s per-frame failure path cannot be triggered in practice. Probe files lived in the session scratchpad, outside the checkout. `graph.py` was restored with `git checkout`.

A-19-03 (every planned call skipped stays on Plan) is the same on develop (`all_skipped` above) and is card 108; not counted.

V-19-01 sits inside a fix made in this card's fix round. It is a test comment with no effect on what a person sees.

Verdict: MERGE (nothing worse than develop for a person using the product on any sequence the live backend produces today; J-19-02 and A-19-04 done; the wording fix is done for the test-queries line but the test comment is inaccurate, V-19-01, minor, comment only).
