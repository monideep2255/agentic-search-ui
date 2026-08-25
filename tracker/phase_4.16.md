# Build phase 4.16: the UI defects from the live demo

Branch: `phase/4.16-ui-streaming-fidelity`
Depends on: 4.12, merged 2026-08-24 as PR #61
Opened: 2026-08-25
Status: OPEN. Scouted, root cause measured, backend premise gate written and watched failing 5 of 5. No product code written yet.

Inserted 2026-08-25 by product-owner decision, the fifth such exception after 4.8, 4.10, 4.11/4.12 and 4.14/4.15. Section 25 does not contain it. It exists because build phase 4.12 put the product in front of a person for the first time, and that person found six defects that no suite in this repository can see.

## Table of contents

- [What this phase is for](#what-this-phase-is-for)
- [The root cause, measured before any ticket was written](#the-root-cause-measured-before-any-ticket-was-written)
- [Two recorded claims this phase corrects](#two-recorded-claims-this-phase-corrects)
- [The constraint is the node boundary, not the missing emit](#the-constraint-is-the-node-boundary-not-the-missing-emit)
- [What the design actually specifies, read rather than assumed](#what-the-design-actually-specifies-read-rather-than-assumed)
- [Tickets](#tickets)
- [Coverage: what this phase does not cover](#coverage-what-this-phase-does-not-cover)
- [History](#history)

## What this phase is for

The six defects the product owner reported from the live demo on 2026-08-24, recorded in their own words in `tracker/phase_4.12.md` and carried past that merge deliberately:

1. "Streaming does not work properly."
2. "Then chat does not continue", a second turn cannot be taken.
3. "The search is super super super super slow."
4. "The answer presentation is horrible and nothing close to what the design sync had."
5. "I do not see the KGX, REST API, command line or MCP setup up properly on the integrations page."
6. No client-side routing. Every page serves at `/` and the URL never changes.

## The root cause, measured before any ticket was written

Defects 1 and 3 are one defect, and it is in the BACKEND, not the frontend. Measured on the deployed API on 2026-08-25 by timestamping each SSE frame as it arrived, rather than by reading either side's code:

```
[ 0.15s] guard
[ 0.15s] think
[ 1.41s] plan
[12.32s] token, token, citation x3, trust_signal x4, done    all within 10ms
```

Three facts follow from that trace, each of which kills a plausible hypothesis:

- The wire is not buffered. Guard, think and plan arrive at three distinct times, so Railway's edge is forwarding `text/event-stream` incrementally. A proxy-buffering theory is dead.
- The browser is not at fault. `useAgentRun` reads the body incrementally and dispatches every frame on arrival (`frontend/src/hooks/useAgentRun.ts`, lines 308 to 330). It is consuming correctly. Nothing is being sent to consume.
- There is a 10.9-second silence between `plan` and the answer, which is the entire Act step, and it emits nothing at all.

THE CAUSE: `sink.emit` in `src/system_03_search_agent/core/graph.py` is called with `guard`, `think`, `plan`, `cost`, `token`, `citation`, `trust_signal`, `error` and `done`. It is NEVER called with `tool_start` or `tool_result`. Both types are defined in the contract (`contracts/events.py`, lines 317 and 335) and all three of the other adapters handle them (`adapters/cli/render.py`, `adapters/mcp/server.py`, `adapters/graphql/fold.py`). Only the producer is missing.

WHAT THAT COSTS ON THE WEB UI, all in `frontend/src/hooks/useRunView.ts`:

| Line | Reads | Consequence |
|------|-------|-------------|
| 198 | `has("tool_start")` sets the active step to Act | The Act step never goes live. The stepper sits on Plan for eleven seconds |
| 207 | `tool_start` or `tool_result` marks Act reached | Act never joins `reachedSteps` |
| 225 | Builds every tool chip from those two types | No tool chip ever appears, on any run |
| 618 | Counts tools for the answer meta line | The meta line always says zero tools |

That module's own docstring, written 2026-08-12, states the consequence exactly: "If the agent emits no `tool_start`, no tool chip appears." It was written as a design principle and had been describing a live defect ever since.

This is `LEARNINGS.md` row 110's lesson reached a second time: when a UI finding names a missing capability rather than a wrong appearance, probe the surface that would have to supply it before deciding which layer owns the defect. Reading the frontend alone would have produced a fix in the wrong repository half.

## Two recorded claims this phase corrects

Both are corrected by measurement rather than quietly dropped, which is this repository's standing practice for a carried-forward figure:

- `tracker/phase_4.12.md` states the API "emits `token` events throughout a 15.8-second answer". It does not. It emits TWO `token` events, both inside the same 10ms burst at the end. The Write step chunks a completed synthesis; it does not stream one.
- The same file's lead for whoever picked this up was "check whether the SSE stream is being consumed incrementally BEFORE treating latency as a separate problem". The premise is right and the layer is wrong: consumption is correct and emission is absent. Following it as written would have sent the work into the browser.

The lead was still load-bearing. It said do not optimise latency before checking streaming, and that is exactly what stopped this phase from opening with a performance ticket.

## The constraint is the node boundary, not the missing emit

Found 2026-08-25 while scoping T-4.16-01, BEFORE any code was written, and recorded rather than quietly folded into the ticket, because the first version of that ticket would not have fixed the defect.

`core/run.py`'s `run_streaming` drives `compiled_graph.astream(initial_state, stream_mode="updates")`, which yields one dict per COMPLETED node. `_EventSink` accumulates a node's events and hands them back through `sink.result()`, so a node's events reach the wire only when that node RETURNS. That is why the measured trace has three separate arrival times: guard, think and plan are three nodes.

`act_node` is one node that runs every tool. So adding `sink.emit("tool_start", ...)` inside its loop, which is what T-4.16-01 originally said, would flush every tool event in a single burst at 12.3 seconds, immediately before the tokens. The stepper would flash through Act at the very end and the eleven-second silence would be unchanged. The fix would have looked right in a unit test and changed nothing a person can see.

`act_node` also has no `_EventSink` at all today. Sinks are constructed at lines 700, 1290, 2519 and 5118, which is guardrail, think, plan and write. Act was written to return state, not to emit, so this is a node that has never produced an event of any kind.

WHAT THE TICKET ACTUALLY NEEDS: the events must escape `act_node` while it is still running. `langgraph.config.get_stream_writer` is available in the installed version and is the idiomatic mechanism, paired with a multi-mode `astream`, so a tool event is written to the custom stream at dispatch time AND still returned through `sink.result()` for the state reducer. The two are not alternatives: the custom write is what a reader sees live, and the returned event is what keeps `seq` and the replay buffer whole.

Verified rather than assumed: `get_stream_writer` imports from the installed `langgraph`, probed directly rather than read from the version pin, which is `langgraph>=0.2` and therefore says nothing about which minor is actually present.

THE GENERAL FORM, and it is `attack-the-constraint` reached from a new direction: the missing emit is the visible absence, and the node boundary is what actually bounds streaming latency. A fix aimed at the absence would have been a fix aimed at a non-bottleneck.

## What the design actually specifies, read rather than assumed

Defect 4 must not be guessed at, per `docs/build/design/Design_to_build_workflow.md`, and the same discipline was applied to defect 1 before writing T-4.16-01.

- `design-system/screens/streaming.html`, the component card and therefore the source of truth, shows the run screen as a stepper, a "Querying" line, three tool chips and Stop. It shows NO answer text. The current `RunScreen` matches its card on structure.
- `design-system/prototype/app.html` does not type the answer in either. `showAnswer(item)` fires whole, 1.6 seconds after Write begins. What carries the wait in the prototype is the live reasoning trace, one timestamped line per stage, plus tool chips landing as each tool fires.

So the fix for defect 1 is NOT to stream answer text into the run screen. Neither artifact asks for that. It is to make the Act step visible, which is what both artifacts show and what the backend never sends.

## Tickets

| Ticket | What | Status |
|--------|------|--------|
| T-4.16-01 | Emit `tool_start` and `tool_result` from the Act step AT DISPATCH TIME, not at node return, so the eleven-second silence becomes the tool chips both design artifacts show. Needs `get_stream_writer` plus a multi-mode `astream` in `core/run.py`, not just an `emit` call in `core/graph.py`. See the section above for why the obvious version fixes nothing. Closes defects 1 and 3's cause | todo |
| T-4.16-02 | Reproduce defect 2 in a browser BEFORE writing a fix, then fix it. `ask()` reads correct on inspection, so the cause is not visible from the source and a fix written from reading would be a guess | todo |
| T-4.16-03 | Answer presentation against the component cards, never the prototype, per `Design_to_build_workflow.md`. Scope set only after a screenshot comparison against each card, which is the step build phase 4.9 recorded as the only thing that finds this class | todo |
| T-4.16-04 | Integrations page corrected to the surfaces that actually shipped. Four concrete errors listed below | todo |
| T-4.16-05 | Client-side routing: `/`, `/integrations`, `/about`, `/docs`. `serve -s dist` is already SPA mode, so deep links resolve once routes exist and no server change is needed | todo |
| T-4.16-06 | The premise gate, written first and watched failing. Every arm carries a populate-check from its first line | in progress. Backend arms landed: `tests/system_03_search_agent/core/test_phase_4_16_premise.py`, 5 arms, all 5 red for the right reason with every populate-check passing first. Frontend arms (routing, integrations, second turn) not yet written |
| T-4.16-07 | The offline mutation harness for this gate, per build phase 4.7's durable fix | todo |
| T-4.16-08 | Re-measure the Act step after T-4.16-01 lands and decide whether defect 3 has any residue once the wait is legible. Deliberately NOT a performance ticket yet | todo |

T-4.16-04's four errors, each verified against the code rather than reported from the page:

- The command line card prints `ncbi-search ask "..."`. The shipped console scripts are `s3` and `s3-kgx-export` (`pyproject.toml`, lines 54 and 55). The advertised command does not exist.
- The KGX card prints `POST /v1/export/kgx`. No such route exists in `adapters/`. KGX export ships as the `s3-kgx-export` console script, which is what build phase 4.4 delivered.
- The MCP card prints an elided `https://.../mcp` rather than the deployed URL, so it cannot be copied and used.
- GraphQL is absent from the page entirely. It shipped in build phase 4.3 as PR #48 and is mounted at `/graphql` (`adapters/graphql/router.py`, line 70). The page's own lede says "reachable four ways" and there are five.

## Coverage: what this phase does not cover

Stated up front so a gap in it is arguable rather than discovered, per `goal-contracts` and build phase 4.4's stated-blind-spot lesson.

- It does not touch grounding, citation or the trust gate. No ticket here changes what is asserted or what backs it.
- It does not address the `GCK` production-only refusal carried open from build phase 4.12. That is an entity-resolution defect with an unproven hypothesis and it needs the traceback first.
- It does not add a visual regression check. This repository still has none, which is build phase 4.8's recorded lesson and the reason this defect list came from a person. Opening the application and looking at it remains a real step in this phase's cadence rather than a nicety.
- It does not make the Write step stream token by token. Neither design artifact asks for it, and doing it would be a scope decision rather than a defect fix.

## History

- 2026-08-25: Opened after the product owner ranked the UI defects ahead of build phase 4.14. Preflight READY on all three transports.
- 2026-08-25: Scouted before writing. Measured the deployed SSE stream frame by frame, found the 10.9-second Act silence, and traced it to `tool_start` and `tool_result` never being emitted. Corrected two recorded claims in `tracker/phase_4.12.md` in the process.
- 2026-08-25: Read both design artifacts before scoping defect 1, and found that neither specifies streaming answer text, which redirected the ticket from the browser to the Act step.
- 2026-08-25: Backend premise gate written and watched failing, 5 arms, 5 red. A5's failure message printed the production event list verbatim, `guard cost think cost plan cost token citation trust_signal trust_signal cost done`, which is the deployed trace with no tool frame in it. TWO GAPS IN THE GATE RECORDED IN ITS OWN DOCSTRING rather than left to a reviewer: A3 stops at its presence check and never reaches the timing comparison that is its whole reason for existing, and A4's populate-check is currently what fails, so it proves nothing A1 does not. Both are closed by T-4.16-07's mutation, not by reading. One defect found in the gate's own fixture while watching it fail: the daily-cap stubs were written `async` against two sync call sites, so every run logged `coroutine ... was never awaited` and the stub silently did not run.
- 2026-08-25: Corrected T-4.16-01 before writing any code. Events flush at node return, so emitting inside `act_node`'s loop would have delivered every tool event in one burst at 12.3 seconds and changed nothing visible. The node boundary is the constraint, not the missing emit.
