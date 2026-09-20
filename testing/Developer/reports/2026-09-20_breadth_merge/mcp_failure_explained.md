# The unexplained MCP failure on the broad-search branch, explained

Written 2026-09-20, working `testing/UI_fix_plan.md`'s "Next, in order" item 1.

## What the cutoff asked for

Item 1 says to merge develop into `.claude/worktrees/breadth-wiring` and re-run the
full suite, and it predicts: "The manifest failure should clear; the MCP one is NOT
predicted to, because the worker tested that and it did not. If it persists, find out
why it appears only in this branch's full run before merging."

## The finding: the worker's test was incomplete, so its prediction does not hold

The overnight worker copied develop's `conftest.py` and the debugging-guide manifest
into the worktree, saw the MCP production-mount test still fail, and concluded the
cause was unknown.

Develop's CI fix, commit `a90ef25`, repaired THREE independent test-isolation defects.
The worker ported TWO of them. The third is the one that addresses this exact failure,
and it lives in a file the worker never copied: `tests/e2e_support/test_real_model_mode.py`.

That fix's own docstring, added in `a90ef25`, names the failure precisely:

> `TestClient` is deliberately NOT used as a context manager. Its `__enter__` runs the
> app's lifespan, and this is the real module-level `app` from `adapters/web_sse/app.py`,
> whose lifespan enters the mounted MCP sub-app's `StreamableHTTPSessionManager.run()`.
> That manager may run exactly once per process, and the one test allowed to enter it is
> `tests/system_03_search_agent/adapters/mcp/test_phase_4_1_production_mount.py`. This
> file collects before that one, so a `with TestClient(...)` here made the production-mount
> test fail in CI with "`.run()` can only be called once per instance" from 2026-09-14 to
> 2026-09-19.

Every observed property of the failure follows from that, with nothing left over:

| Observed | Why |
|---|---|
| Fails only in a FULL run | `tests/e2e_support/` collects before `tests/system_03_search_agent/`, so only a run containing both has a collision |
| Passes when run alone | Nothing else enters the one-shot lifespan |
| Passes with its own directory (82 passed) | `tests/e2e_support/` is not in `adapters/mcp/` |
| The main tree's full run is clean | Develop already carries the fix |
| Copying `conftest.py` and the manifest did not clear it | Neither is the fix for this defect; the fix is in a third file |

So the failure was never a property of the broad-search wiring at all. The branch
predates `a90ef25` and was missing one of its three fixes.

## Why the earlier conclusion was reasonable and still wrong

The worker correctly refused to call the failures pre-existing on inference alone, and
tested the inference directly, which is the right instinct and is why the earlier
"checked rather than assumed" claim was corrected. The test it ran was itself partial:
it varied two of the three fixes and treated the result as covering all three. Porting a
subset of a fix and concluding from the residue is the same shape of error as the claim
it was correcting.

The cheaper move, available the whole time, was to merge develop rather than copy files
out of it. A merge cannot omit a file.

## Verification

Predicted: with develop genuinely merged, the full suite on this branch has zero failures.

The run is `pytest -m "not integration" -q -rs` on the merged branch. Its result is
recorded in `full_suite.md` in this folder. This file is written before that run
finished, deliberately: the finding is established from `a90ef25`'s own diff and
docstring, and the rule here is to write a finding when it is established rather than
hold it in a running process.

## Result: the prediction held, and a second cause turned up behind it

The full suite on the merged branch: `2 failed, 5023 passed, 153 skipped, 23 deselected,
1 xfailed in 211.15s`.

THE MCP PRODUCTION-MOUNT TEST PASSED. Merging develop cleared it, exactly as the analysis
above predicts and contrary to the cutoff's prediction. The cutoff's prediction was sound
given what it knew; what it did not know is that the worker's port was missing a file.

The two remaining failures were BOTH the debugging-guide coverage tests, and both had ONE
cause that has nothing to do with this branch's code:

```
Missing: ['src/system_03_search_agent/tools/cypher_query 2.py']
```

A macOS duplicate-copy artifact, 110,963 bytes, dated 2026-09-20 00:04, sitting in the
worktree's `src/` tree. Established before it was touched:

- It is byte-identical to the PRE-BRANCH version of `cypher_query.py`, so it is a backup
  copy taken before the overnight edit and holds no unique work.
- It is GITIGNORED, by `.gitignore:85`, pattern `* [0-9].py`. That is why `git status`
  showed a clean tree and why it was invisible to every session that looked.
- `test_debugging_guide_coverage.py` walks the FILESYSTEM, not git, so it sees a file
  git is hiding.

It was moved to the Trash rather than deleted, and it is recoverable two ways: from the
Trash, and from git as `git show 0942f86^:src/system_03_search_agent/tools/cypher_query.py`.
After removal those two tests pass, with the MCP test, 8 passed.

## The transferable part

A gitignored file can fail a test while `git status` reports a clean tree. Both of the
overnight session's confusing signals share that shape: a failure whose cause is a file
nobody can see, and a failure whose cause is a file nobody copied.

It also means the branch's earlier `2 failed, 5023 passed` was never reproducible in CI,
because CI checks out from git and the artifact is not in git. A local full-suite
failure count is only comparable to CI's when the working tree holds nothing git is
ignoring.
