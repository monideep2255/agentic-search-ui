# Card 63 verifier report, fix round (2026-09-28)

Fresh verifier, no prior context. Checkout: `.claude/worktrees/card63`, branch `fix/card63-tested`, HEAD `bc6cca1a`, fix UNCOMMITTED in the working tree (`git diff HEAD --stat -- src tests`: 8 files, 290 insertions, 32 deletions at the start of this round).

Method: for each finding, reproduce the original defect's shape against the new code with my own probe (not the fix agent's test), then mutate one property of the fix and confirm a test goes red, then restore from a scratchpad copy. Findings are appended the moment they are established. Closes below are mine only; the finder-is-not-closer split still holds for anything I did not verify myself.

## Findings and verdicts

### Probe 1: the A01 shape and nine siblings through the real loop (my own probe, not the fix agent's test)

`scratchpad/verifier/test_v_probe_loop.py`, importing only `test_breadth_wiring.py`'s fakes (`_ModelSpy`, `_install_lookup`, `_ToolSpy(failing=...)`, `_events`) and asserting my own expectations. Gene question "Which diseases are associated with BRCA1?", every tool faked, `10 passed in 6.72s`. Observed per case (summaries are the streamed `tool_result` summaries; the note is the `kind: "note"` token; "saved" is `answer_markdown_from(events)`):

- `pubmed_fetch_down` (search ok, then fetch `service_down`): summaries `search: 3 id(s)` then `fetch error: the service is down at NCBI`; note and saved block both exactly `PubMed is down at NCBI right now, so this answer may be missing papers from it. Try again later.`; the saved markdown still carries the `## Publication records found` table with `PMID:30000003`; `done` is `ask`.
- `clinvar_summary_down`: `summary error: the service is down at NCBI`; note `ClinVar is down at NCBI right now, so this answer may be missing variant records from it. Try again later.` beside the `## Clinvar records found` table.
- `omim_summary_down`: `OMIM is down at NCBI right now, so this answer may be missing records from it. Try again later.`
- `pubmed_search_down` (the search branch): `search error: the service is down at NCBI`; the same PubMed note.
- `two_down` (PubMed fetch + ClinVar summary): `PubMed and ClinVar are down at NCBI right now, so this answer may be missing sources from them. Try again later.`
- `three_down` (+ OMIM summary): `PubMed, ClinVar and OMIM are down at NCBI right now, so this answer may be missing sources from them. Try again later.`; `done: ask Based on 8 sources, not yet confirmed`.
- `mixed_down_and_timeout` (PubMed fetch down, ClinVar summary `timed_out`): `PubMed is down at NCBI right now, so this answer may be missing papers from it. Another background search did not finish, so other sources may be missing too. Try again later.`
- `mixed_down_and_rate_limited_same_db` (ClinVar search `rate_limited`, PubMed fetch down): the same two-sentence note; the ClinVar follow-up closed as `no ids to fetch: the clinvar_search search did not complete`.
- `fetch_timed_out_only` and `fetch_other_only`: `fetch error: timed out` / `fetch error: other failure`; note is `FAILED_SEARCH_NOTE` verbatim, ending "Ask again to retry."

In every case: none of `SOLR`, `temporarily unavailable`, `Search Backend`, `Cannot connect` appears in the JSON dump of every event payload or in the saved markdown; none of `has no `, `has nothing`, `search is down`, `searches are down`, `NCBI's searches` appears in any note or in the saved markdown; the note is present as its own `\n\n` block in the saved markdown.

### Probe 2: the note builder and the refusal chooser on edge inputs (my own probe, direct calls)

Direct calls to `_build_failed_search_note` and `refusal_message_for`, 17 inputs. Observed:

