# UI fix plan

The ordered work list for fixing the product after the first testing round on 2026-09-12. Each set says:

- What you will see
- What was noted
- And what to expect

So you can check progress without reading the code.

Since 2026-09-24 the work is kept in two files:

- This file: what is being built and what is next.
- `testing/UI_fixes_done.md`: every closed item, with its detail and history. That is an item built and live, approved or still awaiting your retest or decision, or one answered, superseded, run or accepted.

## Table of contents

- [Where every feature stands](#where-every-feature-stands)
- [Open items from earlier sets](#open-items-from-earlier-sets)
- [Where we stopped](#where-we-stopped)
- [Developer items](#developer-items)

## Where every feature stands

The high-level tracker, kept at the top so nobody has to read the sets to
answer "what is done and what is left". REORGANISED 2026-09-23 on the product
owner's instruction, into what needs them first, then what is moving, then
what is finished. Every status word here is copied from the item's own row
further down; the detail stays with the item. Since the 2026-09-24 split, the
row of an item that is built and live sits in `testing/UI_fixes_done.md`.

THIS DOCUMENT IS THE SOURCE OF TRUTH for what gets worked on. An item is
written here BEFORE it is built. Other folders are evidence referenced from
here, never a work queue of their own: `testing/User-feedback/` holds a second
tester's screenshots and is referenced by set 12.

REORGANISED AGAIN the same evening, on the product owner's instruction, into
their three sections:

1. Features being built right now, in priority order
2. Features to do, in priority order
3. Done

### 1. Being built right now, in priority order

Order: 11.11 is the one item still being built; 12.9 and 12.3 went live on
2026-09-24 and moved to your retests in section 2.

| Priority | Feature, in plain words | Item | Where it stands |
|---|---|---|---|
| 1 | Answers modelled on the reference prototype's depth, formatting and structure | 11.11 | In progress: the detail agent is modelling answers on it. The answer-writing model is unchanged; switching models is a separate decision |

### 2. To do, in priority order

Your retests come first, since they are your next action. The rest follow
"Next, in order" in "Where we stopped": 12.14 belongs to its item 1, which
names the Marfan phenotype question; then its items 2 to 7. Rows that list
does not rank keep the order the tracker already listed them in.

| Priority | Feature, in plain words | Item | Waiting on | Where it stands, what it affects, or where the steps are |
|---|---|---|---|---|
| 1 | The seven questions your skip manager asked, all of which now answer | 12.1, 12.2, 12.4, 12.7 | Your retest | `testing/Shipped_2026-09-23.md`, retest items 8 to 11 |
| 2 | The overnight batch: saved answers, MeSH terms, the record count, the MCP address | 10.2, 11.30 and four others | Your retest | `testing/Shipped_2026-09-23.md`, retest items 1 to 7 |
| 3 | The night of 2026-09-22: the two lost searches, the coordinate range, the accessions, the isolate set | various | Your retest | `testing/Shipped_2026-09-22.md`, retest items 7 to 22 |
| 4 | Four one-look checks, under a minute each | 11.14, 11.36, 9.12, 8.4 | Your retest | their rows in `testing/UI_fixes_done.md` |
| 5 | The answer answers the question instead of listing what was found | 12.10 | Your retest | `testing/Shipped_2026-09-23.md`, retest item 14. LIVE on develop at `5d53f78` 2026-09-23, awaiting your retest. A second, cheap model checks each reworded sentence against the exact record words it quotes; code first checks the quote is in the record character for character, the numbers, the negation, and that the sentence does not open on a yes or no verdict. Measured live: every plain-language answer of the seven answered in sentences; two of six guarded reruns fell back to a list, one on a failed model call, which is the check failing closed |
| 6 | The sources chip and the trust line agree with each other | 12.11 | Your retest | `testing/Shipped_2026-09-23.md`, retest item 12. LIVE on develop at `6f8902e` 2026-09-23, awaiting your retest. It now counts distinct pages, the same key the source list merges on. A regression from 12.8 the same day: the line counts citations and the list counts distinct pages |
| 7 | Broken sentences and repeated records in the answer | 12.12 | Your retest | `testing/Shipped_2026-09-23.md`, retest item 13. LIVE on develop at `6f8902e` 2026-09-23, awaiting your retest. An orphan fragment starting lowercase with a stray quote mark, a paragraph opening "Another is titled" with no first, and the same records shown up to three times |
| 8 | A search clicked in the history rail re-runs instead of showing its saved answer | 12.13 | Your retest | `testing/Shipped_2026-09-23.md`, retest item 15. LIVE on develop at `5d53f78` 2026-09-23, awaiting your retest. A search asked in this tab now opens its saved answer |
| 9 | Plain language and researcher differ on every question | 12.9 | Your retest | `testing/Shipped_2026-09-23.md`, retest item 16. LIVE on develop 2026-09-24. Measured live on all 12 full questions from both feedback folders: every one differs in its opening sentence and its list (a list in plain language, a table with identifiers in researcher), and both depths list the same records |
| 10 | A one-to-three-word question is asked back, such as `reflux disease` | 12.3 | Your retest | `testing/Shipped_2026-09-23.md`, retest item 17. LIVE on develop 2026-09-24, decided by a classifier model, not a word list. Measured live three times each: `reflux disease`, `GERD`, `BRCA1` and `Marfan` asked back 3 of 3 with choices written for the subject; `MeSH` 2 of 3; `papers on caffeine` searched |
| 11 | A question about phenotypic features names none | 12.14 | Nobody on it | RAISED 2026-09-23 from the fix-2 screenshots. NOT STARTED, nobody on it |
| 12 | A question asking for recent papers asks what recent means | 12.15 | Nobody on it | RAISED 2026-09-23 from the fix-2 screenshots. NOT STARTED, nobody on it |
| 13 | No hardcoded decisions: prompts, routing and the clarify decision stop relying on word lists and test-question examples | 12.16 | Part 3 not started | RAISED 2026-09-24 by the product owner. Parts 1, 2 and 4 LIVE 2026-09-24; part 3, the literature-request routing word list, not started. Audit in 12.16's row |
| 14 | A good question sometimes fails at the think step and shows a refusal | 12.17 | Nobody on it | RAISED 2026-09-24 from the live runs. NOT STARTED, nobody on it |
| 15 | Four golden test rows disagree with what the product does, row by row | the golden rows | Your decision | The test set only, nothing a user sees |
| 16 | Is twenty sources the right ceiling? | the ceiling, measured and unchanged | Your decision | Every answer hits it and then tells the reader it was cut short, which is a large part of why a good answer reads as a thin one |
| 17 | Tell the reader when the system wrote its own search rather than using a checked one | "Next, in order" item 5 | Nobody on it | Not started. The data exists: `CypherQueryOutput.template` is None exactly then. THE TRAP: the degradation is `ok` to `ok`, never `empty` |
| 18 | Hard and soft edges over a fuller graph, "connecting the dots" | 11.29 | Parked | A discussion that precedes a build. Its scoping document now exists and is measured: `testing/Developer/reports/2026-09-23_overnight/soft_edges_scoping.md` |
| 19 | A bounded trial of the probability model | 11.38 | Parked | Backlog only, nothing designed and nothing promised |
| 20 | Does the Plain language answer keep its small grey medical-advice line? | 9.11 | Your decision | One line under every plain-language answer |
| 21 | The trust-line wording | 9.9 | Your decision | One line under every answer |
| 22 | Judge answer quality once answering is reliable | 10.4 | Nobody on it | Not built. After the release, once 10.3's consistency run shows reliable answering |
| 23 | The load-dependent frontend tests | D4, under "Developer follow-through" | Nobody on it | Journey 7 FIXED 2026-09-23. The load-dependent suite is diagnosed and was still being worked at the close of that session |
| 24 | Internal MCP servers around the Layer 2 and Layer 3 calls | 11.32 | Parked | A discussion that precedes a build under `/bossman-mode`, reclassified 2026-09-22 |
| 25 | The explanation half of 11.31 | 11.31 | Parked | Parked. You approved the current state as is on 2026-09-21 |
| 26 | The byte ceiling at 50,000 | see its row | Parked | Parked |

What the Waiting on column means:

- Your decision: waiting on you: decisions. Each is written so the answer is:
  yes, no, or pick one. None blocks work in flight
- Nobody on it: still to build, nobody on it
- Your retest: waiting on you: retests. Each of these is built, live on
  develop, and needs your eyes before it counts as done. Nothing is blocked
  on them
- Parked: parked, and discussions that precede a build

### 3. Done

Everything built and live is in `testing/UI_fixes_done.md`, including its Done features at a glance table.

### Additional notes

- THE GRAPH HOLDS NO DISEASE NAMES AND NO MESH TERMS, measured graph-wide on
  2026-09-23. Every `Disease` vertex carries its source vocabulary in `name`
  and zero contain the word "syndrome". Known since build phase 2.1 as
  F-2.1-B07. Writing the graph is Systems 1 and 2 work in the other
  repository, so this is a hand-over rather than a task, and it BOUNDS what
  any answer-path work here can achieve.
- ITEM 11.21's PROMISE IS NOT BEING KEPT, measured for the first time on
  2026-09-23 and on wiring nobody changed. Six identical PubMed searches
  returned two distinct result sets, and the GERD questions moved 20 citations
  to 19 with one paper swapped. Separately, which path a question takes is a
  model call, so it is a sample: `reflux disease` resolved nothing on one run
  in six. Nobody had looked. Not yet its own item.
- OMIM is live WITH `filter_omim_titles`; the two ship together and neither is
  enabled or removed without the other
- The cutoff and the ordered next actions are in "Where we stopped"

## Open items from earlier sets

Items raised in Sets 10 to 12 that are still open. The rest of those sets is closed, recorded in `testing/UI_fixes_done.md`.

### 10.4 Judge answer quality once answering is reliable (R39)

Built: · Live: · Approved:

- Feature being tested: answer quality is judged only once the product answers consistently.
- What you noted: "Only once questions answer reliably, judge answer quality: the grader, or a domain expert reading the answers."
- What's expected: a quality pass with the grader or a domain expert, once R38's consistency run shows reliable answering. This is a developer check, not a hand test.

### Set 11, still open

Set 11's intro in `testing/UI_fixes_done.md` defines most of the status words these rows use.

| # | Your feedback | Status | Where it stands |
|---|---|---|---|
| 11.11 | Use your reference prototype for answer depth, formatting and structure; it writes with a different model family | In progress | The detail agent is modelling answers on it. The answer-writing model is unchanged: switching models is a separate decision |
| 11.29 | Think big about connecting the dots: if everything were in the knowledge graph, from PubMed literature to sequence, clinical and PubChem data, how do we find hard edges (direct relationships) and soft edges (indirect, through multi-hop)? Do we need RAG pipelines, vector embeddings, a hybrid knowledge-graph model? | Discussion, precursor to a build | Reclassified 2026-09-22 by the product owner: a discussion that precedes a build under `/bossman-mode`, not a question waiting on them. Raised 2026-09-20. Full detail: [11.29](#detail-1129) |
| 11.32 | Wrap the Layer 2 and Layer 3 API calls in internal MCP servers. "Why dont we wrap our layer 2 and layer 3, the api calls in internal mcps ... can understand from the API keys on how to setup things for each database. Maybe just add to the list for now" | Discussion, precursor to a build | Reclassified 2026-09-22 by the product owner: scoped in a discussion first, then built under `/bossman-mode`, still against the locked Section 6 tool list. Raised 2026-09-20. BACKLOG ONLY, nothing designed and nothing promised. Full detail: [11.32](#detail-1132) |
| 11.38 | Try the new model on OpenRouter that returns probabilities with its output, and decide where calibrated confidence belongs in the architecture: the guardrail, the choice of which resource to pull, and the cite-or-refuse gate | Discussion, precursor to a build | Raised 2026-09-22 by the product owner, who named the guardrail and the resource choice. BACKLOG ONLY, nothing designed and nothing promised. IDENTIFIED 2026-09-23 from the two links the product owner gave: it is `typesafe/jev-1.13` from TypeSafe, and it fits two of the three places they named and not the third. CORRECTION, because the assistant said the opposite hours earlier: it is NOT a harness config change, because it answers on its own `POST /api/alpha/decisions` endpoint rather than chat completions, so a trial needs a new client path. Full detail: [11.38](#detail-1138) |

#### Detail 11.29

The ask: Think big about connecting the dots: if everything were in the
knowledge graph, from PubMed literature to sequence, clinical and PubChem data,
how do we find hard edges (direct relationships) and soft edges (indirect,
through multi-hop)? Do we need RAG pipelines, vector embeddings, a hybrid
knowledge-graph model?

Status: Discussion, not started

Raised 2026-09-20. A DISCUSSION ITEM, deliberately not a build item, and it
needs its own session rather than a slot in the fix loop. Three things are worth
settling before it opens. FIRST, most of the premise is not this repository's to
decide: "everything is in the graph" is Systems 1 and 2, which live in a
separate repository, and `.claude/rules/file-protection.md` forbids this
repository writing into the graph at all, by direction of data flow.

System 3 can only read. SECOND, vector embeddings, RAG pipelines and
knowledge-graph federation sit on the v1 out-of-scope and fast-follow lists in
`.claude/rules/v1-scope-boundary.md`; external non-NCBI federation has NO named
trigger at all, so it stops and asks by rule. Discussing is free, building is
not. THIRD, the multi-hop half is already real and measured rather than
hypothetical: the live graph rejects edge alternation, `[:a|b|c]` fails with
SyntaxError, so the broad search traverses `participates_in` alone and GO
molecular activities and cellular components are not reached
(`2026-09-19_breadth_wiring/build.md`).

That is a soft-edge limitation sitting in the product today, and it costs one
graph call per edge to widen . THE PRODUCT OWNER'S OWN FRAMING, given 2026-09-20
when asked whether the product fails because the data is absent or because we
cannot find the path between things that are present: BOTH, and the headline
verdict is blunter than either: "the answers all look surface level and most
chatbots like ChatGPT, Claude, Gemini can answer better".

That is a judgement on the ANSWER PATH, not on presentation, and it is the bar
11.29 has to clear: not "does it cite" but "is it worth reading instead of a
general chatbot". Every presentation-side fix in Set 11 leaves that bar
untouched

#### Detail 11.32

The ask, in the product owner's own words: "Why dont we wrap our layer 2 and
layer 3, the api calls in internal mcps ... can understand from the API keys on
how to setup things for each database. Maybe just add to the list for now."

Status: Not started. Raised 2026-09-20, backlog only.

THE SOURCE MATERIAL THEY NAMED, both verified to exist on 2026-09-20: <!-- local-refs: allow -->

| What | Where |
|---|---|
| The connection maps and per-database deep dives | `reference/personal-os-work/NIH/NCBI Technical-development-workflow/Architecture-and-databases` <!-- local-refs: allow --> |
| The databases paper | the `NCBI-databases-paper-09-2025` folder inside it |
| Open this first | `NCBI_database_connection_map.md`, then `NCBI_databases_deep_dive.md` and `NCBI_enterprise_infrastructure_deep_dive.md` |

NOTHING IS DESIGNED AND NOTHING IS PROMISED. This crosses the tool-integration
boundary the locked technical specification's Section 6 defines, which names
seven tools and their transports, so under `.claude/rules/v1-scope-boundary.md`
it is scoped against that section and signed off before any work starts, never
the other way round.

Two questions to settle when it is scoped, neither decided here. Whether an
internal MCP server is a TRANSPORT SWAP underneath the existing seven tools,
which would leave every tool schema and call site unchanged the way build phase
4.11's HTTPS graph service did, or a RE-CUT of what the tools are, which is a
contract-version event under `system-design-patterns` pattern 10. And what it
buys over the direct calls the tools make today, since
`.claude/rules/supply-chain-security.md` treats every MCP server as an execution
surface running with the app's own credentials, so the answer has to be worth
that.

ANSWERED 2026-09-22, when the product owner asked directly whether wrapping
Layer 2 and Layer 3 in MCP would be faster and more reliable. The honest answer
splits their question in two, because the valuable half is not the MCP half.

On speed, no, and this is measured rather than argued. MCP is a protocol for one
process to offer tools to another. It does not change what NCBI returns or how
fast NCBI returns it, so wrapping our own calls in it adds a hop rather than
removing one. Item 11.4 measured where the wait actually is: the searches take
about a second, and the wait was the writing step. Item 11.8 then cut the median
answer from 26.5 to 19.7 seconds by working on that step, not on the transport.
Under `.claude/rules/attack-the-constraint.md`, the transport is not the
constraint, so optimising it buys nothing a person would feel.

On reliability, yes, and the product owner's instinct is right, but the thing
that buys it is the half of their sentence that does not mention MCP:

- "reverse engineer the NCBI API, see what data exists, and build functions around them".

- That is a measured, typed function surface
- and it removes a real class of wrong answer, namely the agent choosing an
  endpoint or a parameter that does not mean what it assumed.

It is also the exact method that closed G-035 on the night of 2026-09-22:

- the FTP tree was measured live first (521 MB, 584,433 rows, a 17.7 second full scan)
- a wire contract was pinned from those numbers
- and the shape went from never answering to 5 of 5.

That method is available today, one tool at a time, with no protocol change and
no new execution surface.

So the two halves separate cleanly, and only one of them is blocked:

- The typed, measured function surface per database: valuable, in scope as
  ordinary work on the existing seven tools, and provably effective here.
- The MCP envelope around it: a transport change that earns its keep only if
  these tools must be callable by agents outside this product. That is a
  distribution argument, not a speed or reliability one, and it stays a
  scoping discussion against Section 6 as this detail already says.

Worth stating plainly, because the naming invites the confusion:

- This product already HAS an MCP surface, at `/mcp`, and it points the other way.
- It exists so other agents can call this product.
- Item 11.32 would point MCP inward, at our own calls, which is the direction
  that adds the hop.

#### Detail 11.38

The ask, raised 2026-09-22: try the new model on OpenRouter that returns
probabilities with its output, because it could help the guardrail and the step
where the agent chooses which resource to pull.

Status: Not started. Backlog only, nothing designed and nothing promised.

WHAT IT IS, established 2026-09-23 from the two sources the product owner
supplied, `https://typesafe.ai/` and
`https://openrouter.ai/docs/guides/community/jev`. Read as vendor claims, which
is what they are; nothing below has been measured against this product's own
questions yet.

| Fact | Value |
|---|---|
| Model id | `typesafe/jev-1.13`, alias `~typesafe/jev-latest` |
| Maker | TypeSafe, who call it a "System One Model" |
| Endpoint | `POST https://openrouter.ai/api/alpha/decisions`, NOT chat completions |
| Question types | Choice: the selected option, a probability for every option, and a confidence. Bool: the probability of yes. Score: a probability-weighted position, a probability per level, and a confidence |
| Context | 32,000 tokens, state plus questions |
| Price | Input tokens billable, OUTPUT TOKENS FREE. Vendor claims $42 per billion input tokens |
| Vendor speed and cost claim | 193.6x faster and 244.6x cheaper on their own "System One" tasks: 0.114s and $0.000081 against 8.566s and $0.013880 |

THE LIMITATION THAT DECIDES WHERE IT CAN GO, in the vendor's own words:

- "Jev does not produce reasoning traces, explanations, or free-form text"
- and "It is not a drop-in replacement for a chat model."

That single sentence sorts the whole question. The product owner named three
places. Two of them are decisions, and Jev is built for exactly that shape. The
third is writing, and Jev cannot do it at all.

| Where | Shape today | Does Jev fit |
|---|---|---|
| Guardrail | A Guard-tier chat model classifies the input, and the answer is taken as certain | YES. This is a Choice with a confidence, which is what the step actually needs. A borderline question could be asked about rather than guessed at |
| Which resource to pull | Think and Plan pick from a fixed plan per question shape | YES, and it is the better of the two. The option set is closed and known, which is the condition a typed decision needs |
| Writing the answer | The Synth tier writes prose with inline citations | NO. It emits no free-form text. Not a candidate, at any price |

ON "ZERO HALLUCINATIONS", which is on the vendor's front page and should be read
carefully rather than quoted. The honest version of that claim is structural: a
decision constrained to a fixed option set cannot return an option outside the
set. That is real and it is worth something here, since this product's failures
include the model reading MODY as an organism (item 11.19). It is NOT a claim
that the chosen option is correct, and it must never be repeated to a user as
though it were.

WHY THE INSTINCT IS SOUND, independently of which model it turns out to be. The
loop currently makes three decisions that are taken as if certain and are not:

| Decision | Where | What is lost today |
|---|---|---|
| Is this input safe and on topic | Guardrail | A borderline question is admitted or refused outright, with no middle path such as asking the person what they meant |
| Which resource answers this | Think and Plan | A wrong pick is invisible: the answer comes back confidently sourced from the wrong place |
| Is this claim supported | Write, the cite-or-refuse gate | The gate is deterministic by design, which is correct; a calibrated confidence would inform what the answer SAYS about its own certainty, never whether the gate passes |

A calibrated confidence turns each of those from a silent guess into a number
that can be acted on, and the third one is the trust moat: a product that can
say "I am not sure" honestly is worth more than one that is fluent and wrong.

WHAT IS CHEAP AND WHAT IS NOT, since these are usually conflated. A CORRECTION
FIRST, recorded rather than quietly fixed: on the night of 2026-09-22 the
assistant said trying this model would be a config change under
`system-design-patterns` pattern 11, reversible in one edit. That was said
before the model was identified and it is WRONG for this model. Jev answers on
its own `/api/alpha/decisions` endpoint, not on chat completions, so
`resolve_model()` pointing a tier at it does nothing. A trial needs a new client
path in the harness, which is a small build rather than a config edit. The cost
estimate moves with it.

What remains cheap: the trial is still bounded and reversible, because the two
candidate call sites are decisions with closed option sets, and either can fall
back to today's path on any error. Output tokens being free makes a
side-by-side shadow run, where Jev decides in parallel and its answer is only
recorded rather than acted on, unusually affordable. That shadow run is the
right first step, because it produces this product's own calibration data
instead of a vendor benchmark.

What is NOT cheap: ACTING on a confidence number. A threshold anywhere in the
loop is a new control with its own failure modes, it must be calibrated against
this product's own questions, and under `.claude/rules/goal-contracts.md` a
threshold is a verify surface that must not be quietly lowered later to make
results look better.

TWO CONSTRAINTS THAT BIND ANY TRIAL, both from rules already in force:

- The cite-or-refuse gate stays DETERMINISTIC. `.claude/rules/production-standards.md`
  requires accept or reject by exact or substring match and says outright that
  fuzzy scoring may rank repair suggestions but never gates acceptance. So a
  confidence number may inform what an answer SAYS about its own certainty, and
  may never decide whether a citation passes. This is the place a probability
  model is most tempting and most dangerous.
- `/api/alpha/decisions` is an ALPHA endpoint, and the guardrail is on the path
  of every single query. A dependency that can change under us does not belong
  in front of everything until it has a fallback that is proven by execution
  rather than asserted.

### The product owner's direction on the model architecture, 2026-09-23

Added on the product owner's instruction, IN THEIR OWN WORDS, unedited. Quoted
rather than paraphrased because they asked that the wording not be changed.

> 1. Do we need to rethink the model use architecture, this ties into use of Jev from TypeSafe that we need to discuss.
>
> a) Jev becomes our classfier -> 1-3 words -> clarification question or move forward -> guardrails on the terms of relevancy or any place where a choice needs to be made.
> b) Here is where I do think converting our NCBI APIs and enrichment calls into functions MCP style do make sense. This way easy for Jev to help with the classifer
> c) We use Jev as a classifier where ever we are making those decisions
> d) Ideally we need opensource model but if frontier are needed then so be it.
>
> For instance, example, how models should be chosen, using frontier models as example, if equivalent opensource is available then amazing
>
> OpenAI/Claude example:
>
> Luna/Haiku/Sonnet for query classification, metadata cleanup, simple extraction, routing, or highvolume answer drafts.
> Sol/Opus 5.5 for multi-step retrieval planning, evidence synthesis, code generation, complex user
> questions, and tool-using workflows.
> Astra/Fable 5.1 for difficult scientific reasoning, ambiguous tasks, high-risk decisions, or final
> escalation when lower-cost models cannot reach a quality threshold.
>
> Then another thing you added was the model check.

Added later the same evening, again in the product owner's own words, unedited:

> What we need to be able to do in here. We are a agentic search:
> A conventional chatbot produces text in response to a question.
> An agent works through a sequence: 1.
> It interprets an objective.
> 2.
> It makes a plan.
> 3.
> It uses tools, such as a terminal, browser, spreadsheet, or internal system.
> 4.
> It checks intermediate results.
> 5.
> It adjusts when something fails.
> 6.
> It produces or applies a final result.
> For example, “modernize this legacy service” is not one answer.
> It may require locating dependencies, changing thousands of lines, running tests, investigating failures, revising code, documenting changes, and opening a review.
> The modelʼs value depends on completing the entire loop, not simply generating a plausible code snippet.

Where this connects to items already in this plan, stated by the assistant and
kept separate from the quote above:

- Point a), the 1-3 word clarification question: item 12.3, the product
  owner's open decision, with the fix-2 evidence (`BRCA1`, `MeSH`, `Marfan`
  and `recent papers on statins` all answered without asking).
- Point b), NCBI APIs and enrichment calls as MCP-style functions: item 11.32,
  parked as a discussion that precedes a build.
