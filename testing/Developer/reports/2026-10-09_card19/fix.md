# Card 19 fix round

Findings fixed: J-19-02 / A-19-02, A-19-04, J-19-03 / A-19-07. A-19-03 is not fixed (needs a new backend event, own card).

## J-19-02 / A-19-02: backend test pins start-before-result

- Added `test_every_tool_start_comes_before_the_first_tool_result` to `tests/system_03_search_agent/core/test_breadth_wiring.py`.
- It runs the gene question, asserts follow-up calls ran (fetch and summary actions exist, so it cannot pass vacuously), asserts 13 starts and 13 results, then asserts the last start precedes the first result.

Red, with `act_node` mutated so the follow-up starts are written after the first stage's gather:

```
>       assert max(starts) < min(results), kinds
E       AssertionError: ['tool_start', 'tool_start', 'tool_start', 'tool_start', 'tool_start', 'tool_start', ...]
E       assert 21 < 9
E        +  where 21 = max([0, 1, 2, 3, 4, 5, ...])
E        +  and   9 = min([9, 10, 11, 12, 13, 14, ...])
FAILED tests/system_03_search_agent/core/test_breadth_wiring.py::test_every_tool_start_comes_before_the_first_tool_result
1 failed, 47 deselected in 2.49s
```

Green, after `git checkout -- src/system_03_search_agent/core/graph.py` (graph.py unchanged, empty diff):

```
.                                                                        [100%]
1 passed, 47 deselected in 2.25s
```

## A-19-04

The "WRITE BEGINS WHEN ACT ENDS" comment in `frontend/src/hooks/useRunView.ts` now says only started calls count, and names the backend test above. Comment only.

## J-19-03 / A-19-07

- `frontend/src/hooks/useRunView.writeState.test.tsx`: comment now says Think and Plan had used the 20-call budget, so act_node admitted only graph (Layer 1) calls and skipped every Layer 2/3 call.
- `testing/Test_queries_and_workflows.md` (card 19 line under query 98): replaced with a runnable line, and says the skipped-search case is checked by the frontend test.

## Checks

- Backend (breadth_wiring, phase_4_16_premise, layer_handoff): `81 passed in 10.53s`
- `npx vitest run src/hooks`: 11 files passed, 80 tests passed
- `npx tsc --noEmit -p .`: no output, exit 0
- `ruff check`: All checks passed!
- `isort --check-only --diff src tests services tracker alembic .claude .github`: exit 0, no diff (Skipped 2 files)
