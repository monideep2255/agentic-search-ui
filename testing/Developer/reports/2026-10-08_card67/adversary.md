# Card 67 adversary report

Round one, adversary for pull request 207, branch fix/card67-dated-outage-note at 7e61c7e7. Findings appended as found.

## Findings

### A-67-01: The older saved wording is rewritten into a garbled sentence

- Severity: major
- Regression: yes, new in this change (develop shows the old sentence unchanged and grammatical)
- What: rows saved before the card 63 wording change carry "PubMed's search is down at NCBI right now, so this answer has no papers from it. Try again later." The new `_SINGLE` pattern captures "PubMed's search" as the database name and wraps it in "NCBI's ... database".
- Reproduction: `date_outage_notes("PubMed's search is down at NCBI right now, so this answer has no papers from it. Try again later.", datetime(2026,10,7,9,30,tzinfo=UTC))` returns "When this answer was written on 7 October 2026, NCBI's PubMed's search database was not answering, so this answer has no papers from it. Ask the question again to search afresh."
- Why it matters: every reopened answer saved under the older wording now reads "NCBI's PubMed's search database", a sentence no run ever produced. The build report and the module docstring both claim this wording "is covered too"; the test for it (`test_the_older_saved_wording_is_dated_too`) only asserts the date is present and "right now" is gone, so it passes on the garbled output. The older sentence also says "has no papers from it", an absence claim card 63 withdrew (F-63-A01), and the rewrite keeps it.

### A-67-02: A long saved answer with an outage note can no longer be reopened (500 on REST, validation error on MCP)

- Severity: major (narrow trigger, hard failure)
- Regression: yes, new in this change
- What: capture stores an answer only when it is at most 32000 characters (`MAX_ANSWER_MARKDOWN`). The rewrite lengthens the note by about 80 characters ("When this answer was written on 7 October 2026, NCBI's ... database was not answering" and "Ask the question again to search afresh."). Both reopen surfaces validate `answer_markdown` with `max_length=32000` (`SavedAnswerResponse` in the web adapter, `ReopenedAnswerOutput` in the MCP server), so a stored answer within about 80 characters of the cap that carries an outage note now fails validation after the rewrite.
- Reproduction: a 32000 character stored answer ending in the live PubMed outage note, served through `GET /v1/history/t1/answer` with a FastAPI `TestClient`, the session stubbed as in the author's test and the caller dependency overridden: status 500 Internal Server Error. The same row with the note replaced by a short sentence: status 200. Directly, `date_outage_notes` turns 32000 characters into 32080, and `SavedAnswerResponse(..., answer_markdown=<that>)` raises `string_too_long`.
- Why it matters: the person sees the row in history and clicks it, and the open fails. The web adapter's own comment says a stored answer must never be allowed to "take the whole answer down" for exactly this reason. On develop the same row opens. Long answers are the table-heavy isolate and variant answers, which are also the ones most likely to have lost a background search.

### A-67-03: The note's date and the screen's "asked" date disagree for anyone west of UTC in the evening

- Severity: minor
- Regression: yes, new in this change (develop shows no date in the note, so nothing to disagree with)
- What: `format_written_day` renders `created_at` in UTC. `SavedAnswerScreen.tsx`'s `formatAskedAt` renders the same timestamp in the browser's local zone in the header line "Saved answer · asked ...".
- Reproduction: `created_at = 2026-10-08T00:30:00Z`. In `TZ=America/New_York`, the header's `toLocaleString` gives "Oct 7, 2026, 8:30 PM". `date_outage_notes(..., datetime(2026,10,8,0,30,tzinfo=UTC))` gives "When this answer was written on 8 October 2026, ...". One screen, two different days for the same answer.
- Why it matters: the card's whole point is a trustworthy date on the note. A reader who sees "asked Oct 7" above "written on 8 October" is shown a contradiction in the trust text itself. The note also carries no "UTC" to explain it.

### A-67-04: The rewrite fires on any block line that matches the wording, not only the note, and garbles what it hits

