# Card 19 build: Act completes without waiting on calls that never started

Built on branch `fix/card19-act-complete`, cut from `develop` at `b01dee92`, after phase 8.7 merged.

## What a person sees

- Before: a question that plans more than 20 live lookups left the progress steps on Act for the whole writing wait, 2 to 22 seconds.
- After: the steps move to Write as soon as every lookup that started has handed back.

## What changed

| File | Change |
|---|---|
| `frontend/src/hooks/useRunView.ts` | In the `actComplete` block, the ids to close are the ids that opened. Planned ids that never reached the wire no longer hold Act open. Nothing outside that block changed. |
| `frontend/src/hooks/useRunView.writeState.test.tsx` | One new test: the plan lists two calls, only one starts and returns, and the steps show Write. |
| `testing/Test_queries_and_workflows.md` | One line under query 98 saying what a person sees. |

## Why it is safe

`act_node` writes every start frame before any call runs, so a planned id with no start frame at the moment a result lands will never start.

## Proof

- Base: `b01dee92b2981afce665ecf5949e693664cea3fe`.
- `npx vitest run src/hooks`: 11 files passed, 80 tests passed.
- `npx tsc --noEmit -p .`: exit 0, no output.
- Bite check: restoring the old condition (planned ids added back) turned the new test red ("1 failed | 7 passed (8)"). Restoring the fix gave "8 passed (8)".

## Deviations

None. The full suite was not run, as instructed.