- Pre-card shape with no `kind`, `kind: None`, `kind: "bogus"`, `kind: "SERVICE_DOWN"`: note is `FAILED_SEARCH_NOTE` ("Ask again to retry."), refusal is `FAILED_SEARCH_MESSAGE`. A bogus or missing kind never produces the outage wording.
- `source` empty, `None`, `"bioproject"`, `"PubMed"` (cased), or NCBI's own outage text: the unnamed sentence `Some of NCBI's databases are down right now, so this answer may be missing sources from them. Try again later.` The source value never reaches the note (a `source` of `Search Backend failed: ... SOLR` prints the unnamed sentence).
- `reason` carrying NCBI's outage text: the note and refusal are unchanged, the reason text is not read.
- Duplicate PubMed entries: named once. `gds` + `gene`: `GEO DataSets and Gene are down at NCBI right now, so this answer may be missing sources from them. Try again later.` `medgen`: `MedGen is down ... may be missing records from it.`
- Down + timeout: the two-sentence note; refusal `SEARCH_DOWN_MESSAGE`.
- Down + a no-entity reason: the refusal is `UNRESOLVED_QUESTION_MESSAGE` (the no-entity reason still outranks the outage); the note (which only exists when the answer stands) is the PubMed note plus "Another background search did not finish".
- Down with a topic term: `SEARCH_DOWN_MESSAGE`; no failures with a topic term: the topic-not-found message. Empty list: `REFUSE_MESSAGE`.
- `build_refusal_text("BRCA1", SEARCH_DOWN_MESSAGE)` ends with the fallback link `https://www.ncbi.nlm.nih.gov/search/all/?term=BRCA1`.

### Probe 3: the topic path with the fetch down after a good search does NOT refuse (observation, not a defect)

`scratchpad/verifier/test_v_probe_refusal.py`, `test_topic_search.py`'s fakes with `ncbi_efetch` wrapped so `fetch` answers `service_down`. Observed: summaries `['search: 1 id(s)', 'fetch error: the service is down at NCBI', 'ok: 1 record(s)']`, `done: ask`, the answer reads `Found 1 publication record: 33388079 [1].` (grounded by PubTator's `annotate_publications`), and the note is `PubMed is down at NCBI right now, so this answer may be missing papers from it. Try again later.` A PubMed paper is cited above a note saying PubMed may be missing papers, which is the hedged shape the lead decided on and does not contradict the records. This is the A01 shape on the topic path and it reads correctly. My probe's premise (that it would refuse) was wrong; the refusal probe is re-run below with PubTator answering empty so nothing grounds.

### Frontend note patterns (read and evaluated, not rendered in a browser)

`HIDDEN_NOTE_PATTERNS` (`AnswerScreen.tsx:456`) is two `^Note: ` regexes; `SYSTEM_NOTE_PREFIXES` (`useRunView.ts:56`) is `CAP_NOTE_PREFIX` ("This query reached its resource limit"), seven `Note:` prefixes and the medical disclaimer, and `isSystemNote` is only consulted for a token with no `kind` (`useRunView.ts:780`); a `kind: "note"` token goes to `pendingNotes` (`:709`) and renders as the muted inline note (`AnswerScreen.tsx:1403`) after the `isHiddenNote` filter (`:1442`). Evaluated the five new note wordings and `FAILED_SEARCH_NOTE` against those regexes and prefixes in Python (no `node` on this machine): all five are `shown` and match no system prefix. No frontend file carries the old or the new wording (grep). Not verified in a browser.

### Probe 4: the refusal when a fetch (not a search) is down and nothing grounds (my own probe, real loop)

`scratchpad/verifier/test_v_probe_refusal2.py`: topic question Q6, PubMed search ok (`search: 1 id(s)`), fetch answers `status: "error"` with the outage text and the given kind, PubTator answers empty. `3 passed`:
- `service_down`: `done: refuse`; token text starts `A source I needed is down at NCBI right now, so I could not find grounded evidence this time. Try again later, or try NCBI's cross-database search: https://www.ncbi.nlm.nih.gov/search/all/?term=Are%20there%20...`; `trust_signal` `outcome=refuse scope=answer message=<SEARCH_DOWN_MESSAGE>`; no "A search I needed", no "ask again"; none of the NCBI fragments in any event payload.
- `timed_out` and `other`: `FAILED_SEARCH_MESSAGE` ("Ask again to retry"), so the chooser reads the kind.

