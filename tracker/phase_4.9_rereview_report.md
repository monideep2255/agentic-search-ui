# Build phase 4.9 independent re-review of the fix round

Branch: `phase/4.9-answer-screen-fidelity`
Commit under review: `f72dc88`, "fix(web-ui): close the four adversary criticals and the two gate defects"
Reviewed: 2026-08-14, fresh context, own worktree, no inherited assumptions from the lead, the judge or the adversary
Scope: the FIX ROUND itself, per this repository's own measurement that the worst defect in a round is usually a regression in the previous round's fix

## Verdict

FAIL.

The four criticals are genuinely closed in their headline form, and I re-derived
each one against the code and against the running app rather than against the
commit message. What fails the round is what the fixes did on their way past the
findings they named.

Three of the five majors below are new: a message regression that tells a user
who pressed Stop that their run failed and to try again, a status strip that now
counts its three numbers off two different sources and contradicts itself on
screen, and the "0 layers agreed" nonsense the round was supposed to remove,
which was moved rather than removed. The fourth is a gate that cannot see two of
the three harms its own critical named, proven by two mutations that left it 18
of 18 green against two controls that turned it red. The fifth is that
`tracker/phase_4.9.md` and `tracker/BOARD.md` still say this phase is "not yet
judged or adversarially reviewed" with a "13 of 13" gate and "vitest 147", inside
the same commit that raised CLAUDE.md to 152, and record a disposition for none
of the roughly 29 findings this round did not fix.

## Where the code actually is

Note for whoever reads the commit next: `f72dc88` itself changes four
documentation files and one line of a tracker report. Every code change this
review is about landed in `de8fe0d`, "wip: adversary and judge fix round,
pre-mutation checkpoint". I reviewed the full range `e1c5f34..f72dc88`.

## What I verified as correct

Stated because a FAIL that does not say what held is not a useful report. Each
row was re-derived, not taken from a report.

| Claim | How I checked it | Result |
|-------|------------------|--------|
| vitest 152 | `npx vitest run` in a clean `npm ci` tree | 11 files, 152 passed |
| Typecheck, production build | `npx tsc --noEmit`, `npm run build` | Exit 0, 934 modules, built |
| Playwright 29, and the F-4.9-J-03 flake is gone | `npx playwright test --workers=1`, twice, real FastAPI backend and real Vite | 29 passed, 29 passed. I did not reproduce the judge's 28-of-29 in either run |
| F-4.9-A-01, the cost figure | Scripted the adversary's own frames through the real `App` and read the rendered notice | `answer-failure` reads "This run could not be completed...". No `$0.0`, no "synth tier". Pre-fix, the same stream rendered "synth tier failed after $0.019 of $0.02 spent on run r-99" verbatim |
| F-4.9-A-01, the trust floor | Same stream, pills dumped from the DOM | Post-fix: one pill, `trust-risk` "Not verified · the run did not finish". Pre-fix: `trust-good` "Grounded · every claim cited", `trust-risk` "high risk claim", `trust-plain` "1 layer agreed" |
| `error_class` is a closed enum with no free text | `contracts/events.py:217` (`Literal[...]`) AND `frontend/src/lib/events.ts:362-363`, which independently allowlists the same four values before a frame is accepted | Confirmed at both boundaries. The interpolation is safe |
| F-4.9-A-04, the chip's `data-layer` | Gate clause at `phase49Premise.test.tsx:514-515`, plus reading `AnswerScreen.tsx:467` | Correct: each chip carries its own source's layer |
| `sourceByIndex.get(n)` cannot miss on any App path | `useRunView.ts:252-285`: `citationById` holds exactly one entry per usable `display_index`, and both `claims[].citations` and `sources` are built from that one map | Confirmed. The `?? claim.layer` fallback is unreachable from `App`; it can only fire in a direct `<AnswerScreen>` render such as `phase48Premise.test.tsx` |
| F-4.9-J-01, the count badge | `phase49Premise.test.tsx:317` asserts `getByTestId("sources-count")` with `/^3$/` against `AnswerScreen.tsx:552` | Real fix. Deleting the badge now throws in `getByTestId`, by construction |
| The fixture's count axes | Arithmetic against `STREAM`, plus mutation M4 below | 4 tool calls, 2 cited layers, 3 sources; citation index never equals layer; card position never equals layer; two cards share layer 3. All four hold |
| The new outcome colours pass contrast | `designTokens.risk` `#981B1E` and `warn` `#7A5900` on the panel's white, plus the existing axe sweep in `e2e/accessibility.spec.ts` | Clean |

