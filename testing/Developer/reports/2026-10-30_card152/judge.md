# Card 152 judge report

Judge, one round, branch fix/card152-topic-words-as-one-term at 0617e15e, draft pull request 319. Findings are appended as they are established.

## Findings

Method note: all live evidence is free PubMed ESearch and ESummary GETs, `sort=relevance`, retmax 10, 2026-10-30, under 3 a second, run by the judge's own script (`live_probe.py` in the judge's scratchpad), which builds the space form with the branch's `build_topic_term` and the AND form by joining the branch's own `topic_search_words` with ` AND `. 35 questions, no window. The diagnosis file named in the brief is not in the worktree; it is only in the main checkout (see J-152-06).

### J-152-01: The word extraction, unchanged by this fix, still breaks disease names, so "searches the subject as I wrote it" fails for common questions
- Severity: major (pre-existing, NOT introduced by this diff; identical in both term shapes; it fails the card's acceptance sentence, not its example)
- What: `topic_search_words` (`src/system_03_search_agent/core/breadth_plan.py:630` to `656`, regex `_TOPIC_WORD` at line 608 `[A-Za-z][A-Za-z0-9'-]*`) drops stopwords that are part of a name, drops bare numbers, drops Greek letters and splits any accented word. Joining the result with a space cannot recover what extraction already threw away.
- Evidence, `build_topic_term` on the branch:
  - `recent papers on down syndrome` -> `syndrome` ("down" is in `_TOPIC_STOPWORDS`, line 385)
  - `papers on type 1 diabetes` -> `type diabetes`; `papers on covid 19` -> `covid`; `papers on IL 6` -> `il`; `papers on the 5-HT receptor` -> `ht receptor`
  - `papers on vitamin a deficiency` -> `vitamin deficiency`; `papers on hepatitis a` -> `hepatitis`; `papers on influenza a vaccines` -> `influenza vaccines`
  - `papers on β-thalassemia` -> `thalassemia`; `papers on IL-6 and β-cell function` -> `il-6 cell function`
  - `papers on sjögren syndrome` -> `sj gren syndrome`; `papers on ménière disease` -> `m ni re disease`; `papers on behçet disease` -> `beh et disease`
- Live, ESearch relevance, 2026-10-30 (same count in both shapes):
  - `syndrome`: 1,776,246 hits; top titles "Sunflower syndrome", "Serum hyperviscosity syndrome", "Post-orgasmic illness syndrome", "Stendhal syndrome". 0 of the first 6 are about Down syndrome.
  - `type diabetes`: 449,733 hits; top titles "central diabetes insipidus", "Autoimmune diabetes insipidus", "Monogenic diabetes syndromes", "Wolfram Syndrome". Not type 1 diabetes.
  - `m ni re disease`: querytranslation `"m"[All Fields] AND ("new int"[Journal] OR "narrat inq"[Journal] OR "ni"[All Fields]) AND ("radiation effects"[MeSH Subheading] ...` 40 hits, top titles about cervical cancer radiosensitivity and sotorasib. 0 about Ménière disease.
  - `beh et disease`: `"bull epidemiol hebd paris"[Journal] OR "beh"` AND `"etiology"[MeSH Subheading]`; 177 hits, mixed.
  - `il-6 cell function`: 0 of 10 about beta cells in either shape.
- What a person sees: `recent papers on down syndrome` lists papers on unrelated syndromes, and the plan line says "searching the literature for: syndrome". `papers on type 1 diabetes` lists diabetes insipidus papers. A papers question naming the disease takes this path (diagnosis "Which questions take this path", row 2), so these are reachable today. This is the same class of defect the card describes (the subject not searched as written), at a different step.
- NOT FIXED

### J-152-02: The plan line and the refusal show the extracted words, not "my words as I typed them"
- Severity: minor
- What: the acceptance says "The plan line shows my words as I typed them." `graph.py:7311` shows `topic_term`, which is lowercased, stopword-stripped, number-stripped and accent-split. With commas gone, the stripped string now reads as if it were the person's phrase.
- Evidence (branch `build_topic_term`, which is exactly what the narrative interpolates): `What positive and negative genes do ashkenazi jewish people have?` -> plan line "...for: positive negative genes ashkenazi jewish people"; `papers on type 2 diabetes and SGLT2 inhibitors` -> "for: type diabetes sglt2 inhibitors"; `papers on sjögren syndrome` -> "for: sj gren syndrome". The refusal uses the same string (`refuse.py:102`), e.g. the test's own expectation "variants people mediterranean descent".
- What a person sees: a run-on phrase that is not what they typed; for "sj gren" a visibly mangled name. It is honest about what was searched (which is good), but it is not "my words as I typed them" except in the simple case (`cystic fibrosis`). Before, "type, diabetes, sglt2, inhibitors" at least read as a keyword list.
- NOT FIXED

### J-152-03: A space-joined pair can now be read by PubMed as a journal title or an author name
- Severity: minor (unsure whether any real question hits it badly; the journal case is ORed with the topic, the author case replaces the topic)
- What: with no operator between the words, PubMed's automatic term mapping looks the whole string up in its journal and author tables, which an explicit ` AND ` prevented. A question's words thus acquire a `[Journal]` or `[Author]` tag that the person never typed. This is new behaviour from this diff.
- Evidence, live querytranslation, 2026-10-30:
  - `papers on smith j` -> space term `smith j` -> `j, smith[Investigator] OR smith j[Author] OR smith j[Investigator]`, 36,438 hits, top 10 are that author's papers (obesity GWAS, whole blood in hemorrhage, TOPMed). AND form `smith AND j`: 137,919 hits, titles containing "Smith's".
  - `papers on cell metabolism` -> `"cell metab"[Journal] OR ("cell" AND "metabolism") OR "cell metabolism"[All Fields]`; top 10 includes the journal's own editorials ("Cell Metabolism Clinical and Translational Reports", "Cell metabolism ♥ cardiovascular biology").
  - `nature genetics` -> `"nat genet"[Journal] OR ...`, top 10 is 8 Nature Genetics papers on unrelated subjects (ovarian carcinoma copy number, gallbladder cancer) plus "Nature plants."
  - `sleep medicine` -> `"sleep med"[Journal] OR ...`; `cancer cell` -> `"cancer cell"[Journal] OR ...`; `cancer letters` -> `"cancer lett"[Journal] OR ...` (19,522 against 198,141).
  - `papers on clinical trials` -> `"clinical trial"[Publication Type] OR "clinical trials as topic"[MeSH Terms] ...`.
- What a person sees: for most of these the top 10 stays on topic (cell metabolism, cancer cell, sleep medicine were judged at least as on topic as the AND form). The brief's check "never lets a question's word act as a field tag" is, strictly, not met: PubMed itself attaches the tag. I found no realistic topic question where this produced an off-topic top 10; `nature genetics` and `smith j` are the cases where the subject is replaced by a journal or an author.
- NOT FIXED

### Evidence E-1 (not a finding): live PubMed comparison, AND form against space form

ESearch `sort=relevance`, retmax 10, 2026-10-30. "On topic" is the judge's reading of the ten titles against the subject asked; where a number is marked h it is a keyword heuristic averaged over four repeated runs, because PubMed's relevance order shuffled between identical calls (all four rerun pairs returned a different order from run 1). No call errored, no `errorlist` or `warninglist` was returned for any space term, and no space term carried a boolean operator from the question.

| Question | Space term | Hits AND / space | On topic AND / space |
|---|---|---|---|
| papers on the effects of caffeine on exercise performance | effects caffeine exercise performance | 1,369 / 1,369 (same translation) | 7 / 10 |
| Are there any beneficial variants ... mediterranean descent? | variants people mediterranean descent | 17 / 17 (same) | about 4 / 4 |
| recent papers on statins | statins | 76,581 / 76,581 (same) | 10 / 10, same set |
| what does the literature say about metformin | metformin | 38,411 / 38,411 (same) | same set |
| Does coffee help make exercise more effective? | coffee exercise effective | 534 / 534 (same) | 6 / 7 |
| What positive and negative genes do ashkenazi jewish people have? | positive negative genes ashkenazi jewish people | 27 / 27 (same) | similar |
| recent papers on cystic fibrosis, no window | cystic fibrosis | 70,296 / 69,964 | 7 / 10 (h: 7,7,7,7 / 10,10,10,10) |
| recent papers on cystic fibrosis, 5-year window | cystic fibrosis AND (dp) | 13,392 / 13,356 | 7 / 10 (AND rows 4, 6, 7: general fibrosis, choledochal cysts, bacterial overgrowth) |
| recent-onset diabetes treatment | recent-onset diabetes treatment | 720 / 720 (same) | same |
| latest research on long covid | long covid | 46,777 / 47,152 | 10 / 10 |
| find me studies about vitamin d | vitamin d | 130,911 / 117,012 | 10 / 10 |
| What is known about EGFR mutations in non-small cell lung cancer | egfr mutations non-small cell lung cancer | 15,657 / 15,859 | 8 / 10 |
| papers on breast cancer | breast cancer | 600,318 / 595,192 | 9 / 10 |
| papers on covid-19 vaccine myocarditis (hyphen, number) | covid-19 vaccine myocarditis | 1,433 / 1,175 | 9 / 9 |
| papers on TNF-α inhibitors in Crohn's disease (Greek, apostrophe) | tnf inhibitors crohn's disease | 2,858 / 7,134 | h 7 / 7 |
| papers on type 2 diabetes and SGLT2 inhibitors (number) | type diabetes sglt2 inhibitors | 8,327 / 11,405 | h 4 / 5 (judge's reading of run 1: about 7 / 5, see J-152-04) |
| papers on aspirin OR ibuprofen (uppercase OR) | aspirin ibuprofen | 1,951 / 1,951 (same) | 10 / 10 |
| papers on caffeine[Title] NOT "exercise" (tag, NOT, quotes) | caffeine title exercise | 5 / 5 (same) | same five |
| papers on gene* therapy (asterisk) | gene therapy | 753,989 / 600,337 | 9 / 10 |
| papers on smoking NEAR lung cancer | smoking lung cancer | 33,277 / 33,175 | 10 / 10 |
| papers on (breast cancer) AND (BRCA) (parentheses) | breast cancer brca | 8,104 / 8,089 | about 7 / 8 |
| papers on human genetics | human genetics | 3,473,096 / 1,773,258 | 6 / 10 |
| papers on cell metabolism | cell metabolism | 4,997,145 / 3,005,659 (journal tag, J-152-03) | 5 / 8 |
| papers on nature genetics | nature genetics | 544,474 / 140,935 (journal tag) | ambiguous question |
| papers on sleep medicine | sleep medicine | 163,933 / 156,907 (journal tag) | 10 / 10 |
| papers on cancer cell | cancer cell | 2,585,907 / 1,522,009 (journal tag) | 10 / 10 |
| papers on smith j | smith j | 137,919 / 36,438 (author tag) | ambiguous question |
| papers on alzheimer's disease | alzheimer's disease | 268,425 / 261,815 | 9 / 10 |
| papers on quality of life in heart failure | quality life heart failure | 17,955 / 17,922 | 1 / 9 |
| papers on sonic hedgehog signalling | sonic hedgehog signalling | 5,714 / 5,714 (same) | 10 / 10 |
| papers on gut microbiome and depression | gut microbiome depression | 4,183 / 3,205 | 10 / 10 |
| papers on IL-6 and β-cell function | il-6 cell function | 127,740 / 71,936 | 0 / 0 (J-152-01) |
| papers on "heart attack" in women (quotes) | heart attack women | 2,607 / 28,363 | 9 / 8 loose, about 5 / 8 strict (J-152-04) |
| papers on HIV pre-exposure prophylaxis | hiv pre-exposure prophylaxis | 9,605 / 9,735 | 10 / 10 |
| papers on lyme disease | lyme disease | 17,175 / 17,298 | 10 / 10 |

With the 5-year window on all 35: no error; the same-translation questions kept equal counts; counts moved by under 1 percent for the concept questions except the journal and author cases and `heart attack women` (627 against 6,291).

Operators: an uppercase `OR`, `NOT`, `NEAR`, `AND`, brackets, quotes, parentheses and a trailing asterisk in the question never reached either term; each was lowercased and dropped as a stopword or not matched by `_TOPIC_WORD`. The field-tag NAME survives as a plain word (`caffeine[Title]` -> `caffeine title`), in both shapes, which narrows `caffeine` to 5 hits because "title" becomes a required word; pre-existing.

### J-152-04: Two questions where the space form's top 10 may be no better, or one paper worse, than the AND form
- Severity: minor (unsure; within PubMed's run-to-run ranking noise on one of the two)
- What: the brief's bar is "never fewer on-topic papers in the top 10". Two questions do not clearly meet it.
- Evidence:
  - `papers on "heart attack" in women`, no window: space `heart attack women` maps "heart attack" to `"myocardial infarction"[MeSH Terms]` and returns 28,363 against 2,607. Space top 10 rows 4 "Risk factors profile of young and older patients with myocardial infarction" and 7 "A randomized trial of propranolol in patients with acute myocardial infarction. I. Mortality results" are not about women. AND top 10 row 10 "Cardiac myxoma" is off. Loose reading 9 (AND) against 8 (space); a keyword count over four repeated runs gave 10,10,10,10 against 9,9,9,9. Strict reading (heart attack specifically, not heart disease) favours space, about 5 against 8. With the 5-year window both are about 1 of 10 on "in women".
  - `papers on type 2 diabetes and SGLT2 inhibitors`: judge's reading of run 1, AND about 7, space about 5 (space rows 2 feline diabetes, 6 type 1 diabetes, 8 and 10 heart failure). A keyword count over four repeated runs reversed it: 4,4,4,4 against 5,5,5,4. Not reproducible as a regression.
- What a person sees: on "heart attack in women" the space form shows more heart attack papers and a couple that are not specifically about women. Never an error.
- NOT FIXED

### Evidence E-2 (not a finding): the real planner, branch against origin/develop

A judge-written probe (`tests/system_03_search_agent/core/test_zz_judge152_probe.py`, temporary, removed after the run) drove `run_streaming` with the topic test file's own model, decision and tool stubs, and `plan_node` with the isolate wiring file's stubs, in the worktree and in `git archive origin/develop` exported to the judge's scratchpad. `12 passed` in both trees. Diff of the recorded plan narrative, tool list, every ESearch term sent, trust outcome and answer text:

| Scenario | Result |
|---|---|
| Topic, no entity: `recent papers on cystic fibrosis` | term `cystic AND fibrosis` -> `cystic fibrosis`; narrative "for: cystic, fibrosis" -> "for: cystic fibrosis" |
| Same with a picked 5-year window (window pick stubbed) | `cystic fibrosis AND ("2021/10/30"[dp] : "3000"[dp])`; narrative "...for: cystic fibrosis, published in the last 5 years" |
| Papers question naming a disease (Think labels "cystic fibrosis", MedGen bound, classifier `wants_literature`) | same term and narrative as above, with "you asked for published papers"; graph not called |
| Same with window | same, window kept |
| Multiword gene name, no symbol: `papers on sonic hedgehog signalling` | `sonic hedgehog signalling` |
| Operators: `papers on aspirin OR ibuprofen NOT caffeine[Title] "x" (y) z*` | `aspirin ibuprofen caffeine title x y z`; no operator, bracket, quote or asterisk |
| Topic that finds nothing (Mediterranean question, empty PubMed) | refusal "I searched the published literature for variants people mediterranean descent and found nothing." (was "variants, people, mediterranean, descent") |
| Gene: `What does BRCA1 do?` | IDENTICAL: `BRCA1[Title/Abstract]`, `BRCA1[gene]`, `BRCA1`, same 13 tools |
| Disease without papers: `What is cystic fibrosis?`, `not_literature` | IDENTICAL: graph path, `cypher_query` only |
| Isolate: the golden E. coli question | IDENTICAL apart from `call_id` and helper persona, which differ between two runs of the branch itself (`pd-a729cdcff633` against `pd-f99101745561`) |

Side observation, both trees, not this card: the uppercase `OR` and `NOT` in the operator question were each looked up as a gene symbol (`OR[sym] AND human[orgn]`, `NOT[sym] AND human[orgn]`, twice each).

Encoding: the term reaches ESearch as an httpx `params` dict (`ncbi_eutils_actions.py:731` to `744`, `_get_or_error` -> `ncbi_transport.execute_get`), which percent-encodes it: `httpx.Request(..., params={"term": 'cystic fibrosis&retmax=500#x ...'})` gave `term=cystic+fibrosis%26retmax%3D500%23x+...`. Independently, `build_topic_term` on a question carrying `& # % = ; + / | \ ` ~ ! @ $`, the U+2000 to U+200F spaces, a no-break space, an ideographic space and a zero-width space between `AND` and `OR` returned `retmax b c d e f g h`: the term's character set was empty outside `[a-z0-9' -]`.

### J-152-05: A long question with a picked window can lose its date limit while the plan line says it was applied
- Severity: minor (pre-existing, not introduced by this diff; the space join makes it slightly less likely; contrived input)
- What: `_search_call` truncates the whole term to 500 characters (`breadth_plan.py`, `"term": term[:500]`) AFTER the window clause is appended (`plan_topic_search`), and `_TOPIC_WORD` has no per-word length cap.
- Evidence: `plan_topic_search('papers on ' + ' '.join('x' + c * 62 for c in 'abcdefgh'), window=<5 years>)` gave a 500-character term ending `... xhhhhhhh...h`, with no `[dp]` clause at all, while the narrative would read "published in the last 5 years". A partial cut is accepted silently by PubMed: live `cystic fibrosis AND ("2021/10` returned 294 hits, `"2021/10"[All Fields]`, warning "Unmatched double quote ignored."
- What a person sees: only with eight very long words; papers from any year under a line saying their range was applied.
- NOT FIXED

### J-152-06: The diagnosis named in the brief is not in the branch
- Severity: minor (process)
- What: `testing/Developer/reports/2026-10-30_card152/diagnosis.md` exists only in the main checkout, untracked there; the branch carries `build.md` alone. The build's reasoning rests on the diagnosis's measurements, and a reader of pull request 319 cannot see them.
- Evidence: `ls testing/Developer/reports/2026-10-30_card152/` in the worktree at 0617e15e: `build.md` only (plus this report).
- NOT FIXED

### J-152-07: One test fixture still carries the old AND-joined topic term
- Severity: minor
- What: `tests/system_03_search_agent/core/test_write_answer_structure.py:693` sets `"topic_search_term": "caffeine AND exercise AND performance"`, a shape the planner no longer produces. The build updated the same kind of fixture in `test_card_17_lead_in_order.py:257` and missed this one. Today the write path only reads the term's truthiness (`graph.py:14642`, `14738`) and the refusal, so the test still passes, but it now tests a state production cannot reach.
- Evidence: `grep -rn "topic_search_term" tests` lists line 693 with the AND form.
- What a person sees: nothing; a reader of the test is told the term looks like something it no longer does.
- NOT FIXED

### J-152-08: Comments and test docstrings now attribute AND-form measurements to the space form, or still describe the AND chain
- Severity: minor
- What: the diff rewrote recorded measurements to the new term shape without remeasuring them as dated, and left two comments describing the old join.
- Evidence:
  - `tests/system_03_search_agent/core/test_topic_search.py:136` to `138`: "Measured live: `coffee AND help AND make AND exercise AND effective` returned ZERO hits, and `coffee exercise effective` returned 532." The 532 was measured on 2026-09-23 against `coffee AND exercise AND effective`; the judge measured the space form today at 534.
  - Same file, lines 92 to 99: `# 1,356 hits` and `# 532 hits` now sit beside the space terms; today both shapes give 1,369 and 534.
  - `src/system_03_search_agent/core/breadth_plan.py:606` to `607`: "At most this many words are ANDed together. Every word in an AND chain is REQUIRED". Still true in effect (a space is AND in PubMed), stale in words.
  - `src/system_03_search_agent/core/graph.py:7285` to `7287`: "The narrative names the WORDS searched, never the AND-joined term ... `coffee AND exercise AND effective` is machinery". The narrative now prints the term itself.
- What a person sees: nothing. A later reader is told a number was measured on a shape it was not measured on.
- NOT FIXED

### Evidence E-3 (not a finding): break it

Judge's own mutation script (`mutate.py` in the judge's scratchpad), each mutation applied to the worktree, the five related test files run (`test_breadth_plan.py`, `test_card_17_lead_in_order.py`, `test_topic_search.py`, `test_window_paper_cap.py`, `test_write_answer_structure.py`), then the file restored. Baseline: `252 passed in 6.88s`.

| Mutation | Result |
|---|---|
| M1 `build_topic_term` joins with ` AND ` again | red, `23 failed, 229 passed` |
| M2 joins with ` OR ` | red |
| M3 joins with a double space | red |
| M4 `or` removed from `_TOPIC_STOPWORDS` | red (`test_no_pubmed_operator_can_ride_in_on_the_question_text`) |
| M5 `not` removed | red (`test_lowercase_or_and_not_never_reach_the_term`) |
| M6 `and` removed | red (`test_each_measured_question_builds_the_term_that_was_searched_live[...ashkenazi...]`) |
| M7 no lowercasing, so an uppercase `OR` survives | red |
| M8 `_TOPIC_WORD` admits quotes and brackets | red |
| M9 the window clause joined by a space, not ` AND ` | red, `2 failed` |
| M10 word cap removed | red, `1 failed` |
| M11 narrative comma-splits the term on spaces | red, `1 failed` (`test_a_question_asking_for_papers_reaches_the_papers_whatever_resolved` only) |
| M12 narrative drops the term | red, `1 failed`, same test |
| M13 narrative shows the raw question | red, `1 failed`, same test |
| M14 refusal comma-joins the words | red, `3 failed` |
| M15 refusal skips its whitespace collapse | GREEN, `252 passed`. Equivalent in practice: `build_topic_term` never emits repeated whitespace, so the collapse is defensive only |
| M16 refusal shows a fixed string | red, `5 failed` |

Only one test guards the plan line, and only on the `you asked for published papers` wording; the `no gene, variant or disease was named` wording's "for:" text is unasserted beyond containing that phrase.

### Evidence E-4 (not a finding): gates

- `ruff check .` from the worktree root: `All checks passed!`, exit 0.
- `isort --check-only --diff src tests services tracker alembic .claude .github` (gate02): `Skipped 2 files`, exit 0, no diff.
- Related tests: `252 passed in 6.88s`.

## Verdict

PASS. No blocking finding. One major finding, J-152-01, is in the word extraction this diff did not touch. It fails the card's acceptance sentence for questions such as Down syndrome and type 1 diabetes, though not for the card's own example. The lead should decide whether it belongs to this card or gets its own.

Verified by the judge's own probes:

- The card's example. Live, with the 5-year window, the AND form had 3 of 10 off topic and the space form 0. Through the real planner on both arms, the term and the plan line are "cystic fibrosis".
- The live comparison of 35 questions with and without a window: no error, no operator from the question reaching the term, and same-translation questions with identical counts. On-topic counts are equal or better except the two cases in J-152-04, and those sit within PubMed's run-to-run reorder.
- The isolate path, and plans for gene and disease questions that do not ask for papers, are identical to origin/develop.
- URL encoding, and the character whitelist of the term.
- 15 of 16 mutations went red. The green one is equivalent in practice.
- `ruff` and isort are clean.

Read only, not probed:

- The live product on develop. The branch is not deployed, and the judge made no model call.
- Whether a real Think run sends a papers question naming a disease down the topic path. This was taken from the diagnosis and stubbed in the probe.

Findings that come from this diff itself (round one, so not a fix-of-a-fix): J-152-02 (the plan line's wording), J-152-03 (journal and author mapping that the space join newly allows) and J-152-08 (comments).
