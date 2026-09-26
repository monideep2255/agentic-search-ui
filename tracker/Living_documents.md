# Living documents

The registry of every document a session-closing skill keeps current. One row per document, and each row gives:

- Its one job.
- The skill that owns its upkeep.
- Its current shape, by section name.
- The line that carries its freshness date.
- The DECISIONS.md rows that set the shape.

`/phase-checkpoint` and `/ship` read this file at their first step and take every section name, column name and file path from it. Neither skill hardcodes a section name. When the product owner reshapes a document, the change is one row edit here plus one DECISIONS.md row. No skill is rewritten. A skill never creates, rebuilds or rewrites a section this file does not list.

`python3 tracker/check_living_docs.py` reads the same rows: `--shape` proves every named anchor still exists in its document, `--fresh` proves every freshness date is today. A red `--shape` is not an instruction to put the section back. It means the document changed shape and this registry has not caught up, which is exactly the case the decision guard in `/phase-checkpoint` exists for.

Last updated: 2026-09-25.

## Table of contents

- [How to read a row](#how-to-read-a-row)
- [The registry](#the-registry)
- [The decision guard watermark](#the-decision-guard-watermark)
- [Why the registry lives here](#why-the-registry-lives-here)

## How to read a row

- Document: the path, relative to the repository root. A path with `<date>` in it is a family; none is registered today, since the product owner stopped the daily `testing/Shipped_<date>.md` files on 2026-09-24 ("Yes, stop them"). The three that exist are records, folded into the two testing rows below, and no skill writes or reads one.
- Job: the one fact the document owns. Everything else points at it.
- Owner: the skill or ritual that edits it. A skill not named here does not edit the document.
- Shape: the anchors the owner may write to, one per `;`, each an exact heading or a line prefix as it appears in the file. `none` means the owner appends rows to a table and touches no section. `unpinned` means the shape is mid-change and must be pinned in the commit that lands it.
- Freshness: the text that precedes the document's date on its one dated line (`--fresh` at every `/ship` requires that date to be today), or `none` for an append-only file whose rows carry their own dates, and for a file whose date moves on its own cadence rather than at every checkpoint.
- Set by: the DECISIONS.md rows, by date and short title, that established the current shape. A shape with no row was set before this registry existed.

## The registry

| Document | Job | Owner | Shape | Freshness | Set by |
|---|---|---|---|---|---|
| `HANDOFF.md` | What a fresh session needs and nothing else: what is live, what awaits the product owner, the one next action, pointers | `/phase-checkpoint`, every mode, rewritten in place | `## Table of contents`; `## What is live`; `## What awaits the product owner`; `## The one next action`; `## Where the facts live` | `Last updated:` | 2026-09-24, HANDOFF.md replaces the Phase 6 continuation prompt |
| `tracker/Living_documents.md` | This registry | `/phase-checkpoint` Step 0, the decision guard; the product owner by hand | `## The registry`; `## The decision guard watermark` | `Last updated:` | 2026-09-24, one registry for the living documents |
| `testing/UI_fix_plan.md` | The board: what is not started, what is being built now, what is live awaiting retest; and, under To do, the detail behind the product owner's architecture cards, with their direction of 2026-09-23 verbatim | `/phase-checkpoint` UI-fix-loop mode, and whoever moves a card during work | `## To do`; `## Build in progress`; `## Retest` | `Last updated:` | 2026-09-24, the plan is split by job; 2026-09-24, the plan becomes a kanban board; 2026-09-24, the owner's architecture work stays in To do, never parked; 2026-09-24, exactly three sections, no table of contents, everything inside To do |
| `testing/UI_fixes_done.md` | Every closed item with its detail, the detail behind every card except the architecture cards, whose detail sits under To do on the board, the cutoff, and each day's shipped list as a session table | `/phase-checkpoint` UI-fix-loop mode | `## Done features at a glance`; `## Where we stopped`; `### Next, in order`; `### How to start the next session`; `## Detail for items on the board`; `## Session history` | `LAST UPDATED` | 2026-09-24, the plan is split by job; 2026-09-24, the plan becomes a kanban board |
| `testing/Test_queries_and_workflows.md` | Every query worth typing, what a person should see, and the retest steps the board's Retest cards point at by query number | `/phase-checkpoint` UI-fix-loop mode | `## Every feature and where to try it`; `Queries to try:`; `What you should see:` | `Last updated:` | 2026-09-24, one shape per feature and the shipped lists folded in |
| `testing/Future.md` | The remaining work outside the UI fix loop: Plan.md's Phase 7 backlog and the still-open findings, each a card with where its detail lives, plus the list checked and found closed | `/phase-checkpoint`, every mode | `## To do`; `## Checked and closed`; `## How this file is kept` | `Last updated:` | 2026-09-24, remaining work outside the UI fix loop gets its own file |
| `PROGRESS.md` | The plain-language state of the project, for a reader outside the build | `/phase-checkpoint`, every mode | `## What works today`; `## What does not work yet`; `## The story so far, sprint by sprint`; `## What is next`; `## Problems we know about and are tracking` | `Last updated:` | none recorded |
| `requirements/Plan.md` | The phase narrative and the build narrative (the per-phase story that used to sit in CLAUDE.md and the board) and the phase status table. It states no count: the line under the status table points at `python3 tracker/check_doc_drift.py --counts` | `/phase-checkpoint`, every mode: Revision history entry always, status table in build-phase mode only | `## Status at a glance`; `## Revision history` | `Last updated:` | 2026-07-27, the checkpoint covers build phases; 2026-09-24, the build narrative moves out of CLAUDE.md and the board into Plan.md; 2026-09-25, the lead implements both harness reviews' takeaways (counts are computed on demand, never stated) |
| `CLAUDE.md` and `AGENTS.md` | The instructions every agent loads. They state no count: the Current focus table's build row points at `python3 tracker/check_doc_drift.py --counts`. NOT the build narrative: it moved verbatim to Plan.md on 2026-09-24, and no skill writes narrative here | `/phase-checkpoint` Step 5d for the counts and the date; `docs-sync` for the tables | `## Current focus`; `## Skills`; `## Sub-agents` | `Last updated:` | 2026-08-02, one owner per fact; 2026-09-24, the build narrative moves out of CLAUDE.md and the board into Plan.md; 2026-09-25, the lead implements both harness reviews' takeaways (counts are computed on demand, never stated) |
| `DECISIONS.md` | Every choice between alternatives, append-only | `/phase-checkpoint` Step 1, and anyone at the moment of a decision | `none` | `none` | none recorded |
| `LEARNINGS.md` | Every failure and its fix, append-only | the `learnings` skill, and `/phase-checkpoint` Step 1b | `none` | `none` | none recorded |
| `tracker/BOARD.md` | Build phase status and open flags, build phases only; its narrative paragraphs moved to Plan.md on 2026-09-24 | the `task-tracker` skill. The UI fix loop never writes it | `## Status counts` | `none`: its date moves when a build phase moves, not at every checkpoint | none recorded |

## The decision guard watermark

`/phase-checkpoint` Step 0 reads every DECISIONS.md row below this watermark, updates the rows above for any decision that changes a document's shape or a process, then moves the watermark. The watermark is a row number and a date, never a count of rows, so the drift checker does not read it as a claim.

Guarded through DECISIONS.md row 716, dated 2026-09-25, the product owner's answers of the overnight plan and the lead's decisions of that night. None of them changes a registered document's shape or a process this skill runs: the overnight plan (`testing/Overnight_build_plan_2026-09-25.md`) and the settings log (`testing/Overnight_settings_log.json`) are records of one night, not living documents, and the board and the test queries keep their registered shapes.

## Why the registry lives here

- `tracker/` already holds the machinery that keeps documents honest: `BOARD.md`, `check_doc_drift.py` and the phase files. A registry of living documents is the same kind of thing.
- It is not under `.claude/`, so a change to it needs no pull request under `.claude/rules/git-workflow.md`. A file the product owner must edit on the day they reshape a document cannot sit behind a branch.
- It is a plain markdown table, so any agent, not only this harness, can read it, which is the portability rule in `CLAUDE.md`.