- THE MODEL CHECK: a decision point added on 2026-09-23 under items 12.9 and
  12.10, approved by the product owner the same evening. A guard-tier model
  decides whether a sentence the answer model REWORDED says anything more than
  the exact record words it quotes, after code has verified the quote is in
  the record character for character, the numbers are in the quote and the
  negation matches. It fails closed. It is exactly the kind of yes-or-no
  decision point point c) names, and a candidate for Jev's Bool question type
  once a shadow run has calibrated it. It amends the first constraint above
  (the cite-or-refuse gate stays deterministic) for that one bounded case: the
  rule text changes in pull request #101, and the reasoning is in DECISIONS.md
  on 2026-09-23.

ONE STANDING RULE TO HOLD AGAINST IT, `system-design-patterns` pattern 11 again:
on a recurring failure, iterate the harness first and swap the model second. So
a probability-emitting model is worth a bounded trial on its own merits, never
as the answer to a failure the harness has not been worked on yet.

### Set 12, still open

| # | The feedback | Status | Where it stands |
|---|---|---|---|
| 12.14 | `What phenotypic features are associated with Marfan syndrome?` names no phenotypic feature at either depth | RAISED 2026-09-23 in `testing/User-feedback/fix-2/`. NOT STARTED | Plain language answered "Found 1 disease record, 37 sequence variant records and 3 gene records for Marfan syndrome" and researcher "Found 1 disease record for Marfan syndrome: Marfan syndrome." The question asks for features and the answer substitutes an adjacent record type. This is the honest gap Shipped_2026-09-23 retest item 5 named: removing the dead template stopped a search that could never work, and nothing that CAN answer it runs instead. Evidence: `testing/Developer/reports/2026-09-23_fix2/findings.md` |
| 12.15 | A question asking for RECENT papers should ask what recent means: "recent paper on statin, should have asked a clarification of year range" | RAISED 2026-09-23 in `testing/User-feedback/fix-2/`. NOT STARTED, nobody on it | The product owner's comment is the screenshot's filename. `recent papers on statins` is four words and names what it wants, so 12.3's rule rightly does not ask it back; this is a different clarification, about a time window rather than a subject. Recorded so it is not lost; not being built. Evidence: `testing/Developer/reports/2026-09-23_fix2/findings.md` |
| 12.16 | No hardcoded decisions: "Please do not hardcode! Hopefully not that dumb" | RAISED 2026-09-24 by the product owner. Parts 1, 2 and 4 LIVE on develop 2026-09-24; part 3 NOT STARTED | AUDITED THE SAME NIGHT. No product code special-cases a test question by its text: every mention of the feedback questions in `src/` is a comment recording a measurement. WHAT IS HARDCODED, and what happens to each: (1) three model prompts use examples LIFTED FROM THE TEST QUESTIONS, the answer writer's "Caffeine improves endurance performance", the guardrail's "does coffee help exercise performance", and the sentence checker's "kidney" for "renal" and "mouth" for "oral cavity" from the GERD answer; that is teaching to the test, and they are replaced with neutral examples outside the test set, IN PROGRESS; (2) 12.3's clarify-or-proceed decided by word lists, REDESIGNED as a classifier decision, IN PROGRESS; (3) item 12.7's literature-request routing, decided by a word list (paper, publication, article and kin), to become a classifier decision, NOT STARTED; (4) the grounding gate's phrase lists added on 2026-09-23 for broken sentences and references ("however", "Another", "This ...", a "Yes," opener), which sit beside the exact checks the product owner asked to stay deterministic (quote in the record, numbers, negation), DECIDED 2026-09-24 BY THE PRODUCT OWNER: "Structure, not words", chosen over keeping them as exact backstops and over handing them to the model check. THE REPLACEMENTS, IN PROGRESS: a sentence copied from the middle of a record's sentence and starting in lowercase is that sentence's back half and is dropped, decided from where the words sit in the record, not from a list of connectives; any other lowercase start is capitalised; a reworded sentence that switches to a record the sentence before it did not cite must name something from its own record's title, decided from the records' own titles, not from a list of pointing words; the "Another ..." list is removed, since the restatement rule already drops a sentence that only repeats a row the list shows; the "Yes," or "No," opener stays, stated as the one exception because yes and no are the whole class of English answer words rather than a sample of phrasings. Measured before shipping. The distinction that governs all four: code VERIFIES exactly; a DECISION goes to a classifier. WHAT SHIPPED 2026-09-24: part 1, the three prompt examples replaced with neutral ones, and the guardrail re-measured live, 68 checks and 0 wrong, the coffee question admitted 10 of 10 without its own example; part 2, 12.3 as a classifier decision; part 4, the phrase lists replaced by `_starts_inside_record_sentence` and `_names_its_record`, replayed over three live replies with nothing a reader needed dropped. A RESIDUAL OF PART 4, found in the live run and stated rather than hidden: the switch rule is satisfied by any shared title word, and a generic one is a weak anchor. After a Tay-Sachs sentence, "No patient carried more than one of these mutations" cited a BRCA paper whose title says "patients", so "these mutations" reads as Tay-Sachs while the paper means BRCA founder mutations. The phrase list it replaced would have missed it too, since "these" is not the first word. Not fixed |
| 12.17 | A good question sometimes fails at the think step and shows a refusal | RAISED 2026-09-24 from the live runs. NOT STARTED, nobody on it | Seen twice in about forty live runs over 2026-09-23 and 2026-09-24: `Does coffee help make exercise more effective?` and `is there a trial recruiting for melanoma`, both at researcher depth, each failing with "the plan tier's response did not match the think classification schema". Neither question reaches 12.3's ask-back, which only reads one to three words, so tonight's work did not cause it. The reader sees a refusal for a question the product answers on every other run. Evidence: `testing/Developer/reports/2026-09-24_no_hardcoding/live_runs/` |

