// Path helpers shared by the agent mods. Copied into every mod's hooks/kit/
// folder by sync_mods.py; edit the canonical copy only.
//
// Kit files hold pure functions only. The validator follows `$` only into
// functions declared in the same file as the hook, never across an import,
// so any helper that takes `$` lives in the mod's own register.ts. The
// snippets for those helpers are in SNIPPETS.md beside this file.

/** Relative path of `file` inside `root`, or undefined when it lies outside. */
export function inside(root: string, file: string): string | undefined {
  const r = root.endsWith('/') ? root : root + '/'
  if (file === root) return ''
  return file.startsWith(r) ? file.slice(r.length) : undefined
}

/** True when a path's last segment matches one of the given names or globs (`*` only). */
export function matchesAny(path: string, patterns: readonly string[]): boolean {
  return patterns.some(p => globToRegExp(p).test(path))
}

// Translate a glob to a RegExp matched against the end of a path. A single
// star and a question mark stay inside one path segment. A double star
// followed by a slash matches zero or more whole directories, so the glob
// "tools/(double star)/(star).py" matches both tools/a.py and tools/x/a.py.
// A trailing double star matches anything.
export function globToRegExp(glob: string): RegExp {
  const esc = (s: string) => s.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '[^/]*').replace(/\?/g, '[^/]')
  const body = glob
    .split('**/')
    .map(chunk => chunk.split('**').map(esc).join('.*'))
    .join('(?:[^/]+/)*')
  return new RegExp('(^|/)' + body + '$')
}
