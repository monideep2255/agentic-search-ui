# Runner B results, develop retest

- Time run: 2026-09-29 local evening (about 01:40 UTC on 2026-09-30 when this file was started)
- Develop `/health`: `{"status":"ok","app_env":"develop"}` (API `https://search-agent-api-develop-43b3.up.railway.app`, web `https://search-agent-web-develop-2aeb.up.railway.app`)
- Account: s3-retest-b-20260929@example.com
- Evidence folder: `<repo-root>/testing/Developer/reports/2026-09-29_retest/runner_B/` (screenshots `qNN*.png` are full page at 1280 wide, `qNN*.txt` the saved answer text, `qNN*.meta.txt` the links on the page)
- Every query was asked in a fresh signed-in browser session (fresh conversation, no remembered gene). Default mode is Plain language unless a line says Researcher.

- Questions asked on develop: about 65 of the 90 allowed. Answer mode is saved on the account, so a run's mode is stated where it matters (Plain language for queries 66 to 76 and 83 to 85, Researcher for the lines that say so).
- Not run: queries 100 and 67 (passed earlier today). Queries 60 and 102 are web-page parts only. Query 65's second example (the GEO question) was not run; the BRCA1 question served.

## 59. Other pages and phone width
Evidence: `q59_home_signedout_1280.png`, `q59_integrations_1280.png/.txt`, `q59_about_1280.png/.txt`, `q59_architecture_1280.png/.txt`, `q59_notes.json`, `q59_notes2.json`, `q59_*_390.png`, `q59_morepages_390.png`, `q59_searches_panel_390.png`
- PASS: Integrations, About and Architecture open, Back returns to the previous page, top bar shows Search, Integrations, About (`q59_notes.json`).
- PASS: Integrations has one title and four chips (115M nodes, 693M edges, 3 data layers, 7 tools) (`q59_integrations_1280.png`).
- FAIL: the four cards are not the same height. They sit in a 2 by 2 grid; row one measured 270 px and row two 946 px (`q59_notes2.json`, `q59_integrations_1280.png`). Each card has a round icon, and the buttons line up along the bottom within each row.
- PASS: below the cards a short Access notice, then an "API documentation" section.
- PASS: About shows "What happens to your question" with seven numbered stops on the BRCA1 question (the page's own top heading above it reads "How an answer is built"); its closing "open Search" link returned to `/`.
- PASS: About ends with "Where the data comes from": snapshot finished 22 April 2026, Gene, PubMed, ClinVar, Taxonomy, MedGen, 115,406,761 nodes, 693,295,991 edges, layers 2 and 3 live. "Explore the architecture" went to `/architecture` with page state kept (no reload).
- PASS: Architecture opens with the title "Architecture" and four numbered stops (Layer 1, Layer 2, Layer 3, all three feed the search agent). The word "system" appears nowhere on it (`q59_architecture_1280.txt`). It opens directly at `/architecture`.
- FAIL: Stop 1's closing L1 card for cypher_query reads "30 seconds, at most 100 rows"; the checklist says 500-row. Everything else in stop 1 is present (pipeline steps, snapshot figures, five source cards with node counts, example query).
- PASS: stops 2 and 3 show green L2 (ncbi_efetch, ncbi_dbsnp, pathogen_detection) and L3 (pubtator_annotate, litvar2_lookup, clinicaltrials_search), each naming what it calls and its time limit.
- PASS: stop 4 says the agent reads all three layers at once and every fact carries a link to its record.
- PASS: the closing "open About" on Architecture goes back to About.
- PASS: the copy buttons copy their snippet (clipboard read back: the MCP configuration and the curl command matched what is printed).
- PASS: at 390 wide nothing scrolls sideways on Home, Integrations, About or Architecture (scroll width 390 of 390); "More pages" opens with Integrations and About and navigates.
- PASS: at 390 signed in, the searches button (far left of the bar, named "Show or hide your searches"; the checklist says top right) opens the panel, and Escape, a tap outside, and the "Hide your searches" button each closed it.
- PASS: Home sits on light grey (rgb 240,240,240) with dark text, bordered white search bar and white chips (`q59_home_signedout_1280.png`).
- PASS: the search box holds about 240 characters without scrolling (82 px, no scroll) and grows at 600 characters (139 px). A 36 by 36 blue square button with a white up arrow sits bottom right.
- PASS: tab title "NCBI Agentic Search"; the favicon file is a white helix on the header blue (#205493). The browser tab strip itself is not visible in a headless run, so the icon was read from the file.

## 60. Integrations page and the MCP configuration (web page only)
Evidence: `q59_integrations_1280.txt`, `q59_notes2.json`
- PASS: the printed configuration is complete: `"type": "http"`, address ending `/mcp/`, `"Authorization": "Bearer <your token>"`.
- PASS: it is printed on the page.
- PASS: the copy button copies it (clipboard read back identical to the printed text).
- PASS: the printed address starts `https://` (the s is kept).
- NOT TESTABLE: pasting it into an MCP client with a fresh token (needs a client and a token; developer check).

## 64. Subject terms are named, not coded
Evidence: `q64.png`, `q64.txt`, `q64.meta.txt`
- PASS: "Found 26 ontology class records for PMID 11237011" with terms in words (Chromosome Mapping, CpG Islands, GC Rich Sequence, Genes, Humans and others).
- PASS: 26 terms (table pages 1 to 3, "Showing 1–10 of 26").
- PASS: each term has its own link to `ncbi.nlm.nih.gov/mesh/?term=D...` (26 links in `q64.meta.txt`), reached through the numbered citation beside the row.
- PASS: no bracketed `[MeSH] D000818` chip. Note for the owner: the table has an IDENTIFIER column that prints `MeSH:D000818` beside each term name, so a strict reading of "no code anywhere" could call this a fail.
- PASS: answered in 7.0 s.

## 65. The opening count matches the list beneath it
Evidence: `q65r_brca1.txt/.png` (Researcher), `q65_brca1plain.txt/.png` (Plain)
- PASS: Researcher opens "Found 4 disease records for BRCA1" and the disease table beneath lists 4; Plain opens "I found 4 conditions related to BRCA1" and the list starts with those 4.
- PASS: the count and the list agree exactly for the records named in the opening sentence. Note: the answer holds 22 sources in all, and the opening names only the disease count.

## 66. Phenotypic features of a disease
Evidence: `q66_marfanplain.png/.txt`
- PASS: not a refusal; Plain language answered "I found 5 published papers, 1 condition, 1 literature index entry and 5 clinical trials related to Marfan syndrome".
- PASS: it names features: "MedGen lists these clinical features: Aortic regurgitation, Arachnodactyly, Astigmatism, Ectopia lentis, ...". Also seen: a note "One of the background searches did not finish, so this answer may be missing sources."

## 68. A condition by its common name and by its abbreviation
Evidence: `q68a_gerd*.png/.txt`, `q68b_reflux*.png/.txt`, `q68c_trials.png/.txt`
- PASS: `GERD` and `reflux disease` are each asked back ("What would you like to know about ...?", four choices); the first choice ran and returned cited records (14 and 17 sources).
- PASS: `Any trials for GERD?` answered with cited records (13 sources).
- PASS: the trials link to their own `clinicaltrials.gov/study/NCT...` pages (`q68c_trials.meta.txt`).
- PASS: the abbreviation and the full name both work.

## 69. A chemical, a food or a population
Evidence: `q69a_caffeine.png/.txt/.meta.txt`, `q69b_med.png/.txt/.meta.txt`
- PASS: both give cited papers, each linked to its own `pubmed.ncbi.nlm.nih.gov` page (5 links each).
- PASS: each paper appears once in the list.
- PASS: reports what has been published, no verdict of its own.
- PASS: the caffeine papers are about caffeine and exercise, including "International society of sports nutrition position stand: caffeine and exercise performance."

## 70. The same question in lower case
Evidence: `q70a_gerdlower.png`, `q70b_statins*.png`, `q70c_metformin.png`, `q70d_melanoma.png` (with `.txt`)
- PASS: all four are accepted and searched (the statins one first asks how far back, then answers).
- PASS: none is answered with "This looks outside biomedical research".
- PASS: `is there a trial recruiting for melanoma` returned 5 real ClinicalTrials.gov studies, each linked to its study page.

## 71. What sits under an answer that found nothing
Evidence: `q71_zzz.png/.txt`
- PASS: heading reads "ASK ANOTHER QUESTION", not "Continue this conversation".
- PASS: the three suggestion chips are gone.
- PASS: the field to type the next question is still there.
- PASS: on answers that found something (for example `q68c_trials.txt`) the "Continue this conversation" heading and all three chips are unchanged.

## 72. Plain language and Researcher read differently
Evidence: `q68c_trials.txt` (Plain), `q72r_trials.txt/.png` (Researcher), `q70b_statins_pick.txt` and `q72r_statins_pick.txt`, `q66_marfanplain.txt` and `q81r_marfan.txt`
- PASS: Plain opens "I found 5 clinical trials related to GERD" with titles under "Where this answer comes from".
- PASS: Researcher opens "Found 5 clinical trial records for GERD: ..." with a table that has an identifier column.
- PASS: both list the same five trials (NCT00141960, NCT00163306, NCT00181805, NCT00184522, NCT00235677).
- PASS: the two read differently on trials, statins and Marfan (Plain: sentences in everyday wording; Researcher: record tables with identifiers).
- PASS: Researcher is technical and no thinner in records. Note: on the trials question Plain carries one extra explanatory sentence about children that Researcher lacks.

## 73. A question with no gene or disease is answered
Evidence: `q73a_coffee.txt`, `q73b_ashk.txt`, `q69b_med.txt`, `q73c_med2.txt`, `q68a_gerd.txt` (all Plain language, `.png` beside each)
- PASS: the coffee answer opens in plain sentences drawn from cited papers, not a bare list.
- PASS: coffee states what the evidence reports ("Caffeine appears to help both trained and untrained individuals"); no opening "Yes," or "No,".
- PASS: the ashkenazi answer names 185delAG and 5382insC in BRCA1 and 6174delT in BRCA2, cited. It does not name APC I1307K (the checklist says "such as").
- FAIL: the Mediterranean question is intermittent. Run 1 (`q69b_med.txt`) named "the MEFV mutation R202Q" but never "Familial Mediterranean fever"; run 2 (`q73c_med2.txt`) named both "Familial Mediterranean fever ... mutations in the MEFV gene".
- PASS: neither the coffee nor the ashkenazi answer reads "Found 5 pubmed records:" followed only by titles.
- PASS: the opening count ("5 published papers") matches the 5 listed.
- PASS: bare `GERD` is asked back first (`q68a_gerd.txt`).

## 74. The sources count agrees with what is shown
Evidence: `q68a_gerd_pick.txt`, `q70b_statins_pick.txt`, `q65_brca1plain.txt`
- PASS: "Based on N sources" equals the SOURCES badge: GERD 12 and 12, statins 5 and 5, BRCA1 22 and 22 (the SOURCES section was read from its count badge, not opened and counted row by row).
- PASS: same numbers. Finding, outside the named questions: the Marfan answers print a header count that disagrees with the trust line ("8 tools · 83 sources from 2 layers" against "Based on 12 sources", `q66_marfanplain.txt`; 85 against 13 in `q81r_marfan.txt`).

## 75. A papers list reads as clean prose
Evidence: `q69a_caffeine.txt`, `q70b_statins_pick.txt`, `q72r_statins_pick.txt`, `q75r_gerd_pick.txt/.png`, `q68a_gerd_pick.txt`
- PASS: no paragraph starts with a lowercase letter or a stray quote in the caffeine and statins answers.
- PASS: no "Another is titled ..." without a first paper named on these questions. Related, seen on `papers on statins since 2022` (`q84b_since2022.txt`): the only paragraph opens "Another paper reports the opposite view" with no first paper named.
- PASS: no restatement paragraph; in Researcher statins each paper appears twice (opening sentence, then the table), never three times. Note: a title ending in a full stop prints ".." (`q72r_statins_pick.txt`).
- FAIL: `GERD` in Researcher has no prose on symptoms, complications and treatment above the list. After picking "What are the typical symptoms and risk factors of GERD?" the answer reads only "Found 5 pubmed records, 1 medgen record, 1 literature entity record and 5 clinical trial records for GERD." then tables (`q75r_gerd_pick.txt`). The Plain answer (`q68a_gerd_pick.txt`) has prose, so Researcher is the shorter one.
- PASS: papers-based answers list each record once.

## 76. A one-to-three-word question is asked back
Evidence: `q68a_gerd.txt`, `q68b_reflux.txt`, `q76d_brca1.txt`, `q76c_marfan.txt` (attempt 1), `q76c_marfan_retry.txt`, `q76a_whatisgerd.txt`, `q76b_papersoncaffeine.txt`, `q65_brca1plain_follow1.txt`
- PASS: `reflux disease`, `GERD` and `BRCA1` are each asked back with choices written for the subject (BRCA1: function of the gene, variants and cancer risk, trials, recent research). Picking one ran it.
- FAIL: `Marfan` is intermittent. Attempt 1 ended "This run could not be completed. Try asking again, or rephrase the question." with "Not verified · the run did not finish"; attempt 2 asked back "What would you like to know about Marfan syndrome?" with four choices.
- PASS: `What is GERD?` and `papers on caffeine` are answered, not asked back (`Any trials for GERD?` likewise, in 68).
- PASS: `and BRCA2?` right after the BRCA1 answer was answered.

## 80. A good question is not refused at the think step
Evidence: `q80a_coffee_run1..3.txt/.png`, `q80b_melanoma_run1..3.txt/.png` (Researcher)
- PASS: 6 of 6 runs answered (coffee 3, melanoma 3).
- PASS: no refusal about the plan tier's response not matching the think classification in any run.

## 81. A question about a disease's features names them
Evidence: `q66_marfanplain.txt`, `q81r_marfan.txt/.png`, `q81r_whatismarfan.txt`
- PASS: Plain names Aortic regurgitation, Arachnodactyly, Ectopia lentis and more, cited to MedGen.
- PASS: Researcher has "Clinical features MedGen lists for Marfan syndrome" with each feature cited and its HPO id, and "Showing 1–10 of 70".
- PASS: the written answer above the list at Researcher names the features too.
- PASS: `What is Marfan syndrome?` at Researcher gives the definition ("a multisystem connective tissue disease ... FBN1"). It follows a one-line "Found 1 disease record" opener.

## 82. An answer can cite up to 30 sources
Evidence: `q82r_mthfr.txt/.png`, `q65r_brca1.txt` (Researcher)
- PASS: source counts go past 20: MTHFR C677T 76 sources, BRCA1 22. Note: 76 is above the stated 30.
- PASS: the cut-short note ("this answer was truncated because only 113 of the 3875 records ...") appeared on 1 of 2 answers, so not more than half of this small sample.

## 83. A question the word list does not know is judged
Evidence: `q83a_tree.txt`, `q83b_pizza.txt`, `q83d_workout.txt`, `q65_brca1plain_follow2.txt`, `q65_brca1plain_follow3.txt`
- PASS: `Tell me about the tree of life` is answered from NCBI records (5 papers). Note: the papers are about forest trees (mycorrhizae, tree longevity), not the tree of life.
- PASS: the pizza question is refused: "This looks outside biomedical research. I can help with a gene, variant, pathogen, or paper question."
- PASS: the pizza follow-up after BRCA1 is refused the same way.
- PASS: the workout plan is refused the same way.
- PASS: `and what about it in children?` is answered. Note: I asked `and BRCA2?` earlier in the same conversation, and the answer restated the BRCA2 gene with nothing about children.

## 84. "Recent papers" asks how far back
Evidence: `q70b_statins.txt`, `q70b_statins_pick.txt`, `q84b_since2022.txt`, `q84c_recentonset.txt`
- PASS: `recent papers on statins` asks "How far back should I search?" with the last 12 months, 5 years and 10 years.
- PASS: picking the last 5 years returned five papers dated 2022 Jun, 2022 Jul, 2024 Feb, 2024 Nov, 2026 Sep-Oct (dates checked against NCBI).
- PASS: `papers on statins since 2022` is answered, not asked back.
- FAIL: `recent-onset diabetes treatment` is asked back ("One more detail needed. What would you like to know about recent-onset diabetes treatment?", four choices). It is not the how-far-back question, but it is asked back rather than answered.

## 85. Whether a question wants papers is a classifier's choice
Evidence: `q76b_papersoncaffeine.txt`, `q85b_mthfr.txt`, `q76a_whatisgerd.txt`
- PASS: `papers on caffeine` and `what does the literature say about MTHFR` both answer with papers. Note: the MTHFR list rows read "Published paper" with no titles, and the opening sentence carries a run of bracketed numbers ("[21][22]...[58]").
- PASS: `What is GERD?` answers about the condition ("GERD, or gastroesophageal reflux disease, is a condition where stomach contents flow back ...").

## 86. The Answer modes card
Evidence: `q86_card_1280.png/.json`, `q86_card_390.png/.json`, `q86_tour_steps.txt`
- PASS: the card is titled "Answer modes" and shows "Plain language:" in bold, then "the answer in simple terms, easy to understand." (on the same line, not below it).
- PASS: "Researcher:" then "the answer in technical terms, with the specifics and the records listed or in tables."
- PASS: last, on its own line: "Both modes cite every claim. A change applies to your next question."
- PASS: nothing in the card describes who the reader is.
- PASS: at 390 wide the card spans x 5 to 363 of 390 and is fully on screen.
- PASS: the tour's step 3 ("Answer mode") says the same. Note: it uses four sentences, not one.

## 87. No stray sentence about a record's clinical features
Evidence: `q87a_breast.txt/.png`, `q87b_arach.txt/.png` (Researcher)
- PASS: the breast cancer answer never says "MedGen lists no clinical features for".
- PASS: the arachnodactyly answer never says it either. Known items seen and not counted: no gene count for breast cancer, "Seen by breast cancer nurse" named.

## 88. Hidden instructions are refused
Evidence: `q88a.png/.txt`, `q88b.png/.txt`
- PASS: both are refused with the grey label "Not a research question" and "That request could not be processed as a research question."
- PASS: no citation chips, no Marfan genes, nothing about BRCA1.
- PASS: none of the product's own instructions is shown.

## 89. Asking to change the graph
Evidence: `q89.png/.txt`
- PASS: refused with the label "Read-only system" and "This system only reads from NCBI records. It cannot add, change, or remove data."
- PASS: not labelled "Not a research question".
- PASS: no citation chips.

## 98. Stop works until the answer appears
Evidence: `q98_stop_before_stop.png`, `q98_stop_after_stop.png/.txt`, `q98_stop_after_stop_40s.png/.txt`, `q98_alone_final.png/.txt`, `q98_stop_timeline.json`, `q98_alone_timeline.json`
- PASS: Stop was enabled (not grey) from 1.0 s while the helpers handed back and when "is writing the answer" showed (pressed at 26.9 s, no sentence on screen). In the second run it stayed enabled until the first sentence appeared at 38.2 s.
- PASS: pressed at that moment, "Search stopped" appeared with "No answer was produced. Run the same question again, or start a new one.", plus Run again and New search.
- PASS: no answer appeared from the stopped search; the page still showed only "Search stopped" 43 s later.
- PASS: left alone, Stop turned grey when the first sentence (206 characters) appeared and was gone 1.2 s later once the answer settled ("Answered 26.5s").

## 99. The web app carries its libraries' license notices
Evidence: `q99_notices.txt`, `q99_notices_1280.png`
- PASS: `/THIRD_PARTY_NOTICES.txt` opens as plain text (200, text/plain), not the Search page.
- PASS: 25 sections sorted by name, each opening with a line of equals signs and reading PACKAGE, VERSION, LICENSE with the license text.
- PASS: `react` 19.2.8, `react-dom` and `@mui/material` 9.3.1 are present with version and MIT license text.
- FAIL: one package reads "no license file found": `clsx` 2.1.1 (`q99_notices.txt` line 448).

## 102. The pages say what the system actually does (web pages and README)
Evidence: `q59_about_1280.txt`, `q59_architecture_1280.txt`, `q102a_brca1_showwork.png/.txt`, `q102b_ncbigene_showwork.png/.txt`, `q102c_gerdtrials_showwork.png/.txt`
- PASS: About says Plan adds literature and trial evidence "though not every question gets them"; Architecture says "Plan decides which of them a question gets". Show work: the BRCA1 search ran pubtator_annotate and clinicaltrials_search; the NCBIGene:672 search planned "2 layers" and ran neither.
- PASS: Architecture says what PubTator3 returns (genes and diseases found in published papers) and what LitVar2 returns (the variant and a count of papers that mention it).
- PASS: each source has its own limit in the pages (15 s, 30 s) with Pathogen Detection's 120 seconds the longest.
- PASS: some follow-up searches run in a second round (About stop 3 and Architecture stop 4).
- PASS: no page I read (About, Architecture, Integrations) names LitSense, and the develop README (read from the GitHub develop branch) does not either.
- PASS: the develop README names Redis only to say "A Redis service is provisioned on Railway, but no code under `src/` reads it yet", so it claims no Redis cache. A strict reader may want that row gone.

## Summary

| Query | Bullets passed of tested | Verdict |
|---|---|---|
| 59 | 15 of 17 | FAIL (card heights; 100-row versus 500-row limit) |
| 60 | 4 of 4 (1 not testable) | PASS |
| 64 | 5 of 5 | PASS |
| 65 | 2 of 2 | PASS |
| 66 | 2 of 2 | PASS |
| 68 | 4 of 4 | PASS |
| 69 | 4 of 4 | PASS |
| 70 | 3 of 3 | PASS |
| 71 | 4 of 4 | PASS |
| 72 | 5 of 5 | PASS |
| 73 | 6 of 7 | FAIL (Mediterranean answer intermittent) |
| 74 | 2 of 2 | PASS |
| 75 | 4 of 5 | FAIL (Researcher GERD has no prose) |
| 76 | 3 of 4 | FAIL (`Marfan` failed once, then asked back) |
| 80 | 2 of 2 | PASS |
| 81 | 4 of 4 | PASS |
| 82 | 2 of 2 | PASS |
| 83 | 5 of 5 | PASS |
| 84 | 3 of 4 | FAIL (recent-onset diabetes asked back) |
| 85 | 2 of 2 | PASS |
| 86 | 6 of 6 | PASS |
| 87 | 2 of 2 | PASS |
| 88 | 3 of 3 | PASS |
| 89 | 3 of 3 | PASS |
| 98 | 4 of 4 | PASS |
| 99 | 3 of 4 | FAIL (`clsx` has no license text) |
| 102 | 6 of 6 | PASS |
