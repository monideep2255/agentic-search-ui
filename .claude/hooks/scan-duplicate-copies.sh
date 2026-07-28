#!/usr/bin/env bash
# scope: project
# depends_on: [.gitignore]
# depended_by: [.claude/settings.json]
#
# SessionStart hook: detect macOS Finder/Archive Utility duplicate-copy
# artifacts (e.g. "env 2.py") before they pile up across multiple sessions.
# These appear when a file is copied into a folder that already has a
# same-named file (Finder "Keep Both", or a zip extracted over an existing
# folder), most often from moving work out of a bossman-mode worktree via
# Finder instead of git. .gitignore keeps them out of git; this hook makes
# sure a human actually sees them the next time a session starts.

REPO_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

MATCHES=$(find "$REPO_DIR" \
  \( -path "$REPO_DIR/.git" -o -path "$REPO_DIR/node_modules" \
     -o -path "$REPO_DIR/venv" -o -path "$REPO_DIR/.venv" \
     -o -path "$REPO_DIR/.claude/worktrees" -o -name "__pycache__" \) -prune -o \
  -type f -print 2>/dev/null | grep -E ' [0-9]+\.[A-Za-z0-9]+$')

if [ -n "$MATCHES" ]; then
  COUNT=$(echo "$MATCHES" | wc -l | tr -d ' ')
  echo "WARNING: $COUNT file(s) matching the macOS duplicate-copy pattern ('name N.ext') found:"
  echo "$MATCHES" | sed "s|^$REPO_DIR/|  - |"
  echo ""
  echo "These are usually stray Finder/Archive Utility copies, not real source files."
  echo "Diff each against its non-suffixed counterpart, then move it to Trash (rm is hook-blocked)."
fi

exit 0
