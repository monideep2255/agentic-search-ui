# Card 129: the MedGen check for "breast cancer"

What MedGen returns today for the breast cancer mention, read the way the code reads it. NCBI only, no model call. Run 2026-10-22 through the repository's own `ncbi_eutils_actions.search` and `summary` (the term `breast[title] AND cancer[title]`, retmax 20, as `resolve_disease_mention_to_curies` builds it), plus one raw ESummary call to see which fields NCBI sends beyond the allowlist.

## Table of contents

- [Result](#result)
- [The 20 hits](#the-20-hits)
- [What binds, before and after Fix C](#what-binds-before-and-after-fix-c)
- [Synonyms](#synonyms)
- [The controls](#the-controls)

## Result

| Question | Answer |
|---|---|
| Is C0006142 ("Malignant tumor of breast") in the first 20 hits? | Yes, sixth in MedGen's order |
| Its semantic type | "Neoplastic Process", a disease type |
| Reachable by Fix C? | Yes: with Finding records ranked out, it binds through the synonym tier |
| Records of a disease type among the 20 | 6 |
| Records typed "Finding" among the 20 | 14, "Seen by breast cancer nurse" (C1320450) among them |

## The 20 hits

In MedGen's order. "Phrase in title" means the title carries "breast cancer" as a whole phrase, the code's first tier.

| Rank | Concept id | Title | Semantic type | Phrase in title |
|---|---|---|---|---|
| 1 | C2676676 | Breast-ovarian cancer, familial, susceptibility to, 1 | Finding | no |
| 2 | C2675520 | Breast-ovarian cancer, familial, susceptibility to, 2 | Finding | no |
| 3 | C0346153 | Familial cancer of breast | Neoplastic Process | no |
| 4 | C0677776 | Hereditary breast ovarian cancer syndrome | Neoplastic Process | no |
| 5 | C1708349 | Hereditary diffuse gastric adenocarcinoma | Neoplastic Process | no |
| 6 | C0006142 | Malignant tumor of breast | Neoplastic Process | no |
| 7 | C0268301 | Partial androgen insensitivity syndrome | Disease or Syndrome | no |
| 8 | C3469522 | Breast cancer, susceptibility to | Finding | yes |
| 9 | C4016951 | Breast cancer, early-onset | Neoplastic Process | yes |
| 10 | C1320450 | Seen by breast cancer nurse | Finding | yes |
| 11 | C4304130 | Breast cancer screening declined | Finding | yes |
| 12 | C4016581 | Androgen insensitivity, partial, with breast cancer | Finding | yes |
| 13 | C4016759 | BREAST CANCER, PROTECTION AGAINST | Finding | yes |
| 14 | CN235586 | bilateral breast cancer | Finding | yes |
| 15 | C4047698 | Breast cancer screening not done | Finding | yes |
| 16 | C1968974 | BREAST CANCER, INVASIVE, SUSCEPTIBILITY TO | Finding | yes |
| 17 | C2676677 | BREAST CANCER, FAMILIAL, SUSCEPTIBILITY TO, 1 | Finding | yes |
| 18 | C2675521 | BREAST CANCER, FAMILIAL, SUSCEPTIBILITY TO, 2 | Finding | yes |
| 19 | C4016360 | BREAST CANCER, SUSCEPTIBILITY TO, IN BRCA1 AND BRCA2 CARRIERS | Finding | yes |
| 20 | C1861471 | Paraneoplastic SPS is associated with breast cancer and other malignancies | Finding | yes |

## What binds, before and after Fix C

No title equals "breast cancer", so the exact rule binds nothing either way.

| | Bound records, in order |
|---|---|
| Before | C1320450 (Seen by breast cancer nurse), C1861471, C1968974, C2675521, C2676677, C3469522, C4016360, C4016581: 8 records, all Findings, C0006142 cut |
| After | C4016951 (Breast cancer, early-onset), C0006142 (Malignant tumor of breast), C0268301 (Partial androgen insensitivity syndrome), C0346153 (Familial cancer of breast), C0677776 (Hereditary breast ovarian cancer syndrome), C1708349 (Hereditary diffuse gastric adenocarcinoma): 6 records, all disease-typed |

This confirms the diagnosis's reading of the old binding: the seven upper-case names in the note were these Findings.

What the after set still carries, for the owner to weigh: two of the six match only through a synonym that names breast cancer as one part of a wider condition. Partial androgen insensitivity syndrome lists "androgen insensitivity, partial, with or without breast cancer"; hereditary diffuse gastric adenocarcinoma lists "Diffuse gastric and lobular breast cancer syndrome". Both are real disease records with a breast cancer link, not a nurse visit, but a person asking about breast cancer would not name them first.

## Synonyms

| Question | Answer |
|---|---|
| Does ESummary carry synonyms? | Yes, inside `conceptmeta`, an XML blob of 0.5 to 17.5 KB per record, as `<Name>` elements |
| Does C0006142 list the mention exactly? | Yes: "Breast cancer" and "BREAST CANCER" are among its names |
| Does any other of the 20 list it exactly? | No |
| Is the field already returned to the resolver? | No: `ncbi_eutils_actions` keeps only `conceptid`, `title`, `definition` and `semantictype` for MedGen, so `conceptmeta` is dropped before the resolver sees it |

An exact-synonym rule would bind C0006142 alone, the record a person means. It is not built here: it needs `conceptmeta` added to the MedGen allowlist in `ncbi_eutils_actions.py` (outside this card's file fence) and a parser for a large submitter-assembled XML field, which is not a small read of a field already returned. It is the follow-on candidate the diagnosis names.

Raw ESummary keys for a MedGen record today: `conceptid`, `conceptmeta`, `definition`, `merged`, `modificationdate`, `semanticid`, `semantictype`, `suppressed`, `title`, `uid`.

## The controls

The same check for the two controls, to show Fix C leaves them alone.

| Mention | Hits | Disease-typed | Findings | Bound before | Bound after |
|---|---|---|---|---|---|
| MODY | 8 | 8, all "Disease or Syndrome" | 0 | 8 | the same 8, same order |
| bronchiolitis | 20 | 17 | 3 (History of bronchiolitis C3532617, Bronchiolitis acute and chronic C6066561, Postinfectious bronchiolitis obliterans C5830150) | C0001311, C0006271, C0006274, C0264366, C0264369, C0276154, C0276340, C0340047 | the same 8: the three Findings sort past the cap in both |
