# Card 138 verify: ask-back link text

Fresh verifier, 2026-10-22. Branch fix/card138-ask-back-link-text, commits c464fd7c and 8a9ceb23 on origin/develop. Findings are appended as they are established.

## Findings

### F-138-V-01: the e2e spec still asserts the raw address as the link text
- Severity: major (pending a run, see below)
- What: `frontend/e2e/cite-or-refuse.spec.ts` was not updated. Lines 252 and 289 assert `toContainText(FALLBACK_LINK)` / `toContainText(UNRESOLVED_LINK)` on the refusal block, and lines 260 and 298 look up `getByRole("link", { name: FALLBACK_LINK })` / `{ name: UNRESOLVED_LINK }`. With the fix the anchor text is "Search NCBI for BRCA9" / "Search NCBI for NOTAGENE", so the address no longer appears as text and the role lookup by that name should find nothing. The comment at 255 to 258 says the assertions hold "because the anchor's visible text IS the address", which the fix makes false.
- Reproduction: `grep -n "FALLBACK_LINK\|UNRESOLVED_LINK" frontend/e2e/cite-or-refuse.spec.ts` in the worktree; run result appended below.
- Why it matters: on develop this spec passes; on the branch it should fail. That is worse than develop if CI or a release check runs Playwright.
- NOT FIXED

- Run result, F-138-V-01 confirmed: `PYTHONPATH=<worktree>/src npx playwright test e2e/cite-or-refuse.spec.ts` on the branch gives "2 failed, 1 passed". Failure 1 at `cite-or-refuse.spec.ts:252`: expected substring "https://www.ncbi.nlm.nih.gov/search/all/?term=BRCA9", received "No answer found in NCBI recordsI could not find grounded evidence for this. Try NCBI's cross-database search:Search NCBI for BRCA9". Failure 2 at `:292`, the same shape for NOTAGENE. Lines 260 and 298 (link by name) would fail next. CI does not catch this: gate 10 (`.github/gates/gate10_accessibility.sh`) runs only `e2e/accessibility.spec.ts`, so "CI is green" is not evidence for this spec. The PR template item 9 names cite-or-refuse as a required path.

