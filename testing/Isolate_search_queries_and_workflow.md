# Isolate search: queries and workflow

The isolate search is a new mode of the `pathogen_detection` tool. It lets a person ask for the actual isolates behind a resistance question, for example "which E. coli isolates carry ESBL genes", and get back a short list they can open, each one linked to its NCBI Pathogen Detection page and each one showing its resistance genes, plus an honest count of how many isolates matched and how many are shown. This document is tested from the user's chair: not "does the tool return rows", but "does the person reading the answer get what they came for, and does the answer ever mislead them."

## Table of contents

- [From the user's chair](#from-the-users-chair)
- [The queries](#the-queries)
- [What the answer must never do](#what-the-answer-must-never-do)
- [Workflow for the product owner](#workflow-for-the-product-owner)
- [Workflow for the developer](#workflow-for-the-developer)
- [Where these tests go next](#where-these-tests-go-next)

## From the user's chair

"From the user's chair, the person asking is an outbreak or AMR researcher who wants isolates they can open, each with its resistance genes and a link, and an honest statement of how many there are and how many were shown."

The approved shape answers this directly. Every isolate in a shown row carries its BioSample accession, strain, where and when it was collected, and its full resistance gene list, each linked to that isolate's own Pathogen Detection page rather than a generic search page. The answer states the exact number of isolates that matched and says plainly that only the first 20 are shown. Where a gene family name is ambiguous, such as "ESBL", the answer says which specific gene prefixes were actually searched and why the others were left out, rather than quietly guessing. Nothing here is model memory: every row comes from the current Pathogen Detection snapshot, counted or scanned live.

## The queries

Run these against the develop app, in this house format: Testing states what the query checks, Query is the literal text to type, Steps says how to run it, Expected is what the person should see.

### 1. The golden question: E. coli and ESBL genes

Testing: the flagship isolate search question, matched against the product's own golden dataset (G-035).

Query: `What Escherichia coli isolates in Pathogen Detection carry extended-spectrum beta-lactamase genes?`

Steps: type the query → Search

Expected:

- A list of isolates, each with its BioSample accession, strain, where and when it was collected, and its resistance genes, each gene list linked to that isolate's own Pathogen Detection page.
- The exact number of E. coli isolates the search found, and a plain statement that only the first 20 are shown.
- A note saying only the blaCTX-M family of genes was searched for "extended-spectrum beta-lactamase", and why: a plain blaTEM or blaSHV gene name cannot be told apart from a genuine ESBL by its name alone, so those families were left out rather than risk a wrong label.
- E. coli named and linked to its NCBI Taxonomy record among the sources cited.
- The answer arrives well under a minute.

### 2. The same question on Salmonella

Testing: the isolate search works for an organism other than E. coli, with the same shape of answer.

Query: `Which Salmonella isolates in Pathogen Detection carry ESBL genes?`

Steps: type the query → Search

Expected:

- The same shape as test 1: a list of isolates with accession, strain, collection details, resistance genes and links, an exact count, "showing the first 20", and the same disclosure that only the blaCTX-M family was searched.
- Salmonella named and linked to its own NCBI Taxonomy record, not E. coli's.

### 3. An exact gene, one allele only

Testing: naming a specific gene, rather than a family word, searches for that gene and nothing broader.

Query: `Which Salmonella isolates carry blaCTX-M-15?`

Steps: type the query → Search

Expected:

- Every isolate shown carries a gene starting with blaCTX-M-15, not a different CTX-M number and not a different gene family.
- The count and the "first 20 shown" note, same as the other tests.
- No mention of other ESBL families, since none were asked for.

### 4. Carbapenemase genes in Klebsiella

Testing: a different resistance family, on a different organism, still returns real isolates.

Query: `Which Klebsiella isolates in Pathogen Detection carry carbapenemase genes?`

Steps: type the query → Search

Expected:

- Isolates carrying at least one of the carbapenemase gene families (blaKPC, blaNDM, blaOXA-48, blaVIM, blaIMP), each with its full gene list and link.
- The answer names which gene prefixes it searched.
- An exact count and the first-20 note.

### 5. Colistin resistance in E. coli

Testing: a differently named resistance mechanism (a plasmid-mediated gene, not a beta-lactamase) still resolves correctly.

Query: `Which E. coli isolates in Pathogen Detection carry colistin resistance genes?`

Steps: type the query → Search

Expected:

- Isolates carrying an mcr gene, listed with their full gene set and a link to each isolate's page.
- The answer names the mcr gene prefixes it searched.
- An exact count and the first-20 note.

### 6. A gene nothing in this organism carries

Testing: a real, well-formed gene question that has zero matches gets an honest zero, not a refusal.

Query: `Which Listeria isolates in Pathogen Detection carry blaKPC?`

Steps: type the query → Search

Expected:

- A plain statement that the search found no isolates carrying this gene in this organism, stated as a count of zero, not as "I could not find information on this."
- No isolate rows, since there are none to show.
- No suggestion that the search failed or was refused. It ran, and the true answer is zero.

### 7. An organism Pathogen Detection does not cover

Testing: asking about an organism outside Pathogen Detection's scope gets an honest explanation, not an empty or invented result.

Query: `Which tomato isolates in Pathogen Detection carry resistance genes?`

Steps: type the query → Search

Expected:

- One question back: Pathogen Detection is searched one organism at a time, which organism do you mean, with a few it covers named in words (Escherichia coli, Salmonella, Listeria monocytogenes, Klebsiella pneumoniae, Campylobacter).
- The answer does not claim to know whether "tomato" is or is not in Pathogen Detection. It only recognises the organisms it can search, so it asks rather than asserts.
- No isolate rows and no invented data.

### 8. An organism named with no gene

Testing: naming an organism but no resistance gene or family asks a clarifying question rather than dumping every isolate.

Query: `Which E. coli isolates are in Pathogen Detection?`

Steps: type the query → Search

Expected:

- The answer asks which resistance gene or gene family to search for, rather than listing anything.
- No attempt to return all E. coli isolates. The exact number in the snapshot (in the hundreds of thousands) is never shown as a result list.

### 9. A follow-up asking to filter by year

Testing: a follow-up after an isolate search carries the organism and gene forward, and is honest about what it can and cannot do yet.

Query: after test 1, ask `Show me the ones from 2023`

Steps: finish test 1 → type the follow-up → Search

Expected, honestly stated for the first version: a year filter is not built, and a follow-up does not yet carry an isolate search forward the way it carries a gene forward.

- The answer asks which organism to search, or which gene, rather than pretending to filter.
- It never repeats the same full list as if it had been filtered to 2023, and never invents a filtered list.
- If the answer instead lists 2023 isolates that were genuinely filtered, that is a later version working, not this one; note it as a pleasant surprise rather than a pass.

### 10. The existing single-isolate lookup still works

Testing: the older, single-isolate mode of this tool is not broken by adding isolate search.

Query: `What is known about Salmonella isolate SAMN02147118 in Pathogen Detection?`

Steps: type the query → Search

Expected:

- A single isolate's details: its strain, where and when it was collected, its resistance genes, and a link to its Pathogen Detection page.
- No mention of "showing the first 20" or a count of isolates, since this is a single-record lookup, not a search.

### 11. The wait feels alive

Testing: the person is not staring at a frozen screen while the search runs.

Query: `Which E. coli isolates in Pathogen Detection carry ESBL genes?`

Steps: type the query → Search → watch the progress screen while it runs

Expected:

- The progress steps show the pathogen search running, with continuous motion, not a blank pause.
- The answer arrives and builds on screen; nothing about the wait looks stuck or broken.

### 12. The shortest version a person would type

Testing: a terse, minimally worded question with only "ESBL" as the clue still works.

Query: `ESBL E. coli isolates?`

Steps: type the query → Search

Expected:

- The same shape of answer as test 1: isolates listed with genes and links, an exact count, the first-20 note, the disclosure that only blaCTX-M was searched, and E. coli's Taxonomy record cited.
- The short, informal phrasing is understood the same way as the fully worded question in test 1.

## What the answer must never do

- Never list a blaTEM-1 carrier as an ESBL isolate. blaTEM-1 is a plain, broad-spectrum gene, not an extended-spectrum one, and stating otherwise would be a confident wrong record.
- Never claim a total number of isolates it did not actually count. If the scan was cut off before finishing, the answer says "at least" that many, never a bare exact number it cannot back up.
- Never link an isolate to any page outside NCBI.
- Never answer from memory when the search returned nothing. A true zero is stated as a true zero, and an organism or gene Pathogen Detection genuinely lacks data for is named as such, never papered over with a guess.
- Never show a bare `SAMN` accession as an isolate's only name when it has a strain name. The strain name comes first, with the accession alongside it.

## Workflow for the product owner

1. Open the develop app: <https://search-agent-web-develop-2aeb.up.railway.app> (the URL in `testing/README.md`).
2. Sign in with your usual account, or test as a guest for query 1 if you want to see the guest experience too.
3. Run the twelve queries above in order. Each one builds a little on the last, so running them in order makes it easier to spot where something breaks.
4. Screenshot the answer for every query, and especially screenshot query 6 (the honest zero), query 7 (the unsupported organism), query 8 (the clarifying question) and query 9 (the follow-up), since these are the ones most likely to go wrong quietly.
5. Drop screenshots and notes in `testing/Product/feedback/inbox/`. Put the query number in the filename if that is convenient.
6. Say "check the inbox" when you are done, and the findings will be picked up from there.

## Workflow for the developer

The automated checks that back these queries:

- `tests/system_03_search_agent/tools/test_pathogen_detection.py`: unit tests for the isolate search mode of the tool itself.
- `tests/system_03_search_agent/tools/test_pathogen_detection_premise.py`, run with `RUN_PREMISE_GATE=1`: the live premise gate against the real Pathogen Detection FTP snapshot.
- `tests/system_03_search_agent/core/test_isolate_search.py` and `test_isolate_search_wiring.py`: the agent-loop side, how Think, Plan, Act and Write handle an isolate search question.

For a live proof against develop itself, use the consistency runner at `testing/Developer/reports/2026-09-22_10.3_consistency/run_consistency.py` with `--ids G-035`, run three passes, and keep the laptop awake with `caffeinate -i` for the duration. Do not run any other live measurement against NCBI at the same time, since the E-utilities and Pathogen Detection rate pools are shared and a second live check running in parallel can trip both.

The evidence folder for that run must contain `runs.jsonl` (the raw pass-by-pass record), a `raw/` folder (the full response bodies), and a `findings.md` that states its verdict in the first line, before any detail.

## Where these tests go next

Once this feature is live and the product owner has approved it, query 1 becomes Product_workflows test 23, and the full set of query shapes here becomes a Developer_workflows Tier 2 row. This document is the source; those two documents are the index that points back to it.
