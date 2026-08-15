# Build phase 4.9 judge report

Branch: `phase/4.9-answer-screen-fidelity`
Compared against: `develop`
Judged: 2026-08-14, fresh context, no inherited assumptions from the lead
Judge scope: the premise, not the ticket checklist

## Verdict

FAIL.

Not because the answer screen is wrong. It is mostly right, and the four
findings that were invisible to every prior check (D-09 through D-12) really
did get closed. The verdict is FAIL for three reasons, in order of weight:

1. The gate does not hold. Three mutations aimed directly at three separate
   clauses left the gate 13 of 13 green. One of them deletes a feature this
   phase shipped (the sources count badge) outright. The tracker states "every
   clause is mutation-proven" and "16 mutations, every one red"; that claim
   does not survive a mutation the lead did not pick. The root cause is one
   fixture that is collinear on every axis the gate asserts, and the gate's own
   coverage statement, which `goal-contracts` requires to name what it does not
   test, does not name it.
2. A gate that was green on `develop` is now red. The Playwright suite ran 29
   of 29 twice on `develop` and 28 of 29 in two of three runs on this branch,
   failing a different geometry test each time. I measured the mechanism, and
   it is this phase's own change. The tracker and the board both report 29.
3. Two of the ten tickets are incomplete against the prototype in ways the
   omissions table does not declare, so those gaps are discovered rather than
   arguable. One of them mislabels a whole class of source.

Findings 04, 05, 06 alone would not fail the phase. Findings 01 through 03
would, individually.

## What I verified as correct

Stated because a FAIL that does not say what held is not a useful report.

| Claim | How I checked it | Result |
|-------|------------------|--------|
| Nav order Search, Integrations, About, Docs | Prototype `app.html:441-452` against `AppShell.tsx:26-33` | Exact |
| Status strip text and order | Prototype `.summary` at `app.html:529-533` plus `meta:'11.4s · 3 tools · 3 layers · 3 sources'` at `app.html:824`, against a live render | Exact: `✓ Answered` `11.4s · 4 tools · 3 layers · 3 sources` on a 4-tool fixture |
| `Show work ▾` / `Hide work ▴` | Prototype `toggleWork()` `app.html:1494-1498` | Exact, both glyphs |
| Sources start collapsed, outer disclosure with count, cards independently collapsible | Prototype `finish()` `app.html:1407-1425`, no `open` on `.srcwrap` or `.src` | Exact; the independence clause is genuinely falsifiable (mutation 4 below turned it red) |
| Citation chip carries source identity | Prototype `app.html:831-833`, `<span class="cite c1">1 <span class="src">Gene 672</span></span>` | Matches for the shapes the prototype names |
| Follow-up precedes the rating, labelled "Continue this conversation" | Prototype `#tail` `app.html:539-553` | Order and text exact |
| Trust pill states the layer count | Prototype `app.html:838`, `['plain','3 layers agreed']` | Exact |
| `#tail` order: sources, verdict, follow-up, feedback | Prototype `app.html:539-553` against `AnswerScreen.tsx:477-770` | Exact |
| Run screen order: askline, stepper, persona caption, tool chips, reasoning | Prototype `app.html:499-520` against `RunScreen.tsx` | Exact |
| F-4.9-D-13, the flag button's `nested-interactive` claim | Ran axe against both placements myself in a throwaway Playwright spec | Confirmed. Summary-nested: `["document-title","html-has-lang","nested-interactive"]`. Outside summary: `["document-title","html-has-lang"]`. The claim is real, not a rationalisation |
| F-4.9-D-14, the avatar contrast claim | Computed the composite myself. `rgba(255,255,255,.08)` (`.who`) then `rgba(255,255,255,.22)` (`.av`) over `--blue` `#205493` | Reproduces the lead's numbers exactly: `#5F84B1`, white at 3.873:1. Navy is 13.632:1. The two-layer composite matters; a single-layer one gives 4.448:1 and would also fail |
| SNAPSHOT date not derivable | `contracts/events.py:135-151`, `CitationPayload` with `extra="forbid"` | Confirmed. No such field on any payload |
| Entity name not derivable | Same, plus `ResolvedEntity` at `events.py:78-83` and `core/graph.py:931` | Confirmed. `resolved_entities` carries `text`+`curie` but the shipped `think_node` emits `[]`, and it is not bound to a citation |
| Risk reason not derivable | `TrustSignalPayload`, `events.py:154-193` | Confirmed. `risk_tier` is a bare string; `message`/`fallback_link` are the Section 8.4 refuse payload, not a reason. No edge label anywhere on the wire |
| Doc drift | `python3 tracker/check_doc_drift.py --check` | `ok: 10 facts computed \| 0 stale \| 0 structural` |
| Typecheck, production build, vitest | `npx tsc --noEmit`, `npm run build`, `npx vitest run` | Clean, clean, 147 passed |

