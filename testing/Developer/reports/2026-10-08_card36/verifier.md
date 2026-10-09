# Card 36 fresh verifier report

Verifier checkout: <repo-root>, HEAD 9d4ea328 (git rev-parse HEAD matched the expected tip). Base: origin/develop. No live model calls; probes are local Python and targeted pytest runs.

## Findings

### V-36-01: the helper's docstring and the code comment claim properties the fix round removed

- Severity: minor (documentation of the rule, not behaviour); unsure whether it touches the owner's standing rule
- Regression of: J-36-01 (fix commit 9d4ea328 made typed text a deliberate trigger without updating the helper's own description)
- What: `is_recent_window_option` (`src/system_03_search_agent/core/clarify.py:375` to `:388`) says "It verifies our own fixed strings and reads no free text" and "It exists so the plan can say honestly that a click on our own option could not be applied". It accepts any free-text prefix followed by " from <fixed phrase>?", and since the fix round that typed-text match is intended. The comment at `core/graph.py:6711` to `:6714` calls the wording an "owner decision, 2026-10-08", and build.md says the same. The DECISIONS.md row (commit 7d39ab3e, on `chore/overnight-2026-10-08-night`, not yet on develop or on this branch) says "Decided by the lead on the owner's behalf overnight".
- Reproduction: probe test (removed after the run) through the real graph with models and `decide()` stubbed, HEAD 9d4ea328, no offer ever made:
  ```
  PROBE typed helper=True 'Is BRCA1 linked to cancer from the last 12 months?' | note=True | ... ; the date range in your question could not be applied, so papers from any year were searched
  PROBE typed helper=True 'Did statins trials enrol patients aged 60 from the last 10 y' | note=True | ... ; the date range in your question could not be applied, so papers from any year were searched
  ```
- Why it matters: on the owner's standing rule. The helper still compares only against the product's fixed phrase list and never yields a window or changes a search (searches identical to develop, below), so it decides nothing about which papers are searched. It does decide, by a suffix match on the person's words, to tell them their question held a date range meant for papers: in the first example "from the last 12 months" may describe the cancer, not the papers. The sentence stays literally true (no year limit was applied). The owner has not seen this call; the lead made it. Filed so the owner can confirm it, not as a blocker.
- NOT FIXED

### V-36-02: the note follows the planned PubMed call, not one that ran

- Severity: unsure (not probed; same property as the applied-window sentence beside it on develop)
- What: both sites test `planned_tool_calls` for a `pubmed_search` purpose at plan time (`core/graph.py:7009` to `:7011`, `:7151` to `:7153`). The ticket says "only when a paper search ran". On the gene path the breadth calls are planned after the answer calls so that the Section 21.3 call ceiling skips them first (comment at `core/graph.py:7086` area), so a skipped PubMed call would still carry "papers from any year were searched".
- Reproduction: read only. Not reached in my probes (every planned PubMed search ran).
- Why it matters: rare, and the develop sentence "PubMed papers published in ... only" has the same gap. Not worse than develop in kind.
- NOT FIXED
## Fix-round findings, re-derived

- J-36-01, A-36-01, A-36-02 (typed text and wording): implemented as the DECISIONS.md row describes. New wording present on both paths, typed text ending like an option gets it (probe lines above). Not a code defect; see V-36-01 for the attribution and the stale docstring.
- J-36-02 (note with no paper search): FIXED. Probe, HEAD:
  ```
  PROBE typed helper=True 'Recent papers on NCBIGene:672 from the last 5 years?' | note=False | len=120 | pubmed=[] | searching 2 layers for NCBIGene:672. ...
  PROBE typed helper=True 'What is NCBIGene:672 from the last 5 years?' | note=False | len=120 | pubmed=[] | ...
  ```
  Mutation, gene-path gate reduced to `elif window_lost:`: "1 failed, 87 passed", `test_no_note_when_no_paper_search_was_planned`. Restored.

## Worse than develop

- Note never shown when the window was applied: all six offered options (12 months, 5 years, 10 years on the topic path and the gene path) with the offer kept gave `note=False` and a `[dp]` limit, for example `'Recent papers on BRCA1 from the last 10 years?' | note=False | pubmed=['BRCA1[Title/Abstract] AND ("2016/10/09"[dp] : "3000"[dp])'] | ... PubMed papers published in the last 10 years only`. With the offer cleared: `note=True`, PubMed `['BRCA1[Title/Abstract]']` and `['statins']`, no `[dp]`. `publication_window` is the only date limit in the code (`[dp]` is built only in `core/breadth_plan.py:519`), and `window_lost` requires it to be None (`core/graph.py:6717`). Mutation dropping that condition and the applied sentence: "2 failed, 86 passed" (`test_an_applied_window_does_not_carry_the_not_applied_note`, `test_a_picked_window_reaches_a_gene_question_s_pubmed_search`). Restored.
- Note never shown when no paper search ran: see J-36-02 above.
- Searches unchanged against develop: the same eight typed questions run through the same probe with develop's `src` (extracted from origin/develop to the scratchpad, `-o pythonpath`) and with HEAD. A diff of the two outputs differs only in the three narratives that gained the note; every PubMed term and every other narrative is identical, including `What is BRCA1?`, `papers on statins` and `Papers from the last 10 years on BRCA1?`.
- Owner's standing rule: the helper matches only against `RECENT_WINDOW_PHRASES` and never yields a window or changes a search (confirmed by the identical searches). It does read the end of typed text to decide whether to show the note, by the lead's overnight call rather than the owner's: V-36-01.
- Narrative length: longest seen 287 characters, under the 500 cut, so the note was never truncated in these shapes.

## Items left open

- A-36-03 (note only in the plan line, the answer is not told): develop tells the person nothing anywhere, so no worse.
- A-36-04 (a second offer drops the first offer's windows): pre-existing; HEAD now says the range was not applied, so no worse.
- A-36-05 (organism and fallback paths carry no note): same silence as develop, no worse.

## Tests run

- `core/test_clarify.py`: "39 passed in 0.14s".
- `core/test_bare_topic_clarification.py`: "49 passed in 6.30s".
- `tests/system_03_search_agent/core`: "1392 passed, 56 skipped, 2 warnings in 57.15s".
- The probe file was moved out of the checkout before these runs; `git status --short` clean afterwards.

## Verified by own probe versus read

- Own probe: applied and lost windows on both paths for all three options, the no-paper-search case, typed shapes, the develop comparison, two mutations.
- Read only: V-36-02 (call ceiling), A-36-03 rendering.

Verdict: MERGE. Nothing a person sees is worse than develop: searches are identical, the note appears only when no date limit was applied and a PubMed search was planned. V-36-01 asks the owner to confirm the typed-text call the lead made, and to correct the stale docstring.
