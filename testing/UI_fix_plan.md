# UI fix plan

The board for the UI fix loop. An item starts in To do, moves to Build in
progress when someone starts it, and moves to Retest once it is live on
develop. When you approve it, it leaves the board.

This board is the source of truth for what gets worked on: an item is written
here before it is built. The detail behind the architecture cards sits under
To do, below its table. Every other item's detail, every closed item and every
note behind the board are in `testing/UI_fixes_done.md`.

Last updated: 2026-09-25.

## To do

In priority order.

| # | Feature, in plain words | Item | Waiting on |
|---|---|---|---|
| 1 | An answer about something else can say "MedGen lists no clinical features for ...": 15 golden answers carry it, one "for Seen by breast cancer nurse" inside a question about how many genes relate to breast cancer | `testing/Developer/reports/2026-09-25_product_review_8.1/report.md`, from phase 8.1's fix round | Nobody on it |
| 2 | Every answer opens with the code-built "Found N ... records for X" line, whatever the writing model, so its first sentence never answers the question | `testing/Developer/reports/2026-09-25_writer_bench/results.md` and the 8.1 product review | Your decision |
| 3 | Answers got slower overnight: the golden run's median was 17.1 seconds after phase 8.1 and 21.9 after phase 8.2 | `testing/Developer/reports/2026-09-25_phase_8.2_golden/summary.md` | Nobody on it |
| 4 | Tell the reader when the system wrote its own search rather than using a checked one | the drafted search | Nobody on it |
| 5 | Models chosen per task by tier: open source where an equivalent is available, frontier models where they are needed | [direction, point d](#the-product-owners-direction-on-the-model-architecture-2026-09-23) | Your decision: pick the writing model from `testing/Developer/reports/2026-09-25_writer_bench/results.md` |
| 6 | The agentic loop: interpret the objective, make a plan, use tools, check intermediate results, adjust when something fails, produce or apply the final result | [the agentic loop](#the-product-owners-direction-on-the-model-architecture-2026-09-23) | Nobody on it |
| 7 | Hard and soft edges over a fuller graph, "connecting the dots" | [11.29](#detail-1129) | Nobody on it |
| 8 | The trust-line wording | 9.9; built on the unmerged branch `phase/8.4-answers-worth-reading`, not on develop | Your decision |
| 9 | Judge answer quality once answering is reliable | 10.4 | Nobody on it |
| 10 | A lock file for the Python build | the lock file; decided 2026-09-25, not built | Nobody on it |
| 11 | The same question does not always return the same papers: six identical PubMed searches returned two different sets, and `reflux disease` found nothing on one run in six | Where we stopped, notes carried over from the old tracker; tried 2026-09-25, not reproducible, fix reverted: `tracker/phase_8.1.md` F-8.1-03 | Nobody on it |
| 12 | The trust verdict under an answer changes with nothing else changed: five runs on identical evidence gave `flag` four times and `ask` once | Where we stopped, Next, in order; tried 2026-09-25, the fix labelled correct answers as disagreeing and was reverted: F-8.1-A13 | Nobody on it |
| 13 | `What genes are associated with MODY?` failed its citation check on 5 of 6 runs on 2026-09-20, and nobody owns it | Shipped days, 2026-09-20; tried 2026-09-25, the fix weakened the citation check and was reverted: F-8.1-J01 | Nobody on it |
| 14 | One search took 127 seconds against a median of 14, and nobody owns it | Shipped days, 2026-09-20; diagnosed 2026-09-25, a timeout that stops the wait but not the work: F-8.1-05 | Nobody on it |
| 15 | Close the remaining path where the system writes its own graph search, or ask the reader instead; card 7 only tells them | L-01 | Nobody on it |
| 16 | Three golden questions get nothing from the graph: G-005 and G-022 find nothing, and G-036 never searches it | Where we stopped, loose ends | Nobody on it |
| 17 | A reworded sentence that switches papers can point at the wrong paper when the only title word it shares is a generic one, such as "patients" | 12.16 part 4; built on the unmerged branch `phase/8.4-answers-worth-reading`, not on develop | Nobody on it |
| 18 | A record with several sentences shows as several list rows under one heading, and no test covers it | Where we stopped, loose ends; a helper is on the 8.4 branch, its wiring in `core/graph.py` is not built | Nobody on it |
| 19 | The paced handoff may show a false writing step on some other path, and nobody has checked | 11.28 | Nobody on it |
| 20 | An isolate search can filter only by gene prefix | Shipped days, 2026-09-22; year from the question built on the 8.4 branch, location needs the plan step | Nobody on it |
| 21 | The two command line examples on the Integrations page have never been run as printed | 11.30; measured 2026-09-25, the page fix is on the 8.4 branch | Nobody on it |
| 22 | One answer shows several different totals and never says which is which | D-2, Shipped days, 2026-09-20; the screen half is on the 8.4 branch, the backend wording is not built | Your decision |
| 23 | The provenance note under the variant-to-disease table | Where we stopped, waiting on the product owner; a helper is on the 8.4 branch, its wiring in `core/graph.py` is not built | Your decision |
| 24 | Where the Plain language and Researcher toggle goes | Where we stopped, waiting on the product owner; built on the unmerged branch `phase/8.4-answers-worth-reading`, not on develop | Your decision |
| 25 | Install the public USWDS package, the base of the NCBI design system: yes or no | 2.13; decided 2026-09-25, not built | Nobody on it |
| 26 | Seven test files the deletion inventory set aside | Where we stopped, loose ends; decided 2026-09-25; the deletion was reverted because one file pinned three controls (F-8.5-V08) | Nobody on it |
| 27 | Merge bossman mode's two modes, due with the next build phase | Session history, 2026-09-24 evening | Nobody on it |
| 28 | Something deleted a tracked file from the working tree during a session, and the cause is unknown | Where we stopped, loose ends; lead found 2026-09-25: a process makes " 2" copies inside the repository mid-session (a ref file, `.git/index 2`), likely iCloud Desktop sync | Nobody on it |
| 29 | Show the sentences that answer the question, quoted under each paper, so nobody has to open the paper to find them: from NCBI's LitSense, probed on about ten golden questions before it is built | [13.1](#detail-131); probed twice 2026-09-25, useful for 4 of 20 papers, not built: `testing/Developer/reports/2026-09-25_phase_8.4/litsense_probe/findings.md` | Your decision |
| 30 | `Which BRCA1 variants are pathogenic?` lists 40 unclassified variants and the model's honest caveat is stripped | `tracker/phase_8.1.md` F-8.1-A16, found 2026-09-25, older than that night | Nobody on it |
| 31 | At Researcher depth a question about a disease's features shows them in the list but not in the written answer: give them room in the prompt only when a classifier decides the question asks about features | F-8.1-V01 | Nobody on it |
| 32 | A graph search column named `clinical_features` would be read as MedGen's clinical features | F-8.1-V02 | Nobody on it |
| 33 | Two golden questions that answered on 2026-09-22 no longer do: G-004, a Salmonella isolate question that runs no search, and G-006, sequence data for PMID 11237011 | the golden run of 2026-09-25, `testing/Developer/reports/2026-09-25_phase_8.1_golden/` | Nobody on it |
| 34 | Jev's comparison table is mostly empty: let DeepSeek's pick land any time before the answer finishes, not within one second | `testing/Developer/reports/2026-09-25_phase_8.2_golden/decisions_comparison.md` | Nobody on it |
| 35 | An off-topic follow-up that happens to contain a biomedical word such as "cell" or "study" still gets through, as it did before tonight | `tracker/phase_8.2.md` F-8.2-V01 | Nobody on it |
| 36 | A picked "How far back" window is lost after a restart or deploy, and nothing tells the person | F-8.2-V02 | Nobody on it |

Below sits the detail behind architecture cards 8 to 13 and card 14, 11.11.
It moved here from `testing/UI_fixes_done.md` on 2026-09-24 without a word
changed:

- The product owner will build this work, so no architecture card is parked.
- A status or position written inside the detail records the day it was
  written, and the cards above are current. Among them:
  - 11.32 and 11.38, "backlog only"
  - 11.32, "parked as a discussion that precedes a build"
  - 12.3, "the product owner's open decision", now live and in Retest
  - 11.11, "Tenth" in "Next, in order", now fourteenth
- Set 11's intro, which the table below points to, stays in
  `testing/UI_fixes_done.md`.
- The product owner's direction on the model architecture, in their own
  words, follows the detail for 11.38.

### Set 11, still open

Set 11's intro below defines most of the status words these rows use.

| # | Your feedback | Status | Where it stands |
|---|---|---|---|
| 11.11 | Use your reference prototype for answer depth, formatting and structure; it writes with a different model family | Queued | Tenth in "Next, in order". It was listed as in progress until 2026-09-24 with nobody on it, so it moved out of section 1. 12.9 and 12.10 answered part of its ask. The answer-writing model is unchanged: switching models is a separate decision |
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

#### Detail 13.1

The ask, raised by the product owner on 2026-09-25 after a codeathon: RAG-style retrieval of the specific sections of a source that answer the question, since today the product hands people sources and they still have to browse them.

Status: Not started. Decided 2026-09-25 (`DECISIONS.md`): add the card, probe first.

- The source: NCBI's LitSense, sentence-level search over PubMed abstracts and PMC full text, with the index hosted by NCBI. The locked technical specification already names it as a Layer 3 source in Section 5; nothing in the code calls it yet.
- The probe, first: about ten golden literature questions sent to LitSense live, measuring whether the returned sentences answer the question and how long each call takes.
- The build, in phase 8.4 of `testing/Overnight_build_plan_2026-09-25.md` if the probe holds: the answering sentences shown quoted under each paper, each cited. Verbatim sentences pass the cite-or-refuse gate by construction.
- Not built: chunking or embedding full texts ourselves, which is a data-pipeline project for the data repository.
- Budgets: one of the twenty per-query calls, a 15-second timeout, and the provisional 5 requests per second throttle, since LitSense publishes no rate limit.

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

## Build in progress

Nothing is being built right now.

## Retest

Built and live on develop, newest first. The queries to type and what you
should see are in `testing/Test_queries_and_workflows.md`, by the number in
the last column.

| # | What to check, in plain words | Item | Queries |
|---|---|---|---|
| 1 | A question the biomedical word list does not know is judged by the classifier, not refused: the tree of life is answered, pizza is refused, and off-topic follow-ups are refused | Jev as the classifier, golden row G-038 | 83 |
| 2 | "Recent papers" asks how far back to search, and the choice narrows the papers | 12.15 | 84 |
| 3 | Whether a question wants papers is a classifier's choice, not a word list | 12.16 part 3 | 85 |
| 4 | Jev makes the small choices on develop and DeepSeek's pick is recorded beside it: read the comparison table | Jev, the probability model trial | Nothing to try by hand: `testing/Developer/reports/2026-09-25_phase_8.2_golden/decisions_comparison.md` |
| 5 | The NCBI and enrichment calls are listed once as typed functions the classifier can choose from | 11.32, the function catalogue | Nothing to try by hand: `src/system_03_search_agent/tools/catalogue.py` |
| 6 | Golden row G-035 accepts the Taxonomy link the product cites | the golden rows | Nothing to try by hand |
| 7 | The graph's data gaps are handed to the repository that writes the graph | disease names, the hand-over | Nothing to try by hand: read `docs/data-engineering/Graph_data_hand_over_2026-09-25.md` |
| 8 | The design card's four type values match the shipped code | 2.13, the four type values | Nothing to try by hand |
| 9 | `/phase-checkpoint` names the counts line by what it holds | the checkpoint line | Nothing to try by hand |
| 10 | A question about a disease's features names them, each cited to MedGen: in the written answer at Plain language, in the list at Researcher | 12.14 | 81 |
| 11 | A good question is never refused because the think step's reply was malformed | 12.17 | 80 |
| 12 | An answer can cite up to 30 sources, and a question about papers reaches them | the ceiling, the byte ceiling | 82 |
| 13 | An NCBI outage no longer turns the build red | the live NCBI unit test | Nothing to try by hand: CI's unit gate deselects the live test |
| 14 | "Based on N sources" equals the SOURCES count on the page | 12.11, 12.8 | 74 |
| 15 | No broken sentences and no restatement paragraph | 12.12 | 75 |
| 16 | The answer answers the question in plain sentences drawn from the papers, each cited | 12.10 | 73 |
| 17 | A search clicked in the history rail, in the same tab, opens its saved answer | 12.13 | 67 |
| 18 | Plain language and researcher differ on every question | 12.9 | 72 |
| 19 | A one-to-three-word question is asked back, with choices written for its subject | 12.3 | 76 |
| 20 | The seven questions your skip manager asked all answer | 12.1 | 68, 69, 73 |
| 21 | A literature question typed in lowercase is not refused as "Outside biomedical research" | 12.2 | 70 |
| 22 | A refusal says "Ask another question" | 12.4 | 71 |
| 23 | A question naming no gene and no disease finds the papers, each shown once | 12.7 | 69 |
| 24 | The MCP configuration on the Integrations page connects, and never sends you to an `http://` address | 11.30 | 60 |
| 25 | History shows the saved answer at once, with Run again | 10.2 | 67 |
| 26 | MeSH terms show as real terms, each linked to its MeSH record | G-019 | 64 |
| 27 | The opening sentence's count agrees with the list beneath it | the opening count | 65 |
| 28 | The Marfan phenotype question no longer says "I could not find evidence"; what it answers instead is 12.14 in To do | the phenotype template | 66 |
| 29 | Two questions keep their own graph search: MLH1 and MSH2, and GEO datasets for TP53 | G-033, G-037 | 24, 25 |
| 30 | A chromosome range is answered with its genes and records, and a range with no assembly asks which | the coordinate range | 27, 28, 29 |
| 31 | An answer never lists the question's own words as diseases it did not address | the question's own words | 23, 25 |
| 32 | A BioProject or BioSample accession is answered, and an unknown one is named as not found | the accessions | 30, 31, 32 |
| 33 | Pathogen Detection isolate questions answer with a table of isolates and their resistance genes | G-035 | 33, 35, 36, 38, 39, 40, 44, and `testing/Product/queries/Isolate_search_queries_and_workflow.md` |
| 34 | Copy an answer and paste it somewhere: no "Source 1, layer 2" text | 11.14 | 6 |
| 35 | Open the answer-modes info button: no promise of a word count | 11.36 | 3 |
| 36 | Change the mode while a search is running: it cannot change mid-search | 9.12 | 4 |
| 37 | Open the app twice: different scientists, the same answer | 8.4 | 9 |