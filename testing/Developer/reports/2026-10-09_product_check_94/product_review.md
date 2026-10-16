# Card 94 product check: an isolate answer's "Collected" cell says when and where

The product reviewer's pre-screen of card 94 (pull request #226, merge 75be0bbb) on deployed develop. It files findings and closes nothing; the owner's retest decides. Card 94 changes only the answer the API writes; the web bundle is unchanged. No golden run was in this brief.

## Table of contents

- [Which app answered](#which-app-answered)
- [Findings](#findings)
- [Result](#result)
- [What was not captured](#what-was-not-captured)

## Which app answered

- API `/health`: `{"status":"ok","app_env":"develop"}` at 05:53 UTC and again at 10:57 UTC, read from the shell and from inside the signed-in page (`run_1280_log.json`, `run_390_log.json`, step "health").
- Develop head at 10:57 UTC: still 75be0bbb, the card 94 merge.
- Web bundle `index-NJO4wipr.js`, the same bundle as card 109's check (log step "bundle").
- One throwaway develop account, its name masked as "account hidden" on every screenshot (log step "email visible unmasked": false).
- First attempt, about 05:54 UTC: the reviewer's network dropped mid-question and the page read "network error" (`attempt0_1280_answer_viewport.png`). Kept as evidence, not judged. The coordinator asked for the check to be run again; it was, from 10:57 UTC.

## Findings

### PR-94-01: At 1280 in Researcher, all ten rows on page 1 read "Not recorded", and their BioSample records hold neither a date nor a place
- Kind: answer
- Verdict: pass
- What: asked query 33 at 1280 in Researcher at 10:57 UTC; the answer landed at 27.4 s ("Answered 27.0s · 2 tool calls · 21 sources cited from 1 layer"). The table "Isolates and their AMR genes" shows page 1 of 2, ten rows, C236-11 (SAMN00715300) to 11-4632 C5 (SAMN00715312), and every "Collected" cell reads "Not recorded". The BioSample records of four of them (SAMN00715300, SAMN00715303, SAMN00715305, SAMN00715312), fetched from E-utilities, hold geographic location "missing" and no collection date attribute at all. So "Not recorded" is true, and the placeholder word "missing" was not shown as a place.
- Evidence: `run_1280_log.json` ("answer landed", `answer.tables[0].rows`); `1280_table_viewport.png`; BioSample SAMN00715300, BioSample SAMN00715303, BioSample SAMN00715305, BioSample SAMN00715312 (`geo_loc_name` "missing", no `collection_date`).
- Why a person would care: "It tells me plainly the record has no date or place, instead of printing the word missing as if it were a country."
- NOT CLOSED

### PR-94-02: Page 1 never shows card 94's new behaviour, a place, so a person sees no change on the first screen
- Kind: answer
- Verdict: needs your eye
- What: the first ten isolates are the 2011 E. coli submissions whose records hold no date or place, so the whole visible "Collected" column reads "Not recorded" at 1280, before and after card 94 alike. Whether any of the 20 rows shows "2013, USA: Minnesota" style text depends on page 2 (see the 390 findings). The order is the snapshot's order, not chosen by the change.
- Evidence: `1280_table_viewport.png`, `1280_answer_full.png`.
- Why a person would care: "The column I was told now shows where isolates came from is ten rows of Not recorded."
- NOT CLOSED

### PR-94-03: At 390 in Plain language, page 2 shows when and where for eight of ten isolates, and every place matches the isolate's own BioSample record
- Kind: answer
- Verdict: pass
- What: asked query 33 at 390 in Plain language at 10:59 UTC; the answer landed at 20.4 s ("Answered 20.0s · 2 tool calls · 21 sources cited from 1 layer"). Page 1 is the same ten "Not recorded" rows as at 1280. Page 2 reads, row by row: C227-11 "Not recorded"; Ec11-4988, Ec11-5603 and Ec11-6006 "2011, France: Bordeaux"; 11-02030 "2011, Germany: Leverkusen"; 11-02033-1 "2011, Germany: Bremerhaven"; 11-02092 "2011, Germany: Freiburg i.Br."; 11-02093 "2011, Germany: Rostock"; 2011C-3493 "Not recorded"; NA114 "2009, India: Pune". Each row's source link is its Pathogen Detection search by BioSample accession (for example `https://www.ncbi.nlm.nih.gov/pathogens/isolates#/search/biosample_acc:SAMN00778958`). Checked against the BioSample record of all ten page 2 rows: Ec11-4988 "France: Bordeaux", 2011-07-02; 11-02030 "Germany: Leverkusen", 2011-05-19; 11-02092 "Germany: Freiburg i.Br.", 2011-05-23; NA114 "India: Pune", 2009-11-16; C227-11 place "missing", no date; 2011C-3493 neither attribute. All ten cells agree with their records. "Freiburg i.Br." keeps its dots, so the placeholder matching that strips dots did not eat a real place.
- Evidence: `390_table_page2_viewport.png`, `390_table_page2_full.png`; `run_390_log.json` ("answer landed", `sources`); BioSample SAMN00715316, BioSample SAMN00778958 to SAMN00778960, BioSample SAMN01141737 to SAMN01141740, BioSample SAMN01831188, BioSample SAMN02603711.
- Why a person would care: "I can see these are the 2011 Bordeaux and German outbreak isolates and one from Pune in 2009, without opening each record."
- NOT CLOSED

### PR-94-04: No cell shows a placeholder word as a place, at either width
- Kind: answer
- Verdict: pass
- What: the five rows whose BioSample place reads "missing" (SAMN00715300, SAMN00715303, SAMN00715305, SAMN00715312, SAMN00715316) all read "Not recorded"; no cell on either page contains "missing", "not collected", "unknown" or "NA". The page 1 text at 1280 and 390 was read from the page; page 2 was read from the 390 screenshots only.
- Evidence: `run_1280_log.json` and `run_390_log.json` (`answer.text`); `390_table_page2_viewport.png`, `390_table_page2_full.png`.
- Why a person would care: "Nobody would think an isolate came from a place called missing."
- NOT CLOSED

### PR-94-05: The table fits at both widths; at 390 it becomes stacked rows, with no scrolling of any kind
- Kind: screen
- Verdict: pass
- What: horizontal page overflow is 0 at 390 on the landing page, after the answer, and on page 2 (`"doc":0,"body":0`). At 390 the isolates are not a table at all but one stacked block per isolate (name, accession, genes, then the "Collected" line), so nothing scrolls inside a box either. At 1280 the table sits in an `overflow-x: auto` box 786 px wide whose scroll width equals its width (786), so it does not scroll there either.
- Evidence: `run_390_log.json` ("overflow landing", "overflow after answer", "overflow on page 2"); `run_1280_log.json` (`tables[0].box`); `390_answer_full.png`, `390_table_page2_full.png`, `1280_table_viewport.png`.
- Why a person would care: "On my phone I read each isolate top to bottom, nothing cut off."
- NOT CLOSED

### PR-94-06: At 1280 the "Collected" column is narrow, so "Not recorded" breaks over two lines on every row
- Kind: screen
- Verdict: needs your eye
- What: the "Collected" column at 1280 is about 90 px wide while "AMR genes" takes most of the row; every "Not recorded" wraps to "Not / recorded". A longer cell such as "2011, Germany: Freiburg i.Br." will wrap to three lines there. Page 2 at 1280 was not captured, so the long places were seen only at 390.
- Evidence: `1280_table_viewport.png`.
- Why a person would care: "The place column is squeezed; the gene list gets all the room."
- NOT CLOSED

### PR-94-07: The gene list is not itself a link; each row reaches its Pathogen Detection page through the citation number
- Kind: answer
- Verdict: needs your eye
- What: query 33's line says "each gene list is linked to that isolate's own Pathogen Detection page". No cell in the table holds a link (`cellLinks` is empty, 0 links inside the table). The row's green number (1 to 20) points to the source whose link is the isolate's Pathogen Detection search. Probably the same as before card 94; the wording of the test document and the screen differ.
- Evidence: `run_390_log.json` ("links inside table": 0, `sources`); `1280_table_viewport.png`.
- Why a person would care: "I tapped the genes and nothing happened; I had to find the little number."
- NOT CLOSED

### PR-94-08: The first sentence lists twenty strain names instead of answering, and "11-4632 C1" is bold for no reason, at both depths
- Kind: answer
- Verdict: needs your eye
- What: Researcher opens "The query identified the following isolates: C236-11, 11-3677, ... and NA114." Plain language opens "The isolates are C236-11, 11-3677, ... and NA114." Both bold "11-4632 C1" alone. The two depths otherwise read nearly the same. Rubric line 1 ("lists what was found instead of answering"). Not caused by card 94.
- Evidence: `run_1280_log.json`, `run_390_log.json` (`answer.text`); `1280_table_viewport.png`, `390_table_page2_full.png` (bold "11-4632 C1").
- Why a person would care: "The first thing I read is a wall of strain codes, and one of them is bold as if it mattered more."
- NOT CLOSED

### PR-94-09: The Researcher answer took 27.4 s, over the 20 second target; Plain language took 20.4 s
- Kind: answer
- Verdict: needs your eye
- What: one ask each, so not a measure of speed, only an observation. First table row at 19.4 s at 1280.
- Evidence: `run_1280_log.json` ("first table row on screen" 19.37, "answer landed" 27.37); `run_390_log.json` ("answer landed" 20.38).
- Why a person would care: "Nearly half a minute for the flagship question."
- NOT CLOSED

### PR-94-10: The count reads 141,360 isolates where query 33's line says 140,476
- Kind: answer
- Verdict: needs your eye
- What: "Pathogen Detection lists 141,360 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown." Query 33 expects 140,476. Most likely Pathogen Detection grew since the document was written; not caused by card 94.
- Evidence: `run_1280_log.json` and `run_390_log.json` (`answer.text`, Notes).
- Why a person would care: only a tester comparing against the document.
- NOT CLOSED

## Result

| Width and depth | Card 94 result | Rests on |
|---|---|---|
| 1280, Researcher | Pass on what was seen (PR-94-01, PR-94-04): page 1's ten rows read "Not recorded", true to their records | `run_1280_log.json`, `1280_table_viewport.png` and four BioSample records, all read by the reviewer |
| 390, Plain language | Pass (PR-94-03, PR-94-04, PR-94-05): page 2 shows "2011, France: Bordeaux" and the like, all ten matching BioSample; overflow 0 | `390_table_page2_viewport.png`, `390_table_page2_full.png`, `run_390_log.json` and ten BioSample records, all read by the reviewer |

Card 94 changes the answer, so it waits for the owner's verdict whatever this pre-screen says.

## What was not captured

- Questions spent: three, not two. The first, at about 05:54 UTC, failed on the reviewer's own dropped network ("network error", `attempt0_1280_answer_viewport.png`); the coordinator asked for the check to be run again, and the two briefed questions followed at 10:57 and 10:59 UTC.
- Page 2 at 1280 was not opened: the script learned to page only after the 1280 run. Page 2 was read at 390 only, and from screenshots rather than page text.
- The places were checked against BioSample records fetched from E-utilities (fourteen rows), not against the Pathogen Detection isolate page itself, which is a script-drawn page the capture did not render. Pathogen Detection takes its place and date from BioSample.
- The rows "2013, place not recorded" and "USA: Minnesota, date not recorded" from query 33's line did not occur in this answer; the "place, no date" and "date, no place" halves were not seen on screen. "Both" and "neither" were.
- The full-page shots at 390 draw the sticky header and footer part way down the page (over the 11-02093 row in `390_table_page2_full.png`); that is how a full-page capture paints fixed bars, not what a phone shows. The row reads "2011, Germany: Rostock" in `390_table_page2_viewport.png`.
- No prototype comparison and no golden run: neither was in this brief.
- Every verdict above rests on a log, screenshot or BioSample record the reviewer read itself; PR-94-07 also rests on the test document's wording.

The BioSample records were fetched on 2026-10-09 and read by the reviewer; they are not kept in the repository because they name the people who submitted them. Each can be read at `https://www.ncbi.nlm.nih.gov/biosample/<accession>`.