On the changed pre-existing checks (judge instruction 3): the two rail
sign-out routes, the trust-surface disclosure-opening helper and the
accessibility `step-Guard` locator are all route changes with the guarantee
intact. The rail counts inversion is equivalent in strength, not weaker: both
directions are equally satisfiable against a mock that produces identical
values, which was already true before. `testTimeout` is treated separately as
F-4.9-J-11.

---

## Findings

### F-4.9-J-01 (major) The sources count badge can be deleted and the gate stays green

File: `frontend/src/phase49Premise.test.tsx:286`, against
`frontend/src/components/screens/AnswerScreen.tsx:519-533`

The clause "starts the sources collapsed, with their count, and opens them"
asserts the count with:

```js
expect(wrap).toHaveTextContent("3");
```

`wrap` is the whole `<details>`, and a closed `<details>` still holds its
children in the DOM, so `textContent` includes every source card. The third
card's `source_id` is `21990134`, which contains the character `3`. The
assertion is satisfied by the fixture's own data regardless of whether a count
is rendered at all.

How I verified: deleted the entire count-badge `<Box>` (`AnswerScreen.tsx:519-533`)
and ran the gate.

```
MUTATION APPLIED: count badge removed
Test Files  1 passed (1)
     Tests  13 passed (13)
```

This is the tenth assertion-that-cannot-fail found in this territory. The
count is half of what T-4.9-05 delivers and nothing protects it.

### F-4.9-J-02 (major) The gate's fixture is collinear on every axis it asserts, and the coverage statement does not say so

File: `frontend/src/phase49Premise.test.tsx:97-128` (the fixture),
`:24-54` (the coverage statement)

In `STREAM`, every quantity the gate distinguishes is numerically identical or
positionally identical to every other:

- `display_index` 1, 2, 3 map to `layer_1_graph`, `layer_2_api`,
  `layer_3_enrichment`, in that order. Citation index equals layer number
  equals card position.
- tool count is 3, layer count is 3, source count is 3.

So no clause can tell which field a value was derived from. Two mutations
aimed at two different clauses prove it.

Mutation A, aimed at "names each source's layer in words, not just L1"
(`:309-319`). Changed `AnswerScreen.tsx:594` from keying the layer word off
`source.layer` to keying it off `source.n`, the card number:

```
MUTATION 3 APPLIED: layer word keyed off the card INDEX, not the layer
Tests  13 passed (13)
```

That is not a theoretical defect. The backend numbers citations in claim order,
not layer order, so source `[1]` is routinely a layer 2 or layer 3 record. Under
that mutation every such card is labelled with the wrong layer, and the clause
whose entire job is the layer word stays green.

Mutation B, aimed at "states the outcome and the elapsed time, not counts
alone" (`:186-198`). Rewrote `useRunView.ts:523-527` so the strip reports
`sources.length` as the tool count, `sources.length` as the layer count and
`toolCalls.length` as the source count:

```
MUTATION 2 APPLIED: counts swapped/aliased
Tests  13 passed (13)
```

`goal-contracts` requires a verify surface to state its own coverage, and this
gate's statement does that carefully for geometry and for the three unbuildable
fields. It says nothing about the fixture being collinear, which is the one
property that determines whether nine of its thirteen clauses mean what they
appear to mean. Someone asked "what would this gate miss" could not answer it
from the gate.

I built a non-collinear fixture (citation `[1]` = layer 3, `[2]` = layer 1,
`[3]` = layer 2; 4 tools, 3 layers, 3 sources) and rendered the real app
against it. The shipped code is correct on every one of these axes. Only the
gate is blind.

### F-4.9-J-03 (major) The Playwright suite regressed from green to intermittently red, and this phase's change is the mechanism

Files: `frontend/e2e/rail-collapse.spec.ts:43-64` (the helper), `:91`, `:167`,
caused by `frontend/src/components/screens/RunScreen.tsx:277-297`

Measured, serially, `--workers=1`, tracked specs only:

