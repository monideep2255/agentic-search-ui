# Card 123 build notes: the info card stays on screen on a phone

## What changed

- File: `frontend/src/components/shell/PersonaChip.tsx`, the `PersonaInfo` card.
- Below 720 px the card now uses `box-sizing: border-box`. Before, its padding and border added 30 px to the `calc(100vw - 32px)` width, so it was wider than the screen.
- After the card lays out, a layout effect measures it and slides it sideways with a transform until it sits inside a 16 px gutter on each side. This holds wherever the icon is, and for the persona chips, the answer line, the run caption and the depth control, since they all use this component.
- At 720 px and wider the effect does nothing, so 1280 px is unchanged.

## Test

- File: `frontend/src/components/shell/PersonaChip.test.tsx`, a new describe block with three cases.
- A 390 px phone with the icon at 100 px: the card is pushed left by 84 px (fails on the old code, which sets no shift).
- A card that already fits is left alone.
- At 1280 px nothing moves.
- Result: 17 of 17 pass in the file. The type check passes. The project has no eslint config, so eslint could not run.

## Measured in a browser

A component-level render in a Vite page with the icon 220 px from the left (no backend). The number is the page scroll width minus the window width.

| Viewport | Before | After |
|---|---|---|
| 390 x 844 | 242 px overflow, card 244 to 632 | 0 px overflow, card 16 to 374 |
| 1280 x 900 | 0 px, card 244 to 554 | 0 px, card 244 to 554 |

Screenshots: `old_390.png`, `new_390.png`, `old_1280.png`, `new_1280.png` in this folder.
