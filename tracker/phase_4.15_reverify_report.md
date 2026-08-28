# Build phase 4.15: round 2 re-verification report

Agent: re-verifier, fresh context, no prior involvement in this phase.
Date: 2026-08-28. Branch: `phase/4.15-release-environments`, HEAD `fc8dd95`.

Verdict: FAIL. The round STOPPED EARLY under Rule 4 of `.claude/skills/bossman-mode/SKILL.md`, "The review loop has a budget", because a defect was located inside code written earlier in this phase to fix an earlier finding. One finding filed, `F-4.15-RV-01`, critical, `Regression of: F-4.15-J-03`.

## Table of contents

- [The stop](#the-stop)
- [Item by item](#item-by-item)
- [Handover, the four items Rule 3 requires](#handover-the-four-items-rule-3-requires)

## The stop

F-4.15-J-03 and F-4.15-A-15 were filed independently in round 1 on one property: the mutation harness asserted in its own docstring that it covered every arm, and it covered seven of nine. Round 2's fix commit `be22908` added the two missing cases, rewrote the docstring to record the miss rather than quietly filling it in, and re-asserted the total claim in the same sentence.

That re-asserted claim is FALSE at HEAD.

`tests/system_03_search_agent/tools/test_release_environments_mutation.py:20`:

```
what nobody re-reads. Every arm, P1 through P9 including P3a, P3b and P7b, now
has at least one case, and the way to keep that true is to add the case in the
same edit as the arm rather than afterwards.
```

Measured, not read:

```
$ grep -c "^def test_p" tests/system_03_search_agent/tools/test_release_environments_premise.py
13

$ grep -n "p3b" tests/system_03_search_agent/tools/test_release_environments_mutation.py
$ echo $?
1

$ grep -c "p9b" tests/system_03_search_agent/tools/test_release_environments_mutation.py
0

$ grep -o "test_p[0-9a-z_]*" tests/.../test_release_environments_mutation.py | grep -o "test_p[0-9]*[ab]*_" | sort -u
test_p10_
test_p1_
test_p2_
test_p3a_
test_p4_
test_p5_
test_p6_
test_p7_
test_p7b_
test_p8_
test_p9_
```

Eleven arm names of thirteen. `test_p3b_the_two_deployments_hold_different_signing_keys` and `test_p9b_the_release_scripts_themselves_hold_their_safety_rules` are referenced nowhere in the harness. The only occurrence of the string `P3b` in the whole file is the docstring sentence claiming it is covered; the lowercase identifier appears zero times.

Why this is the Rule 4 shape rather than an ordinary gap:

- The claim is the exact artifact the round-1 critical was raised against, and it was rewritten by the round-2 fix, so the defect is inside the fix.
- P3b is the half of the F-4.15-J-04 split that carries the key-separation property. The critical was raised because P3 proved a correlate; the arm created to prove the real property is the one left unproven.
- P9b, created by `199bc8b` to close F-4.15-A-13, is not covered and is not even named in the claim, so the same omission recurred twice in one round across two different fix commits.
- The pattern the docstring itself names, "the claim is written at the moment of most confidence, and confidence is exactly what nobody re-reads", reproduced itself one commit after being written down.

Per Rule 4 the finding was written to `tracker/phase_4.15.md` BEFORE the round stopped and before this report was composed, which is the ordering that rule specifies after it was got wrong on 2026-08-27.

## Item by item

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 1 | Hunt inside the four fix commits first | FAIL | `git show 87d33e9 be22908 199bc8b 7b1fca9` read. The defect found is inside `be22908`'s rewritten docstring, compounded by arms added in `87d33e9` and `199bc8b` with no matching cases |
| 2 | Rule 4, does any defect sit inside a prior fix | FAIL, STOP | Yes. `F-4.15-RV-01`, `Regression of: F-4.15-J-03`. Round stopped here, not batched |
| 3a | F-4.15-J-04 closed (P3a/P3b sound) | NOT RUN | Reached only far enough to establish that P3b has no mutation case. Whether P3a can pass against a deployment that does not verify signatures, and whether P3b reads what it claims, was NOT exercised. Not run is a FAIL, never a pass |
| 3b | F-4.15-J-03 / F-4.15-A-15 closed (every arm has a case) | FAIL | 11 of 13 arms covered. See "The stop". The claim is not true now |
| 3c | F-4.15-A-14 closed (develop bundle no longer ships `http://127.0.0.1:8000`) | NOT RUN | Both live bundles were NOT fetched. Not run is a FAIL |
| 3d | F-4.15-A-01/03/07 closed (one `commit_lib.sh`) | NOT RUN | No throwaway repository was created and no hostile commit subject was exercised. Not run is a FAIL |
| 4 | Mutation-test the new arms P3a, P3b, P7b, P9b, P10 | FAIL | P3b and P9b have NO mutation case to test. P3a, P7b and P10 have cases which were NOT independently broken before the stop |
| 5 | Run and paste real output | PASS | Below |
| 6 | P5's "unblockable before merge" claim | NOT RUN | Neither `/health` endpoint was fetched. Not run is a FAIL |

### Item 5 output, run at HEAD `fc8dd95`

```
$ source venv/bin/activate && python -m pytest tests/system_03_search_agent/tools/test_release_environments_premise.py tests/system_03_search_agent/tools/test_release_environments_mutation.py -q -p no:randomly
sssssss.s...s.....................                                       [100%]
25 passed, 9 skipped in 0.11s
```

```
$ ruff check src services
All checks passed!
```

```
$ python tracker/check_doc_drift.py --check
ok: 10 facts computed | 0 stale | 0 structural
```

```
$ for f in .github/release/*.sh; do bash -n "$f" && echo "OK $f"; done
OK .github/release/commit_lib.sh
OK .github/release/derive_version.sh
OK .github/release/open_backmerge_pr.sh
OK .github/release/tag_and_release.sh
OK .github/release/write_changelog.sh
```

Note on that green suite: `25 passed, 9 skipped` is exactly the number the defect hides behind. The harness is green because it never names the two arms it does not cover, so nothing counts arms and nothing fails. This is the same relationship build phase 4.14 recorded between a green `4019 passed` and 25 tests that could never run.

`RUN_PREMISE_GATE=1` was NOT set, so P2 and P3a created no accounts on the live deployments.

## Handover, the four items Rule 3 requires

Which findings remain open, with severity:

- `F-4.15-RV-01`, critical, new this round, the Rule 4 stop.
- Every round-1 finding whose closure this round did not reach: `F-4.15-J-04` critical, `F-4.15-A-14` critical, `F-4.15-A-01`, `F-4.15-A-03`, `F-4.15-A-07` major, `F-4.15-A-09` major. Their fixes exist in the tree and were NOT verified by exercise. Treat them as unverified, not as closed.
- The ledger's own State column still reads `open` for `F-4.15-J-03`, `F-4.15-J-04`, `F-4.15-A-14`, `F-4.15-A-15` and `F-4.15-A-09` at HEAD, so the tracker and the fix commits already disagree about what shipped.

What each fix attempt changed, as a diff summary per attempt:

- `87d33e9`: split P3 into P3a and P3b in the premise gate, +215 lines there, +201 in the tracker. Created two arms; added a mutation case for one.
- `be22908`: +207 lines in the mutation harness (P6 and P9 cases, the two the round-1 critical named), +94 in the premise gate (P1 project-id comparison, P7b), a one-word comment fix in `ci.yml`, a docstring finding-id fix in `app.py`, goal contract rewritten. This is the commit carrying the false claim.
- `199bc8b`: added P9b, +70 lines in the premise gate; corrected `docs/build/Release_flow.md`'s present-tense `app_env` assertion; recorded F-4.15-A-16 as accepted. Created an arm; added no mutation case.
- `7b1fca9`: replaced two commit parsers with `.github/release/commit_lib.sh`, +183 new lines, rewrote `derive_version.sh` and `write_changelog.sh` around it; added P10 with two mutation cases; documented the back-merge CI gap in three places.

Whether any round-2 finding sits inside a round-1 fix, named explicitly:

Yes. `F-4.15-RV-01` sits inside `be22908`, the round-2 fix for `F-4.15-J-03` and `F-4.15-A-15`. It is filed with `Regression of: F-4.15-J-03`.

Options, with a recommendation:

1. RECOMMENDED. Stop treating "every arm is covered" as a prose claim and make it a structural arm. Add one test to the mutation harness that enumerates `def test_p*` in the premise file, enumerates the arm names the harness references, and asserts the two sets are equal. Then add the missing P3b and P9b cases so it goes green. This converts the class into a build failure, the same move build phase 4.7 made permanent with its offline mutation harness and build phase 4.14 made when the shell left the workflow. It is a category fix, not an enumeration: the next arm added without a case fails the suite on the spot rather than waiting for a fourth review round.
2. Fix by enumeration: add cases for P3b and P9b and correct the docstring. Cheaper, and it leaves the class alive. This phase has now shipped the same class three times (round 1 at seven of nine, round 2 at eleven of thirteen), which is the evidence against this option.
3. Revert this phase's round-2 fixes and re-decompose. Not recommended: the fixes are substantively right where they were exercised, and the three uncovered classes are narrow. The failure is the coverage claim, not the fixes.

Whichever is chosen, items 3a, 3c, 3d and 6 above still have to be run. No agent in this phase has yet exercised the F-4.15-J-04 fix, the F-4.15-A-14 fix, the `commit_lib.sh` fix or the P5 unblockability claim against anything but their own authors' reading.

## Two things observed after the stop, recorded rather than acted on

Neither was hunted for. Both surfaced from the item-5 commands and both bear directly on `F-4.15-RV-01`, so they are corroboration of the filed finding rather than new findings batched onto it.

The board states the same false claim in a second place. `tracker/BOARD.md:78` was rewritten at 12:21 on 2026-08-28, during this run and by another agent, and its evidence cell reads "mutation harness 21 cases over all 11 arms". The premise gate holds THIRTEEN arms, `grep -c "^def test_p"` returns 13, and eleven is the count of arms that have a case. Calling the covered subset "all" is the identical move the harness docstring makes. The board also says "live premise gate 33 of 34" while `check_doc_drift.py` computes 9 of 9 from source.

`check_doc_drift.py --check` was GREEN at the start of this run and is RED now:

```
tracker/BOARD.md:78: says premise gate 33 of 34 (computed: 9 of 9)
tracker/BOARD.md:9: 'Last updated: 2026-08-27' predates a later date in the body (2026-08-28)
error: 10 facts computed | 1 stale | 1 structural
```

Both stale facts live in `tracker/BOARD.md`, which this agent did not touch; the only file this agent wrote in the tracker is the `F-4.15-RV-01` row in `tracker/phase_4.15.md` and this report. The item-5 PASS above is recorded against the state at the start of the run, and the gate's current state is RED. Whoever picks this up owns reconciling the board's two numbers with what the source computes, and per `goal-contracts`'s "never corrupt the subject to satisfy the check", establish first which of the board and the checker is right, because "33 of 34" and "9 of 9" may be counting different things.
