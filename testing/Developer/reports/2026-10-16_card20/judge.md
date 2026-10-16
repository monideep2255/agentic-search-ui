# Card 20, second build: judge report (dial position 2)

Judge for pull request #247, `git diff bce08af9...2bd5125e`. One round. Findings are appended as they are established; the verdict is at the end.

## Findings

### J2-20-01: A place of any shape that stands in the question is quoted back under the answer when the model also gives a valid place_alt
- Severity: minor (the quoted text is always the person's own words, so this is not the A-20-01 model-invented sentence; the build report's claim is broader than the code)
- What: `verify` sets `place_as_written` to the model's `place` whenever EITHER `place` or `place_alt` passes `PATHOGEN_LOCATION_PATTERN`. With `place_alt="Italy"`, a `place` holding markdown or HTML that stands in the question is kept and printed by `applied_phrase` and `filter_notes`. The build report says "A place with an unsafe shape is never used or quoted"; its test `test_a_place_with_an_unsafe_shape_is_not_used_and_is_not_quoted_back` only covers `place_alt=None`.
- Reproduction: probe on the branch tree, question `Which Klebsiella isolates carry blaKPC from [Italy](https://evil.example/x) <img src=x onerror=alert(1)> since 2020?`, reply `{"year_relation":"since","year_a":2020,"place":"[Italy](https://evil.example/x)","place_alt":"Italy","place_role":"collected"}` gives `places=('Italy',), place_as_written='[Italy](https://evil.example/x)'` and the note `Filters applied: isolates collected in Italy (you wrote: [Italy](https://evil.example/x)), in 2020 or later.` The same with `place="<img src=x onerror=alert(1)>"` prints `(you wrote: <img src=x onerror=alert(1)>)`. With `place_applied=False` it prints `The place '[Italy](https://evil.example/x)' could not be applied ...`.
- Why it matters: only the person's own text can appear, so the harm is limited to a pasted question or a shared answer page; whether the UI renders notes as markdown decides whether the link is live. Not worse than develop for a plain question.
- NOT FIXED

### J2-20-02: The "place stands in the question" check is a substring test, so a model reply of Niger for Nigeria or India for Indiana passes as the person's own words
- Severity: minor (needs a model mistake; the applied place is shown, but without the "(you wrote: ...)" marker because `place_as_written` is the model's text, not the person's)
- What: `verify` accepts `place` when `place.casefold() in question.casefold()`. That is a substring test, not a whole-word test.
- Reproduction: branch tree probe. `Klebsiella isolates from Nigeria` with `place="Niger"` gives `places=('Niger',), place_as_written='Niger'`. `Klebsiella isolates from Indiana` with `place="India"` gives `places=('India',)`. `Klebsiella isolates from Guinea-Bissau` with `place="Guinea"` gives `places=('Guinea',)`. `E. coli isolates from Italy` with `place="it"` gives `places=('it',)`.
- Why it matters: the tool's whole-name match (which closes J-20-01) then filters to the wrong country with a note "Filters applied: isolates collected in Niger" and no hint the person wrote Nigeria. A confident wrong record. Depends on the model erring, which the build report's own 12-call probe suggests is rare.
- NOT FIXED

### J2-20-03: place_alt is not checked by code at all, so a model reply can add any second country, including the Guinea-Bissau case J-20-01 closed
- Severity: minor (disclosed: the note shows the matched spelling beside "you wrote")
- What: `place_alt` is only checked for shape. It need not stand in the question, need not be in `GEO_LOC_COUNTRIES` and need not be the same place.
- Reproduction: branch tree probe. `Klebsiella isolates from Atlantis` with `place="Atlantis", place_alt="Italy"` gives `places=('Atlantis', 'Italy')`. `Klebsiella isolates from Guinea` with `place_alt="Guinea-Bissau"` gives `places=('Guinea', 'Guinea-Bissau')`.
- Why it matters: the count then includes a different country. The answer reads "collected in Italy (you wrote: Atlantis)" so a careful reader sees it. Checking that `place_alt` is a member of the reference list would be code verifying a model claim against a closed set (allowed by the no-hardcoded-decisions rule), but the builder chose not to; owner's call.
- NOT FIXED

