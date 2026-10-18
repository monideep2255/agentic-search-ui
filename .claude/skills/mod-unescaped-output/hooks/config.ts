// Per-repository settings for mod-unescaped-output.
export const config = {
  frontendPrefix: 'frontend/src/',
  frontendExtensions: ['.ts', '.tsx', '.js', '.jsx'],
  pythonPrefix: 'src/',
  pythonExtension: '.py',
  maxToasts: 3,
  // Files that already hold an audited use of a pattern. A match in one of these is silent when the same
  // line is already in the file on disk, so editing near an old line does not nag about it. A new line warns.
  // Found by grepping frontend/src: every target="_blank" site carries rel="noopener noreferrer" today, the two
  // screens below only name dangerouslySetInnerHTML in comments that explain why it is forbidden
  // (rule: .claude/rules/production-standards.md), and routing.ts only reads window.location.
  allowlist: {
    'frontend/src/components/answer/CitationMarkers.tsx': ['target-blank'],
    'frontend/src/components/shell/PersonaChip.tsx': ['target-blank'],
    'frontend/src/components/screens/SavedAnswerScreen.tsx': ['target-blank', 'dangerously-set-inner-html'],
    'frontend/src/components/screens/InfoScreens.tsx': ['target-blank'],
    'frontend/src/components/screens/AnswerScreen.tsx': ['target-blank'],
    'frontend/src/components/screens/savedAnswerMarkdown.tsx': ['dangerously-set-inner-html'],
    'frontend/src/lib/routing.ts': ['location-assign'],
  } as Record<string, string[]>,
}