## How I tested

Two instruments, both against the code rather than the reports.

- A scripted-stream probe rendering the real `App` through the real
  `parseAgentEvent`, `useAgentRun` and `useRunView`, dumping the status strip,
  every `trust-*` pill, and every notice. Ten streams. Run identically at
  `f72dc88` and at `e1c5f34` (the pre-fix commit) so every "this regressed" claim
  below is a measured before-and-after, not an inference.
- A mutation battery against `src/phase49Premise.test.tsx`, one mutation per
  fixed behaviour, each reverted with `git checkout --` before the next. Two
  controls (M4, M5) turned the gate red, which is what makes the green ones
  evidence rather than noise.

## Count by severity

| Severity | Count | Ids |
|----------|-------|-----|
| Critical | 0 | |
| Major | 5 | F-4.9-R-01 through F-4.9-R-05 |
| Moderate | 4 | F-4.9-R-06 through F-4.9-R-09 |
| Minor | 5 | F-4.9-R-10 through F-4.9-R-14 |

---

## Major

### F-4.9-R-01 (major): "0 layers agreed" is still reachable. The fix moved the nonsense rather than removing it

Files: `frontend/src/hooks/useRunView.ts:577-578`, `:580-584`

F-4.9-A-05 was filed because the triangulation pill printed "0 layers agreed",
which the adversary correctly called "not a degraded message, a nonsense one".
The fix re-keys `layerCount` from the tool calls to the sources and the commit
says the two "agree by construction" now. They agree. The nonsense survives.

Measured, same stream at both commits. A run that queries three layers, finds
nothing citable in any of them, and still reports `triangulated: true`:

```
guard, tool_result x3 (layer_1_graph, layer_2_api, layer_3_enrichment, all result_count 0)
token   {text:"BRCA1 repairs DNA. ", marker_ids:[]}
trust_signal {outcome:"answer", risk_tier:"low", grounded:true, triangulated:true}
done    {..., trust_outcome:"answer"}
```

| | strip | pills |
|--|-------|-------|
| `e1c5f34` (pre-fix) | `✓ Answered 5.0s · 3 tools · 3 layers · 0 sources` | `Grounded · every claim cited` \| `3 layers agreed` |
| `f72dc88` (post-fix) | `✓ Answered 5.0s · 3 tools · 0 layers · 0 sources` | `Grounded · every claim cited` \| `0 layers agreed` |

Before the fix this run over-claimed. After the fix it prints the exact string
the finding was filed about, and adds "0 layers" to the strip beside "3 tools".
The class of run that produces it is not exotic: it is any run whose citations
do not arrive, which is the same class F-4.9-A-02 already exists for.

The commit's own reasoning ("the tools a run ran and found nothing in are still
visible in the reasoning log") is a defensible product argument for the strip. It
is not an argument for the pill, whose entire job is to state a count, and which
now states zero.

How I verified: the probe above, run at both commits, output compared line by
line.

### F-4.9-R-02 (major): the status strip now counts its three numbers off two different sources, and contradicts itself on one line

Files: `frontend/src/hooks/useRunView.ts:585-589`, gate at
`frontend/src/phase49Premise.test.tsx:217-224`

`meta` is built from `toolCalls.length`, then `layersUsed.size`, then
`sources.length`. After this round, `toolCalls` still comes from `tool_start` and
`tool_result` events while `layersUsed` comes from the citations. The three
numbers on one line no longer describe one thing.

The gate's own fixture is the clearest demonstration. Four tool calls spanning
three layers, citations in two, and clause 2 now asserts the rendered result:

```
✓ Answered  11.4s · 4 tools · 2 layers · 3 sources
```

A reader parses that as "four tools across two layers". The run used four tools
across three. The probe in F-4.9-R-01 gives the degenerate form of the same
sentence, `3 tools · 0 layers`, which is not merely imprecise: a tool call
carries a layer on the wire, so three tools cannot have touched zero layers.

