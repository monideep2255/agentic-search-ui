# Card 63 adversary round

- Round: adversary, one round, risk dial position 2
- Subject: fix/card63-tested at bc6cca1a (probe checkout `.claude/worktrees/card63-adv`)
- Base: origin/develop 7bac224e
- Commits under review: d1736e13, bf4a697e, aed1c99f, ecbf15ba, cf156daa (the last two are fixes from the test round, hunted hardest)
- Date: 2026-09-28
- Author: adversary (files only, closes nothing)

## Findings

### F-63-A01: the outage note asserts an absence the answer above it contradicts (fetch or summary failure after a successful search)
- Severity: major (should-fix; a lying note under a biomedical answer)
- Where: `core/graph.py` `_build_failed_search_note` (bf4a697e; wording untouched by ecbf15ba). Not inside cf156daa.
- What: the note's wording is derived from `kind` and `source` alone, and it says "<DB>'s search is down at NCBI right now, so this answer has no <papers|variant records> from it." That sentence is asserted for ANY failed `ncbi_efetch` action on that database, including a `fetch` or `summary` that failed AFTER the search on the same database succeeded. The answer then lists records from that database directly above a note saying it has none.
- Reproduction (my own probe, `scratchpad/adversary/test_probe2_loop.py`, real loop with every tool faked exactly as `test_breadth_wiring.py` does, gene question "Which diseases are associated with BRCA1?"):
  - Case A, PubMed `fetch` returns `status="error", failure_kind="service_down"` while the PubMed `search` succeeds. Observed tool_result summaries: `'search: 3 id(s)', ..., 'fetch error: the service is down at NCBI', 'ok: 3 record(s)'`. Observed saved markdown tail:
    ```
    ## Publication records found
    | Paper | Identifier |
    | 30000001 [7] | PMID:30000001 |
    | 30000002 [10] | PMID:30000002 |
    | 30000003 [12] | PMID:30000003 |
    ...
    PubMed's search is down at NCBI right now, so this answer has no papers from it. Try again later.
    ```
    `done.trust_line: Based on 12 sources, not yet confirmed`. Three PubMed papers are cited and the note says the answer has no papers from PubMed.
  - Case B, ClinVar `summary` returns `service_down`. Observed: `'summary error: the service is down at NCBI'` and the markdown carries `## Clinvar records found | NM_007294.4(BRCA1):c.672del [9] | VCV672 |` immediately followed by `ClinVar's search is down at NCBI right now, so this answer has no variant records from it. Try again later.`
- Why it matters: the person reads a note that flatly contradicts the table above it. Either the papers are not to be trusted or the note is wrong, and they cannot tell which. Because card 63 now SAVES every `ask` answer, this contradiction is stored and reopened from history and MCP as-is. It also mislabels what failed: "search is down" when the search worked and a record fetch did not. Reachable in production because `_get_or_error` and the `service_down` classifier are shared by search, summary, fetch and link, so any ESummary/EFetch `ERROR` body containing "unavailable" takes this path.
- NOT FIXED

### F-63-A02: "search is down" is said for a failed fetch, summary or link, and the refusal says "A search I needed is down" for the same
- Severity: minor (wording; but it is the sentence the person reads)
- Where: `core/graph.py` `_build_failed_search_note`, `_execute_planned_call`'s fetch branch (bf4a697e), and `synthesis/refuse.py` `SEARCH_DOWN_MESSAGE` (cf156daa, the fix under review).
- What: `failure_kind`/`failure_source` are set on the fetch/summary/link branch too, and the note and refusal both name the failure a "search" regardless of action. NCBI's ESearch (SOLR) being down does not imply EFetch or ESummary are down, and the reverse; telling a person "PubMed's search is down" when what failed was retrieving three already-found records sends them to the wrong conclusion about what to expect when they retry.
- Reproduction: same probe as F-63-A01 case A; observed summary `fetch error: the service is down at NCBI` beside note `PubMed's search is down at NCBI right now`.
- NOT FIXED
### F-63-A03: a reopened `ask` answer replays "down at NCBI right now ... Try again later" as present tense, with no date
- Severity: minor / unsure (design consequence of saving `ask`; filing because it is a trust sentence that becomes false with time)
- Where: `feedback/capture.py` `answer_markdown_from` stores every `note` token as a plain block (pre-existing), and aed1c99f now saves `ask` answers, whose notes are exactly the outage and retry notes.
- What: the saved markdown ends with `PubMed's search is down at NCBI right now, so this answer has no papers from it. Try again later.` (or `... Ask again to retry.`). Reopened from history or MCP `reopen_past_answer` a day later, the screen states an outage as current fact and tells the person to wait, when the right action then is to re-run the search. The saved-answer screen renders notes as ordinary paragraphs with no "as of <date>" framing, so nothing marks the sentence as historical.
- Reproduction: `scratchpad/adversary/test_probe2_loop.py`, case "search down, account": `row.trust_signal: ask | has markdown: True | trust_line: Based on 9 sources, not yet confirmed`; markdown tail: `PubMed's search is down at NCBI right now, so this answer has no papers from it. Try again later.`
- Why it matters: the card's stated purpose is that the reopened answer carries "its trust line and note"; the note is faithful to what was shown, but a present-tense outage claim and a "wait" instruction are the one kind of note that stops being true on its own. The person may not re-ask a question that would now answer fully.
- NOT FIXED
### F-63-A04: an outage answered as an XML `<ERROR>` body is never `service_down`, so it keeps "Ask again to retry"
- Severity: unsure / minor (outside the JSON path the card measured; filing because it is exactly "a real outage that falls through and invites an immediate retry")
- Where: `tools/ncbi_transport.py` `_classify_eutils_xml` (unchanged by the card) versus `_classify_eutils_json` (d1736e13), which is the only branch that sets `failure_kind`.
- What: only the JSON classifier reads `ERROR` and assigns a kind. The XML classifier has no `ERROR` handling at all: an `<eSearchResult><ERROR>...</ERROR></eSearchResult>` body is refused as an unrecognised root, and an `<ERROR>` child under an allowed root (EFetch, the one action this tool requests as XML for PubMed) is not looked for. Either way `failure_kind` is None, the answer reads `other`, and the note and refusal say "Ask again to retry".
- Reproduction (`scratchpad/adversary/probe1_pure.py`): input `content_type="text/xml"`, text `<eSearchResult><ERROR>Search Backend failed: Search is temporarily unavailable. Cannot connect to SOLR</ERROR></eSearchResult>`; output `('error', None, 'E-utilities XML root <eSearchResult> is not a recognized shape (expected one of ...')`. The same outage text under JSON gives `('error', 'service_down', ...)`.
- Why it matters: if NCBI ever answers an EFetch (XML) request with an outage `ERROR`, the person is told to ask again into the outage, the exact behaviour the card exists to remove. I could not establish whether NCBI does this, hence unsure.
- NOT FIXED

