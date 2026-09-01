# UI feedback

Product owner feedback on the user experience, raised 2026-08-31, plus what was verified against the live production deployment rather than taken on trust.

The short version: the backend works and the product is still not usable. Every complaint below was checked, and one of them turned out to have a different root cause than the words suggested. That one is the most important thing in this file.

Last updated: 2026-09-01.

## Table of contents

- [The headline finding](#the-headline-finding)
- [Seen in a real browser, not inferred](#seen-in-a-real-browser-not-inferred)
- [The evidence, measured](#the-evidence-measured)
- [Complaint 1: the UI is not as responsive as the design](#complaint-1-the-ui-is-not-as-responsive-as-the-design)
- [Complaint 2: the answer flow feels fragmented](#complaint-2-the-answer-flow-feels-fragmented)
- [Complaint 3: follow-up questions do not continue the thread](#complaint-3-follow-up-questions-do-not-continue-the-thread)
- [Complaint 4: the integrations page is a placeholder](#complaint-4-the-integrations-page-is-a-placeholder)
- [Complaint 5: the answer just stops, and never offers the next step](#complaint-5-the-answer-just-stops-and-never-offers-the-next-step)
- [What this means for sequencing](#what-this-means-for-sequencing)
- [Why the two-day reference build felt better](#why-the-two-day-reference-build-felt-better)
- [Test against develop, not production](#test-against-develop-not-production)
- [Manual test workflows, for the product owner to run](#manual-test-workflows-for-the-product-owner-to-run)
- [End-to-end workflows for browser-driven testing](#end-to-end-workflows-for-browser-driven-testing)
- [Working practice: two sessions, one checkout](#working-practice-two-sessions-one-checkout)
- [What has not been checked](#what-has-not-been-checked)

## The headline finding

The stated complaint was "the UI looks good but no answers are getting produced". That is not quite what is happening, and the difference changes what needs fixing.

Answers ARE produced. The agent loop runs end to end, calls two tools, grounds three claims and cites all three. What comes back is unreadable:

> MedGen:C2676676 [1], MedGen:C3280442 [2], and MedGen:C4554406 [3].

A person asked which diseases are associated with BRCA1 and got three opaque identifiers. No disease names. From a user's seat that is indistinguishable from no answer, which is why the complaint was phrased the way it was.

So the defect is NOT in the UI, and it is not that the loop fails. It is that the answer is technically correct, fully cited, trust-gated, and useless.

### The likely root cause, and it is a known pattern here

`tools/schema_slice.py` tells the Cypher-generating model which vertex labels, edge predicates and CURIE prefixes exist. It does not appear to tell it which node PROPERTIES may be selected. The word "properties" appears once in that file, in a comment about something else.

If the model is never told a Disease node carries a human-readable name, it cannot select one, so it selects the identifier it does know about. The answer is then correct about the only field it was able to ask for.

This is the same shape as the build phase 2.1 lesson already recorded in `.claude/rules/attack-the-constraint.md`: the schema slice handed to the model contained no Disease label at all, and three review rounds hardened the wrong component before anyone printed the prompt. The rule's own words apply here without modification: check whether the correct answer is even expressible from what the model was given, before debugging what it produced.

CONFIRMED AND CORRECTED, 2026-08-31, by querying the live graph. The hypothesis was half right, and the half it got wrong is the important half.

A `name` property DOES exist on Disease nodes. It does not hold a disease name. Sampled across 25 Disease nodes, `name` takes exactly three distinct values:

```
MedGen:C0000737   name='SNOMEDCT_US'
MedGen:C0000744   name='MedGen'
MedGen:C0000771   name='MeSH'
```

Three values across twenty-five nodes. The Disease `name` column was populated with the SOURCE VOCABULARY the record came from, not the label of the disease.

The same probe against Gene nodes shows the field working correctly there, 23 distinct values across 23 nodes:

```
NCBIGene:213      name='albumin'
NCBIGene:207      name='AKT serine/threonine kinase 1'
NCBIGene:226      name='aldolase, fructose-bisphosphate A'
```

So this is not a general graph problem and not a schema-slice problem. It is specific to the Disease label, and it means the readable answer was NEVER EXPRESSIBLE from Layer 1. Exposing `name` to the Cypher generator would have changed the answer from four CURIEs to the word "SNOMEDCT_US" four times, which is worse.

### Two ways to fix it, and only one of them lives in this repository

| Path | Where | Trade-off |
|---|---|---|
| Re-ingest Disease nodes with the real MedGen label in `name` | Systems 1 and 2, the data-engineering repository. NOT this one | The correct fix. Fixes every query at once and costs nothing at runtime. Needs a re-ingest and is not on this repository's schedule |
| Resolve MedGen CURIEs to names at query time through Layer 2 | This repository. `ncbi_efetch` already reaches MedGen | Available now, no re-ingest. Costs a live API call per answer and adds latency to a path already taking 12 to 14 seconds |

The second path is worth noting carefully: `ncbi_efetch` ALREADY RAN in the observed query, as the second of the two tools. So the machinery to turn `MedGen:C0346153` into a disease name is already in the loop and is already being called. What it is not doing is using that call to label the entities in the answer.

That makes this materially cheaper than it first looked, and it is the single highest-value thing on this whole list.

### The second defect in the same answer

The answer ended with this, shown to the user:

> Note: this answer reports 3 of the 5 findings prepared for it, and the 2 not reported are absent from the citations as well as from the text above

That is internal accounting. It tells a researcher nothing they can act on, and it undermines confidence in the three results that did survive. The run also came back with `trust_outcome: "ask"` and `risk_tier: "high"`, so the interface renders it as a hedged, half-trusted response rather than an answer.

## Seen in a real browser, not inferred

Playwright drove Chromium against live production on 2026-08-31 and captured the answer screen. Screenshot: `docs/build/design/evidence/2026-08-31_live_answer_brca1.png`.

The picture settles the argument more cleanly than any API probing did. THE INTERFACE IS NOT THE PROBLEM.

What the page renders is competent. It has all of this, and it is laid out well:

- A clear question header with a "New search" control.
- A trust line carrying elapsed time, tool count and source count.
- The answer in a quoted block.
- Numbered citation chips under the answer.
- A collapsible sources disclosure.
- Trust pills.
- A follow-up field with three suggested questions.
- A feedback control.

It is a well-built page displaying this:

```
The knowledge graph associates the gene BRCA1 with four disease records:
MedGen:C0346153, MedGen:C2676676, MedGen:C3280442, and MedGen:C4554406.
```

Four identifiers. A researcher cannot use that sentence for anything. This is the whole problem in one screenshot: excellent chrome around content nobody can read.

Details the browser run added that the API run did not:

| Observed | Note |
|---|---|
| Header reads "Single source, not independently confirmed" | The trust line leads with a caveat before the answer |
| "12.3s, 2 tools, 5 sources from 2 layers" | Latency is shown honestly, which is good, and it is still 12 seconds |
| Pills read "Grounded, every claim cited" and "high risk claim" | Both true, and together they tell a user the answer is simultaneously trustworthy and dangerous |
| The findings-accounting note did NOT appear this run | It appeared in the API run earlier the same day. So it is intermittent, not constant, and reproducing it needs a specific path |
| Four diseases here, three in the earlier API run | Same question, different result count on two runs minutes apart. Worth understanding before anything else is tuned |
| Follow-up help text says "A follow-up runs a full search" | The interface is HONEST about the behaviour in complaint 3. It is documented, not broken. Whether it is the right behaviour is a product question |

The last row matters for how complaint 3 gets framed. The product is not failing to do something it claims. It is doing something it explains clearly, and that behaviour is not what you want.

## The evidence, measured

Run against the production deployment on 2026-08-31, not against a local build or a test fixture.

| Step | Result |
|---|---|
| `GET /health` | `{"status":"ok","app_env":"production"}` |
| Web app load | HTTP 200 in 0.148s |
| `POST /auth/guest` | HTTP 201, guest token, allowance 5 |
| `POST /v1/query` | HTTP 202 in 0.168s |
| Event stream | 17 events: guard, think, plan, 2 tool_start, 2 tool_result, 2 token, 3 citation, 4 trust_signal, done |
| Tools that ran | `cypher_query` (Layer 1), then `ncbi_efetch` (Layer 2) |
| Elapsed | 14130ms |
| Reported cost | `0.0` |
| Trust outcome | `ask`, risk tier high |

Two things in that table deserve their own follow-up beyond the answer-quality problem:

- 14.1 seconds from question to done, with roughly 7 seconds between the first tool starting and the answer arriving. That is the latency the interface has to cover, and it is the direct cause of complaint 2.
- `total_cost_usd` reports `0.0` on a run that made two tool calls and several model calls. Either cost accounting is not wired to the guest path or it is reporting a placeholder. Worth checking before anyone trusts a spend figure.

## Complaint 1: the UI is not as responsive as the design

Design source: `docs/build/design/`, in particular `design/design-system/prototype/app.html`.

Not yet diagnosed. This one I have not verified, because judging responsiveness against the approved design needs a browser and a side-by-side comparison, not a curl. It should be checked by opening the prototype and the live app next to each other at the same viewport widths.

What is worth knowing before that comparison: build phases 4.8 and 4.9 delivered the visual design and a nine-gap fidelity pass, so the gap being described now is either a regression since then or something the fidelity pass did not cover. Establish which before opening work, because those are different jobs.

## Complaint 2: the answer flow feels fragmented

Confirmed, and the measurement above explains it. There are 14 seconds to cover and the interface currently gives the user very little during them.

The pieces exist. `tool_start` and `tool_result` events fire at dispatch, which build phase 4.16 fixed specifically so tool chips could render while the Act step is still working.

What is missing is a continuous sense of progress. Any one of these would do:

- A spinner that runs for the whole wait.
- A live status line naming the step underway.
- A step indicator that visibly moves.

The sequence a user actually experiences today:

- Question submitted, then a gap.
- Some chips appear.
- Another gap of several seconds.
- Two token events arrive almost simultaneously, so the answer does not stream in, it appears at once.

That last point matters and is easy to miss. Only two `token` events were emitted 47 microseconds apart. The answer is not being streamed word by word, it is being delivered whole in two chunks at the end. Any perception of "streaming" in the current UI is therefore cosmetic. If streaming is wanted, that is a Write-step change, not a frontend change.

## Complaint 3: follow-up questions do not continue the thread

Partly built, and the gap is real.

What exists already:

- Bounded session memory, shipped in build phase 4.5, keyed per session. It can shape the Think and Plan steps.
- The follow-up input field.
- A conversation thread that keeps earlier turns on screen, added in build phase 4.16.

CHECKED AND RULED OUT: my first hypothesis was that the frontend mints a new `session_id` per question, which would make session memory correct but blind. It does not. `App.tsx` holds `sessionId` in state and resets it exactly once, on sign-out, deliberately, so a new person at the same workstation does not inherit the previous account's conversation. The id is stable across follow-ups.

THE ACTUAL CAUSE is stated in the repository's own stub registry, `frontend/src/stubs/registry.ts`, which describes the follow-up surface in its own words:

> A follow-up field with suggested hints, which starts a fresh run.

So the follow-up field dispatches a NEW RUN rather than continuing the thread. Session memory exists behind it and shares the session id, but the interaction model is one-shot question, one-shot answer, repeated. That is why it feels like it forgets: structurally, each turn is a fresh start that happens to share a key.

Fixing this is more than wiring. It means deciding what a follow-up turn actually sends. The options:

- The prior question and answer as context.
- The resolved entities from the previous turn.
- The full thread.

That is a product decision before it is an engineering one, and it is the single change that would most move this from a search box to an assistant.

## Complaint 4: the integrations page is a placeholder

Confirmed, and the underlying problem is worse than the page.

The page does name KGX, MCP, GraphQL, REST and SSE. What it does not do is let anyone use them, and in one case the capability does not exist over the web at all:

| Surface | Page says | Reality |
|---|---|---|
| KGX export | Described, with a request button | There is NO KGX HTTP endpoint. Export exists only as the `s3-kgx-export` command-line tool. `stubs/registry.ts` describes the button in its own words as "a request button that acknowledges and does nothing" |
| MCP | Named | Server exists and is outbound-only. The page gives no connection details a person could paste into a client |
| REST and SSE | Endpoint paths shown | Accurate, and the most useful thing on the page |
| GraphQL | Named twice | Registered accounts only, no guest path. The page does not say so |

### Owed: a proper comparison against the reference build

The product owner's instruction on 2026-08-31 was to look at how `reference/ncbi_ai_agents-ncbi-kg` set up integrations, on the grounds that it was perfect and everything just worked. That comparison is NOT done.

What is established so far is only its shape:

- A React frontend carrying `src/services` and `src/components/admin`.
- An `api` directory.
- A top-level `mcp_server.py`.
- A `KG` directory.
- Netlify and Railway deployment config committed in the repository.

The specific question to answer when it is done: what did that build put in front of a user that this one does not, for each of KGX, MCP and the API. Do not answer it from the directory listing above, which is why this is recorded as owed rather than summarized here.

So the page is not lying, but it advertises a shelf of capabilities and hands the visitor nothing to pick up. For KGX specifically the honest options are to build the HTTP endpoint or to stop advertising a button that does nothing.

## Complaint 5: the answer just stops, and never offers the next step

Raised by the product owner, 2026-08-31: an answer should be able to end by offering where to go next, for example "would you like me to dive deeper into XYZ", so a discussion can actually finish rather than simply halting.

This is a DIFFERENT gap from complaint 3 and the two are easy to merge by mistake. Complaint 3 is that a follow-up the user types does not continue the thread. This one is that the system never proposes a follow-up at all. Fixing either leaves the other exactly as it is: a thread that continues properly still ends on a full stop, and a well-phrased offer that starts a fresh run is still amnesia.

### The field already exists, and nothing has ever written to it

Checked in the source rather than assumed, because the interesting part is that this is not a missing feature so much as a dead one.

| Layer | State |
|---|---|
| Event contract | `ThinkPayload.clarifying_question`, a `str` capped at 500 characters, `contracts/events.py:128` |
| Backend | Set in exactly ONE place in `src/`, `core/graph.py:1496`, and that place sets it to `None`. Unconditionally, on every query, since it was added |
| Frontend type | Declared, `frontend/src/lib/events.ts:76`, as `string` or `null` |
| Frontend renderer | NONE. Every other reference in `frontend/src/` is a test fixture passing `null` |

So the field is wired end to end as a TYPE and is dead as a BEHAVIOUR. This is the same shape build phase 4.5 recorded for session memory, in that phase's own words: write without read and read without write are the same bug seen from two sides, and both look correct in isolation. Here it is neither written nor read, which is why no test has ever failed over it.

There is a second, adjacent piece of machinery that is genuinely live: Section 22.1's ambiguous-query path emits `trust_signal = ask` with a clarifying question as the answer text. That path works. It is not this. It fires BEFORE any tool runs, to disambiguate an entity the system could not resolve, and it replaces the answer. What is being asked for here fires AFTER a complete, cited answer and adds to it.

### What has to be decided before this is buildable

Naming this as a product decision rather than a ticket, because getting it wrong makes the product worse rather than merely unfinished. An offer to go deeper is a claim that there IS something deeper, and this system's whole trust position rests on not asserting things it cannot cite.

- Where the suggestion comes from. Generated by the Synth tier as free text is the easy path and the dangerous one: it can invent a follow-up about data the graph does not hold, which is a confident wrong answer wearing a question mark. Deriving it from what retrieval ACTUALLY returned and had to leave out, the truncation disclosures and omitted findings this system already computes, is harder and is the honest version.
- Whether it is one offer or several. One is a conversation. A list of three is a menu, and a menu is what the existing suggested-hints row already is.
- What happens when it is accepted. This lands straight on complaint 3: if accepting an offer starts a fresh run, the offer makes the amnesia more obvious rather than less, because the system will have proposed the topic and then forgotten proposing it. THE ORDERING FOLLOWS FROM THAT: complaint 3 is a prerequisite for this, not a sibling of it.
- Whether an answer may decline to offer anything. It must be able to. A refusal, an empty retrieval, or a single-fact lookup has no honest next step, and a system that always asks something will pad.

### Sequencing

Behind build phases 6.0 and 6.1 with the rest of the UI work, per the decision below, and behind complaint 3 within that work for the reason just given.

## What this means for sequencing

The question raised was whether UI work comes before or after build phases 6.0 and 6.1.

Recommendation: do the answer-quality fix FIRST, before either, and it is not really UI work.

The reasoning is the repository's own `attack-the-constraint` rule. The bottleneck right now is not throughput, hardening, or visual fidelity. It is that a correct, cited, fully-instrumented answer is unreadable to the person who asked. Every other item on this list is worth less until that is fixed:

- Rate limiting (6.0) protects a system nobody wants to use twice.
- Release hardening (6.1) hardens the same.
- Making the UI match the design more closely renders unreadable output more beautifully.
- User feedback gathered now would all be the same feedback: the answers are not answers.

### DECIDED: 6.0 and 6.1 go first. Product owner, 2026-08-31

This overrides the recommendation below, which argued for fixing answer readability first. The recommendation is left in place rather than deleted, so the reasoning on both sides survives.

The product owner's reasoning, and it is stronger than mine on the thing I was not weighing:

- Fixing UI issues piecemeal means some are fixed and some remain, and every partial pass requires re-testing the whole surface. That is worse than one coherent pass.
- The feedback is not finished being collected. This document is going to grow as the app gets used.
- This is a show piece. It needs to be right as a whole, not right in patches.

So the plan is: build 6.0 and 6.1, collect UI feedback into this file continuously while doing it, then fix the UI issues in ONE pass against a complete list.

What that means for whoever picks this up:

- Do NOT start fixing items from this file yet. It is still being written.
- Add to it freely. Every new observation makes the eventual single pass better.
- The answer-readability finding is the exception worth watching: if 6.0 and 6.1 take long enough that the product is shown to anyone in the meantime, revisit whether it should jump the queue, because it is the one item that makes every demo fail.

### The original recommendation, kept for its reasoning

Suggested order, with the reasoning attached to each:

1. Answer readability. Establish whether disease names are in the graph, fix the schema slice and the Write step so answers name things rather than identify them, and drop the internal findings-accounting note from user-facing text. Backend work, small, and it is the difference between a demo and a product.
2. Session continuity, complaint 3. Not a one-line fix: the follow-up field starts a fresh run by design, so this needs a product decision about what a follow-up turn carries forward before any code is written.
3. Progress feedback during the 14-second wait, complaint 2. Cheap, high perceived value, and it does not depend on anything above.
4. Integrations honesty, complaint 4. Either build the KGX endpoint or remove the button. Removing is a one-hour job and stops the page lying by implication.
5. Design fidelity, complaint 1. After a browser comparison establishes what actually regressed.
6. Then 6.0 and 6.1.

That ordering is a recommendation, not a decision. The one part I would argue for hardest is item 1 going before everything, including before gathering user feedback, because feedback collected against unreadable answers will only ever produce one finding.

## Why the two-day reference build felt better

Reference: `reference/ncbi_ai_agents-ncbi-kg`.

This deserves an honest answer rather than a defensive one, and I have not yet done the comparison properly, so what follows is a hypothesis to test rather than a conclusion.

The likely difference is not effort or code quality. The earlier build probably returned whatever the model said, directly, in plain language.

This build interposes a deterministic grounding layer between the model and the user:

- Findings are built in code rather than by the model.
- Every claim must match a retrieved source by exact or substring comparison.
- Unmatched claims are STRIPPED.
- What survives is what you read.

That layer is why this system cannot invent a citation. It is also, on the evidence above, why the answer reads as three identifiers and a disclaimer: the only claims that could be grounded were the CURIEs, so the CURIEs are what survived.

The moat and the defect are the same mechanism. The fix is not to remove the grounding layer, it is to give it human-readable fields to ground against. That is what makes item 1 above a schema and prompt problem rather than an architectural retreat.

## Test against develop, not production

Correction to how the evidence in this file was gathered. Everything above was run against PRODUCTION, and it should have been run against DEVELOP. Production moves only on a deliberate release, so it lags whatever is being worked on, and testing there measures an older build than the one anyone is fixing.

The two deployments, from `README.md`:

| Deployment | Web | API |
|---|---|---|
| Develop | `https://search-agent-web-develop-2aeb.up.railway.app` | `https://search-agent-api-develop-43b3.up.railway.app` |
| Production | `https://search-agent-web-production.up.railway.app` | `https://search-agent-api-production.up.railway.app` |

They are fully separate: different Railway projects, different databases, different signing keys. Ask either API's `/health` and it names itself in an `app_env` field.

From here on, UI verification runs against DEVELOP. Production gets checked only when confirming a release actually shipped what it claimed. The live diagnostic spec at `frontend/e2e/live-answer-screenshot.spec.ts` currently hardcodes the production URL and should take the target from an environment variable instead.

## Manual test workflows, for the product owner to run

Added 2026-09-01, by product-owner decision. THE ASSISTANT DOES NOT DRIVE THE BROWSER unless asked. It fixes the frontend and the backend, then writes the workflow here, and the product owner runs it and records what they saw.

Where to test: DEVELOP, `https://search-agent-web-develop-2aeb.up.railway.app`. Production is checked only when confirming a release shipped what it claimed.

How to read the tables: type what is in the "type this" column, watch for what is in "what to watch", and write what you actually saw in "what I saw". A blank verdict means not yet run, which is different from a passing one.

### Ready to test now

These are on the build phase 6.2 branch and are NOT on develop yet. They become testable the moment that branch merges. Nothing below has been seen by a person yet.

| # | Workflow | Type this | What to watch | What I saw |
|---|---|---|---|---|
| W1 | Disease names in an answer | `Which diseases are associated with BRCA1?` | The answer names diseases in words, for example "breast-ovarian cancer, familial, susceptibility to, 1". It should NOT read `MedGen:C2676676`. Each name should have a numbered citation that opens a real MedGen page | |
| W2 | The wait feels alive | The same question, then watch without touching anything | A number next to the question counting up every second, and the current step's dot pulsing. There should be no stretch longer than about two seconds where nothing on screen moves | |
| W3 | No internal bookkeeping | The same question | If the answer says something was left out, it should say it in your terms, for example "3 further disease records were found for this question and are not described above". It should NOT say "4 of the 5 findings prepared for it" | |
| W4 | A second gene, to see it is not a one-off | `Which diseases are associated with TP53?` | Same three things as W1 to W3. TP53 has more associated diseases, so this is also the case where something is most likely to be left out | |

### Also ready to test, built after the decisions of 2026-09-01

UPDATED 2026-09-01: all five are now BUILT and sit on the phase branch alongside W1 to W4. They become testable at the same moment, when that branch merges to develop. Nothing here has been seen by a person yet.

| # | Workflow | Type this | What to watch | What I saw |
|---|---|---|---|---|
| W5 | A follow-up continues the thread (BUILT) | Ask `Which diseases are associated with BRCA1?`, wait for the answer, then in the follow-up box ask `What variants cause it?` | The second answer should know that "it" means the diseases just discussed, without you naming them again. Every claim in it should still carry its own citation | |
| W6 | The thread survives more than one turn (BUILT) | After W5, ask a third question referring further back, for example `And which of those has the most evidence?` | It should still be following the conversation, not just the previous turn | |
| W7 | The answer offers a next step (BUILT) | Any question that returns several results | The answer may end by offering somewhere to go next. That offer must be about something actually found and not described, never an invented topic. Accepting it should CONTINUE the thread, not start over | |
| W8 | An answer with nothing to offer stays quiet (BUILT) | Ask something with no answer, for example `Which diseases are associated with the gene ZZZZZZ999?` | It should refuse cleanly and offer NO next step. A system that always asks something is padding | |
| W9 | No broken sentences (BUILT) | Any question where part of the answer is left out, W4 is the likeliest | Sentences should be whole. No unclosed brackets, no sentence missing its verb. A sentence that lost a piece should be dropped entirely rather than shown broken | |

### Known, not yet fixed, so not worth reporting as new

Recording these so a test run does not spend time on things already on the list:

- The answer can take more than 25 seconds on develop, longer than the 12 to 14 seconds measured on 2026-08-31. The counter in W2 makes the wait visible and makes it no shorter.
- The app scrolls sideways by about 8 pixels on a 390px-wide phone screen. 768px and 1440px are clean.
- The answer arrives in one or two chunks at the end rather than streaming in word by word.
- The reported cost of a run is `0.0`, which is not yet trusted either way.

### The eight browser journeys, and what each would cost to run

Built and gated behind `RUN_LIVE_JOURNEYS=1`, available the moment they are asked for. Three have been run; the rest are waiting on an instruction, per the decision above.

| # | Journey | Cost to run | State |
|---|---|---|---|
| 1 | First visit to first answer | 1 guest answer | Built, not run |
| 2 | The wait, one frame a second | 1 guest answer | Run 2026-09-01 |
| 3 | Follow-up continuity | 2 guest answers | Built, not run. The evidence behind W5 |
| 4 | Guest allowance exhaustion | 6 answers, a whole guest allowance | Built, not run |
| 5 | Every integrations affordance | None | Run 2026-09-01 |
| 6 | Refusal and error paths | Up to 2 answers | Built, not run. The evidence behind W8 |
| 7 | Narrow viewports | None | Run 2026-09-01 |
| 8 | Sign up, reload, sign in | None, creates an account | Built, not run |

### Correction to complaint 4, from journey 5

The integrations page on DEVELOP has no buttons at all. It is five cards carrying real endpoint paths, a pasteable MCP config and real CLI commands, and the KGX card states its own limitation in the product's own words: "A batch command rather than a live endpoint, and not a whole-graph snapshot". The GraphQL card says "Registered accounts only".

That does not match complaint 4 below, which describes "a request button that acknowledges and does nothing". The likely reason is the one this document itself raises: complaint 4's evidence was gathered against PRODUCTION, which lags develop by a release. NOT YET ESTABLISHED, and deliberately not assumed: whether production still shows the dead button.

## End-to-end workflows for browser-driven testing

Browser control is available and proven, not theoretical:

- Playwright 1.62 with Chromium is installed.
- `frontend/e2e/` already holds live diagnostic specs.
- A run against the deployed app on 2026-08-31 drove a real query and captured the answer screen in 29 seconds.

What is missing is a set of workflows worth running. The specs that exist test narrow assertions. What this file needs is journeys a real person takes, each ending in a screenshot that a human or an agent can look at and judge.

Build these as `frontend/e2e/journeys/`, gated behind an environment variable like the existing diagnostics, pointed at DEVELOP by default.

### The journeys worth having

| # | Journey | What it must capture | Which complaint it covers |
|---|---|---|---|
| 1 | First visit to first answer | Landing, disclaimer, question typed, every intermediate state during the wait, final answer | 1, 2 |
| 2 | The wait itself | A screenshot every second from submit to answer, so the 12 to 14 second gap is visible as a filmstrip rather than described | 2 |
| 3 | Follow-up continuity | Ask, then ask a dependent follow-up such as "what variants cause it", and capture whether the second answer knows what "it" refers to | 3 |
| 4 | Guest allowance exhaustion | Ask six times as a guest, capture what the fifth and sixth look like | Untested entirely |
| 5 | Every integrations affordance | Click each control on the integrations page, capture what happens, including the KGX button that does nothing | 4 |
| 6 | Refusal and error paths | Ask something unanswerable, ask something the guardrail rejects, capture both | Untested entirely |
| 7 | Narrow viewports | Journey 1 repeated at 390px, 768px and 1440px | 1 |
| 8 | Sign up, sign out, sign in | Including whether history survives, which build phase 4.13 merged with known gaps | Untested entirely |

### What makes them useful rather than decorative

- Each ends in a named screenshot committed under `docs/build/design/evidence/`, dated, so a change can be compared against the last run rather than against memory.
- Each captures INTERMEDIATE states, not just the end. The complaint in this file is about the experience during the wait, and a final screenshot cannot show it.
- Each runs against develop by default and takes its target from an environment variable.
- None of them assert. They CAPTURE. A journey that fails a strict assertion stops and tells you nothing about the other seven steps, and the point here is to see the whole flow.

Journey 2 is the one to build first. The fragmentation complaint is currently described in prose, and a filmstrip of the twelve-second wait would turn it into something anyone can look at and immediately agree or disagree with.

## Working practice: two sessions, one checkout

Recorded because it already caused a real mistake, and it will keep happening while UI work and build-phase work run at the same time.

WHAT HAPPENED, 2026-08-31. A second session opened build phase 6.0 and created `phase/6.0-rate-limit-concurrency` in the SAME working directory this session was using. Git branches are per-checkout, so the branch switched under this session mid-task. The consequences, in order:

- A UI documentation commit intended for `develop` landed on the 6.0 phase branch instead.
- Pushing that to `develop` carried the other session's phase-opening commit `42847f5` with it, so a tracker commit reached `develop` without passing through its own pull request.
- Nothing broke. Both commits are documentation, and git will not duplicate `42847f5` when 6.0 merges. But neither was the pushing session's to push.

WHY IT MATTERS BEYOND THIS INSTANCE: the failure is silent.

- Neither session is told the branch moved.
- The first sign is a `git status` showing a branch nobody in this conversation checked out.
- The commit still succeeds and the push still succeeds, so the wrong thing lands without an error.

THE FIX, when the UI pass starts: give the UI work its own git worktree, the way the debugging guide got one. A worktree is a second checkout with its own branch and its own working directory, so two sessions cannot move each other's branch. The command is one line:

```bash
git worktree add ../agentic-search-ui-ui develop
```

It was deliberately NOT done today, by product-owner decision, because today's work was recording feedback rather than changing code. Do it before the first UI fix lands, not after.

THE INTERIM RULE while both streams share one checkout: check `git rev-parse --abbrev-ref HEAD` immediately before every commit, and never assume the branch is the one you were on when you started.

## What has not been checked

Stated so this document is not read as more complete than it is:

- Complaint 1 entirely. No browser comparison against the design prototype was run.
- Why `total_cost_usd` reported `0.0`.
- Whether the two-token delivery is the Write step's design or a defect.
- Anything about the reference build beyond its directory listing.
