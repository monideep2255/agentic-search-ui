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

## Disposition

Defects 1 and 2 went to a fix agent the same night, on the answer path, with five live runs per case required. Its report: `testing/Developer/reports/2026-09-14_answer_quality/report.md`.
