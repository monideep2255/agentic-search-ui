# Card 24 judge report, pull request 245

Judge, dial position 2, one round. Diff under review: `git diff bce08af9...3f6392e3`. Worktrees: `<scratchpad>/judge24/j24` at 3f6392e3, `<scratchpad>/judge24/j24dev` at bce08af9.

## Findings

### J-24-01: The guest cost line states a per-guest "left today" count the server no longer enforces and the rest of the app no longer shows
- Severity: major (inherited from the card's spec and its owner-approved wording; the build follows the spec exactly)
- What: for a guest, `depthConfirmCopy` (`App.tsx`) renders "(N left today)" from `Math.max(allowance.total - allowance.used, 0)`. On the server, `GET /v1/allowance` returns for a guest `used=runs_used, total=FREE_RUN_ALLOWANCE (5), counted=True` (`adapters/web_sse/app.py` lines 815 to 820), but since Set 1 (R1, R3, 2026-09-12) `spend_one_anonymous_run` advances `runs_used` with no ceiling ("the guest's counters are advanced with no ceiling, so this function never returns EXHAUSTED", `data/guest_sessions.py`), and `POST /v1/query` no longer returns `guest_allowance_exhausted` (app.py line 1378). `runs_used` is a lifetime count on a 7-day guest identity, not a daily one. The rest of the UI deliberately shows a guest no count at all: `App.tsx` home footer comment "Set 1 (R2, 2026-09-12): no guest dots. There is no per-guest allowance to show."
- Reproduction: read the three code paths named above at 3f6392e3. Consequence by arithmetic: a guest who has asked 2 questions sees "It counts as one new search (3 left today)."; after 5 questions, "(0 left today)", and "Ask again" then succeeds anyway because no per-guest refusal exists. The spec's own "Not covered" premise ("the server refuses it with the existing daily-limit refusal") is false for the per-guest number; the only refusals are the system-wide and per-source anonymous caps, which this line never names.
- Why it matters: from the user's chair this is a confident wrong number on the one sentence this card adds, the "confident wrong record is worse than a missing one" rule. A guest is told a limit that does not exist and a count that is not daily, and nowhere else in the app sees it. Needs the owner: the approved wording rests on a guest allowance retired on 2026-09-12. Candidate fix: treat `kind === "guest"` like signed-in ("It runs as one new search."), or name `blocked_reason` when present.
- NOT FIXED

### J-24-02: Focus is dropped to the page body after "Cancel" and after "Ask again"
- Severity: major (accessibility; the brief names focus after confirm and cancel)
- What: both buttons on the confirmation line unmount themselves on click, and nothing moves focus. `document.activeElement` becomes `<body>`.
- Reproduction: judge probe `judgeProbe24.test.tsx` (in the judge's own worktree, not committed), `AnswerScreen` with `onDepthChange`, `depthValue="plain_language"`; click Researcher, click Cancel. Printed: `PROBE focus after Cancel -> BODY:Q?✓ Answered1 toolPlain langua`. Same for Ask again: `PROBE focus after Ask again -> BODY:...`.
- Why it matters: a keyboard or screen-reader user who presses Cancel is thrown to the top of the document and must tab back through the top bar, rail and heading to reach the answer again. Expected: focus returns to the Researcher button (or the group) after Cancel; after Ask again, to the new turn's heading or the progress.
- NOT FIXED

### J-24-03: Keyboard order puts "Show work" between the switch and the line it just opened; Escape does not close the line
- Severity: minor
- What: with the line open, Tab from Researcher goes to Show work, then Ask again, then Cancel. Escape leaves the line open.
- Reproduction: judge probe, focus Plain language, Tab, Enter, Tab x4. Printed order: `Plain language, Researcher, (Enter: line=true), Show work ▾, Ask again, Cancel, citation-1`. `PROBE line open after Escape -> true`.
- Why it matters: the question just raised ("Ask again in Researcher?") is not the next stop; a keyboard user passes an unrelated control first. Small, but it is the new control's whole interaction.
- NOT FIXED

### J-24-04: While the line is open, the switch still shows the old mode pressed and clicking it does not close the line
- Severity: unsure (the spec says clicking the shown mode does nothing; this is the case the spec did not consider)
- What: after clicking Researcher, `aria-pressed` stays false on Researcher and true on Plain language; clicking Plain language (the natural "never mind") leaves "Ask this question again in Researcher?" open.
- Reproduction: judge probe. Printed: `PROBE line open after clicking shown mode while held -> true Researcher pressed: false`.
- Why it matters: a person who changes their mind by clicking back sees nothing happen. Owner call whether that click should act as Cancel.
- NOT FIXED

### J-24-05: For a signed-in reader, the 12-minute session rotation flips the switch back to the saved mode under a Researcher answer, and the next follow-up runs in the old mode
- Severity: major
- What: `depthValue={depth}` is `App`'s `depth` state. The `fetchMe` effect keyed on `[token]` (`App.tsx` around line 660) calls `setDepth(me.audience_depth)` every time the token changes, and the keep-alive effect rotates the token every 12 minutes (`ROTATE_EVERY_MS`). Nothing saves the strip's choice to the profile, so after the next rotation `depth` returns to the saved mode. The new `App.tsx` comment's claim, "the strip's toggle can never show a mode this run was not actually asked at", is false.
- Reproduction: judge probe `App.judgeProbe24.test.tsx` (judge worktree only). Signed in through the real login gate, saved mode `plain_language`; ask, land, Researcher, Ask again, land; then invoke the captured 12-minute interval callback (refresh resolves a new pair, the stream replays the Researcher answer); then ask a follow-up. Without rotation: `PROBE after switch landed, strip: Plain language=false,Researcher=true` and `PROBE rotate=false follow-up depth: researcher`. With rotation: `PROBE after rotation, strip: Plain language=true,Researcher=false` and `PROBE rotate=true follow-up depth: plain_language`.
- Why it matters: the person is reading a Researcher answer while the switch says Plain language. Clicking "Researcher" then offers to spend a new search on the mode they are already reading, and a follow-up typed after a coffee break silently comes back in Plain language, breaking "later follow-ups use the new mode" from the card's own words. The root (`fetchMe` resetting depth on rotation) predates this card, but this card is what makes it visible and what promises the opposite. The PR's tests never sign in, so nothing covers it.
- NOT FIXED

### J-24-01 addendum: run evidence
- Judge probe, guest, `getAllowance` = `{kind: "guest", used: 7, total: 5, counted: true, blocked_reason: null}`: `PROBE used7/5 line: Ask this question again in Researcher? It counts as one new search (0 left today).` and `PROBE other 'left' text in page: null`, so no other surface shows a guest any count to match.
- First-time guest, mint response `used: 4, total: 5`, allowance refresh never resolving: `(1 left today)`. A guest with `used: 7` exists only because the server no longer caps per guest.
- Signed in (`counted: false`): `It runs as one new search.` with no number, as specified.

### J-24-06: After a switch, the conversation shows the same question twice with nothing saying which answer is Plain language and which is Researcher
- Severity: minor (unsure; no design draws the folded pair)
- What: `PreviousTurn` carries `question` and `meta` but no mode, and the live strip's switch is the only place a mode is shown. The folded turn above repeats the identical question heading with no mode label; the switch itself is never drawn on a folded turn.
- Reproduction: judge App probe, ask, land, Researcher, Ask again, land: `PROBE threads: 1`, and both turns carry the heading "Which diseases are associated with BRCA1?". `grep` of `PreviousTurn` (AnswerScreen.tsx line 904) finds no depth or mode field.
- Why it matters: the card's point is comparing the two readings. A person scrolling up sees two answers to one question and has to infer which is which.
- NOT FIXED

### J-24-07: The switch's corner radius is 8 px, the mockup and the design system draw 4 px
- Severity: minor (design)
- What: `DepthStripToggle` uses `borderRadius: 1`, which MUI multiplies by the theme's `shape.borderRadius: 8`. `Main.dc.html` line 55 draws `border-radius: 4px`, the design system's `.depth` uses `var(--r-sm)` = 4px, and the card's spec says "a 4 px radius". Same drift exists on the home `DepthControl` (pre-existing), which the port copied.
- Reproduction: judge probe rendering `DepthStripToggle` inside the app theme: `PROBE strip toggle border-radius: 8px`.
- Why it matters: small visual mismatch with the approved mockup; one token (`borderRadius: 0.5`) away.
- NOT FIXED

### J-24-08: Two names for one control: "Answer mode" on the home page, "Answer depth" on the strip
- Severity: minor (unsure)
- What: the home `DepthControl` shows and announces "Answer mode" (`aria-label="Answer mode, audience-level depth"`); the strip's group announces "Answer depth".
- Reproduction: `DepthControl.tsx` lines 163, 171 and 280 at 3f6392e3.
- Why it matters: a screen-reader user hears the same Plain language / Researcher choice under two different names.
- NOT FIXED

### J-24-09: The "held mode clears when the question or mode changes" behaviour has no test; deleting it leaves every test green
- Severity: minor
- What: the build report claims "The held mode clears when the answer's mode or question changes" (`useEffect(() => setHeldDepth(null), [depthValue, question])` in `AnswerBody`). No test pins it.
- Reproduction: judge mutation, that `useEffect` replaced with a comment in `AnswerScreen.tsx`; ran `App.depthToggle.test.tsx`, `AnswerScreen.depthToggle.test.tsx`, `DepthControl.test.tsx`, `App.test.tsx`, `AnswerScreen.thread.test.tsx`: `Test Files 5 passed (5)`, `Tests 66 passed (66)`. Restored, `cmp` clean.
- Why it matters: the live `AnswerBody` is one instance across running and landed (phase 8.7), so without the reset a person who opens the line and then asks a typed follow-up would land on the new answer with "Ask this question again in Researcher?" still open, now pointing at a different question. One small test closes it.
- NOT FIXED

### J-24-10: Judge mutation that went red as expected (no defect)
- Severity: none, evidence only
- Mutation: `App.tsx` `onDepthChange={(next) => void ask(searchView.question, next, false)}` (re-run starts a new conversation instead of joining as a follow-up).
- Result: `App.depthToggle.test.tsx` "dispatches a fresh run at the OTHER depth..." failed; `Tests 1 failed | 21 passed (22)`. Restored, `cmp` clean, `git status` shows no tracked change.

### J-24-11: The e2e "exactly one new POST" check passes as soon as the second POST arrives; a later third is never seen
- Severity: minor (test strength)
- What: `answer-depth-switch.spec.ts` asserts `await expect.poll(() => posts.length).toBe(2)` and stops. A double dispatch arriving a few milliseconds later would pass.
- Reproduction: read at 3f6392e3, spec lines near the end of the test. The unit-level double-click is safe: judge probe `user.dblClick` plus `fireEvent.click` on "Ask again" gave `PROBE onDepthChange calls after dblclick+click -> 1`.
- Why it matters: the spec's stated property is "exactly one". Wait for the answer to land, then assert the count is still 2.
- NOT FIXED

### J-24-12: The switch is offered on refused and failed answers too
- Severity: unsure (read only, not probed)
- What: `AnswerBody` renders the switch whenever `onDepthChange` is passed and the strip exists (`meta || outcome`), with no check of `refusal`, `failure` or `capMessage`. `App` passes `onDepthChange` to every landed live answer.
- Reproduction: read only, `AnswerScreen.tsx` status strip block at 3f6392e3.
- Why it matters: re-asking a refused or cap-blocked question in Researcher spends a search for the same refusal. Owner call whether the switch should hide there.
- NOT FIXED

## Gates and runs by the judge

| Check | Result |
|---|---|
| `npm run build` | exit 0, only the existing chunk-size warning |
| `npx vitest run --maxWorkers=2` | 71 files, 649 tests passed |
| Develop regression set (16 files: cards 22, 23, 71, 102, 112 history, phase 8.7 listing-first and thread, stop and replay, saved answers) on base bce08af9 and head 3f6392e3 | 188 passed on both; passing test names identical |
| Playwright `answer-depth-switch.spec.ts` and `accessibility.spec.ts`, judge config on separate ports, no server reuse | 12 passed |
| `ruff check` (no path) | All checks passed |
| isort, gate 2 command | exit 0 |
| Mutation: re-run with `continuesThread=false` | red, 1 test; restored |
| Mutation: held-mode reset removed | green, survives (J-24-09); restored |

## Verified by probe versus read

- Probed: cost line shows and runs nothing; Ask again runs once with Researcher; double click runs once; signed-in form has no number; guest numbers including 0 and over-cap; follow-up after a switch uses Researcher without rotation and Plain language after a rotation (J-24-05); old answer folds into the thread; focus after Cancel and Ask again (J-24-02); tab order and Escape (J-24-03); computed radius (J-24-07); aria-live box mounted empty and filled on hold; axe scan of the strip at 1280 and 390 (author's spec, run by the judge).
- Read only: the server's guest allowance semantics (J-24-01, code read, no live server call); conflict resolution in `AnswerScreen.tsx` (diff read, plus the regression set run); refused-answer behaviour (J-24-12); the 390 wrap from the build's own screenshot, not regenerated.
- No finding sits inside a fix made during this phase's review rounds; this is the first judge round on the card.

## Verdict

FIX FIRST. The mechanics hold: nothing runs before confirm, confirm runs exactly once at the other mode, cancel and same-mode do nothing, the switch is gone while a run is in flight, and develop's answer-screen behaviours pass unchanged. Two things fail the card's own words. J-24-01: the guest's "(N left today)" is a number the server stopped enforcing on 2026-09-12 and that no other surface shows, so it needs the owner. J-24-05: for a signed-in reader, the switch and the next follow-up go back to the saved mode at the next 12-minute rotation. J-24-02, focus dropped to the page, should go in the same round.
