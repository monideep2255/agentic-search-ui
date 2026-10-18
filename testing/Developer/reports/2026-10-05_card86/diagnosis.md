# Card 86 diagnosis: `clsx` shows "no license file found"

Diagnosed by the lead on 2026-10-05, read-only. Card 86 on `testing/UI_fix_plan.md`, test query 99.

## What the person sees

The web app's `THIRD_PARTY_NOTICES.txt` lists 25 bundled packages. Twenty-four carry their license text. `clsx` 2.1.1 reads "no license file found" (`testing/Developer/reports/2026-09-29_retest/runner_B/q99_notices.txt`). MIT requires the license text to travel with the copy, so the notice file is incomplete for that package.

## Root cause

- `frontend/vite.config.ts`, `thirdPartyNoticesPlugin`, looks for exactly three file names: `LICENSE`, `LICENSE.md` and `LICENCE`, with `existsSync`.
- `clsx` ships its license as a lowercase `license` file. Of the 25 bundled packages it is the only one whose license file name is not in that list (checked against `frontend/node_modules` on 2026-10-05).
- On a Mac the file system ignores case, so a local build finds `license` when it asks for `LICENSE` and the notice looks complete. Develop is built on Linux, where names are case-sensitive, so the lookup misses and the placeholder is written.
- `.github/scripts/assert_license_notices.py` fails the build on the placeholder only for its three required packages (`react`, `react-dom`, `@mui/material`), so CI did not catch it for `clsx`.

## Fix options

| Option | What changes | Risk |
|---|---|---|
| A, recommended | The plugin lists the package folder and matches any file named `license` or `licence`, with or without `.md` or `.txt`, ignoring case; the CI check fails on the placeholder for any package, not only the three | Low. A new dependency without any license file then fails CI instead of shipping a placeholder, which is the intended behaviour |
| B | Add `license` to the name list only | Fixes `clsx` today; the next package with `LICENSE.txt` or another spelling repeats the defect, and CI still would not notice |

Option A touches `.github/scripts/`, so it goes on a branch with a pull request. It does not change the answer path, so no golden run is needed. Verify by building on Linux (CI's frontend gate) and reading the `clsx` section of the built notices file, then query 99 on develop.

## Not covered

- Whether any package bundled only by a future dependency upgrade lacks a license file entirely; option A makes that a CI failure rather than guessing.
- The command line client's own notices, which are a separate file (`clients/system3-cli/NOTICE`).
