# Guardrail design build: cards 84 and 72

The builder's record for steps 1 and 3 of `design.md` in this folder, accepted by the owner on 2026-10-08. Step 2 (host routing) is parked and not built here. Step 4 is kept by changing nothing in the topic check or the rate-limit handling.

- Branch: `fix/card84-72-guardrail`
- Base: `c916cfa30f59802dfd85c81ef7ba39bdcfc2b263` (origin/develop)
- No live model calls; no model credit spent.

## Table of contents

- [Tickets and commits](#tickets-and-commits)
- [Finding IDs, where each is fixed and tested](#finding-ids-where-each-is-fixed-and-tested)
- [Deviations from the design and the brief](#deviations-from-the-design-and-the-brief)
- [Findings while building](#findings-while-building)
- [Test runs](#test-runs)
- [Learnings](#learnings)

## Tickets and commits

| Ticket | Step | Commit | Status |
|---|---|---|---|
| 1 | Step 1: plain words when the guardrail fails | pending | built, tested |

## Finding IDs, where each is fixed and tested

| Finding | What a person meets | Fixed in | Tested by |
|---|---|---|---|
| F-72-V05 | "In a moment" for a guardrail failure; a long wait read as thousands of seconds | `frontend/src/hooks/useRunView.ts`, `guardrailFailure` | `useRunView.retryAfter.test.ts`, "a wait past two minutes reads in whole minutes" and "a double timeout reads the plain words" |
| F-84-A01 | A wait that has passed told as if the person should retry into a limit | same | "a wait that has passed, or none named, never says to wait" |
| F-84-A02 | "About 86400 seconds" | same, minutes past two minutes | "a wait past two minutes reads in whole minutes" |
| F-84-A09 | Every passing failure told to wait; "wait passed" and "none named" not told apart | same: only `source === "guardrail"` changes, and both 0 cases read the plain "Try asking again." | "every other failure keeps its own words" and "a wait that has passed, or none named" |
| F-4.8-A-15 | Backend text on screen | same: only `source`, `error_class` and `retry_after_s` are read | "never renders the backend's own message" |

## Deviations from the design and the brief

- Step 1, no backend change: on develop the guardrail sends `retry_after_s: 0` on every step error (`core/graph.py` `_step_error_kwargs`, and the unusable-verdict dict), so today a person always reads the plain words. The "about 20 seconds" wording is ready for the day a guardrail rate limit carries its wait; sending it is a backend change outside this card's fence and outside step 4's "leave the rate-limit handling as develop has it".
- Step 1, minutes only: the design says "in minutes past two minutes", so a day reads "about 1440 minutes". No hours arm was added.

## Findings while building

- None yet.

## Test runs

- `npx vitest run src/hooks/useRunView.retryAfter.test.ts`: 9 passed. Mutations: the guardrail branch disabled gave "6 failed | 3 passed"; the branch read for every source gave "1 failed | 8 passed". Restored after each.
- `npx vitest run src/hooks/`: "Test Files  11 passed (11)", "Tests  78 passed (78)".
- `npx tsc --noEmit -p .`: exit 0.

## Learnings

- None yet.
