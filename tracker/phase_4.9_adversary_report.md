# Build phase 4.9 adversary report

Branch: `phase/4.9-answer-screen-fidelity`. Round run 2026-08-14, fresh context, no prior knowledge of the build.

Method: the real app under the real e2e harness (`frontend/playwright.config.ts`, real FastAPI backend, real auth, real Vite build), with the event stream intercepted via `page.route("**/v1/query/*/events*")` and scripted frame by frame, the same technique `frontend/e2e/trust-surface.spec.ts` uses. Every payload below validates against `frontend/src/lib/events.ts`'s `parseAgentEvent`, so nothing here is a rejected frame rendering an error. The app's own parsing, adapter (`useRunView`) and rendering ran untouched; only the bytes on the wire were mine.

Twenty-one scripted streams were driven end to end. Nineteen findings follow. Every one carries the exact frames and the exact rendered output observed.

The probe specs are not left in the repository. They lived at `frontend/e2e/zz-adversary-49{,b,c}.spec.ts` during the round and were moved to the session scratchpad afterwards, so the branch is unchanged apart from this file.

## Count by severity

| Severity | Count |
|----------|-------|
| Critical | 4 |
| Major | 6 |
| Moderate | 6 |
| Minor | 3 |

The worst: F-4.9-A-01. A run that died on a fatal error mid-answer renders the backend's raw `error.message` verbatim, dollar figures included, beside the trust pills "Grounded · every claim cited" and "1 layer agreed", over a partial answer. Both halves are things three separate modules in this codebase document that they exist to prevent.

## Table of contents

