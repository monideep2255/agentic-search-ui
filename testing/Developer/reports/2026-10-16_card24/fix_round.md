# Card 24 fix round

Base: `b440a222`, branch `fix/card24-answer-depth-switch`, pull request 245, clean at start. One round, dial 2. Nothing committed.

## Table of contents

- [Closed findings](#closed-findings)
- [Choices](#choices)
- [Mutations](#mutations)
- [Gates](#gates)

## Closed findings

| Finding | What changed | Test |
|---|---|---|
| J-24-01, A-24-02, A-24-05 | The line reads "It runs as one new search." for everyone. `depthConfirmCopy` and the allowance count are removed from `App.tsx` and `AnswerScreen.tsx` | `AnswerScreen.depthToggle.test.tsx` "no number for any reader"; `App.depthToggle.test.tsx` guest and signed-in forms; e2e exact line text |
| A-24-04, J-24-05 | `App` keeps `answerDepth`, set in `ask()` from the same value the request sends as `audience_depth`. The switch and follow-ups read it, not `depth`. The false comment is deleted | `App.depthToggle.test.tsx`: session refresh keeps the switch, follow-up after refresh runs in Researcher, late profile load cannot move the switch |
| A-24-01, J-24-12 | No switch when the answer has a refusal, a refusal label (how an ask-back arrives), a failure or a cap message | unit table of four cases; App-level refused answer |
| J-24-02 | Cancel and Escape return focus to the Researcher button; Ask again focuses the question heading | two unit tests |
| J-24-03, A-24-03, J-24-04 | Escape closes the line; clicking the lit mode closes it (new `onSelectCurrent` prop); the line is next in tab order after the switch | three unit tests |
| J-24-06 | Each folded answer shows its mode label, from `PreviousTurn.depth` | unit and App-level tests |
| J-24-07 | Corners 4px (`borderRadius: 0.5`) | unit test with the app theme, computed style |
| J-24-08 | Group name is the home page's "Answer mode, audience-level depth" | unit test |
| J-24-09 | Test for clearing the held mode on mode change and on question change | two unit tests |
| J-24-11 | e2e waits for the new answer, then 1 second, then asserts still two requests | mutation below |

## Choices

- Asked mode source: the depth passed to `ask()`, which is the request body's `audience_depth`. No other run field was needed.
- Tab order: the line is before Show work in the page order and `order` keeps it on its own row below. On screen Show work stays beside the switch.
- Capped answers (`capMessage`) also lose the switch, following J-24-12.
- The profile seed still sets `depth` on each refresh (the home page control); it no longer reaches the answer screen.
- The home page `DepthControl` still has 8px corners (not in this card).

## Mutations

Each by one change, red, then restored.

| Mutation | Red tests |
|---|---|
| Number added to the line | 4 (two unit, two App) |
| Cancel no longer focuses | 2 |
| Ask again no longer focuses the heading | 1 |
| Escape key check broken | 1 |
| Lit mode no longer closes the line | 1 |
| Show work moved before the line in the page | 1 |
| Switch condition ignores refusal fields | 5 |
| Folded label not rendered | 2 |
| Corners back to 8px | 1 |
| Name back to "Answer depth" | 4 |
| Held-mode reset removed | 2 |
| Switch reads `depth` | 2 |
| Follow-up reads `depth` | 1 |
| Archived turn drops its mode | 1 |
| Ask again fires a second `ask` after 400 ms (e2e) | 2 (both widths), "Expected length: 2, Received length: 3" |

## Gates

| Gate | Result |
|---|---|
| `npm run build` | passes, chunk-size warning only |
| `npx vitest run --maxWorkers=2` | 71 files, 669 tests passed |
| Develop answer-screen set (card 22, answer layout, card 102, saved answers, listing-first, thread, previous turn body) | 7 files, 81 passed; the stop and history files are in the full run |
| Playwright `answer-depth-switch.spec.ts` and `accessibility.spec.ts`, ports 5473 and 8973, no server reuse | 12 passed |
| `ruff check` | All checks passed |
| isort gate 2 (`gate02_import_order.sh`) | exit 0 |

Screenshots of the new line: `w1280_cost_line.png`, `w390_cost_line.png` (a throwaway example.com account). Test query 112 in `testing/Test_queries_and_workflows.md` is rewritten for what a person now sees.
