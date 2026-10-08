# Card 59 build: an answer that finished before Stop arrived stands

Option A of `diagnosis.md`, per owner decision D18. Frontend only. No backend file, migration or package changed.

## Table of contents

- [The change, in the reader's words](#the-change-in-the-readers-words)
- [How it works](#how-it-works)
- [Choices](#choices)
- [Tests](#tests)
- [Left open](#left-open)

## The change, in the reader's words

- Stop pressed on an answer the server had already finished: the whole answer shows at once, with its sources and trust line. History and the conversation hold the same answer, so the next "it" refers to an answer the person can see.
- Stop pressed while the server is still working: Stop reads "Stopping…" for about one round trip, then "Search stopped". Nothing is recorded as answered and nothing is remembered, as before.
- Stop pressed in the instant the server finishes: the server's reply decides. The screen shows the answer or "Search stopped", never both and never neither.
- If the stop request fails, or no reply comes within 5 seconds, the screen shows "Search stopped", as it did before this card.

## How it works

- `deriveStopVerdict` in `frontend/src/components/chat/StopButton.tsx` reads the first terminal event on the arrived stream after a press: `done` means `answered`, the `cancelled` error means `stopped`, neither means `pending`. A stream that ended with neither falls back to `stopped`.
- `frontend/src/App.tsx` no longer aborts the stream on Stop. If `done` has already arrived it sends nothing and the answer lands. Otherwise it sends the stop and keeps reading, so the server's reply reaches the screen.
- While `pending` and after `stopped`, the screen shows the run as it stood at the press (`stopPress.mark`); the reveal stays frozen, so no sentence appears under a stop that may yet be confirmed.
- On `answered` the pacing and the reveal flush, so the answer lands in full at once.
- A confirmed stop's `cancelled` error is treated as a normal end of the stream, not a failure, so no error text shows under "Search stopped".
- `RunProgress` takes a `stopping` prop: Stop reads "Stopping…" and stays off.

## Choices

- The server decides, not the browser. Rejected: deciding from what the browser has seen, which leaves the in-flight case wrong; retracting a finished answer on the server, which contradicts D18 and is outside the fence.
- No stop is sent once `done` has arrived. A cancel landing while the server still files the answer could cut that filing short (see "Left open").
- "Stopping…" for one round trip, rather than an immediate "Search stopped" that might flip to the answer. Honesty over polish: the screen never states an outcome it later takes back.
- Card 58's arms in `frontend/src/App.stopUntilAnswer.test.tsx` that pressed Stop after `done` encoded the behaviour D18 reverses. They now keep the stream open at the press and confirm the stop with the server's `cancelled` error, so they still prove what a stop leaves on screen (F-58-J02, F-58-A01, F-58-J03).

## Tests

- New `frontend/src/App.stopAfterAnswer.test.tsx`, four arms. Seen red before the change: Stop after the server finished (no answer appeared, "Search stopped" did), Stop before it finished ("Search stopped" showed before the server confirmed), and the in-flight boundary ("Search stopped" showed before the server replied). Green after. The fourth arm, a failed stop request falls back to "Search stopped", passed before and after as a guard.
- The boundary arm watches every element added to the page, so a "Search stopped" that flashed up before the answer fails it.
- New `deriveStopVerdict` unit arms in `frontend/src/components/chat/StopButton.test.tsx`, including the first-terminal-wins rule.
- Card 58's seven arms green after the rework. Server side, "no answered record and no memory turn" for a stop before the server finished is card 58's backend arms S2 and S3 (`tests/system_03_search_agent/core/test_run_registry_stop_mid_write.py`) plus `_remember_turn` sitting after the graph loop; no backend code changed here.

## Left open

- The server window in `diagnosis.md`, last section: a stop reaching the server after it sent `done` but before it finished filing (memory, then the history row) can still skip that filing while the screen shows the answer. Rare: it needs a press within one round trip of the server finishing. Fix outside this card's fence: `cancel_run` in `core/run_registry.py` leaves a run whose buffered events already hold `done` alone.