F-4.9-A-06 asked for the strip and the source cards to stop contradicting each
other. This makes the strip agree with the cards by making it disagree with the
word immediately to its left. The honest forms are either two numbers with two
labels ("4 tools · 3 layers queried · 2 layers cited") or dropping one, and both
are product calls. What is not defensible is that the phase's own verify surface
now pins the incoherent pair as the expected output, so nothing will report it
again.

How I verified: read `useRunView.ts:585-589`; ran the gate and the probe; counted
the fixture's tool layers ({1,2,3}) against its cited layers ({1,3}).

### F-4.9-R-03 (major): a cancelled run now tells the user it failed and to try again

Files: `frontend/src/App.tsx:327`, `frontend/src/hooks/useAgentRun.ts:364`

The two halves of the F-4.9-A-01 fix compose into a message regression on the
cancellation path. `useAgentRun` no longer surfaces the backend's text, and `App`
now puts the curated `view.failure` ahead of `streamError`. `view.failure`
(`useRunView.ts:603-605`) is one fixed string for every fatal class, so the
`cancelled` class loses the only message it had.

Measured, the exact terminal event `core/run_registry.py:277` emits for a
stopped or abandonment-cancelled run:

```
error {fatal:true, scope:"run", source:"run_registry", error_class:"cancelled",
       message:"this run was stopped before it finished", retry_after_s:0}
```

| | `answer-failure` |
|--|------------------|
| `e1c5f34` | "this run was stopped before it finished" |
| `f72dc88` | "This run could not be completed. Try asking again, or rephrase the question." |

The user stopped the run. The app now tells them it broke and invites them to
re-spend the cost. The backend added that event at build phase 4.0 (F-4.0-A-04)
"precisely so a cancellation is legible", and the UI has now made it illegible
again, one layer up from where F-4.9-A-08 says it is unreachable today.

Reachability: F-4.9-A-08 is right that pressing Stop aborts the stream before the
event arrives, so the single-tab Stop path does not hit this. The event is still
delivered to any consumer that did not abort, which build phase 4.0's
multi-consumer resumable SSE (`Last-Event-ID`) makes a shipped capability, and
to any abandonment-cancelled run whose watcher reconnects. It is also the message
the UI will show the moment F-4.9-A-08 is fixed, which is the more likely way
this lands in front of a user.

The narrow fix is to branch `failure` on `error_class === "cancelled"`, which is
exactly what the comment at `useAgentRun.ts:355-363` says the enum was kept for.
Nothing branches on it (see F-4.9-R-13).

How I verified: ran the identical probe stream at both commits and compared the
rendered `answer-failure` text.

### F-4.9-R-04 (major): the gate cannot see the two harms F-4.9-A-04 actually named

Files: `frontend/src/phase49Premise.test.tsx:505-516`, against
`frontend/src/components/screens/AnswerScreen.tsx:449-455` and `:481-482`

F-4.9-A-04 named three harms, in the adversary's own order of severity: the
chip's rendered background and left border painted in the wrong layer colour
(measured from the live DOM, `rgb(231,238,246)` and `rgb(32,84,147)` on a Layer 3
source), the screen-reader text asserting "Source 1 and 2, layer 1" over a
PubTator annotation, which the adversary called "worse, because it states the
wrong thing", and the `data-layer` attribute.

The new clause asserts the third only. Two mutations, each reverting one of the
first two while leaving `data-layer` correct:

```
M2  AnswerScreen.tsx:481-482, borderLeft and bgcolor keyed off claim.layer again
    npx vitest run src/phase49Premise.test.tsx    ->  Tests  18 passed (18)

M3  AnswerScreen.tsx:452-454, screen-reader text back to
    `Source ${claim.citations.join(" and ")}, layer ${claim.layer}.`
    npx vitest run src/phase49Premise.test.tsx    ->  Tests  18 passed (18)
```

Under M2 the exact rendering the adversary measured returns in full, chip 2 of a
graph-plus-literature claim painted navy while its own card reads "L3 ·
literature", and the clause named for that finding stays green. Under M3 a
text-mined co-mention is announced to a screen reader as a curated graph
assertion, and the same clause stays green.

Controls, proving the harness works:

```
M4  useRunView.ts:577, layer count back to the tool calls  ->  2 failed | 16 passed
M5  useRunView.ts:411, reword the no-trust-signal pill     ->  1 failed | 17 passed
```

This is the eleventh assertion-shaped hole found in this territory, and it is the
same shape as F-4.9-J-02: the clause tests the attribute the fix happened to
touch first rather than the behaviour the finding described.