### J2-20-04: Every isolate search now waits about 1.3 to 1.6 s longer before the search starts, query 33 and 35 included, where develop adds nothing
- Severity: minor (measured, inside the run-to-run spread of a 23 to 55 s answer; the owner chose the design knowing the cost)
- What: the extraction call runs before the isolate search on every isolate plan, filtered or not. The time to the plan event is the clean measure, since the tool and the writer vary by seconds between runs.
- Reproduction: judge's own script, sequential, develop's settings (CLASSIFIER_PROVIDER=jev, guard and plan deepseek/deepseek-v4-flash, synth z-ai/glm-5.2, cap $0.25), order alternated per round, spend $0.081 for 12 runs.

| Tree, query | Total s (3 runs) | Median | Plan event at, s | Median | Extraction s |
|---|---|---|---|---|---|
| develop, 33 | 32.47, 22.69, 23.78 | 23.78 | 7.05, 3.91, 4.33 | 4.33 | none |
| branch, 33 | 30.11, 26.59, 27.80 | 27.80 | 6.16, 5.89, 5.05 | 5.89 | 1.70, 1.62, 1.64 |
| develop, 35 | 55.60, 27.20, 27.84 | 27.84 | 7.80, 3.36, 3.82 | 3.82 | none |
| branch, 35 | 32.44, 28.33, 28.97 | 28.97 | 5.54, 4.89, 5.11 | 5.11 | 2.47, 1.59, 1.48 |

- Same answer on both trees: tool input carried no filter key on all 6 branch runs, `filter_report` None, count sentence identical ("Pathogen Detection lists 141,578 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown.", and 2,716 for query 35), no filter note. Trust outcome varied ask/answer on both trees.
- Why it matters, said plainly: a person asking query 33 waits about a second and a half longer for the same answer, on a wait of 23 to 55 s. Nobody would notice it against the spread, but it is strictly worse than develop on the flagship question and it pushes every isolate answer further past the 20 s target in the no-degradation rule. A cheaper shape (skip the call when the question holds no four-digit number and no capitalised word beyond the organism and gene) would be a word-list decision, so the cost may be the price of the owner's design. Owner's call, not a blocker in my judgement.
- Side fact, not this card: query 35's count is now 2,716 on develop too; the test queries document says 2,678.
- NOT FIXED

