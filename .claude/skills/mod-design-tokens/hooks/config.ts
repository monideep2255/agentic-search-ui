// Per-repository settings for mod-design-tokens.
export const config = {
  // Script and what it reads: tracker/check_design_tokens.py takes no arguments, scans frontend/src, exits 0 when clean and 1 with finding lines.
  command: ['python3', 'tracker/check_design_tokens.py'],
  watchedPrefix: 'frontend/src/',
  watchedExtensions: ['.ts', '.tsx', '.css', '.js'],
  debounceMs: 20_000,
  maxToasts: 3,
  timeoutMs: 30_000,
}