## Where we stopped

READ THE TRACKER AT THE TOP FIRST. Added 2026-09-24: everything below was
written on the morning of 2026-09-23, and the night that followed shipped
most of it. Set 12's seven questions now answer or are asked back (12.3),
12.9 to 12.13 are live, and "Where every feature stands" at the top of
this plan is the current state. This section is fully refreshed at the next
session checkpoint.

The cutoff.

- It is updated at the end of every working session, so the next
  session starts here rather than reconstructing state.
- LAST UPDATED 2026-09-23 MORNING, when the product owner brought a second
  tester's feedback and it was re-run against today's code before anything
  was planned.
- THE ONE THING TO KNOW: six of that tester's seven questions still return no
  citation at all, unchanged since the 2026-09-14 build they were asked on,
  so SET 12 IS NOW THE PRIORITY and is item 1 of "Next, in order".
- The overnight session that preceded it ran unsupervised after the product
  owner approved a named list and then authorised picking up further work.
- Eight agents ran, tiered by task.

What it did:

- Fixed 11.30's second half, the MCP address that downgraded an HTTPS request
  to plaintext, in the app rather than in a deployment setting
- Built 10.2, history showing the saved answer instantly with Run again, across
  a backend, a frontend and a third pass that closed the seam between them
- Closed both halves of D4, and made the frontend suite FASTER than it had been
  all night as well as trustworthy