How I verified: the four mutations above, applied to a clean tree and reverted
with `git checkout --` between each.

### F-4.9-R-05 (major): the tracker asserts a state that is false, and records a disposition for none of the unfixed findings

Files: `tracker/phase_4.9.md:6`, `:28-38`; `tracker/BOARD.md:62`

As committed at `f72dc88`:

- `tracker/phase_4.9.md:6` reads "Status: BUILD COMPLETE, in review. Gate 13 of
  13 green, 16 mutations all red. Not yet judged or adversarially reviewed."
  Both review reports are in the same tree, in the same commit range.
- The "What shipped" table reads gate 13 of 13, 16 mutations, vitest 147,
  Playwright 29. The gate is 18 clauses (I ran it), the commit message itself
  claims 10 mutations, and vitest is 152.
- `CLAUDE.md` and `AGENTS.md` were raised to 152 tests and 29 Playwright cases in
  this very commit, so one commit now states two different test counts.
- `tracker/BOARD.md:62`'s evidence column still reads "gate 13 of 13, 16
  mutations all red, vitest 147, playwright 29".
- Roughly 29 of the 33 filed findings (19 adversary, 14 judge) were not fixed this
  round. Not one of them appears in `tracker/phase_4.9.md`, in BOARD.md's flags
  table, or in the "What is deliberately not in this phase" table. Nothing is
  silently marked CLOSED, which is the one thing this could have got worse; the
  defect is that nothing is marked at all, so every one of them is discovered
  rather than arguable, which is the exact failure `goal-contracts` and
  F-4.9-J-14 both name.
- `python3 tracker/check_doc_drift.py --check` returns "ok: 6 facts computed (4
  skipped) | 0 stale | 0 structural", so the drift checker is green while the
  phase file and CLAUDE.md disagree about the same number. The checker does not
  cover `tracker/phase_N.M.md`.

How I verified: `git show f72dc88:tracker/phase_4.9.md`, `git show
f72dc88:tracker/BOARD.md`, `git show --stat f72dc88`, and running the drift
checker and the gate myself.

---

## Moderate

### F-4.9-R-06 (moderate): the F-4.9-A-02 guarantee does not hold on the path the existing e2e suite actually takes

File: `frontend/src/hooks/useRunView.ts:408`

The new branch is `else if (trustEvents.length === 0 && landed)`. `landed`
requires a `done` or a fatal `error` event. `App.tsx:184` also navigates to the
answer screen on `status === "error"`, which is set by any transport or
frame-validation failure, and on that path `landed` is false.

Measured. A stream carrying a token and then a `done` frame the validator
rejects:

```
(no status strip at all)
BRCA1 repairs DNA.        <- uncited, no chip, no pill of any kind
answer-failure: "event.payload does not match the "done" payload schema"
```

No `trust-risk`. No "Not verified". An uncited biomedical assertion on screen
with no grounding signal, which is F-4.9-A-02's own description of the defect.

This is not a contrived path. The adversary already recorded that
`e2e/trust-surface.spec.ts`'s `done` frame omits `total_cost_usd` and
`total_tool_calls` and adds `status` and `truncated`, so it is rejected and that
whole suite reaches the answer screen exactly this way. The suite named "the
trust surface" runs against a screen state no real run produces, and that is
still true after this round.

Secondary, in the same rendering: the failure notice shown to the user is the
frontend's own parser string, "event.payload does not match the "done" payload
schema". It is not backend text, so it is outside F-4.9-A-01's letter, but it is
the same class of internal detail reaching a user that the round spent its
largest fix removing.

How I verified: the probe above (stream ends with a schema-invalid `done` frame),
rendered through the real `App`.

### F-4.9-R-07 (moderate): the success tick can be deleted outright and the gate stays green

Files: `frontend/src/components/screens/AnswerScreen.tsx:344`, gate at
`frontend/src/phase49Premise.test.tsx:490-503`

The A-03 clause asserts a refusal has no `✓`. Nothing anywhere asserts that an
answer has one.

```
M1  AnswerScreen.tsx:344, `{outcomeTone === "risk" ? "⚠" : ...} {outcome}` -> `{outcome}`
    npx vitest run src/phase49Premise.test.tsx    ->  Tests  18 passed (18)
```