| Branch | Run 1 | Run 2 | Run 3 |
|--------|-------|-------|-------|
| `develop` | 29 passed | 29 passed | — |
| `phase/4.9-answer-screen-fidelity` | 28 passed, 1 failed (`:167` full height of the shell) | 28 passed, 1 failed (`:91` collapses to a strip) | 29 passed |

Two different tests, two different runs, both pass in isolation. `develop` did
not fail once.

The mechanism, measured directly with a probe spec that samples the layout
every 400ms after `signInAndAsk` returns:

```
PROBE 0 {"scrollH":720,"clientH":720,"mainH":566.39,"headX":476,"landed":false}
PROBE 3 {"scrollH":720,"clientH":720,"mainH":566.39,"headX":365,"landed":false}
PROBE 4 {"scrollH":731,"clientH":720,"mainH":577.47,"headX":365,"landed":true}
```

The content's left edge moves 111px and the shell's height moves 11px while
these tests are measuring, and after landing the document overflows its
viewport (731 against 720), which is where a scrollbar enters the geometry.
`signInAndAsk` waits only for the rail to become visible, never for the run to
land, so it returns during exactly that window. `develop`'s run screen was
static enough for the race not to matter; T-4.9-04 added a reasoning log that
grows as steps arrive, and that is what opened the window.

This is a merge gate, and the tracker (`tracker/phase_4.9.md:35`) and the board
(`tracker/BOARD.md:62`) both record it as 29 passed. It is 28 in two runs of
three on this branch.

### F-4.9-J-04 (moderate) A ClinicalTrials.gov source is labelled "L3 · literature"; the prototype says "L3 · trials"

File: `frontend/src/components/screens/AnswerScreen.tsx:226`

```js
const LAYER_WORD: Record<number, string> = { 1: "graph", 2: "live", 3: "literature" };
```

The prototype has four tag values, not three. `app.html:895`, `:896` and `:929`
all read `tag:'L3 · trials'` for ClinicalTrials.gov sources, alongside
`'L3 · literature'` for PubTator, LitVar2 and PubMed at `:892`, `:893`, `:894`.

Rendered against a real `clinicaltrials_search` citation, the shipped card reads:

```
▶[1]ClinicalTrials.gov recruiting  L3 · literature
```

A registry record is not literature, and this is the exact class of substitution
the premise forbids: the specific the prototype names, replaced with a summary
of it. `clinicaltrials_search` is one of the seven tools and ships today, so
this is reachable in production, not hypothetical. It is derivable from the
citation's own `field`, so it is not blocked by a missing backend field, and it
is not in the omissions table.

### F-4.9-J-05 (moderate) The run screen's reasoning is not the prototype's disclosure and has no step counter

File: `frontend/src/components/screens/RunScreen.tsx:277-297`

The prototype's run screen carries (`app.html:515-518`):

```html
<details class="trace" id="traceWrap" open>
  <summary><span class="arrow">▶</span>Reasoning<span class="tn" id="traceN"></span></summary>
  <div class="tracelog" id="trace"></div>
</details>
```

`traceN` is set on every trace line to `st.trace.length + ' steps'`
(`app.html:1311`), and `.trace>summary` is styled as a working disclosure with
a rotating arrow (`app.html:166-170`).

What shipped is a static uppercase `<p>Reasoning</p>` followed by the log. No
disclosure, no arrow, no "N steps" counter. On a long run the prototype lets a
reader collapse the log; the shipped screen does not. The counter is a specific
the prototype names and it is not in the omissions table.

### F-4.9-J-06 (moderate) The answer screen's Show work panel drops the prototype's tool-chips row

File: `frontend/src/components/screens/AnswerScreen.tsx:354-358`

The prototype builds `#workPanel` as two blocks (`app.html:1342-1344`):

```js
$('workPanel').innerHTML = '<div class="now" style="margin:0">' +
  item.tools.map(...).join('') +
  '</div><div class="tracelog" style="max-height:none;margin-top:14px">' + (st.trace || []).join('') + '</div>';
```

The tool chips come first, the trace log second. What shipped is the trace log
only. Rendered, the whole panel is:

```
0.0sGuardIn scope. ... 0.0sActclinicaltrials_search — 47 results0.0sActcypher_query — 25 results...
```

The chips are the layer-coloured summary of what the run touched, and once the
run screen is gone this panel is the only place they exist. T-4.9-03's own
ticket text says the disclosure reopens "the run's steps", so half the panel is
missing against the source of truth, and the omission is not declared.

