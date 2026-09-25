# Build phase 8.5: housekeeping nobody sees

Branch: `phase/8.5-housekeeping`. Opened 2026-09-25, built alongside phases 8.1 and 8.2 on files neither touched.

The fifth phase of the overnight plan, `testing/Overnight_build_plan_2026-09-25.md`. Nothing here changes what a person using the product sees. It needs a pull request because it touches `.claude/` (the `git-workflow` rule), and a judge round; no adversary round, since no runnable product code changes, and no golden run, since nothing here is on the answer path.

## Table of contents

- [Tickets](#tickets)
- [Not built tonight](#not-built-tonight)
- [History](#history)
- [Findings](#findings)

## Tickets

### T-8.5-01: The graph's data gaps are handed to the repository that owns the graph (card 29)

Status: in-review, builder E, `02556f6`
Acceptance: `docs/data-engineering/Graph_data_hand_over_2026-09-25.md` states each gap with its measurement, date and query, and what a person loses because of it. Nothing under `reference/` is modified.

### T-8.5-02: The design card's four type values match the shipped code (card 34)

Status: in-review, builder E, `908980a`
Acceptance: `docs/build/design/design-system/foundations/type.html` carries theme.ts's h1, h2 and body1 values; `frontend/src/theme.ts` is untouched (the product owner's ruling, 2026-09-25).

### T-8.5-03: `/phase-checkpoint` names the counts line by what it holds, not a line number (card 40)

Status: in-review, builder E, `98b2d81`
Acceptance: `.claude/skills/phase-checkpoint/SKILL.md` no longer says "line 32" anywhere; each reference names the Current focus table's build row.

### T-8.5-04: The four streaming-timing test files are deleted together (card 37)

Status: in-review, builder E, `dab2757`
Acceptance: the four files are gone, collection still works, and the deletion inventory records the product owner's ruling.

### T-8.5-05: The deleted-file mystery is investigated (card 41)

Status: investigated, nothing changed: the repository's hooks are ruled out by their own matching rules (builder E); the lead found a process creating " 2" copies inside the repository mid-session, a ref file and `.git/index 2`, likely iCloud Desktop sync. Card 41 stays in To do with this lead.

### T-8.5-06: The Integrations page's two command examples, run as printed (card 30)

Status: measured by builder E: `s3 login` fails as printed (it needs the email) and `s3-kgx-export` needs graph credentials no public user has; `s3 ask` works. The page fix is in phase 8.4's branch (builder G, `22e0e2b`).

## Not built tonight

- Card 18, the Python lock file, and card 35, the USWDS package: each changes what develop builds or installs, and each deserves a morning with the product owner awake rather than an unattended deploy. Decided and ready to build.
- Card 39, merging bossman mode's two modes: due after a build phase closes, now true; a `.claude/` change of its own, left for a session with the owner.

## History

- 2026-09-25: builder E built tickets 01 to 06 in its own worktree; the lead merged develop into the branch and opened the pull request.

## Findings

Written the moment a finding is established.