- Found L-01's cause, corrected the measurement that described it, and
  established it is no longer reproducible on develop
- Probed all eleven graph templates against the live graph and removed the one
  that could never return a row
- Made MeSH identifiers resolve to real terms, in two calls for any number of
  them
- Fixed an answer that said "Found 20 records" above a list of 26
- Answered 11.32 with measurement, and recorded 11.38 after the product owner
  supplied the model's documentation mid-session

Read this, then the Set 11 table in `testing/UI_fixes_done.md`.

This section is also the shared plan. What we agreed, what is done and what is
next all live here rather than in a session that disappears, so the product
owner and whoever picks this up read the same record. Since the 2026-09-24
split, what is done lives in `testing/UI_fixes_done.md`.

The 2026-09-20 shipped list, with what to retest, is
`testing/Shipped_2026-09-20.md`. This section owns per-item status.

### The result that should shape what happens next

THE GROUNDING GATE PERMITS QUOTING AND FORBIDS EXPLAINING, and this is the
session's most transferable finding. `ground_claim` accepts a claim against a
finding only on contiguous containment. For a short record that is healthy: a
sentence wraps the value verbatim. For a long free-text value, such as an
abstract or a gene summary, only a verbatim excerpt survives, because a
sentence cannot contain a 400-word abstract.

