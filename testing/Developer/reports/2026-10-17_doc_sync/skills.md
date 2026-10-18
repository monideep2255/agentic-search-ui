# Skills and registry edits for the LEARNINGS.md table move

- `.claude/skills/learnings/SKILL.md`: the "Entry format" lead line says append at the end of the file, which is the end of the Lessons table, no blank line before the row; the drift list now has four failures, the fourth a dated row outside the table.
- `.claude/skills/phase-checkpoint/SKILL.md`: Step 1b append rule names the end of the file; one new bullet confirms the new row is the last line and reports a `none` registry shape as the gap; the drift-check description (exit checklist area) adds a dated row outside either table.
- `.claude/skills/ship/SKILL.md`: Step 0 says a blank line inside either append-only table or a dated row outside either fails.
- `.claude/skills/precommit/SKILL.md`: the integrity list adds a dated row outside the table.
- `tracker/Living_documents.md`: LEARNINGS.md row shape is `## Index by theme`; `## Lessons`, Set by cites the 2026-10-17 decision. No date line moved.

Why Step 1b and /ship missed the class: the registry pinned LEARNINGS.md as `none`, so `--shape` could not see a wrong section, and Step 1b only said "no blank line inside the table".

`python3 tracker/check_living_docs.py --shape`: "living documents: 20 rows, shape as registered", exit 0.
