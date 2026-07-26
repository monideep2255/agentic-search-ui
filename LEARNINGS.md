# Learnings

What broke during the build, what was tried, and what actually fixed it. Written at the moment of failure, not reconstructed at phase end.

Maintained by the `learnings` skill. Read before opening any build phase, filtered to that phase's tools and layers. This file is also the captured record that feeds the Plan.md Step 6.2 reconciliation, so the PRD, tech spec, and strategic memo get updated from evidence rather than memory.

Newest entries at the bottom.

## Lessons

| Date | Applies to | What broke | What was tried | What fixed it |
|------|-----------|------------|----------------|---------------|
| 2026-07-26 | `.claude/hooks/sync-agents-md.sh`, Phase 5 | AGENTS.md silently drifted one line out of sync with CLAUDE.md. The body is supposed to be byte-identical from line 4 onward, and the sync hook normally guarantees it | Assumed the hook had not fired at all, and checked whether the hook script was broken. It was not; it had fired correctly on every earlier edit in the session | The hook is wired to PostToolUse on Edit and Write. The final change to CLAUDE.md was made with `sed -i` through Bash, which is neither, so the hook never ran. Any edit path that bypasses the Edit and Write tools also bypasses every PostToolUse hook. Use Edit for files that have hooks attached, or re-run the sync by hand afterward |
| 2026-07-26 | `.claude/` generally, Phase 5 | Six parallel agents each reported `git status --short` as empty after writing files, which read as "the write silently failed" | Checked for permission errors and for agents writing to the wrong path. Neither was true; the files existed on disk with correct content | `.claude/` is gitignored as of the 2026-07-25 untracking decision, so nothing inside it can ever appear in `git status`. Verify with `ls -la` and `git check-ignore -v`, not with `git status`, when working inside `.claude/`. This also means Phase 5's skill and rule work is not version controlled, see the note below |

## Standing notes

Phase 5 infrastructure is not in git. The 2026-07-25 decision untracked `.claude/`, so every skill, rule, agent, and hook lives only on this machine. Consequences to keep in mind:

- Skill and rule changes cannot be reviewed in a pull request, and will not appear in any diff.
- A fresh clone, a CI runner, or a new machine gets none of it, including the security hooks.
- There is no backup other than this working copy.

Tracked artifacts that survive: `LEARNINGS.md`, `tracker/`, `docs/`, `CLAUDE.md`, `AGENTS.md`, `README.md`, `DECISIONS.md`, `requirements/`, and `.github/`.
