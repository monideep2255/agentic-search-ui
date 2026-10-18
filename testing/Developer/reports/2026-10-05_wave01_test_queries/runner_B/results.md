# Wave 01 test queries, runner B

Target: develop web and API, guest sessions only, a fresh guest session per question, Chrome headless at 1280 wide. Folder: `<repo-root>/testing/Developer/reports/2026-10-05_wave01_test_queries/runner_B/`. Scripts: `ask.mjs`, `ask_pick.mjs`, `poll.sh`. Each run has a `.png` (full page) and a `.txt` (answer text, buttons, link list).

## Table of contents

- [Wait for the card 87 merge](#wait-for-the-card-87-merge)
- [Query 84](#query-84)
- [Query 76](#query-76)
- [Queries 33, 34 and 37](#queries-33-34-and-37)
- [Query 99](#query-99)
- [Query 1](#query-1)
- [Summary](#summary)
- [Notes](#notes)

## Wait for the card 87 merge

- Probe at start: `recent-onset diabetes treatment` was asked back (`probe/probe0.txt`).
- Poll 1 at 18:03:48 UTC: asked back (`probe/poll1.txt`).
- Poll 2 at 18:05:17 UTC: NOT asked back (`probe/poll2.txt`). Develop served the card 87 fix about 2 minutes into the wait. The commit hash itself is not exposed by the API, so this is judged by behaviour.
- Log: `probe/poll.log`.

## Query 84

| Run | Bullet | Verdict | Evidence |
|---|---|---|---|
| `recent papers on statins` | Asks "How far back should I search?" with last 12 months, last 5 years, last 10 years | PASS | `q84_statins_recent_step1_askback.txt`, 6.7 s. Shows "How far back should I search?" and the three "Recent papers on statins from the last ..." choices |
| same, pick 5 years | Returns only papers from those years | PASS | `q84_statins_recent.txt`, 35.8 s from first submit. Five PubMed links (36693830, 36958647, 37186323, 37795366, 38325336), publication dates 2023 to 2024 by NCBI esummary |
| `papers on statins since 2022` | Not asked back | PASS | `q84_since2022.txt`, answered in 15.9 s with 5 papers |
| `recent-onset diabetes treatment` run 1 | Not asked back | PASS | `q84_recent_onset_run1.txt`, 24.8 s, "I found 5 published papers on this topic" |
| run 2 | Not asked back | PASS | `q84_recent_onset_run2.txt`, 19.8 s. Answered, but the content is off the question: "I found 1 condition related to diabetes" and a type 3c diabetes paragraph. Not a bullet failure, worth a look |
| run 3 | Not asked back | PASS | `q84_recent_onset_run3.txt`, 24.9 s, 5 papers |

The known note (a choice clicked after a redeploy loses its year limit) was not exercised.

## Query 76

| Question | Bullet | Verdict | Evidence |
|---|---|---|---|
| `reflux disease` | Asked back with "What would you like to know about ...?" and subject-specific choices | PASS | `q76_reflux.txt`, 4.6 s, 4 choices (what is it, genes, trials, recent research) |
| `GERD` | Same | PASS | `q76_gerd.txt`, 7.6 s, 4 choices |
| `BRCA1` | Same, gene-shaped choices | PASS | `q76_brca1.txt`, 3.1 s, 4 choices (gene, variants, trials, literature) |
| `Marfan` | Asked back | PASS | `q76_marfan.txt`, 9.1 s, "What aspect of Marfan syndrome are you interested in?" with 4 choices |
| `Any trials for GERD?` | Answered, not asked back | PASS on rerun | Run 1 `q76_trials_gerd.txt`, 49.7 s: "This run could not be completed. Try asking again in a moment." Rerun `q76_trials_gerd_rerun.txt`, 49.8 s: "I found 5 clinical trials related to GERD", 12 sources |
| `What is GERD?` | Answered, not asked back | PASS | `q76_what_gerd.txt`, 19.7 s, papers, condition and 5 trials |
| `papers on caffeine` | Answered, not asked back | PASS | `q76_caffeine.txt`, 55.8 s, 5 papers |
| `and BRCA2?` follow-up after query 1 | Answered, since the conversation gives context | NOT RUN | Budget |

## Queries 33, 34 and 37

All three answered in the web app as a guest. The answer shows 20 isolate source cards (10 per page, 3 pages) titled by strain, each linked to `ncbi.nlm.nih.gov/pathogens/isolates#/search/biosample_acc:...`. None shows a table headed "Isolates and their AMR genes", a gene column, or any gene name.

| Query | Bullet | Verdict | Evidence |
|---|---|---|---|
| 33 | Table "Isolates and their AMR genes" with 20 rows, accession, strain, place and date, gene list | FAIL | `q33_ecoli_esbl.txt`, `.png`: a one-column source list of strain names, no gene column, no heading, no place or date. 20 BioSample links are present |
| 33 | Every row carries a blaCTX-M gene | FAIL | No gene name appears anywhere in the page text |
| 33 | Count line and first 20 | PASS | "Pathogen Detection lists 141,055 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown." The count differs from 140,476, a newer snapshot, not a failure |
| 33 | Note that only blaCTX-M was searched and why | FAIL | No such note, only the count line under NOTES |
| 33 | E. coli linked to NCBI Taxonomy | PASS | `https://www.ncbi.nlm.nih.gov/taxonomy/562` |
| 33 | Well under a minute | PASS | 24.3 s |
| 34 | Same shape: list, accession, strain, genes, links | FAIL | `q34_salmonella.txt`: strain list only, some rows read "Pathogen sample", no genes shown |
| 34 | Exact count and first 20 | PASS | 20,423 Salmonella isolates, first 20 shown, 27.4 s |
| 34 | Same blaCTX-M disclosure | FAIL | Absent |
| 34 | Salmonella linked to its own Taxonomy record | PASS | `taxonomy/590` |
| 37 | Isolates carrying an mcr gene with full gene set, linked to each isolate page | FAIL | `q37_colistin.txt`: not a zero (12,563 isolates, 20 shown, 20 isolate links), but no mcr gene or any gene set is visible, so carriage cannot be confirmed from the page |
| 37 | Names the mcr prefixes searched | FAIL | Absent |
| 37 | Exact count and first-20 note | PASS | "12,563 ... the first 20 in the snapshot are shown" |

## Query 99

Evidence: `q99_THIRD_PARTY_NOTICES.txt` (saved copy of the fetched file).

| Bullet | Verdict | Evidence |
|---|---|---|
| Plain text file opens, not the Search page | PASS | HTTP 200, content-type text/plain |
| One section per package, sorted, equals line then PACKAGE, VERSION, LICENSE, full text | PASS | 25 PACKAGE sections, sorted, 27 equals lines (25 section openers plus separators) |
| react, react-dom, @mui/material present with version and license | PASS | react 19.2.8, react-dom 19.2.8, @mui/material 9.3.1, all MIT text |
| No package reads "no license file found" | PASS | 0 matches |

## Query 1

`q01_brca1.txt`, 13.6 s.

| Bullet | Verdict | Evidence |
|---|---|---|
| Answered, well within 90 s | PASS | 12.0 s |
| Diseases named in words, no bare code | PASS | "Familial breast-ovarian cancer susceptibility 1", "Fanconi anemia complementation group S" |
| Does not open on a broken sentence | PASS | "I found 4 conditions related to BRCA1." |
| Source links open ncbi.nlm.nih.gov pages | PASS by link list, not clicked |
| Progress screen details, sentence by sentence build | NOT CHECKED | Headless capture only |

## Summary

| Query | Bullets passed | Verdict |
|---|---|---|
| 84 | 6 of 6 runs and bullets | PASS |
| 76 | 7 of 7 run, 1 not run | PASS (one guard failure on the first trials run, passed on rerun) |
| 33 | 3 of 6 | FAIL: no gene table, no blaCTX-M note |
| 34 | 3 of 5 | FAIL: same |
| 37 | 1 of 3 | FAIL: no mcr genes shown (not a zero) |
| 99 | 4 of 4 | PASS |
| 1 | 3 of 3 checked | PASS |

## Notes

- "This run could not be completed" (card 72): once, `q76_trials_gerd.txt`. Rerun once, answered. Both recorded above.
- Budget: 19 submissions against 18. My first runs of 33 and 34 were cut short by my own script reading a progress line as an end state (the screenshot was of a half-run page); they were repeated as `q33_ecoli_esbl` and `q34_salmonella`, whose first attempts were overwritten. The statins question counts as two submissions only if the choice click counts.
- Isolate gene columns could be missing from the guest page text because they sit inside the collapsed Sources panel or card hover. Not opened, so the three isolate FAILs are "not visible on the answer page".
- Count differences from the document (141,055 against 140,476) are a newer snapshot and are not failures.
- The browser was installed Chrome via Playwright's chrome channel, since bundled Chromium is not installed.
