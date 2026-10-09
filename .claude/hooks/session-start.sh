#!/bin/bash
# scope: project
# Session start context loader for agentic-search-ui (System 3).
# Prints date, recent commits, working tree, and scope reminder. The current
# focus is not printed: CLAUDE.md already loads it into every session.
echo "=== Session Context: agentic-search-ui (System 3) ==="
echo "Date: $(date '+%A, %B %d, %Y')"
echo ""
echo "--- Scope reminder ---"
echo "This repository = System 3 (search agent + FastAPI + LangGraph + React UI)."
echo "System 1+2 (data pipelines, KG loader) lives in a separate repository."
echo "The live graph is read-only via psycopg2. Never write to it from here."
echo ""
echo "--- Recent Commits ---"
git -C "$CLAUDE_PROJECT_DIR" log --pretty=format:"%h %s" -5 2>/dev/null || echo "(no git history)"
echo ""
echo ""
echo "--- Working tree ---"
git -C "$CLAUDE_PROJECT_DIR" status --short 2>/dev/null | head -10
echo ""
echo "=== Read CLAUDE.md for full instructions ==="
