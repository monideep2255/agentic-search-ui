#!/bin/bash
# scope: project
# Session start context loader for agentic-search-data-engineering.
# Prints date, current focus, recent commits, and a System 1+2 only reminder.
echo "=== Session Context: agentic-search-data-engineering ==="
echo "Date: $(date '+%A, %B %d, %Y')"
echo ""
echo "--- Scope reminder ---"
echo "This repo = System 1 (data pipelines) + System 2 (knowledge graph)."
echo "System 3 (search agent, FastAPI, LangGraph, UI) lives in a separate repo."
echo "Do NOT add System 3 dependencies or code here."
echo ""
echo "--- Current Focus ---"
sed -n '/^## Current focus/,/^---$/p' "$CODEX_PROJECT_DIR/AGENTS.md" 2>/dev/null | sed '$d'
echo ""
echo "--- Recent Commits ---"
git -C "$CODEX_PROJECT_DIR" log --pretty=format:"%h %s" -5 2>/dev/null || echo "(no git history)"
echo ""
echo ""
echo "--- Working tree ---"
git -C "$CODEX_PROJECT_DIR" status --short 2>/dev/null | head -10
echo ""
echo "=== Read AGENTS.md for full instructions ==="