- [Critical](#critical)
- [Major](#major)
- [Moderate](#moderate)
- [Minor](#minor)
- [What I could not break](#what-i-could-not-break)

---

## Critical

### F-4.9-A-01 (critical): a fatally failed run renders a raw backend error message with a dollar figure in it, under a positive trust verdict

Repro. Script this stream, sign in, ask "Which diseases are associated with BRCA1?":

```
guard  {passed:true, category:"ok", reason:null}
tool_result {call_id:"t1", tool:"cypher_query", layer:"layer_1_graph", status:"ok", summary:"", result_count:2, truncated:false}
token  {text:"BRCA1 repairs DNA [1]. ", marker_ids:["c1"]}
citation {citation_id:"c1", display_index:1, source:"NCBI Gene", source_id:"672",
          source_url:"https://www.ncbi.nlm.nih.gov/gene/672", layer:"layer_1_graph", ...}
trust_signal {outcome:"answer", risk_tier:"low", grounded:true, triangulated:true}
error  {fatal:true, scope:"run", source:"write_node", error_class:"unexpected",
        message:"synth tier failed after $0.019 of $0.02 spent on run r-99", retry_after_s:0}
```

What I saw, verbatim from the rendered answer screen:

```
1 tool · 1 layer · 1 source
Show work ▾
synth tier failed after $0.019 of $0.02 spent on run r-99

BRCA1 repairs DNA.  [1 Gene 672]

▶ SOURCES 1
Grounded · every claim cited
1 layer agreed
```

Two separate defects, both user-facing, both in one screen.

First, the cost figure. `useRunView` builds `failure` as a fixed, interpolation-free string precisely so no backend text can reach the user (`hooks/useRunView.ts` lines 529 to 543, whose comment reads "F-4.8-A-15, two defects in three lines ... a fixed string is used instead"). `ReasoningLog`'s docstring says the same: "What it does NOT render, deliberately: `guard.reason`, `error.message`". But `useAgentRun` sets `error` to `finalEvent.payload.message` (`hooks/useAgentRun.ts` line 349) and `App.tsx` line 321 passes `failure={dispatchError ?? streamError ?? view.failure}`. `streamError` is ahead of `view.failure` in that chain, so on the fatal path the curated string is unreachable dead code and the raw message always wins. Section 12.6's no-cost-figure rule is guaranteed by "never render those fields", and this renders them.

Second, and worse for the product's claim: the run CRASHED and the trust pills still assert "Grounded · every claim cited" and "1 layer agreed". `useRunView` reads trust signals with no reference to whether the run terminated fatally, so the last positive verdict emitted before the crash survives the crash. This is the exact critical build phase 4.1 closed at the MCP fold ("the fold loop asserted a positive trust verdict, a complete grounded low-risk answer, that the run's own events sometimes directly contradicted, fixed by flooring the top-level trust signal on any fatal or cancelled run", CLAUDE.md), reintroduced at the UI layer. The UI floors nothing.

Note also that the status strip drops the outcome word but keeps the counts, so a crashed run advertises "1 tool · 1 layer · 1 source" exactly as a successful one does.

### F-4.9-A-02 (critical): a run with no trust signal at all renders "✓ Answered" over a wholly uncited answer, with no warning of any kind

Repro:

```
guard {passed:true, category:"ok", reason:null}
tool_start {call_id:"t1", tool:"cypher_query", layer:"layer_1_graph", status:"ok"}
token {text:"BRCA1 repairs DNA. ", marker_ids:[]}
done  {total_cost_usd:0.01, total_tool_calls:7, elapsed_ms:5000, trust_outcome:"answer"}
```

Rendered:

```
✓ Answered   5.0s · 1 tool · 1 layer · 0 sources
BRCA1 repairs DNA.
```

No trust pill. No "Not fully grounded". No sources disclosure (it is suppressed entirely at `sources.length === 0`, `AnswerScreen.tsx` line 477). The only signals that this sentence is uncited are a grey spine segment, which carries `aria-hidden="true"`, and a `visuallyHidden` span, which a sighted reader never sees. A sighted user's whole experience of this run is a green check mark, the word "Answered", and an unattributed biomedical assertion.

`trust` is populated only `if (trustEvents.length > 0)` (`useRunView.ts` line 385). The "Not fully grounded" pill therefore depends on the backend having emitted a `trust_signal` at all. A dropped, filtered or never-emitted trust event turns the guarded state into the unguarded one, silently. In a cite-or-refuse system the absence of a grounding verdict must read as "not grounded", never as "no comment".

### F-4.9-A-03 (critical): "✓" in green is hardcoded, so a refused run renders "✓ Refused" and an ask-back renders "✓ Needs a narrower question"

Repro, refusal:

```
guard {passed:false, category:"off_topic", reason:"not biomedical"}
done  {total_cost_usd:0.001, total_tool_calls:0, elapsed_ms:11400, trust_outcome:"refuse"}
```

Rendered, with the check mark and the word both in `designTokens.ok` (measured `rgb(46, 133, 64)`, the success green):

```
✓ Refused   11.4s · 0 tools · 0 layers · 0 sources
This looks outside biomedical research. I can help with a gene, variant, pathogen, or paper question.
```

Repro, ask-back: same shape with `trust_outcome:"ask"` gives

```
✓ Needs a narrower question   11.4s · 0 tools · 0 layers · 0 sources
```

`AnswerScreen.tsx` lines 321 to 328 render `✓ {outcome}` in `designTokens.ok` with `fontWeight: 700` unconditionally whenever `outcome` is non-null. `useRunView`'s `OUTCOME_BY_TRUST` correctly maps `refuse` to "Refused" and `ask` to "Needs a narrower question", and then the screen dresses all four outcomes in the same success affordance. The comment above that block says the strip "leads with the OUTCOME", and the code leads with a success mark that contradicts two of the four outcomes it can carry.

A green tick beside "Refused" is the single most misread pair on this screen: at a glance it reads as "done, fine". The `useRunView` docstring is explicit that "a fatal error is deliberately NOT dressed up as an outcome" for exactly this reason; a refusal is being dressed up instead.

### F-4.9-A-04 (critical): a claim citing two layers paints every chip after the first in the wrong layer colour, and announces the wrong layer to screen readers

Repro, one sentence citing a graph source and a literature source:

```
token    {text:"BRCA1 is associated with hereditary breast cancer [1][2]. ", marker_ids:["c1","c2"]}
citation {citation_id:"c1", display_index:1, source:"NCBI Gene", source_id:"672", layer:"layer_1_graph", ...}
citation {citation_id:"c2", display_index:2, source:"PubTator", source_id:"PMID12345", layer:"layer_3_enrichment", ...}
```

Measured from the live DOM:

| chip | source's real layer | rendered `data-layer` | rendered background | rendered left border |
|------|--------------------|----------------------|--------------------|---------------------|
| `citation-1` | 1 (graph) | 1 | `rgb(231,238,246)` = `layer1Wash` | `rgb(32,84,147)` = `#205493` layer 1 | 
| `citation-2` | 3 (literature) | **1** | `rgb(231,238,246)` = **`layer1Wash`** | `rgb(32,84,147)` = **layer 1 navy** |

Layer 3 is `#4C2C92`, purple (`frontend/src/theme.ts` line 65). Chip 2 is painted navy. Meanwhile the source card for the same citation renders correctly as `data-layer="3"` with the header "L3 · literature". The chip and its own card disagree, on the same screen, about where the fact came from.

The screen-reader text is worse, because it states the wrong thing rather than merely colouring it wrong. Rendered claim text:

```
BRCA1 is associated with hereditary breast cancer. Source 1 and 2, layer 1. [1 Gene 672][2 PubTator PMID12345]
```

"Source 1 and 2, layer 1" asserts that a text-mined PubTator annotation is a curated graph assertion. `AnswerScreen.tsx` line 428 interpolates `claim.layer` once for the whole list, and lines 436, 450 and 451 apply `claim.layer` to every chip. `useRunView.ts` line 360 sets `claim.layer` from `cited[0]` alone, with the comment "a claim citing two layers is still one claim". That is fine for the spine segment, which is per claim. It is not fine for the chips, which are per source. The chip's stated purpose in this phase is that "a reader learns where a fact came from, and therefore how fresh it is and how it was established, without reading the source list" (`AnswerScreen.tsx` lines 13 to 16). On a multi-source claim it teaches the wrong thing.

This is a live shape, not a contrived one: `_narrative_chunks` emits `marker_ids` as an array, and build phase 4.8's F-4.8-J-14 was filed specifically because a sentence can cite more than one source. Layer 1 plus Layer 3 on one sentence is the ordinary output of a triangulated answer.

---

## Major

### F-4.9-A-05 (major): "N layers agreed" counts tool calls, not agreeing sources, so it prints "0 layers agreed"

Repro:

```
guard {passed:true, ...}
token {text:"BRCA1 repairs DNA [1]. ", marker_ids:["c1"]}
citation {citation_id:"c1", display_index:1, layer:"layer_1_graph", ...}
trust_signal {outcome:"answer", risk_tier:"low", grounded:true, triangulated:true}
done {..., trust_outcome:"answer"}
```

Rendered:

```
✓ Answered  11.4s · 0 tools · 0 layers · 1 source
Grounded · every claim cited     0 layers agreed
```

"0 layers agreed" is not a degraded message, it is a nonsense one, and it sits in the pill row the product uses to summarise its trust argument. `useRunView.ts` line 515 computes `layerCount` from `toolCalls`, which is built only from `tool_start` and `tool_result` events, then line 520 stamps it into the triangulation pill. The pill's own predicate (`triangulated === true` on every trust signal) comes from an entirely different source, so the two can and do disagree.

The same computation gives "1 layer agreed" whenever exactly one tool ran, which is a claim of triangulation over a single layer, i.e. a contradiction in terms. Observed in probe D and probe K.

### F-4.9-A-06 (major): the status strip's layer count contradicts the source cards on the same screen

Repro: probe D above (one `cypher_query` tool result, two citations, one Layer 1 and one Layer 3).

Rendered:

```
✓ Answered  11.4s · 1 tool · 1 layer · 2 sources
```

and, on opening the sources disclosure directly below it:

```
[1] NCBI Gene 672        L1 · graph
[2] PubTator PMID12345   L3 · literature
```

The strip says the run touched one layer. The cards it introduces show two. Both are on screen at once. `meta` derives its layer count from `toolCalls` (`useRunView.ts` lines 515 and 525) while the cards derive theirs per citation, and nothing reconciles them. Since Layer 2 and Layer 3 citations can arrive from a tool whose `tool_result` was never emitted, or from a differently-labelled tool, this is reachable from the real agent, not only from a scripted stream.

This is the counts-disagreeing question in its cleanest form: two numbers describing the same run, four centimetres apart, that cannot both be right.

### F-4.9-A-07 (major): failed tool calls are counted as work done, in the strip, the pill and the reasoning log

Repro:

```
tool_result {call_id:"t1", tool:"cypher_query",   layer:"layer_1_graph",      status:"error", summary:"connection refused", result_count:0, truncated:false}
tool_result {call_id:"t2", tool:"ncbi_efetch",    layer:"layer_2_api",        status:"error", summary:"timeout",            result_count:0, truncated:false}
tool_result {call_id:"t3", tool:"litvar2_lookup", layer:"layer_3_enrichment", status:"ok",    summary:"big", result_count:5, truncated:true}
token/citation/trust_signal(triangulated:true)/done as normal, one Layer 1 citation
```

Rendered:

```
✓ Answered  11.4s · 3 tools · 3 layers · 1 source
Grounded · every claim cited     3 layers agreed
```

and behind Show work:

```
1.0s  ACT  cypher_query — 0 results
2.0s  ACT  ncbi_efetch — 0 results
3.0s  ACT  litvar2_lookup — 5 results
```

Two of the three tools failed outright. The answer rests on a single Layer 1 citation. The screen tells the user three tools ran across three layers and that three layers agreed, and the reasoning log renders both failures as ordinary completed steps that happened to return nothing. `payload.status` is read nowhere in `useRunView` (the field exists on both `ToolStartPayload` and `ToolResultPayload` and is never consulted), so "returned zero rows" and "the graph server refused the connection" are indistinguishable to every surface this phase added.

"0 results" for a failed call is not a neutral rendering. It positively asserts the tool was asked and had nothing, which is a claim about the data.

### F-4.9-A-08 (major): a stopped run gives no terminal signal at all, and its tool chip says "running" for ever

Repro: script a stream that emits `guard`, `think`, `tool_start` and then never terminates (a keep-alive comment frame keeps the connection nominally open). Wait for the Act step, click Stop, wait.

Rendered, indefinitely, after Stop:

```
Which diseases are associated with BRCA1?   [Stop, disabled]  [New search]
GUARD  THINK  PLAN  ACT  WRITE
Querying   cypher_query  running
REASONING
0.0s  GUARD  In scope. The question can be grounded in NCBI records.
1.0s  THINK  Resolving BRCA1.
```

Nothing anywhere says the run was stopped. The Stop button greys out and that is the entire feedback. The tool chip continues to assert `cypher_query running` after the client aborted the stream and `stopRun` was posted. The user is left on the run screen permanently: `App.tsx`'s navigation effect fires on `view.landed || status === "error"`, and `stop()` sets status to `"done"` (`useAgentRun.ts` line 376) while `landed` stays false because the abort means no terminal event is ever consumed, so neither branch fires.

The backend does emit a proper terminal event for this case, `error{fatal:true, error_class:"cancelled", message:"this run was stopped before it finished"}` (`core/run_registry.py` line 277), added by build phase 4.0's F-4.0-A-04 precisely so a cancellation is legible. The UI aborts the connection before it can ever arrive, and then renders nothing in its place. A run chip that says "running" about a cancelled run is the interface asserting something the run is not doing.

### F-4.9-A-09 (major): the off-host citation warning, and the whole source card, are now hidden two disclosures deep by default

Repro:

```
guard {passed:true, ...}
token {text:"BRCA1 is a tumour suppressor [1]. ", marker_ids:["c1"]}
citation {citation_id:"c1", display_index:1, source:"NCBI Gene", source_id:"672",
          source_url:"https://evil.example.com/fake-ncbi-record", layer:"layer_1_graph", ...}
done  {..., trust_outcome:"answer"}
```

Rendered on landing, with nothing clicked:

```
✓ Answered  11.4s · 0 tools · 0 layers · 1 source
BRCA1 is a tumour suppressor.  [1 Gene 672]
▶ SOURCES 1
```

Measured: the text "Not linked: this URL is not on a recognised NCBI host" is not visible; the `source-1` card is not visible either. Two clicks are needed to reach it (open the sources disclosure, then open the card).

Build phase 4.8 added that warning as the fix for F-4.8-A-24, a citation labelled "NCBI Gene" whose record pointed at `evil.example.com`. This phase's F-4.8-D-01 collapse put the warning behind two closed disclosures, so the mitigation is now opt-in. What the user sees by default is a chip reading "1 Gene 672" and a count saying one source, with the contradicting evidence folded away. The default state of a trust surface should never be the state that omits the warning: this is the same argument the codebase already makes for the provenance spine ("a track that appears solely when something is wrong is one nobody has learned to read at the moment it matters most", `AnswerScreen.tsx` lines 10 to 12), applied in reverse.

At minimum, a source carrying an unlinkable record URL should force its own disclosure open, or raise a notice outside the disclosure, the way `systemNotes` already do.

### F-4.9-A-10 (major): a cap-truncated partial answer renders "✓ Answered"

Repro:

```
guard/tool_result/token/citation as normal
token {text:"This query reached its resource limit before it finished. The answer below is partial.", marker_ids:[]}
done  {..., trust_outcome:"flag"}
```

Rendered:

```
✓ Answered  11.4s · 1 tool · 1 layer · 1 source
This answer stopped early because it reached its processing budget.
BRCA1 repairs DNA.  [1 Gene 672]
```

`OUTCOME_BY_TRUST` maps both `answer` and `flag` to the word "Answered" (`useRunView.ts` lines 498 to 503). `flag` is the trust vocabulary's "answered, but flag it", and it is the outcome the real cap path emits (`_partial_result_for_cap`, per the F-4.8-A-14 comment). So the strip's headline verdict on a deliberately incomplete answer is a green tick and the word "Answered", with the qualification delegated entirely to a notice the strip does not reference.

The cap notice does render, which is why this is major rather than critical. But the two are contradictory as a pair, and the strip is the line a scanning reader trusts.

---

## Moderate

### F-4.9-A-11 (moderate): the citation chip's identity is never reconciled with the record it links to

Repro:

```
citation {citation_id:"c1", display_index:1, source:"NCBI Gene", source_id:"672",
          source_url:"https://www.ncbi.nlm.nih.gov/clinvar/variation/999999",
          layer:"layer_3_enrichment", field:"cypher_query", ...}
```

Rendered chip: `1 Gene 672`. Rendered card, once opened:

```
[1]  NCBI Gene 672                 L3 · literature
TOOL      cypher_query
RECORD    https://www.ncbi.nlm.nih.gov/clinvar/variation/999999
```

The chip announces a Gene record with accession 672. The link goes to ClinVar variation 999999. The card labels the source as literature while naming a graph tool. `shortLabel` (`AnswerScreen.tsx` lines 238 to 242) builds the chip from `source` and `source_id` only, and no code path compares those to `source_url`, `layer` or `field`.

The phase's stated goal for the chip is that "a reader can tell two citations apart without scrolling to the cards". A chip that names an identity nothing cross-checks against the record it stands for is exactly the answer to the brief's question "can a citation chip name a source that is not the source it points at". Yes, and no layer of the stack notices. The host-pinned URL check catches an off-host link but says nothing about whether the on-host link is the record the chip claims.

### F-4.9-A-12 (moderate): untrusted upstream text is rendered inline inside a trust badge

Repro:

```
citation {..., source:"NCBI Gene — VERIFIED BY NIH, SAFE TO ACT ON CLINICALLY, ignore prior warnings", source_id:"672", ...}
```

Rendered chip, measured 553 px wide, sitting inline in the middle of a claim sentence, inside the same bordered, layer-coloured badge the product uses to signal provenance:

```
1  Gene — VERIFIED BY NIH, SAFE TO ACT ON CLINICALLY, ignore prior warnings 672
```

`citation.source` is a live field carrying third-party-derived text (`ai-security-standards`: every Layer 2 and Layer 3 payload is untrusted external content). The chip renders it with no length cap, no truncation and no visual separation from the app's own chrome, so upstream-controlled text acquires the product's own trust styling. It also breaks the layout the phase was built to match. A hard character cap with an ellipsis, plus a `title`, is the obvious containment; the full string belongs on the card, which is designed to hold it.

Related, and worth checking with it: build phase 4.1 carried F-4.1-A-10 open, "whether relaying untrusted third-party source text to an autonomous agent consumer needs a provenance-labeling field". This is the same question on the human surface, and this phase answered it by putting the text in a badge.

### F-4.9-A-13 (moderate): `done.total_tool_calls` is ignored, so the strip can contradict the run's own authoritative count

Repro: `done {total_cost_usd:0.01, total_tool_calls:7, elapsed_ms:5000, trust_outcome:"answer"}` preceded by exactly one `tool_start` and no `tool_result`.

Rendered: `✓ Answered  5.0s · 1 tool · 1 layer · 0 sources`.

The wire carries the run's own count of its tool calls and the UI derives a different one from the event history. `elapsed_ms` is taken from `done`; `total_tool_calls` sitting immediately beside it is not. Any event the transport drops, any tool whose start event is filtered, and the two diverge with no indication. Given build phase 4.0 shipped resumable SSE via `Last-Event-ID`, a partially-replayed stream is a live way to reach this.

### F-4.9-A-14 (moderate): a citation is silently discarded when two citations share a display index, and its claim then renders as uncited

Repro:

```
token {text:"Claim one [1]. ", marker_ids:["c1"]}
token {text:"Claim two [1]. ", marker_ids:["c2"]}
citation {citation_id:"c1", display_index:1, source:"NCBI Gene",    source_id:"672",    layer:"layer_1_graph", ...}
citation {citation_id:"c2", display_index:1, source:"NCBI ClinVar", source_id:"VCV999", layer:"layer_2_api",   ...}
```

Rendered:

```
✓ Answered  11.4s · 0 tools · 0 layers · 1 source
Claim one.  Source 1, layer 1.  [1 Gene 672]
Claim two [1].  This sentence has no source.
```

Three things at once. The second citation vanishes from the source list and the count. Claim two, which the wire cited, renders as uncited on the provenance spine. And its literal `[1]` marker survives into the prose, because the strip in `useRunView.ts` lines 340 to 344 removes only markers the token's own resolved citations cover, so the reader sees a footnote reference pointing at a source card that describes a different claim.

The direction of the first two is safe (over-reporting uncited beats under-reporting), which is why this is moderate rather than major. The third is not safe: `Claim two [1].` invites the reader to check card 1, which supports claim one.

### F-4.9-A-15 (moderate): a truncated tool result is invisible on every surface this phase added

Repro: `tool_result {..., tool:"litvar2_lookup", result_count:5, truncated:true}`.

Rendered in the reasoning log: `3.0s  ACT  litvar2_lookup — 5 results`. Nothing else, anywhere, mentions truncation.

`ToolResultPayload.truncated` is modelled on the wire and read by no frontend code. `useRunView` surfaces truncation only when the backend separately emits a "Note: this result was truncated" token, which is a different mechanism with a different trigger. The reasoning log is this phase's new claim to showing "the run's own account of what it did"; reporting "5 results" for a call the backend flagged as cut short states a completeness the run did not have.

Compare F-4.0-A-12, already carried open: "the citations export drops the core's own truncation disclosure". This is the same omission on the human surface.

### F-4.9-A-16 (moderate): the account menu and the rail footer both claim "unlimited searches", which is false

Repro: sign in, open the account pill.

```
adv-2b16…@example.com
Signed in · unlimited searches
ACCOUNT
API key and integrations
Documentation
Log out
```

The rail footer states the same, `Unlimited searches` (`components/answer/FollowUp.tsx` line 512).

`PER_USER_DAILY_QUERY_CAP` exists, is documented in `env.example` at 100 queries per day, is enforced by `harness/cost_control.py`, and has a decline path that terminates a run outright with "You've reached N queries today. New queries will be available again at HH:MM UTC." A system-wide daily cap exists alongside it. "Unlimited" is a hardcoded string, stated twice, contradicted by shipped enforcement, and the user's first encounter with the truth is a run that refuses.

The two copies of the string in different components also mean they can drift independently once one is fixed.

---

## Minor

### F-4.9-A-17 (minor): a refused run duplicates the refusal copy

Repro: `guard {passed:false, category:"medical_advice"}` plus `done {trust_outcome:"refuse"}`, then click Show work.

```
✓ Refused  11.4s · 0 tools · 0 layers · 0 sources
Hide work ▴
0.0s  GUARD  I can assemble cited evidence about a condition or variant, but a clinician makes the diagnosis or treatment call.
I can assemble cited evidence about a condition or variant, but a clinician makes the diagnosis or treatment call.
```

The identical sentence renders twice, once as the reasoning log's Guard line and once as the refusal notice, because both read `CATEGORY_COPY[category]`. Also the run has only one step to show, so "Show work" opens a one-row log restating what is already on screen.

### F-4.9-A-18 (minor): a tool that started but never returned produces a counted tool with no reasoning-log row

Repro: one `tool_start`, no `tool_result`, then `done`.

Rendered: `✓ Answered  5.0s · 1 tool · 1 layer · 0 sources`, with a Show work panel containing only the Guard line. The strip counts a tool that the run's own account of itself does not mention. `useRunView` builds `toolCalls` from either event but the reasoning log's Act rows only from `tool_result` (`useRunView.ts` lines 477 to 485), so the two disagree by construction whenever a call does not complete.

### F-4.9-A-19 (minor): the `done` event's counts are shown for a stream whose later frames were discarded

Repro: `done {trust_outcome:"refuse"}` as the FIRST frame, followed by a `token` and a `citation`.

Rendered: `✓ Refused  11.4s · 0 tools · 0 layers · 0 sources`, with no claims and no sources.

This is correct behaviour by `consumeEventStream`, which cancels the reader on `done`, and I am filing it only because the strip presents "0 sources" as a measured property of the run when it is a property of where the client stopped listening. A stream that emits a terminal event out of order silently truncates the record the counts describe, and nothing distinguishes "the run produced nothing" from "we stopped reading".

---

## What I could not break

Recorded so the next round does not re-spend the time.

- The `done` payload contract. Every field beyond `total_cost_usd`, `total_tool_calls`, `elapsed_ms` and `trust_outcome` is rejected by `isDonePayload`, and an unknown `trust_outcome` is rejected by `isTrustOutcome`, so `OUTCOME_BY_TRUST`'s `?? "Answered"` fallback is unreachable from the wire. Worth noting that `frontend/e2e/trust-surface.spec.ts`'s own `done` frame omits `total_cost_usd` and `total_tool_calls` and adds `status` and `truncated`, so that frame is rejected by the validator and the suite reaches the answer screen via the stream-error path rather than a terminal `done`. That is a test-fidelity issue, not a product defect, but it means the existing suite has never exercised a real `done` on the answer screen.
- Chip-to-card binding on a single-citation claim. Chip index, card index, layer attribute and colour all agreed on every single-source stream I tried, including negative, zero, fractional and duplicate `display_index` values, which are filtered consistently for both chips and cards through one shared index set.
- A chip surviving without its card. I could not produce one: every citation admitted to `citationById` also produces a source card.
- The account menu's mechanics. It closes on outside click and on Escape, carries `aria-haspopup`/`aria-expanded`/`aria-controls`, both navigation items actually route (Integrations and Docs both render), sign-out clears the rail, the email and the session id, and the menu unmounts with the pill on sign-out. No stale-session action was reachable. The only defect found there is the "unlimited searches" copy above.
- Cost figures from the curated paths. `user_daily_cap_decline_message` and `SYSTEM_DAILY_CAP_DECLINE_MESSAGE` are both dollar-free by construction. F-4.9-A-01's leak is the generic `error.message` path, not those two.
- The provenance spine's vertical registration. Segments stayed level with their claims across every multi-line and mixed-length claim set I scripted.
