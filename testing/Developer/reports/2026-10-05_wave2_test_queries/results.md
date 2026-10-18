# Wave 2 test queries on develop, 2026-10-05

Target: the develop web app, guest session, fresh per question, headless Chrome at 1280 wide. Runner: `run.mjs` in this folder, run from `<repo-root>/frontend`. Each run saved a .png and a .txt (answer text plus link list). 9 questions asked (GERD asked back each time, and the first ask-back choice was picked; those picks are counted inside the 4 GERD runs). No run showed "This run could not be completed", so no reruns.

## Query 33, E. coli ESBL (q33_run1, q33_run2), Plain language

- Table headed "Isolates and their AMR genes" with genes per isolate: FAIL. Neither run shows that heading or any gene. Seen: "WHERE THIS ANSWER COMES FROM" with only isolate names (C236-11, 11-3677 ...), 10 per page, page 1 of 3.
- Isolate line: PASS in form. "Pathogen Detection lists 141,055 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown." (expected text says 140,476; the count has moved).
- Note naming what was searched (blaCTX-M): FAIL as expected before a later merge. No such note in either run; Notes holds only the count line and "This is a research summary, not medical advice."
- E. coli with a Taxonomy link: not confirmed. Run 2 says "The taxonomy of these isolates is Escherichia coli.1"; the link list has only Pathogen Detection isolate links on page 1.
- Under a minute: PASS. Run 1 20.8 s (page timer), run 2 33.0 s.
- Differences between runs: run 1 prose lists the 20 isolate names; run 2 gives a one-line taxonomy sentence. Run 1 trust line "Based on 21 sources"; both without a gene column.

## Query 37, colistin (q37)

- Isolates with mcr genes in the table: FAIL. Only isolate names (KTE156, UMEA 3318-1, BIDMC 2B ...); no gene column, no mcr text anywhere.
- Full gene set and mcr prefixes named: FAIL, not shown.
- Exact count and first-20 note: PASS. "Pathogen Detection lists 12,563 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown."
- Also seen: "Note: no written summary could be checked against the records, so the records found are listed below with their sources", and "Based on 21 sources, not yet confirmed". Time 23.7 s.

## Query 27, chromosome window (q27)

- First sentence has no raw bracketed numbers: PASS. "I found 1 gene and 34 genetic variants related to BRCA1, RPL21P4, LOC127886930, ... and LOC111589215.1-20" (superscript range only).
- dbVar records listed: PASS. 5 `https://www.ncbi.nlm.nih.gov/dbvar/variants/nsv...` links in the list.
- BRCA1 named, ClinVar records present: PASS. 
- Seen as caveats: truncation note, "no written summary could be checked", and a note that 7 LOC and pseudogene entities were not addressed. Trust line "not yet confirmed". Time 14.3 s.

## Queries 75 and 68, GERD (4 runs; bare GERD asked back first, first choice picked)

Choices picked: researcher run 1 "What are the symptoms of GERD?", run 2 "What is GERD?", plain run 1 "What are the causes and symptoms of GERD?", plain run 2 "What is GERD?".

- Written answer above the tables: PASS in all four. No "no written summary" note appeared in any GERD run.
- Researcher run 1 (24.5 s): one sentence on children, a "COMPLICATIONS" paragraph, no treatment prose. Partial against "symptoms, complications and treatment".
- Researcher run 2 (14.3 s): definition, symptoms, complications, a "TREATMENT" paragraph, then tables. PASS, and longer than plain.
- Plain run 1 (18.2 s) two sentences; plain run 2 (25.1 s) longer, ends with the truncated text "...but GERD in children is a less common," in the .txt (cut at my 600 char display, not verified as cut in the app).
- Researcher longer than Plain: run 1 FAIL (about the same as plain run 1), run 2 PASS.
- Trials question (query 68 third item) not asked, per the brief. Records cited, with 5 ClinicalTrials.gov studies listed: PASS.
- Lowercase or "Another is titled" paragraphs: none seen.

## Query 24, MLH1 and MSH2 (q24)

- Garbled "Muir-TorrÃ© syndrome": still shows (FAIL for the fix, expected before a later merge). Source row 3 reads "Muir-TorrÃ© syndrome".
- Duplicated OMIM row: PASS. No OMIM row on page 1 and no repeated link in the link list.
- Both genes' condition records present: PASS (mutL homolog 1, mutS homolog 2, Lynch syndrome 1 and others). No "background search did not finish" line. Note: "does not address ... Colorectal cancer". Time 29.0 s.

## Integrations and About pages (integrations_1280/390, about_1280/390)

- Command line tools card shows the install as a command: PASS. Code block with `python3.11 -m venv s3-env`, `. s3-env/bin/activate`, `pip install "git+https://github.com/..."` (390 screenshot confirms code blocks, with "Copy install command").
- Integrations: four cards (REST and SSE, GraphQL, MCP server, Command line tools) and four chips: PASS.
- About shows layer cards before the walk-through: PASS. "How an answer is built" (Knowledge graph L1, Live NCBI APIs L2, Enrichment L3) comes before "What happens to your question".
- No sideways scroll at 390: PASS on both pages (scrollWidth 390 = clientWidth 390). 1280 also fits.

## Summary

| Item | Result | Time |
|---|---|---|
| Q33 run 1 and 2: table with genes | FAIL | 20.8 s, 33.0 s |
| Q33 blaCTX-M note | FAIL (expected, later merge) | |
| Q37: mcr genes in table | FAIL | 23.7 s |
| Q27: no raw brackets, dbVar listed | PASS | 14.3 s |
| Q75/Q68 GERD, written answer above tables (4 runs) | PASS | 14 to 27 s |
| GERD Researcher fuller than Plain | 1 of 2 runs | |
| Q24: Muir-TorrÃ© | still garbled (expected) | 29.0 s |
| Q24: duplicated OMIM row | PASS | |
| Integrations 1280 and 390 | PASS | |
| About 1280 and 390 | PASS | |
