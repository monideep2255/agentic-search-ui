# Streaming and "writing the answer", measured on develop, 2026-09-14

Commit 2b6d274. Measured by a sub-agent; its own write of a report file was refused, so the main agent recorded its findings here. Scripts, raw event timings (`events_raw.json`), the 28-frame timeline (`timeline.json`) and key frames are beside this file.

## Findings

- Event timing, 6 live runs (BRCA1 Plain language x3, GCK Researcher x3): all 14 to 33 `token` events for an answer arrived within 1.3 to 216.7 ms of each other, after a silent gap of 1.9 to 22.6 seconds following Act's last `tool_result`. `citation`, `trust_signal` and `done` followed within tens of milliseconds. Nothing streamed progressively.
- Backend: `_EventSink.emit` (graph.py around line 642) only appends to a list, and events reach the client when the node returns. `_EventSink.emit_live` (around line 659) pushes events out of a running node and is already used by `act_node` since build phase 4.16. `write_node` uses plain `sink.emit` for every token, citation and trust signal, and builds sentence chunks only after the Synth call is fully awaited and grounding has finished.
- Screen, 28 frames at 250 ms on the BRCA1 question: "is writing the answer" never appeared. The claim count jumped from 0 to 9 in one 335 ms window. From 4.0 s to 8.8 s the stepper sat on ACT with an open ring, although Act finished at 3.3 s.
- Frontend: `useRunView.ts` around line 395 sets the active step to Write only when a `token` event exists, which is the moment Write has already ended.

## Root causes

- Streaming: built, but the backend sends everything at once, because Write uses `emit` rather than `emit_live`.
- Writing state: built, but never visible, because the frontend enters Write only on the first token.

## Recommendations, ranked

1. The frontend enters Write when Act completes, with a minimum visible time for the banner. Low cost and risk. Assigned to the answer-layout agent.
2. The frontend reveals a token burst one item at a time at reading pace. Low to moderate cost, frontend only, does not touch cite-or-refuse. Assigned to the answer-layout agent.
3. `write_node` emits its start and each grounded sentence with `emit_live`, the fix already proven for `act_node`. Moderate cost, needs care on the cite-or-refuse path. Queued until the agent currently editing `graph.py` lands.
4. Streaming the model's raw draft text. Not recommended: ungrounded text would reach the screen, which the cite-or-refuse gate forbids.
