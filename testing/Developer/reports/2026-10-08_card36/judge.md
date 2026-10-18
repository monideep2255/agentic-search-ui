# Card 36 judge report, round 1

Judge base: HEAD a6d67d3cd66961fb2ad4c6839417d00ed7a0d54a, compared with origin/develop. Findings are written as they are established.

## Findings

### J-36-01: the note fires on words a person typed, not only on our own offered option

- Severity: major (against the brief's line "the helper may match only the product's own fixed option strings, never free text")
- Evidence: `is_recent_window_option` (`core/clarify.py:375` to `:388`) accepts any text that ends with " from <fixed phrase>?". The part before the suffix is whatever the person wrote, so the helper cannot tell our chip from a typed question; the build notes say so under Deviations. Probe through the real graph with no offer ever made (`_install_decide()` with its safe picks):

  ```
  TYPED: What do studies say about statins from the last 5 years? | note: True | pubmed: ['statins'] | ... for: statins; the date range you chose could not be applied, so papers from any year were searched
  TYPED: Is BRCA1 linked to cancer from the last 12 months? | note: True | pubmed: ['BRCA1[Title/Abstract]'] | ... the date range you chose could not be applied, so papers from any year were searched
  ```

  The second person never picked a date range for papers; "from the last 12 months" may describe the cancer. The plan line tells them "the date range you chose could not be applied". The module's own header says "text nobody was offered, however it is worded, limits nothing" (`core/clarify.py` comment above `_OFFER_TTL_S`); this helper keeps that for the search but now lets the same typed words change what the plan line says.
- Why it matters: a decision about what the question means (did the person pick a range?) is now made by matching the person's words in code. That is the shape the owner's standing rule forbids.
- Smallest fix: an owner call, asked as one question. Either (a) accept the deviation in a `DECISIONS.md` row and reword the note so it is true for typed text too (for example "no date limit was applied, so papers from any year were searched"), or (b) gate the note on something the product itself stored, which today exists only in process memory and is lost by the same restart.

### J-36-02: the note says papers were searched when no paper search was planned (inside this card's fix)

- Severity: minor (rare trigger; the applied-window sentence beside it has the same gate and the same gap, present before this card)
- Evidence: the gene path appends the note whenever `gene_curie is not None or disease_text` (`core/graph.py:7144` to `:7145`), not when a PubMed search was planned. Probe, a CURIE written in the question so no gene symbol reaches the PubMed term:

  ```
  NOPUB: Recent papers on NCBIGene:672 from the last 5 years? | note: True | pubmed: [] | searching 2 layers for NCBIGene:672. Layer 1, the knowledge graph: cypher_query; Layer 2, live NCBI records: ncbi_efetch; the date range you chose could not be applied, so papers from any year were searched
  ```

  `pubmed: []`: no PubMed search ran, and the plan line says "papers from any year were searched".
- Smallest fix: add the note only when a planned call has the `pubmed_search` purpose (the same test `_follow_up_calls_for` already keys on), and apply the same gate to the applied-window sentence at `core/graph.py:7140`.

## Checks with evidence

- Correctness, both plan paths, through the real five-node graph with models and `decide()` stubbed (helpers from `test_bare_topic_clarification.py`), every offered option, offer kept and offer cleared:

  ```
  OFFERED lost= False Recent papers on BRCA1 from the last 5 years? | note: False | pubmed: ['BRCA1[Title/Abstract] AND ("2021/10/09"[dp] : "3000"[dp])'] | ... PubMed papers published in the last 5 years only
  OFFERED lost= False Recent papers on statins from the last 5 years? | note: False | pubmed: ['statins AND ("2021/10/09"[dp] : "3000"[dp])'] | ... published in the last 5 years
  OFFERED lost= True Recent papers on BRCA1 from the last 5 years? | note: True | pubmed: ['BRCA1[Title/Abstract]'] | ... the date range you chose could not be applied, so papers from any year were searched
  OFFERED lost= True Recent papers on statins from the last 5 years? | note: True | pubmed: ['statins'] | ... the date range you chose could not be applied, so papers from any year were searched
  ```

  All six offered options behave the same way (12 months, 5 years, 10 years on each path). The note appears only when the window was not applied and never when it was; the lost window is never re-applied (no `[dp]` in the lost searches). Narrative lengths 175 and 280, under the 500 cut, so the note is never truncated in these shapes.
- Owner's classifier rule: the helper compares against the fixed `RECENT_WINDOW_PHRASES` (`core/clarify.py:254` to `:259`) but accepts any prefix, so typed text triggers it: J-36-01. It never yields a window and never changes a search.
- Security: no query, no log line, no new parsing of anything but a fixed suffix. `ruff check` on the four changed Python files: "All checks passed!".
- Tests: `test_clarify.py` "39 passed in 0.34s"; `test_bare_topic_clarification.py` "46 passed in 8.10s"; `tests/system_03_search_agent/core` "1389 passed, 56 skipped, 2 warnings in 79.43s".
- Mutations, each restored with `git checkout` (results for `test_clarify.py`, then `test_bare_topic_clarification.py`): site 1 off "39 passed" / "1 failed, 45 passed"; site 2 off "39 passed" / "1 failed, 45 passed"; note also on an applied window "39 passed" / "1 failed, 45 passed"; helper always true "1 failed, 38 passed" / "46 passed"; length guard removed "39 passed" / "46 passed"; "?" not required "1 failed, 38 passed" / "2 failed, 44 passed"; second half of the note dropped "39 passed" / "2 failed, 44 passed". The length-guard survivor is an equivalent mutant: after `strip()` the text cannot start with the suffix's leading space, so the guard can never decide anything. Not filed. `git diff --stat HEAD` empty afterwards.
- Documentation: query 108 is a new, unique number (`testing/Test_queries_and_workflows.md:1580`). Query 84's "Known: after develop restarts or redeploys, a choice clicked on an earlier question searches without the year limit." is still true; it could now add "and the plan line says so". Not filed.

## Verdict

FIX FIRST: J-36-01 (major, needs the owner's call on typed text and the note's wording). J-36-02 (minor) sits inside this card's fix and is a one-condition change worth taking in the same round.