## Verdict

FAIL, on F-63-A01. The card promises that during an outage the note says what is missing and why; on the fetch and summary branches the note asserts "this answer has no papers / variant records from it" directly under a table of exactly those records, and that contradiction is now SAVED and reopened verbatim (F-63-A03). None of the four findings sits inside ecbf15ba or cf156daa, so no Rule 4 stop: cf156daa's chooser held up under every mixed, missing-kind, bogus-kind and no-entity ordering I tried, and its refusal renders through the frontend's structural refusal path rather than a wording match.

Blocking: F-63-A01. Should-fix: F-63-A02. Filed for the closer's judgement: F-63-A03, F-63-A04.

Verified by my own probes (files under `scratchpad/adversary/`):
- Classifier: 17 hostile and boundary bodies (`probe1_pure.py`). "Empty Term" stays `other`; markers match case-insensitively; a marker past 2000 characters falls to `other`; an ERROR value that is a dict, list, empty or null does not crash; a title or warninglist quoting the outage phrase is `ok`/`empty`, never `service_down`. Contrived false positive noted but NOT filed: `Invalid db name specified: unavailable` is `service_down`, which needs a schema-refused db.
- Live NCBI, 4 ESearch requests at 1/s: an empty term returns `"Empty term and query_key - nothing todo"` (no marker), and `unavailable[badfield]`, an unbalanced quote and an unbalanced parenthesis all return ordinary result sets. NCBI did not echo the term into an ERROR string, so a question's own words cannot fake an outage through the topic path.
- Log line: database `pub med; evil\x07` logs `unrecognised`, `PubMed` logs `unrecognised`, None logs `unspecified`; the NCBI text with a URL, a key-shaped string, markup and a control character never appears in the log record. Two mutations of my own (log the raw database; append NCBI's text) each turned the relevant arms red: `1 failed, 81 passed` and `2 failed, 179 passed`. File restored, `git status --short` empty.
- Note builder and refusal chooser: pre-card entry with no `kind`, `kind: None`, `kind: "SERVICE_DOWN"`, duplicate databases, three named, unknown and empty source, `PubMed` casing, down beside a timeout, down beside a no-entity reason, down on the topic path.
- Real loop with every tool faked (`test_probe2_loop.py`, `test_probe3_refusals.py`, `test_probe4_clarify.py`): PubMed search down gives `ask`, trust line "Based on 9 sources, not yet confirmed", the outage note, summary `search error: the service is down at NCBI`; the stream, the synthesis prompt and the saved markdown carry none of "SOLR", "temporarily unavailable", "Search Backend", the canary or the injected instruction. A timeout keeps "Ask again to retry". A guest stores nothing (`has markdown: False`). A clarifying question ("What variants cause it?") ends `refuse` and stores nothing. Fetch-stage and summary-stage outages produced F-63-A01.
- The develop merge 9e1190ff: develop's changes to the card's four source files are 13 lines of unrelated edits; the merge's own src diff equals develop's.

Read only, not executed: `feedback/history.py`'s owner-scoped SQL for `list_history` and `get_saved_answer`; `GET /v1/history/{trace_id}/answer` and MCP `reopen_past_answer` passing `trust_signal` and `trust_line` through with the caller's own `owner_id`; `SavedAnswerScreen.tsx` showing a check mark only when the trust line starts "Confirmed" (no Postgres and no browser here). Not probed: another account's or a guessed trace id against a live database.
