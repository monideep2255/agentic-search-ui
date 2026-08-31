# UI feedback

Product owner feedback on the user experience, raised 2026-08-31, plus what was verified against the live production deployment rather than taken on trust.

The short version: the backend works and the product is still not usable. Every complaint below was checked, and one of them turned out to have a different root cause than the words suggested. That one is the most important thing in this file.

Last updated: 2026-08-31.

## Table of contents

- [The headline finding](#the-headline-finding)
- [The evidence, measured](#the-evidence-measured)
- [Complaint 1: the UI is not as responsive as the design](#complaint-1-the-ui-is-not-as-responsive-as-the-design)
- [Complaint 2: the answer flow feels fragmented](#complaint-2-the-answer-flow-feels-fragmented)
- [Complaint 3: follow-up questions do not continue the thread](#complaint-3-follow-up-questions-do-not-continue-the-thread)
- [Complaint 4: the integrations page is a placeholder](#complaint-4-the-integrations-page-is-a-placeholder)
- [What this means for sequencing](#what-this-means-for-sequencing)
- [Why the two-day reference build felt better](#why-the-two-day-reference-build-felt-better)
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

Confirm before building anything: run one Cypher query against a Disease node and look at its `properties` payload. If a name key is there, this is a schema-slice fix and a prompt fix, not a UI fix.

### The second defect in the same answer

The answer ended with this, shown to the user:

> Note: this answer reports 3 of the 5 findings prepared for it, and the 2 not reported are absent from the citations as well as from the text above

That is internal accounting. It tells a researcher nothing they can act on, and it undermines confidence in the three results that did survive. The run also came back with `trust_outcome: "ask"` and `risk_tier: "high"`, so the interface renders it as a hedged, half-trusted response rather than an answer.

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

## What this means for sequencing

The question raised was whether UI work comes before or after build phases 6.0 and 6.1.

Recommendation: do the answer-quality fix FIRST, before either, and it is not really UI work.

The reasoning is the repository's own `attack-the-constraint` rule. The bottleneck right now is not throughput, hardening, or visual fidelity. It is that a correct, cited, fully-instrumented answer is unreadable to the person who asked. Every other item on this list is worth less until that is fixed:

- Rate limiting (6.0) protects a system nobody wants to use twice.
- Release hardening (6.1) hardens the same.
- Making the UI match the design more closely renders unreadable output more beautifully.
- User feedback gathered now would all be the same feedback: the answers are not answers.

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

## What has not been checked

Stated so this document is not read as more complete than it is:

- Complaint 1 entirely. No browser comparison against the design prototype was run.
- Whether Disease nodes actually carry a name property. The root-cause hypothesis stands or falls on this and it needs one live Cypher query.
- Why `total_cost_usd` reported `0.0`.
- Whether the two-token delivery is the Write step's design or a defect.
- Anything about the reference build beyond its directory listing.
