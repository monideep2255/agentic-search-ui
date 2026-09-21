# Live check of sets 8 and 9 on develop, 2026-09-14

Commit `537377d`, both Railway services SUCCESS. Checked with `live_check.mjs` (this folder) against the develop web app at 1280 and 390 wide, as a guest. Screenshots and `results.json` are beside this file.

## What worked

- The scientist handoff shows during Act: "Levi-Montalcini is handing off to Chain, Salk and Nightingale", then one line per layer with its L1, L2 or L3 badge and an info control. The helpers differed on every run, and the lead stayed the same.
- The plan narrative names the three layers and four tools. All four tools ran and returned rows.
- Plain language is the default and ends with "This is a research summary, not medical advice." Researcher does not.
- One trust line under the answer, for example "Based on 4 sources, not yet confirmed" with "High-risk claim" in red. No pills.
- Every claim and list row carried a citation chip (0 without a marker in all four answers).
- Researcher GCK: 4 group headings, 20 list rows, bold variant names, trial and literature citations named `clinicaltrials.gov NCT…` and `ncbi_gene @GENE_GCK`.
- No sideways scroll at 390 or 1280.
- The follow-up "What variants cause it?" answered about BRCA1, citing 20 sources from 3 layers.

## Defects found

1. BRCA1 diseases question, Plain language: the prose answers a different question. It is about clinical trials ("There is a trial called Study to Evaluate Treatment Customized According to RAP80…"), or opens "The gene symbol BRCA1 and the literature entity name BRCA1." The four diseases appear only in the code-built record lines as "Disease name: Familial cancer of breast." Likely cause: findings reach the answer writer ordered Layer 2, Layer 3, Layer 1 (set 8), so trials lead the prompt. Seen at both widths.
2. GCK Researcher: no summary paragraph. The prose restates records one by one ("SequenceVariant ClinVar:1028584 is named …"), four sentences read "… has a source URL of https://www.ncbi.nlm.nih.gov/clinvar/variation/…", and the same variants repeat in the code-built list below.
3. Not observed live: an answer sentence appearing while Stop was still visible on a first question. The check polls every 0.7 seconds and the write step takes a few seconds, so this is unproven either way live; the browser spec's Stop-mid-stream arm proves it against the mock model.
4. Not observed live: the mode lock marker, which the check looked for once, 1.5 seconds after Search. Unproven live; covered by unit tests.

Raw `MedGen:C…` codes appear only inside citation chips (the record id), not in answer words.

5. `flagship_measure.py 5` against `537377d` (log beside this file): 22 of 25 answered. Every question kept one distinct source set. Three runs ended in a fatal error with no answer: "What variants cause disease in BRCA1?" 1 of 5 and "Which diseases are associated with BRCA1 and BRCA2?" 2 of 5. A reproduction hit it 2 of 5 more times. All four tools returned `ok`, then the write step failed with `error_class: transient` at 49 to 53 seconds in total. The write step's budget is 45 seconds (`_TIER_STEP_BUDGET_S["synth"]`), and a killed step is reported as transient. Successful runs took 38 to 52 seconds, so the write step is running at its ceiling. Leading hypothesis: the Researcher directive asks for about 700 words while grounding keeps about 200, so most of the Synth time buys text that is then stripped. Railway's log stream shows no request-level logs, so the traceback could not be read remotely. Handed to the same fix agent, with raising the budget ruled out unless the product owner decides it.

## After the answer-quality fix, commit `674b7b9`

Same script, same questions, results and screenshots in `after_674b7b9/`.

