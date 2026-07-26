#!/bin/bash
# scope: project
# Session start context loader for agentic-search-ui (System 3).
# Prints date, current focus, recent commits, and scope reminder.
echo "=== Session Context: agentic-search-ui (System 3) ==="
echo "Date: $(date '+%A, %B %d, %Y')"
echo ""
echo "--- Scope reminder ---"
echo "This repo = System 3 (search agent + FastAPI + LangGraph + React UI)."
echo "System 1+2 (data pipelines, KG loader) lives in a separate repo."
echo "The live graph is read-only via psycopg2. Never write to it from here."
echo ""
echo "--- Current Focus ---"
sed -n '/^## Current focus/,/^---$/p' "$CLAUDE_PROJECT_DIR/CLAUDE.md" 2>/dev/null | sed '$d'
echo ""
echo "--- Recent Commits ---"
git -C "$CLAUDE_PROJECT_DIR" log --pretty=format:"%h %s" -5 2>/dev/null || echo "(no git history)"
echo ""
echo ""
echo "--- Working tree ---"
git -C "$CLAUDE_PROJECT_DIR" status --short 2>/dev/null | head -10
echo ""
echo "=== Read CLAUDE.md for full instructions ==="
