# Findings: fix-2 screenshots, 2026-09-23

Information 12 of 13, answered 3 of 13.

Judged by a fresh-context agent against the product owner's two criteria (UI_fix_plan row 12.10): did it provide the information, and did it answer the question conversationally. Saved here by the lead, since the agent could not write files. The thirteenth "no information" is ZZZFAKE1, which correctly found nothing.

## Table of contents

- [Per screenshot](#per-screenshot)
- [Cross-cutting defects](#cross-cutting-defects)

## Per screenshot

| Filename comment | Query typed | Sources | Information | Answered | Evidence, verbatim | Other defects |
|---|---|---|---|---|---|---|
| BRCA1 works, but wasn't a one-word clarification introduced? | `BRCA1` | 18, 3 layers | Yes | No | "Found 1 gene record for BRCA1: BRCA1 DNA repair associated. Its gene symbol is BRCA1. BRCA1. One is named Germline BRCA1 and BRCA2 Mutations in Jewish Women Affected by Breast Cancer. Another is named BRCA1 Haploinsufficiency and Gene Expression. A third is named ..." | "Its gene symbol is BRCA1. BRCA1." repeats itself. No clarification asked |
| diseases brca1 | `Which diseases are associated with BRCA1?` | 23, 2 layers | Yes | Yes | "BRCA1 is associated with four diseases: Familial cancer of breast, Familial breast-ovarian cancer susceptibility 1, Pancreatic cancer susceptibility 4, and Fanconi anemia complementation group S. Mutations in this gene are responsible for approximately 40% of inherited breast cancers and more than 80% of inherited breast and ovarian cancers." | The cleanest pass in the set |
| marfan | `Marfan` (bare term) | 19, 2 layers | Yes | No | "Found 7 disease records for Marfan." | Record listing only, no clarification |
| mesh terms | `What MeSH terms are assigned to PMID 11237011?` | 26, 1 layer | Yes | Yes | "The MeSH terms assigned to PMID 11237011 include "Animals", "Chromosome Mapping", ..., and "Sequence Analysis, DNA"." | Real terms, no `[MeSH] D000818` codes; trust line 26 matches |
| mesh | `MeSH` (bare term) | 5, 1 layer | Yes | No | "Found 5 pubmed records: Meshing with MeSH., Multimorbidity and Comorbidity are now separate MESH headings., ..." | No clarification asked |
| metformin | `what does the literature say about metformin` | 5, 1 layer | Yes | No | "Another is titled Metformin: Mechanisms in Human Obesity and Weight Loss. A third is titled Cellular and Molecular Mechanisms of Metformin Action. ..." | Titles restated, never what the literature says. "Another" with no first |
| no problem with capitals | `any trials for gerd?` | 12, 2 layers | Yes | Partly | "Found 5 clinical trial records for gerd: Famotidine in Subjects With Non-erosive Gastroesophageal Reflux Disease, ..." | Accepted in lowercase, so 12.2 holds. Never says "yes, there are trials" |
| phenotypic feature plain language | `What phenotypic features are associated with Marfan syndrome?`, plain language | 53, 3 layers | Yes | No | "Found 1 disease record, 37 sequence variant records and 3 gene records for Marfan syndrome. Another gene is NCBIGene:7046, whose name is transforming growth factor beta receptor 1." | Names NO phenotypic feature; variants and genes substituted for what was asked |
| phenotypic features researcher | Same question, researcher | 13, 2 layers | Yes | No | "Found 1 disease record for Marfan syndrome: Marfan syndrome." | Shorter than plain language: one sentence against two, 13 sources against 53 |
| recent paper on statin, should have asked a year range | `recent papers on statins` | header 6, SOURCES 5 | Yes | No | "so that clinical judgment remains necessary in making the decision to use them.5" | Orphan lowercase fragment; "Another is titled ..." chain; trust line 6 against SOURCES 5; no year range asked |
| trial for melanoma | `is there a trial recruiting for melanoma` | 94, 3 layers | Yes | Partly | "One trial is named Modified Vaccine for High Risk or Low Residual Melanoma Patients. Another trial is named ..." | Status column says RECRUITING, the prose never says yes |
| variants | `What variants cause ZZZFAKE1?` | 0 | Correct refusal | Yes | "No answer found in NCBI records. I could not identify that gene. NCBI has no record matching the name in your question, so no graph query was attempted." | Correct and actionable |
| clicking the saved answer re-runs the search | `Which diseases are associated with BRCA1?` from the history rail | 22, 2 layers | Yes | Partly | "BRCA1 is associated with four diseases: ..." | No "Saved answer" label and no Run again button; 22 sources against the original 23 and a new VARIANT RECORDS paragraph, so a second search ran |

## Cross-cutting defects

- The answer lists instead of answering (12.10): seven of thirteen never state the fact asked for.
- One-word questions get no clarification (12.3, the product owner's open decision): `BRCA1`, `MeSH` and `Marfan` were all answered with a record listing.
- The phenotype question names no phenotypes at either depth: it answers with variant and gene records, an adjacent record type.
- Researcher is shorter than plain language (12.9): 13 sources and one sentence against 53 sources and two.
- The history rail re-runs a search asked in the same tab. Cause found by a second agent, `history_rerun.md` in this folder: `hasSavedAnswer` is set only by `mergeServerHistory` (`frontend/src/App.tsx:316`), which runs once per sign-in, so a row asked since page load never carries it and `onOpen` (`App.tsx:1947-1973`) falls through to `ask()`. Rows restored at sign-in do open the saved answer. Both 10.2 commits are on develop, so this is a gap in shipped code, not a missed deploy.
- The trust line disagrees with the source list on the statin question (12.11): header and line say 6, SOURCES says 5.
- A broken sentence on the statin question (12.12): an orphan lowercase fragment opening "so that".
