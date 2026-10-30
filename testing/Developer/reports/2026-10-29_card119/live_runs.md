# Card 119: five live runs against develop

Five pairs of live runs of the windowed BRCA1 question, develop's code (`b5690f98`) against card 119's (`e2244a2c`), run one after the other on the lead's machine on the night of 2026-10-29. Each run asked `Recent papers on BRCA1`, read the "How far back" choices from the answer, and sent back "Recent papers on BRCA1 from the last 5 years?" in the same session, through `core.run.run_streaming()`, the path the web app uses. Researcher depth, local user database, about $0.16 in all.

## Table of contents

- [Results](#results)
- [What a person sees](#what-a-person-sees)
- [Verdict](#verdict)

## Results

| Pair | Develop, seconds | Card 119, seconds | Develop, PubMed records | Card 119, PubMed records | Develop count line | Card 119 count line |
|---|---|---|---|---|---|---|
| 1 | 24.2 | 18.1 | 5 | 10 | Found 4 papers | Found 9 papers |
| 2 | 22.0 | 19.0 | 5 | 10 | Found 4 papers | Found 9 papers |
| 3 | 33.6 | 22.3 | 5 | 10 | Found 4 papers | Found 9 papers |
| 4 | 19.5 | 21.5 | 5 | 10 | Found 4 papers | Found 9 papers |
| 5 | 17.6 | 25.9 | 5 | 10 | Found 4 papers | Found 9 papers |

- Median time: develop 22.0 s, card 119 21.5 s. The machine ran other agents' tests at the same time, so both sides run slower than deployed develop. The spread overlaps, and card 119 is not slower.
- Cost per question: develop $0.013 to $0.022, card 119 $0.015 to $0.018.
- Errors: none on either side.

## What a person sees

- Develop lists five PubMed records and says "Found 4 papers". Card 119 lists ten and says "Found 9 papers".
- In each case the one record not counted is a PubMed book record, the GeneReviews chapter of card 124, which the abstract parser skips. Card 124 waits for the owner's call.
- Every run on both sides has a written summary drawn from the papers' abstracts: five to eight paragraphs, such as "BRCA1-BARD1 directly stimulates the EXO1- and DNA2-dependent long-range DNA end resection pathways ...". Card 119 draws on the five newest papers, develop on the five it lists.

## Verdict

Nothing worse than develop: twice the papers from the window, the same speed, the same cost, and a written summary every time. The run files stay in the session scratchpad and are not committed.
