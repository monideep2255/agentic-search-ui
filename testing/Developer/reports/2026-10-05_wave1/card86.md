# Card 86 report: license notices for every package

## Change

- `frontend/vite.config.ts`, `thirdPartyNoticesPlugin`: lists the package folder and accepts any file named license or licence, with or without `.md` or `.txt`, ignoring case. An exact `LICENSE` wins when several match. Behaviour no longer depends on the file system's case rules.
- `.github/scripts/assert_license_notices.py`: fails when ANY package entry carries the "no license file found" placeholder. The three required packages still need an entry with non-empty text.
- `tests/ci/test_assert_scripts.py`: new test `test_the_placeholder_fails_for_any_package_not_only_the_required_three`. The existing three-package placeholder test still passes.

## Checks

- New test fails on the old script (stashed the script change, saw it go red), passes with the change. All 19 notices tests pass.
- Gate 2 passes, gate 3 passes, gate 4: 6803 passed, 143 skipped.
- Frontend `npm ci`, `npm run build`: build succeeds. Built `dist/THIRD_PARTY_NOTICES.txt` clsx section carries the MIT text; zero placeholders in the file. `assert_license_notices.py frontend/dist` prints ok.
- Frontend `npm test`: 483 to 479 passed, with 2 to 6 failures that differ per run, all 15 s timeouts in `App.test.tsx` and `App.stopUntilAnswer.test.tsx` under machine load. Not in code this change touches.

## Not covered

- The plugin has no frontend unit test (the config file has no test harness), and a Mac cannot reproduce the Linux case-sensitive miss. The proof is the built file plus the new assert test. Linux CI's frontend gate is the real check.
- The command line client's notices.
