# Product check, card 37 slice A1, on deployed develop

Pre-screen before the owner's retest of card 37 slice A1 (pull request #262, merge commit `655e9dfe`). It files findings and closes nothing. The owner's verdict closes.

- Target: develop. The API's `/health` read `{"status":"ok","app_env":"develop"}` before capture, and the capture recorded `app_env` develop and deployed commit `655e9dfe` (`run1/results.json`).
- Asked as a guest, in the browser, each question once at 1280 and once at 390: 8 questions, the spend cap.
- Step 2, the golden run, was skipped: the owner chose "No, test queries only" for tonight (DECISIONS.md, 2026-10-16).
- Capture: `.claude/skills/verify/scripts/capture.mjs`, spec in `run1/spec.json`. Every verdict below rests on an answer text (`run1/*.txt`) I read in full, or on a screenshot I opened myself, named where used.

## Table of contents

- [Result](#result)
- [Per answer](#per-answer)
- [Rubric](#rubric)
- [What to look at first](#what-to-look-at-first)
- [Overflow and missing design](#overflow-and-missing-design)
- [Not captured](#not-captured)
- [Findings](#findings)

## Result

Card 37 slice A1 passes at both widths, 1280 and 390, on what it promised. rs334's record is called rs334 and never by the list of classification words; in Researcher its row shows HBB and a column of its own headed "Clinical significance"; the mixed question heads its column "Clinical significance or consequence" and each cell starts "significance:" or "consequence:"; Plain language reads "Genetic variant (HBB), clinical significance: ...". Horizontal overflow is 0 px on all eight captures.

Beside the pass, two fails a person will see first: the Researcher text reads "Found 1 variant record record" and "Variant record records found" (PR-card37-01), and rs334 still never names sickle cell disease (PR-card37-02). The RS1 control lists off-topic papers among its sources (PR-card37-06); these captures cannot say whether that is new.

Golden result: not run tonight (owner's decision). Answered against the floor, and answered well of the fixed ten, are not reported.

## Per answer

| Question | Mode | Width | Record rows as shown | Trust line | Time |
|---|---|---|---|---|---|
| Query 23, rs334 | Researcher | 1280 | Variant rs334, Identifier rs334, Gene HBB, Clinical significance "not-provided, protective, likely-benign, pathogenic, other" | "? Answered"; "Based on 1 source cited, not yet confirmed · High-risk claim" | 7.7 s |
| Query 23, rs334 | Researcher | 390 | Stacked, unlabelled: "rs334", "rs334", "HBB", "not-provided, protective, likely-benign, pathogenic, other" | same | 11.0 s |
| Query 23, rs334 | Plain language | 1280 | "Genetic variant (HBB), clinical significance: not-provided, protective, likely-benign, pathogenic, other" | same | 6.1 s |
| Query 23, rs334 | Plain language | 390 | same text | same | 13.8 s |
| rs334 and rs6025 | Researcher | 1280 | Head "Clinical significance or consequence"; rs334, rs334, HBB, "significance: not-provided, protective, likely-benign, pathogenic, other"; rs6025, rs6025, F5, "consequence: coding_sequence_variant, missense_variant" | "? Answered"; "Based on 2 sources cited, not yet confirmed · High-risk claim" | 12.4 s |
| rs334 and rs6025 | Researcher | 390 | Same values stacked, no column labels | same | 12.1 s |
| RS1 gene, control | Plain language | 1280 | Ten of 19 records: "retinoschisin 1", "RS1", an IQUB radial spoke 1 paper, two RS1 ClinVar variants, OMIM entries, an RS1 gene transfer trial, a viral ADP-ribosyltransferase paper | "✓ Answered"; "Sources disagree on at least one claim" | 10.0 s |
| RS1 gene, control | Plain language | 390 | same ten | same | 6.4 s |

Times are the app's own "Answered" figure. Median 10.5 s, worst 13.8 s; none over the owner's 20 s target or over 25 s. The control was asked in Plain language; the brief named no mode for it.

## Rubric

| Line | Verdict | Rests on |
|---|---|---|
| 1. First sentence answers | Fail for rs334 (all four), needs your eye for RS1 | rs334: "Found 1 variant record record for rs334: rs334." and "I found 1 genetic variant related to rs334." RS1: "The protein is assembled and secreted from photoreceptors and bipolar cells as a homo-oligomeric protein complex." comes before the disease sentence. |
| 2. Teaches what a chatbot would not | Fail for rs334, needs your eye for the mixed table, pass for RS1 | rs334 names no condition. rs6025 shows only "consequence: coding_sequence_variant, missense_variant". RS1: "Mutations in this gene cause X-linked retinoschisis", cited, with ClinVar variants and a gene transfer trial. |
| 3. Plain language and Researcher differ | Pass | Plain: "I found 1 genetic variant related to rs334." with the row "Genetic variant (HBB), clinical significance: ..."; Researcher: "Found 1 variant record record for rs334" with a four-column table. |
| 4. Seconds to answer | Pass | 6.1 s to 13.8 s. |
| 5. Screens match design | Pass at 1280, needs your eye at 390 | `run1/q23_rs334_researcher_1280.png` beside `run1/prototype_q23_rs334_researcher_1280.png`: the table sits inside the answer card, bordered, uppercase heads, as the prototype's result table. At 390 the live table stacks without labels where the prototype scrolls sideways (`run1/rs334_rs6025_researcher_390.png`, `run1/prototype_q23_rs334_researcher_390.png`). |

## What to look at first

1. Fail, PR-card37-01: "Found 1 variant record record" and "Variant record records found" in every Researcher answer (`run1/q23_rs334_researcher_1280.png`).
2. Fail, PR-card37-02: rs334 never names sickle cell disease (`run1/q23_rs334_plain_1280.txt`), carried over from PR-card30-03.
3. Fail, PR-card37-06: the RS1 answer lists a radial spoke 1 paper and a viral enzyme paper as sources (`run1/rs1_gene_control_390_fold.png`).
4. Needs your eye, PR-card37-08: at 390 the record rows lose their column labels (`run1/rs334_rs6025_researcher_390.png`).
5. Needs your eye, PR-card37-04: rs6025 (Factor V Leiden) shows only raw consequence terms (`run1/rs334_rs6025_researcher_1280.png`).
6. Needs your eye, PR-card37-07: the RS1 answer opens "The protein is..." and counts 18, 19 and 20 sources.
7. Needs your eye, PR-card37-03: the note says "listed below" for records above it.
8. Needs your eye, PR-card37-05: follow-ups on a variant ask "What variants cause it?".
9. Needs your eye, PR-card37-09: Variant and Identifier columns repeat; the design itself overflows at 390.

## Overflow and missing design

- Overflow at 390: 0 px on all four live screens (`run1/results.json`). The prototype's rs334 answer overflows by 322 px at 390.
- No design: the Notes list, the "not yet confirmed" trust text and the stacked phone form of a record table appear in no prototype screen. The result table is designed only inside `prototype/app.html`, as a three-column genotype table.

## Not captured

- The golden run: skipped by the owner's decision.
- The prototype for the other three questions: it has no canned answer for them, so only the rs334 prototype answer was captured, at both widths.
- Screenshots I opened myself: rs334 Researcher at 1280, rs334 Plain language at 390, the mixed table at 1280 and 390, the prototype at 1280 and 390, and the RS1 first screen at 390. Every other verdict rests on the saved answer text, read in full, not on a screenshot or a summary.
- Each question once per width: one sample each, so a pass here is not proof of stability.
- The RS1 control in Researcher, and Plain language for the mixed question: outside the 8-question cap.

## Findings

### PR-card37-01: the Researcher lede and heading say "record record" and "Variant record records"
- Kind: answer
- Verdict: fail
- What: in Researcher at both widths the first sentence reads "Found 1 variant record record for rs334: rs334." and the table heading reads "VARIANT RECORD RECORDS FOUND".
- Evidence: run1/q23_rs334_researcher_1280.txt, run1/q23_rs334_researcher_390.txt
- Why a person would care: "The very first line has a typo in it. If it cannot write its own sentence, why trust the record?"
- NOT CLOSED

### PR-card37-02: rs334 still never names the condition the question asks for
- Kind: answer
- Verdict: fail
- What: asked "What is rs334 and what condition is it associated with?", all four answers (both modes, both widths) give no written answer. Researcher opens "Found 1 variant record record for rs334: rs334."; Plain language opens "I found 1 genetic variant related to rs334." Neither names sickle cell disease or sickle cell trait anywhere. Each carries "Note: no written summary could be checked against the records, so the records found are listed below with their sources". The same fail was filed as PR-card30-03 on 2026-10-16; card 37 slice A1 fixes the record's name, not this.
- Evidence: run1/q23_rs334_researcher_1280.txt, run1/q23_rs334_researcher_390.txt, run1/q23_rs334_plain_1280.txt, run1/q23_rs334_plain_390.txt
- Why a person would care: "I asked which condition. It showed me a row of classification words. Any chatbot says sickle cell."
- NOT CLOSED

### PR-card37-03: the note says the records are "listed below" when they sit above it
- Kind: answer
- Verdict: needs your eye
- What: in all four rs334 answers the record row comes first and the note after it reads "the records found are listed below with their sources". Below the note are only the folded Sources list and the trust line.
- Evidence: run1/q23_rs334_plain_1280.txt, run1/q23_rs334_researcher_1280.txt
- Why a person would care: "Below where? I scroll down and find nothing new."
- NOT CLOSED

### PR-card37-04: rs6025, Factor V Leiden, shows no clinical significance, only "coding_sequence_variant, missense_variant"
- Kind: answer
- Verdict: needs your eye
- What: in the mixed table at both widths the rs6025 row reads "rs6025 | rs6025 | F5 | consequence: coding_sequence_variant, missense_variant". The column head "Clinical significance or consequence" and the "significance:" and "consequence:" prefixes work as the card promised. But rs6025 is the Factor V Leiden variant, and the answer never says it is linked to a clotting risk; the consequence values are shown as raw snake_case database terms.
- Evidence: run1/rs334_rs6025_researcher_1280.txt, run1/rs334_rs6025_researcher_390.txt
- Why a person would care: "Factor V Leiden is one of the best-known risk variants there is. Showing only 'missense_variant' reads as if nobody has classified it."
- NOT CLOSED

### PR-card37-05: the follow-up suggestions on a variant question ask "What variants cause it?"
- Kind: answer
- Verdict: needs your eye
- What: all six variant answers (rs334 in both modes, the mixed table) offer the follow-ups "What variants cause it?", "Which trials are recruiting?", "What does the literature add?". The question was already about a variant.
- Evidence: run1/q23_rs334_researcher_1280.txt, run1/rs334_rs6025_researcher_1280.txt
- Why a person would care: "I asked about a variant and it suggests I ask which variants cause it. Cause what?"
- NOT CLOSED

### PR-card37-06: the RS1 gene answer lists papers about "radial spoke 1" and a viral enzyme among its sources
- Kind: answer
- Verdict: fail
- What: the RS1 control (Plain language) at both widths lists, among its first ten records, "Differential requirements of IQUB for the assembly of radial spoke 1 and the motility of mouse cilia and flagella." (record 3) and "A viral ADP-ribosyltransferase attaches RNA chains to host proteins." (record 7). Neither is about the retinoschisin gene. "RS1" here matched the abbreviation for radial spoke 1. These captures cannot say whether this predates card 37; the control's gene facts themselves are right and unchanged in kind.
- Evidence: run1/rs1_gene_control_1280.txt, run1/rs1_gene_control_390.txt
- Why a person would care: "A paper about mouse sperm flagella is listed as a source for an eye disease gene. Now I have to check every other source too."
- NOT CLOSED

### PR-card37-07: the RS1 answer opens "The protein is assembled..." before saying which protein, and its counts disagree
- Kind: answer
- Verdict: needs your eye
- What: the first sentence at 1280 is "The protein is assembled and secreted from photoreceptors and bipolar cells as a homo-oligomeric protein complex.", followed by "I found 1 gene related to RS1." The disease sentence that answers "what does it do" comes second. The meta line says "18 sources cited", the pager says "Showing 1–10 of 19", and both claims cite marker 20. Record 6 drops an apostrophe: "People s Expectations".
- Evidence: run1/rs1_gene_control_1280.txt, run1/rs1_gene_control_390.txt
- Why a person would care: "Which protein? And is it 18, 19 or 20 sources?"
- NOT CLOSED

### PR-card37-08: at 390 the record table becomes stacked rows with no column labels
- Kind: screen
- Verdict: needs your eye
- What: at 390 each record is a block of four unlabelled lines, for example "rs334", "rs334", "HBB", "significance: not-provided, protective, likely-benign, pathogenic, other". The headings "Variant", "Identifier", "Gene" and "Clinical significance" shown at 1280 are not shown. The significance line keeps its "significance:" or "consequence:" prefix only in the mixed table; in the rs334-only answer the line is bare. The prototype instead keeps the table and scrolls it sideways inside its box (`.rtab{display:block;overflow-x:auto}` at 720px). Page overflow is 0 px, so nothing spills off the phone.
- Evidence: run1/rs334_rs6025_researcher_390.png, run1/q23_rs334_researcher_390.txt, run1/prototype_q23_rs334_researcher_390.png
- Why a person would care: "On my phone I see 'HBB' and a list of words with no label. Is that the gene? Is that the classification?"
- NOT CLOSED

### PR-card37-09: the design's own rs334 answer overflows by 322 px at 390, and the live Variant and Identifier columns repeat each other
- Kind: screen
- Verdict: needs your eye
- What: the prototype's rs334 answer measured 322 px of horizontal overflow at 390 (results.json, prototype_overflow_px), so at that width the design is not a clean reference. Separately, at 1280 the live table shows "rs334" in both the Variant and the Identifier column, and "rs6025" in both for the mixed table.
- Evidence: run1/results.json, run1/prototype_q23_rs334_researcher_390.png, run1/q23_rs334_researcher_1280.png
- Why a person would care: two columns saying the same thing take room from the one column a reader came for, the significance.
- NOT CLOSED

