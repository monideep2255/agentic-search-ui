# Card 43b: Keep the citation number with the name

On phone widths, citation 5 now stays beside the last characters of the variant name in both the record row and its sentence instead of appearing alone on the next line. The longer name still wraps inside the record row, and the desktop table stays on one line.

## Table of contents

- [What changed](#what-changed)
- [Red and green evidence](#red-and-green-evidence)
- [Screenshots](#screenshots)
- [Checks](#checks)
- [Not covered](#not-covered)

## What changed

| File | Change |
|---|---|
| `frontend/src/components/screens/AnswerScreen.tsx` | Keep only the final three characters of a phone record name and its marker in one no-wrap span. In cited prose ending with a long unbroken name, keep its final three characters, trailing punctuation and citation markers together without preventing the preceding text from wrapping. Preserve the lead sentence's emphasized term even if it crosses the split; leave ordinary prose's text nodes intact. |
| `frontend/e2e/long-variant-name.spec.ts` | Add the shorter variant with citation 5 and assert the marker's top is above the bottom of the name's final characters at 390, 412 and 414 pixels in both the record row and prose. Keep the existing long-name, width and accessibility assertions. |
| `frontend/e2e/long-variant-name.spec.ts` and `frontend/e2e/tour-button-contrast.spec.ts` | Capture screenshots only with `FACTORY_SHOTS=1`, so normal CI runs do not rewrite committed images. |

Decision: keep a short tail with the marker, not the entire identifier or sentence. The preceding text must remain able to wrap without making the phone page wider.

## Red and green evidence

| Check | Before | After |
|---|---|---|
| Phone record row, citation 5 | Failed on develop: the name's last characters ended at 209.06 pixels and the marker started at 212.81 pixels, on the next line. | Passed with the final three characters and marker kept together. Removing that wrapper alone makes the same assertion fail. |
| Phone prose, citation 5 | Passed at 390 without a change, but failed at 412 and 414 with "the prose citation sits alone below the variant name": the name ended at 41.8125 pixels and the marker started at 49.875 pixels. | Passed at 390, 412 and 414 with the final characters, punctuation and markers held together. Removing the prose wrapper restores the 412/414 failure. |
| Long variant and desktop table | The card 43 assertions were retained. | Passed at 390, 412, 414 and 1280 pixels, with zero axe violations. |
| Screenshot gating | The old specs wrote to committed image paths on every run. | A normal 16-test browser run left all committed screenshots unchanged. A separate `FACTORY_SHOTS=1` run wrote only the two images in this report folder. |

An initial version split every prose claim and made five existing unit assertions fail because ordinary sentence text was no longer in one text node. Restricting the wrapper to cited prose ending in a long unbroken name restored those assertions; all 489 unit tests passed on the rerun with one worker. A timing-sensitive Stop test failed once under the default parallel run, then passed alone and in the full one-worker run.

## Screenshots

| Phone, 390 pixels | Desktop, 1280 pixels |
|---|---|
| ![Citation 5 stays with the name on a phone](answer_390.png) | ![Record table remains on one line on desktop](answer_1280.png) |

Generated account labels were masked in both screenshots.

## Checks

| Command | Result |
|---|---|
| `cd frontend && npm run build` | Passed; reported its existing large-chunk warning. |
| `cd frontend && npm test -- --maxWorkers=1 && python3 ../.github/scripts/assert_license_notices.py dist` | Passed: 58 test files, 489 tests and license notices. |
| `cd frontend && CI=1 npx playwright test e2e/long-variant-name.spec.ts e2e/tour-button-contrast.spec.ts e2e/accessibility.spec.ts --workers=1` with the main checkout's Python environment on PATH | Passed: 16 browser tests, including 412/414-pixel prose geometry and long-name and tour accessibility scans. No tracked image changed. |
| `python3 tracker/check_doc_drift.py --check` | Passed: 2 facts computed, 0 stale and 0 structural findings. |
| `python3 .claude/skills/ship/scripts/check_public_leaks.py --base origin/develop` | Passed: 0 findings. Both screenshots were reviewed by eye. |

## Not covered

- A live model answer or the deployed develop app. The browser test used scripted events and the fake-model backend.
- A record row carrying many distinct citation numbers in one superscript.
- The product owner's post-merge retest.
