# Card 94 adversary round, 2026-10-15 (pull request #244)

Adversary, dial position 2, one round. Branch 2aceb25e against develop 7626fe85, each in its own scratch worktree. Findings are appended as they are established.

## Findings

### A2-94-01: a Listeria innocua isolate Pathogen Detection holds is reported "not found", because a genus name sends the lookup to the wrong folder
- Severity: major
- What: `organism_of_record` maps the BioSample record's organism through `_find_organism`, whose genus entries (`Listeria`, `Klebsiella`, `Campylobacter`, `Shigella`) catch every species of that genus. Pathogen Detection files several of those species in their own folders (`Listeria_innocua`, `Klebsiella_oxytoca`, 14 `Enterobacter_*`, 13 `Neisseria_*` and so on, from the live FTP listing of `pathogen/Results/`). A Listeria innocua BioSample is looked up in the `Listeria` folder, which holds only L. monocytogenes (86,532 rows, every one monocytogenes, read live), reads it to the end inside the 8 s bound, and the answer states the isolate is not in Pathogen Detection.
- Reproduction: branch 2aceb25e, `run_streaming`, reads_placement=True, develop's settings. Question: `What is known about Listeria isolate SAMN01909077 in Pathogen Detection?` Answer, 13.1 s, trust "ask": "SAMN01909077 was not found in NCBI Pathogen Detection's Listeria data, so only its BioSample record is shown." The tool result was `pathogen_detection empty`, at 8.4 s. The live file `Listeria_innocua/latest_snps/Metadata/PDG000000091.232.metadata.tsv` holds `SAMN01909077`, strain `FSL J1-023`, target `PDT000008493.3`.
- Why it matters: a confident wrong "not in Pathogen Detection" about a record Pathogen Detection holds. The person cannot tell that only the L. monocytogenes folder was read: "Pathogen Detection's Listeria data" reads as all of Listeria. The same mapping sends Klebsiella oxytoca, michiganensis and planticola (6,825 rows in `Klebsiella_oxytoca`) to `Klebsiella`, see A2-94-02.
- NOT FIXED

### A2-94-02: a Klebsiella oxytoca isolate reads "took too long", when no amount of time would find it in the folder searched
- Severity: major
- What: same root as A2-94-01. The record's organism "Klebsiella oxytoca" matches the genus entry `Klebsiella`, so the lookup scans `Klebsiella` (177,378 rows, none of them oxytoca or michiganensis, read live in 17 s with curl). Pathogen Detection files this isolate in `Klebsiella_oxytoca`. The 8 s bound stops the scan, and the line blames time.
- Reproduction: branch, `What is known about Klebsiella isolate SAMN02463894 in Pathogen Detection?` 16.2 s, trust "ask", the code-built list note, and "The Pathogen Detection lookup took too long and was stopped, so only the BioSample record of SAMN02463894 is shown." Tool result `pathogen_detection error` at 13.1 s (started 4.8 s). Develop, same question: 7.0 s, trust "answer", a written sentence about the BioSample record, no Pathogen Detection line. The live `Klebsiella_oxytoca/latest_snps/Metadata/PDG000000030.1298.metadata.tsv` holds `SAMN02463894`, target `PDT000008935.2`.
- Why it matters: the person is told the lookup was slow, so they retry; it can never succeed. Here the branch is 9 s slower than develop, loses the written answer and its trust label, and adds a line that points at the wrong cause.
- NOT FIXED

### A2-94-03: a BioSample with two Pathogen Detection isolates shows one, and the summary counts one
- Severity: minor
- What: the lookup reads with `max_matches=1, one_row_per_key=True` on the assumption "biosample_acc is unique per row in Metadata". It is not: live, `SAMEA3110714` has two rows in the Salmonella metadata (`PDT000050599.1` and `PDT000069594.1`, both strain H58), and Listeria_innocua has 3 such BioSamples and Klebsiella_oxytoca 1 (`SAMN02463897`: `PDT000012332.2` and `PDT000071276.1`).
- Reproduction: branch, `What is known about Salmonella isolate SAMEA3110714 in Pathogen Detection?` 9.3 s: one isolate row `H58 | SAMEA3110714 | aph(3'')-Ib, aph(6)-Id, blaTEM-1, catA1, dfrA51, dfrA7, gyrA_S83F=POINT, ... | Not recorded`, and "Found 1 pathogen detection isolate record". In this case the two rows' AMR genotypes are identical, so nothing shown is wrong; I did not find a pair whose genes differ, and did not look past the first 60,000 Salmonella rows.
- Why it matters: when the two isolates of one sample differ (a re-analysis, a second assembly), the person sees one gene list stated as the sample's, with nothing saying a second exists. Unsure how often the genes differ.
- NOT FIXED

