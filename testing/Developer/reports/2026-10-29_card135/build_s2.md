# Card 135 build, slice S2: a reopened answer names and cites its sources as the live one does

Slice S2 covers parts 135.2 (sources carry raw tool names) and 135.3 (citations show as plain "[1]" text) of `testing/Developer/reports/2026-10-29_card135_136/diagnosis.md`. Part 1, the OMIM link, is a separate pull request and is not touched here.

## Table of contents

- [Cause, as confirmed in code](#cause-as-confirmed-in-code)
- [Fix](#fix)
- [Live labels that change](#live-labels-that-change)
- [Saved-screen labels that change](#saved-screen-labels-that-change)
- [Tests](#tests)
- [Known gaps](#known-gaps)
- [Fix round](#fix-round)

## Cause, as confirmed in code

135.2, sources:

- Confirmed: `frontend/src/components/screens/SavedAnswerScreen.tsx` labelled a row `entity_name ?? source` and dropped `source_id`, so twenty isolate rows each read "pathogen_detection".
- Confirmed: the live list (`frontend/src/hooks/useRunView.ts`) named the same citation `sourceDisplayName(source, source_id)`, so it read "pathogen_detection SAMN00715300". The two screens disagreed, and both printed a tool's string.
- Confirmed where tool strings come from: the fallback citation in `core/graph.py` sets `source` to the tool name, `tools/pathogen_detection.py` sends "pathogen_detection" and `tools/clinicaltrials_search.py` sends "clinicaltrials.gov".
- Corrected detail: no frontend table of database names existed. The server's table is `_NCBI_DATABASE_NAMES`, `_NCBI_RESEARCH_NAMES` and `_DATABASE_NAMES` in `src/system_03_search_agent/synthesis/trust.py`, keyed by `record_database`.

135.3, citations:

- Confirmed: `feedback/capture.py` writes markers into the stored markdown as `[n]` text (claim text inline, `_markers_for` on a table's first cell and on a list item).
- Confirmed: `frontend/src/components/screens/savedAnswerMarkdown.tsx` printed every block, cell and list item raw, and `SavedAnswerScreen.tsx` passed it only the markdown, never the citations.

## Fix

Sources, one helper for every screen:

- New `frontend/src/lib/sourceDatabase.ts`: the trust line's table ported unchanged, and `recordDatabase(url)`, the page branch of `trust.py`'s `record_database`.
- New `sourceLabel(source, source_id, source_url)` in `frontend/src/hooks/useRunView.ts`, beside `sourceDisplayName`. When `source` is a tool's string (a snake_case name such as `ncbi_efetch`, or a bare host such as `clinicaltrials.gov`) and the record page names a database the table knows, the label is the database's name, then the record id. A CURIE prefix on the id that names the same database is dropped; any other prefix stays. The fallback placeholder id "unknown" is not printed.
- Every other source keeps exactly today's label. A source that already names its database ("NCBIGene", "MedGen", "ClinVar", "gene", "dbsnp", "omim") is never rewritten, and a page on a host the table does not know is never guessed at.
- Used by the live Sources list, the marker card (it reads the same `name`) and the saved Sources list. The saved row no longer prints `entity_name`, because the live screen does not.

Citations:

- `SavedAnswerScreen.tsx` passes `answer.citations` to `SavedAnswerMarkdown`.
- `savedAnswerMarkdown.tsx`'s `withCitationMarkers` renders each run of `[n]` through the live `CitationMarkers` component, in paragraphs, list items and a table's first cell. So the small raised numbers, the collapse of four or more into one range marker, and the card a marker opens are the live screen's own.
- The live R-05 rule holds: a number is a marker only when it is a stored citation's number. Any other bracketed number stays as text.
- Sentence punctuation after a run moves in front of the marker, so "coli [1]...[20]." reads "coli." then the marker, as live.
- Other table cells stay data. Without citations, every `[n]` stays text, as before.

## Live labels that change

Only sources whose `source` is a tool's string change. The table lists every shape the producers send that is affected.

| Source on the wire | Before | After |
|---|---|---|
| `pathogen_detection`, isolate page | pathogen_detection SAMN00715300 | Pathogen Detection SAMN00715300 |
| `clinicaltrials.gov`, study page | clinicaltrials.gov NCT00590109 | ClinicalTrials.gov NCT00590109 |
| `ncbi_efetch` fallback, gene page, CURIE id | ncbi_efetch NCBIGene:672 | NCBI Gene 672 |
| `ncbi_efetch` fallback, no CURIE | ncbi_efetch unknown | NCBI Gene (or the page's database) |
| any other tool name (`ncbi_dbsnp`, `litvar2_lookup`, `pubtator_annotate`, `cypher_query`) on a known page | tool name, then id | the page's database (dbSNP, LitVar2, PubTator3, PubMed, and so on), then id |
| any tool name on a page the table does not know | tool name, then id | unchanged |

Unchanged: every graph source (CURIE prefixes such as "NCBIGene 672", "MedGen C0346153", "ClinVar VCV000267740") and every Layer 2 source that already sends a database name ("gene 672", "dbsnp rs80357906", "omim 113705", "litvar2 ..."). A normal gene answer's Sources list reads exactly as before. The marker card's mono tool row on the live screen is unchanged.

Because this is a visible change to the live answer screen as well, the product reviewer should check it at 1280 and 390, and the owner's retest row should say the live labels changed too.

## Saved-screen labels that change

- A row is now named as the live list names it: "Pathogen Detection SAMN00715300" where it read "pathogen_detection", "NCBIGene 672" where it read "NCBIGene".
- A row whose stored `entity_name` is set (for example "BRCA1") keeps that name, as on develop (changed in the fix round below).
- The summary's "[1][2]...[20]" is one range marker reading 1 to 20; a table row's "C236-11 [1]" and a list item's "Escherichia coli[21]" carry a marker each.

## Tests

Run from `frontend/`: `npx vitest run src/components/screens/ src/hooks/ src/components/answer/ src/lib/sourceDatabase.parity.test.ts` gives 38 files, 366 passed. `npx tsc --noEmit -p .` is clean. Also green: `src/App.savedAnswer.test.tsx`, `src/lib/riskTag.parity.test.tsx`, `src/lib/api.fetchHistoryAnswer.test.ts` (43 passed).

New and changed tests:

- `frontend/src/lib/sourceDatabase.parity.test.ts` (new): reads `trust.py` and holds the three tables equal both ways; pins `recordDatabase` on the cases `record_database` names.
- `frontend/src/hooks/useRunView.sourceName.test.ts`: `sourceLabel` for every page key in the table, the three raw sources from the retest, a foreign prefix kept, the "unknown" placeholder dropped, an unknown host falling back, and database-named sources never rewritten. The live list fed the card 22 BRCA1 citations reads exactly `sourceDisplayName`'s labels; a `pathogen_detection` citation reads "Pathogen Detection SAMN00715300".
- `frontend/src/components/screens/SavedAnswerScreen.card102.test.tsx`: stored `pathogen_detection`, `clinicaltrials.gov` and `ncbi_efetch` citations run through the real `fetchHistoryAnswer` into the real screen read the same names the real `useRunView` gives the same payloads; the BRCA1 gene row reads as live; stored "[1][2][3]" render as three markers and an uncited "[9]" stays text.
- `frontend/src/components/screens/savedAnswerMarkdown.test.tsx`: G-035's twenty-marker summary renders one marker labelled `markerLabel([1..20])` with no bracket left and the full stop before it; the table's first cell and the list item carry markers, the second cell does not; "[12]" and "[99]" with no citation stay text; three markers stay three; pressing a saved marker opens the live card naming "Pathogen Detection SAMN00715300" with its record link.
- `frontend/src/components/screens/savedAnswerMarkdown.card71.test.tsx`: changed. The two phone-row tests pinned "Isolate-1 [1]" and "Iso-1 [1]" as text. They now pass the stored citations and assert the first cell is "Iso-1" followed by the live marker, with the other stacked values unchanged.
- `frontend/src/components/screens/SavedAnswerScreen.test.tsx`: changed. The row once asserted "1. BRCA1" from `entity_name`; it now asserts the live label "1. Gene".

Mutations, each restored after:

| Mutation | Result |
|---|---|
| Live list calls `sourceDisplayName` again | 2 red |
| Saved row back to `entity_name ?? source` | 3 red |
| `withCitationMarkers` returns the raw text | 7 red |
| Screen stops passing `citations` | 1 red |
| Every bracketed number becomes a marker (R-05 broken) | 8 red |
| Every source relabelled from its page | 3 red |
| Table name drifts from `trust.py` | 3 red |
| Punctuation not moved before the marker | 2 red |
| Table first cell left raw | 1 red |

## Known gaps

- The saved marker card's mono tool row is empty. The live card shows the citation's `field` there, and the saved-answer parser in `frontend/src/lib/api.ts` (outside this slice's files) does not keep `field`. It is left empty rather than filled with a tool's string.
- A mixed run such as "[1][99]" keeps a space before "[99]" on the saved screen; the live screen would print "Another[99]". Neither producer emits this shape today.

## Fix round

Judge finding J-135S2-01, decided by the lead from the reader's chair: a reopened answer still names a source by what it is, such as BRCA1, and where it used to show an internal tool name it now names the database and the record.

- `SavedAnswerScreen.tsx`: the saved Sources row label is the record's `entity_name` when present and non-empty, exactly as develop; otherwise `sourceLabel(source, source_id, source_url)`. The live Sources list and marker card are unchanged and never show `entity_name`.
- `SavedAnswerScreen.test.tsx`: the first test is back to develop's "1. BRCA1". New: no entity name with source `pathogen_detection` on a pathogens host reads "Pathogen Detection SAMN00715300" and no tool name; no entity name with source "Gene" reads the live label.
- Mutations: always `sourceLabel` turns 1 test red (BRCA1); always `entity_name || source` turns 2 red (the two new cases). Both restored.
- Run from `frontend/`: `npx vitest run src/components/screens/ src/hooks/ src/components/answer/ src/lib/` and `npx tsc --noEmit -p .`.
