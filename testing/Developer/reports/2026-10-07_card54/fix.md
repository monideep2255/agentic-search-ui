# Card 54 fix round

One fix round for pull request #202, answering the judge and adversary reports in this folder.

## Table of contents

- [J-54-01 and A-54-02: old answers that reopen short](#j-54-01-and-a-54-02-old-answers-that-reopen-short)
- [J-54-03 and A-54-01: comments that still said 50](#j-54-03-and-a-54-01-comments-that-still-said-50)
- [A-54-06: order and survivors](#a-54-06-order-and-survivors)

## J-54-01 and A-54-02: old answers that reopen short

What changed:

- The saved-answer reply (`GET /v1/history/{trace_id}/answer`) carries a new field, `citations_omitted`. It counts the distinct `[n]` markers in the stored answer text that have no stored citation numbered `n`. It is read from the row's own data, never from a date, and uses the same marker pattern the MCP reopen uses, so web and MCP agree. It defaults to 0 and is additive within v1.
- The client parser reads the field (0 when absent). The reopened answer screen shows one line under the sources when the count is above 0.

The exact line, where N is the highest source number the saved answer kept:

- With sources kept: "This answer was saved when only its first N sources were kept, so markers above [N] have no source listed."
- With none kept: "This answer was saved without its sources, so its markers have no source listed."

Tests:

- Endpoint: 50 stored citations under text citing [1] to [61] reports 11; a complete answer reports 0. Red before the change (the field did not exist, and with the count forced to 0 the test fails).
- Screen: through the real parser into the real screen, a reply with `citations_omitted` 60 and one stored citation numbered 50 shows the line above, and a reply with 0 shows none. Red with the line removed.

## J-54-03 and A-54-01: comments that still said 50

- `adapters/web_sse/app.py`: the `_MAX_CITATIONS_PER_RUN` comment now names `MAX_CITATIONS_PER_ANSWER` (100), and the "left open" paragraph in the export now says the cap moved with card 54.
- `adapters/graphql/types.py`: the export is described as 100, and "the 50-citation cap" reads "the 100-citation cap".
- `tests/.../feedback/test_contracts.py`: the ceiling test docstring names `MAX_CITATIONS_PER_ANSWER` instead of 50.

The spec and `adapters/mcp/server.py` line 170 are outside this round's file fence and stay open.

## A-54-06: order and survivors

Three tests now fail when citations are stored or returned in another order, or when the wrong ones survive the ceiling:

- Capture: 120 citation events numbered 1 to 120 store numbers 1 to 100 in order. Red when capture iterates `reversed(events)`.
- Saved-answer reply: 61 stored citations come back numbered 1 to 61 in order. Red when the endpoint reverses the list.
- REST export: 120 events export numbers 1 to 100 in order. Red when the export iterates `reversed(entry.events)`.