### F-4.9-J-07 (minor) The reasoning log's phase label is one colour; the prototype colours it by layer

File: `frontend/src/components/screens/ReasoningLog.tsx:75`

Every phase label renders `designTokens.blue`. The prototype colours it by the
layer the line belongs to (`app.html:180`):

```css
.tl.p1 .ph{color:var(--l1)} .tl.p2 .ph{color:var(--l2)} .tl.p3 .ph{color:var(--l3)} .tl.p0 .ph{color:var(--ink-faint)}
```

and assigns the class per act line from the tool's own layer
(`app.html:1287`, `cls:'p'+t.c.slice(1)`). Layer colour is this product's
central signal, and `ReasoningStep` carries no layer field to restore it with,
so this is a shape decision in T-4.9-01's own deliverable rather than a CSS
detail.

### F-4.9-J-08 (minor) The account initials do not use the prototype's algorithm, and the comment says they do

File: `frontend/src/components/shell/AccountMenu.tsx:33-36`

```js
/** The prototype's `.av`: the account's first two characters, uppercased. */
function initialsOf(email: string): string {
  return email.slice(0, 2).toUpperCase();
}
```

That is not what the prototype does. `initials()` at `app.html:1543-1546` takes
the local part, splits it on non-alphabetic characters, and takes the first
letter of each of the first two words. For `first.last@example.com` the
prototype gives `FL`; the shipped code gives `FI`, which I confirmed by
rendering it:

```
=== ACCOUNT PILL ===
"FIfirst.last@example.com▾"
```

The two agree only on single-word local parts, which is what the gate's fixture
and every existing test happen to use. Per `self-eval-loop`, a comment
asserting a property needs a test asserting the same property; here the comment
asserts a property the code does not have and no test looks.

### F-4.9-J-09 (minor) A stale comment claims the flag button lives inside the summary

File: `frontend/src/components/screens/AnswerScreen.tsx:612-614`

```js
// It lives inside the summary, as it does in the
// prototype, so without this a flag click also opens or
// closes the card under the user's cursor.
event.preventDefault();
event.stopPropagation();
```

It does not live inside the summary. The summary closes at `:596` and this
button opens at `:606`, which is the whole point of F-4.9-D-13, explained
correctly in the comment 8 lines above at `:598-605`. Two adjacent comments now
contradict each other about a placement that is a WCAG finding, and the next
reader has no way to know which is current without re-deriving the JSX nesting.

### F-4.9-J-10 (minor) The follow-up heading is a paragraph, not the prototype's label

File: `frontend/src/components/answer/FollowUp.tsx:49-62`, input at `:81`

The prototype is `<label for="fubox">Continue this conversation</label>`
(`app.html:544`). What shipped is a `<p>` with no `htmlFor`, while the input
keeps `aria-label="Ask a follow-up question"`. The visible heading and the
accessible name are now two different strings, and the visible one is
programmatically attached to nothing. The comment at `:44-48` quotes the
prototype's `<label for>` line while shipping a `<p>`.

### F-4.9-J-11 (minor) `testTimeout` was raised project-wide to accommodate one file

File: `frontend/vite.config.ts:20-43`

The direction is defensible and the reasoning recorded is honest: the leak was
found first and fixed, and the residual contention was measured at three
failures in five runs before the change. I measured the heaviest new test at
7.6s, so 5s is genuinely too tight for it.

The objection is scope. A hang detector was loosened 3x for all 147 tests to
accommodate roughly eight of them. `goal-contracts` permits adding checks and
not weakening them, and a per-file or per-test `timeout` on the new App-level
SSE tests would have bought the same headroom without lowering the bar
everywhere else. Filed so the choice is arguable rather than settled by
default.

### F-4.9-J-12 (minor) The trust pills drop two prototype specifics, and a comment asserts one of them is present

Files: `frontend/src/hooks/useRunView.ts:411`, `:415`; comment at
`frontend/src/components/screens/AnswerScreen.tsx:722-732`

Rendered:

```
trust-good  "Grounded · every claim cited"
trust-risk  "high risk claim"
trust-plain "3 layers agreed"
```

The prototype (`app.html:838`) is:

```js
verdict:[['good','✓ Grounded · every claim cited'],['high','High-risk claim · gene to disease'],['plain','3 layers agreed']]
```

