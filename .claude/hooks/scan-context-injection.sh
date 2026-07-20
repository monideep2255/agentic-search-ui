#!/bin/bash
# scope: project
# depends_on: [.claude/rules/, .claude/skills/, CLAUDE.md, AGENTS.md]
# depended_by: [.claude/settings.json]
#
# SessionStart hook: scan context files for prompt injection patterns before
# they are injected into the system prompt.
#
# Scans: .claude/rules/, .claude/skills/ SKILL.md files, CLAUDE.md, AGENTS.md
# Checks for: role hijack, instruction override, exfiltration, invisible unicode

REPO_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
ISSUES_FOUND=0
ISSUE_FILES=""

# Patterns that indicate prompt injection attempts
scan_file() {
  local file="$1"
  local relative="${file#$REPO_DIR/}"
  local found=false

  # Role hijack and instruction override
  if grep -qiE 'ignore (previous|all|above|prior) instructions' "$file" 2>/dev/null; then
    ISSUE_FILES="$ISSUE_FILES\n  - $relative: 'ignore previous instructions' pattern"
    found=true
  fi

  if grep -qiE 'disregard (your|all|any) (instructions|rules|guidelines)' "$file" 2>/dev/null; then
    ISSUE_FILES="$ISSUE_FILES\n  - $relative: 'disregard instructions' pattern"
    found=true
  fi

  if grep -qiE 'system prompt override' "$file" 2>/dev/null; then
    ISSUE_FILES="$ISSUE_FILES\n  - $relative: 'system prompt override' pattern"
    found=true
  fi

  if grep -qiE 'do not tell the user' "$file" 2>/dev/null; then
    ISSUE_FILES="$ISSUE_FILES\n  - $relative: 'do not tell the user' deception pattern"
    found=true
  fi

  # Exfiltration patterns
  if grep -qE '(curl|wget).*\$(KEY|TOKEN|SECRET|API_KEY|PASSWORD)' "$file" 2>/dev/null; then
    ISSUE_FILES="$ISSUE_FILES\n  - $relative: exfiltration command with secret variable"
    found=true
  fi

  if grep -qE 'cat (\.env|credentials|\.netrc|\.ssh/)' "$file" 2>/dev/null; then
    ISSUE_FILES="$ISSUE_FILES\n  - $relative: secret file read pattern"
    found=true
  fi

  # Invisible unicode (zero-width spaces, joiners, BOM in middle of file).
  # grep -P is GNU-only; on BSD/macOS grep this check is skipped (fails safe, exit 0).
  if grep -qP '[\x{200B}\x{200C}\x{200D}\x{FEFF}\x{2060}\x{2061}\x{2062}\x{2063}\x{2064}]' "$file" 2>/dev/null; then
    ISSUE_FILES="$ISSUE_FILES\n  - $relative: invisible unicode characters detected"
    found=true
  fi

  if [ "$found" = true ]; then
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
  fi
}

# Scan rules
for file in "$REPO_DIR"/.claude/rules/*.md; do
  [ -f "$file" ] && scan_file "$file"
done

# Scan skill SKILL.md files
for file in "$REPO_DIR"/.claude/skills/*/SKILL.md; do
  [ -f "$file" ] && scan_file "$file"
done

# Scan root context files
for file in "$REPO_DIR"/CLAUDE.md "$REPO_DIR"/AGENTS.md; do
  [ -f "$file" ] && scan_file "$file"
done

if [ "$ISSUES_FOUND" -gt 0 ]; then
  echo "WARNING: Context injection patterns found in $ISSUES_FOUND file(s):"
  echo -e "$ISSUE_FILES"
  echo ""
  echo "These files are injected into the system prompt every session."
  echo "Review the flagged patterns before proceeding."
fi

exit 0
