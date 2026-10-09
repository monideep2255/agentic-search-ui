# Card 67 judge: the dated outage note

Fresh judge, branch `fix/card67-dated-outage-note` at 7e61c7e7 against `origin/develop` 17b2a721. Findings are appended as they are established; the verdict is at the end.

## Findings

### J-67-01: the note's day is the UTC day, so a late-evening answer is dated the next day, contradicting the header on the same screen

- Severity: major
- Regression: no (new behaviour introduced by this card; develop shows no date)
- What: `format_written_day` in `src/system_03_search_agent/feedback/outage_note.py` (line 38 to 41) converts `created_at` to UTC before taking the day. `SavedAnswerScreen.tsx` (`formatAskedAt`, line 71 to 83) shows the same `asked_at` in the reader's local time. For anyone west of UTC who asks in the evening, the two disagree.
- Reproduction: an answer saved at 2026-10-07 23:30 at UTC minus 4 is stored as `2026-10-08T03:30:00+00:00`. Through the real functions, `date_outage_notes(_build_failed_search_note([{"source": "pubmed", "kind": "service_down", ...}]), created_at)` returned "When this answer was written on 8 October 2026, NCBI's PubMed database was not answering, ...". `new Date("2026-10-08T03:30:00+00:00").toLocaleString(...)` with the header's options gave "Oct 7, 2026, 11:30 PM". So the reopened screen reads "asked Oct 7, 2026, 11:30 PM" above a note that says it was written on 8 October.
- Why it matters: the card exists to make the note's date true. A date one day off, on the same screen as the correct one, is the confident wrong fact the user's-chair rule ranks below a missing one. It hits every US-evening answer (owner's time zone is UTC minus 4 or 5, so 8 pm onwards). MCP callers get the UTC day with no local header to compare, which is defensible there, but the web screen is the main reader. No test covers a time zone other than UTC (`test_outage_note_dated.py` line 15 uses 09:30 UTC).
- NOT FIXED

### J-67-02: an older saved wording is not matched, and the two older wordings that are matched read ungrammatically

- Severity: minor (probably no stored rows carry them; see below)
- Regression: no
- What: the card 63 first wording (`bf4a697e`, `core/graph.py`) had three openers. `outage_note.py` lines 30 to 32 match them as follows.
  - "Some of NCBI's searches are down right now, so ..." is not matched at all (`_GENERIC` expects "databases"; `_PLURAL` expects "at NCBI"). It reopens unchanged, "right now" and "Try again later." intact.
  - "PubMed's search is down at NCBI right now, so ..." becomes "When this answer was written on 7 October 2026, NCBI's PubMed's search database was not answering, so this answer has no papers from it."
  - "The PubMed and ClinVar searches are down at NCBI right now, so ..." becomes "When this answer was written on 7 October 2026, The PubMed and ClinVar searches were not answering at NCBI, ..." (capital "The" mid-sentence).
- Reproduction: a probe calling `date_outage_notes(text, datetime(2026, 10, 7, 9, 30, tzinfo=UTC))` on each of the three strings; outputs quoted above exactly.
- Why it matters: the diagnosis table lists "Older saved rows" as covered and `test_the_older_saved_wording_is_dated_too` only checks one of the three, by substring, so "NCBI's PubMed's search database" passes it. Mitigation, checked: walking `origin/develop`'s first-parent history, `bf4a697e` first reaches develop in merge `25800026` (PR #128), the same merge that brought the current wording `b6e7f918`, so the older wording was never live on develop. Rows carrying it exist only if a branch build was deployed and used by a signed-in account. Unsure whether that happened.
- NOT FIXED
### J-67-03: a saved answer near the 32000-character cap no longer opens, on the web or over MCP

- Severity: major
- Regression: yes. The same row opens on develop.
- What: capture stores an answer of up to `MAX_ANSWER_MARKDOWN` (32000) characters (`feedback/capture.py` line 63). Dating lengthens the outage note: "PubMed is down at NCBI right now, so " becomes "When this answer was written on 30 September 2026, NCBI's PubMed database was not answering, so " and "Try again later." becomes "Ask the question again to search afresh.". `get_saved_answer` (`feedback/history.py` line 418) returns the longer text, and both readers build a response model capped at exactly 32000: `SavedAnswerResponse.answer_markdown` (`adapters/web_sse/app.py` line 891) and `ReopenedAnswerOutput.answer_markdown` (`adapters/mcp/server.py` line 533). Neither catches the error.
- Reproduction: a stored row of exactly 32000 characters ending in `_build_failed_search_note` for GEO DataSets and MedGen down plus one timeout, `created_at` 2026-09-30 09:00 UTC, served through `get_saved_answer` with a stub session (the same stub the card's own test uses). Dated length: 32075. `get_v1_history_answer("t1", caller=...)` raised `ValidationError: 1 validation error for SavedAnswerResponse, answer_markdown, String should have at most 32000 characters`. `ReopenedAnswerOutput(...)` raised the same. With `history.date_outage_notes` replaced by identity (develop's behaviour) the same row gave "web OK 32000" and "mcp OK".
- Why it matters: a person clicks a past search they can see listed and gets a server error instead of the answer they opened yesterday; an MCP caller gets an internal error. Only answers within about 60 to 110 characters of the cap that also carry an outage note are hit, so it is rare, but it is strictly worse than develop and it is the large table answers (isolate lists) that sit near the cap. The build's claim "an answer with no outage note reopens byte for byte" is true; the converse case, an answer with a note, was not bounded.
- NOT FIXED
### J-67-04: the card's tests do not pin the date's time zone or the dated sentence's wording; five of twelve one-line mutations stay green

- Severity: minor
- Regression: no
- What: `tests/system_03_search_agent/feedback/test_outage_note_dated.py` checks the lead "When this answer was written on 7 October 2026," and the absence of "right now" and "Try again later". It never checks the rest of the sentence, a non-UTC timestamp, or a naive one.
- Reproduction: each mutation applied to one line, the card's test file run, the file restored with `git checkout`:

| Mutation | Result |
|---|---|
| `outage_note.py` line 40, drop the UTC conversion | 9 passed |
| line 40, convert to the server's local zone instead | 9 passed |
| plural branch reworded to "{names} are down at NCBI, so" (present tense outage after the date) | 9 passed |
| single branch reworded to drop "NCBI's ... database" | 9 passed |
| always rejoin blocks even when nothing changed | 9 passed (harmless: identical output) |
| `_SINGLE` anchored to block start `\A` instead of every line | 9 passed (harmless for real notes) |
| keep "Try again later." | 6 failed |
| drop the generic branch | 2 failed |
| drop the plural branch | 1 failed |
| `history.py` line 418 back to the undated text | 1 failed |
| short month ("Oct") | 7 failed |
| date from the clock instead of `created_at` | 7 failed |

- Why it matters: the plural mutation leaves a reopened answer saying "When this answer was written on 7 October 2026, PubMed and ClinVar are down at NCBI", the stale present-tense claim the card removes, and the tests stay green. The time zone mutations staying green is why J-67-01 shipped. The red-first claim in `build.md` (no-op function, 7 of 9 fail) is true but only proves the lead is added.
- NOT FIXED

### J-67-05: any block whose first line opens with a period-free clause ending "is down at NCBI right now, so " is rewritten, and every "Try again later." in that block is replaced

- Severity: minor (unsure; the trigger phrase is product wording a writer or a paper is unlikely to produce at a line start)
- Regression: no
- What: `_SINGLE` and `_PLURAL` (`outage_note.py` lines 30 and 31) take `[^.\n]+?` as the name, anchored at any line start with `re.MULTILINE`, and the replacement of "Try again later." (line 65) covers the whole block, not only the note.
- Reproduction, real function, `created_at` 2026-10-07 09:30 UTC:
  - Writer prose "The authors wrote that the server is down at NCBI right now, so they used a mirror. Try again later." became "When this answer was written on 7 October 2026, NCBI's The authors wrote that the server database was not answering, so they used a mirror. Ask the question again to search afresh."
  - Table row "| PubMed is down at NCBI right now, so nothing | x |" became "When this answer was written on 7 October 2026, NCBI's | PubMed database was not answering, so nothing | x |", which breaks the table's row.
  - List item "- PubMed is down ..." became "... NCBI's - PubMed database ...".
  - Two outage sentences on two lines of one block: only the first dated, the second keeps "right now" (count 1 per block, line 56).
  - A sentence quoting "right now" mid-paragraph, and "Rates are high right now ... Try again later in the season." were left alone, correctly.
- Why it matters: the brief asked whether a writer's sentence, a paper's text or a table cell can be matched by mistake. They can, if they open a line with the product's own outage words. I found no producer that does so today, so the practical risk is low; the guard is the regex's shape, not a typed marker. The note token is typed `kind="note"` at write time (`core/graph.py` line 12691) but that type is lost in the stored markdown.
- NOT FIXED

### J-67-06: the refusal's outage sentence matches the single-database pattern and would be garbled if it were ever stored

- Severity: minor (latent; not reachable today)
- Regression: no
- What: `SEARCH_DOWN_MESSAGE` (`synthesis/refuse.py` line 69 to 73) opens "A source I needed is down at NCBI right now, so I could not find ...".
- Reproduction: `build_refusal_text("TP53", message=refusal_message_for([{"source": "pubmed", "kind": "service_down", ...}]))`, through `answer_markdown_from`, then `date_outage_notes` gave "When this answer was written on 7 October 2026, NCBI's A source I needed database was not answering, so I could not find grounded evidence this time. Try again later, or try NCBI's cross-database search: ..." ("Try again later," with a comma is not replaced either).
- Why it matters: today a refusal is never saved (`feedback/capture.py` line 88, `_SAVEABLE_OUTCOMES` excludes `refuse`), so no person sees this. If refusals are ever saved, this ships as nonsense with no test going red.
- NOT FIXED

### J-67-07: a row with no `created_at` makes every reopen fail, including answers with no outage note

- Severity: minor (unsure; the column is `nullable=False` with `server_default now()`, `data/models.py`, `Interaction.created_at`)
- Regression: yes in principle, unreachable with the current schema
- What: `date_outage_notes` calls `format_written_day(written_at)` before looking for a note (`outage_note.py` line 49), and `format_written_day` reads `when.tzinfo`.
- Reproduction: `date_outage_notes("plain answer", None)` raised `AttributeError: 'NoneType' object has no attribute 'tzinfo'`. A naive `datetime(2026, 10, 7, 23, 30)` is taken as already UTC and gives "7 October 2026".
- Why it matters: the build's claim that an answer with no outage note reopens byte for byte depends on `created_at` being present. Computing the day only when a note is found would make that claim unconditional.
- NOT FIXED

### J-67-08: the build dates on reading, not on saving as decision D17 states, and its reason for not saving is weaker than stated

- Severity: unsure (owner's call)
- Regression: no
- What: `testing/Board_plan.md` line 222 records D17 as "the outage note is dated when the answer is saved". `build.md` dates on reading because `created_at` is a database default and dating at capture "would mean a guessed clock". Capture runs within seconds of the insert, so the clock it would read differs from `created_at` by seconds, which only changes the day in the seconds around midnight.
- Why it matters: dating on save would have kept the 32000 cap check in capture (J-67-03 would not exist: an over-long dated answer is stored as None, the documented fallback), but would leave rows saved before this card undated. Dating on read covers old rows. Both are defensible; the departure from the owner's recorded words should be the owner's to accept, and `build.md` discloses it.
- NOT FIXED

### J-67-09: the module docstring names a test file that does not exist

- Severity: minor
- Regression: no
- What: `outage_note.py` line 19 says `tests/unit/feedback/test_outage_note.py` "builds each one from that function and fails if this module stops recognising it". That path does not exist; the test is `tests/system_03_search_agent/feedback/test_outage_note_dated.py`.
- Reproduction: `ls tests/unit/feedback/test_outage_note.py` gave "No such file or directory".
- Why it matters: a maintainer changing `_build_failed_search_note` looks for the guard the docstring promises and does not find it.
- NOT FIXED

## The five questions

| Question | Answer | How I know |
|---|---|---|
| 1. Every wording matched, nothing else | The three live openers and the mixed-failure form are matched and dated. One of three older card 63 openers is missed and two read badly (J-67-02). Product wording at a line start in writer text, a table row or a list item is matched by mistake (J-67-05); mid-sentence "right now" is not. | Own probes through `_build_failed_search_note`, `answer_markdown_from`, `build_refusal_text` and `date_outage_notes` |
| 2. The date is right | Format "7 October 2026" is right. The day is the UTC day, one day ahead of the screen's own header for US evening answers (J-67-01). No `created_at` raises (J-67-07). | Own probe, 23:30 at UTC minus 4; header format checked with the screen's `toLocaleString` options |
| 3. Both readers agree | Yes. The web endpoint and MCP `reopen_past_answer` both read `get_saved_answer`. `list_history` selects no markdown. No GraphQL or export surface reads `answer_markdown` (grep of `src/`). | Read and grep; both response models exercised in J-67-03's probe |
| 4. Nothing worse than develop | No: a stored answer near the 32000 cap with an outage note now fails to open on both surfaces (J-67-03). | Own probe, same row green with develop's behaviour |
| 5. Mutations | 7 of 12 one-line mutations go red; the 5 that survive include the time zone and a present-tense plural rewording (J-67-04). | Own mutations, each restored with `git checkout`, `git diff` clean after |

## Test counts

- `tests/system_03_search_agent/feedback`: 179 passed.
- Saved-answer surfaces and the note's producer (`adapters/web_sse/test_saved_answer_endpoint.py`, `adapters/mcp/test_parity_tools.py`, `adapters/mcp/test_no_cost_and_auth.py`, `core/test_write_failed_search.py`): 81 passed.
- `ruff check` on the three changed Python files: all checks passed.

## Verified versus read

- Verified with my own probes: J-67-01, J-67-02, J-67-03 (both response models, and the develop comparison), J-67-05, J-67-06, J-67-07, the mutation table, the test counts, and that the old wording never reached develop on its own.
- Read only: that no other surface returns saved markdown (grep), that refusals are never saved (`capture.py`), the frontend's header format (one `node` call with the same options, not a browser render), and D17's wording (`testing/Board_plan.md`).

## Verdict

FAIL. The live answer is unchanged and the common case reads as the card intends, but J-67-03 makes a rare saved answer unopenable on the web and over MCP where develop opens it, and J-67-01 puts a wrong day on every US-evening outage answer, next to the correct day in the screen's header.

Worse than develop: yes
