# UI fix plan

The board for the UI fix loop. An item starts in To do, moves to Build in
progress when someone starts it, and moves to Retest once it is live on
develop. When you approve it, it leaves the board.

This board is the source of truth for what gets worked on: an item is written
here before it is built. Every item's detail, every closed item and every note
behind the board are in `testing/UI_fixes_done.md`.

Last updated: 2026-09-24.

## To do

In priority order.

| # | Feature, in plain words | Item | Waiting on |
|---|---|---|---|
| 1 | A question about phenotypic features names none: `What phenotypic features are associated with Marfan syndrome?` answers with variant and gene records at both depths | 12.14 | Nobody on it |
| 2 | A good question sometimes fails at the think step and shows a refusal | 12.17 | Nobody on it |
| 3 | Which questions count as a request for papers becomes a classifier's decision; today it is a word list | 12.16 part 3 | Nobody on it |
| 4 | A question asking for recent papers asks what recent means | 12.15 | Nobody on it |
| 5 | Four golden test rows disagree with what the product does, row by row | the golden rows | Your decision |
| 6 | Is twenty sources the right ceiling? | the ceiling | Your decision |
| 7 | Tell the reader when the system wrote its own search rather than using a checked one | the drafted search | Nobody on it |
| 8 | Hard and soft edges over a fuller graph, "connecting the dots" | 11.29 | Parked |
| 9 | A bounded trial of the probability model | 11.38 | Parked |
| 10 | Answers modelled on the reference prototype's depth, formatting and structure | 11.11 | Nobody on it |
| 11 | Does the Plain language answer keep its small grey medical-advice line? | 9.11 | Your decision |
| 12 | The trust-line wording | 9.9 | Your decision |
| 13 | Judge answer quality once answering is reliable | 10.4 | Nobody on it |
| 14 | A lock file for the Python build | the lock file | Your decision |
| 15 | Internal MCP servers around the Layer 2 and Layer 3 calls | 11.32 | Parked |
| 16 | The explanation half of 11.31 | 11.31 | Parked |
| 17 | The byte ceiling at 50,000 | the byte ceiling | Parked |

## Build in progress

Nothing is being built right now.

## Retest

Built and live on develop, newest first. The queries to type and what you
should see are in `testing/Test_queries_and_workflows.md`, by the number in
the last column.

| # | What to check, in plain words | Item | Queries |
|---|---|---|---|
| 1 | "Based on N sources" equals the SOURCES count on the page | 12.11, 12.8 | 74 |
| 2 | No broken sentences and no restatement paragraph | 12.12 | 75 |
| 3 | The answer answers the question in plain sentences drawn from the papers, each cited | 12.10 | 73 |
| 4 | A search clicked in the history rail, in the same tab, opens its saved answer | 12.13 | 67 |
| 5 | Plain language and researcher differ on every question | 12.9 | 72 |
| 6 | A one-to-three-word question is asked back, with choices written for its subject | 12.3 | 76 |
| 7 | The seven questions your skip manager asked all answer | 12.1 | 68, 69, 73 |
| 8 | A literature question typed in lowercase is not refused as "Outside biomedical research" | 12.2 | 70 |
| 9 | A refusal says "Ask another question" | 12.4 | 71 |
| 10 | A question naming no gene and no disease finds the papers, each shown once | 12.7 | 69 |
| 11 | The MCP configuration on the Integrations page connects, and never sends you to an `http://` address | 11.30 | 60 |
| 12 | History shows the saved answer at once, with Run again | 10.2 | 67 |
| 13 | MeSH terms show as real terms, each linked to its MeSH record | G-019 | 64 |
| 14 | The opening sentence's count agrees with the list beneath it | the opening count | 65 |
| 15 | The Marfan phenotype question no longer says "I could not find evidence"; what it answers instead is 12.14 in To do | the phenotype template | 66 |
| 16 | Two questions keep their own graph search: MLH1 and MSH2, and GEO datasets for TP53 | G-033, G-037 | 24, 25 |
| 17 | A chromosome range is answered with its genes and records, and a range with no assembly asks which | the coordinate range | 27, 28, 29 |
| 18 | An answer never lists the question's own words as diseases it did not address | the question's own words | 23, 25 |
| 19 | A BioProject or BioSample accession is answered, and an unknown one is named as not found | the accessions | 30, 31, 32 |
| 20 | Pathogen Detection isolate questions answer with a table of isolates and their resistance genes | G-035 | 33, 35, 36, 38, 39, 40, 44, and `testing/Product/queries/Isolate_search_queries_and_workflow.md` |
| 21 | Copy an answer and paste it somewhere: no "Source 1, layer 2" text | 11.14 | 6 |
| 22 | Open the answer-modes info button: no promise of a word count | 11.36 | 3 |
| 23 | Change the mode while a search is running: it cannot change mid-search | 9.12 | 4 |
| 24 | Open the app twice: different scientists, the same answer | 8.4 | 9 |