Frontend refusal path: `useRunView.ts:600-640` classifies a refusal by the `trust_signal` event's `scope === "answer"` and `outcome === "refuse"`, not by the sentence; grep for "I needed", "down at NCBI", "Try again later" in `frontend/src` finds no match. The wording change cannot be mis-classified there.

### Mutation M1 (A01): the single-database sentence put back to "has no", nothing else touched

`graph.py` `_build_failed_search_note`: `may be missing ` -> `has no ` in the one-database sentence only (one replacement, count asserted 1). `test_write_failed_search.py test_breadth_wiring.py test_capture_saved_answer.py`: `6 failed, 66 passed in 9.52s`; the red arms are `test_an_answer_that_lost_a_search_to_an_outage_says_try_later_not_ask_again`, `test_the_outage_note_names_each_database_that_is_down_once`, `test_the_outage_note_says_when_another_search_also_failed`, `test_a_search_down_at_ncbi_says_so_in_our_words_and_says_try_later`, and both ids of `test_an_outage_after_a_successful_search_never_says_the_answer_has_none`. Restored from the scratchpad copy, `cmp` clean.

### Mutations M1b to M5: one property each, all red, all restored

Each mutation was a single string replacement with its count asserted to be 1, every symbol left intact; after each, the file was restored from the scratchpad copy and `cmp` reported no difference. Final `git diff HEAD --stat -- src tests`: `8 files changed, 290 insertions(+), 32 deletions(-)`, and the SHA-1 of `graph.py`, `refuse.py` and `ncbi_transport.py` equal the copies taken before any mutation.

- M1b (A01), multi-database sentence back to "has nothing from them": `1 failed, 53 passed`, red on `test_the_outage_note_names_each_database_that_is_down_once`.
- M1c (A01), unnamed sentence back to "NCBI's searches": `1 failed, 20 passed`, red on `test_an_outage_on_a_database_the_note_cannot_name_is_still_disclosed`.
- M2 (A02), `SEARCH_DOWN_MESSAGE` back to "A search I needed": `1 failed, 75 passed` over `test_write_failed_search.py test_topic_search.py`, red on `test_the_outage_refusal_says_a_source_is_down_not_a_search`. Note that the end-to-end topic test stays green under M2 because it compares against the constant, so the exact-string arm is the only one pinning the wording; that is enough, and it is one arm, not a claim of two.
- M3 (J01), `_SERVICE_DOWN_MARKERS` without "cannot connect": `1 failed, 182 passed`, red on `test_each_outage_marker_alone_makes_an_error_body_service_down[cannot_connect_only]`. The arm asserts each phrase carries exactly one marker before classifying, so it cannot pass through the other marker.
- M4 (J02), fetch/summary/link branch `failure_kind=None`: `5 failed, 49 passed`, red on the three direct arms and both A01 end-to-end ids.
- M4b (J02), that branch's summary reverted to the pre-card `"{action}: N record(s)"`: `5 failed, 28 passed`, same five arms.
- M5 (J03), ncbi_efetch timeout path `failure_kind="other"`: `1 failed, 32 passed`, red on `test_an_ncbi_efetch_timeout_records_the_timed_out_kind`. The arm reads the recorded `kind` itself (via a recording wrapper around the real note builder) and asserts exactly one `timed_out` from `ncbi_efetch` and no `other`, so a subject that recorded nothing or the old value fails it.

### Other gates and untouched findings

- `tests/system_03_search_agent/synthesis/test_required_paths.py tests/system_03_search_agent/adapters/cli/test_render.py`: `87 passed in 4.97s`. The nine named files together (baseline before any mutation): `397 passed in 8.12s`.
- `ruff check` (no path, the whole repository, as gate 3 runs it): `All checks passed!`, exit 0. `isort --check-only --diff src tests services tracker alembic .claude .github` (the exact `gate02` command): `Skipped 2 files`, exit 0.
- The fix's source hunks (`git diff HEAD -U0 -- src`) are confined to `_build_failed_search_note` (lines 9161 to 9234), one comment in `_write_answer` (12588), and `refuse.py`'s comments, `SEARCH_DOWN_MESSAGE` and the `refusal_message_for` docstring. `capture.py` and `ncbi_transport.py` have no working-tree diff; `graph.py:6750` and `:7381` (`"error": output.error`, J04) are unchanged. So F-63-A03, F-63-A04 and F-63-J04 were neither fixed nor altered, as briefed, and remain open with their original text.
- `git status --short`: the eight src/tests files of the fix, the two report files the lead edits, the judge's and adversary's reports, and this file. Nothing else.

