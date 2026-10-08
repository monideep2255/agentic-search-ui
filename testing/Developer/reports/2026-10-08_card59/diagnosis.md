# Card 59 diagnosis: Stop after the server finished

The card, in the reader's words: a question stopped after the server had already finished shows "Search stopped" on screen, yet comes back as answered in history after a reload, and the conversation remembers it, so the next "it" can refer to an answer the person was told was stopped. Evidence: card 58's review, F-58-V02 and F-58-A05 (`testing/Developer/reports/2026-09-27_card58_stop/review.md`). The owner's decision D18 (`testing/Board_plan.md`): an answer that finished before Stop arrived stands.

Read at develop 17b2a721. Paths are relative to `<repo-root>`. Every finding is from reading code and card 58's measurements; no live call was made.

## Table of contents

- [Summary](#summary)
- [How the screen decides "stopped"](#how-the-screen-decides-stopped)
- [How far the screen lags the stream](#how-far-the-screen-lags-the-stream)
- [What the server records when Stop arrives](#what-the-server-records-when-stop-arrives)
- [Where the three disagree](#where-the-three-disagree)
- [Options](#options)
- [A narrow window left on the server](#a-narrow-window-left-on-the-server)

## Summary

| Question | Answer |
|---|---|
| Who decides "stopped" today | The browser alone, the instant Stop is pressed, without asking whether the server had finished |
| How far the screen lags | Up to 13.3 s between the server's last event and the first sentence on screen (card 58, 11 develop runs) |
| What the server keeps after a late Stop | Everything: an answered history row with the saved answer, and the turn in session memory. A late stop is a no-op there |
| What the server keeps after an early Stop | A history row marked `refuse` with no saved answer, and no memory turn |
| Root cause | The screen decides before the only party that knows, the server, has said whether there was anything left to stop |
| Fix | Frontend only: the server's own stream is the verdict. `done` means the answer stands; the `cancelled` error means it stopped |

## How the screen decides "stopped"

- `stopCurrentRun` in `frontend/src/App.tsx` sets the `stopped` latch, aborts the event stream (`useAgentRun`'s `stop`), and fires `POST /v1/query/{run_id}/stop` without waiting for it.
- The latch drives three things: `usePacedEvents` flushes, `useAnswerReveal` freezes and withholds the whole answer if no sentence is on screen yet (`withholdAnswer`, card 58), and `RunProgress` swaps the stepper for the "Search stopped" block.
- Nothing in that path reads whether `done` had already arrived. Card 58 keeps Stop offered until the first sentence is on screen (`deriveStopOffered` in `frontend/src/components/chat/StopButton.tsx`), which is often after `done` has arrived, so a Stop on a finished answer is the common case, not an edge.
- Because the stream is aborted on press, the browser never reads the server's reply to the stop: the `cancelled` fatal error that `core/run_registry.py`'s `_drain_into_entry` appends when it really cancels a run.

## How far the screen lags the stream

- `usePacedEvents` holds arrived events back so each stage can be read. Its ceiling grows with the helpers the plan named (`maxLagFor`: 3.2 s plus 1.9 s per extra helper).
- `useAnswerReveal` then holds the first sentence until the writing banner has been up 1.5 s.
- Card 58's builder measured 11 develop runs (`testing/Developer/reports/2026-09-27_card58_stop/builder.md`): in 9 the server had finished 0.8 to 13.3 s before the first word was on screen. On G-013 the server finished at 17.3 s and the reader saw the first word at 30.1 s.
- So for up to 13 s the person sees the search still running, with Stop on, while the server has already answered, recorded and remembered.

## What the server records when Stop arrives

The order of a finished run in `core/run.py`'s `run_streaming`:

1. The graph's events are yielded, `done` last.
2. `_remember_turn` folds the turn into session memory (`core/session_memory.py`'s `remember_turn_for_caller`).
3. The `finally` block runs `_capture_interaction`, which writes the `interactions` row. For an `answer`, `flag` or `ask` outcome on a signed-in account it saves the answer (`feedback/capture.py`, `_SAVEABLE_OUTCOMES`).

Stop after the server finished:

- `cancel_run` in `core/run_registry.py` cancels only a task that is not done, so a late stop changes nothing.
- History: the row is answered and has a saved answer. After a reload `mergeServerHistory` marks the rail row as saved, and opening it shows the answer.
- Memory: the turn is kept, so the next follow-up's "it" can resolve to the answer the person was told was stopped.

Stop before the server finished:

- The drain task is cancelled. `_drain_into_entry` appends a fatal `error` with `error_class` `cancelled`, and no `done` reaches any reader.
- `_remember_turn` sits after the graph loop, so it is never reached: no memory turn.
- The capture row is written from a synthesized `done` with `trust_outcome` `refuse`, which is never saved as an answer. History shows nothing answered.
- Card 58's backend arms S2 and S3 (`tests/system_03_search_agent/core/test_run_registry_stop_mid_write.py`) prove the stream and the row.

## Where the three disagree

| When Stop is pressed | Screen today | History | Memory |
|---|---|---|---|
| Before the server finished | Search stopped | Not answered | No turn |
| After `done` arrived in the browser, answer still held back on screen | Search stopped | Answered, saved | Turn kept |
| While `done` is in flight | Search stopped | Answered, saved | Turn kept |

The first row agrees. The second is the card, and it is the common one because of the lag. The third is the boundary: the browser had not seen `done` yet, so even a rule "show the answer if `done` arrived" would still say "stopped" there.

## Options

- A, chosen: the server's stream is the verdict, frontend only. On Stop, if `done` has already arrived, the answer stands and shows at once in full. Otherwise send the stop and keep reading: whichever terminal event comes next decides. `done` means the server finished first, so the answer shows. The `cancelled` error means the stop landed first, so "Search stopped" shows. The screen then always says what the server recorded, by construction. The cost: between the press and the verdict, normally one round trip, Stop reads "Stopping…" and the screen holds still.
- B, rejected: retract a finished answer on a late stop, deleting the saved answer and the memory turn. It contradicts D18, needs the stop endpoint and the run record to change, and is outside this card's fence.
- C, rejected: decide in the browser from what has arrived and keep "Search stopped" immediate otherwise. It fixes the common case and leaves the boundary row open.

## A narrow window left on the server

Outside this card's fence, so reported rather than changed.

- After `run_streaming` yields `done`, the drain task still runs: the graph loop winds down, then `_remember_turn`, then capture in the `finally`.
- A stop that reaches the server in that window (the browser pressed Stop less than one round trip before `done` arrived) still cancels the task. The browser shows the answer, since `done` reached it, but the cancellation can skip `_remember_turn` and can interrupt the capture write.
- Result: the answer on screen, and the memory turn, and possibly the history row, missing. Rare, since it needs a press within milliseconds of the server finishing, but it is the same class of disagreement.
- Recommended follow-up: `cancel_run` treats a run whose buffered events already hold a `done` as finished and does not cancel it. A two-line change in `core/run_registry.py` with one registry test.