Two gaps, neither declared. The good pill has no `✓`, while the comment at
`AnswerScreen.tsx:727-729` justifies its colour choice by saying "the border,
the wash and the check mark keep carrying the green" — there is no check mark
in the code. And the risk pill reads `high risk claim`, interpolated lowercase
from the raw `risk_tier`, where the prototype reads `High-risk claim`. The
reason half (`· gene to disease`) is correctly declared out of scope; the
casing and the check mark are not, and both are pure string edits with no
backend dependency.

### F-4.9-J-13 (minor) The board's description of this phase contradicts the phase file's own scope

File: `tracker/BOARD.md:62`

The board describes the 4.9 deliverable as nine gaps including "the layer and
entity named in words, the SNAPSHOT date". `tracker/phase_4.9.md:89-95`
declares both the SNAPSHOT date and the entity name explicitly out of scope and
assigns them to build phase 6.0g. The row also lists `F-4.8-D-03 snapshot date
missing from a source card` in its findings column with no carried-open marker.

A reader of the board would close this phase believing D-03 and half of D-02
shipped. The same row's evidence column asserts `playwright 29`, which
F-4.9-J-03 shows is not reliably true.

### F-4.9-J-14 (minor) The account menu's "Recent searches" section is omitted, and only the source file says so

File: `frontend/src/components/shell/AccountMenu.tsx:14-17`

The prototype's `renderAcctMenu()` (`app.html:1549-1561`) has four blocks:
header, "Recent searches" with up to five items or an empty state, "Account",
then the three action rows. The shipped menu has three; the recent-searches
section is gone.

The omission is reasoned in the component docstring (the rail beside it shows
the same list) and I do not dispute the reasoning. It is not in
`tracker/phase_4.9.md`'s "What is deliberately not in this phase" table, which
is the table that exists so an omission is arguable rather than discovered. I
discovered it by diffing the prototype, which is what that table is meant to
prevent.

---

## Count by severity

| Severity | Count | Ids |
|----------|-------|-----|
| Critical | 0 | |
| Major | 3 | F-4.9-J-01, F-4.9-J-02, F-4.9-J-03 |
| Moderate | 3 | F-4.9-J-04, F-4.9-J-05, F-4.9-J-06 |
| Minor | 8 | F-4.9-J-07 through F-4.9-J-14 |

## Reproduction commands

Every mutation was applied to a clean tree, run, then reverted with
`git checkout -- <file>`. The `frontend/src` sweep the tracker warns about was
never used.

```bash
# F-4.9-J-01: delete AnswerScreen.tsx:519-533 (the count badge <Box>)
cd frontend && npx vitest run src/phase49Premise.test.tsx      # 13 passed

# F-4.9-J-02 mutation A: AnswerScreen.tsx:594
#   L{source.layer} · {LAYER_WORD[source.layer] ?? "source"}
# → L{source.n}     · {LAYER_WORD[source.n]     ?? "source"}
cd frontend && npx vitest run src/phase49Premise.test.tsx      # 13 passed

# F-4.9-J-02 mutation B: useRunView.ts:523-527, alias the three counts
cd frontend && npx vitest run src/phase49Premise.test.tsx      # 13 passed

# Control, proving the harness works: AnswerScreen.tsx:220-223,
# make toggleSource open every card at once
cd frontend && npx vitest run src/phase49Premise.test.tsx      # 1 failed, 12 passed

# F-4.9-J-03
cd frontend && npx playwright test e2e/accessibility.spec.ts \
  e2e/query-stream-and-stop.spec.ts e2e/rail-collapse.spec.ts \
  e2e/trust-surface.spec.ts --workers=1
# develop: 29, 29. branch: 28, 28, 29.
```

Note for whoever reruns this: `frontend/e2e/__ds_audit.spec.ts` is untracked in
the working tree and takes about five minutes. Every count above was taken by
naming the four tracked specs explicitly.

## What would turn this to PASS

1. Make the count assertion in clause 6 read the badge, not the disclosure's
   whole text.
2. Rebuild `STREAM` so citation index, layer and card position disagree, and
   so the tool, layer and source counts are three different numbers. Then
   re-run the lead's sixteen mutations, because several of them were graded
   against a fixture that could not see them. Add the collinearity statement to
   the coverage block.
3. Land the run before the rail geometry tests measure, or make the run
   screen's height stable, and get three consecutive green serial Playwright
   runs before claiming 29.
4. Either ship `L3 · trials`, the `traceN` counter and the work panel's tool
   chips, or put all three in the omissions table with a named reason.
