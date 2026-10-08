# Card 67 diagnosis: the outage note has no date

## Table of contents

- [Where the note is composed](#where-the-note-is-composed)
- [How it reaches the stored answer](#how-it-reaches-the-stored-answer)
- [How the saved screen shows it](#how-the-saved-screen-shows-it)
- [Every wording variant](#every-wording-variant)

## Where the note is composed

- `_build_failed_search_note` in `src/system_03_search_agent/core/graph.py` builds the outage note from the typed `kind` and `source` of each failed call. The write step emits it as a `note` token.
- It always speaks in the present tense ("right now") and ends "Try again later."

## How it reaches the stored answer

- `answer_markdown_from` in `feedback/capture.py` writes every `note` token into the saved markdown as a plain block, unchanged.
- The row's `created_at` is a server default filled on insert, so capture does not hold the stored timestamp at the time it writes the text.

## How the saved screen shows it

- `get_saved_answer` in `feedback/history.py` returns the stored markdown and `asked_at` (the row's `created_at`). The web endpoint and the MCP tool `reopen_past_answer` both call it.
- `SavedAnswerScreen.tsx` renders the markdown as given, so the stale sentence shows as an ordinary paragraph.

## Every wording variant

| Variant | Opener |
|---|---|
| One database | "{Name} is down at NCBI right now, so this answer may be missing {records} from it." |
| Several databases | "{A} and {B} are down at NCBI right now, so this answer may be missing sources from them." |
| Unnamed | "Some of NCBI's databases are down right now, so this answer may be missing sources from them." |
| Mixed failure | Any of the above, then "Another background search did not finish, so other sources may be missing too." |
| Closing | "Try again later." |
| Older saved rows | "{Name}'s search is down at NCBI right now, so this answer has no papers from it. Try again later." |

The "did not finish" notes ("Ask again to retry", "Ask again in a minute") are not outage notes and are not changed.