So the gate proves half of the fix: the glyph does not lie on a refusal. It
cannot tell that from the glyph having been removed for every outcome, which is
the cheapest possible way to satisfy the clause and would delete a specific the
prototype names (`app.html:530`, `<span class="ok">&#10003; Answered</span>`).
A clause that a deletion satisfies is the same shape as F-4.9-J-01, one round
later.

How I verified: mutation M1, controls M4/M5 red.

### F-4.9-R-08 (moderate): F-4.9-A-01's third defect is untouched and undeclared, while the finding is presented as closed

Files: `frontend/src/hooks/useRunView.ts:548-561`, `:585-589`

F-4.9-A-01's closing paragraph reads: "Note also that the status strip drops the
outcome word but keeps the counts, so a crashed run advertises '1 tool · 1 layer
· 1 source' exactly as a successful one does."

Measured at `f72dc88`, a run that died mid-answer:

```
strip:  1 tool · 1 layer · 1 source
```

Identical to the pre-fix rendering. `outcome` and `outcomeTone` are both null on
a fatal run by design, `elapsedMs` is null because there is no `done`, and `meta`
is still built because `landed` is true, so the line reads as a normal completed
run with the verdict clipped off. Whether to state "Stopped" there, or to drop
the counts, is a product call and I am not arguing for either. The defect is that
the commit message presents A-01 as closed with two named defects and this third
one is neither fixed nor recorded anywhere. The prototype has a shape for it,
`app.html:1219`, `'stopped by you · N steps completed'`.

How I verified: probes P4 and P6 at both commits; read `useRunView.ts:548-561`.

### F-4.9-R-09 (moderate): the new pill now fires on refusals and ask-backs, where nothing was ever verified

File: `frontend/src/hooks/useRunView.ts:408-412`

The A-02 branch fires on any landed run with no `trust_signal`, which includes
every guard-stopped refusal and every ask-back, since those terminate before
`write_node` emits one.

| stream | `e1c5f34` | `f72dc88` |
|--------|-----------|-----------|
| guard fail + `done{refuse}` | no pill | `trust-risk` "Not verified · no grounding check was recorded" |
| `done{ask}` | no pill | `trust-risk` "Not verified · no grounding check was recorded" |

A guard-stopped run never attempted an answer, so "no grounding check was
recorded" describes something that correctly did not happen, presented in the
risk colour beside an already-red "⚠ Refused". The direction is safe, which is
why this is moderate rather than major, but it is a new user-visible artifact of
the fix on the two outcomes the same round was separately making more honest, and
the gate cannot see it: the A-02 clause uses a PASSING guard with a citation, so
the refusal and ask-back shapes are unexercised.

Worth pairing with the backend reading, since it changes who this fires for:
`core/graph.py:4141-4157` and `:3880-3891` show a refusal DOES emit a
`trust_signal`, so a real write-stage refusal takes the third branch and reads
"Not fully grounded" instead. It is the guard-stopped and ask-back shapes,
exactly the two above, that reach the new branch.

How I verified: probes P1 and P2 at both commits; read the two backend emission
sites.

---

## Minor

### F-4.9-R-10 (minor): the e2e helper's own docstring now contradicts the line added directly beneath it

File: `frontend/e2e/rail-collapse.spec.ts:36-42` against `:65-81`

The helper's docstring still reads "The run does not need to complete: the rail
is populated at ask time, and this file is about the rail rather than the answer.
Waiting for the run heading is what proves we left the landing screen." Eighteen
lines later the fix adds a wait for `answer-meta`, which exists only once the run
HAS completed.

Two adjacent comments now contradict each other about the helper's own contract.
This is F-4.9-J-09's exact shape, filed against this branch the same day,
reintroduced by the round that was reading that report.

Second-order, worth deciding rather than inheriting: every geometry clause in
this file now measures the ANSWER screen where it previously measured the run
screen, and every one now depends on a full agent run terminating within 30
seconds. A slow or failing run will now fail a layout test, which is a new
coupling the file's docstring explicitly disclaims.

How I verified: read the file; ran the suite twice at `--workers=1`, 29 passed
both times.

### F-4.9-R-11 (minor): the rebuilt fixture is still collinear on two axes its coverage statement does not name

File: `frontend/src/phase49Premise.test.tsx:92-112` (the docstring), `:113-149`

