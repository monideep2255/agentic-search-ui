# Card 67 fix round: the outage note in the past tense, with no date

One fix round for pull request 207, answering `judge.md` and `adversary.md`. The lead's decision for this round: a reopened outage answer no longer says NCBI is down "right now", and the note carries no date. The date a person needs is the one the saved screen already shows in its header, in their own time zone, so the note can never disagree with it.

## Table of contents

- [What a person reads now](#what-a-person-reads-now)
- [Measured lengths](#measured-lengths)
- [Per finding](#per-finding)
- [Left as decided](#left-as-decided)
- [Red then green](#red-then-green)
- [Gates](#gates)

## What a person reads now

The live answer is unchanged. The reopened answer's note, exactly:

| Case | Reopened note |
|---|---|
| One database (PubMed shown; ClinVar, OMIM, GEO DataSets, MedGen and Gene the same shape with their own words) | When this answer was written, NCBI's PubMed was not answering, so this answer may be missing papers from it. Ask the question again to search afresh. |
| Several databases | When this answer was written, NCBI's PubMed and ClinVar were not answering, so this answer may be missing sources from them. Ask the question again to search afresh. |
| Unnamed | When this answer was written, some of NCBI's databases were not answering, so this answer may be missing sources from them. Ask the question again to search afresh. |
| Any of the above with a lost search too | The same, with "Another background search did not finish, so other sources may be missing too." kept before "Ask the question again to search afresh." |

What each database is missing, as the live builder words it: PubMed papers, ClinVar variant records, OMIM records, GEO DataSets datasets, MedGen records, Gene gene records.

## Measured lengths

Characters, present-tense note against the past-tense note that replaces it:

| Note | Present | Past | Growth |
|---|---|---|---|
| PubMed | 96 | 149 | 53 |
| ClinVar | 106 | 159 | 53 |
| OMIM | 95 | 148 | 53 |
| GEO DataSets | 104 | 157 | 53 |
| MedGen | 97 | 150 | 53 |
| Gene | 100 | 153 | 53 |
| PubMed, plus a lost search | 175 | 228 | 53 |
| PubMed and ClinVar | 112 | 165 | 53 |
| PubMed, ClinVar and Gene, plus a lost search | 197 | 250 | 53 |
| Unnamed | 110 | 164 | 54 |
| Older: PubMed's search | 97 | 149 | 52 |
| Older: ClinVar's search, plus a lost search | 186 | 238 | 52 |
| Older: The PubMed and ClinVar searches | 114 | 165 | 51 |
| Older: Some of NCBI's searches | 109 | 164 | 55 |

The past-tense sentence cannot be made no longer than the present-tense one without changing the decided wording: "When this answer was written, NCBI's ... was not answering" is longer than "... is down at NCBI right now", and "Ask the question again to search afresh." is longer than "Try again later.". So the length guard does the work: when the rewritten answer would exceed the 32000-character saved-answer limit, the stored text is returned unchanged. A present-tense note is better than an answer that will not open.

## Per finding

| Finding | What changed | Test |
|---|---|---|
| J-67-03, A-67-02: a long answer stops opening | `past_tense_outage_notes` returns the stored text unchanged when the rewrite would exceed `MAX_ANSWER_MARKDOWN` (imported from `feedback/capture.py`, not a second number). | `test_an_answer_at_the_length_limit_is_returned_unchanged`, `test_an_answer_whose_rewrite_just_fits_is_rewritten`, and `test_a_saved_answer_at_the_limit_still_opens_on_the_web_and_over_mcp` (three note shapes at exactly 32000 characters, served through `get_saved_answer`, then built into the web `SavedAnswerResponse` and the MCP `ReopenedAnswerOutput`) |
| J-67-01, A-67-03: a UTC day under a local header | No date in the sentence. `format_written_day` is gone. The web screen's header already shows "asked" in local time (`formatAskedAt`). The MCP reopen output already carries `asked_at` with its UTC marker, so no MCP change was needed. | `test_no_present_tense_outage_words_survive` asserts no month name; the MCP test above asserts `asked_at` serialises as `2026-10-07T09:30:00Z` |
| A-67-01, A-67-05, J-67-02: older wordings garbled or missed | All three card 63 first-wording openers are recognised as whole notes and rewritten into the current past-tense wording. The older "has no papers from it" becomes "may be missing papers from it", because card 63 withdrew that absence claim (F-63-A01). | `test_every_older_wording_reopens_as_a_clean_sentence`, four exact output strings |
| A-67-09: tests could not see a garble | Every rewrite assertion compares the whole reopened answer to an exact string, and each live case first asserts the builder's exact present-tense note. | `test_every_live_outage_note_reopens_as_this_exact_sentence`, eleven cases |
| A-67-04, J-67-05, J-67-06: text that is not the note | A paragraph is rewritten only when the whole paragraph is one of the builder's notes, word for word (`fullmatch`), with a database name from the builder's own list and that database's own missing words. A table row, list item, quote, a paragraph with anything before or after the note, an unknown name, a mismatched name and missing pair, and the refusal sentence are all left alone. | `test_text_that_is_not_the_note_paragraph_is_never_touched`, thirteen cases; `test_the_database_list_is_the_builders_own` keeps the list equal to `_DOWN_SOURCE_WORDS` |
| J-67-07: no `created_at` crashes | A missing timestamp returns the text unchanged: the note points at the time the screen shows, and without one there is nothing to point at. | `test_a_missing_timestamp_leaves_the_text_unchanged` |
| A-67-08, J-67-09: docstring names a missing test | The docstring now names `tests/system_03_search_agent/feedback/test_outage_note_dated.py`, which exists. | Read check |
| J-67-04: mutations stayed green | Exact-string tests and the length tests. See the mutation table below. | All of the above |

The function was renamed from `date_outage_notes` to `past_tense_outage_notes`, since it no longer dates anything; `feedback/history.py` calls the new name.

## Left as decided

- A-67-06: "Ask the question again to search afresh." stays. For an answer reopened after the outage, asking again is the remedy.
- A-67-07, J-67-08: the note is rewritten on reading, not on saving as D17 says. The lead records why; the mechanism is unchanged.

## Red then green

- Red first: the new test file run against the branch's previous `outage_note.py` (with only a name alias added so it imports): 44 failed, 4 passed. The 4 that passed before are the database-list check (satisfied by the alias), the two "not an outage note" cases the old code also left alone, and the length measurement, which reads constants only.
- Green: the same file against the fix, 48 passed.

One-line mutations of the fix, each restored afterwards:

| Mutation | Result |
|---|---|
| Length guard removed | 4 failed |
| Several-databases sentence back to "are down at NCBI" | 5 failed |
| One-database sentence back to "is down" | 18 failed |
| `fullmatch` replaced by `search` | 8 failed |
| Missing-timestamp guard removed | 1 failed |
| Name and missing-words pair check removed | 1 failed |

## Gates

| Gate | Exit code |
|---|---|
| `ruff check` (no path) | 0 |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | 0 |
| `tests/system_03_search_agent/feedback` (218 passed) | 0 |
| MCP adapter tests, the saved-answer endpoint and the note's producer tests (114 passed) | 0 |
| `python3 tracker/check_doc_drift.py --check` | 0 |
