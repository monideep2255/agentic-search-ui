---
description: "File naming conventions for meetings, prep docs, explanations, decisions, questions"
scope: portable
alwaysApply: true
---

## File naming conventions

**Use sentence case** - same rules as headings. Capitalize only the first word, proper nouns, acronyms, and named tools. Use underscores between words.

| Type | Format | Example |
|------|--------|---------|
| Meeting notes (simple) | `Month_Day.md` | `January_06.md` |
| Meeting notes (numbered) | `{number}_Meeting:{topic} {Month} {Day}.md` | `2_Meeting:technical_refinement_January_20.md` |
| Meeting notes (person) | `{number}_Meeting_{Person}_{Month}_{Day}.md` | `2_Meeting_Kimberly_January_22.md` |
| Meeting prep | `Prep_for_{Month}_{Day}.md` | `Prep_for_January_20.md` |
| Explanations | `Concept_explained.md` | `NCBI_project_explained.md` |
| Decisions | `Topic_decision.md` | `Neo4j_vs_ArangoDB_decision.md` |
| Questions | `Questions_for_X.md` | `Questions_for_first_WG_meeting.md` |
| Discussion/insight | `Topic_description_Month_Day.md` | `AI_as_programming_language_discussion_March_20.md` |

## Same-day sessions go in one file

When multiple working sessions or steps happen on the same day, keep them in a single dated file and append each new session as a section. Do not create a separate file per step. Name the file for the day and the span of steps it covers.

| Type | Format | Example |
|------|--------|---------|
| Same-day working session (meetings/) | `YYYY-MM-DD_Phase_N_steps_X-Y.md` | `2026-07-21_Phase_1_steps_1.6-1.7.md` |
| Same-day detailed record (phase_N/) | `Session_Month_Day.md` (one file per day, append each step as a section) | `Session_July_21.md` |