The new docstring names four distinctions and closes the two the judge exploited.
Two aliases remain, and the statement does not mention them, which is the same
`goal-contracts` gap F-4.9-J-02 was filed for.

- `display_index` still equals card position. The indexes are 1, 2, 3 and
  `sources` is sorted by `n`, so position and index are the same number on every
  card.

  ```
  M6  AnswerScreen.tsx:568-616, card number and data-testid keyed off the ARRAY
      POSITION instead of source.n
      npx vitest run src/phase49Premise.test.tsx  ->  Tests  18 passed (18)
  ```

  Given F-4.8-A-25 and F-4.8-A-18 (display_index of 0, -3, and duplicates) this
  is the axis with the most history behind it.
- Layer is still derivable from two other fields. Both Layer 3 sources are
  `PubMed` with `field: pubtator_annotate`, and the Layer 1 source is `NCBI Gene`
  with `field: cypher_query`, so a layer word keyed off the source NAME or off
  the tool passes. The judge's mutation A is closed only because it also re-keyed
  the `L{n}` number.

How I verified: mutation M6, plus reading the fixture's three `CIT(...)` calls.

### F-4.9-R-12 (minor): the "?" glyph appears nowhere in the prototype, and the whole A-03 fix is an undeclared divergence from it

File: `frontend/src/components/screens/AnswerScreen.tsx:344`

Two things, both undeclared against a phase whose premise is "with the specifics
the prototype names rather than summaries of them".

- The prototype's `.summary` markup is static: `<span class="ok">&#10003;
  Answered</span>` at `app.html:530`, never rewritten by `finish()`. On its own
  refusal path (`app.html:1085-1088`) it leaves "✓ Answered" showing and puts the
  honesty in the verdict pill, `⚠ Refused · out of scope`. So the app is now MORE
  honest than its source of truth, which I think is right, and it is a divergence
  that belongs in the omissions table beside F-4.9-D-13 and F-4.9-D-14 rather
  than in a code comment.
- The `?` glyph for the ask outcome is invented. The prototype's vocabulary is
  `&#10003;` and `&#9888;` only; `&#9888;` (⚠) covers both of its non-success
  states, including "No answer written". A bare question mark is also read aloud
  as "question mark" by a screen reader, which the two existing glyphs at least
  earn.

How I verified: grepped `docs/build/design/design-system/prototype/app.html` for
every glyph in `.summary` and `.verdict`; read `AnswerScreen.tsx:330-346`.

### F-4.9-R-13 (minor): `error_class` is kept for a branch that does not exist, and the message it forms is less actionable than the one it replaced

File: `frontend/src/hooks/useAgentRun.ts:355-364`

The comment states: "The error_class is kept, because it is a closed enum the UI
may branch on, and it carries no free text." The enum claim is true and I
verified it at both boundaries. Nothing branches on it. `run failed
(${error_class})` is now the LAST term in `App.tsx:327`'s chain, so on the fatal
path, which is the only path that sets it, it is unreachable: `view.failure` is
always non-null there. It survives only as the transient string the run screen
shows in the tick before navigation.

`production-standards`' retry-safety gate wants an error to say what to do next.
"run failed (unexpected)" says less than the string it replaced did, and less
than the curated string that now wins. If the enum is genuinely being kept for a
future branch, F-4.9-R-03 is the branch, and writing it would make both of these
true at once.

How I verified: read the chain in `App.tsx:327`, `useRunView.ts:603-605`, and
`useAgentRun.ts:346-370`; confirmed the enum at `contracts/events.py:217` and
`lib/events.ts:362-363`.

### F-4.9-R-14 (minor): no decision and no learning was logged for a round that changed a number's meaning

Files: `DECISIONS.md`, `LEARNINGS.md`

`DECISIONS.md`'s last entry is the 2026-08-14 orphaned-modules deletion.
`LEARNINGS.md`'s last row is 97, the guard-copy and stream-leak pair from the
build round.

Three choices in this round meet `decision-logging`'s "reverting later would cost
real work" bar and none is recorded: counting the strip's layers from the
citations rather than the tool calls (F-4.9-R-01, F-4.9-R-02), placing `flag` in
the success tone so a cap-truncated answer keeps a green tick, and ordering the
curated failure string ahead of the stream error (F-4.9-R-03). The first of those
changed what a number on the primary screen MEANS, which is the kind of thing the
next reader will otherwise re-derive from a code comment.