Explaining means using different words. So every explanatory sentence the
model writes is deleted silently, and the answer arrives looking thin rather
than censored. Measured: 19 candidate sentences across 8 shapes returned 3
survivors, all literal excerpts.

FIVE VERSIONS OF THE DEPTH DIRECTIVE HAVE NOW FAILED, two of them written this
session, each by instructing the model about form:

| Version | Instructed | Result |
|---|---|---|
| 1 | Do not print identifiers | The depth refused outright |
| 2 | Keep background to a minimum | Reported three of four findings, looking confident |
| 3 | State identifiers exactly, say less | Refused with an empty narrative |
| 4 | Give each finding its own sentence | 206 words of enumeration, explaining nothing |
| 5 | Explain, quote exactly, no length rule | 58 words, still explaining nothing |

A sixth version is not the fix. The lever that remains, recorded and NOT
built because it changes what an answer is composed of rather than how a model
is instructed: have the CODE place the plain source text verbatim and cited,
the way the record tables under every answer are already built, where no model
touches the text so it can neither hallucinate nor be stripped. The product
owner reviewed this and approved the current state as is, so it is a standing
option rather than a queued task.

### What is parked, and why

- THE OMIM DISPATCH IS NO LONGER PARKED. It was enabled and reverted on
  2026-09-21 because `breadth_plan.filter_omim_titles` existed and nothing
  called it. On 2026-09-22 the filter was wired into the act result path and
  the dispatch went live. What stays true, and is why the line is kept rather
  than deleted: the dispatch and the filter ship together, and re-enabling one
  without the other cites a different gene than the question asked about.
