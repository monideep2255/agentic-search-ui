# Product check on develop: cards 133 and 137 part 1

Pre-screen before the owner's retest, run on 2026-10-23 for the cards merged on the night of 2026-10-22. It files findings and closes nothing. The owner's verdict closes.

## Table of contents

- [Target](#target)
- [Findings](#findings)
- [Per query results](#per-query-results)
- [What was not captured](#what-was-not-captured)

## Target

- Web: https://search-agent-web-develop-2aeb.up.railway.app
- API /health, read before the first capture: `{"status":"ok","app_env":"develop"}`
- Deployed commit: 0c97b2c6 (merge of pull request 300), develop deployment status "success" at 04:13 UTC on 2026-10-23, per the repository's deployment record.
- Guest sessions only, no sign-in, no accounts. Every run is a fresh browser context loaded at the width in its file name.
- Times are on my clock from the Search click: first records is the first moment a records list or table is on screen, done is when the answer meta line appears.

## Findings

### PR-card133-01: "What does BRCA1 do?" lists the BRCA1 gene once, with both names, and every count agrees (pass)
- Kind: answer
- Verdict: pass, recorded so the owner sees what was checked
- What: in all four runs (Researcher and Plain language, each at 1280 and 390) the gene appears as one row, "BRCA1 DNA repair associated (BRCA1)", carrying chips 1 and 2. List total, Sources count, "Based on" line and meta line all read 17. Researcher tables hold 1 gene, 5 papers, 5 ClinVar, 1 OMIM and 5 trials, which is 17. Plain language shows "Showing 1–10 of 17". The count line reads "Found 1 gene record for BRCA1: BRCA1 DNA repair associated." (Researcher) and "I found 1 gene related to BRCA1." (Plain language), and both agree with the one gene row.
- Evidence: `brca1_do_researcher_1280.png` and `brca1_do_plain_390.png` (read myself), with the text in `brca1_do_researcher_1280.txt`, `brca1_do_researcher_390.txt`, `brca1_do_plain_1280.txt` and `brca1_do_plain_390.txt`. Meta line "Answered 9.5s · 13 tool calls · 17 sources cited from 3 layers" and the Sources header "17".
- Why a person would care: "BRCA1 is listed once, and every number on the page matches."
- From this card: yes. This is the fix.
- NOT CLOSED

### PR-card133-02: At 1280 the BRCA1 answer opens on "The encoded protein..." and never says what BRCA1 does in its first sentence
- Kind: answer
- Verdict: needs your eye
- What: at 1280 the first sentence in Researcher is "The encoded protein combines with other tumor suppressors, DNA damage sensors, and signal transducers to form a large multi-subunit protein complex known as the BRCA1-associated genome surveillance complex (BASC)." In Plain language it is "The protein it makes joins with other tumor suppressors...". Neither sentence names what "the encoded protein" belongs to. The fresh 390 runs opened well: "BRCA1 is a 190 kD nuclear phosphoprotein that maintains genomic stability and acts as a tumor suppressor..." (Researcher) and "BRCA1 is a gene that helps keep our DNA stable and acts as a tumor suppressor..." (Plain language). This fails rubric line 1 in 2 of the 4 runs.
- Evidence: `brca1_do_researcher_1280_fold.png` (read myself), `brca1_do_plain_1280.txt`. Compare `brca1_do_researcher_390.txt` and `brca1_do_plain_390.png`.
- Why a person would care: "I asked what BRCA1 does and the first line talks about 'the encoded protein' as if I already knew which one."
- From this card: no. Card 133 changes only the record rows. The summary sentences come from the gene summary, and choosing the first sentence is a separate path.
- NOT CLOSED

### PR-card133-03: Summary chips read 19 while the answer says 17 sources
- Kind: answer
- Verdict: needs your eye
- What: every summary sentence in the BRCA1 answers carries chip 19, but the Sources header and meta line say 17. By my count, chips 1, 2 and 19 all point to the one gene page, so 19 chips over 17 pages adds up. A reader cannot see that, though.
- Evidence: `brca1_do_researcher_1280_fold.png`, "...complex (BASC).19".
- Why a person would care: "It says 17 sources. Where is number 19?"
- From this card: no. Yesterday's check filed it as PR-answers-05 and PR-answers-12 (`testing/Developer/reports/2026-10-22_product_check_answers/report.md`).
- NOT CLOSED

### PR-card133-04: Query 24 totals agree at 23, and no gene is listed twice (pass)
- Kind: answer
- Verdict: pass, recorded so the owner sees what was checked
- What: in Plain language at both widths the list reads "Showing 1–10 of 23". The Sources header, "Based on 23 sources cited..." and the meta line "23 sources cited from 3 layers" agree. Paging through all three pages in a third run shows 23 rows, with MLH1 once ("mutL homolog 1 (MLH1)", chips 1 and 8) and MSH2 once ("mutS homolog 2", chip 5). The team's earlier runs read 24 against 23.
- Evidence: `q24_plain_1280.png`, `q24_plain_390_fold.png` (read myself), every page in `q24_plain_pages_1280.txt` and `q24_plain_pages_1280_p1.png` to `_p3.png`.
- Why a person would care: "Two genes, twenty-three sources, and the numbers match."
- From this card: yes. This is the fix.
- NOT CLOSED

### PR-card133-05: In query 24 MLH1 now shows its symbol but MSH2 does not
- Kind: answer
- Verdict: needs your eye
- What: the merged first-gene row reads "mutL homolog 1 (MLH1)". The second gene reads only "mutS homolog 2", with no "(MSH2)". Only the first gene gets the live lookup that brings in the symbol, so the two genes the person asked to compare are named in two different styles.
- Evidence: `q24_plain_pages_1280.txt`, page 1, rows 1 and 5.
- Why a person would care: "I asked about MLH1 and MSH2. I can see MLH1, but which row is MSH2?"
- From this card: partly. "mutS homolog 2" with no symbol was already there (`2026-09-29_retest/runner_A/results.md`). The mismatch beside the newly merged "mutL homolog 1 (MLH1)" comes from this card.
- NOT CLOSED

### PR-card133-06: Query 24 says it did not address colorectal cancer, while it lists a colorectal cancer record, and the summary never compares the two genes
- Kind: answer
- Verdict: needs your eye
- What: the note reads "Note: this answer does not address the following entities named in the question: Colorectal cancer." The same list shows "Colorectal cancer, hereditary nonpolyposis, type 2". The 1280 summary has two sentences, both about MLH1 only ("MLH1 was identified as a gene often mutated in hereditary nonpolyposis colon cancer."), and says nothing about MSH2. The first sentence lists what was found ("I found 2 genes and 5 conditions related to MLH1, MSH2 and colorectal cancer."). That fails rubric line 1 for a "Compare..." question.
- Evidence: `q24_plain_1280.txt` and `q24_plain_390_fold.png`.
- Why a person would care: "I asked for a comparison and got a paragraph about one gene, plus a note saying it skipped colorectal cancer."
- From this card: no. The same note appears in `2026-09-29_retest/runner_A/q24.txt`.
- NOT CLOSED

### PR-card133-07: Query 1 in Researcher lists each gene once and its counts agree at 21 (pass)
- Kind: answer
- Verdict: pass, recorded so the owner sees what was checked
- What: at both widths the gene table has one row, "BRCA1 | NCBIGene:672", with chips 5 and 9. The tables hold 4 diseases, 1 gene, 5 papers, 5 ClinVar, 1 OMIM and 5 trials, which is 21, matching the Sources header "21" and "Based on 21 sources cited". "Found 4 disease records for BRCA1" matches the 4 disease rows.
- Evidence: `q1_researcher_1280_fold.png` (read myself), `q1_researcher_1280.txt`, `q1_researcher_390.txt`.
- From this card: yes, no regression.
- NOT CLOSED

### PR-card133-08: Card 137 part 2 seen again: at 1280 the heading "Disease associations" sits over a fragment with no verb
- Kind: answer
- Verdict: needs your eye (observation only, not fixed tonight)
- What: at 1280, Researcher query 1 shows the heading "DISEASE ASSOCIATIONS" over "Familial cancer of breast and familial breast-ovarian cancer susceptibility 1." That is a noun phrase, not a sentence. This run did not show "DNA REPAIR PATHWAY DISEASE". The fresh 390 run showed "BIOLOGICAL PROCESSES" over a full sentence ("The graph links BRCA1 to double-strand break repair via homologous recombination...") and had no fragment. So 1 of 2 runs showed it.
- Evidence: `q1_researcher_1280_fold.png` (read myself), `q1_researcher_390.txt`.
- Why a person would care: "There's a heading and then half a sentence under it. Did something get cut off?"
- From this card: no. This is card 137 part 2, already known.
- NOT CLOSED

### PR-card133-09: Control: query 1 in Plain language reads as it did yesterday (pass)
- Kind: answer
- Verdict: pass
- What: both widths show "I found 4 conditions related to BRCA1.", the four conditions named in words, the gene row "BRCA1" with chips 5 and 9, "Showing 1–10 of 21" and Sources 21. This matches yesterday's control (`2026-10-22_product_check_answers/control_q1_brca1_plain_390.txt`). The opening varies between runs, as it did before. At 1280 it opens "Changes in this gene cause about 40% of inherited breast cancers..." ("this gene" comes before any gene is named). At 390 it opens on the count line.
- Evidence: `q1_plain_control_1280.txt`, `q1_plain_control_390.txt`.
- From this card: no change seen.
- NOT CLOSED

## Per query results

One run per row. Times are in seconds from the Search click. Horizontal overflow at 390 measured 0 on every run, and the 1280 runs also measured 0.

| Query | Mode | Width | First records | Done | Entry | Screenshot |
|---|---|---|---|---|---|---|
| What does BRCA1 do? | Researcher | 1280 | 6.0 | 10.3 | pass | `brca1_do_researcher_1280.png` |
| What does BRCA1 do? | Researcher | 390 | 4.4 | 7.9 | pass | `brca1_do_researcher_390.png` |
| What does BRCA1 do? | Plain language | 1280 | 5.0 | 8.0 | pass | `brca1_do_plain_1280.png` |
| What does BRCA1 do? | Plain language | 390 | 5.5 | 8.8 | pass | `brca1_do_plain_390.png` |
| What does BRCA1 do? (paging run) | Plain language | 1280 | not timed | 6.3 | pass, 17 rows | `brca1_do_plain_pages_1280_p1.png`, `_p2.png` |
| 24, MLH1 and MSH2 | Plain language | 1280 | 5.1 | 9.0 | pass | `q24_plain_1280.png` |
| 24, MLH1 and MSH2 | Plain language | 390 | 6.5 | 9.1 | pass | `q24_plain_390.png` |
| 24, MLH1 and MSH2 (paging run) | Plain language | 1280 | not timed | 9.4 | pass, 23 rows | `q24_plain_pages_1280_p1.png` to `_p3.png` |
| 1, BRCA1 diseases | Researcher | 1280 | 5.0 | 8.0 | pass | `q1_researcher_1280.png` |
| 1, BRCA1 diseases | Researcher | 390 | 9.3 | 12.1 | pass | `q1_researcher_390.png` |
| 1, control | Plain language | 1280 | 3.7 | 6.5 | pass | `q1_plain_control_1280.png` |
| 1, control | Plain language | 390 | 6.2 | 8.8 | pass | `q1_plain_control_390.png` |

- Every answer landed within 20 s. The slowest was 12.1 s.
- Query 24's entry passes: both genes' records are present, the Lynch and mismatch repair condition records are among the sources, and no line says a background search did not finish.
- Query 1's entry passes at both depths: diseases are named in words, the answer does not open on a broken sentence, and any note follows the answer.
- I read these myself: `brca1_do_researcher_1280_fold.png`, `brca1_do_plain_390.png`, `q1_researcher_1280_fold.png` and `q24_plain_390_fold.png`, and the saved page text of every run. I did not open the other full-page screenshots. Their verdicts rest on the page text only.

## What was not captured

- No golden consistency run. The brief asked for guest sessions only, with no accounts, and the run needs two signed-in accounts. Card 133 changes which record rows an answer shows, so it is an answer-path change. Under the procedure the golden run against the floor of 102 of 150 is still owed before this card counts as clear.
- No comparison against the design prototype. These cards change answer content, not layout, and no screen design changed. The 390 full-page screenshots show the fixed header and footer partway down the page. That comes from the full-page capture method, not from the app.
- Citation chip links were not opened, so it is not checked that each chip opens an ncbi.nlm.nih.gov page.
- One run per width per query. Variation between runs (PR-card133-02, PR-card133-08) is an observation, not a rate.
- Other answers named in the diagnosis (query 29, CFTR window; query 25, TP53 GEO; query 116, TP53 orthologs) were not run, because they were outside this brief.
