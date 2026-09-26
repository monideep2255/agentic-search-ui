---
name: ship
description: Runs the CI gates locally before anything is staged. Syncs the four canonical docs and commits with a Conventional Commit subject. Pushes to develop in the UI fix loop or to the phase branch in build-phase mode. Proves the remote advanced and confirms the deploy. Clears away leftover agent worktrees. Use when ending a work block or after a logical milestone.
---

# /ship - gates, docs-sync, git-sync, then worktree cleanup

A single ritual to end a work block: run the local gates, bring docs in line with code, commit and push, then clear away any worktrees and branches that background agents left behind. The gates run directly; the docs-sync and git-sync steps delegate to an agent each; the worktree step is done directly, because it deletes things and the check that makes deletion safe is three commands.

## Table of contents

- [Step 0: the gates, before anything is staged](#step-0-the-gates-before-anything-is-staged)
- [Step 1: docs-sync agent](#step-1-docs-sync-agent)
- [Step 1b: stray file sweep](#step-1b-stray-file-sweep)
- [Step 2: git-sync agent](#step-2-git-sync-agent)
- [Step 3: leftover worktree cleanup](#step-3-leftover-worktree-cleanup)
- [Guards](#guards)
- [Output](#output)

## Step 0: the gates, before anything is staged

No verification ran before a push until this step existed. The product owner set standing pre-push checks on 2026-09-12 and 2026-09-20, and until now they lived only in memory and in the old continuation prompt, never enforced here. CI on GitHub runs on every push to `develop` and on every pull request, but it reports after the push, and this repository also works in a UI fix loop where pushes go straight to `develop` with no PR and no review round. So the local gates below are the only checks that run before a change reaches `develop`.

### Gate on the exit code, never through a pipe

Every check gates on its own exit code, never through a pipe. Run the check with output to a file. Capture `rc=$?` and continue only if it is 0:

```bash
pytest ... > /tmp/gate_output.txt 2>&1
rc=$?
cat /tmp/gate_output.txt | tail -20
if [ $rc -ne 0 ]; then echo "GATE FAILED, rc=$rc"; fi
```

A chain like `pytest ... | tail -3 && git commit` reports `tail`'s exit code, not the test run's, so a red suite still lets the `&&` continue. Commit `ff80814` (2026-09-12) and one commit on 2026-09-22 went out with a red arm this way.

### The checks, in order

- `ruff check` with no path: the whole repository, matching CI gate 3. Report folders under `testing/` count as source.
- `isort --check-only --diff src tests services tracker alembic .claude .github`: matches CI gate 2.
- `bash .github/gates/gate04_unit_suite.sh`: whenever any Python file under `src/`, `tests/`, `services/` or `tracker/` changed. Roughly five minutes. A docs-only change skips this and the report says so.
- `npm run build` in `frontend/`: whenever any file under `frontend/` changed. Railway's own build is what fails silently otherwise, and this is the only local check that would catch it first.
- `python3 tracker/check_doc_drift.py --check`: always. It checks document structure (tables of contents, the two append-only tables, phase and pull request references), compares no count and runs no tests, so it takes seconds. A fact it could not compute is a failure line naming why, never an "ok".

### A red gate stops the ship

Fix the cause, then make a NEW commit. Never `--amend`.

### CI runs after the push, so check it before claiming it

CI runs failed from 2026-09-22 into 2026-09-24 while the account's billing setting blocked Actions, and completed green on `develop` again on 2026-09-25 and 2026-09-26 (`gh run list --branch develop`). Check `gh run list --branch develop --limit 3` for the pushed commit before claiming CI ran on it. A push that changes only Markdown runs no workflow (`paths-ignore` in `.github/workflows/ci.yml`), so for a documentation-only push the local gates are the only evidence, and the report says so rather than imply CI backed it up.

## Step 1: docs-sync agent

Dispatch the `docs-sync` sub-agent (`.claude/agents/docs-sync.md`).

It will:

1. Run `git status --short` to see what changed
2. Use its routing to identify which canonical docs need updating (CLAUDE.md, AGENTS.md, README.md, DECISIONS.md)
3. Read only affected docs
4. Make surgical edits, not rewrites
5. Report what changed (or "no changes needed")

Wait for docs-sync to complete before proceeding. Its edits may add files to the commit.

### What docs-sync owns, and what it must not touch

docs-sync edits only CLAUDE.md, AGENTS.md, README.md and DECISIONS.md. Everything else a session boundary changes is owned by `/phase-checkpoint`, and the list of those documents is not written here: it is every row of `tracker/Living_documents.md` whose owner is `/phase-checkpoint` (the handoff, the board, the done file, the test queries, Plan.md and PROGRESS.md, as of 2026-09-26).

A push does not need `/phase-checkpoint` first. One thing does, at a session end only: `HANDOFF.md` is rewritten before the push (`/phase-checkpoint` Step 4 is the procedure), so the next session starts from what is true. Every other document is edited when its fact changes, not because a date is due, and nothing here checks that a document carries today's date.

That replaced a freshness gate on 2026-09-25. `python3 tracker/check_living_docs.py --fresh` used to require every registered document to carry today's date before a push, so every session ended with edits that only moved dates, and the documents still drifted within a day. Build harness review item D2 removed the gate and the rule that `/phase-checkpoint` runs before every push, delegated by the product owner that day (DECISIONS.md, the lead implements both harness reviews' takeaways).

## Step 1b: stray file sweep

Account for EVERY stray file before anything is staged. Each one falls into exactly one of three categories, and "I did not look" is not one of them:

- Work that belongs in the commit
- Work that belongs in `.gitignore`
- A leftover to remove

### Why this step needs two sources

This step used to run `git status --porcelain` alone. That is structurally blind, and it failed in production on 2026-09-20:

- A filesystem walk found 163 macOS duplicate-copy files of the shape `<name> 2.<ext>`.
- Nine of them were under `src/`.
- One was a stale copy of a live document.
- `git status` listed NONE of them.

This repository's own `.gitignore` lines 85 to 94 carry rules of the form `* [0-9].py` and `* [0-9].md`, so git is instructed to hide the exact shape this sweep exists to catch.

Worse, the sweep looked like it was working. The 119 files it did surface that day were `.txt`, `.png`, `.jsonl` and `.log`, extensions no ignore rule covers. A check that catches the easy half and silently drops the half that matters is more dangerous than one that catches nothing. The same blindness hid `src/system_03_search_agent/tools/cypher_query 2.py` and cost a day of debugging, and duplicate `test_*.py` files collected by pytest inflated the tracked test count from 5222 to 6016.

`.claude/hooks/scan-duplicate-copies.sh` is NOT the defect. It already walks the filesystem with `find` and would have caught every one of the 163. It fires at SessionStart only, and these files appeared mid-session, which is the gap this step covers.

So run both sources. Neither one alone is sufficient:

- `git status --porcelain`: authoritative for what the commit will contain. It is the only source that sees a modified, staged or deleted tracked file, and it surfaces ordinary untracked work such as the probe script or report you just wrote. It cannot see an ignored path, by design.
- The filesystem walk below: the only source that sees a path `.gitignore` hides. It cannot see a modification to a tracked file, or anything in the index, at all.

### The walk

Paste this as is, from anywhere in the repository. It prints duplicate-copy candidates with a verdict for each, then every other file on disk that git does not track.

```bash
python3 - <<'PY'
import filecmp, os, re, subprocess
root = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True).stdout.strip()
prune = {".git", "node_modules", "venv", ".venv", "__pycache__", ".pytest_cache",
         ".ruff_cache", ".mypy_cache", "dist", "build"}
dup = re.compile(r"^(?P<stem>.+) \d{1,2}(?P<ext>\.[^.]+)?$")
tracked = set(subprocess.run(["git", "-C", root, "ls-files"],
                             capture_output=True, text=True).stdout.splitlines())
dups, strays = [], []
for base, dirs, files in os.walk(root):
    dirs[:] = [d for d in dirs if d not in prune and not d.endswith(".egg-info")]
    for name in files:
        path = os.path.join(base, name)
        rel = os.path.relpath(path, root)
        m = dup.match(name)
        if m:
            mate = os.path.join(base, m.group("stem") + (m.group("ext") or ""))
            if not os.path.exists(mate):
                verdict = "NO COUNTERPART, classify by hand"
            elif filecmp.cmp(path, mate, shallow=False):
                verdict = "byte-identical to counterpart, safe to Trash"
            else:
                verdict = "DIFFERS from counterpart, diff before touching"
            dups.append(f"{rel}: {verdict}")
        elif rel not in tracked:
            strays.append(rel)
print(f"duplicate-copy candidates: {len(dups)}")
for d in sorted(dups):
    print("  " + d)
print(f"untracked or ignored files on disk: {len(strays)}")
for s in sorted(strays):
    print("  " + s)
PY
```

The pruned directories are named in the script so the walk stays fast. The three cache directories beyond the base set (`.ruff_cache`, `.mypy_cache`, `*.egg-info`) are the same category of generated output and are pruned for the same reason.

Use this rather than a `find ... | grep` pipeline. Every one of these filenames contains a space, and feeding `find` output into a shell loop splits each path into fragments: `./sub`, `dir/beta`, `2.md`, none of which exist. Verified by running it on 2026-09-20.

### Classifying an ordinary stray

For each path in either list, say which it is and why, in one clause:

| What it is | What to do |
|---|---|
| Work that belongs in this commit | Stage it by name |
| Output worth keeping but not committing (a large dump, a local measurement) | Add it to `.gitignore`, or move it under a path already ignored |
| A leftover probe, log or temp file | Remove it, and SAY SO in the report rather than removing it silently |
| Something you did not create and cannot classify | Leave it, name it in the report, and ask. Never remove a file whose purpose you do not know |

Where scratch actually lives, because this is the part that gets assumed wrongly in both directions:

- The session scratchpad is OUTSIDE the repository, under the harness's own temp directory. Nothing in it is tracked, nothing in it can be committed, and committing does not touch it. There is no cleanup to do there and no risk to guard against.
- The risk is a file written INSIDE the repository by mistake: a probe script, a measurement dump, a log, an `out.txt`, a half-written report. That one is invisible to the reasoning above and is exactly what this sweep is for.

### Classifying a duplicate-copy candidate

This family is now a three-time recurrence, so it gets its own verdicts rather than being folded into the table above:

| The walk's verdict | What to do |
|---|---|
| Byte-identical to counterpart | A true duplicate. Move it to the Trash and say so. The content comparison is what makes this safe, not the filename shape |
| Differs from counterpart | NOT deletable on sight. Diff it line by line against its counterpart and prove nothing is lost before anything moves. The one found on 2026-09-20 was a stale snapshot of a live document |
| No counterpart | Not a duplicate at all, and the digit may be part of a real name. Leave it, name it in the report, and ask |

Removing a leftover follows `file-protection`: inform first, and prefer moving to the Trash over `rm`, so a wrong call is recoverable.

## Step 2: git-sync agent

Dispatch the `git-sync` sub-agent (`.claude/agents/git-sync.md`) with a "push" operation.

It will:

1. Run `git status` and `git diff --stat` to confirm what's staged
2. Show the file list before committing
3. Stage specific files (never `git add -A`)
4. Commit with a descriptive message (why, not what)
5. Push to origin

Additional context to pass to git-sync:

- The commit subject follows Conventional Commits per `.claude/rules/git-workflow.md`: `<type>[optional scope]: <description>` in sentence case, one logical change per commit, the body saying why.
- NEVER add `Co-Authored-By` lines or any co-author trailer (project rule).
- Push target by mode: in the UI fix loop, `develop` directly, which is one of the two named carve-outs in `.claude/rules/bossman-mode.md`; in build-phase mode, the `phase/N.M-...` branch with `-u`, then offer the pull request; anything under `.claude/`, hooks or settings goes on a `chore/` or `fix/` branch with a pull request regardless of mode.
- Prove the push: compare `git rev-parse HEAD` with `git rev-parse origin/<branch>` and require equality; never a verbose curl trace (`docs/rules/Sandbox_diagnosis.md`).
- After a push to develop, confirm the Railway deploy for that commit reached SUCCESS (the `develop` project's API service; a deploy takes two to three minutes) before telling the product owner anything is live; a push is not a deploy.

## Step 3: leftover worktree cleanup

Agents dispatched with `isolation: "worktree"` each get their own git worktree and a `worktree-agent-*` branch. Neither is removed when the agent finishes, so they accumulate silently: four had built up across three sessions before anyone looked, one of them still holding a checked-out worktree on disk.

They are not harmless clutter. A stale worktree keeps a second checkout of the whole repository on disk, and a stale branch makes `git branch` unreadable, which is exactly the list a person scans when deciding what is safe to delete.

Run this after the push, never before:

```bash
git worktree list
git branch | grep worktree-agent
```

AN EMPTY `git log develop..<branch>` DOES NOT MEAN SAFE TO DELETE, and this step used to say it did. Measured on 2026-09-20: two worktrees both returned zero commits ahead of `develop`, and deleting either would have destroyed work.

| Worktree | What `git log develop..<branch>` said | What was actually there |
|---|---|---|
| The broad search wiring | 0 commits | 726 insertions across 8 files, entirely UNCOMMITTED. The branch was never committed to, so the log is blind to all of it |
| The bold and pacing work | 0 commits | Its commit IS an ancestor of `develop`, because it was merged and then REVERTED. The log reads "already merged" and the work is not in the tree |

The old wording made it worse by calling what a worktree holds "untracked scratch, normally the agent's own probes and safe to drop". That is sometimes true and was catastrophically false here.

So the check is three questions, and ALL THREE must clear before anything is removed:

1. Unmerged commits: `git log develop..<branch> --oneline`. Non-empty means stop.
2. Uncommitted work in the worktree: `git -C <worktree-path> status --short` and `git -C <worktree-path> diff --stat`. ANY modified tracked file means stop, regardless of what the commit log says. Untracked files are classified individually, never dismissed as scratch by default.
3. Reverted-after-merge: `git log --oneline --grep="Revert" develop | head`, and check whether the branch's commit was merged and then reverted. An ancestor of `develop` whose change is no longer in the tree is PARKED work, not finished work.

Two situations change HOW a worktree is removed, both measured on 2026-09-24:

- Locked by a running process. `git worktree list` shows `locked`, and the lock reason names a process id. If `ps -p <pid>` shows that process running, leave the worktree: it is released when the process ends. Never `git worktree remove -f -f` past a live lock.
- A link into the main checkout. An agent that ran the frontend suite in its worktree linked `frontend/node_modules` to the main checkout's. `unlink` any such link first (`test -L <path> && unlink <path>`), then remove the worktree, so no removal can follow the link into the main checkout's files.

Only when all three clear: `git worktree remove --force <path>`, `git worktree prune`, and `git branch -D <branch>`.

If any question does not clear, do NOT delete. Report the worktree. Say which question stopped it and what it holds. Leave it. A parked worktree costs disk; a deleted one costs the work.

Report which branches and worktrees were removed, and name anything skipped and why. If a branch had unmerged commits, do NOT delete it. Surface it to the user as its own item: that is a lost-work risk, not housekeeping.

This step is deletion, so it follows `file-protection`: say what is going before it goes. The check in step 1 is what makes that statement true rather than hopeful.

## Guards

- If docs-sync says "no changes needed" but there are uncommitted code changes, still proceed to git-sync
- If there is nothing to commit at all, report that and stop
- Do NOT push if the commit would include `.env`, secrets, or anything in the gitignore. Block and ask
- Do NOT push with an unexplained stray file in the tree. Every path from BOTH of Step 1b's sources, `git status --porcelain` and the filesystem walk, is classified there, or the push waits. A clean `git status` is not evidence the tree is clean, since `.gitignore` hides the duplicate-copy family from it.
- Do NOT push if pre-commit hooks fail. Fix the cause and create a NEW commit (never `--amend` after a hook failure)
- Do NOT push with any Step 0 gate red or unrun
- Do NOT push at a session end until `HANDOFF.md` has been rewritten this session (`/phase-checkpoint` Step 4); its `Last updated:` line reading today's date is the proof. No other document needs a date to be pushed

## Output

After all steps complete, report:

1. Step 0 gate results: each command and its exit code, and which were skipped and why
2. Files changed (count + list)
3. Commit hash
4. Push status (pushed / nothing to push / blocked)
5. The hash comparison proving the remote advanced (`git rev-parse HEAD` versus `git rev-parse origin/<branch>`)
6. Deploy status (Railway deploy reached SUCCESS, or not confirmed, and why)
7. Every untracked path that was found, and what happened to each: staged, ignored, removed, or left with a question
8. Worktrees and `worktree-agent-*` branches removed, and anything skipped with the reason
9. One-line summary of what was shipped