- THE EXPLANATION HALF OF 11.31, above.
- THE BYTE CEILING. `_MAX_FINDING_TOTAL_BYTES` stays at 50,000 after the 11.33
  fix. Measured: a fetch of 20 PubMed records with 2000-character abstracts is
  45,841 bytes and all 20 rows survive; the ceiling fires at 22 rows. Whether
  50,000 is still right is a product decision, deliberately not taken inside a
  defect fix.

### What is waiting on the product owner

Rewritten 2026-09-22 after the product owner approved the review backlog: the
three consistency-run questions that used to sit here were all settled that
day (BLAST and VCF are refused, the golden widening was discarded, and the
lost search is disclosed). What remains is small, and none of it blocks:

- Four checks of under a minute each, the only rows still not approved:
  - Copy an answer and paste it somewhere (11.14)
  - Open the answer-modes info button (11.36)
  - Change the mode while a search is running (9.12)
  - Open the app twice to see different scientists with the same answer (8.4)
- Two decisions, both already on the standing list below: whether Plain
  language answers keep the small medical-advice line (9.11), and the
  trust-line wording (9.9).

The longer standing list is unchanged:

- the three `theme.ts` logo tokens
- the six undesigned surfaces
- whether answers carry a medical-advice notice
- the 720px nav
- the 20-source citation cap
- the provenance note
- the mode toggle's placement
- and the trust-line wording.

