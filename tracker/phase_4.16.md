# Build phase 4.16: the UI defects from the live demo

Branch: `phase/4.16-ui-streaming-fidelity`
Depends on: 4.12, merged 2026-08-24 as PR #61
Opened: 2026-08-25
Status: MERGED as PR #63 on 2026-08-25, and VERIFIED LIVE on the deployed product. All seven defects closed. One residual named rather than glossed: 6.4 seconds still pass between the last `tool_result` and the answer, because the Write step emits nothing while it synthesises. That is T-4.16-08 and it is the same defect class one step further along.

Inserted 2026-08-25 by product-owner decision, the fifth such exception after 4.8, 4.10, 4.11/4.12 and 4.14/4.15. Section 25 does not contain it. It exists because build phase 4.12 put the product in front of a person for the first time, and that person found six defects that no suite in this repository can see.

## Table of contents

- [What this phase is for](#what-this-phase-is-for)
- [The root cause, measured before any ticket was written](#the-root-cause-measured-before-any-ticket-was-written)
- [Two recorded claims this phase corrects](#two-recorded-claims-this-phase-corrects)
- [The constraint is the node boundary, not the missing emit](#the-constraint-is-the-node-boundary-not-the-missing-emit)
- [What the design actually specifies, read rather than assumed](#what-the-design-actually-specifies-read-rather-than-assumed)
- [Tickets](#tickets)
- [The near miss, recorded because it was one line from shipping](#the-near-miss-recorded-because-it-was-one-line-from-shipping)
- [Defect 7, the feedback thumbs, and why it read as two problems](#defect-7-the-feedback-thumbs-and-why-it-read-as-two-problems)
- [One pre-existing end-to-end failure, proven not ours](#one-pre-existing-end-to-end-failure-proven-not-ours)
- [Defect 2 does not reproduce, and what looking for it found instead](#defect-2-does-not-reproduce-and-what-looking-for-it-found-instead)
- [Defect 4, the answer presentation, measured against the card](#defect-4-the-answer-presentation-measured-against-the-card)
- [Routing and the integrations page, both done](#routing-and-the-integrations-page-both-done)
- [Defect 2 was a missing conversation thread, and both earlier readings were wrong](#defect-2-was-a-missing-conversation-thread-and-both-earlier-readings-were-wrong)
- [Superseded: defect 2 read as salience](#superseded-defect-2-read-as-salience)
- [Two presentation defects fixed, and one design gap the cards do not cover](#two-presentation-defects-fixed-and-one-design-gap-the-cards-do-not-cover)
- [The browser suite cannot reach a real tool dispatch](#the-browser-suite-cannot-reach-a-real-tool-dispatch)
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
7. Added 2026-08-25, in the product owner's own words: "the feedback buttons were not working properly. The down arrow was outside the box."

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
| T-4.16-01 | DONE, `1786b02` and `4dd4752`. Emit `tool_start` and `tool_result` from the Act step AT DISPATCH TIME, not at node return, so the eleven-second silence becomes the tool chips both design artifacts show. Needs `get_stream_writer` plus a multi-mode `astream` in `core/run.py`, not just an `emit` call in `core/graph.py`. See the section above for why the obvious version fixes nothing. Closes defects 1 and 3's cause | todo |
| T-4.16-02 | DONE. The real defect was that the answer screen had NO THREAD: every follow-up replaced the previous turn, which the prototype archives into a collapsed `<details>` and keeps. Settled by the product owner 2026-08-25: "follow up is part of the current search" | done |
| T-4.16-02a | Superseded record: the reported defect DOES NOT REPRODUCE as stated. Signed in and as a guest, locally and on the deployed demo, a second turn lands. Three real defects were found while trying, all recorded below, none of them the reported one. NEEDS THE PRODUCT OWNER to say what they saw | blocked, product owner |
| T-4.16-03 | BOTH SEPARATE DEFECTS DONE. The chip no longer repeats its source, and the `ask` outcome no longer blames the reader for the evidence. The four card gaps that traced to missing tool events are closed by T-4.16-01 and need re-measuring after deploy | done, pending re-measure |
| T-4.16-04 | DONE. Integrations page corrected to the five surfaces that actually shipped, and cross-checked against `pyproject.toml` and the FastAPI route table by a Python test, since nothing linked the page's prose to the modules it describes | done |
| T-4.16-05 | DONE. Client-side routing over the History API, NO new dependency for four static paths. Four browser arms including back and forward; mutation-proven | done |
| T-4.16-06 | Backend arms DONE, frontend arms open. The premise gate, written first and watched failing. Every arm carries a populate-check from its first line | in progress. Backend arms landed: `tests/system_03_search_agent/core/test_phase_4_16_premise.py`, 5 arms, all 5 red for the right reason with every populate-check passing first. Frontend arms (routing, integrations, second turn) not yet written |
| T-4.16-07 | DONE, `1786b02`. The offline mutation harness, 7 cases over all 5 arms. M1 applies the plausible wrong fix in process and pins A3 red on its TIMING branch, closing the gap the gate recorded about itself | done |
| T-4.16-10 | DONE, defect 7. The thumb-down glyph rendered 8.5px outside its own button, so clicking what a reader could see missed the control. One defect, two symptoms | done |
| T-4.16-09 | DONE, as a scripted-stream arm plus the producer-side premise gate. A REAL dispatch is unreachable from the browser suite and that is recorded rather than papered over. Originally: an end-to-end arm that LOOKS AT a rendered tool chip. No Playwright spec in this repository has ever emitted a `tool_start`, and only one has ever emitted a `tool_result`, so the chip path has never been exercised in a browser. Nothing at the hook level feeds `tool_start` either | todo |
| T-4.16-08 | Re-measure the Act step after T-4.16-01 lands and decide whether defect 3 has any residue once the wait is legible. Deliberately NOT a performance ticket yet | todo |

T-4.16-04's four errors, each verified against the code rather than reported from the page:

- The command line card prints `ncbi-search ask "..."`. The shipped console scripts are `s3` and `s3-kgx-export` (`pyproject.toml`, lines 54 and 55). The advertised command does not exist.
- The KGX card prints `POST /v1/export/kgx`. No such route exists in `adapters/`. KGX export ships as the `s3-kgx-export` console script, which is what build phase 4.4 delivered.
- The MCP card prints an elided `https://.../mcp` rather than the deployed URL, so it cannot be copied and used.
- GraphQL is absent from the page entirely. It shipped in build phase 4.3 as PR #48 and is mounted at `/graphql` (`adapters/graphql/router.py`, line 70). The page's own lede says "reachable four ways" and there are five.

## The near miss, recorded because it was one line from shipping

T-4.16-01 was very nearly delivered as a backend-only change. It would have taken the deployed application DOWN rather than merely underdelivering, and the reasoning that nearly allowed it is worth keeping.

`frontend/src/lib/events.ts` re-validates every frame on receipt, and `isToolStartPayload` required `status` to be one of `ok`, `empty` or `error`. The widened producer emits `running`. Two things then had to be established rather than assumed:

- What rejection DOES. The first draft of the fix's own comment said the browser would "silently drop" the frame. That was wrong. `parseAgentEvent` THROWS, the throw leaves `consumeEventStream`, and `useAgentRun`'s catch sets `status: "error"` and abandons the stream. So every query would have died in the browser at the first tool frame with no answer rendered at all.
- How that was established. The test asserting rejection was written as `toBeNull()` and FAILED, which is what corrected the belief. Reading the guard had produced the wrong answer twice, once in the fix's comment and once in the test's first assertion.

A second, quieter half: `isToolResultPayload` delegates to `isToolStartPayload`, so widening the start guard silently widened the result guard too. A finished call could have reported itself as still running, leaving a chip spinning for ever. The type says it is re-narrowed, but a TypeScript type is erased at runtime and the guard is what actually decides, so it had to be re-narrowed there as well.

THE GENERAL FORM: a contract widened on the producer and not on its validator does not degrade gracefully, it fails hard on the first message. And the direction of the failure is not guessable from reading the validator, which is why it needed a test rather than an argument.

## Defect 7, the feedback thumbs, and why it read as two problems

Reported 2026-08-25: "the feedback buttons were not working properly. The down arrow was outside the box." It is ONE defect, and the functional half falls out of the visual half rather than being a second bug.

`Thumb` in `frontend/src/components/feedback/FeedbackSurface.tsx` put its rotation on the OUTERMOST `<svg>`. There, `transform` is not an SVG transform at all, it is a CSS one, resolved in the element's own pixel space instead of the viewBox coordinate system. So `rotate(180 8 8)` rotated about a point 8 CSS pixels from the element's origin rather than about the centre of a `0 0 16 16` viewBox, and displaced the glyph 16px down and to the right.

MEASURED IN CHROMIUM before anything was changed, because the correct and incorrect placements are one word apart and read identically:

| Variant | Result |
|---------|--------|
| Up, no transform | contained |
| Down, transform on the root `<svg>` | OUTSIDE: right 8.5px, bottom 8.5px |
| Down, transform on an inner `<g>` | contained |

WHY IT ALSO READ AS "NOT WORKING". The `<button>` stayed a correct 30 by 30 hit target throughout, and the send path was working the whole time (`e2e/feedback-submission.spec.ts`'s "a rating actually reaches the backend" passes, and passed before this fix). Only the glyph moved. So the thumb a person could SEE sat outside the control it belonged to, and clicking what they saw missed it.

THE GUARD is a bounding-box measurement in a real browser, added to `e2e/feedback-submission.spec.ts`, and it was mutation-run before commit: putting the `transform` back on the `<svg>` fails it on the down thumb with an 8px right overflow while the up thumb stays green, which is the asymmetry the defect actually had.

This is `LEARNINGS.md` rows 107, 108 and 109 for the fourth time. Every one of this repository's 211 frontend assertions checks WHAT is on screen and never WHERE, and jsdom has no layout at all, so a pure-geometry defect is invisible to all of them. It took a person looking at the page, again.

## One pre-existing end-to-end failure, proven not ours

`e2e/query-stream-and-stop.spec.ts`'s "a signed-in query streams through the pipeline and produces an answer" fails waiting for `getByTestId("answer-cap")`.

PROVEN PRE-EXISTING rather than argued: the branch was set aside and the same spec run at `e486310`, this phase's branch point on `develop`, where it fails identically with none of this phase's changes present. It is therefore not a regression from the Act-step events, and it is not this phase's to fix silently either. Recorded here with an owner rather than left in a passing-suite claim.

The current end-to-end figure is 33 passed, 1 failed, and that one is the row above.

## Defect 2 does not reproduce, and what looking for it found instead

T-4.16-02's ticket said reproduce before fixing, because `ask()` reads correct. It was reproduced against nothing: signed in and as a guest, locally against the mock and against the deployed demo, a second turn dispatches and lands. What the attempt found instead is three defects nobody had filed, two of them in this phase's own new work.

FINDING 1, AN ASSERTION THAT COULD NOT FAIL, WRITTEN BY THE LEAD. The first landed-signal helper waited for the "New search" button, copied from `e2e/feedback-submission.spec.ts`. That button is rendered by BOTH `RunScreen.tsx` line 168 and `AnswerScreen.tsx` line 305, so it is visible from the instant a question is dispatched, before a single event arrives. Both second-turn tests passed in under two seconds against it and proved nothing whatsoever. It was caught by SCREENSHOTTING the deployed demo after the helper said an answer had landed, and seeing the run screen with five pending pips and no answer on it. Reading the helper had not revealed it. This is the fifth assertion-that-cannot-fail in this repository's recorded history and the fourth written by a lead. The fix waits on `answer-meta`, which only `AnswerScreen` renders.

FINDING 2, THE GUEST PATH WAS NEVER EXERCISABLE IN THE BROWSER SUITE. With a correct landed signal, the guest test failed: `POST /v1/query` returned `net::ERR_FAILED`, which reads like CORS and is not. `tests/e2e_support/mock_llm_backend.py`'s env defaults omit `ANON_DAILY_RUN_CAP`, and `cost_control.anon_daily_run_cap` reads it through `_read_int_env`, which RAISES rather than defaulting. So every anonymous run 500'd and reset the connection. Guest coverage was not failing, it was ABSENT: no spec had ever asked a question without signing up first, which is the only way the deployed demo is actually used. This is the same unset variable build phase 4.12 hit in production as its defect 3, fixed there and not here, because nothing local exercised the path that needs it.

FINDING 3, A HAZARD THIS PHASE INTRODUCED AND CAUGHT. Two live diagnostic specs were written with docstrings saying "skipped by default" and NO skip in them. An ordinary `npx playwright test` would have fired both at the public demo, spending a real guest allowance and real model budget, and a CI run would have done it on every pull request. Both are now gated on `RUN_LIVE_DIAGNOSTICS=1`. A comment claiming a property is not that property, which is F-2.1-J5-01 reached from a new direction, this time in a test rather than in product code.

WHAT IS ACTUALLY LEFT OF DEFECT 2, and it needs the product owner rather than another agent. Three readings fit "then chat does not continue", and they are different work:

- The follow-up field was not FOUND. Measured on the deployed demo, it renders late, after the answer and after the "New search" button, and a `getByTestId` count taken the moment the answer landed returned zero before the element appeared. A reader looking for a way to continue may simply not have seen one.
- The conversation does not ACCUMULATE. By design, a follow-up runs a full search and the answer screen shows one answer at a time, replacing the last. There is no transcript. That is what `FollowUp.tsx` says it does and what the prototype does, so if the expectation was a chat log, this is a product decision and not a bug.
- Something environment-specific that neither environment reproduced.

Nothing is being guessed at here. The question is recorded and the ticket is blocked on the answer rather than closed as "works for me".

## Defect 4, the answer presentation, measured against the card

Captured 2026-08-25 from the DEPLOYED demo with a correct landed signal, at 1440 by 1000, and compared line by line against `design-system/screens/answer.html`. This is the gap list `Design_to_build_workflow.md` requires instead of guessing at "horrible".

| Aspect | The card | Deployed |
|--------|----------|----------|
| Status | "Answered", with a tick | "Needs a narrower question", with a query mark, ALONGSIDE a grounded five-citation answer |
| Meta line | "11.4s, 3 tools, 3 layers, 3 sources" | "11.2s, 0 TOOLS, 5 sources from 2 layers" |
| Answer body | Three claims, one per sentence, each ending in its own chip | ONE run-on sentence listing raw CURIEs, with all five chips bunched at the end |
| Citation chip | "1 Gene 672", "2 MedGen C0677776" | "1 gene 672", "2 MedGen MedGen:C0346153" |
| Sources | Expanded, each naming its record and layer | Collapsed behind "SOURCES 5", which is build phase 4.9's deliberate change and NOT a defect |
| Trust pills | Three: grounded, "High-risk claim, gene to disease", "3 layers agreed" | Two: "Grounded, every claim cited", "high risk claim". The layers-agreed pill is absent and the risk pill has lost its qualifier and its capitalisation |

FOUR OF THESE TRACE TO ONE ALREADY-FIXED CAUSE, which is why this ticket must be re-measured after T-4.16-01 deploys rather than worked from this table:

- "0 tools" is `view.toolCalls.length`, built from `tool_start` and `tool_result`, which nothing emitted until T-4.16-01.
- The missing "N layers agreed" pill is the same: `useRunView.ts` line 591 already records that "without `tool_result` events printed '0 layers agreed' beside source".
- So the meta line and the verdict strip were both reporting an Act step that was invisible, not an Act step that did not happen.

TWO ARE GENUINELY SEPARATE AND NEITHER IS FIXED:

- THE CHIP LABEL DUPLICATES ITS SOURCE. `useRunView.ts` line 277 builds a source name as `${payload.source} ${payload.source_id}`, and the deployed Layer 1 citation carries `source: "MedGen"` with `source_id: "MedGen:C0346153"`, a full CURIE, so the chip reads "MedGen MedGen:C0346153". The card wants the bare local id. Whether the fix belongs in the citation builder or in this formatter is undecided and must be settled by looking at where the value is produced, not by stripping the prefix in the UI because that is the nearer file.
- THE OUTCOME CONTRADICTS THE VERDICT. The strip says "Needs a narrower question" while the pills say "Grounded, every claim cited" on an answer with five resolving citations. One of the two is wrong and this is a trust-surface defect rather than a cosmetic one, since the product's whole argument is that its status line can be believed.

NOT YET COMPARED, and named so the absence is arguable: the run screen against `screens/streaming.html`, the source cards expanded against `components/source-card.html`, and every screen at a narrow viewport. This table is one screen at one size.

## Routing and the integrations page, both done

T-4.16-05, ROUTING, ADDS NO DEPENDENCY. `frontend/package.json` had no router and still has none. `production-standards` requires a security review for every new dependency and `system-design-patterns` puts it in the ASK bucket, which is right for a library that earns it. Four static paths, no parameters, no nested layouts, and one piece of state a router would only mirror do not earn it. `lib/routing.ts` is the History API in a few lines.

Deep links needed no server change and never did: `serve -s dist` is single-page-app mode, so `/integrations` always reached the app and there was simply no code to read it.

MUTATION-PROVEN, and the asymmetry is the point. Removing the `popstate` listener, leaving a push-only implementation, keeps the URL arm and the deep-link arm GREEN and fails only the back-button arm with "the URL went back but the page did not, so the address bar is lying". Three of the four arms cannot tell routing from half-routing, which is why that fourth one exists.

T-4.16-04, THE INTEGRATIONS PAGE, was never missing capability. Every surface it named had shipped. It described them in shapes that do not exist:

- `ncbi-search ask "..."`, a command that has never existed. `pyproject.toml` declares `s3` and `s3-kgx-export`.
- `POST /v1/export/kgx`, a route that does not exist, while the same card's body correctly called KGX "a batch job".
- An elided `https://.../mcp`, which cannot be copied and run.
- GraphQL absent entirely, under a lede reading "reachable four ways", when it shipped in build phase 4.3 and there are five.

THE GUARD IS A PYTHON TEST GRADING A TYPESCRIPT FILE, and that inversion is the fix rather than an oddity. The truth lives in `pyproject.toml` and the FastAPI route table, so no frontend test could have caught any of it. `tests/system_03_search_agent/test_integrations_page_claims.py` asserts that every command the page prints is a declared console script and every path it prints is a real route. A command on a page is a claim, exactly as a citation is.

TWO DEFECTS IN THAT GUARD, both found by mutation and both recorded:

- Its fixture read the raw file, so three arms matched `ncbi-search`, `POST /v1/export/kgx` and `https://...` inside the comment that DOCUMENTS them as the old defect. The tempting fix was deleting the comment, which would have passed the test and destroyed the record. Comments are stripped instead.
- Its own populate-check then asserted `"s3 ask" in text`, which is page CONTENT rather than fixture health. Under the mutation it fired first and masked all four real failures, reporting a broken harness for an intact page. It now counts `<Card` occurrences.
- And its surfaces arm asserted `"GraphQL" in source`, which passes against `"GraphQLXX"`. A substring check cannot see a renamed card. Now matched as an exact card title. That is the FOURTH assertion-that-cannot-fail in this phase and the third written by the lead.

## Defect 2 was a missing conversation thread, and both earlier readings were wrong

SETTLED 2026-08-25 by the product owner: "follow up is part of the current search. Check out style in the design system that we have." Reading the design system rather than reasoning about it produced the answer in one step, after two rounds of investigation had produced two wrong ones.

WHAT THE PROTOTYPE ACTUALLY DOES, which no component card covers and nothing in this repository had implemented. `askFollowUp` calls `archiveCurrent()`, which lifts the finished turn, its question, meta line, spine, answer, sources and verdict, into a collapsed `<details class="prev">` appended to `<div class="thread">`, and only then renders the new answer above it. The markup order in the prototype's answer section is `sources`, `verdict`, `thread`, then the follow-up form, so the current answer stays at the top, earlier turns sit beneath it, and the input that continues the conversation comes last.

The implementation had no thread at all. Every follow-up REPLACED the answer, so the previous turn vanished and the screen stopped reading as a conversation. The dispatch always worked, which is precisely why two rounds of hunting for a failed second turn found nothing wrong.

BOTH OF THIS PHASE'S EARLIER READINGS WERE WRONG, and are corrected here rather than deleted:

- "It renders late." An artifact of the vacuous landed-signal described above. With a correct signal it is in the DOM the moment the answer screen is.
- "It is salience, and `New search` is the competing affordance." Plausible, measured, and still wrong. The position measurements below stand as evidence and the conclusion drawn from them did not.

The measurements, kept because they remain true and they rule position out: the follow-up input's top is 463px at 1280 by 650, at 1440 by 760 and at 1440 by 1000, and 509px on the deployed demo. Above the fold everywhere tested.

THE MUTATION IS THE FINDING. Disabling the archive turns the two new arms red and leaves BOTH existing second-turn arms GREEN. Those two asked "can a second turn be taken" and answered yes, everywhere, on every path, in two environments. They were correct and they were measuring the wrong property. A test can be right, honest, and blind to the defect a person actually reported.

A DESIGN-SYSTEM GAP, recorded rather than worked around: the follow-up and the thread exist ONLY in `prototype/app.html`. `design-system/screens/answer.html` does not contain either, so the component cards, which `Design_to_build_workflow.md` makes the thing builders build against and gates assert on, have nothing to say about the surface that carries the conversation. The styling here is taken from the prototype's own `.prev` and `.thread` rules rather than invented, and the card should absorb it.

## Superseded: defect 2 read as salience

The product owner settled it on 2026-08-25: "I couldn't find the follow-up field". Measured rather than assumed from there, and one earlier note in this file is CORRECTED rather than carried: it said the follow-up "renders late", which was an artifact of the same vacuous landed-signal described above. With a correct signal it is in the DOM the moment the answer screen is.

POSITION IS NOT THE CAUSE. `e2e/followup-position-diagnostic.spec.ts` measures the input's top at three viewports:

| Viewport | Input top | Below the fold |
|----------|-----------|----------------|
| 1280 by 650, a 13-inch laptop | 463px | no |
| 1440 by 760 | 463px | no |
| 1440 by 1000 | 463px | no |

On the deployed demo, with a real answer above it, it measured 509px. Above the fold everywhere tested.

WHAT IS LEFT IS SALIENCE AND ONE COMPETING AFFORDANCE. "New search" is a bordered button in the answer's top-right corner. The follow-up is a 10.5px uppercase grey label over a quiet field, further down and below the trust pills. A reader wanting to ask another question reaches for the button they can see, and that button RESETS to the landing screen rather than continuing. That reads precisely as "then chat does not continue" while every mechanism underneath works, which is what this phase measured twice.

NOT FIXED, and deliberately. Raising the follow-up's prominence or demoting "New search" is a change to the answer screen's own composition, which `docs/build/design/Design_to_build_workflow.md` says originates from the product owner editing a card. The measurement above is the evidence for that decision, not a licence to make it.

## Two presentation defects fixed, and one design gap the cards do not cover

THE CHIP NO LONGER REPEATS ITS SOURCE. `sourceDisplayName` in `useRunView.ts` strips a `source:` prefix from `source_id` at display time only. Neither producer was wrong, which is why the fix is there: `core/graph.py` documents that "the CURIE prefix names the source database, the full CURIE is the source id", and a resolvable CURIE is what makes a Layer 1 citation followable. Trading a provenance field for a nicer label is the wrong direction in this product. Mutation-proven: restoring the plain join reproduces "MedGen MedGen:C0346153" and turns two of five arms red while THREE stay green, those three being the shapes a narrower test would have covered.

DELIBERATELY NOT NORMALISED: the case of `source` itself. Layer 2 sends "gene" and the card shows "Gene". Capitalising is right for that value and wrong for "dbSNP" and "MedGen", so it is left for the design card rather than guessed.

THE `ask` OUTCOME NO LONGER BLAMES THE READER. It said "Needs a narrower question" above a grounded answer with five resolving citations. The question was fine. Locked spec 8.3.3, in its own words: "Ask is reserved for a high-stakes claim resting on a single independent-origin source." It is the `(high, grounded, insufficient)` row of the decision table, so the backend was correct and the copy described something else entirely.

It now reads "Single source, not independently confirmed", stating the evidence the way the neighbouring pills do rather than instructing the reader. PRODUCT-OWNER DECISION, 2026-08-25, taken directly because the trust-pills design card has NO `ask` state at all: there was nothing to build against. That card gap is real and is recorded here for the card to absorb.

## The browser suite cannot reach a real tool dispatch

Found while building T-4.16-09 and recorded with an owner rather than worked around.

The e2e mock replaces the outbound MODEL call only. Entity resolution and the tools are real, so `plan_node` needs a live NCBI lookup to resolve BRCA1 before it can plan any tool. Driven against the mock backend, the answer came back "0 tools, 0 sources", and raising `PER_QUERY_COST_CAP_USD` changed nothing, which rules the cost cap out.

So T-4.16-09 ships as a SCRIPTED-stream arm. It proves the renderer turns tool frames into chips and a truthful meta line; it does not prove the backend emits them. That half is the Python premise gate driving the real loop. The two halves are in different languages against different surfaces, and NEITHER alone would have caught the shipped defect: the producer gate cannot see a chip, and the renderer arm cannot see a silent producer.

Mutation-proven: deleting the four tool frames reproduces the deployed meta line character for character, "0 tools, 1 source from 1 layer".

CARRIED, with an owner: making a real tool dispatch reachable from the browser suite. It is the same gap that leaves `query-stream-and-stop.spec.ts`'s `answer-cap` arm failing, since that arm also depends on the loop reaching a state this harness cannot produce.

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
- 2026-08-25: DEFECT 2 CLOSED, and it was neither of this phase's two earlier readings. The product owner pointed at the design system; the prototype archives each finished turn into a collapsed disclosure and keeps it on the page, and nothing had built that. The mutation proves both existing second-turn arms stay green without it.
- 2026-08-25: T-4.16-03's two separate defects fixed, the chip label and the `ask` copy, the second a product-owner decision because the trust-pills card has no `ask` state. T-4.16-09 landed as a scripted arm after a real dispatch proved unreachable from the browser suite. Defect 2 measured to salience rather than position, and left for the design card.
- 2026-08-25: T-4.16-05 routing and T-4.16-04 integrations both landed, each mutation-proven. Three more assertions-that-cannot-fail were found and fixed inside the integrations guard itself.
- 2026-08-25: Defect 2 resolved to DISCOVERABILITY by the product owner, not a dispatch failure. Defect 4's gap list captured from the deployed demo against the answer card; four of its six rows trace to T-4.16-01's already-fixed missing tool events, so it must be re-measured after that deploys.
- 2026-08-25: T-4.16-02 investigated. Defect 2 does not reproduce on any path in any environment. Three other defects found while trying: a vacuous landed-signal the lead wrote, the guest path never having been exercisable in the browser suite, and two ungated live specs this phase had just introduced. Blocked on the product owner rather than closed.
- 2026-08-25: Defect 7 reported by the product owner and closed as T-4.16-10. Root cause measured in Chromium, not reasoned about; guard added as a bounding-box arm and mutation-run red before commit. While running the full browser suite for it, one PRE-EXISTING failure was found and proven pre-existing by re-running it at the branch point.
- 2026-08-25: T-4.16-01 and T-4.16-07 landed. Gate 5 of 5 green, mutation harness 7 of 7, suite 3942 passed with zero failed, frontend 211, typecheck and production build clean, ruff clean, drift 0 stale 0 structural. Five `test_graph.py` `act_state` literals gained the required `seq` key: they were incomplete `GraphState`s that only worked while `act_node` did not read it, and the fixtures were corrected rather than softening the code to `state.get("seq", 0)`, which would let a mid-run seq collision pass silently. No assertion was weakened.
- 2026-08-25: Backend premise gate written and watched failing, 5 arms, 5 red. A5's failure message printed the production event list verbatim, `guard cost think cost plan cost token citation trust_signal trust_signal cost done`, which is the deployed trace with no tool frame in it. TWO GAPS IN THE GATE RECORDED IN ITS OWN DOCSTRING rather than left to a reviewer: A3 stops at its presence check and never reaches the timing comparison that is its whole reason for existing, and A4's populate-check is currently what fails, so it proves nothing A1 does not. Both are closed by T-4.16-07's mutation, not by reading. One defect found in the gate's own fixture while watching it fail: the daily-cap stubs were written `async` against two sync call sites, so every run logged `coroutine ... was never awaited` and the stub silently did not run.
- 2026-08-25: Corrected T-4.16-01 before writing any code. Events flush at node return, so emitting inside `act_node`'s loop would have delivered every tool event in one burst at 12.3 seconds and changed nothing visible. The node boundary is the constraint, not the missing emit.
