# Card 67 build: the outage note is dated when reopened

## What a person reads now

- Live answer: unchanged ("PubMed is down at NCBI right now ... Try again later.").
- Reopened answer: "When this answer was written on 7 October 2026, NCBI's PubMed database was not answering, so this answer may be missing papers from it. Ask the question again to search afresh."
- Several databases: "When this answer was written on 7 October 2026, PubMed and ClinVar were not answering at NCBI, so ..."
- Unnamed: "When this answer was written on 7 October 2026, some of NCBI's databases were not answering, so ..."

## Why the date is added on reading, not on saving

- Owner decision D17 prefers dating at save time from the stored timestamp. That timestamp (`created_at`) is a database default filled on insert, so the text cannot be dated from it at capture without a guessed clock or a schema change. A migration is out of bounds.
- Dating on reading uses the row's own `created_at`, covers every answer saved before this card, and changes no stored text.
- The change is in `feedback/outage_note.py`, called by `get_saved_answer`, so the web screen and the MCP reopen tool both get it. The frontend is unchanged.

## Tests

- `tests/system_03_search_agent/feedback/test_outage_note_dated.py`: each live wording (built by the live function) reopens with the date and without "right now" or "Try again later"; the older saved wording does too; an answer with no outage note is returned unchanged; the live builder keeps "right now"; `get_saved_answer` dates the note from the row and leaves stored text alone.
- Red first: with the dating function made a no-op, 7 of 9 failed. With it restored, all 9 pass.