### Loose ends, named rather than left

- L-01 is MEASURED, its two causes are READ, and the reader is now TOLD:
  a lost search is disclosed under the answer and a question the product
  could not read is answered with a request for a name (`10f6a46`). What
  is NOT fixed is the cause itself: the deterministic half is a Think gap
  and the variance half is the act budget, both below.
- THE DETERMINISTIC HALF OF L-01 was a Think gap: for a GRCh38 coordinate
  range (G-001), a Pathogen Detection isolate (G-035), a BioProject accession
  (G-007) and on some passes Lynch syndrome (G-003), Think resolved no entity
  and the plan still dispatched `cypher_query`, which refuses to run with
  nothing to bind. THE COORDINATE RANGE IS FIXED (`66b3811`, the same night);
  the isolate and the accession are item 2 of the next list. G-005 and G-022
  resolve an entity and find nothing; G-036 never calls Layer 1.
- THE VARIANCE HALF OF L-01 was NOT the act budget and NOT a follow-up: the
  graph server's own log shows the question's OWN search, taking the model
  path on an exploratory no-shape question, killed by the graph's 30-second
  statement timeout after 85 seconds because the planner mis-estimates an
  id match by four orders of magnitude. Fixed for the exploratory class
  (`2bc8ec0`). G-037 and G-033 were a different fault: generation or
  validation failing before the transport ("Generated Cypher references
  vertex label", "appears to bind a literal value"). FIXED the same evening
  as fix-plan item 1:
  - No template matched, so both took the model path
  - Both take a template now (`27d68ae`)
  - And G-037 also searches GEO (`b6cd025`)
  - See the 2026-09-22 session table in `testing/UI_fixes_done.md`
- THE TRUST TIER `ask` AND THE PARKED GRADER'S `ask` ARE TWO MEANINGS OF ONE
  WORD. Widening the golden rows to accept the trust tiers was built, found to
  erase the parked grader's answer-versus-clarification distinction (two of
  its tests go red for a real reason), and discarded. The 77 percent
  answer-or-refuse figure is the one to read; the 14 percent is vocabulary.
  Recorded in `DECISIONS.md` for whoever un-parks the grader.
- DEVELOP TRACES NOTHING TO LANGSMITH, BY DESIGN: tracing runs on production
  only, product-owner confirmation of 2026-09-22. So a cause behind a develop
  measurement is read by local reproduction, as L-01's was, never from a
  trace. Any future "read the trace" step written against develop is wrong
  on its face.
- `testing/Shipped_2026-09-20.md` was found deleted from the working tree
  mid-session by something outside this session's tool calls, and restored
  from HEAD unchanged. Cause unknown.
- The 2026-09-20 L-01 instrument filtered on `layer_1` while the API emits
  `layer_1_graph`, so its own anomaly field read zero on every run. Any
  instrument that reports "no anomalies" deserves a populate-check.
- A multi-sentence record can now render as several list rows under one record
  heading, a consequence of 11.34's fix. Not a grounding or citation defect,
  and no test covers it.

### Next, in order

UPDATED 2026-09-24: items 1 and 2 below are DONE and live. Set 12's
questions answer (12.1, 12.2, 12.4, 12.7, 12.10) or are asked back when they
are one to three words (12.3). What remains of Set 12 is 12.14, 12.15 and
12.17, in section 2 of the tracker at the top, which is the current order.

REWRITTEN 2026-09-23 MORNING, after the product owner brought a second
tester's feedback. That feedback was re-run against today's code before
anything was written down, and it takes the top of this list on the product
owner's own condition: "else this the priority and we fix it first". Six of
the seven questions return no citation at all, and the seventh answers only
because its name happens to land on concept ids the graph holds.

Items 1 to 7 in `testing/Shipped_2026-09-23.md` await the product owner's
retest, and items 7 to 22 in `testing/Shipped_2026-09-22.md` are still
awaiting the retest from the night before. Nothing below is a retest; every
item is engineering or a decision, ordered by what the person typing the
question feels first.

What is open and not on this list as its own item, each recorded in
`testing/Developer/reports/2026-09-23_overnight/findings.md`:

- The graph holds no disease names and no MeSH terms. Every `Disease` vertex
  is named after its source vocabulary and every `OntologyClass` after its own
  identifier, measured graph-wide. Known since build phase 2.1 as F-2.1-B07.
  Writing the graph is Systems 1 and 2 work in the other repository, so this
  is a hand-over rather than a task. It BOUNDS item 1: a disease question can
  be answered from the live records and the literature, and never from the
  graph's disease names.
- The model's written prose still fails the grounding gate on several question
  shapes, so the code-built table carries the answer.
- `trust_outcome` is unstable: five runs with byte-identical evidence returned
  `flag` four times and `ask` once.