- BRCA1 diseases, Plain language, at 1280 and 390: the answer opens "Found 4 disease records for BRCA1: Familial cancer of breast, Familial breast-ovarian cancer susceptibility 1, Pancreatic cancer susceptibility 4 and Fanconi anemia complementation group S." with four citations, the model's disease sentence follows, and the trials come after the note. Every claim cited, trust line and medical-advice line present, no sideways scroll. Remaining roughness: the second sentence repeats the four names.
- Follow-up "What variants cause it?": opens "Found 13 sequence variant records for BRCA1, of 15310 available." with 20 sources from 3 layers. Remaining roughness: in Plain language the records the prose left out still read as "SequenceVariant ClinVar:1000183, name: NM_007294.4(BRCA1):c.4709T>C (p.Leu1570Pro)." lines, cited but stiff.
- GCK, Researcher: opens "Found 13 sequence variant records for **GCK**, of 1333 available.", then grouped headings (sequence variant, gene, literature entity, clinical trial records found) with a cited bulleted list; every variant row reads as its HGVS name, none as a URL. This matches the reference screenshot's shape except for model-written topic prose, which grounding strips.
- No "has a source URL of" sentence in any answer; 0 claims without a marker in all four.
- `flagship_measure.py 5` against `674b7b9` (`after_674b7b9/flagship_measure_674b7b9.log`): 25 of 25 answered, one distinct source set per question (BRCA1 diseases 11, BRCA1 variants 20, GCK 20, BRCA1 and BRCA2 20, lowercase brca1 11), no write-step error, 13 to 71 seconds. Before the fix the same measurement was 22 of 25 with three write-step errors. The error is not proven gone: its measured cause (the Synth tier's reasoning effort "low" occasionally running out the 45-second step) is unchanged, and the shorter directives made each Synth call shorter, which is the likely reason none fired in these 25 runs.

## After quieter citations, the writing state and the speed fix, commit `2b6d274`

Same script and questions, results and screenshots in `after_2b6d274/`. Both Railway services reached SUCCESS.

- Citations render as small raised numbers in the layer colour on every answer. The BRCA1 summary sentence carries one "1–4" marker, and the GCK summary one "1–13" marker. No boxed chips remain.
- BRCA1 diseases, Plain language, at 1280 and 390: opens on "Found 4 disease records for BRCA1: …", then a model sentence naming the four diseases, then the trial and literature record lines. Every sentence carries a marker, the trust line and medical-advice line are present, and nothing scrolls sideways.
- Follow-up "What variants cause it?": opens "Found 13 sequence variant records for BRCA1, of 15310 available." with 20 sources from 3 layers. The check reported 12 claims without a marker, but the screenshot shows a marker on every sentence: the script's selector reads the old chip label, so the count is a measurement artifact, not an uncited claim.
- GCK, Researcher: opens on the "Found 13 sequence variant records for GCK, of 1333 available." summary with 4 group headings and 20 cited list rows.
- No "has a source URL of" sentence in any answer.
- `flagship_measure.py 5` against `2b6d274` (`after_2b6d274/flagship_measure_2b6d274.log`): median 19.7 seconds and worst 53.0, against 26.5 and 71.0 on `674b7b9` the night before. Four questions answered 5 of 5 with one source set each. "Variants in GCK causing MODY" answered 3 of 5: one fatal error at 15.7 seconds and one refusal at 5.4 seconds.
- Reproduced on develop, 8 more GCK runs: 7 answered (14.8 to 37.2 seconds, 20 citations each), and 1 refused in 4.0 seconds. On the refused run the guard passed, and Think's own narrative named the gene ("Query requires linking gene GCK to variants…"), yet Think resolved no entity, so no tool ran and the answer was the unresolved-gene refusal. Consistent with the speed-fix report's note that GCK refused in Think 2 of 10 runs because the live symbol lookup returned nothing. The 15.7-second fatal error did not recur in 8 runs. Its timing matches the 15-second guard budget, and a guard timeout was seen once in the synth-effort measurement, so it is recorded as a likely intermittent guard-step timeout, not yet proven.
- Remaining roughness, unchanged by this commit: record lines such as "Clinical trial name: …" and "SequenceVariant ClinVar:…, name: …" still read stiffly, and the model's sentence repeats the summary's disease names. The variant-to-disease and gene-to-disease tables in progress address part of this.

## Disposition

Defects 1 and 2 went to a fix agent the same night, on the answer path, with five live runs per case required. Its report: `testing/Developer/reports/2026-09-14_answer_quality/report.md`.
