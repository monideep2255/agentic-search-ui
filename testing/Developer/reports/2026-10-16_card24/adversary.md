# Card 24 adversary report

Adversary round, dial 2, against `3f6392e3`. Probes: a throwaway App-level vitest file in a scratch worktree (same mocks as `App.depthToggle.test.tsx`) and Playwright. Nothing was fixed.

## Findings

### A-24-01: the switch (and "Ask again") is offered on a refused answer and on an asked-back answer
- Severity: major
- What: the strip draws whenever `meta || outcome` is set, so the Plain language / Researcher switch appears on an off-topic refusal and on a clarifying question. Neither answer can differ by mode: the refusal is decided before mode matters and the ask-back asks the same thing. The cost line then offers to spend a search on it.
- Reproduction: App-level probe. Stream `guard {passed:false, category:"off_topic"}` then `done {trust_outcome:"refuse"}`. After landing, the screen reads "Outside biomedical research ... Plain languageResearcherShow work" and `getByRole("group", {name:/answer depth/i})` is present (printed `P4 refused: group present true`). Same with a `think` event carrying `clarifying_question: "Which one do you mean?"`: `P5 askback: group present true`.
- Why it matters: a person who clicks the switch on a refusal is told "It counts as one new search" and, if they confirm, spends one to get the same refusal. For a guest that is one of five daily searches.
- NOT FIXED

### A-24-02: at "(0 left today)" the line still offers "Ask again", and the refusal folds the answer away
- Severity: minor
- What: with a counted guest at zero left, the line reads "...counts as one new search (0 left today)." with a live "Ask again". The build report admits the server refuses it. `ask()` has already archived the answer into the thread, set `depth` to the new mode and cleared the run before the refusal arrives.
- Reproduction: probe with `getAllowance` and `mintGuest` returning used 5, total 5. Line text printed: `Ask this question again in Researcher? It counts as one new search (0 left today).Ask againCancel`. Then `createRun` rejected with a 429 `anon_daily_cap_reached` ApiError: the live answer's strip and switch are gone (`group present: false`), the old answer shows folded under "Show answer", and a failure banner sits under it. Last probe printed the banner as the raw reason `anon_daily_cap_reached` only because my mock passed that string as the message; the real copy comes from `DAILY_CAP_COPY` and I did not check it renders.
- Why it matters: the person is invited to press a button that cannot work, and the answer they were reading collapses when it fails. Hiding or disabling "Ask again" at 0 would be the honest form.
- NOT FIXED

### A-24-03: after clicking Researcher then Plain language, the line for Researcher stays up with Plain language lit
- Severity: minor
- What: clicking the mode already shown is a no-op, so the held mode is not cleared. The cost line keeps asking about the other mode, with nothing changed on the switch.
- Reproduction: land a Plain language answer, click Researcher (line appears), click Plain language. Printed: `P3 line after Researcher then Plain: Ask this question again in Researcher? It counts as one new search (5 left today).Ask againCancel pressed plain: true researcher: false`.
- Why it matters: the person who clicked back to say "no, stay in Plain" still has an Ask-again button asking about Researcher. Only Cancel clears it. No search is spent.
- NOT FIXED

### A-24-04: the switch shows App's last-chosen depth, not the depth the answer on screen was asked at
- Severity: major
- What: `depthValue={depth}` reads the single App-wide `depth` state. Any later writer moves the lit button without a new run: the `GET /auth/me` seed (`setDepth(me.audience_depth)`), which also reruns on every access-token rotation (every 12 minutes while signed in), and `ask()` itself, which calls `setDepth(chosenDepth)` before the run is accepted. The answer carries no depth of its own. The switch's own no-op guard (`option === shown`) then compares against the wrong mode too: the mode the answer really is can be offered as the "other" one, and a spend would re-run the same mode.
- Reproduction: signed-in App probe, `fetchMe` held pending. Log in, ask at the default depth, answer lands. Printed `P7 asked at plain_language`. Then `fetchMe` resolves with `audience_depth: "researcher"`. Printed `P7 plain pressed false researcher pressed true`. The Plain language answer is on screen with Researcher lit; clicking Plain language now opens "Ask this question again in Plain language?" for the mode already read.
- Why it matters: this is the "switch shows the wrong state" failure. Narrow in time on first load (needs a slow `/auth/me`), but the 12-minute rotation re-seeds from the server, which on normal use equals the last query's depth, so the common path is correct and only a race breaks it. I did not test the rotation path.
- NOT FIXED

### A-24-05: the cost line's number can lag one search behind the account menu's source while the post-run allowance refresh is in flight
- Severity: minor
- What: for a guest the count is refreshed by a fire-and-forget `getAllowance` after `createRun`. Until it returns, both the line and the account menu read the pre-run count. The line is built from the same state as `dailyLimitPhrase` so the two always agree with each other, but both can be one too high, and the line is a promise about this one decision.
- Reproduction: guest probe, `getAllowance` held pending, one answer landed, click Researcher. Printed `P8 line (refresh pending): ...counts as one new search (5 left today).` After the refresh resolves with used 1 of 5, the same open line re-renders to `(4 left today)`.
- Why it matters: the number is wrong for the seconds the refresh takes, and only on a slow call. The line does self-correct. The signed-in line has no number and so cannot be wrong. Unsure whether this is worth acting on.
- NOT FIXED

## Probed and clean

- Double click on the switch: one line, no run (posts stayed 1). Enter and Space on the focused switch: line only, no run.
- Double click on "Ask again": exactly one new POST, at `researcher` (browser, 1280 and 390).
- Cancel removes the line (count 0). After the new answer lands the line is gone and the switch is not drawn while the run is in flight.
- The switch is not drawn on a reopened saved answer (a separate screen).
- After a switch at 1280 and 390: sources, tables, follow-up chips, feedback, Show work all present, no sideways scroll (1280/1280 and 390/390), axe on the whole page returned no violations. Screenshots kept in the scratch folder, not committed.
- Not covered: the real server's refusal at zero left; the 12-minute token rotation path of A-24-04.

Verdict: FAIL on A-24-01 and A-24-04 (major). The others are minor or unsure.