1. SET 12, THE SECOND TESTER'S QUESTIONS. The priority, and the one item a
   person feels immediately: seven ordinary questions, six of them unanswered.
   THE DONE-WHEN, set by the product owner on 2026-09-23, is "the whole folder
   answers": every question in `testing/User-feedback/` returns a cited answer,
   verified by re-running the committed script rather than by judgement. The
   full contract, including the one honest exception and the blocked-stop, is
   at the head of Set 12 in `testing/UI_fixes_done.md`. Three pieces of work, independent of each other,
   running in parallel since 2026-09-23:
   - 12.1, give a disease anchor the same breadth a gene anchor already has.
     `_build_layer_tool_calls` gates everything on `if gene_symbol:`, so
     "Any trials for GERD?" runs one Cypher query and never calls the trials
     registry that holds thousands of GERD trials. This is the largest of the
     three and the one that changes the most answers.
   - 12.2, put literature vocabulary in the guardrail allowlist. Today
     `any trials for gerd?` is refused as outside biomedical research and
     `Any trials for GERD?` is not, because capitalisation decides. The
     refusal text offers "a paper question" and `paper` is not in the
     allowlist.
   - 12.6 turned out to be ALREADY BUILT and is closed with no work. The
     clarification does reach the reader today, shipped 2026-09-22, and the
     tester's screenshots predate it. The claim that it was discarded was the
     assistant's, made from reading the tool's error text without checking
     what the screen shows, and it is corrected in the Set 12 table in `testing/UI_fixes_done.md` rather than deleted.
   - 12.4, stop inviting a reader to "continue the conversation" under a
     screen that carried no answer. The cheapest change here.

   VERIFY THE MARFAN PHENOTYPE QUESTION AS PART OF THIS, not separately: it is
   the same family, a disease-anchored question reaching a single graph call
   that returns nothing. It was the overnight session's one open item and it
   belongs to 12.1's fix.
2. 12.3, WHETHER A ONE-TO-THREE-WORD QUESTION SHOULD BE ASKED BACK. The
   product owner's question, now measured: there is no such clarification
   today, and the four paths that do exist cover none of it. Decide AFTER item
   1, because a question that can be answered should be answered rather than
   queried back, and item 1 changes how many of them can be answered.
3. THREE GOLDEN ROWS DISAGREE WITH THE GUARDRAIL, product owner's call, row by
   row:
   - "334" expects a clarifying ask and is refused as off-topic
   - "tell me about the tree of life" expects an answer
   - the pathogenicity classification request expects a flag rather than a
     medical-advice refusal

   Nothing blocks on it. A fourth row joins them: G-035's Taxonomy must-cite
   URL. ITEM 12.2 MAY CLOSE SOME OF THESE ON ITS OWN, since they are the same
   check.
4. THE TWENTY-SOURCE CEILING, still waiting on the product owner.
5. TELL THE READER WHEN A SEARCH WAS DRAFTED RATHER THAN CHECKED. Worker E
   established that when no code template matches, the plan-tier model writes
   the Cypher fresh, and two drafts are not equivalent. The data already
   exists: `CypherQueryOutput.template` is None exactly in that case, and
   `_cypher_output_to_structured_fields` currently drops it. THE TRAP, and the
   reason this is not the obvious one-liner: the degradation is `ok` to `ok`, a
   hundred rows then one count, NEVER an `empty`, so any rule keyed on
   empty-or-failed misses the case that actually costs the reader their
   evidence. Key it on the query having been drafted. The stronger version of
   this item is to close the remaining model path entirely, the way `27d68ae`
   closed it for gene questions.
6. 11.29's BUILD, now that its scoping document exists and is measured. Read
   `testing/Developer/reports/2026-09-23_overnight/soft_edges_scoping.md`
   first: it counts how many golden questions need multi-hop (five, all walking
   one already-built shape), how many need data the graph does not hold
   (twelve), and says plainly that vector embeddings and a RAG pipeline have a
   motivating count of zero here. Its own first recommendation is that the
   grounding gate, which accepts a verbatim excerpt and rejects a faithful
   paraphrase, is what actually stands between the product and being worth
   reading instead of a general chatbot.
7. 11.38, a bounded trial of the probability model, if the product owner wants
   it. The cheap first step is a SHADOW RUN on the guardrail: it decides in
   parallel, its answer is only recorded and never acted on, which produces
   calibration data from this product's own questions rather than a vendor
   benchmark. Output tokens are free, which is what makes that affordable.
   Acting on a confidence number is a separate and much larger decision.

   The three discussion items this list carried are all closed: 11.30 was
   built, 11.32 was answered with measurement, and 11.29's discussion produced
   the document named in item 5. 11.22's live check was already done.

NOT ON THIS LIST, and deliberately: the explanation half of item 11.31. The
product owner approved the current state as is on 2026-09-21. The remaining
lever is recorded in "The result that should shape what happens next" above as
a standing option, not as queued work.

### How to start the next session

1. Read "Where we stopped" above, starting with the one-table summary of the
   2026-09-23 overnight session, then the 2026-09-22 table, then the
   2026-09-21 table, then the Set 11 table, all in `testing/UI_fixes_done.md`.
2. Run `git status` and `git worktree list`. Both should be clean, with local
   carrying only `develop`.
3. Read "What is parked, and why" before picking anything up. OMIM is live
   WITH its title filter; the two ship together and neither is re-enabled or
   removed without the other.
4. Pick up the tracker at the top of this plan, section 2, which is the
   current order (UPDATED 2026-09-24: the rest of this step describes
   2026-09-23). Then "Next, in order" at item 1, SET 12, the second tester's seven
   questions, of which zero are answered today. Its three pieces (12.1 the
   disease anchor's breadth, 12.2 the guardrail's literature vocabulary, 12.4
   the refusal's follow-up invitation) are independent and can run in
   parallel, and the Marfan phenotype check belongs to 12.1 rather than
   standing alone. Items 2 to 4 are the product owner's calls and nothing
   blocks on them. Awaiting their retest: items 1 to 7 in
   `testing/Shipped_2026-09-23.md` and items 7 to 22 in
   `testing/Shipped_2026-09-22.md`. The call ceiling is measured and stays at
   twenty.

## Developer items

### Developer follow-through

Done alongside the sets in `testing/UI_fixes_done.md`, not as sets of their own:

- D4: fix the load-dependent frontend tests and journey 7's navigation before relying on them in quick checks. Best done during set 2.
- R37: update `Product/Product_workflows.md` in the same push as each set that changes a test.
- Any file added, renamed or repurposed under `src/` updates `docs/build/Debugging_guide.md` in the same commit, which CI enforces.
- Each set updates section 11 of the report and the progress table in `testing/UI_fixes_done.md`.

