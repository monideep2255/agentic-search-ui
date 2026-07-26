## V1 scope boundary

`requirements/PRD.md` and `requirements/Technical_specification.md` are locked. Both name capabilities explicitly excluded from v1. Nothing currently enforces either list at the point an agent is actually writing code, which is low risk under supervised work and high risk under a long autonomous run: an out-of-scope capability that looks easy, fits naturally next to what is already being built, or would make a demo more impressive is exactly the kind of boundary an agent talks itself across when no one is watching each step. This rule is the enforcement point. Read the two source lists, never edit them: `PRD.md` and `Technical_specification.md` are locked documents.

### The load-bearing principle

Building an out-of-scope capability is a scope violation regardless of how easy it looks, how well it would fit the surrounding code, or how directly it would answer the user's underlying question. Ease of implementation is not a scope criterion. Each deferred capability below has a named trigger, and the trigger is the only thing that promotes it into scope. An agent does not invent its own trigger, does not decide a trigger has been met without evidence, and does not build the capability "just this once" or "as a small version" to unblock other work. An agent that encounters a task crossing this boundary stops and reports rather than proceeding, especially during autonomous execution such as bossman-mode phases, where this rule binds hardest because no human is reviewing each step as it happens.

### PRD: out of scope for v1

From `requirements/PRD.md`, "Out of scope for v1":

- Compute tools: no BLAST, no sequence-similarity search, no VCF ingestion. The three execution-heavy questions (Q2, Q7, Q9) are the fast-follow set.
- Segmental-duplication overlap for Q1: deferred to the fast-follow with a UCSC source.
- External non-NCBI knowledge-graph federation: v1 federation is exactly the three data layers.
- Model distillation (fine-tuning a smaller student model): a v2 optimization, deferred until query logs stabilize.
- Fusion and ensemble model panels: a v2 triggered-escalation lever.
- The automated mining half of the online feedback loop: v1 ships capture plus manual review plus hand-promotion.
- Full Section 508 and WCAG audit, and enterprise security (IAM, session expiry, access review): the production track.
- Sub-query decomposition for deep research: the planned upgrade, triggered by a failure rate above 20 percent on that query class.

The external non-NCBI knowledge-graph federation item has no separately named trigger anywhere in the technical specification's fast-follow table below. Treat the absence of a trigger as a reason to stop and ask, never as license to build it because no promotion condition was written down.

### Technical specification: fast-follow disposition (Section 25)

From `requirements/Technical_specification.md` Section 25, each row names why the capability is deferred and the specific trigger that promotes it:

| Capability | Why deferred | Trigger to build |
|------------|---------------|-------------------|
| Automated mining, stage 2 of the feedback loop | Decision G scopes v1 to capture plus manual review plus hand-promotion | Enough interaction data captured to cluster meaningfully |
| Persistent cross-session per-user memory | Decision F scopes v1 to bounded in-conversation session memory only | Interaction capture (build phase 4.6) has run long enough to seed it |
| Compute tools: BLAST, sequence-similarity search, VCF ingestion (Q2, Q7, Q9) | PRD out-of-scope for v1, the seven must-pass questions already cover all three wedge types without them | The fast-follow set is added after the loop works, with pinned fixtures |
| UCSC segmental-duplication enrichment for Q1 | Not in the NCBI three-layer API set, PRD out-of-scope for v1 | A new non-NCBI source integration, scheduled with the fast-follow set |
| Model distillation (fine-tuning a student model) | PRD out-of-scope for v1, a v2 optimization | Query logs stabilize enough to distill from |
| Fusion and ensemble model panels | PRD out-of-scope for v1, a v2 escalation lever | Low-confidence or hardest deep-research queries need it, gated by cost caps |
| Sub-query decomposition for deep research | Single orchestrator holds for v1 | Failure rate above 20 percent on the deep-research query class |
| Full Section 508 and WCAG 2.1 AA audit, enterprise IAM | Track 1 prototype does reasonable-effort accessibility only, enterprise IAM is a production-track concern | Migration to the NCBI or OCCS production track |
| FedRAMP, FISMA, ATO federal authorization path | Binds the production path only, per Step 1.13 | Migration to the NCBI or OCCS production track |

### How the two lists relate

The PRD states the out-of-scope decision at the product level. The technical specification's fast-follow table restates most of the same items with an implementation-level trigger attached, and adds two items the PRD does not separately name: persistent cross-session per-user memory (PRD's session-memory-only framing implies it, but the tech spec's Decision F and G are the controlling source) and the FedRAMP, FISMA, ATO federal authorization path (an extension of the PRD's "production track" framing for enterprise security). When the two lists differ on wording, the technical specification is the more recent and more specific source, consistent with how Section 25's own flags table resolves conflicts between the two documents elsewhere.

### Known anchors, always in scope for this rule

Regardless of which list an agent consults, three items are the most likely to look like a natural, low-cost addition mid-build and must never be built in v1 without an explicit trigger event and human sign-off: no BLAST, no sequence-similarity search, no VCF ingestion. These are the compute-tools items driving Q2, Q7, and Q9, and they are the anchor case this rule exists to stop.

### What "stop and report" means in practice

- Name the specific capability and quote or point to the exact out-of-scope or fast-follow line it falls under.
- State what would have been built and why it looked like the natural next step.
- Do not silently substitute an in-scope alternative and continue without flagging the substitution, since that hides the boundary crossing rather than avoiding it.
- Wait for explicit human confirmation that the named trigger has actually been met, or that the user wants an exception, before proceeding. A trigger being plausible is not the same as a trigger being confirmed met.

### Three-state permissions

Allow:
- Reading the PRD's out-of-scope section and the technical specification's fast-follow table freely to check whether a task crosses the boundary
- Flagging a scope violation in an existing plan, PR, or in-progress build during any review, without asking
- Building toward any capability inside the locked build order in Technical_specification.md Section 25 that is not named on either list above

Ask:
- Before building any capability on either list above, even a small or partial version, if a human has stated the named trigger is now met
- Before treating a PRD item that has no matching tech-spec trigger, such as external non-NCBI knowledge-graph federation, as buildable for any reason

Deny:
- Never build a capability named out-of-scope or fast-follow because it looks easy, fits naturally, or would improve a demo
- Never invent a trigger, or assert a named trigger has been met, without explicit human confirmation
- Never silently substitute an in-scope workaround for an out-of-scope capability without flagging the substitution
- Never edit `requirements/PRD.md` or `requirements/Technical_specification.md`, they are locked
- Never treat this rule as suspended by `bossman-mode`. The bossman-mode rule suspends clarification and permission-seeking for in-scope execution decisions, not for crossing the v1 scope boundary itself

The test: before writing code, does the capability appear on the PRD out-of-scope list or the technical specification fast-follow table, and if so, has its named trigger actually been confirmed met by a human, not assumed?
