# Card 36 adversary, round 1

- Checkout: the adversary checkout, HEAD a6d67d3cd66961fb2ad4c6839417d00ed7a0d54a, merge base with origin/develop c916cfa30f59802dfd85c81ef7ba39bdcfc2b263
- Method: own probes (small scripts and single test files), no live model calls

## Findings

### A-36-01: the note depends on punctuation and position, so the same ignored range is disclosed or silent by the question mark
- Severity: minor
- What: `is_recent_window_option` is an `endswith(" from <phrase>?")` check, case-sensitive and needing the final "?". A typed range that is equally not applied gets the note or silence depending on where it sits and how it is punctuated. A lost click always matches (our own option text), so the card's own scenario holds; the inconsistency is on typed text, which the build report's Deviations already says gets the note.
- Reproduction: probe test test_zz_adv36_probe.py (removed after the run), HEAD a6d67d3c, decide stubbed to safe picks, fresh session. Every case searched PubMed as `['BRCA1[Title/Abstract]']`, no `[dp]`:
  - `Recent papers on BRCA1 from the last 10 years?`: note=True
  - `What did BRCA1 studies find from the last 5 years?`: note=True
  - `Papers from the last 10 years on BRCA1?`: note=False
  - `recent papers on brca1 FROM THE LAST 10 YEARS?`: note=False
  - `Recent papers on BRCA1 from the last 10 years` (no "?"): note=False
  - `Recent papers on BRCA1 from the last 10 years ?`: note=False
- What a person sees: two people type the same range, both get papers from any year; one is told, the other is not. Not a regression (silence was the behaviour before), but the signal's presence carries no information.
- NOT FIXED

### A-36-02: on a range the person typed (never offered), the note says "the date range you chose could not be applied", which reads as a failure of ours
- Severity: minor (wording; unsure whether the owner wants typed ranges disclosed differently)
- What: for a typed question the range was never going to be applied by design (F-8.2-A07: only an offered pick limits). The note frames it as a choice that failed, and offers no next step (no "pick a range from the choices" or "ask again").
- Reproduction: same probe, `What did BRCA1 studies find from the last 5 years?` in a session with no offer gave plan narrative `searching 3 layers for NCBIGene:672. Layer 1, the knowledge graph: cypher_query; Layer 2, live NCBI records: ncbi_efetch; Layer 3, literature and trials: pubtator_annotate, clinicaltrials_search; the date range you chose could not be applied, so papers from any year were searched`.
- What a person sees: "could not be applied" suggests retrying might work; it will not, for typed text. The decide-from-the-user's-chair rule asks that a refusal says what to type next.
- NOT FIXED
### A-36-03: the note reaches only the reasoning log; the answer the person reads, and the writing model, are told nothing
- Severity: major (unsure: rests on reading plus the frontend source, model prose not probed live)
- What: the note is appended to `PlanPayload.narrative` only. In the web client that string is rendered as a "Plan" step of the reasoning log (`frontend/src/hooks/useRunView.ts` lines 1031 to 1032), not in the answer. The Write step receives `question=query.text`, which still says "from the last 10 years?", and nothing in `synthesis/` or the write path mentions the publication window (grep for `window` in `src/system_03_search_agent/synthesis/*.py` finds only the findings-prompt window and an abbreviation window). So the model answers a question that asks for the last 10 years, over papers from any year, with no instruction that the range was dropped.
- Reproduction: lost-offer probe (offer for "recent papers on statins", `clear_offered_windows()`, click option 2) gave plan narrative `no gene, variant or disease was named, so searching the published literature for: statins; the date range you chose could not be applied, so papers from any year were searched` and PubMed term `['statins']`. Query 108's "The answer heading does not claim a window that was not used" is asserted by no test in this diff.
- What a person sees: possibly an answer that opens "Over the last 10 years, studies show..." citing a 1998 paper, while the honest note sits in a log they must open. The ticket's words are met ("the plan line says so"); the person's need may not be.
- NOT FIXED
- Correction to A-36-03's reproduction: the quoted statins narrative came from the two-offers probe (A-36-04 below), not from a `clear_offered_windows()` run. The card's own test `test_a_picked_window_whose_offer_is_lost_says_it_was_not_applied` covers the restart case and passes; the narrative shape is the same.

### A-36-04: a second "How far back" offer in the same session silently drops the first offer's windows, with no restart
- Severity: minor (the new note makes this honest; recorded because query 108 and the Known line in query 84 name only a restart)
- What: `offer_recent_windows` replaces the session's whole offer map. A person who asks two recent-work questions, then clicks a chip still on screen under the first, gets no date limit.
- Reproduction: same probe file, one session: offer for "recent papers on statins", then offer for "recent papers on BRCA1", then click statins option 2 (`... from the last 5 years?`). Output: `[first offer clicked after second] plan='no gene, variant or disease was named, so searching the published literature for: statins; the date range you chose could not be applied, so papers from any year were searched'`, PubMed `['statins']`. Then BRCA1 option 2: `PubMed papers published in the last 5 years only`, term with `("2021/10/09"[dp] : "3000"[dp])`.
- What a person sees: the plan log now says the range was not applied, which is true. The chip they clicked was offered moments earlier in the same conversation, so "could not be applied" with no reason is puzzling. The test-queries document tells testers it happens only after a restart.
- NOT FIXED

### A-36-05: the paths that plan no date-limited search carry no note when a picked window is lost
- Severity: unsure (read only, not probed)
- What: `window_lost` is surfaced only in the topic branch and in the gene or disease branch. The organism branch (`searching NCBI ... by organism alone`) and the fallback `selected cypher_query for a Layer 1 graph lookup` carry neither the applied-window wording nor the lost note.
- Reproduction: graph.py at HEAD a6d67d3c, the organism `PlanPayload` (around line 6945) and the `else` at about line 7012 have no `window_lost` reference.
- What a person sees: someone who clicked "from the last 5 years" on a question that lands on these paths gets no word about the range at all. Pre-existing silence; recorded because the card's promise is "the plan line says so".
- NOT FIXED
- Note on the probe file: it was moved out of the checkout to the session scratchpad (`test_zz_adv36_probe.py`), not deleted; the checkout is clean.

## Verdict

- FAIL is not claimed: the card's own scenario (offer lost on restart, then a click) shows the note on both plan paths, and an applied window never shows it. Verified by my own probes: applied windows on BRCA1 and statins for all three options (no note, `[dp]` present), typed variants, two offers in one session. Read only: A-36-03 (frontend rendering and the Write prompt) and A-36-05.
- Verdict: PASS against "the plan line says so", with A-36-03 (major, unsure) as the open question of whether a log line is what the person needs. No finding sits inside a fix made during this phase.
