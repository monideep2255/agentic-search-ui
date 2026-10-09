# Wave 1 builder brief, shared by all six builders

You build one small change from `testing/Board_plan.md`, wave 1. Your prompt names your card, your worktree and your branch.

## Rules

- Work only inside your worktree, `.claude/worktrees/<name>` under the repository root, where your branch is checked out from `origin/develop`. Quote paths: the repository path contains a space.
- Never use `git stash`: the stash stack is shared by every worktree. To prove a test fails on old code, use a temporary WIP commit or copy the old file with `git show origin/develop:<file>` into a scratch path.
- Do not dispatch agents. Do not push, open pull requests, or touch another branch or worktree. Commit locally when done: a Conventional Commits subject in sentence case, one logical change, and no Co-Authored-By or any other trailer.
- Read the diagnosis your prompt names in full before coding, from the main repository root (it is not in your worktree).
- Decisions belong to the classifier model; code only verifies. Never put a test question, a disease or gene name, or a word list into code or a prompt to make a case pass.
- The cite-or-refuse checks stay strict. Never loosen a grounding, number or citation check to make output survive.
- Match the surrounding code's style, naming and comment density. Read `.claude/rules/production-standards.md` before coding.
- Public repository: no local absolute paths, credentials or tokens in code, tests, logs, comments or reports. Use `<repo-root>`. Never log a person's question text or any personal data.

## Verify, immutable: add checks, never weaken them

1. Each new or changed behaviour has a unit test that fails on the old code. Prove it: run the test with your change stashed or reverted and see it go red, then restore.
2. The repository's CI gates, exactly as CI runs them: `bash .github/gates/gate02_import_order.sh`, `bash .github/gates/gate03_lint.sh` (ruff over the whole repository, no path), and `bash .github/gates/gate04_unit_suite.sh`. All green. If gate 1 fails only because the package is not importable in your shell, say so and run the unit suite the way gate 4 does.
3. Where your prompt asks for local live runs, run them and record each result.

The lead runs your card's test queries on develop after merge; that is the gate. Say in your report what your checks do not cover.

## Output

- The local commit on your branch.
- `testing/Developer/reports/2026-10-05_wave1/<name>.md` inside your worktree, committed with the change: the change in plain words, the tests and that each failed on the old code, gate results, any live runs, and what is not covered.

## Blocked-stop

Stop and report, without guessing, if: the fix needs a check loosened; the change grows beyond your card into another card's code; a gate fails for a reason outside your change; or the diagnosis turns out wrong.

Return about 200 words: what changed, test and gate results, the commit hash, and anything the lead must know.