- Baseline for F-138-V-01: with the anchor text set back to `{link}` (develop's rendering, scratch edit), the same Playwright command gives "3 passed". So the two failures are introduced by this branch: worse than develop.

## Break-it result
- Scratch edit: `{refusalLinkText(link)}` back to `{link}` in `AnswerScreen.tsx:1183`. `npx vitest run src/components/screens`: "1 failed | 196 passed", the failing arm "renders the NCBI fallback address as a real link on an answer-level refusal". The suite does go red.
- File restored from a byte copy; `git diff HEAD` empty afterwards, `git status --short` shows only `?? frontend/node_modules`.

## Own probes (scratch test file copied in, run, moved out; worktree left clean)
- Coverage: the backend sends every ask-back through one emit site (`core/graph.py:13982` to `14000`: token text is the question, `trust_signal.fallback_link = build_fallback_link(query.text)`). Driving `useRunView` with a think `clarifying_question` plus four options and that trust_signal, then rendering `AnswerScreen`, for GERD, Marfan and "recent papers on BRCA1": label "One more detail needed", one anchor, inside `[data-testid="answer-refusal"]`, text "Search NCBI for GERD" / "Search NCBI for Marfan" / "Search NCBI for recent papers on BRCA1", href unchanged, no "https://" anywhere in the rendered text. The only render site of `refusalLink` is `RefusalBlock` (`AnswerScreen.tsx:2065` to `2070`, reached for the live turn at 3032 and previous turns at 2762); the options render as buttons in `FollowUp.tsx:264`, with no link. Coverage of the card holds.
- Safety: `http://www.ncbi...`, `https://ncbi.nlm.nih.gov.evil.com/...`, `javascript:alert(1)//?term=X` and `https://evil.com/?term=Search` each give zero anchors and the raw string shown as text, so the R14 host check still decides. A term `<img src=x onerror="alert(1)"><b>x</b>` renders as literal text, zero img and zero b elements. No `dangerouslySetInnerHTML` anywhere in `frontend/src` outside comments and a test name.
- Long term: 460 unbroken characters give a 476-character label inside the same `wordBreak: "break-word"` span; the raw address was an equally unbroken 506 characters, so layout is no worse (read, not measured: jsdom has no layout).

### F-138-V-02: decoding the term shows invisible and direction-changing characters the encoded address neutralised
- Severity: minor, unsure
- What: `refusalLinkText` (`AnswerScreen.tsx:1063`) decodes the term and only `trim()`s it. `?term=%E2%80%AEevil` gives "Search NCBI for " followed by U+202E (right-to-left override) and "evil"; `?term=%E2%80%8B` gives "Search NCBI for " plus a zero-width space, a label that looks like it names nothing. On develop these showed as visible percent escapes.
- Reproduction: `refusalLinkText("https://www.ncbi.nlm.nih.gov/search/all/?term=%E2%80%AEevil")` returned "Search NCBI for ‮evil"; with `%E2%80%8B` it returned "Search NCBI for ​".
- Why it matters: low. The term comes from the reader's own question, and the href is unchanged, so this is self-inflicted text only. Filed because the link text is now built from decoded input.
- NOT FIXED

### F-138-V-03: no test renders the ask-back path the card is about
- Severity: minor
- What: the changed render arm (`AnswerScreen.refusal.test.tsx:145` to `151`) drives an answer-level refusal for BRCA9, not a clarification. No unit or e2e test renders a `clarifying_question` run and checks the link text, so the card's own case (GERD, Marfan) is covered only because it shares `RefusalBlock`.
- Reproduction: `grep -rn "Search NCBI" frontend/src frontend/e2e` finds only `AnswerScreen.tsx` and `AnswerScreen.refusal.test.tsx`; the clarification tests in `src/hooks/useRunView.clarification*.test.ts` assert the view, not the rendered anchor.
- Why it matters: a later change that renders an ask-back through another block would go unnoticed.
- NOT FIXED

## Commands run
- `npx vitest run src/components/screens`: 20 files, 197 tests passed.
- `npx vitest run` (whole frontend suite, what gate 8's `npm test` runs): 71 files, 671 tests passed.
- `npx tsc -b`: exit 0. `npm run build` not run.
- `npx playwright test e2e/cite-or-refuse.spec.ts`: 2 failed on the branch, 3 passed with develop's rendering (F-138-V-01).

## House text
- The diff adds no em or en dash (counted: 0 and 0). The new words "Search NCBI for <term>" and "Search NCBI" name an action, not the reader.
- Stale comment: `frontend/e2e/cite-or-refuse.spec.ts:255` to `258` still says the anchor's visible text is the address. Part of F-138-V-01.

## Verdict
- HOLD. Something is worse than develop: F-138-V-01, the cite-or-refuse e2e spec passes on develop and fails twice on this branch, and CI's gate 10 runs only the accessibility spec, so a green CI does not show it. The fix itself is right: coverage, the host check and escaping all held under my probes.
- Checked with my own probes: ask-back render path for GERD, Marfan and "recent papers on BRCA1"; host check with four bad addresses; markup term; odd and long terms; the break-it mutation; the e2e failure and its develop baseline; the unit suite and tsc.
- Only read, not run: the backend emit site (`core/graph.py:13982` to `14000`) and `build_fallback_link`'s encoding; long-term layout (jsdom has no layout); that `FollowUp` options carry no link.
- None of these findings sits inside a fix made earlier in this card's own review loop. This is the first verify round.

## Fix round, fresh verifier
- Scope: commit `7f7944b9` on `fix/card138-ask-back-link-text`, read and run against `origin/develop`. Findings are appended below as they are established.

### F-138-V-04: one unidentified failure in the screens suite on the first run, not reproduced
- Severity: unsure
- What: the first `npx vitest run src/components/screens` on `7f7944b9` reported "1 failed | 197 passed (198)" in 127 s; three reruns gave "198 passed (198)" in about 47 s. Ten other vitest processes from other worktrees were running on the machine at the time, so a timeout under load is the likely cause. I did not capture which test failed.
- Reproduction: first run tail "Test Files 1 failed | 19 passed (20) / Tests 1 failed | 197 passed (198) / Duration 127.12s"; reruns at 21:18 and after: "Tests 198 passed (198)".
- Why it matters: probably nothing about card 138. Filed because a flaky arm in this suite would make CI's green less informative.
- NOT FIXED

### F-138-V-05: the Cf strip also removes the joiners ZWJ and ZWNJ, which change how some words and emoji render
- Severity: minor (inside this fix round's change, `AnswerScreen.tsx:1066`; not worse than develop, which showed these as percent escapes)
- What: `/\p{Cf}/gu` removes U+200C (zero-width non-joiner) and U+200D (zero-width joiner). Those are format characters but carry meaning: ZWNJ is part of normal Persian spelling, ZWJ selects Devanagari half-forms and builds emoji sequences.
- Reproduction (real `refusalLinkText`, scratch test): term "می‌خواهم" gives "Search NCBI for میخواهم" (code points 645 6cc 62e ..., no 200c); "क्‍ष" gives "Search NCBI for क्ष" (915 94d 937); "👩‍🔬" gives "Search NCBI for 👩🔬" (1f469 1f52c, two emoji instead of one).
- Why it matters: a reader asking in Persian or Hindi sees their word in a slightly different written form in the link text. The href is unchanged, so the search itself is right. A narrower class (bidi controls U+202A to U+202E, U+2066 to U+2069, U+200E, U+200F, U+200B, U+FEFF) would close V-02 without this.
- NOT FIXED

### F-138-V-06: a few invisible characters outside Cf still give a label that names nothing
- Severity: minor, unsure (residual of F-138-V-02, not worse than develop)
- What: U+3164 (Hangul filler, Lo) and U+2800 (braille blank, So) are not Cf, so they survive the strip and the trim; U+2028 (line separator, Zl) survives inside a term.
- Reproduction: term "ㅤ" gives "Search NCBI for ㅤ" (last code point 3164); "⠀" gives "Search NCBI for ⠀"; "a b" gives "Search NCBI for a b" (code point 2028 kept).
- Why it matters: only self-inflicted, from the reader's own question; the all-Cf fallback works for the characters V-02 named.
- NOT FIXED

### Probes that held (fix round)
- Ordinary letters, combining marks and spaces are kept: "café lait" keeps U+0301; "Sjögren syndrome", "α-synuclein", "乳腺癌" unchanged; "TP53   R175H" keeps its three inner spaces; NBSP kept inside; "cystic+fibrosis" reads "cystic fibrosis".
- All-Cf terms fall back: "​‎‮⁦﻿" and " ​  ‏ " both give "Search NCBI"; empty term gives "Search NCBI"; a non-URL gives "Search NCBI". V-02's two cases (U+202E, U+200B) are closed.
- Soft hyphen and tag characters are dropped ("BRCA­1" gives "BRCA1"), which is right for a label.
- R14 still decides linking: the render site (`AnswerScreen.tsx:1177`) gates the anchor on `isLinkableRefusalLink(link)` and the text helper is only inside that branch. Host probes: http, `ncbi.nlm.nih.gov.evil.com`, `javascript:`, `evil.com`, `evilncbi.nlm.nih.gov`, an address that puts the NCBI host before an at sign and evil.com after it all false; `https://www.ncbi.nlm.nih.gov/...` true.
- Two `term` parameters show the first ("A&term=B" gives "Search NCBI for A"), matching what `URLSearchParams.get` sends to NCBI.

### Earlier findings, status after the fix round
- F-138-V-01: closed. `frontend/e2e/cite-or-refuse.spec.ts:252`, `:261`, `:293`, `:299` now expect "Search NCBI for BRCA9" and "Search NCBI for NOTAGENE" as text and link name, and the href assertions on `FALLBACK_LINK` and `UNRESOLVED_LINK` are kept. The stale comment at `:255` to `:259` is rewritten. `npx playwright test e2e/cite-or-refuse.spec.ts`: "3 passed".
- F-138-V-02: closed for the characters it named (U+202E, U+200B), with the side effects in F-138-V-05 and the residue in F-138-V-06.
- F-138-V-03: left open, knowingly per the brief. No ask-back (clarifying_question) render test was added; the commit message does not say it was left.
- Grep: nothing in `frontend/src` or `frontend/e2e` still asserts a refusal's raw address as link text. The only `getByRole("link", { name: "https://..." })` left is `SavedAnswerScreen.test.tsx:76`, a citation record link, not a refusal.

### Break-it, fix round
- Scratch edit `AnswerScreen.tsx:1185` from `{refusalLinkText(link)}` to `{link}`.
- `npx vitest run src/components/screens`: "1 failed | 197 passed (198)", the failing arm "renders the NCBI fallback address as a real link on an answer-level refusal".
- `npx playwright test e2e/cite-or-refuse.spec.ts`: "2 failed, 1 passed", both refusal tests (`:244`, `:281`) on `toContainText`. Unit and e2e both go red.
- Restored with `git checkout --`; `cmp` against a byte copy identical; `git diff HEAD` 0 bytes; `git status --short` shows only `?? frontend/node_modules`. Scratch probe test moved out to the scratchpad.

### Commands run, fix round
- `npx vitest run src/components/screens`: 198 passed on three runs, 1 unidentified failure on the first run under machine load (F-138-V-04).
- `npx playwright test e2e/cite-or-refuse.spec.ts`: 3 passed.
- `npx tsc -b`: exit 0.

### Verdict, fix round
- PASS on "nothing worse than develop". V-01 is closed, the e2e spec passes, the R14 host check still decides linking, and the break-it mutation turns unit and e2e red.
- Two findings sit inside this fix round's own change (F-138-V-05, the joiner strip; F-138-V-06, residue), both minor, and neither is worse than develop, where these terms showed as percent escapes. Per the review loop they still count as a finding inside a fix, so the lead should say so to the owner rather than run another round.
- Verified with my own probes: the Cf strip on 21 terms against the real `refusalLinkText`; the all-Cf fallback; seven host-check inputs; the break-it on unit and e2e; the three commands.
- Only read, not run: that the render site gates the text helper behind the host check (`AnswerScreen.tsx:1177` to `1185`, read, and consistent with the host probes); that no ask-back renders through another block (from the earlier round, not rechecked).
