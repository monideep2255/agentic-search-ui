// Per-repository settings for mod-route-capture.
export const config = {
  /** Edits under this folder count. */
  sourceRoot: 'frontend/src/',
  /** The capture script resolves Playwright from this folder, so it runs from here. */
  workingDir: 'frontend',
  /** The capture script, relative to workingDir. */
  script: '../.claude/skills/verify/scripts/capture.mjs',
  /** Spec files for /capture all, relative to the repository root. */
  specsDir: '.claude/skills/verify/specs',
  /**
   * Where each run's screenshots and results go, relative to the repository
   * root. logs/ is gitignored, so a capture never adds files git would track.
   * The capture script accepts --out only for a folder inside the repository.
   */
  outRoot: 'logs/capture',
  /** The capture script requires a topic for a run built from --screen. */
  topic: 'mod_capture',
  /** The local stack the script's local target uses: the ports fixed in frontend/playwright.config.ts. */
  webUrl: 'http://127.0.0.1:5273/',
  apiHealthUrl: 'http://127.0.0.1:8931/health',
  probeTimeoutMs: 2_000,
  captureTimeoutMs: 300_000,
  /** Screens a bare address reaches. Every other screen needs a spec with steps. */
  screenPaths: { home: '/', answer: '/' } as Record<string, string>,
  /** Files that never change what a screen shows. Globs with * and **, matched against the path under sourceRoot. */
  ignore: ['*.test.ts', '*.test.tsx', 'setupTests.ts', 'vite-env.d.ts', 'stubs/**'],
  /** Which screens a changed file can alter. Every rule that matches adds its screens. */
  rules: [
    { glob: 'components/screens/HomeScreen.tsx', screens: ['home'] },
    { glob: 'components/screens/AnswerScreen.tsx', screens: ['answer'] },
    { glob: 'components/screens/RunScreen.tsx', screens: ['answer'] },
    { glob: 'components/screens/RunProgress.tsx', screens: ['answer'] },
    { glob: 'components/screens/ReasoningLog.tsx', screens: ['answer'] },
    { glob: 'components/screens/SavedAnswerScreen.tsx', screens: ['answer'] },
    { glob: 'components/screens/savedAnswerMarkdown.tsx', screens: ['answer'] },
    { glob: 'components/screens/AboutScreen.tsx', screens: ['about'] },
    { glob: 'components/screens/ArchitectureScreen.tsx', screens: ['architecture'] },
    { glob: 'components/screens/InfoScreens.tsx', screens: ['about', 'architecture', 'integrations'] },
    { glob: 'components/answer/**', screens: ['answer'] },
    { glob: 'components/chat/**', screens: ['answer'] },
    { glob: 'components/controls/**', screens: ['answer'] },
    { glob: 'components/feedback/**', screens: ['answer'] },
    { glob: 'hooks/**', screens: ['answer'] },
    { glob: 'components/shell/**', screens: ['home', 'answer'] },
    { glob: 'components/brand/**', screens: ['home', 'answer'] },
    { glob: 'components/auth/**', screens: ['home', 'answer'] },
    { glob: 'components/guest/**', screens: ['home', 'answer'] },
    { glob: 'components/tour/**', screens: ['home', 'answer'] },
    { glob: 'App.tsx', screens: ['home', 'answer'] },
    { glob: 'main.tsx', screens: ['home', 'answer'] },
    { glob: 'index.css', screens: ['home', 'answer'] },
    { glob: 'theme.ts', screens: ['home', 'answer'] },
  ] as { glob: string; screens: string[] }[],
}
