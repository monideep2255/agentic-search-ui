# Card 22 judge report

Judge round 1, fresh context, 2026-10-06. Branch `fix/card22-name-every-total` against origin/develop d8179c4e. Findings are appended as they are established; the checklist and verdict come last.

## Table of contents

- [Findings](#findings)
- [Checklist](#checklist)
- [Not covered](#not-covered)
- [Verdict](#verdict)

## Findings

### J-22-01: the two page keys differ on four whitespace characters
- Blocking: no (minor; not reachable through a valid citation today)
- Where: `src/system_03_search_agent/synthesis/trust.py:568` (`.strip()`), `frontend/src/components/screens/AnswerScreen.tsx:507` (`.trim()`)
- What: Python's `str.strip()` and JavaScript's `String.trim()` use different whitespace sets. The keys disagree on a leading U+FEFF (byte order mark, stripped by the frontend only) and on trailing U+001C to U+001F and U+0085 (stripped by the backend only).
- Evidence: my own probe ran both real functions over 24 inputs (scratch file `cases.json`). 21 agree. The three that differ: `'﻿https://x/'` gives `'﻿https://x'` in Python and `'https://x'` in TypeScript; `'https://x/\x1c'` gives `'https://x'` and `'https://x/\x1c'`; `'https://x/\x85'` gives `'https://x'` and `'https://x/\x85'`. The build report and the fixture say the two are "the same rule tested against the same cases"; the shared fixture has no non-ASCII whitespace case.
- In the user's words: none today. `NCBI_SOURCE_URL_PATTERN` (`contracts/events.py:181`) rejects every one of these characters, so no citation card can carry them. The backend, however, counts `claim.finding.source_url`, which is not held to that pattern, so the claim "identical on every input shape" is not literally true.
- Suggested fix: strip only ASCII whitespace in both (`strip(" \t\n\r\f\v")` and a `/^[ \t\n\r\f\v]+|[ \t\n\r\f\v]+$/g` replace), or state in both docstrings that the key is only defined on pattern-valid URLs.
- NOT FIXED

### J-22-02: a live gene citation merged into a graph card is labelled "L1 · graph", and the answer's live layer disappears
- Blocking: yes. This sits inside this card's own fix (the page key made the cross-layer merge reachable), which is the review loop's stop condition.
- Where: `frontend/src/components/screens/AnswerScreen.tsx:552-581` (`groupSourcesByLayer`, merged card takes the first citation's layer), `:515-521` (`citedSourceCounts`, layers counted as groups), `frontend/src/hooks/useRunView.ts:1175-1182` (meta line)
- What: when an answer cites the graph's gene link (`tools/cypher_provenance.py:231`, no slash, layer 1) and the live Datasets gene link (`tools/ncbi_datasets_actions.py:327`, trailing slash, layer 2), the two citations now become one card filed under Knowledge graph and labelled "L1 · graph" while carrying both markers. The prose marker for the live citation still says layer 2. If that was the only live citation, the Live NCBI APIs group vanishes and the meta line says one layer.
- Evidence: my own probe (scratch worktree, real `useRunView` and `AnswerScreen`), events: a cypher_query and an ncbi_datasets tool result, citation 1 `https://www.ncbi.nlm.nih.gov/gene/672` on `layer_1_graph`, citation 2 `https://www.ncbi.nlm.nih.gov/gene/672/` on `layer_2_api`, each on its own sentence. Rendered: meta "2 tool calls · 1 source cited from 1 layer"; Sources "Knowledge graph 1 ▶ [1][2] NCBIGene 672 L1 · graph"; `sources-group-2` absent; marker `citation-2` has `data-layer="2"` and `aria-label="Source 2, layer 2"`; `view.layerCount` is 2. On develop the same events give two cards in two groups and "from 2 layers".
- In the user's words: "I clicked marker 2 and it says it came from a live NCBI lookup; the Sources list files marker 2 under the knowledge graph snapshot and says the answer drew on one layer. Which is it?" The label on the card is false for one of its two markers, and the reader loses the fact that the answer was checked against live NCBI. F-4.9-A-04's rule is that each source names its own layer. The build report records this as a deliberate choice ("one page, one card"), but the card's own goal is that every label is true, and this label is not.
- Suggested fix: keep one card per page but give it every layer its markers came from (for example "L1 · graph, L2 · live") and count the meta line's layers over the citations, not the groups; or key the grouping by layer plus page and accept that the cross-layer case is two cards counted once, stated on the heading. Either way, add the cross-layer case to the unit test with the marker's layer asserted against the card's.
- NOT FIXED

### J-22-03: "Confirmed by N independent databases" counts every database the answer cites, not the ones that confirmed
- Blocking: no (major, pre-existing number; this card renamed its noun and wrote the info card that describes it, so the label is now this card's words)
- Where: `src/system_03_search_agent/synthesis/trust.py:652` (`database_count` over all claims), `:663` (the line), `frontend/src/components/screens/AnswerScreen.tsx:95-99` (info card: "Confirmed means two or more independent databases agree on the same high-stakes fact")
- What: N is the number of distinct origin databases across every grounded claim, low-risk claims included. It is not the number of databases that agree on the high-stakes fact. Where a finding has no CURIE, the "database" is the tool name, so one page fetched by two tools counts as two databases.
- Evidence: my own probes against the real `answer_trust_line`. (a) One high-risk claim marked concordant (ClinVar) plus four low-risk claims from MedGen, NCBIGene, MeSH and a trial: output `'Confirmed by 5 independent databases'`. (b) Two citations of `https://www.ncbi.nlm.nih.gov/gene/672` and `.../gene/672/`, both with an empty CURIE, tools `cypher_query` and `ncbi_datasets`, one high-risk concordant claim: output `'Confirmed by 2 independent databases'`, while the Sources list for the same pair shows one card (J-22-02 probe).
- In the user's words: "It says five databases confirmed this. Two did; the other three are about something else." From the chair: a confident overstatement of corroboration is worse than no number. The info card, rewritten by this card, tells the reader exactly the reading that is false.
- Suggested fix: count the databases behind the concordant high-risk claims only (the triangulation verdict already knows them), or word it "Confirmed by two or more independent databases" with no number. Never count a tool name as a database. A follow-up card if the owner prefers, since it changes a number, not only a word.
- NOT FIXED

### J-22-04: a reopened saved answer says "Based on 16 sources cited" over a Sources list of 18 rows
- Blocking: yes, against the card's stated intent ("every number on an answer that says sources equals the source cards a person can open and count"); the lead may rescope it to a follow-up card, since the saved-answer list was not in the build's file fence and the brief did not name it out of scope
- Where: `frontend/src/components/screens/SavedAnswerScreen.tsx:259-270` (stored trust line) and `:285-303` (one row per citation, no page key)
- What: the saved-answer screen shows the stored trust line, which this card now computes over distinct pages, above a Sources list that renders one row per citation with no grouping. On the BRCA1 evidence the number and the rows disagree, and the gene page is listed three times.
- Evidence: my own probe rendered the real `SavedAnswerScreen` with the card's fixture citations (18) and its expected trust line. Output: trust line "Based on 16 sources cited, not yet confirmed"; list items 18; rows naming gene 672: 3. Before this card the same screen read "Based on 17 sources" over 18 rows, so the disagreement is not new, but the card's claim that every "sources" number now matches what a person can count is false on this screen.
- In the user's words: "I reopened yesterday's answer. It says 16 sources and I count 18 under Sources, and BRCA1 is there three times."
- Suggested fix: render the saved list through `groupSourcesByLayer` (or at least dedupe by `sourcePageKey`, carrying every marker) so the rows match the stored number; add the saved screen to query 107.
- NOT FIXED

### J-22-05: the history rail says "16 sources cited" for a search, then "18 sources" for the same search after a reload
- Blocking: no (the build names it out of scope; recorded because this card created the split)
- Where: `frontend/src/App.tsx:264-277` (`formatHistoryMeta`, counts stored citations), `src/system_03_search_agent/feedback/history.py:146` (`_citation_count`), `feedback/capture.py:415` (stores one payload per citation event); live rail item takes `view.meta` (`App.tsx:1153-1179`)
- What: before the card, the live rail item and the restored one both read 18 sources. After the card the live item reads "13 tool calls · 16 sources cited from 3 layers" and the same item after a reload reads "18 sources · Oct 6". The MCP `past_searches` output carries the same 18 as `citation_count` (`adapters/mcp/server.py:491`).
- Evidence: read, not run. `formatHistoryMeta` prints `${citation_count} source(s)`; `citation_count` is `len(stored citations)`; capture stores every `citation` event payload (18 on the evidence, per the fixture).
- In the user's words: "My search said 16 sources. I refreshed the page and the same search now says 18."
- Suggested fix: count distinct `source_page_key` values in `_citation_count` (and the MCP field) or relabel it "citations"; a follow-up card if the owner agrees.
- NOT FIXED

### J-22-06: the command line prints "Based on 16 sources cited" above 18 references, the gene page three times
- Blocking: no (minor; same class as J-22-04, on the command line and the MCP `ask` output)
- Where: `src/system_03_search_agent/adapters/cli/render.py:1060-1105` (one reference line per citation); `adapters/mcp/server.py:411` and `:449-451` (the MCP output carries the trust line beside the full per-citation list)
- What: the build report says the command line "shows no other total". It shows no other number, but its References block is a list a person counts, one line per citation.
- Evidence: my own probe fed the fixture's 18 citations and the new trust line through the real `Renderer`. Output: "Based on 16 sources cited, not yet confirmed", then "References:" with lines [1] to [18], of which [1], [6] and [9] are `https://www.ncbi.nlm.nih.gov/gene/672/`, `.../gene/672` and `.../gene/672/`.
- In the user's words: "The terminal says 16 sources and lists 18."
- Suggested fix: group the references block by `source_page_key`, printing "[1][6][9] NCBIGene - ..." once, or say "18 citations to 16 sources" on the trust line for these surfaces.
- NOT FIXED

Process note: an adversary round is writing in this worktree at the same time (`adversary.md`, `raw/`). After my first mutation (M1, a few seconds, restored, `git status` clean of tracked changes) I moved every further mutation and probe to scratch worktrees of the same commit, so nothing I changed can have been seen by the adversary's runs except possibly M1's window.

### J-22-07: no test holds which layer a merged cross-layer card is filed under
- Blocking: no (test gap; it sits on the behaviour of J-22-02, inside this card's fix)
- Where: `frontend/src/components/screens/AnswerScreen.card22.test.tsx` ("counts layers as the Sources list groups them ..."), `frontend/src/components/screens/AnswerScreen.tsx:563-566`
- What: the build's docstring promises "filed under the layer cited first". Mutating the merge so the card takes the LAST cited layer (`existing.ns.push(source.n); existing.layer = source.layer;`) leaves every screen test green.
- Evidence: mutation M2 in a scratch worktree of f82c1230, `npx vitest run src/components/screens/`: "Tests 138 passed (138)". Restored with `git checkout --`, `git status` clean of tracked changes.
- In the user's words: a change that moves a gene's card from Knowledge graph to Live NCBI APIs, or back, ships without any check noticing.
- Suggested fix: assert the merged card's group and its layer label in the cross-layer test, and, per J-22-02, assert that each marker's layer is still visible on the card.
- NOT FIXED

### J-22-08: the rewritten info card says "not yet confirmed" means a high-stakes fact lacks a second database, but the line also appears when there is no high-stakes fact at all
- Blocking: no (major; inside this card's own rewrite of the info card text, so it counts toward the stop condition)
- Where: `frontend/src/components/screens/AnswerScreen.tsx:95-99` (new sentence "Not yet confirmed means a high-stakes fact has not been found in a second independent database."); `src/system_03_search_agent/synthesis/trust.py:664-665`; the `ask` floors in `core/graph.py:13382`, `:13414`, `:13466`, `:13485` (structured fallback, a named entity left unanswered, omitted findings, a failed background search)
- What: the trust line says "not yet confirmed" whenever the answer's outcome is `ask`. Four of the five ways to reach `ask` have nothing to do with a second database: they are floors for a partial or incomplete answer. The info card now explains every "not yet confirmed" as a missing second database.
- Evidence: my own probe: one low-risk claim with verdict `answer`, aggregated with the `ask` floor exactly as `core/graph.py:13466` does: outcome `ask`, line `'Based on 1 source cited, not yet confirmed'`. There is no high-stakes fact in that answer. The BRCA1 evidence itself carries the note "One of the background searches did not finish", one of these floors.
- In the user's words: "The info button says nothing high-stakes was double-checked. The answer had no high-stakes claim; the real reason was that a search did not finish." The old sentence ("rests on a single source") was also wrong for these cases, so this is not a regression in truth, but the card rewrote this exact sentence to make it true and it still is not.
- Suggested fix: word the card for every cause, for example "Not yet confirmed means a high-stakes fact has not been found in a second independent database, or the answer may be missing records; the notes above say which.", or have the trust line name its reason.
- NOT FIXED

### J-22-09: two comments state numbers and rules the code no longer has
- Blocking: no (minor, documentation in code)
- Where: `frontend/src/hooks/useRunView.ts:1171-1172` says the meta line now reads "13 tool calls · 17 sources cited from 3 layers"; the card's own fixture and screenshot show 16. `src/system_03_search_agent/synthesis/trust.py:623-624` (docstring of `answer_trust_line`) still says `citation_count` is "keyed by exact `source_url`", which this card changed to `source_page_key`; the same paragraph still carries the old typo "Based on N source(s))".
- Evidence: read; `grep` shows both lines on the branch.
- In the user's words: none directly. A later builder who trusts the comment re-derives 17 or re-keys by exact URL, which is how the 18 against 17 split started.
- Suggested fix: 16 in the comment; "keyed by `source_page_key`" in the docstring.
- NOT FIXED

## Checklist

| # | Item | Verdict | Evidence |
|---|---|---|---|
| 1a | "13 tool calls" | True | Distinct `call_id`s over `tool_start` and `tool_result` (`frontend/src/hooks/useRunView.ts:500-527`); every one is a call the run made. Read, and seen as "2 tool calls" in my probe for two calls. |
| 1b | "16 sources cited" (meta) | True on the evidence; false layer story on a cross-layer merge | `citedSourceCounts` reads the list's own groups (`AnswerScreen.tsx:515-521`); probe: 16 on the fixture through the real hook and screen (author's test, re-run green). See J-22-02. |
| 1c | "from 3 layers" | True on the evidence; understated when one page is cited from two layers | J-22-02 probe: "from 1 layer" while marker 2 says layer 2 and `view.layerCount` is 2. |
| 1d | "Based on N sources cited" | True on the web screen for the evidence; not true on the saved-answer screen or the command line, which list one row per citation | J-22-04 and J-22-06 probes (16 against 18 rows). Backend counts `grounding.claims` (`core/graph.py:13848`), frontend counts citation events: equal except where a citation builder returns None (`core/graph.py:10700-10718`), not reproduced. |
| 1e | "Confirmed by N independent databases" | The noun is now right, the number is not what the words say | J-22-03 probes: 5 for one concordant fact; 2 for one page fetched by two tools without a CURIE. |
| 1f | Info card text | Partly true | "Sources cited counts the record pages ... two links to one page count once" is true. "Not yet confirmed means a high-stakes fact has not been found in a second independent database" is false for four of the five ways to reach `ask` (J-22-08). |
| 2 | One key on every input shape | Same on trailing slashes, repeated slashes, ASCII whitespace, empty, missing, query strings, fragments, case, http and https (none of the last four merged, on both sides) | My probe ran both real functions over 24 inputs: 21 identical; three differ on non-ASCII whitespace that the citation URL pattern rejects (J-22-01). Inputs where the three numbers can still disagree: a cross-layer merge (layers only, J-22-02); a citation whose builder returns None (backend counts it, no card; read, not run); `omim.org` beside `www.omim.org` (both admitted by `contracts/events.py:181`, not merged by either key; read). |
| 3 | Cross-layer merge | Fails | J-22-02 (blocking, inside this card's fix) and J-22-07 (no test holds the layer). On develop the same events gave two cards in two groups and "2 sources from 2 layers"; on the branch one card under Knowledge graph labelled "L1 · graph" carrying a live citation. |
| 4 | Saved answers, rail, follow-ups, command line, MCP | Disagreements remain | Saved answer: J-22-04 (run). Rail after reload: J-22-05 (read). Follow-up turns: each turn's meta comes from its own `useRunView` (`App.tsx:1339`, `AnswerScreen.tsx:2261`), same rule (read). Command line: J-22-06 (run). MCP: trust line passes through beside the full citation list and `citation_count` (`adapters/mcp/server.py:411`, `:451`, `:491`) (read). GraphQL passes the trust line through unchanged (`adapters/graphql/fold.py:823`, `:937`) (read). |
| 5 | End-to-end failures on develop | Confirmed pre-existing; no new failure from this branch | Scratch worktree of origin/develop d8179c4e, `npm ci`, `CI=1 npx playwright test e2e/trust-surface.spec.ts e2e/citation-host-allowlist.spec.ts`: 8 failed, 1 passed. Same command on the branch: the same 8 failed, 1 passed. Whole suite, load average about 50 from parallel work: develop 40 failed, 58 passed, 13 skipped; branch 30 failed, 70 passed, 13 skipped. The build's 19 is not reproducible on this machine at this load, so I compared sets. Branch-only failures were three: `rail-collapse.spec.ts:347` is develop's `:346` moved one line by this card's comment (same test, failing on both); `answer-layout.spec.ts:337` and `citations-and-writing.spec.ts:215` passed on a targeted rerun of the branch. In that rerun `card22-name-every-total.spec.ts` passed at 1280 and 390 and `tool-chip.spec.ts:173` passed; `rail-collapse.spec.ts:212` timed out in its sign-in helper before its first assertion (also failing on develop), and passed in the branch's whole-suite run. Scratch worktrees removed afterwards. |
| 6 | Tests and mutations | Card tests green; four of my five mutations caught, one survived | Backend `test_trust_line_names_its_count.py` plus `test_answer_layout.py`: 85 passed. Frontend `AnswerScreen.card22.test.tsx`: 19 passed. M1 heading counts `sources.length`: caught (1 failed). M2 merged card takes the last layer: survived, 138 passed (J-22-07). M3 `database_count` over page keys: caught (2 failed). M4 backend `removesuffix("/")`: caught (1 failed). M5 frontend single-slash regex: caught (1 failed). M1 ran in this worktree for a few seconds; M2 to M5 in a scratch worktree of f82c1230, each restored with `git checkout --` and confirmed at f82c1230 with no tracked change. This worktree: `git status` shows no tracked change. |
| 7 | Gates and leak scan | Pass | gate02 exit 0, gate03 exit 0 ("All checks passed!"), run on a clean checkout of f82c1230 with the main virtual environment first on PATH. `check_public_leaks.py --base origin/develop`: PASS, 0 findings; 10 binary files listed for a person to look at, including this card's two screenshots, which I looked at (no email or local path visible; sign-in masked). |

Correction to J-22-09: the stale docstring line in `trust.py` is 625, not 623-624.

## Not covered

- No live model call and no live NCBI call, as briefed. Every probe used the real functions with constructed events.
- I did not reproduce a citation builder returning None in a real run, so the backend-only count in that case is read, not run.
- I did not run gate04 (whole unit suite) or `npm test` in full; I ran the card's own backend and frontend tests and the whole `src/components/screens/` vitest folder under mutation M2 (138 passed).
- Plain-language depth: read only; the trust line and the meta line do not depend on depth.
- The build's two screenshots were taken by the builder; I looked at both but took none of my own.
- An adversary round wrote in this worktree at the same time; I did not read its report, so overlaps with its findings are possible.

## Verdict

FAIL.

Blocking:

- J-22-02: a live gene citation merged into a graph card is labelled "L1 · graph" and the answer's live layer disappears from the list and the meta line. This sits inside this card's own fix (the page key made the cross-layer merge reachable), which fires the review loop's stop condition: escalate to the product owner rather than run another round.
- J-22-04: a reopened saved answer says "Based on 16 sources cited" over 18 source rows. Not new in kind, but the card's stated intent is false on this screen; the lead may rescope it to a follow-up card.

Also inside this card's own changes, non-blocking: J-22-08 (the rewritten info card sentence is false for most "not yet confirmed" answers) and J-22-07 (no test holds the merged card's layer).

Verified with my own probes: both page keys over 24 inputs (J-22-01); the cross-layer merge on the branch and on develop (J-22-02); the confirmed line's number (J-22-03); the saved-answer screen (J-22-04); the command line (J-22-06); the `ask` floor wording (J-22-08); five mutations; the two named end-to-end specs on develop and on the branch; both whole suites; gates 02 and 03; the leak scan.

Only read, not run: the history rail after a reload and the MCP history count (J-22-05); MCP and GraphQL trust line pass-through; follow-up turns; the backend-only count when a citation builder fails; the two stale comments (J-22-09, confirmed by grep).
