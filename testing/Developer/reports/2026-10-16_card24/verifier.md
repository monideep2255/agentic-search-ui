# Card 24 fresh verifier report

Verifier: fresh context, dial position 2, 2026-10-16. Subject: pull request #245, `git diff bce08af9...438a9b95`. Findings are written as they are established.

## Findings

### V-24-01: The branch does not merge cleanly into origin/develop: a text conflict in the test queries document
- Severity: minor (documentation only, no code conflict)
- What: develop moved 11 commits past the branch base `bce08af9` (card 17 merged, adding query 113 at the same spot). Both sides insert a new section after line 440 of `testing/Test_queries_and_workflows.md`.
- Reproduction: `git merge-tree --write-tree origin/develop 438a9b95` (origin/develop = `2903ce43`) exits 1 with `CONFLICT (content): Merge conflict in testing/Test_queries_and_workflows.md`. No other file conflicts. Resolution is to keep both sections, 112 before 113.
- Why it matters: the pull request cannot merge as is; the resolver must keep both query sections or a person's retest text is lost. The branch also adds no row to the document's feature table for card 24, where develop's card 17 added one.
- NOT FIXED

### V-24-02: A folded answer asked at a stored legacy mode is labelled with the raw value "clinical_brief"
- Severity: minor (reachable only for an account whose last search came from the CLI, MCP or GraphQL at `clinical_brief` or `deep_technical`)
- What: `depthModeLabel` falls back to the raw enum when the mode is not one of the two `AUDIENCE_MODE_OPTIONS`. The server still stores and returns all four modes (`auth/preferences.py` `_ALLOWED`), the profile seed puts them into `depth`, and `ask` sends and records them. The switch on such an answer lights Plain language (via `displayedMode`), although the request was `clinical_brief`, which the server itself folds to "researcher" (`_WIRE_DEPTH_BY_STORED` in `adapters/web_sse/app.py`); clicking Plain language is then a no-op, so the switch cannot offer a true Plain language answer.
- Reproduction: verifier App-level vitest probe (`App.vprobe24.test.tsx`, verifier worktree only), signed in with `fetchMe` returning `audience_depth: "clinical_brief"`; ask, land, type a follow-up. Printed: `VPROBE P10 sent clinical_brief pressed plain true` and `VPROBE P10 follow-up sent clinical_brief folded label clinical_brief`.
- Why it matters: a person sees an internal identifier, "clinical_brief", as the label over their earlier answer, and a switch that says Plain language for an answer the server treats as researcher-facing. Develop shows no label and no switch, so the raw label is new text; the mislit home control is pre-existing.
- NOT FIXED

### V-24-03: With no mode held, the status strip carries about 10px of empty space from the always-mounted live region; the answer starts 19px lower than on develop
- Severity: minor (layout, unsure whether a person would notice)
- What: the empty `aria-live` box is a 100%-wide flex item, so it opens a second flex line; its `mt: -1.25` does not fully cancel the 10px row gap. The status strip's row is 41px tall while its tallest child (the switch) is 31px.
- Reproduction: verifier Playwright probe (local mock stack, own ports, a throwaway example.com account), same scripted answer on both trees, height of the bordered status strip with no line open. Develop `2903ce43`: `1280 V1 strip height line closed 50.59375`, `390 V1 strip height line closed 103.625`. Branch `438a9b95`: `1280 V1 strip height line closed 69.625`, `390 ... 122.8125`. Branch parts at 1280: `row 41 gap 10px kids ✓ Answered6.:205+22 ; Plain langua:200+31 ; :236+0 ; Show work ▾:205+21`.
- Why it matters: about half of the added height is the switch, which the design draws. The other half is blank space under the strip on every landed answer, there only to hold an empty announcement box. It is cosmetic, and nothing a person reads is lost.
- NOT FIXED

### V-24-04: A-24-02 is only half closed: when the guest cap is reached, "Ask again" still folds the answer away behind the refusal
- Severity: unsure (the same thing happens on develop when a person types a follow-up at the cap, so this is not worse than develop)
- What: the fix round closes A-24-02 by removing the "(0 left today)" count. The second half of A-24-02, that a refused "Ask again" folds the answer the person was reading, is unchanged. The server's system-wide guest pause still exists, and the line still promises "one new search" when none can run.
- Reproduction: verifier App-level vitest probe, guest, an answer landed, Researcher, Ask again, with `createRun` rejecting 429 `anon_daily_cap_reached`. Printed: `VPROBE P6 createRun 2 group false thread true label Plain language` and the main text containing `...Show answer✓ Answered...Guest searches are paused for today...`. The earlier answer is folded under "Show answer", labelled Plain language, and the live turn shows the pause message.
- Why it matters: a guest at the system-wide pause clicks Ask again and the answer they were reading collapses. They must click "Show answer" to get it back. This is develop's follow-up behaviour, so I raise it as a closure claim that went less far than stated, not as a regression.
- NOT FIXED