### A2-94-04: a question naming two isolates now gets a one-row isolate table for the first, and nothing about the second
- Severity: minor
- What: confirmed live; the single-accession limit is older than this card (A-94-02 of 2026-10-09 filed it read-only). What is new is that the first accession now arrives as an "Isolates and their AMR genes" table, so the answer reads as complete.
- Reproduction: branch, `Compare Salmonella isolates SAMN02147118 and SAMEA1705941 in Pathogen Detection.` 13.0 s: one isolate row (SQ0227, SAMN02147118), "Found 1 pathogen detection isolate record, 1 biosample record and 1 sra record". SAMEA1705941 appears nowhere. Develop: 7.1 s, the SAMN02147118 BioSample only, with the code-built list note; SAMEA1705941 also absent.
- Why it matters: a comparison question is answered about one isolate with no line saying the other was not looked up. Pre-existing gap, newly better dressed.
- NOT FIXED

### A2-94-05: an isolate of another organism than the one the question names is shown with no word that the organism differs
- Severity: unsure
- What: the organism comes from the BioSample record by design (query 42's text). The answer does not say that the record's organism is not the one the person named.
- Reproduction: branch, `What is known about Salmonella isolate SAMN02368173 in Pathogen Detection?` 31.9 s (think alone took 28 s, LLM variance, not the card): the table "Isolates and their AMR genes" with `ESC0165 | SAMN02368173 | acrF, blaEC, mdtM | USA, date not recorded`; the only organism word is inside the record title "Pathogen sample from Escherchia coli". No line says "this is an E. coli sample, not Salmonella". Develop shows the same BioSample record, also without a mismatch line, and no isolate table.
- Why it matters: the isolate shown is the one the accession names, so this is not a wrong record. But a person who typed the accession expecting Salmonella sees an AMR gene table under their Salmonella question; a typo in the accession would look the same. Filed as unsure: the owner's design may accept it.
- NOT FIXED

### A2-94-06: the "no organism" line tells the person Pathogen Detection does not cover organisms it does cover
- Severity: minor
- What: `LOOKUP_NO_ORGANISM` reads "its BioSample record names no organism that Pathogen Detection covers here". The table holds 20 organisms; the live FTP listing has over 100 folders. Probed `organism_of_record` on the branch: `Neisseria meningitidis`, `Vibrio parahaemolyticus`, `Enterobacter hormaechei`, `Streptococcus pyogenes`, `Clostridium perfringens`, `Enterococcus hirae`, `Staphylococcus pseudintermedius` all return None, and each has its own Pathogen Detection folder (`Neisseria_meningitidis`, `Vibrio_parahaemolyticus`, `Enterobacter_hormaechei`, ...). The same probe gives `Salmonella phage P22 -> Salmonella`, so a phage BioSample is looked up as a Salmonella isolate.
- Reproduction: `PYTHONPATH=<branch>/src python -c "from system_03_search_agent.core.isolate_search import organism_of_record as o; print(o('Neisseria meningitidis'), o('Salmonella phage P22').taxon_folder)"` prints `None Salmonella`. Not run live through the app.
- Why it matters: "names no organism that Pathogen Detection covers" reads as a fact about Pathogen Detection, and is false for these. The word "here" carries the whole qualification. The build report's "Not covered" names the 20-organism limit, but not that the line misstates it.
- NOT FIXED

### A2-94-07: only the oldest tenth or so of Salmonella isolates is reachable in 8 s; any recent isolate reads "took too long" and costs 5 to 14 s over develop
- Severity: major
- What: the Salmonella metadata file is 870,471,095 bytes (live `Content-Length`), in submission order, so recent isolates sit at its end. I picked real isolates at fixed byte offsets with HTTP range reads and asked about each once on both trees. The build report's "roughly a quarter of the way into the file" is optimistic: 25% was not reached.
- Reproduction: question `What is known about Salmonella isolate <acc> in Pathogen Detection?`, one run each, branch then develop:

| Position in file | Accession | Branch | Lookup span | Branch shows | Develop |
|---|---|---|---|---|---|
| 3% | SAMN03765217 | 11.4 s | 3.4 to 7.5 s | isolate row | 7.6 s |
| 6% | SAMN05928274 | 13.0 s | 4.5 to 10.9 s | isolate row | 8.3 s |
| 10% | SAMN07573505 | 13.4 s | 6.1 to 12.2 s | isolate row | 9.0 s |
| 25% | SAMN12547597 | 14.5 s | 4.8 to 13.3 s | "took too long" | 12.8 s |
| 50% | SAMN28036139 | 20.7 s | 10.0 to 18.8 s | "took too long" | 6.5 s |

- Why it matters: query 42 passes because SAMN02147118 is row 1 of the file. A researcher asking about an isolate from the last several years (the 25% isolate is from 2019, the 50% one from 2022) waits longer than on develop and gets one more line saying the lookup was stopped, never the isolate. Both stopped answers also list the assembly named `PDT000559774.1` / `PDT001297987.1`, the very Pathogen Detection isolate the lookup "took too long" to find, beside the line "so only the BioSample record ... is shown", which is also untrue as worded since SRA and assembly rows are shown too.
- NOT FIXED

### A2-94-08: a Salmonella BioSample Pathogen Detection does not hold now always ends "ask" with the code-built list, 5 to 10 s slower than develop
- Severity: minor (unsure on the trust part: small samples)
- What: for the not-held BioSample the lookup always runs to the 8 s bound, so the answer is slower than develop on every run, and in my runs the trust label was "ask" with the fallback note on every branch run.
- Reproduction: `What is known about Salmonella isolate SAMN64233002 in Pathogen Detection?`, four runs per tree, sequential, both trees at once.
  - Branch: 21.0, 14.9, 19.6, 14.5 s; trust ask, ask, ask, ask; each with "The Pathogen Detection lookup took too long and was stopped, so only the BioSample record of SAMN64233002 is shown." and "Note: no written summary could be checked against the records, ...". Lookup spans 8.2, 8.2, 8.2, 8.2 s.
  - Develop: 10.4, 9.4, 10.0, 11.4 s; trust ask, ask, answer, ask.
  - Pooled with the build report (branch 11 of 12, develop 5 of 9): branch 15 of 16 "ask", develop 8 of 13.
  - Query 42 (isolate found) goes the other way in my runs: branch ask 1 of 4 (29.9, 10.6, 7.2, 9.3 s; the 29.9 s run spent 25 s before Plan, in guard and think), develop ask 3 of 4 (9.2, 12.4, 7.0, 6.8 s).
  - All "lookup showed no isolate" questions in this round, paired: branch "ask" 6 of 9 runs, develop 4 of 8.
- Why it matters: for the not-held case the person waits about twice as long as on develop, one run passes the 20 s goal (21.0 s), and the answer looks less trustworthy than develop's more often, with nothing more to show for it than a line that the lookup was stopped. I cannot say from 16 against 13 runs that the lookup causes the extra "ask"; the direction is consistent.
- NOT FIXED

### A2-94-06, addendum: reproduced live
- Branch, `What is known about Neisseria meningitidis isolate SAMN02603997 in Pathogen Detection?` 8.6 s, trust "ask": "Pathogen Detection was not looked up for SAMN02603997: its BioSample record names no organism that Pathogen Detection covers here, so only the BioSample record is shown." The live `Neisseria_meningitidis/latest_snps/Metadata` file holds `SAMN02603997`, strain `MC58`, target `PDT000004526.3`. The progress events also carry a `pathogen_detection` tool result "empty" for a lookup that never ran. Develop, same question: 15.3 s, trust "ask", the same three records, no line.

### A2-94-09: an isolate named by its strain gets a clarification that does not say to use the BioSample accession
- Severity: minor (pre-existing, same on develop)
- What: a strain name is not an accession, so the card's lookup does not run; the isolate-question shape asks which kind of record instead.
- Reproduction: both trees, `What is known about Salmonella isolate SQ0227 in Pathogen Detection?` (SQ0227 is SAMN02147118's strain). Branch 7.5 s, develop 3.8 s, both "refuse": "Which kind of Salmonella record do you want? For example Salmonella genome assemblies, Salmonella SRA sequencing runs, or Salmonella isolates in Pathogen Detection that carry a resistance gene family, such as ESBL or carbapenemase genes." No tool ran on either.
- Why it matters: a refusal should say what to type next; the one thing that would work, the BioSample accession, is not offered. Not caused by this card.
- NOT FIXED

## Not findings, checked

- Privacy: no email address in any event payload of 69 runs (regex over every payload). The BioSample `organization` field matched answer text for two records only because it reads "NCBI" (it matched the citation host). `logs/tool_audit.jsonl`, written to the working folder of the run, carries request parameters and record ids only. The isolate row's fields are strain, accession, genes, place and date; no Pathogen Detection `collected_by` field is read.
- SAMEA and SAMD accessions: SAMEA1705941 (row 2,596) and SAMD00043356 (row 34,332) were found, with the right strain and genes, in 6.7 and 9.3 s.
- Shigella: `E. coli isolate SAMN02604096` (a Shigella flexneri record) was looked up in `Escherichia_coli_Shigella` and found, 7.7 s.
- Query 42 found its isolate in 10 of 10 of my runs (4 sequential, 6 three at a time), lookup 1.5 to 5.2 s. The build report's 1 of 6 "took too long" did not reproduce.
- Controls 33 to 37: the same 21 rows and the same count sentence on both trees (counts read 141,578, 20,472, 2,716, 88,701 and 12,587 on both; the test document's figures are an older snapshot). Times vary both ways with the isolate scan, which this card does not touch.
- Three BioSample questions with no isolate word: no lookup planned, same rows on both trees.
- The "lookup span" in A2-94-07 and A2-94-08 runs from the `tool_start` event, emitted at Plan, so it includes the BioSample fetch the lookup waits for (about 0.3 to 1 s).

## Timing, branch against develop

One run each unless listed; both trees ran at the same time, each sequential.

| Question | Branch seconds | Develop seconds |
|---|---|---|
| Listeria innocua SAMN01909077 | 13.1, 12.3 | 7.5 |
| Klebsiella oxytoca SAMN02463894 | 16.2 | 7.0 |
| Salmonella named, E. coli record SAMN02368173 | 31.9 (28 s in think) | 10.8 |
| E. coli named, Shigella record SAMN02604096 | 7.7 | 6.2 |
| SAMEA3110714 (two isolates) | 9.3 | 6.9 |
| SAMEA1705941 | 6.7 | 5.3 |
| SAMD00043356 | 9.3 | 6.8 |
| Two accessions, "Compare" | 13.0 | 7.1 |
| Strain name SQ0227 | 7.5 | 3.8 |
| Salmonella at 3% of file | 11.4 | 7.6 |
| Salmonella at 6% | 13.0 | 8.3 |
| Salmonella at 10% | 13.4 | 9.0 |
| Salmonella at 25% | 14.5 | 12.8 |
| Salmonella at 50% | 20.7 | 6.5 |
| Neisseria meningitidis SAMN02603997 | 8.6 | 15.3 |
| Query 42, SAMN02147118 | 29.9, 10.6, 7.2, 9.3 | 9.2, 12.4, 7.0, 6.8 |
| Not held, SAMN64233002 | 21.0, 14.9, 19.6, 14.5 | 10.4, 9.4, 10.0, 11.4 |
| Query 33 | 34.9 | 35.4 |
| Query 34 | 59.2 | 53.1 |
| Query 35 | 67.3 | 72.5 |
| Query 36 | 22.2 | 19.4 |
| Query 37 | 52.5 | 40.6 |
| What is BioSample SAMN02147118? | 6.0 | 8.7 |
| Runs linked to BioSample SAMEA3110714 | 6.4 | 5.0 |
| Where and when was SAMN07573505 collected? | 9.3 | 6.2 |

Spend: 69 runs, $0.2302, no Opus.

## Verdict

FAIL. A2-94-01 is a false "not found" about a record Pathogen Detection holds, A2-94-02 a "took too long" that more time could never fix, and A2-94-07 shows the lookup reaches only about the first tenth of the Salmonella file, so most real isolates read "took too long" and arrive slower than on develop.

A2-94-01, A2-94-02 and A2-94-06 sit inside this phase's own fix: reading the organism from the BioSample record was the fix for A-94-01 of 2026-10-09 (wrong folder), and the not-found line was the fix for A-94-04. The same table still sends a species to the wrong folder, and the new line now states the wrong result as fact. A2-94-07 sits inside the 8 s bound, set after the mutation run.

Verified with my own live probes: A2-94-01, 02, 03, 04, 05, 06 (also by direct call), 07, 08, 09, the controls, privacy in the answers and the audit log. Read only: the four-line wording's source, the cancellation behaviour of `enforce_timeout`, and that the Plan ceiling drops no linked record (row counts matched in every pair I ran, but I did not construct a record at the ceiling).
