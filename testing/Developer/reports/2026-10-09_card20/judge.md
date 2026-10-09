# Card 20 judge report, 2026-10-09

Fresh-context judge of `fix/card20-isolate-year-place` at 01e9cb74 (card 20's 21a99f80 with develop 75be0bbb merged in). Findings are appended as they are established.

## Findings

### J-20-01: A place filter for Guinea, Netherlands or Serbia also counts isolates from Guinea-Bissau, Netherlands Antilles and Serbia and Montenegro
- Severity: major (a confident wrong filter; the places are rare in the file, which bounds the harm, not the defect)
- What: `_location_matches` in `tools/pathogen_detection.py` accepts any cell that starts with the place and whose next character is not a letter or digit. A hyphen or a space counts as a boundary, so a vocabulary name that is a prefix of another vocabulary name followed by `-` or ` ` matches both. `apply_filters` keeps "Guinea", "Netherlands" and "Serbia" (all in `GEO_LOC_COUNTRIES`), and the tool then counts the other country's isolates as matching.
- Reproduction: probe outside the checkout calling `_isolate_search_predicate(["blaKPC"], location=L, collection_year_min=None, collection_year_max=None)` on a row `{"AMR_genotypes": "blaKPC-2=COMPLETE", "geo_loc_name": G, "collection_date": "2021"}`:
  - L="Guinea", G="Guinea-Bissau: Bissau" gives True
  - L="Netherlands", G="Netherlands Antilles" gives True
  - L="Serbia", G="Serbia and Montenegro" gives True
  - controls: L="Niger", G="Nigeria" gives False; L="USA", G="USA: California" gives True
- Why it matters: the note says "collected in Guinea" while the count and the rows include isolates from a different country. The place cell (card 94) would show "Guinea-Bissau" on the row, so a careful reader can catch it, but the count beneath it is wrong with no sign. The real `geo_loc_name` separator after a country is a colon, so ending the match at `:` or end of cell (not at any non-alphanumeric character) would close it; that is the fixer's call.
- NOT FIXED

### J-20-02: Under a year filter, isolates with no readable collection date are dropped and the answer never says so
- Severity: major (the brief's own bar: "a missing date never matches a year filter, and the answer says so"; the first half holds, the second does not)
- What: the tool excludes a row whose `collection_date` is missing, a placeholder word, or any shape other than `YYYY`, `YYYY-MM`, `YYYY-MM-DD` (correct, never a false match). But nothing the person reads says those isolates were left out. `isolate_search.disclosure` names the filter ("collected in USA since 2020") and nothing else; `count_sentence` is unchanged; `_filters_applied_clause` speaks only on the tool's empty and timeout messages, which do not reach the answer's notes. `grep -n "not recorded\|without a date\|no collection date\|undated" core/isolate_search.py` finds nothing.
- Reproduction: offline, `parse_isolate_question("Which E. coli isolates carry blaKPC genes in the USA since 2020?")`, `apply_filters(..., year_min=2020, year_max=None, location="USA", ...)`, then `disclosure(...)` gives exactly "searching Escherichia coli isolates in Pathogen Detection for AMR genotypes starting blaKPC, collected in USA since 2020". The predicate, on rows dated "missing", "not collected", "", None, "2020-05-14T10:00:00Z", "2019/2020", "May-2020", "05/14/2020", "2020-5", returns False for min 2020, for max 2020 and for 2020 to 2020 alike.
- Why it matters: a researcher asking "since 2020" reads the count as every blaKPC isolate collected since 2020; isolates whose date the submitter never recorded, or wrote in another shape, are silently outside it, and the count reads as complete. One clause ("isolates with no collection date are not counted") would close it. A share of undated rows in the real file was not measured here.
- NOT FIXED

### J-20-03: The year check lets a one-year-off model reply through as a confident filter
- Severity: minor (unsure whether the slack is worth its cost; it is a stated design choice)
- What: `_year_is_anchored` accepts a bound within one of any four-digit number in the question, to keep exclusive bounds ("after 2020" as 2021). The same slack keeps a wrong reading: "collected in 2020" read as 2021 to 2021 is applied and labelled "collected in 2021".
- Reproduction: offline, question "Which E. coli isolates carry blaKPC genes collected in 2020?" with model values (2021, 2021, None) gives tool input `{'collection_year_min': 2021, 'collection_year_max': 2021}` and note "..., collected in 2021". With (2019, 2021) the same question gives "collected from 2019 to 2021".
- Why it matters: code is meant to keep only what the question supports. The note names the year actually used, so a careful reader can see it; a quick reader sees a filtered list and assumes it is 2020. Whether the live model ever does this was probed separately (see the isolate table below).
- NOT FIXED

### J-20-04: A number that is not a year anchors a year filter when the model takes it for one
- Severity: minor (depends on the model erring; the anchor check cannot catch it by design)
- What: any standalone four-digit number in 1900 to 2100 anchors a year, including one that counts something, and a gene name with a four-digit suffix.
- Reproduction: offline, "Which E. coli isolates carry blaKPC genes from 2000 hospitals in Brazil?" with model (2000, 2000, "Brazil") gives tool input `{'location': 'Brazil', 'collection_year_min': 2000, 'collection_year_max': 2000}`, note "collected in Brazil in 2000". "Which E. coli isolates carry blaKPC-2020 genes?" with model (2020, 2020) gives "collected in 2020" (the `(?<!\d)` lookbehind treats the hyphen as a boundary).
- Why it matters: TASK 6 tells the model a counting number is not a year, so this is defence in depth only; the note does name the year. Live behaviour on a counting number is in the isolate table below.
- NOT FIXED

### J-20-05: Under a filter, the count sentence still reads as every isolate with these genes
- Severity: unsure (the build left `count_sentence` unchanged on the diagnosis's advice; filed so the owner sees the reading)
- What: with a filter applied, the first note under the answer is "Pathogen Detection lists 580 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown." The filter is named only in the next note ("Searching ... collected in USA since 2020."). The count sentence alone states a total that is not the organism's total for these genes.
- Reproduction: read, not run live: `_isolate_count_note` calls `count_sentence(label, shown, total, complete)` with no filter argument (graph.py, `_isolate_count_note`); the two notes are assembled adjacently in that order (graph.py, the `notes = [...]` list in Write). The 580 figure is the build's own measured live count.
- Why it matters: a quote of the count sentence alone, or a reader who stops at it, carries a wrong total. Adjacent placement makes this mild.
- NOT FIXED

### J-20-06: The year parser's comment says the pattern is never end-anchored, and it is
- Severity: minor
- What: `_COLLECTION_DATE_YEAR_PATTERN` is `^(\d{4})(?:-\d{2}(?:-\d{2})?)?$`; the comment above it says "Anchored at the START only, never `$`: a malformed suffix after a genuine leading year ... still yields a real year". The code does the stricter thing, so a timestamped date such as "2020-05-14T10:00:00Z", a range "2019/2020", or "2020-5" yields no year and the row is excluded under any year filter.
- Reproduction: `_parse_collection_year("2020-05-14T10:00:00Z")` returns None; `_parse_collection_year("2019/2020")` returns None; `_parse_collection_year("2020 ")` returns 2020.
- Why it matters: the exclusion is the safe direction, but the next person reading the comment will believe the opposite of what runs, and these rows join J-20-02's silent exclusion.
- NOT FIXED

### J-20-07: A malformed year or place in Think's reply now fails the whole classification, on any question
- Severity: minor (no live occurrence in 80 non-isolate calls; the one retry with the schema error is the backstop; filed because TASK 6 adds this failure surface to every question)
- What: `_ThinkClassification.collection_year_min` and `collection_year_max` are `int | None`, and `location` is `str | None` with `max_length=100`. A reply carrying "2020s", "since 2020", "", 2020.5, a list, or a place over 100 characters fails validation of the whole reply. The code comment says "an odd year is dropped by the verifier and disclosed, never a reason to refuse the whole reply"; that holds for an integer only.
- Reproduction: offline, `_parse_think_classification` on a valid reply plus each extra field: `{"collection_year_min": "2020s"}`, `"since 2020"`, `""`, `2020.5`, `{"location": ["USA"]}`, `{"location": "x"*101}` each raise `ThinkClassificationUnavailableError` ("did not match the think classification schema (collection_year_min: Input should be a ..."). `"2020"` and `2020.0` coerce to 2020; `True` coerces to 1 (then dropped and disclosed by `apply_filters`).
- Why it matters: a second bad reply ends the search with "A step in this query hit a temporary error" for a question about BRCA1 that never needed a year. Reading these three fields leniently (anything not an integer, or a string over the bound, as null plus a "could not be applied" note) would keep a filter slip from costing the whole answer.
- NOT FIXED

### J-20-08: "Georgia" is applied as the country with no word that it could be the US state
- Severity: unsure (the question is genuinely ambiguous; filed because the result is a confident filter either way)
- What: for a question naming Georgia, the model returns "Georgia", which is in the INSDC vocabulary as the country, so code keeps it and the note says "collected in Georgia". US-state isolates are written "USA: Georgia" and never match.
- Reproduction: live, branch, develop's plan model: "Which Klebsiella isolates with carbapenemase genes were collected in Georgia before 2019?" gave model values (None, 2018, "Georgia"), tool input `{'collection_year_max': 2018, 'location': 'Georgia'}`, note "..., collected in Georgia in or before 2018; ...". Offline, `_isolate_search_predicate(..., location="Georgia")` matches "Georgia: Tbilisi" and not "USA: Georgia".
- Why it matters: a US researcher asking about Georgia gets the country's isolates (likely a near-zero count) under a note that reads as their answer. The place cell on each row would say "Georgia" rather than "USA: Georgia", which is the only clue.
- NOT FIXED

### J-20-09: When the model does not name a place it cannot spell, the place is dropped in silence, as before the card
- Severity: major (query 110's third expectation, the Atlantis note, fails on live runs; the person sees every isolate with no word that their place was ignored)
- What: the "could not be applied" note fires only when the model returns a place that code then rejects. When the model returns null for a place the question did name (it did so for "Atlantis" and "California" on the second live pass), code has nothing to verify and the disclosure is the unfiltered one. TASK 6 tells the model to return the place "exactly as the query wrote it when you do not know that spelling", but the model does not do so reliably.
- Reproduction: live, branch, develop's plan model, Think's classification call as `_think` makes it (no exact matches, no memory):
  - "E. coli isolates with blaKPC from Atlantis": pass 0 model (None, None, "Atlantis"), note ends "a place was asked for (Atlantis), but it is not a country name Pathogen Detection uses, ..."; pass 1 model (None, None, None), tool input `{}`, note "searching Escherichia coli isolates in Pathogen Detection for AMR genotypes starting blaKPC" with nothing about the place.
  - "Which E. coli isolates from California carry colistin resistance genes?": pass 0 model (None, None, "California"), disclosed; pass 1 model (None, None, None), silent.
  Further passes are in the table at the end of this report.
- Why it matters: this is the exact failure the card was opened for ("place dropped in silence"), now intermittent instead of constant. A person asking for isolates from a named place sees a list and a count that read as their place. The owner's decision has code only verify; it does not cover the case where the model omits, so this needs either a stronger instruction, a second look when the question has a place-shaped phrase the model left empty, or the owner's acceptance of the miss rate.
- NOT FIXED

### J-20-10: Measured share behind J-20-02: about 39 percent of Klebsiella isolates carry no readable collection year
- Severity: major (raises J-20-02: the silent exclusion is not an edge case)
- What: on the real file, a large share of rows have an empty `collection_date`, and a further share use a date range ("2010/2012", "2014-11/2016-01", "2011-09-01/2012-06-10"), which `_parse_collection_year` reads as no year. Under any year filter all of them are excluded without a word (J-20-02). A range lying wholly inside the asked years (for example "2018/2019" under "since 2015") is excluded too.
- Reproduction: the first 40,000,000 bytes of `https://ftp.ncbi.nlm.nih.gov/pathogen/Results/Klebsiella/PDG000000012.836/Metadata/PDG000000012.836.metadata.tsv` (public, fetched with a byte range), 36,448 complete rows, each `collection_date` run through the branch's `_parse_collection_year`: 14,193 rows (38.9 percent) give None. Of those, 13,074 are empty, 543 "missing", and the rest are ranges (top: "2010/2012" 178, "2014-11/2016-01" 132, "2011-09-01/2012-06-10" 83, "2018/2019" 56). Date shapes: `YYYY` 11,577, `YYYY-MM-DD` 9,703, `YYYY-MM` 975, `YYYY/YYYY` 305, `YYYY-MM/YYYY-MM` 152, `YYYY-MM-DD/YYYY-MM-DD` 119.
- Why it matters: "Klebsiella isolates with carbapenemase genes since 2018" counts only isolates whose submitter wrote a single dated year; roughly two in five isolates in this slice could never be counted under a year filter, and the answer reads as complete. The same slice holds "Viet Nam" 439 times and no "Vietnam" (relevant to J-20-11), and no Guinea-Bissau, Netherlands Antilles or Serbia and Montenegro rows, so J-20-01 is a defect with little weight in Klebsiella today.
- NOT FIXED

### J-20-11: A common spelling the model does not convert is dropped with a note that misstates the file
- Severity: minor (honest that no place filter ran, but the stated reason is false to the reader)
- What: when the model returns the person's spelling rather than the vocabulary's ("Vietnam", "UK"), code drops it and the note says the place "is not a country name Pathogen Detection uses". The file does hold that country, under "Viet Nam" and "United Kingdom". A reader takes the sentence to mean Pathogen Detection has no isolates from Vietnam.
- Reproduction: live, branch: "Which Klebsiella isolates from Vietnam carry blaNDM genes since 2018?" gave "Vietnam" on 2 of 3 passes, tool input `{'collection_year_min': 2018}`, note "...; a place was asked for (Vietnam), but it is not a country name Pathogen Detection uses, so isolates from every place are counted"; the third pass gave "Viet Nam" and was applied. "Which Salmonella isolates from the UK collected in the last 5 years carry ESBL genes?" gave "UK" on 1 of 3. The real Klebsiella slice (J-20-10) holds "Viet Nam" 439 times.
- Why it matters: the same question applies the filter one time in three and, the other two times, tells the person something untrue about the database. Wording such as "could not be matched to a country name as Pathogen Detection spells it" would be accurate; whether to ask the model again is the fixer's call.
- NOT FIXED

### J-20-12: A state or city the model widens to its country is applied as the country, with no note that the narrower place was not
- Severity: minor
- What: when the model maps "California" to "USA", code keeps "USA" and the note says "collected in USA". Nothing says California itself could not be applied.
- Reproduction: live, branch: "Which E. coli isolates from California carry colistin resistance genes?" three passes gave "California" (dropped and disclosed), None (silent, J-20-09), and "USA" (tool input `{'location': 'USA'}`, note "..., collected in USA"). Three passes, three different outcomes.
- Why it matters: the person asked for California and reads a USA-wide list under a note naming USA; most would notice, some would not. Combined with J-20-09 the same question gives three different answers.
- NOT FIXED

### J-20-13: J-20-03 seen live: "after 2021" read as 2021 and applied
- Severity: minor (adds live evidence to J-20-03)
- What: the model sometimes reads an exclusive bound as inclusive; the one-year slack keeps it.
- Reproduction: live, branch: "Which Klebsiella isolates collected after 2021 in South Korea carry blaKPC?" gave collection_year_min 2022 on 2 passes and 2021 on 1; the 2021 pass planned `{'collection_year_min': 2021, 'location': 'South Korea'}`, note "collected in South Korea since 2021", so 2021 isolates were counted though the question excluded them.
- Why it matters: the note names 2021, so it is visible, but the same question returns two different counts across runs.
- NOT FIXED

### J-20-14: TASK 6 shifts Think's query class on some non-isolate questions beyond develop's own run-to-run spread
- Severity: minor (unsure: six runs a tree is a small sample; record_type and the new fields never moved)
- What: with the same model and messages, three questions whose query class develop gives consistently came back differently on the branch. `query_class` sets step budgets and the call budget (graph.py, `call_budget.set_query_class`, `_step_deadline`).
- Reproduction: live, Think's classification call as `_think` makes it (`_build_think_messages(text, [], "")`, `_run_think_classification`), PLAN_MODEL deepseek/deepseek-v4-flash (develop's, per `docs/architecture/Model_architecture.md`), six runs a tree, develop 75be0bbb exported outside the checkout:
  - "What phenotypic features are associated with Marfan syndrome?": develop single_hop 6 of 6; branch single_hop 3, lookup 2, aggregate 1.
  - "What is known about Salmonella isolate SAMN02147118 in Pathogen Detection?": develop exploratory 6 of 6; branch single_hop 4, exploratory 1, lookup 1.
  - "Find GEO expression datasets studying TP53 in human tumour samples.": develop named "human" as an organism 6 of 6; branch 4 of 6.
  Every other field change sits inside develop's own spread (table below). record_type matched on all 20 questions. The three new fields were null on all 120 branch runs, including "papers on statins since 2022" and the Mediterranean question.
- Why it matters: a lookup budget on a features question can cut its Act or Write time; the effect on answers was not measured here. Five or more full live runs of the Marfan question (query 66) would settle it.
- NOT FIXED

### J-20-15: Think is slightly slower on the branch
- Severity: minor
- What: the longer instruction costs a little time per classification call.
- Reproduction: same 240 calls as J-20-14, both trees run at the same time in parallel processes: develop median 1.75 s, mean 2.56 s, p90 4.20 s; branch median 1.94 s, mean 2.76 s, p90 5.43 s. Zero parse retries on the branch, one on develop; zero failures on either. "What is rs334 and what condition is it associated with?" was slower on the branch on 5 of 6 runs (branch 1.6 to 9.2 s, develop 1.4 to 3.2 s), cause not found.
- Why it matters: about 0.2 s at the median on every question, inside the 20 s rule, but every question pays it, including those that never ask for a year or place.
- NOT FIXED

## Think comparison table, non-isolate questions

Six runs a tree (two passes, then four more after a network drop voided the first attempt). Entity letters: g gene, d disease, o organism.

| # | Question | query_class, develop | query_class, branch | record_type dev / branch | entities, develop | entities, branch | new fields, branch | median s dev / branch |
|---|---|---|---|---|---|---|---|---|
| 1 | `Which diseases are associated with BRCA1?` | single_hop 5, multi_hop 1 | single_hop 6 | none 6 / none 6 | brca1:g 4, brca1:g+diseases:d 2 | brca1:g 5, brca1:g+diseases:d 1 | all null | 1.93 / 2.04 |
| 2 | `What is known about EGFR mutations in non-small cell lung ` | exploratory 6 | exploratory 6 | none 6 / none 6 | egfr:g+non-small cell lung cancer:d 6 | egfr:g+non-small cell lung cancer:d 6 | all null | 1.93 / 1.88 |
| 3 | `Variants in GCK causing MODY` | single_hop 4, multi_hop 1, exploratory 1 | multi_hop 3, single_hop 3 | none 6 / none 6 | gck:g+mody:d 6 | gck:g+mody:d 6 | all null | 1.76 / 1.81 |
| 4 | `What MeSH terms are assigned to PMID 11237011?` | single_hop 4, lookup 2 | lookup 5, single_hop 1 | none 6 / none 6 | none 6 | none 6 | all null | 1.35 / 1.51 |
| 5 | `What are the typical symptoms and risk factors of GERD?` | single_hop 3, exploratory 2, lookup 1 | exploratory 4, lookup 2 | none 6 / none 6 | gerd:d 6 | gerd:d 5, none 1 | all null | 2.09 / 1.80 |
| 6 | `What is rs334 and what condition is it associated with?` | single_hop 6 | single_hop 6 | none 6 / none 6 | none 4, rs334:g 1, rs334:d+rs334:g 1 | none 4, rs334:g 1, condition:d+rs334:g 1 | all null | 1.66 / 5.05 |
| 7 | `Compare what is known about MLH1 and MSH2 in colorectal ca` | exploratory 5, aggregate 1 | exploratory 6 | none 6 / none 6 | colorectal cancer:d+mlh1:g+msh2:g 6 | colorectal cancer:d+mlh1:g+msh2:g 6 | all null | 1.87 / 2.12 |
| 8 | `Find GEO expression datasets studying TP53 in human tumour` | single_hop 5, exploratory 1 | single_hop 3, exploratory 1, multi_hop 1, lookup 1 | none 6 / none 6 | human:o+tp53:g 6 | human:o+tp53:g 3, tp53:g 2, human:o+tp53:g+tumour:d 1 | all null | 1.71 / 2.01 |
| 9 | `What phenotypic features are associated with Marfan syndro` | single_hop 6 | single_hop 3, lookup 2, aggregate 1 | none 6 / none 6 | marfan syndrome:d 6 | marfan syndrome:d 6 | all null | 1.79 / 1.96 |
| 10 | `How many genes are associated with breast cancer?` | aggregate 6 | aggregate 6 | none 6 / none 6 | breast cancer:d 6 | breast cancer:d 6 | all null | 2.74 / 1.77 |
| 11 | `What ACMG-relevant evidence is available for a copy number` | aggregate 3, single_hop 1, multi_hop 1, exploratory 1 | multi_hop 3, exploratory 2, aggregate 1 | none 6 / none 6 | none 6 | none 6 | all null | 1.69 / 1.75 |
| 12 | `For BioProject PRJNA31257, list the BioSamples, the SRA ru` | multi_hop 3, aggregate 2, exploratory 1 | multi_hop 3, single_hop 2, exploratory 1 | none 5, sra 1 / none 6 | none 6 | none 6 | all null | 1.67 / 2.25 |
| 13 | `Find SRA runs of SARS-CoV-2 sequenced on Illumina from cli` | aggregate 3, single_hop 2, exploratory 1 | exploratory 2, lookup 2, single_hop 1, aggregate 1 | sra 6 / sra 6 | sars-cov-2:o 2, none 2, illumina:g+sars-cov-2:o 1, clinical respiratory samples:d+illumina:d+sars-cov-2:o 1 | none 4, sars-cov-2:o 1, illumina:g+sars-cov-2:o 1 | all null | 2.69 / 2.17 |
| 14 | `Which genome assemblies are available for Mycobacterium tu` | single_hop 4, lookup 2 | single_hop 5, lookup 1 | assembly 6 / assembly 6 | mycobacterium tuberculosis:o 6 | mycobacterium tuberculosis:o 6 | all null | 1.61 / 1.83 |
| 15 | `What is known about Salmonella isolate SAMN02147118 in Pat` | exploratory 6 | single_hop 4, exploratory 1, lookup 1 | none 6 / none 6 | salmonella:o 2, none 2, salmonella:o+samn02147118:d 1, salmonella:o+samn02147118:o 1 | none 5, salmonella:o 1 | all null | 3.34 / 1.73 |
| 16 | `Are there any beneficial variants typically found in peopl` | exploratory 6 | exploratory 6 | none 6 / none 6 | none 5, mediterranean:o 1 | none 5, mediterranean:o 1 | all null | 2.83 / 3.25 |
| 17 | `papers on statins since 2022` | exploratory 4, lookup 1, single_hop 1 | exploratory 5, lookup 1 | none 6 / none 6 | none 6 | none 6 | all null | 1.59 / 1.92 |
| 18 | `is there a trial recruiting for melanoma` | lookup 3, single_hop 2, exploratory 1 | single_hop 3, exploratory 2, lookup 1 | none 6 / none 6 | melanoma:d 6 | melanoma:d 6 | all null | 2.08 / 3.07 |
| 19 | `What does the literature say about MTHFR C677T?` | exploratory 6 | exploratory 6 | none 6 / none 6 | mthfr:g 5, c677t:d+mthfr:g 1 | mthfr:g 4, c677t:d+mthfr:g 2 | all null | 1.66 / 2.38 |
| 20 | `Does coffee help make exercise more effective?` | exploratory 6 | exploratory 6 | none 6 / none 6 | none 5, coffee:d+exercise:d 1 | none 6 | all null | 1.45 / 1.87 |

## Isolate questions, live on the branch

Three passes each. Model values are (collection_year_min, collection_year_max, location); "kept" is what `apply_filters` passed to the tool.

| Question | Model values, three passes | Kept, three passes | Verdict |
|---|---|---|---|
| `Which E. coli isolates carry blaKPC genes in the USA since 2020?` | (2020, None, USA) x3 | min 2020, USA x3 | right, note "collected in USA since 2020" |
| `Which E. coli isolates in Pathogen Detection carry ESBL genes collected in 2023?` | (2023, 2023, None) x3 | 2023 to 2023 x3 | right |
| `E. coli isolates with blaKPC from Atlantis` | Atlantis, None, Atlantis | nothing x3 | 2 of 3 disclosed; 1 silent (J-20-09) |
| `What Escherichia coli isolates in Pathogen Detection carry extended-spectrum beta-lactamase genes?` (33) | all null x3 | nothing x3 | right, note unchanged |
| `Show me the ones from 2023` (41) | all null x3 | not an isolate search | unchanged from develop, outside the card |
| `Which Salmonella isolates from the United States collected between 2015 and 2018 carry blaCTX-M-15?` | (2015, 2018, USA) x3 | all kept x3 | right |
| `Which Klebsiella isolates with carbapenemase genes were collected in Georgia before 2019?` | (None, 2018, Georgia) x3 | all kept x3 | ambiguous place applied as the country (J-20-08) |
| `Which E. coli isolates from California carry colistin resistance genes?` | California, None, USA | nothing, nothing, USA | disclosed, silent, widened (J-20-09, J-20-12) |
| `Which Salmonella isolates from the UK collected in the last 5 years carry ESBL genes?` | (2019, 2024, United Kingdom), (2018, 2023, UK), (2019, 2024, United Kingdom) | UK kept 2 of 3; years dropped x3 and disclosed | the years were wrong (today is 2026) and correctly refused; "UK" dropped once (J-20-11) |
| `Which Klebsiella isolates from Vietnam carry blaNDM genes since 2018?` | Vietnam, Vietnam, Viet Nam | min 2018 x3; place 1 of 3 | J-20-11 |
| `Which E. coli isolates carry blaKPC genes in the 2000 samples from Brazil?` | (None, None, Brazil) x2, all null x1 | Brazil 2 of 3 | the counting number was never taken as a year; place silent once (J-20-09) |
| `Which Klebsiella isolates collected after 2021 in South Korea carry blaKPC?` | min 2022, 2021, 2022 | as named | 2021 is one year off and kept (J-20-13) |

No isolate run returned isolates from a wrong place or year under a matching label except through J-20-08 (Georgia, ambiguous) and J-20-13 (one year off, named in the note). The confident-wrong cases code can catch it does catch: the wrong "last 5 years" bounds were refused every time.

## What was verified, and how

| Claim | How | Result |
|---|---|---|
| Think's other outputs unchanged for non-isolate questions | Own probe, live, 20 questions from the test queries document, six runs a tree, both trees in parallel | Mostly; J-20-14, J-20-15 |
| New fields stay null off the isolate path | Same probe | Null on all 120 branch runs |
| Think extracts year and place on isolate questions | Own probe, live, 12 isolate questions including 33, 41 and 110's three, three passes | Right on the plain cases; J-20-08, J-20-09, J-20-11, J-20-12, J-20-13 |
| Code keeps only what the question supports | Own offline probe of `apply_filters` with 31 model replies, plus the live runs | Holds for unwritten years, out-of-vocabulary and unsafe places; J-20-03, J-20-04 for the slack |
| Note says when a filter could not be applied | Offline and live | Yes when the model names the filter; no when it omits it (J-20-09); misleading reason (J-20-11) |
| Tool filters `geo_loc_name` and `collection_date` correctly, missing date never matches | Own offline probe of `_isolate_search_predicate` on 31 place pairs and 26 date shapes, and the real Klebsiella file's first 36,448 rows | Missing and placeholder dates never match; J-20-01 boundary; J-20-06 comment |
| The answer says a missing date was not counted | Read of `disclosure`, `count_sentence`, Write's note list; offline disclosure output | Not said (J-20-02, J-20-10) |
| Card 94's place cell values | Read only: `isolate_place` and `PLACE_PLACEHOLDERS` in `synthesis/answer_layout.py` show the cell verbatim; the tool's place filter ignores placeholder words because none is in the vocabulary | No conflict found |
| Named tests | Run: the five files (the cache prefix test lives under `tests/system_03_search_agent/synthesis/`) | 172 passed |
| Tests catch the new behaviour | Own mutations, each restored with `git checkout`: a missing date matching, any place kept, no year anchor, the not-applied note dropped, the place boundary removed | Each turned 1 to 8 tests red |
| ruff check (no path) | Run | All checks passed |
| isort `--check-only --diff src tests services tracker alembic .claude .github` | Run | Clean (2 files skipped by config) |
| Prompt cache prefix unchanged | Read only, plus the named test passing | Not probed beyond the test |

Read only, not run: the count sentence's placement (J-20-05), the full answer as a person sees it (no end-to-end live search was run), and the `query_class` effect on budgets (J-20-14). The live Think probe passed no exact-match list and no memory suffix, the same on both trees.

OpenRouter credits: 31.5150 left before, 31.4232 after, about 0.09 spent (a network drop voided the first 80 calls, which cost about 0.015).

## Verdict

FIX FIRST.

The plain cases work: "USA since 2020", "in 2023", "between 2015 and 2018" are extracted, verified and named, the wrong "last 5 years" bounds are refused every time, and no non-isolate question gained a filter. Three things should be fixed before merge, all in this card's own code, none inside an earlier fix round:

- J-20-02 with J-20-10: under a year filter about two in five isolates are left out with no word, against the brief's own "and the answer says so".
- J-20-09: the place is still dropped in silence when the model returns null, so query 110's Atlantis expectation fails on some runs.
- J-20-01: Guinea, Netherlands and Serbia match a different country's cells.

J-20-11's note wording is a one-line fix worth taking at the same time. J-20-03, J-20-08, J-20-12, J-20-13 and J-20-14 are owner calls on how much model slack to accept.