### J2-20-05: Verified, no defect: Think and non-isolate Plan are byte-identical to develop on 19 of 19 judge-chosen questions
- Severity: none (evidence for checklist item 2)
- What: the judge's own harness (not the builder's): network blocked at `httpx.AsyncClient.send`, a model stub that returns entities from capitalised words and a class from a hash, a symbol resolver that returns hashed NCBIGene CURIEs (so graph templates are selected, which the builder's stub never did), the decision seam stubbed. 20 questions, chosen to tempt the change: non-isolate questions with years and places ("Papers on BRCA1 in breast cancer from Italy since 2020", "Measles cases in Guinea since 2020", "Salmonella genome assemblies from Guinea since 2020", "SRA runs for Escherichia coli from Italy collected in 2021", "Clinical trials for cystic fibrosis in the USA after 2021", "What diseases is CFTR linked to, in the 2010s?"), an isolate question with no organism that clarifies ("Which isolates carry ESBL genes from Italy since 2020?"), a window, an rsID, a recent-papers question, and one real isolate question as the positive control.
- Reproduction: each tree run twice: develop md5 638ee8cc896fac6f607c5a22d4fbcb10 both runs, branch fef7cc6dfd368992c51e1f73a120bba7 both runs (repeatable). Per question: 19 of 19 non-isolate questions have identical Think output, identical Plan output (tool calls up to 13 per plan) and identical model calls (system prompt hash and user text). The clarifying isolate question makes 1 model call on both trees. The control ("Which Klebsiella pneumoniae isolates carry blaKPC genes from Italy since 2020?") differs as it should: 1 call on develop, 2 on the branch. So the files differ only on the isolate question, and the check is not vacuous.
- NOT FIXED (nothing to fix)

### J2-20-06: No test pins the count when a place is not applied; removing the fallback count leaves every test green
- Severity: minor (the code is right today, verified live; the guard on it is vacuous)
- What: when the file holds no isolate for the place, `_isolate_search` must swap `match_count` to `tally.fallback_count`. Without the swap the total is `max(0, len(isolates))`, so the answer would say "lists 20 ... all shown" for a set of thousands. The builder's test `test_a_place_the_file_does_not_hold_is_not_applied_and_the_list_is_the_unfiltered_one` uses a 4-row table with 2 matches, below the 20-row cap, so `max(0, 2) == 2` passes either way.
- Reproduction: in a copy of the branch, deleted the line `            match_count = tally.fallback_count` in `tools/pathogen_detection.py`. `pytest core/test_isolate_filters.py tools/test_pathogen_detection.py core/test_think_organisms.py core/test_graph.py -m "not integration"`: 353 passed, 0 failed. Restored, `cmp` identical. Live on the branch the swap does work: the Guinea question below returned total 11,059 with place_applied False.
- Why it matters: a later edit can break the not-applied count and no gate notices; the person would read a count of 20 as the whole set. A fixture with more matches than `max_isolates` closes it.
- NOT FIXED

### J2-20-07: The Plan step's narrative says "collected in Guinea" before the tool finds the place is not in the file, and nothing corrects it in that step
- Severity: minor (the notes under the answer are honest; this is the plan line a person sees while waiting)
- What: `_isolate_filter_narrative` writes the requested filters into the plan event's narrative ("searching ... collected in Guinea, in 2020 or later"). When the tool then reports the place not applied, the plan line stays as written. The card's own words are "never shows a filter as applied when it was not".
- Reproduction: live, branch, `Salmonella isolates from Guinea since 2020 carrying blaCTX-M genes`: plan narrative `searching Pathogen Detection Salmonella isolates for AMR genotypes starting blaCTX-M, collected in Guinea, in 2020 or later, and the organism's NCBI Taxonomy record`; tool report `place_applied: False`, 11,059 total; rows from USA and United Kingdom only. Answer notes: "Pathogen Detection lists 11,059 Salmonella isolates with these genes collected in 2020 or later ...", "Filters applied: isolates collected in 2020 or later.", "The place 'Guinea' could not be applied: no isolate with these genes lists it in Pathogen Detection, so isolates from every place are counted. Places that do appear include USA, China, United Kingdom, South Korea, Chile.", "1,232 isolates have no collection date ...". The synthesised prose made no Guinea claim (the writer fell back to a listing). 71.9 s total, tool 60.4 s, extraction 1.51 s, trust "ask".
- Why it matters: the plan line reads as a description of what is being searched, which is true at that moment, so a person is unlikely to be misled once the notes appear. Unsure whether the UI keeps the plan line visible beside the answer; if it does, it contradicts the note on the same screen. Wording such as "asked for: Guinea" would remove the doubt.
- NOT FIXED

### J2-20-08: Three 2026-10-09 findings are not avoided by construction; they rest on the model reading the question right
- Severity: minor (each is no worse than develop, which applies no filter at all; the build report names two of them under "Left for review")
- What and reproduction, per finding, from the branch tree probes of `isolate_filters.verify`:
  - J-20-04 (a number that is not a year): `the 2000 samples from Brazil carrying blaKPC` with a model reply `in 2000` verifies to `year_min=2000, year_max=2000`. Code accepts any four-digit number written in the question; only the model separates a count from a year. Shown to the person as "collected ... in 2000", so it is visible.
  - J-20-09 (a filter the model does not report is dropped in silence): a reply of `{"year_relation":"none","place_role":"none"}` produces no filter and no note, whatever the question says. Builder states it openly; closing it needs code to read the question, which the no-hardcoded-decisions rule forbids.
  - A-20-12 (Congo): the tool matches whole names, so "Congo" never matches "Democratic Republic of the Congo" or "Republic of the Congo". The not-applied note offers the top five countries among all gene-carrying isolates (live Guinea run: USA, China, United Kingdom, South Korea, Chile), not the near spellings, so the person is not told what to type for Congo unless the model supplies a `place_alt`.
- Avoided by construction, re-derived by probe: J-20-01 and A-20-02 (Guinea against Guinea-Bissau, Equatorial Guinea, Papua New Guinea; Netherlands against Netherlands Antilles; Serbia against Serbia and Montenegro; Niger against Nigeria; all False), J-20-02, J-20-10 and A-20-04 (every unreadable date is counted as left out, 21 date shapes tried), J-20-03 and J-20-13 ("after 2021" with relation after gives 2022 onward; a model year 2022 not written in the question is refused), J-20-07, J-20-14, J-20-15, A-20-13 and A-20-15 (Think untouched, J2-20-05), A-20-05 (count sentence names the year live), A-20-07 (decade 2010s gives 2010 to 2019), A-20-08 (travel role "other" applies nothing).
- NOT FIXED

### J2-20-09: "from Italy or Spain" becomes one place called "Italy or Spain", which matches nothing, and the note then lists Italy among the places that do appear
- Severity: major for the person asking (a common question shape gets China and USA rows and a note that contradicts itself); not worse than develop, which drops the place silently, and no filter is shown as applied. A-20-14 (two countries) is not avoided
- What: the prompt asks for one place "copied exactly as the question wrote it". The model copied "Italy or Spain"; it stands in the question and fits `PATHOGEN_LOCATION_PATTERN`, so `verify` passes it, and the tool's whole-name match finds no such country.
- Reproduction: live, branch src, develop's settings, `Which Klebsiella pneumoniae isolates carry blaKPC genes from Italy or Spain submitted since 2021?`. Tool input `{"location_names": ["Italy or Spain"], "collection_year_min": 2021, ...}`. Report `place_applied: False`, `file_places_example: ['China', 'USA', 'Italy', 'United Kingdom', 'Brazil']`, total 15,274. Rows from China and USA only. Notes: "Filters applied: isolates collected in 2021 or later." and "The place 'Italy or Spain' could not be applied: no isolate with these genes lists it in Pathogen Detection, so isolates from every place are counted. Places that do appear include China, USA, Italy, United Kingdom, Brazil." 25.5 s, extraction 1.21 s, trust "ask". Plan narrative: "collected in Italy or Spain, in 2021 or later".
- Why it matters: a researcher comparing two countries is told Italy is not in the file and Italy is in the file, in one sentence, and gets rows from neither. Honest that the place was not applied, so it does not break the card's promise, but it reads as broken. The schema already takes up to three spellings; letting the model return each named place as its own entry, or telling it that a list of places is not one place, would close it without a word list.
- NOT FIXED

### J2-20-10: "submitted since 2021" is applied as "collected 2021 or later" (A-20-09 not avoided)
- Severity: minor (the note says "collected", so the substitution is visible to a careful reader)
- What: the prompt names only a collection year and gives the model no way to say a year is about something else (submission, publication). The model returned `since 2021` and code applied it to the collection date.
- Reproduction: the same live run as J2-20-09: question says "submitted since 2021"; tool input `collection_year_min: 2021`; note "Filters applied: isolates collected in 2021 or later."; count sentence "lists 15,274 Klebsiella pneumoniae isolates with these genes collected in 2021 or later".
- Why it matters: submission and collection dates differ by years in this file, so the set is not what was asked for. Disclosed by one word.
- NOT FIXED

### J2-20-11: Verified: the 297-name country list is read only by the model, and it does not break the no-hardcoded-decisions rule
- Severity: none (checklist item 3)
- What: `grep -rn GEO_LOC_COUNTRIES src tests` on the branch finds three lines: the docstring, the definition, and the one use, `"NCBI's country list: " + "; ".join(GEO_LOC_COUNTRIES)` inside `_SYSTEM_INSTRUCTION`. No code path tests membership, filters, or chooses by it. `verify` decides only by checking the model's claims against the question (years written, place standing in the text, role "collected") and by shape; the tool decides by the file's own text.
- Judgement: the list is the INSDC country vocabulary, not words lifted from the test questions, and it informs a spelling the model then claims; that is reference material, which the rule allows. The costs are that it is static (a vocabulary change needs a code edit) and that it is about 800 prompt tokens on every isolate question. The places where the design leans on the model without code verification are J2-20-02, J2-20-03, J2-20-08 and J2-20-09, not the list.
- Extraction only on isolate plans: verified by J2-20-05 (19 of 19 non-isolate questions make no extra call; the clarifying isolate question makes none; the planned isolate question makes one) and by mutation: removing the "place stands in the question" guard in `verify` turns `test_a_place_the_question_never_wrote_is_dropped` red (1 failed, 92 passed), restored 93 passed.
- NOT FIXED (nothing to fix)

### J2-20-12: When a place is not applied and the year range then leaves nothing, the tool's message says the search was "filtered to place 'Atlantis'" and that no isolate "carries a gene named blaKPC"
- Severity: minor (rare on real files, which hold thousands of gene carriers; it sits in a message this phase rewrote, `_filters_applied_clause` in the empty path)
- What: the empty-result message names every requested filter from the input, not from what was applied, and keeps develop's "carries a gene named X" wording, which is false once a filter, not the gene, is what emptied the set.
- Reproduction: a pytest probe in a copy of the branch, using the builder's own helpers: table `[USA: AZ 2010 blaKPC-2, Canada 2011 blaKPC-2]`, input `location_names=["Atlantis"], collection_year_min=2020`. Output: status `empty`, `place_applied=False`, error `None of the 2 Escherichia_coli_Shigella isolates in this snapshot (filtered to place 'Atlantis', collected 2020 or later) carries a gene named blaKPC. The whole file was read, so this is an exact answer rather than a scan that ran out of time.` Both rows carry blaKPC. The notes under the answer would say at the same time that Atlantis "could not be applied ... isolates from every place are counted".
- Related, same probe file: a deadline-cut scan with `location_names=["Italy"]` that read 3 USA rows carrying blaKPC returns `timeout` with no `filter_report` and the message "no isolate carrying one of the named genes had been found in the portion scanned", so the person gets no filter note at all and an untrue gene statement. The "could not be confirmed before the search ran out of time" sentence in `filter_notes` is unreachable, since the timeout output never carries a report.
- Why it matters: a filter shown as applied when the report says it was not, which is the card's one promise, though only on a path the live data rarely reaches.
- NOT FIXED

## Gates

| Gate | Result, on the branch at 2bd5125e |
|---|---|
| `ruff check` (no path) | All checks passed! |
| isort gate 2 (`isort --check-only --diff src tests services tracker alembic .claude .github`) | Clean, "Skipped 2 files", exit 0 |
| `pytest tests/system_03_search_agent -m "not integration" -q` | 6997 passed, 143 skipped, 24 deselected, 1 xfailed, 0 failed (268 s) |
| Mutation 1: remove the "place stands in the question" guard in `verify` | Red: `test_a_place_the_question_never_wrote_is_dropped`, 1 failed 92 passed; restored 93 passed |
| Mutation 2: remove the fallback count swap in the tool | Stays green, 353 passed (J2-20-06) |

Live spend this round: $0.081 timing plus about $0.015 for two probes, under the $0.30 budget. No Opus.

## Verdict: FIX FIRST

Against the bar "nothing worse than develop": no finding gives a person a wrong answer where develop gave a right one. Query 33 and 35 return the same count sentence, the same rows and no filter note. The one cost is time: about 1.5 s more before every isolate search starts (J2-20-04).

Against the card's own promise, "never shows a filter as applied when it was not", the main path holds live (Guinea, Italy or Spain). Two places break it:

- J2-20-09 (major): "Italy or Spain" becomes one place that matches nothing. The note then says Italy is not in the file and lists Italy as a place that does appear. It is a common way to ask.
- J2-20-12 (minor): on a rare path, the tool's own message says "filtered to place 'Atlantis'" after the report says the place was not applied.

Both are cheap to fix, and J2-20-06 is a vacuous test on the same not-applied path. Fix those three, then ship. J2-20-04 is the owner's call. None of the findings sits inside a fix made by an earlier review round. This is the card's second build. J2-20-12 sits in an error message this build rewrote.

What I verified with my own probes: the whole-name place match, the counting of undated isolates on 21 date shapes, `verify` on 27 replies, Think and non-isolate Plan identity with my own stub on 20 questions I chose, 12 sequential timing runs, two live filtered questions, the empty and cut-scan tool paths, and the gates. The two mutations are mine.

What I only read: the build report's 21 live runs, its 12-call extraction probe, its four mutations, and how the UI renders notes and the plan line (J2-20-01, J2-20-07 depend on that).