How I verified: tailed both files at `f72dc88`.

---

## What the round did not fix, checked for honesty rather than for correctness

Instruction 4 asked whether any unfixed finding is silently closed or
contradicted. It is not. I sampled the shapes most at risk of being quietly
"handled" and confirmed each still behaves exactly as filed:

| Finding | Still reproduces | Evidence |
|---------|------------------|----------|
| F-4.9-A-10, a cap-truncated answer reads "✓ Answered" | Yes, and it is now a deliberate coded mapping | `OUTCOME_TONE.flag = "good"`, `useRunView.ts:543`. Probe: `✓ Answered 11.4s · 1 tool · 1 layer · 1 source` over the cap notice |
| F-4.9-A-14, a duplicate `display_index` leaves a live `[1]` in the prose | Yes, unchanged | Probe: `"Claim two [1]. This sentence has no source."` at both commits |
| F-4.9-A-08, a stopped run gives no terminal signal | Yes, unchanged | `App.tsx:184`'s nav effect and `useAgentRun.ts:391` are untouched |
| F-4.9-A-07, failed tool calls counted as work | Yes, unchanged | `payload.status` is still read nowhere in `useRunView.ts` |
| F-4.9-J-04, `L3 · trials` | Yes, unchanged | `AnswerScreen.tsx:229`, three entries |
| F-4.9-J-08, the account initials comment | Yes, unchanged | `AccountMenu.tsx:33-36` |
| F-4.9-J-09, the stale flag-button comment | Yes, unchanged | `AnswerScreen.tsx:612-614` |

The problem is not that any of these was closed dishonestly. It is that none of
them, nor the roughly 22 others, is written down anywhere as carried, which is
F-4.9-R-05.

## Reproduction

Every mutation was applied to a clean tree and reverted with `git checkout --`
before the next. The probe file and the mutation script were kept untracked in a
private worktree and are not on the branch.

```bash
# Baselines, in a fresh `npm ci` tree at f72dc88
cd frontend
npx vitest run                    # 152 passed
npx tsc --noEmit                  # clean
npm run build                     # built
npx playwright test --workers=1   # 29 passed (run twice, 29 both times)

# The gate's blind spots (all four stay 18 of 18 green)
# M1  AnswerScreen.tsx:344      drop the outcome glyph for every outcome
# M2  AnswerScreen.tsx:481-482  chip borderLeft + bgcolor back to claim.layer
# M3  AnswerScreen.tsx:452-454  screen-reader text back to one layer for the list
# M6  AnswerScreen.tsx:568-616  card number and testid keyed off array position
npx vitest run src/phase49Premise.test.tsx

# Controls, proving the harness works
# M4  useRunView.ts:577    layersUsed back to toolCalls    -> 2 failed | 16 passed
# M5  useRunView.ts:411    reword the no-trust-signal pill -> 1 failed | 17 passed

# The before-and-after probes: ten scripted streams rendered through the real
# App, run once at e1c5f34 and once at f72dc88, output diffed.
```

## What would turn this to PASS

1. Decide what the strip's middle number means and make the pill agree with it.
   Either count layers queried (and let the pill count cited layers, labelled as
   such) or count layers cited (and relabel or drop the tool count). Either way,
   "0 layers agreed" must be unreachable, and the gate must assert against a
   fixture where tool layers and cited layers differ, which the current one
   already provides.
2. Branch `failure` on `error_class === "cancelled"` so a stopped run is told it
   was stopped, and pin it with a clause.
3. Add two clauses to the A-04 test: the chip's rendered `borderLeft` colour, and
   the claim's visually-hidden text naming each source's own layer. Re-run M2 and
   M3 and confirm both go red.
4. Add one clause asserting an ANSWER carries the success glyph, so M1 goes red.
5. Bring `tracker/phase_4.9.md` and `tracker/BOARD.md:62` to the real state (18
   clauses, 10 mutations, vitest 152, judged and adversarially reviewed), and give
   every unfixed finding a row with a named owner or a named reason. Consider
   teaching `check_doc_drift.py` the phase file's own counts, since it reported
   clean across a two-count contradiction inside one commit.
6. Either close F-4.9-R-06 by dropping the `&& landed` guard on the no-trust
   branch, or state in the gate's coverage block that the `status === "error"`
   navigation path is not covered.
