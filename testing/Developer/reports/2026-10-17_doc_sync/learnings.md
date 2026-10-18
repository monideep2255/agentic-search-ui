# LEARNINGS.md row repair and theme index

The repair of `LEARNINGS.md` after commit `468e8898` gathered every dated row into the one Lessons table at the end of the file. Once the drift check could see those rows, it reported malformed ones. This report says what was wrong, how each row was repaired, how the theme index changed, and how the work was checked.

## Table of contents

- [Result](#result)
- [Rows repaired](#rows-repaired)
- [Theme index](#theme-index)
- [How it was checked](#how-it-was-checked)

## Result

| Check | Outcome |
|---|---|
| `python3 tracker/check_doc_drift.py --check` | `ok: 2 facts computed \| 0 could not be computed \| 0 stale \| 0 structural`, no `LEARNINGS.md` finding |
| Word comparison of every dated row against `git show 468e8898:LEARNINGS.md` | Zero rows whose words differ |
| Lessons table position | Still the last section of the file, so the index's "below" stays true |
| Rows left unrepaired under the blocked-stop | None: every row had a boundary its own markup made plain |

## Rows repaired

Repairs are structural only. No word was added, removed or reworded. Rows are named by date and the start of their "Applies to" cell.

| Row | Fault | Repair, and how the boundary was decided |
|---|---|---|
| 2026-08-22, "Any TCP port probe run from inside this harness" | Too few cells; "what fixed it" never closed | The two dropdowns ran together as `</details> <details><summary>what fixed it`. The closing tag of the first dropdown is the boundary, so a cell separator went there. A `</details>` was added at the end of the last cell |
| 2026-08-22, "Remote operations over `ssh` from this harness" | Too few cells | Same boundary: a separator between `</details>` and `<details><summary>what fixed it` |
| 2026-10-09, "Overnight runs, background agents" | Too few cells | Same boundary |
| 2026-10-09, "Product check evidence fetched from NCBI" | Too few cells | Same boundary |
| 2026-10-09, "Reviewer probes in the shared scratchpad" | Too few cells | Same boundary |
| 2026-08-26, "Any gate that verifies a property of TEXT" | Too many cells; "what was tried" never closed | The literal pipes in `` `\|\|#` `` and `` `\|\| true` `` became `\|`. A `</details>` closes the "what was tried" cell before the separator that already stood in front of `<details><summary>what fixed it` |
| 2026-08-29, "Any cross-cutting log, audit trail, or instrumentation hook" | Too many cells | The literal pipes in `` `ok\|empty\|error` `` became `\|` |
| 2026-09-24, "Any scripted edit to a markdown table" | Too many cells | The literal pipe in the quoted substring `it is small \|")` became `\|` |
| 2026-08-30, "Any handoff whose next action was written by the session that just ended" | No dropdowns | The row already had five cells; the last two were wrapped in `<details><summary>what was tried</summary>` and `<details><summary>what fixed it</summary>` |
| 2026-08-30, "Any gate that exists only in CI" | No dropdowns | Wrapped the same way |
| 2026-08-30, "Any check that shells out to a subprocess to compute a fact" | No dropdowns | Wrapped the same way |
| Every 2026-08-16 row, and the 2026-08-17 rows on `RequestTimeoutExtension` and the premise gate found by a mutation sweep | "What fixed it" opened a dropdown and never closed it | A `</details>` was added at the end of the cell. The drift check does not test for a closing tag, so a scan of every row for matched `<details>` and `</details>` found these |
| Every 2026-08-21 row from "Any premise gate, and any ticket written from a specification" to "The shared findings ledger" | Same: "what fixed it" never closed | A `</details>` at the end of the cell |
| Every 2026-08-26 row before the TEXT row | "What was tried" never closed | A `</details>` before the separator in front of `<details><summary>what fixed it` |

After the repair, every dated row has five cells, and its last two cells each start with `<details><summary>` and end with `</details>`.

## Theme index

Changes to the "Index by theme" section:

- Removed "about 79 dated rows" from the intro, under the house rule that a document states no count. The sentence now says the table below has no anchors.
- Removed the two ranking claims, "the single most repeated failure in the file" and "the second most repeated failure in the file". Both rested on a count of rows, and with the later rows indexed neither theme is the largest. The dated fact beside the first, the self-counting instances up to an eleventh by 2026-08-14, stays.
- Added the dates of rows from 2026-08-16 to 2026-10-17 to the existing themes they fit, and widened four descriptions with one clause each naming what the later rows add: silent tooling failures, two writers on one file, environment and dependency traps, assertions that cannot fail.
- Kept every date the index already listed.

New themes, each shared by several rows that no existing theme named:

| Theme | What it groups |
|---|---|
| Lost work when an agent stops or a clean-up runs | Sleep, session limits, a lost network or a restart stopping agents, and clean-ups removing the only copy |
| Live sources that behave unlike their documentation or our assumption | NCBI fields in several shapes, an accession field that does not resolve, graph `LIMIT` timing, acronym lookups |
| A measurement misread as a finding | Sandbox port probes, cold caches, a shared database, load, a dropped tunnel, CI status read too early |
| A written claim trusted over what it describes | Handoffs, ledgers, board cells, commit messages, code comments, briefs and agent reports that the code or record contradicts |
| Scripted edits that cut, move or capture the wrong text | Heredoc appends, bulk replaces, rebases, splices, verbatim moves, a two-dot diff |
| Agents acting outside their role | Judges closing their own findings, builders marking tickets done, nested dispatch, turns ended on background work |
| Private data in committed evidence | A local path, a home-folder prefix and a submitter's name in evidence, and a scan blocking on untracked evidence |

Rows no theme names: these rows fit none of the themes and were not forced into one. Their dates are already listed under other themes, so each still appears in the index.

- 2026-07-27, the Conventional Commits type and scope mix-up.
- 2026-08-03, the build velocity post-mortem.
- 2026-08-05, the dormant token-pattern limitation armed by a later ticket.
- 2026-08-16, the citation URL pattern finding made exploitable by a new surface.
- 2026-09-22, the co-author trailer on every commit of one night.
- 2026-09-24, the ask-back decision built from fixed word lists.

## How it was checked

- The drift check, run from the worktree after each step; its line is in [Result](#result).
- A comparison script: for every dated row, in order, it strips `\|`, `<summary>...</summary>`, `<details>`, `</details>` and the cell pipes, splits on whitespace, and compares the word lists before and after against `git show 468e8898:LEARNINGS.md`. Its output:

```
dated rows before: 253, after: 253
rows whose markup changed: 31
rows whose words differ: 0
```

- A diff against `468e8898` outside the dated rows shows only the "Index by theme" section changed.
- A tag scan: every dated row now carries matched `<details>` and `</details>` pairs with the summaries "what was tried" and "what fixed it".