## Checks

| Check | Result | How |
|---|---|---|
| 1. Fix round closures | Re-derived for J-24-01 to J-24-09, J-24-11, J-24-12 and A-24-01, A-24-03 to A-24-05. A-24-02 is half closed (V-24-04). J-24-06's label shows a raw value for legacy modes (V-24-02) | Own vitest App probes, own Playwright probes, own mutations |
| 2. No search without confirm | Holds. A double click on the switch, Enter or Space on the switch, Escape, Cancel, a click on the lit mode, a page reload with the line open, a typed follow-up with the line open, and a refused or asked-back answer all spend nothing. Ask again by a double click, by two Enter presses, or by a double click plus two more clicks spends exactly 1 | vitest P1 to P9 (`createRun` 1, then 2), Playwright V1 to V4 at 1280 and 390 (`posts after reload 1`, `posts after dblclick Ask again 2` after a 3 s wait) |
| 3. Develop's answer-screen set | Identical. The 35 files are develop's answer, thread, stop, history, saved-answer and follow-up tests: `files 35 total 310 passed 310 failed 0` on both trees, and the sorted name-and-status lists `diff` empty. Develop's frontend has no change since `bce08af9` | `vitest --reporter=json` on both worktrees |
| 3b. Merge into origin/develop | Not clean, a docs-only conflict (V-24-01) | `git merge-tree` |
| 4. Accessibility | Clean. `accessibility.spec.ts` gives the same 10 names passing on develop and the branch. Axe on the whole page with the line open and after the switch: `none` at 1280 and 390. Tab order goes Researcher, Ask again, Cancel, Show work, with a visible focus ring (`outline:auto 1px`). Escape and Cancel return focus to Researcher; Ask again moves it to the question heading, and it stays there after the answer lands. Group name `Answer mode, audience-level depth`, radius `4px` | Playwright, own config, ports 5491/8991 and 5492/8992, no server reuse |
| 5. Mutations | Each mutation was one change, went red, and was restored with `git diff --stat` empty. Dropping `refusalLabel` from the switch condition: 1 red. Removing `aria-live`: 1 red. Making `depthValue` read `depth`: 2 red. Removing the held-mode reset: 2 red | vitest |
| Gates | `npm run build` exit 0 (chunk-size warning only). `npx vitest run --maxWorkers=2`: `Test Files 71 passed (71)`, `Tests 669 passed (669)`. `ruff check`: `All checks passed!`. Gate 2 isort: exit 0. Author's `answer-depth-switch.spec.ts` plus `accessibility.spec.ts`: `12 passed` | Run in the verifier worktree at `438a9b95` |

## Verified by probe versus read

- Probed: every row above. Also V-24-02, V-24-03 and V-24-04. I also checked that a history item, which in the mock stack re-asks on both trees (`posts 2`, as on develop), shows the switch only on that fresh live answer.
- Read only: the server stores four modes (`auth/preferences.py`). "Run again" after a stopped run still reads `depth`, not the asked mode, as on develop. I did not probe it across a session refresh. The live app and its real model were not asked anything; all answers are scripted streams.

## Escalation note

V-24-02 sits inside a change this fix round made (J-24-06's folded mode label). It is not a regression of a develop behaviour. It is new text that shows a raw identifier only for an account whose stored mode is a legacy one.

## Verdict

PASS. Nothing a person does on the answer screen is worse than on develop. No search runs without "Ask again", and "Ask again" runs exactly one. Develop's 310 answer-screen tests pass under identical names, and the accessibility spec and axe are clean. Before merge: resolve V-24-01, the docs conflict in `testing/Test_queries_and_workflows.md`, by keeping both query 112 and query 113. Open and minor: V-24-02, inside the fix round, a raw "clinical_brief" label for legacy-mode accounts; V-24-03, about 10px of blank space under the strip; V-24-04, A-24-02 half closed, the same as develop.

### Note on V-24-01, added after the verdict
While I was verifying, someone else moved the branch head to `961497c4` at 05:34 EDT, "Merge remote-tracking branch 'origin/develop' into fix/card24-answer-depth-switch". I did not make that commit. At `961497c4` both query sections 112 and 113 are present, and `git merge-tree --write-tree origin/develop 961497c4` exits 0. `git diff 438a9b95 961497c4 -- frontend` is 0 lines, so every frontend probe above holds for the new head. V-24-01 stays filed for the closer to confirm.