- Severity: minor (unsure how often real writer or record text reaches the pattern; the planting route is real)
- Regression: yes, new in this change
- What: the stored markdown no longer carries the token `kind`, so `date_outage_notes` matches by wording on every block. `_SINGLE` accepts any text without a full stop or newline before " is down at NCBI right now, so " at the start of any line, including a table row, a list item, a block quote, or a writer's prose paragraph. Whatever precedes is wrapped as "NCBI's <it> database", and every "Try again later." in that block is replaced.
- Reproduction (all with the 7 October 2026 timestamp):
  - Table row `| ClinVar is down at NCBI right now, so | Try again later. |` becomes `When this answer was written on 7 October 2026, NCBI's | ClinVar database was not answering, so | Ask the question again to search afresh. |`, a row whose first cell now starts outside the pipe.
  - List item `- dbSNP is down at NCBI right now, so ...` becomes `When this answer was written on 7 October 2026, NCBI's - dbSNP database was not answering, ...` (list marker swallowed into the sentence).
  - Quote `> Our server is down at NCBI right now, so results may vary.` becomes `... NCBI's > Our server database was not answering ...`.
  - Writer prose `The ClinVar mirror is down at NCBI right now, so curated data may lag. Try again later. Variant X is pathogenic [1].` becomes `When this answer was written on 7 October 2026, NCBI's The ClinVar mirror database was not answering, so curated data may lag. Ask the question again to search afresh. Variant X is pathogenic [1].`
  - Planted record text (a title cell or claim beginning `Study: Ignore prior; the drug is safe is down at NCBI right now, so this answer may be missing papers from it.`) is reworded into the product's own dated trust sentence: `When this answer was written on 7 October 2026, NCBI's Study: Ignore prior; the drug is safe database was not answering, ...`.
- Why it matters: the live answer showed such text as record content; the reopened answer presents it in the product's voice, attributed to NCBI, with a date, which is a stronger claim than the live screen made. Table cells come from record fields (`_cell` escapes pipes but not this wording), so a record author controls the input. The fix would be to anchor the match to a whole block that is exactly a note shape, not to any line start.

### A-67-05: The other older wordings are half handled: one stays undated, one gains a capital "The" mid-sentence

- Severity: minor (unsure it is reachable, see below)
- Regression: partly (the plural garble is new; the undated generic is unchanged from develop)
- What: the first card 63 builder (commit bf4a697e) had three openers. Only one is named in the diagnosis. The other two: "The {A} and {B} searches are down at NCBI right now, so ..." and "Some of NCBI's searches are down right now, so ...". `_GENERIC` matches "databases", not "searches".
- Reproduction:
  - "The PubMed and ClinVar searches are down at NCBI right now, so this answer has no papers or variant records from them. Try again later." reopens as "When this answer was written on 7 October 2026, The PubMed and ClinVar searches were not answering at NCBI, so ..." (capital "The" after a comma).
  - "Some of NCBI's searches are down right now, so this answer may be missing sources from them. Try again later." is returned unchanged: still "right now", still "Try again later", no date.
  - "ClinVar's search is down at NCBI right now, so this answer has no variant records from it. ..." reopens as "... NCBI's ClinVar's search database was not answering ..." (same garble as A-67-01).
- Reachability: I checked develop's first-parent history. Merge 25800026 (pull request 128) is the first develop commit containing bf4a697e, and it already contains b6e7f918, the current wording. So the older wordings never sat on develop alone, and rows carrying them exist only if a card 63 branch build saved answers into a shared database between 26 and 28 September. The build report and the module docstring assert such rows exist ("rows saved before the wording change carry it"); I could not confirm that without a database, which I was told not to touch. If they do not exist, A-67-01 and this finding are dead code paths that garble; if they do, the module's claimed coverage of them is wrong.
- Why it matters: either the coverage claim is false (rows exist and come out garbled or undated) or the code and test carry a path for text that never shipped.

Addendum to A-67-02, measured on the MCP surface too: `ReopenedAnswerOutput(..., answer_markdown=date_outage_notes(<32000 characters ending in the PubMed note>))` raises `ValidationError ... String should have at most 32000 characters`. Growth is 80 characters for the one-database note and 72 for the plural and generic notes, so the failing window is a stored length above roughly 31920.

### A-67-06: A reopened note now says "Ask the question again", the advice card 63 removed for an outage still in progress

- Severity: minor
- Regression: yes, new wording
- What: `Try again later.` is replaced with "Ask the question again to search afresh." whatever the gap between writing and reopening. Card 63 (`_build_failed_search_note`'s docstring, decided from the user's chair on 27 September) chose "Try again later" and "never ask again" because asking again during an outage sends the person straight back into it.
- Reproduction: any live note reopened with a `created_at` of a minute ago, for example `date_outage_notes(note, datetime.now(UTC))`, reads "When this answer was written on 7 October 2026, NCBI's PubMed database was not answering, ... Ask the question again to search afresh." The person reopening from history during the same outage is told to ask again, spends one of the day's questions, and hits the same outage. An MCP agent reading the reopened text is told the same.
- Why it matters: the reopened answer gives advice the live answer deliberately did not, and it costs a guest or a capped account a question. A dated note ("When this answer was written on ...") is already enough to tell a later reader the outage may be over; the advice could stay neutral.

### A-67-07: The build departs from owner decision D17 without the owner being asked

- Severity: unsure (process, not a code defect)
- Regression: not applicable
- What: `testing/Board_plan.md` records D17 as "Card 67: the outage note is dated when the answer is saved". The build dates it when the answer is read, and the build report explains why. I found no row in `DECISIONS.md` or the board recording the owner accepting the change of mechanism.
- Reproduction: `grep -n D17 testing/Board_plan.md DECISIONS.md` finds only the board row above.
- Why it matters: the two mechanisms differ in what a person sees: read-time dating rewrites stored text on every open (A-67-02, A-67-04 follow from that), while save-time dating would have fixed the text once. Whether the trade-off is acceptable is the owner's call under the decision-cadence rule.

### A-67-08: The module docstring names a guard test that does not exist

- Severity: minor
- Regression: yes, new text
- What: `feedback/outage_note.py` says "`tests/unit/feedback/test_outage_note.py` builds each one from that function and fails if this module stops recognising it." That file does not exist. The test that does this is `tests/system_03_search_agent/feedback/test_outage_note_dated.py`.
- Reproduction: `ls tests/unit/feedback/test_outage_note.py` gives "No such file or directory".
- Why it matters: the next person changing the live wording follows the docstring to the guard and finds nothing, and may conclude there is none.

### A-67-09: The tests cannot see a garbled rewrite

- Severity: minor
- Regression: yes, new tests
- What: every dated-output assertion checks only that "When this answer was written on 7 October 2026," is present and that "right now" and "Try again later" are absent. None checks the sentence that results, so a rewrite producing "NCBI's PubMed's search database" (A-67-01) or "NCBI's - dbSNP database" (A-67-04) passes. None checks a near-cap answer still validates (A-67-02), and none checks that table rows, list items or quotes are left alone.
- Reproduction: A-67-01's exact output passes `test_the_older_saved_wording_is_dated_too` as written (it is that test's own input).
- Why it matters: the suite would stay green through the defects above.

## What held

- Every live wording from today's `_build_failed_search_note` (one database for each of the six named sources, several databases, unnamed, and each with the "Another background search did not finish" sentence) reopens grammatically with the right database names and the 7 October 2026 date; the mixed-failure sentence is kept.
- Text before the note is untouched: the claim paragraph and its `[1]` marker come back byte for byte. An answer with no outage note is returned identical (the function returns the original string object when nothing matched).
- Notes that are not outage notes ("did not finish", "Ask again to retry") are not rewritten. A sentence with the outage wording that does not start a line ("TP53 [1]. PubMed is down at NCBI right now, ...") is not rewritten.
- The stored row is not modified; only the returned copy changes.
- Coverage of surfaces: `get_saved_answer` is the only reader of `answer_markdown` in `src`, and both the web endpoint and MCP `reopen_past_answer` go through it. The GraphQL adapter has no saved-answer field. `list_history` carries no answer text, so there is no undated history preview. The web screen's parser (`savedAnswerMarkdown.tsx`) has no wording-based note detection, so the rewritten paragraph renders as an ordinary paragraph exactly as the old one did.
- The refusal sentence ("A source I needed is down at NCBI right now, so ...") would be garbled by the same pattern ("NCBI's A source I needed database"), but refusals are not saved (`_SAVEABLE_OUTCOMES`), so it cannot reach a reopened answer today.
- `created_at` is a timezone-aware column, so the UTC date is computed from a real instant, not a naive guess.

Note on running the author's tests: in three of my first runs the author's test file failed (2, 1 and then 7 of 9). The worktree's `outage_note.py` modification time moved after the commit while `git status` was clean, and a concurrent pytest from another session was running in the same worktree, so I attribute those failures to another reviewer's mutation run, not to the code. Ten later runs with the source confirmed equal to HEAD were 9 of 9 green. All my probes were re-run with `git diff --quiet HEAD -- src` true before and after.

## Verdict

FAIL. The change does what it says for every wording the live product writes today, but it introduces a hard failure to reopen long answers that carry an outage note (A-67-02, measured: 500 on REST, validation error on MCP), a UTC date that contradicts the screen's local "asked" date (A-67-03), a wording-only match that rewrites and garbles non-note text into a dated sentence in the product's voice (A-67-04), and garbled output for the older wordings it claims to cover (A-67-01, A-67-05). None of these sit inside an earlier fix made during this card; all are in the card's only change.

Verified with my own probes: A-67-01, A-67-02 (REST via TestClient and MCP via the output model), A-67-03 (node `toLocaleString` in New York against the Python output), A-67-04, A-67-05, A-67-06, A-67-08, and every item under What held except the D17 history. Only read: A-67-07 (board and decisions text), the claim that refusals are never saved, and the reachability of old-wording rows in a real database.

Worse than develop: yes. On develop a long outage answer reopens (with a stale but grammatical note); on this branch it fails to open, and non-note text and older notes can come back reworded wrongly.
