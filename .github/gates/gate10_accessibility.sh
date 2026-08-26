#!/usr/bin/env bash
# Section 24 gate 10: accessibility, WCAG 2.1 AA.
#
# Only `accessibility.spec.ts`, not the whole Playwright suite, and that is a
# deliberate scope: `query-stream-and-stop.spec.ts` carries a standing failure
# that build phase 4.16 proved PRE-EXISTING at its own branch point and left
# unowned. Making the whole suite blocking would block every pull request on a
# defect none of them introduced.
set -euo pipefail
npx playwright test e2e/accessibility.spec.ts
