# Card 136 slice S3: the searches drawer closes on a phone

What the person sees now: on a phone, picking a past search or tapping "+ New search" in "Your searches" closes the drawer, so they see the answer or the empty question screen. On a computer the rail behaves as before.

## Change

- File: `frontend/src/components/answer/FollowUp.tsx` only. App.tsx is untouched, because "+ New search" is rendered inside `HistoryRail`.
- A small `closeAfterPick` helper in `HistoryRail` calls the existing `onCollapse` only when `isNarrow` is true. `isNarrow` is the component's own `useMediaQuery(theme.breakpoints.down("md"))`, the same test that decides it is a drawer.
- A row click calls `onOpen`, then `closeAfterPick`. "+ New search" calls `onNewSearch`, then `closeAfterPick`.
- Focus: no new close path. It goes through the same `onCollapse` that the backdrop, Escape and the close button use.

## Tests

- File: `frontend/src/components/answer/HistoryRail.phone.test.tsx`, three new cases.
- Narrow: a row pick calls `onOpen("q-1")` and `onCollapse` once.
- Narrow: "+ New search" calls `onNewSearch` and `onCollapse` once.
- Wide: row pick and "+ New search" call their handlers and never `onCollapse`.
- Mutation: replacing the narrow check with `false` turned 2 of 8 red. Restored, green.
- Results: `npx vitest run src/components/answer/` 35 passed (5 files); `npx tsc --noEmit -p .` clean.
