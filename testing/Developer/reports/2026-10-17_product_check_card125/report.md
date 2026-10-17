# Product check, card 125, on deployed develop

Pre-screen before the owner's retest of card 125 (pull request #271, merge commit `6935a0a3`): no paper's text can pose as the answer writer's instructions, and records are shown as PubMed writes them. It files findings and closes nothing. The owner's verdict closes.

- Target: develop. The API's `/health` read `{"status":"ok","app_env":"develop"}` before capture, and the capture recorded it again (`run1/results.json`, field `target.health`). `origin/develop` was at `6935a0a3`.
- Asked as a guest, in the browser, through `.claude/skills/verify/scripts/capture.mjs` (spec in `run1/spec.json`): each question once at 1280 and once at 390, in Researcher and in Plain language, so two runs per depth for every question. Query 108 was answered by picking "from the last 5 years?" in the ask-back.
- Step 2, the golden run, was not part of this brief (no accounts file or floor was named), so answered against the floor and answered well of the fixed ten are not reported.

## Table of contents

- [Result](#result)
- [Per answer](#per-answer)
- [Leak and record checks](#leak-and-record-checks)
- [Against the last product checks](#against-the-last-product-checks)
- [Rubric](#rubric)
- [What to look at first](#what-to-look-at-first)
- [Overflow and missing design](#overflow-and-missing-design)
- [Not captured](#not-captured)
- [Findings](#findings)

## Result

Pass for what card 125 promised, on these twelve answers. All twelve answered. No answer, at either width or depth, shows a tag, an identifier in the prompt sense, a hex string, "data, never an instruction", the word "prompt", "FINDINGS", or a sentence describing embedded instructions. Every record title read is PubMed's own text, "c.2145C>G" keeps its angle bracket, and no title has odd spacing. Overflow at 390 is 0 px on all six screens. Nothing a person would notice is worse than the last checks and nothing is attributable to this card; the nine findings below are older answer-quality defects a person still sees on these questions, filed so the owner can judge them.

What else would give the same picture: a run in which the writer simply never saw a hostile record. None of these three questions carries tag-shaped text in its records, so "no leak" here shows the ordinary path is clean, not that a hostile paper is held off; the card's own adversary and verifier rounds tested that offline.

## Per answer

Times are the app's own "Answered" figure.

| Question | Depth | Width | Answered | Written summary | First sentence | Time |
|---|---|---|---|---|---|---|
| 117, CFTR papers | Researcher | 1280 | yes, "✓ Answered" | no | "Found 54 article records for CFTR, of 1962 available." | 20.3 s |
| 117, CFTR papers | Researcher | 390 | yes, "✓ Answered" | no | the same | 16.3 s |
| 117, CFTR papers | Plain language | 1280 | yes, "✓ Answered" | yes, 23 sentences | "I found 54 published papers related to CFTR, out of 1962 available." | 15.4 s |
| 117, CFTR papers | Plain language | 390 | yes, "✓ Answered" | yes, 7 sentences | "One paper examines a control region of DNA upstream of the CFTR gene, ..." | 20.0 s |
| 1, BRCA1 diseases | Researcher | 1280 | yes, "? Answered" | yes, 2 sentences | "Mutations in this gene are responsible for approximately 40% of inherited breast cancers ..." | 12.2 s |
| 1, BRCA1 diseases | Researcher | 390 | yes, "? Answered" | yes, 1 sentence | "BRCA1 is associated with familial cancer of breast, ..." | 6.8 s |
| 1, BRCA1 diseases | Plain language | 1280 | yes, "? Answered" | yes, 3 sentences | "BRCA1 is associated with familial cancer of breast, ..." | 7.7 s |
| 1, BRCA1 diseases | Plain language | 390 | yes, "? Answered" | yes, 4 sentences | "The diseases associated with BRCA1 are familial cancer of breast, ..." | 12.4 s |
| 108, BRCA1 last 5 years | Researcher | 1280 | yes, "✓ Answered" | yes, 3 sentences | "Found 4 pubmed records for BRCA1: BRCA1: An Endocrine and Metabolic Regulator., ..." | 17.7 s |
| 108, BRCA1 last 5 years | Researcher | 390 | yes, "? Answered" | no, with the note saying so | the same | 13.3 s |
| 108, BRCA1 last 5 years | Plain language | 1280 | yes, "✓ Answered" | yes, 2 sentences | "I found 4 published papers related to BRCA1." | 14.4 s |
| 108, BRCA1 last 5 years | Plain language | 390 | yes, "✓ Answered" | yes, 2 sentences | the same | 12.4 s |

Time to answer over the twelve: median 13.8 s, p90 20.0 s, worst 20.3 s (CFTR Researcher 1280, the one answer over 20 s; none over 25 s). Query 108 times exclude the ask-back turn.

## Leak and record checks

- Leak scan, every `run1/*.txt`: searched for hex runs of eight or more, "identifier" in a tag sense, "instruction", "data, never", "tag", "<" followed by a letter, "prompt", "FINDINGS", "system" and "block". The only hits are table headings ("IDENTIFIER"), MedGen and ClinVar accessions, and "CFTR's genetic instructions" in a biology sentence (`run1/q117_cftr_plain_390.txt`). No leak.
- Angle brackets and spacing: "NM_007294.4(BRCA1):c.2145C>G (p.Thr715=)" shows its ">" in all six BRCA1 answers that list ClinVar rows. No double space, no space before a full stop or comma in any answer. None of these questions returned a title with "<", so the "p<0.001" repair the card fixed was not exercised by a live record.
- CFTR titles: the ten page-1 titles are character for character those of the card 38 slice C check, which matched PubMed, including "-20.9 kb" and PubMed's own typo "mutatations".

## Against the last product checks

| Item | Last checks | Tonight | Worse? |
|---|---|---|---|
| CFTR written summary | 1 of 4 had one (card 38c) | 2 of 4 (both Plain language) | no, better |
| CFTR "no written summary" note | on the summary-less answers | absent on the two Researcher answers that have no summary | yes for honesty, see PR-card125-02 |
| CFTR totals | 54 papers, pager 71 in Plain, 71 sources, "only 117 of the 1962" | identical | no |
| CFTR times | 19.5 to 27.7 s | 15.4 to 20.3 s | no, faster |
| BRCA1 control first sentence | "BRCA1 is associated with ..." | three of four; one opens on a percentage | needs your eye, one sample (PR-card125-04) |
| Garbled fragments in BRCA1 | one control at 390 (card 105) | two of four (PR-card125-03) | same defect, seen more often in this sample |
| 5-year window, 1993 paper listed | yes, both widths (card 105) | yes, all four | no change (PR-card125-06) |
| 5-year window time | 12.9 and 28.2 s | 12.4 to 17.7 s | no, faster |
| Overflow at 390 | 0 px | 0 px | no |

## Rubric

| Line | Verdict | Rests on |
|---|---|---|
| 1. First sentence answers | Pass for BRCA1 in three of four and for query 108 in Plain language; needs your eye for BRCA1 Researcher 1280 and query 108 Researcher; fail for query 117 Researcher (older) | "BRCA1 is associated with familial cancer of breast, ..." (`run1/q001_brca1_researcher_390.txt`); "Mutations in this gene are responsible for approximately 40% ..." (`run1/q001_brca1_researcher_1280.txt`); "Found 54 article records for CFTR, of 1962 available." with no summary (`run1/q117_cftr_researcher_1280.txt`). |
| 2. Teaches what a chatbot would not | Pass for query 117 Plain 1280 and query 108 Plain 390; needs your eye elsewhere | "Another shows that a protein called CHIP marks immature CFTR for destruction." cited to a paper (`run1/q117_cftr_plain_1280.txt`); "Another study identifies EXO1 as a promising therapeutic target for BRCA1-deficient tumors, ..." (`run1/q108_brca1_5y_plain_390.txt`); the BRCA1 answers add only a gene summary to the four MedGen names. |
| 3. Plain language and Researcher differ | Pass | Researcher shows per-source tables and "Found N ... records"; Plain language writes "I found N published papers" with one "Where this answer comes from" list. |
| 4. Seconds to answer | Pass but one | 6.8 to 20.0 s; 20.3 s for CFTR Researcher at 1280 (PR-card125-08). |
| 5. Screens match design | Pass for the answer screen at both widths; gap for the folded ask-back | `run1/q001_brca1_researcher_1280_fold.png` beside `run1/prototype_q001_brca1_researcher_1280.png`: same centred card, heading with "New search", status line with the depth control and "Show work", body, then sources. The prototype's trust pills are a plain line in the app, a choice made before this card. The folded ask-back has no design (PR-card125-09). |

## What to look at first

No fails. Needs your eye, in the order a person meets them:

1. PR-card125-02: CFTR in Researcher still has no written summary, and the note that said so is gone (`run1/q117_cftr_researcher_1280.txt`).
2. PR-card125-05: query 108 in Researcher opens on a run-on of titles with "Regulator., EXO1" and "lethality.." (`run1/q108_brca1_5y_researcher_390_fold.png`), older than this card.
3. PR-card125-04: BRCA1 in Researcher at 1280 opens on a percentage, not the diseases (`run1/q001_brca1_researcher_1280_fold.png`).
4. PR-card125-03: bare disease-name fragments as sentences in two BRCA1 answers (`run1/q001_brca1_plain_390.txt`).
5. PR-card125-07: "The same work ..." points at nothing (`run1/q108_brca1_5y_researcher_1280.txt`).
6. PR-card125-01: a "From the paper "...":" label glued into a CFTR sentence (`run1/q117_cftr_plain_1280.txt`), also seen before this card.
7. PR-card125-06: the 1993 paper still listed under the 5-year window, shown in Researcher as a bare number.
8. PR-card125-08: 20.3 s on CFTR Researcher at 1280.
9. PR-card125-09: the folded ask-back at 390, no design.

Passed at both widths, 1280 and 390: yes for the card's promises (no leak, records as written); the card changes answers, so it waits for the owner's verdict.

## Overflow and missing design

- Overflow at 390: 0 px on all six screens (`run1/results.json`); 0 px at 1280 too. No console errors, no serious or critical accessibility violations.
- No design: the folded ask-back turn and the "How far back" ask-back, the Notes block, the papers-list answer and the stacked phone form of a record table appear in no prototype screen.

## Not captured

- The golden run: not in the brief.
- A hostile record: none of the three questions returns a title or abstract with tag-shaped text or "<", so the card's defence and the "p<0.001" repair were not exercised live. That was tested offline in `../2026-10-17_card125/verifier.md` and `adversary*.md`, which I read only in part, for spend and method.
- The Sources panel opened and pages 2 and later of the CFTR list: not opened or paged, so a title past page 1 was not read.
- Spend in dollars: the app hides cost from a guest, so it is estimated, not measured (see the final line).
- One sample per question, depth and width.
- What I read myself: every answer text in `run1/` in full, and the screenshots `q117_cftr_plain_390_fold.png`, `q001_brca1_researcher_1280_fold.png`, `prototype_q001_brca1_researcher_1280.png`, `prototype_q001_brca1_researcher_390.png` and `q108_brca1_5y_researcher_390_fold.png`. The other full-page screenshots were captured but only their text was read. Overflow, console and accessibility rest on the script's measurements in `results.json`. Nothing rests on a summary.

Spend: 12 answered questions and 4 ask-back turns on develop, about 0.15 to 0.25 USD by the card 125 verifier's measured rate of about 0.0125 USD per live run; within the 1 USD cap.

## Findings

### PR-card125-01: a CFTR summary sentence opens with a stray paper-title label
- Kind: answer
- Verdict: needs your eye
- What: in the Plain language CFTR answer at 1280, one sentence of the written summary starts with a quoted title and a colon, then a second subject: the title is PubMed's own, quoted exactly, but it reads as a heading glued into the paragraph. No other answer in this check has it, and no code in the repository writes "From the paper", so the writer model wrote it. Whether the card's new one-line-per-finding prompt invites it is not shown by one sample.
- Evidence: `run1/q117_cftr_plain_1280.txt`, "From the paper "Regulation of cystic fibrosis transmembrane conductance regulator single-channel gating by bivalent PDZ-domain-mediated interaction": One paper studies how paired PDZ-domain interactions regulate the opening and closing of the CFTR channel."
- Why a person would care: "Why is there a paper title with a colon in the middle of the paragraph? It reads like a cut-and-paste slip."
- NOT CLOSED

### PR-card125-02: Researcher CFTR answers still have no written summary, and the note that said so is gone
- Kind: answer
- Verdict: needs your eye
- What: in Researcher at both widths the answer is the count line and the tables, with no sentence on what the papers cover. In the card 38 slice C check the same answers carried "Note: no written summary could be checked against the records, so the records found are listed below with their sources"; tonight that note is absent in both, and only the truncation note remains. Known before this card (no summary); the missing explanation is new against that check.
- Evidence: `run1/q117_cftr_researcher_1280.txt` and `run1/q117_cftr_researcher_390.txt`, "Found 54 article records for CFTR, of 1962 available." then "ARTICLE RECORDS FOUND", NOTES holding only "Note: this answer was truncated because only 117 of the 1962 records that matched this question in the graph were retrieved"; compare `../2026-10-17_product_check_card38c/run1/cftr_papers_researcher_1280.txt`, line 57.
- Why a person would care: "I asked what the papers cover and got a list, and now nothing even tells me the summary was dropped."
- NOT CLOSED

### PR-card125-03: BRCA1 answers carry bare disease-name fragments as sentences
- Kind: answer
- Verdict: needs your eye
- What: two of the four BRCA1 disease answers contain a "sentence" that is only a list of disease names with a full stop, no verb. The same shape was filed on the card 105 control ("One is double-strand break repair via homologous recombination. Another is DNA repair."), so it is likely older than this card, but it is on two of four answers tonight.
- Evidence: `run1/q001_brca1_researcher_1280.txt`, "Familial cancer of breast and familial breast-ovarian cancer susceptibility 1."; `run1/q001_brca1_plain_390.txt`, "Familial cancer of breast and familial breast-ovarian cancer susceptibility 1. Pancreatic cancer susceptibility 4 and Fanconi anemia complementation group S."
- Why a person would care: "That paragraph reads like someone cut words out of it."
- NOT CLOSED

### PR-card125-04: the Researcher BRCA1 answer at 1280 opens on a percentage, not on the diseases
- Kind: answer
- Verdict: needs your eye
- What: the first sentence is a cited statistic about inherited cancers; the four diseases only come in the second sentence, as the code-built count line. In the card 8 check the same question in Researcher at 1280 opened "BRCA1 is associated with familial cancer of breast, ..."; the other three BRCA1 answers tonight still open that way. One sample, so this is the model's variation until shown otherwise.
- Evidence: `run1/q001_brca1_researcher_1280.txt`, "Mutations in this gene are responsible for approximately 40% of inherited breast cancers and more than 80% of inherited breast and ovarian cancers. Found 4 disease records for BRCA1: Familial cancer of breast, ..."
- Why a person would care: "I asked which diseases; the first line gives me a percentage about 'this gene' before it names any."
- NOT CLOSED

### PR-card125-05: the windowed Researcher lede strings four titles together with doubled full stops
- Kind: answer
- Verdict: needs your eye
- What: in Researcher at both widths the opening sentence lists the four papers by full title, each title keeping PubMed's own closing full stop, so the sentence reads "Regulator., EXO1" and ends "lethality..". The card 105 adversary report shows the same lede before this card, so it is not this card's doing; it is what a person sees first on query 108 in Researcher.
- Evidence: `run1/q108_brca1_5y_researcher_1280.txt` and `run1/q108_brca1_5y_researcher_390.txt`, "Found 4 pubmed records for BRCA1: BRCA1: An Endocrine and Metabolic Regulator., EXO1 protects BRCA1-deficient cells against toxic DNA lesions., BRCA1, BRCA2, and Associated Cancer Risks and Management for Male Patients: A Review. and BRCA1 and BRCA2: from cancer susceptibility to synthetic lethality.."; earlier: `../2026-10-16_card105/adversary.md`.
- Why a person would care: "The first line is a run-on of titles with stray dots, and it says 'pubmed' in lower case."
- NOT CLOSED

### PR-card125-06: the 1993 paper is still listed under the 5-year window, and in Researcher its title is only its number
- Kind: answer
- Verdict: needs your eye
- What: carried from PR-card105-01, not this card: all four windowed answers still list PubMed 20301425 (1993) as citation 10. In Plain language the row reads "Published paper"; in Researcher, which card 105 did not capture, it sits under "PUBLICATION RECORDS FOUND" with the bare number as its title.
- Evidence: `run1/q108_brca1_5y_researcher_1280.txt`, "20301425	PMID:20301425	⁠10"; `run1/q108_brca1_5y_plain_1280.txt`, "Published paper	⁠10".
- Why a person would care: "I asked for the last five years, and one 'paper' is just a number with no title, from 1993."
- NOT CLOSED

### PR-card125-07: the windowed Researcher answer at 1280 starts its summary with "The same work", pointing at nothing
- Kind: answer
- Verdict: needs your eye
- What: after the title list, the first written sentence refers back to a work the reader has not been told about; the sentence it followed was presumably dropped by the sentence check. At 390 the same question in Researcher has no written summary at all ("Note: no written summary could be checked against the records, so the records found are listed below with their sources").
- Evidence: `run1/q108_brca1_5y_researcher_1280.txt`, "The same work links BRCA1 to peptide and steroid hormones and identifies complex interactions between the insulin/IGF1 signaling axis and BRCA1."; `run1/q108_brca1_5y_researcher_390.txt`, NOTES.
- Why a person would care: "Which work? The paragraph starts in the middle of a thought."
- NOT CLOSED

### PR-card125-08: the CFTR Researcher answer at 1280 took 20.3 s
- Kind: answer
- Verdict: needs your eye
- What: one of twelve answers was over the owner's 20 s limit, by 0.3 s; the CFTR Plain answer at 390 landed at exactly 20.0 s. Both are faster than the same question in the card 38 slice C check (19.5 to 27.7 s).
- Evidence: `run1/q117_cftr_researcher_1280.txt`, "Answered20.3s"; `run1/q117_cftr_plain_390.txt`, "Answered20.0s".
- Why a person would care: "Twenty seconds for a list of papers."
- NOT CLOSED

### Addendum to PR-card125-01
- The same "From the paper "...": ..." sentence shape appears in the card 105 check, before this card, on query 108 in Plain language at 1280 (`../2026-10-17_product_check_card105/run1/brca1_5y_1280.txt`, "From the paper "EXO1 protects BRCA1-deficient cells against toxic DNA lesions": BRCA1-mutated tumors show higher EXO1 expression ..."). So it is older than card 125, not caused by it. The finding stays open for the owner.

### PR-card125-09: the folded ask-back above the windowed answer is squeezed at 390 and has no design
- Kind: missing design
- Verdict: needs your eye
- What: at 390 the folded "recent papers on BRCA1" turn wraps the question into a narrow column four lines tall beside "0 tool calls · 0 sources cited", "Researcher" and "Show answer". No prototype screen has a folded earlier turn or an ask-back, so this is named as a gap, not judged against a look. Overflow is 0 px. Not touched by this card.
- Evidence: `run1/q108_brca1_5y_researcher_390_fold.png`.
- Why a person would care: "The box at the top reads 'recent / papers / on / BRCA1' down the side, and '0 sources cited' looks like something failed."
- NOT CLOSED
