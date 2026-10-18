# Card 63 review record

Card 63, "every not yet confirmed answer saved, and a search down at NCBI said so", at risk dial position 2: one judge round and one adversary round, one fix round, then a fresh verifier. The builder's report and the test round are in `builder.md` beside this file. The judge's and the adversary's findings are appended, as they find them, to `judge.md` and `adversary.md` beside this file; this record carries the verdicts, filed by the lead.

## Table of contents

- [Why both rounds run again](#why-both-rounds-run-again)
- [Dispatches](#dispatches)
- [Verdicts](#verdicts)
- [Gates on the fix round](#gates-on-the-fix-round)

## Why both rounds run again

- The machine restarted at 06:45 UTC on 2026-09-27, part-way through the judge's round, and the restart cleared the temporary folder that held the reviewers' probes (`DECISIONS.md`, 2026-09-27).
- The board and `HANDOFF.md` record the adversary as PASS, but no adversary finding row or verdict was written to this folder or anywhere else in the repository.
- At position 2 the report folder holds the judge's and the adversary's rows before the push. With no rows for either, both rounds run again, from the branch as it would land.
- The branch was brought up to date with develop first: merge commit `9e1190ff` merges `origin/develop` at `7bac224e` into `fix/card63-tested` at `1c1558a4`, with no conflicts. The rounds review `git diff origin/develop...HEAD` from there.

## Dispatches

| # | Role | Model and effort | Start (UTC) | End (UTC) | Tokens | Result |
|---|---|---|---|---|---|---|
| 1 | Judge, in `.claude/worktrees/card63` | Fable, high | 2026-09-29 00:24 | 2026-09-29 00:41 | 232,556 | PASS; F-63-J01 to J03 should-fix, J04 unsure and pre-existing |
| 2 | Adversary, probing in its own checkout `.claude/worktrees/card63-adv` at `bc6cca1a` | Fable, high | 2026-09-29 00:24 | 2026-09-29 00:45 | 239,845 | FAIL on F-63-A01; A02 to A04 minor or unsure |
| 3 | Fix agent, holding F-63-A01, A02 and J01 to J03 in one pass, since they share files (Rule 1) | Sonnet, medium | 2026-09-29 00:48 | 2026-09-29 01:05 | 208,202 | A01, A02 and J01 to J03 fixed, uncommitted; each new test red on one broken property, then green |
| 4 | Fresh verifier, no prior context | Fable, high | 2026-09-29 01:07 | 2026-09-29 01:15 | 204,623 | MERGE; A01, A02, J01 to J03 closed by its own probes and single-property mutations |

## Verdicts

| Round | Verdict | Blocking |
|---|---|---|
| Judge, at `bc6cca1a` | PASS | none; no finding inside the fix commits `ecbf15ba` or `cf156daa` |
| Adversary, at `bc6cca1a` | FAIL | F-63-A01, not inside a fix commit, so no Rule 4 stop; confirmed by the lead's own read of `_build_failed_search_note` |
| Fix round | A01, A02 and J01 to J03 fixed, each new test shown red then green | none |
| Fresh verifier, on the uncommitted fix round | MERGE | none; nothing found inside the fix, no Rule 4 stop |

## Gates on the fix round

The full unit suite, `.github/gates/gate04_unit_suite.sh`, ran on an exact copy of the uncommitted fix round in a second checkout, `git apply` of `git diff HEAD -- src tests` on `bc6cca1a` (8 files, 290 insertions, 32 deletions in both), while the fresh verifier worked in the first:

```text
6501 passed, 143 skipped, 24 deselected, 1 xfailed, 8 warnings in 466.54s (0:07:46)
```

Exit 0. For comparison, develop at `6789cdf3` on the same machine: 6456 passed, after the five `/verify` capture tests that needed Node on the path were rerun with it (`5 passed in 1.93s`).
