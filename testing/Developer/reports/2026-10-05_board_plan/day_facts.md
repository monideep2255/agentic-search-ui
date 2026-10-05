# 2026-10-05: the day's facts, for the checkpoint

The single source the 2026-10-05 checkpoint writers work from. Every claim here is checked against git, the board and the reports named.

## Merged into develop, in order

| Pull request | What a person notices | Board card |
|---|---|---|
| #155 | Documents: the whole-board plan, nine diagnoses, the board clean-up and the filing rule | none |
| #156 | The facts checker passes again after the 2026-10-04 rewording | 51, part |
| #157 | Every library's license text ships with the web app | 86 |
| #158 | Chromosome windows list their dbVar records; the colistin search finds mcr carriers instead of a false zero | 92; 94, part |
| #159 | One log line per guard-model and Jev call (time, outcome, upstream host) | 72, part |
| #160 | The TP53 dataset question uses the checked graph search | 91 |
| #161 | GERD keeps its reworded answer sentences; a record cited twice shows each sentence's own quote | 88; 57 |
| #162 | "recent-onset diabetes treatment" is answered; a bare subject is still asked back | 87 |
| #163 | A repair draft with more grounded sentences on the same records wins | 88 |
| #164 | No raw "[21]" markers in a long first sentence | 95 (new) |
| #165 | Plain language shows the isolates and genes table (isolate-only answers) | 94, part |
| #166 | One row per record (no duplicated OMIM row); an empty guard reply asks to try again | 97, 98 (new) |
| #167 | The Integrations card shows its commands; About shows its layer cards first; two page sentences corrected | 79, 80, 85 part |
| #168 | When no written summary survives, one plain line says why; a capped question lists what it gathered | 46, decision D1 |
| #169 | The answer names which search failed and why, which gene families an isolate search used, and when trials were not searched | 91, 77, 94 part |
| #170 | "Muir-Torré syndrome" spelled right (NCBI's own record carries broken encoding; repaired on arrival) | 96 (new) |
| #171 | A question about one paper uses a checked graph search | 15, step 1 |
| #172 | A paper's linked data (sequences, BioProjects, SRA, assemblies) from NCBI's live links | 74 |
| #173 | Organisms resolve through NCBI Taxonomy, with SRA and assembly routes | 56 (failed live, back in To do) |
| #174 | The isolates table also shows when an organism record sits beside the isolates | 94, part |
| #175 | The sentence check reads the whole record sentence a quote sits in; the writer quotes whole sentences | 89 |

## Test queries on develop (the gate)

- Morning (`testing/Developer/reports/2026-10-05_wave01_test_queries/`): queries 84, 76, 99, 1, 75, 68, 27, 29, 25, 24 passed; 33, 34, 37 failed (fixed later).
- Afternoon (`testing/Developer/reports/2026-10-05_wave2_test_queries/`): 27, GERD, the Integrations and About pages at 1280 and 390 passed; 33 and 37 failed (fixed by #174).
- Final (`testing/Developer/reports/2026-10-05_final_test_queries/results.md`): 9 of 10 passed: 33 twice, 37, 24, PMID 11237011, the Mediterranean question twice (names Familial Mediterranean fever), 75, 25. Failed: the SARS-CoV-2 question still answered about the disease SARS (card 56 back in To do).

## Board movement

- To do went from 78 to 51 cards: four dead cards removed (53, 62, 90, 93), ten moved to `testing/Future.md` rows 48 to 57, fifteen moved to Retest (13, 39 and 41 there for the owner to approve closing), card 99 added, card 56 returned.
- Retest, newest first: 89; 88; 74; 94 part; 92 with 95; 91 with 77; 87; 96 with 97; 46; 79, 80, 85 part; 86; 13, 39 and 41 (proposed for closing: superseded, done, done in the tracked tree); then the three older cards.
- Card 98 (an empty guard reply) is live with no query to type.
- New card 99: the sentence check approves rewordings that drop a qualifier ("young children" shown as "children"); waits on measuring the pair check (owner, 2026-10-05).

## Held, and why

- Phase 8.7 (the strongest writer, first sentence answers, records within seconds): resume plan `testing/Developer/reports/2026-10-05_phase_8.7_resume/plan.md`, decisions taken, waiting on an OpenRouter top-up (about $38.50 left against up to $60).
- The guardrail design (cards 84 and 72): waits on a fuller day of guard-call logs. Today's sample: Jev decides in 0.12 to 0.29 seconds; the guard model's on-topic check takes 1.3 to 7.3 seconds across five upstream hosts.
- Card 56: passed locally, failed on develop; next is why.

## Decisions logged today (DECISIONS.md, 2026-10-05)

Diagnose the nine together; board clean-up and the filing rule; the judge and the adversary set aside for now; the whole-board plan with D1 to D4 (the fallback line shown; a subject plus a request answered; the facts checker's patterns; the test queries document gates, the golden run is an alarm only); card 87's criterion names therapy options; card 96's repair on arrival; D9 (NCBI Taxonomy, no semantic search for now); phase 8.7's resume terms; the sentence check reads the whole record sentence, with the guard fallback kept; card 56's build choices; card 89 ships; dropped qualifiers measured first; Factory's lane.

## Process

- Factory, a second development agent, works the screen and wording lane (cards 43, 44, 18, 23, 24, 25, 47, the rest of 61) in its own worktrees on `factory/` branches. The lead keeps the answer path, the board, the plan and the one merge queue.
- Lessons in LEARNINGS.md, 2026-10-05: the shared git stash; CI starvation from several pull requests at once; untracked evidence and the leak guard; Jev's literal criteria; fixtures from real answers; paths with a space; parallel builders on one file.