## Per-finding verdicts

- F-63-A01: CLOSED (verified). Probe 1 reproduced the original shape (PubMed search ok, fetch `service_down`; ClinVar summary `service_down`) through the real loop: the note reads `PubMed is down at NCBI right now, so this answer may be missing papers from it. Try again later.` beside the `## Publication records found` table, streamed and saved alike, and never "has no"; one, two and three named databases and the unnamed sentence all match the lead's required wording; mixed kinds keep the "Another background search did not finish" sentence. M1, M1b and M1c each went red on a test.
- F-63-A02: CLOSED (verified). Probe 4 drove a refusal through the real loop with the FETCH down and nothing grounding: the token text and the `trust_signal` message are exactly `A source I needed is down at NCBI right now, so I could not find grounded evidence this time. Try again later, or try NCBI's cross-database search:` followed by the fallback link; the note never says "search is down" (probe 1). M2 went red.
- F-63-J01: CLOSED (verified). M3 (marker tuple without "cannot connect") went red on `cannot_connect_only`; the arm asserts each phrase carries exactly one marker, so it cannot pass through the other.
- F-63-J02: CLOSED (verified). M4 (`failure_kind=None` on the fetch/summary/link branch) and M4b (that branch's summary reverted) each went red on the three direct arms and both A01 end-to-end ids; the populate arm (`fetch: 1 record(s)`, no kind, empty source) reads the same call answering `ok`.
- F-63-J03: CLOSED (verified). M5 (`failure_kind="other"` on the ncbi_efetch timeout path) went red on `test_an_ncbi_efetch_timeout_records_the_timed_out_kind`, which reads the recorded kind itself and also asserts the note stays `FAILED_SEARCH_NOTE`.
- F-63-A03, F-63-A04, F-63-J04: NOT IN THIS ROUND, unchanged, still open.

No new finding. Two observations, neither a defect: `PROGRESS.md:685` still describes the card as "an answer says plainly when NCBI's search is down" (prose about the feature, not the note's wording; the fix agent already left it for the lead); and no end-to-end arm exercises a failed `link` action because the gene question plans none, so the `link` case rests on the direct `_execute_planned_call` arm alone.

## Verdict

MERGE. All five findings the fix round took are closed on my own probes and mutations; nothing new was found inside the uncommitted fix, so Rule 4 does not fire. The three findings deliberately left out of the round (A03, A04, J04) are untouched and remain open for the lead.

Verified by my own probe or mutation: the A01 shape through the real loop on fetch, summary and search (probe 1, ten cases); the builder and chooser on 17 edge inputs including missing, `None`, bogus and upper-cased kinds, unknown, empty and hostile sources, a no-entity reason outranking an outage, and a topic term (probe 2); the topic path with a fetch down while PubTator still grounds (probe 3) and with nothing grounding (probe 4); absence of NCBI's text in every event payload and in the saved markdown (probes 1, 3, 4); every claimed red in the builder's fix-round section re-derived with my own single-property mutations (M1, M1b, M1c, M2, M3, M4, M4b, M5) and the tree restored byte for byte; the cite-or-refuse files; ruff and the gate-form isort.

Read only: the frontend patterns (`HIDDEN_NOTE_PATTERNS`, `SYSTEM_NOTE_PREFIXES`, the structural refusal classification) were evaluated against the new wording in Python and by grep, not rendered in a browser (no `node` here); the saved-answer read path (`feedback/history.py`, the history endpoint, MCP reopen) was not exercised against a database.
