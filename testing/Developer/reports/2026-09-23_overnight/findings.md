
## Worker A: existing test file left broken by the shipped fix

`tests/system_03_search_agent/adapters/web_sse/test_mcp_mount_redirect_scheme.py`
predates `proxy_scheme.py` and encodes the REJECTED alternative as fact: its
docstring and two of its three tests assert that the scheme downgrade is a
"deployment-configuration fact, not something app.py can fix by itself" and
that nothing in `app.py` reads `x-forwarded-proto`. That premise is now false.
Ran it against the current tree (`venv/bin/python -m pytest
tests/system_03_search_agent/adapters/web_sse/test_mcp_mount_redirect_scheme.py -q`,
exit code 1):

```
FAILED test_untrusted_proxy_address_downgrades_the_redirect_scheme
FAILED test_app_py_does_not_read_x_forwarded_proto_itself
2 failed, 1 passed
```

`test_untrusted_proxy_address_downgrades_the_redirect_scheme` expects the
`Location` header to stay `http://` when uvicorn's own `ProxyHeadersMiddleware`
does not trust the caller. It now reads `https://`, because
`ProxySchemeMiddleware` (added by this same fix) reads `x-forwarded-proto`
itself regardless of uvicorn's proxy-trust configuration, which is the whole
point of the fix. `test_app_py_does_not_read_x_forwarded_proto_itself` fails
because `inspect.getsource` on `app.py` now picks up the docstring comment
above `app.add_middleware(ProxySchemeMiddleware)`, which mentions
`x-forwarded-proto` in prose while explaining the new design; the assertion
was written to catch a literal in-code header read, not a comment naming the
header, so it is a false positive on its own populate check as much as a
premise conflict.

This is not a defect in `proxy_scheme.py` or `app.py`: the new fix is
correct and this is the file that needs updating to match the decision it
now contradicts. I do not own this file under tonight's contract (worker A
owns only the new `test_proxy_scheme.py` and one Debugging_guide.md row), so
I have not edited it. Recorded as a blocked-stop item for the planner: this
file should be retired or rewritten in the same change that ships the fix,
or CI will show two new test failures tomorrow that have nothing to do with
tonight's actual defect.

## Worker B1: the finished answer is not a text stream, and joining token text loses the table

Established 2026-09-22 from a real run, not from an event name. Source:
`testing/Developer/reports/2026-09-22_isolate_search/round2/tokens_G-035.json`,
31 real `token` events from question G-035 on develop.

What carries the finished answer, measured:

- The answer text is the `token` events, in `seq` order. There is no single
  event holding the whole answer.
- The citations are the `citation` events, and those are ALREADY STORED: the
  `interactions` table's `citations` column holds the full `CitationPayload`
  dicts (`feedback/capture.py:220`, capped at 50). The citation half of the
  wire contract needs no new column at all.
- `run_consistency.py:208`, the 150-run measurement harness, flattens the
  answer as `"".join(p["text"] for p in token payloads)`. That is the obvious
  reading of `answer_markdown` and IT IS NOT FAITHFUL.

Why it is not faithful, measured on G-035:

- A `table_header` token has `text: ""` and its entire visible content in
  `cells: ["Isolate", "AMR genes"]`. A text join contributes nothing for it.
- A `table_row` token's visible content is `cells: ["C236-11", "acrF,
  aph(3'')-Ib, blaCTX-M-15, ..."]`, while its `text` is the grounded sentence
  `"Pathogen Detection isolate name: C236-11 [1]. "`. A text join therefore
  yields twenty repetitive sentences where the person saw a twenty-row table,
  and every AMR gene on screen is gone.

So the answer IS faithfully reconstructable from the events, but only from
the TYPED tokens (`kind`, `cells`, `emphasis`, `marker_ids`), never from
`text` alone. This is not a blocked stop. It is the reason this ticket builds
the markdown in code from each token's own kind (heading, paragraph break,
table header, table row, list item, note, claim) rather than concatenating a
string, and the reason a future reader must not "simplify" that function back
into a join.

## Worker B1: no account delete path exists today, so "deleted with the account" cannot be proven end to end

Established 2026-09-22 by searching rather than assuming, as the brief asked.

- No route anywhere under `adapters/` or `auth/` declares a DELETE verb.
- No code path anywhere under `src/` deletes a `User` row. Every `select(User)`
  call site (`auth/dependencies.py:108`, `auth/router.py:557`, `591`, `627`)
  reads; none deletes.
- `interactions.user_id` is `ON DELETE SET NULL` (`data/models.py:178`), so
  even if a row were deleted directly in the database, the interaction rows
  would survive with a null user.

So the product owner's "delete it with the account" cannot be satisfied by a
foreign key today and cannot be proven on a path that does not exist. This is
the second of the two branches the brief named, taken deliberately: a named,
tested function `feedback/history.py::forget_saved_answers_for_account` clears
the saved answer for one account's rows, and its test is the arm that a future
delete path has to keep green. It is called by nothing today, and its
docstring says so plainly rather than implying a wiring that is not there.

WHAT A FUTURE DELETE PATH MUST DO, in one line, so it cannot ship without it:
call `forget_saved_answers_for_account(user_id)` inside the same transaction
that deletes the user, BEFORE the row goes, because `ON DELETE SET NULL` drops
the only link back to the account the moment it does.

## Worker B1: the pinned wire contract's two depth values, against four stored ones

`Query.audience_depth` (`contracts/query.py:250`) has FOUR legal values:
`clinical_brief`, `researcher`, `deep_technical`, `plain_language`. The pinned
wire contract gives `depth: "plain" | "researcher"`.

Not a blocked stop, and the contract is not changed. The web UI offers exactly
two of those four (the field's own comment says so), and the history screen is
the web UI. Resolution: the column stores the real four-way value, so the
stored record stays true, and the endpoint maps at the wire, where
`plain_language` answers `"plain"` and the other three answer `"researcher"`.
Recorded here because a caller on the CLI, MCP or GraphQL surface can set
`clinical_brief` or `deep_technical`, and their saved answer will report
`"researcher"` on this endpoint. That is a lossy label on a wire field, never
a lossy stored row, and it is the product owner's call whether the contract
should grow a third value later.


## Worker C: journey 7's selector was wrong role, inside a catch that hid it

Defect 10 (`Developer_workflows.md`). `frontend/e2e/journeys/narrow-viewports.spec.ts`
selected the Integrations and About nav items with `getByRole("link")`. They
are MUI `Button`s, role "button" (`AppShell.tsx` lines 381-490), never a
link. Below 720px only the current page's button stays inline; the rest are
`display: none` and reachable only through `NavOverflowMenu`'s "More pages"
button and its `role="menuitem"` entries (`AppShell.tsx` lines 159-266).

Proof the old selector never navigated: reverted to the old code, stripped
the `.catch()` so the failure could show, and ran journey 7 live against a
local stack (`RUN_LIVE_JOURNEYS=1`, `S3_LIVE_WEB_URL=http://127.0.0.1:5273`,
`S3_LIVE_API_URL=http://127.0.0.1:8931`, `playwright.config.ts`'s loopback
carve-out, so this spent no guest allowance). RED:
`TimeoutError: locator.click: Timeout 5000ms exceeded ... getByRole('link', {
name: /integrations/i })`, confirming zero matching elements at 390px.

Fixed selector: `role: "button"`, branching on `width <= 720` to open the
overflow menu first. First attempt used a case-insensitive regex on the
label and a LIVE run (not a guess from source) caught a second bug the
diagnosis had not predicted: `PersonaChip` renders an "About Fleming" info
button inside the same `<nav>`, so `/about/i` is a strict-mode violation,
two elements. Fixed with `{ name: "About", exact: true }` /
`{ name: "Integrations", exact: true }`. GREEN: `1 passed (15.2s)`, 9 frames
captured across all three widths, and `frame-01.png` shows the Integrations
screen actually rendered at 390px (verified visually, not just "no error").

The `.catch(() => undefined)` is removed, not kept around a better selector.

Files: `frontend/e2e/journeys/narrow-viewports.spec.ts`.

## Worker D: four questions get zero graph rows from hops the graph answers in under a second

Established while counting hard edges for the 11.29 scoping document, by
putting two measurements this repository already holds side by side. They
contradict each other and the contradiction is a live defect, not a
bookkeeping problem.

The live graph probe of 2026-09-14
(`testing/Developer/reports/2026-09-14_handover_inputs/breadth/graph_probe.jsonl`)
ran each single-hop template against the real graph and recorded the rows:

| Hop | Anchor | Rows | Median seconds |
|---|---|---|---|
| participates_in | BRCA1 | 54 | 0.72 |
| actively_involved_in | BRCA1 | 27 | 0.55 |
| located_in | BRCA1 | 24 | 1.42 |
| participates_in | GCK | 27 | 0.58 |

The consistency run of 2026-09-22 (`runs.jsonl`, deployed commit `63ec316`)
asked the golden questions that target exactly those hops. Each made one
`cypher_query` call, each came back `status: empty`, `result_count: 0`, with
no tool error, on all three passes:

| Id | Question | Hop it targets | Graph rows, three passes | Outcome |
|---|---|---|---|---|
| G-017 | Which biological processes is BRCA1 actively involved in? | participates_in | 0 / 0 / 0 | answered from Layers 2 and 3 |
| G-018 | Where in the cell is the TP53 protein located? | located_in | 0 / 0 / 0 | answered from Layers 2 and 3 |
| G-031 | What molecular activity does the KRAS gene product have? | actively_involved_in | 0 / 0 / 0 | answered from Layers 2 and 3 |
| G-032 | Which pathways does PTEN participate in? | participates_in | 0 / 0 / 0 | answered from Layers 2 and 3 |
| G-022 | What phenotypic features are associated with Marfan syndrome? | has_phenotype, Disease to PhenotypicFeature | 0 / 0 / 0 | refused, no evidence, all three passes |

Four of the five were rescued by Layer 2, so nobody saw a failure. G-022 was
not: a person asking what Marfan syndrome looks like is told there is no
evidence, three times out of three, while the graph carries 6,076,735
`has_phenotype` rows.

What this is NOT: it is not the graph being empty. The 2026-09-14 probe is
the control, and it populated. The defect is between the question and the
Cypher, not in the data.

Two candidate mechanisms, neither confirmed, both cheap to check and NEITHER
checked here because tonight's brief is a document and not a build:

- Template selection. `cypher_templates.select_template` matches shape
  keywords against `query_intent`. G-032 says "pathways", and the `processes`
  shape's keyword list is built around "process". A question that matches no
  shape on a Gene anchor fell through to the model path on the `single_hop`
  class until fix-plan item 1 landed on the evening of 2026-09-22, which is
  the same day as this run, so the run may predate the record fallback.
- Ambiguity. G-017 contains both "biological processes" and "actively
  involved in", which are the keyword triggers for two different shapes.

Why it belongs in the 11.29 document: the product owner asked whether soft
edges need embeddings or a RAG pipeline. Five hard edges that the graph
already holds, and that return in under a second, are not reaching answers
today. That is the constraint, and it is upstream of every mechanism the
question names.

## Worker D: the whole golden set contains exactly one distinct two-hop path

Counted by hand across all 50 golden questions, checked against the graph's
14 edge labels in `tools/graph_schema_constants.py`.

Five questions strictly require a path of two or more hops where both edges
exist in the graph: G-002, G-003, G-025, G-030 and G-040. Every one of them
walks the same pattern, in one direction or the other:

```
Gene -> SequenceVariant -> Disease
```

No golden question needs three hops. No golden question needs a second
distinct two-hop pattern. And the one pattern that does appear is already
hardcoded as three named templates (`gene_variant_diseases_one`,
`gene_variant_disease_link`, `disease_genes_*` with its variant fallback),
built on 2026-09-14 after a live measurement.

The count that motivates a general multi-hop traversal engine is therefore
one path shape, and it is already built. Recorded because the brief asks for
a proposal whose motivating count is zero to be written down as costing
nothing to skip, and this is the closest the set comes.

## Worker D: the two call-count measurements disagree, and the one that binds shows 17 of 20

The consistency run records `total_tool_calls` from the stream's `tool_start`
events. Over its 86 answered runs the maximum is 10 and the median is 9,
which reads as ten calls of headroom under the twenty-call ceiling.

That reading is wrong. The ceiling measurement of the same day
(`testing/Developer/reports/2026-09-22_call_ceiling/findings.md`) counts at
the transports, where `harness/call_budget.py` actually charges, and reports
a worst observed cold pass of 17 of 20, with a theoretical cold worst case
above 20. The difference is Think's own live span confirmations and Write's
MedGen name resolution, which never appear as `tool_start` events and were
invisible to every measurement before `df657ad`.

So the headroom is three calls, not ten, and anyone reading the consistency
run alone will get this wrong. Recorded here because it changes the answer to
"can a connect-the-dots feature afford more calls": it cannot, if those calls
are Layer 2 or Layer 3.

The corollary is the useful half. `harness/call_budget.py`'s own docstring
states that `graph_http_transport` is Layer 1 and is out of scope by Section
21.3's wording. A deeper graph traversal costs zero against the ceiling. Going
deeper in the graph is free; going wider in the APIs is not.

## Worker C: defect 12 diagnosis, interrupted mid-run, NOT closed

Defect 12, the load-dependent unit suite. Diagnosis before fixing, as the
brief requires, and reported honestly incomplete: a forced handback landed
before the reproduction finished running, so nothing below is fixed and NO
FILE UNDER `frontend/` OR THE VITEST CONFIG WAS EDITED FOR THIS DEFECT.

What was established:

- Baseline, no artificial load: `npm test` in `frontend/`, 499 tests, 54
  files, all green, wall duration 144.92s (`vitest`'s own report; this run's
  wall time is close to the slow 139s figure in the defect report, so the
  baseline machine here is already close to the "slow" end of the range
  that produced 5 failures before).
- Candidate mechanism A, the one most likely to be it: 78 `waitFor(...)`
  call sites and 55 `findBy*` call sites across the suite (`App.test.tsx`,
  `phase410Premise.test.tsx`, `phase49Premise.test.tsx`,
  `threadContinuation.test.tsx`, `hooks/useAgentRun.test.ts`, and others)
  carry NO explicit timeout, so they inherit `@testing-library`'s 1000ms
  default. No `configure()` call anywhere in `src/setupTests.ts` or
  elsewhere raises that default. Every one of those call sites races a real
  timer (a mocked-but-still-async promise resolution, or React's own
  commit and effect scheduling) against a fixed 1000ms wall-clock ceiling.
  Under CPU contention that ceiling is exactly the kind of thing that flips:
  fast enough to pass on an idle machine, not guaranteed under load.
- Candidate mechanism B, narrower and already partly mitigated: the 15 or so
  `findByTestId(..., { timeout: 10000 })` call sites in
  `App.test.tsx`/`phase49Premise.test.tsx`/`phase410Premise.test.tsx`/
  `threadContinuation.test.tsx` wait out a REAL (non-fake-timer) run of
  `useAnswerReveal` (`minBannerMs: 1500`, `perItemMs: 110`) and
  `usePacedEvents` (a per-helper real dwell). These files call no
  `vi.useFakeTimers()`, unlike `hooks/usePacedEvents.test.ts` and
  `hooks/useAnswerReveal.test.ts`, which do and are not exposed to this.
  10000ms is generous against the pacing hooks' own worst case on an idle
  machine, but was not stress-tested against contention before this run was
  interrupted.
- Ruled out, tentatively, not conclusively: `phase48Premise.test.tsx`'s
  `globalThis.fetch` stub is installed in `beforeAll` and restored in
  `afterAll` with the restore point recorded in that file's own docstring
  as a prior fix (F-4.5-A-23) for exactly this class of leak; no other
  module-level fixture without a matching teardown was found by grep across
  `src/**/*.test.ts*` for `beforeAll`/`afterAll`. Not proven absent, only
  not found by this pass.
- NOT reached: the actual reproduction. A driver script
  (`run10.sh`, not committed, lived only in the scratchpad) was mid-way
  through run 1 of a planned 10 (3 under artificial CPU load from 8
  `yes > /dev/null` background processes, one per core, a no-install way to
  saturate macOS CPU) when this worker was forced to hand back. No run had
  completed under load and no specific failing test name was captured.

What this means for the done-when: item 3 (name every flipping arm with its
mechanism) is NOT met, only candidates are. Item 4 (10 consecutive runs, 3
under load) is NOT met, zero of 10 completed. No timeout was raised, so
there is nothing to disclose under the last-resort rule, and nothing was
edited under `frontend/e2e/` or the vitest config for this half of D4.

Recommended next step for whoever picks this back up: run the same
reproduction (CPU load via `yes`, no install needed, one process per core)
for at least 3 load runs and name the specific test titles that fail, not
just the file. If they cluster on bare `waitFor`/`findBy` calls, the fix is
adding an explicit, generous timeout at each exposed call site (not a global
default bump, since `@testing-library`'s default exists precisely so a
genuinely broken assertion still fails fast); if they cluster on the 10000ms
pacing-aware `findByTestId` calls, the fix is switching those test files to
`vi.useFakeTimers()` around the reveal, the way `usePacedEvents.test.ts` and
`useAnswerReveal.test.ts` already do, which removes the race against wall
time entirely rather than widening the window it races in.

## Worker C: defect 12, sweep instrument built, run blocked on a concurrent suite

Following the coordinator's correction: dropped the CPU-load instrument
(`yes` processes), which was slow, noisy, and actively harmful tonight since
it would have corrupted every other worker's frontend suite run and
competed with them for the machine. Built the deterministic replacement
instead, per the coordinator's own read of the diagnosis: lowering
testing-library's `asyncUtilTimeout` below its 1000ms default is the same
experiment as machine load, except fast and repeatable, because it exposes
exactly the bare `waitFor`/`findBy` call sites whose real margin against the
ceiling is small.

Built, not yet run:

- `/private/tmp/.../scratchpad/d4_sweep/sweep-setup.ts` (session scratchpad,
  not under `frontend/`): a throwaway setup file that calls
  `configure({ asyncUtilTimeout: n })` from `@testing-library/react`, `n`
  read from the `SWEEP_TIMEOUT` env var so one file serves the whole sweep.
- `frontend/vitest.sweep.config.ts` (untracked, will be moved out before
  this defect closes): the same `test` block as the committed
  `vite.config.ts`, `setupFiles` pointed at the scratchpad script above
  instead of `src/setupTests.ts`. Nothing under `frontend/src/` was read or
  changed to build this; it only points at a different setup file from the
  existing `vite.config.ts` shape.

NOT YET RUN. Before starting, `ps` showed worker B2's own vitest run still
in progress (`npx vitest run src/App.test.tsx src/App.savedAnswer.test.tsx
src/components/screens/SavedAnswerScreen.test.tsx
src/lib/api.fetchHistoryAnswer.test.ts src/lib/api.fetchHistory.test.ts
src/railCollapsePremise.test.tsx src/components/answer/HistoryRail.phone.test.tsx`,
pid 37113/37039, started 00:06, writing `/tmp/b2_test5.log`), per the
coordinator's explicit instruction to wait rather than run concurrently. A
monitor set to wait on those PIDs was still armed when this worker was
forced to hand back before it fired, so the sweep itself has not produced
any data yet, at any `n`, for either cluster. Nothing in this entry is a
result; it is the state of the instrument and the reason for the wait.

## Worker B2: no design exists for the saved-answer screen, and answer_markdown renders as plain text

Checked per `.claude/rules/design-consistency.md` before styling anything:
`docs/build/design/README.md`'s coverage table has no row for a saved-answer
view, and the history rail's own design (`prototype/app.html`'s `#rail`)
covers only the rail, not what opening a past item shows. This is a genuine
gap, not a missed search: the answer screen's design
(`design-system/screens/answer.html`) assumes a live, streamed run with a
per-sentence provenance spine, which a stored `answer_markdown` string plus a
flat citation list cannot reconstruct faithfully.

So `SavedAnswerScreen` (`frontend/src/components/screens/SavedAnswerScreen.tsx`)
is built from the nearest designed neighbours rather than inventing a new
look: the answer screen's own card, heading and button chrome, its plain
trust-signal line, and the citation card's "Not linked" language. The one new
element, the "Saved answer" marker banner, reuses the `layer1`/`layer1Wash`
pairing the rail already uses to mark an active item, rather than choosing an
unprecedented colour. Every value is a `designTokens` entry already used
elsewhere for the same purpose; none is new.

Separately, and also worth recording rather than fixing silently: this screen
renders `answer_markdown` as plain text (`white-space: pre-wrap`), never
parsed as markdown. No markdown renderer exists anywhere in this frontend
today, and adding one is a new dependency, outside tonight's scope and
`supply-chain-security`'s pre-install review besides. Worker B1's answer
confirmed the stored text is assembled from typed tokens in code
(headings, table rows, list items), not raw markdown syntax, so this is
unlikely to show visible markup in practice, but it is not proven absent
either. If a future backend change starts emitting real markdown syntax into
`answer_markdown`, this screen will show it literally rather than rendered.
Not a blocked stop; flagged for whoever next touches this screen.

## Worker A: closing note on the existing-test-file finding above

Resolved by the maker (not this worker), 2026-09-23. Rather than overruling
`test_mcp_mount_redirect_scheme.py`'s security objection, the maker answered
it structurally: `proxy_scheme.py`'s `_forwarded_scheme` is now UPGRADE ONLY
(returns `"https"` or `None`, never `"http"`), which makes reading the
header safe regardless of trust, and the old test file was rewritten in
place (kept, not deleted) to argue the new position with 4 arms. Verified:
`tests/.../test_proxy_scheme.py` and `tests/.../test_mcp_mount_redirect_scheme.py`
together, `venv/bin/python -m pytest` both files, rc=0, 27 passed. No stale
document left behind.

## Worker A: re-check of the maker's upgrade-only rewrite

Coordinator asked for an independent re-check of `proxy_scheme.py` after the
upgrade-only rewrite, since this worker's finding drove the change and the
maker must not be the one to sign off on it.

Structural review: `_forwarded_scheme` can only return `_UPGRADE_SCHEME`
("https") or `None`. `ProxySchemeMiddleware` only mutates `scope["scheme"]`
when the return value is not `None`. Therefore `scope["scheme"]` can only
ever be left unchanged or set to `"https"`; there is no code path that sets
it to `"http"` or anything else, regardless of header content. Checked by
hand against every shape the coordinator named (bare `http`, a comma list
with `http` first and `https` second, mixed case, leading/trailing
whitespace, an empty first entry, a duplicate header with `http` first and
`https` second, and non-ASCII/null-byte bytes, which `latin-1` decoding
cannot raise on) and none reaches a downgrade. No finding.

Added 7 new arms to `test_proxy_scheme.py`, each starting the scope at
`"https"` (built directly, not through `TestClient`, which cannot represent
a genuine HTTPS connection) and asserting the scheme survives: a bare
forged `http`, a comma list led by `http`, mixed case, whitespace padding,
an empty value, a duplicate header led by `http`, and malformed bytes
containing a null byte. Rewrote 2 stale arms
(`test_http_header_leaves_the_scheme_as_http`,
`test_reversed_comma_list_also_uses_the_first_entry`) whose old assertions
were still numerically correct but whose docstrings claimed a property
(`http` explicitly honoured) the rewrite removed; both now state plainly
that they cannot alone distinguish "ignored" from "accepted and happened to
match" and point to the https-starting arm that can.

Suite: 23 arms in `test_proxy_scheme.py` (16 original plus 7 new, 2 rewritten
in place). `venv/bin/python -m ruff check`, rc=0. `venv/bin/python -m pytest`
on the file alone, rc=0, 23 passed. Together with the maker's rewritten
`test_mcp_mount_redirect_scheme.py`, rc=0, 27 passed.

Mutation proof against the new code, four mutations via monkeypatch,
reverted after each, never written to disk:
- Mutation A (middleware disabled): 7 arms killed, unchanged from before the
  rewrite.
- Mutation B (all validation removed, raw value passed through): 11 arms
  killed, including 6 of the 7 new downgrade arms plus the malformed-bytes
  arm.
- Mutation C (client address also trusted): 1 arm killed, the load-bearing
  client-identity arm, unchanged from before the rewrite.
- Mutation D (the actual regression: `_forwarded_scheme` restored to accept
  both `http` and `https`, the coordinator's specific ask): 5 arms killed
  (`test_forged_http_header_does_not_downgrade_an_https_scope`,
  `test_comma_list_leading_http_does_not_downgrade_even_with_https_later`,
  `test_mixed_case_http_does_not_downgrade`,
  `test_whitespace_padded_http_does_not_downgrade`,
  `test_duplicate_header_leading_http_does_not_downgrade`). At least one arm
  dying under D was the coordinator's bar for coverage; five did.

Verdict: the maker's change holds. No input shape tried reaches a downgrade.

## Planner: every Disease vertex in the graph is named after its source, not the disease

Established 2026-09-23 by read-only parameterised probes against the live graph
service, `probe_g022.py` and `probe_disease_names.py` in this folder. Both are
committed so the next person re-runs them rather than re-deriving them.

This started as a check of worker D's G-022 finding and found something larger,
so the G-022 answer is at the bottom rather than the top.

### What was measured

| Probe | Result |
|---|---|
| `Disease` vertices whose `name` matches `(?i).*marfan.*` | ZERO, graph-wide |
| `Disease` vertices whose `name` matches `(?i).*syndrome.*` | ZERO, graph-wide |
| Full property bag of the 8 diseases FBN1 links to | `name` reads `GARD`, `MONDO`, `MedGen` |
| Full property bag of three arbitrary `Disease` vertices | `name` reads `SNOMEDCT_US`, `MedGen`, `MeSH` |
| `Disease`-[:has_phenotype]->anything | ZERO, graph-wide, with no filter |
| What `has_phenotype` actually joins | `SequenceVariant` to `Disease`, source ClinVar |
| `PhenotypicFeature` vertices | Exist, and every one sampled is `[stub] HP:0000002` shape, `source` = `stub`, empty `source_url` |
| `Gene {id: NCBIGene:2200}` | Resolves correctly, `name` = `fibrillin 1` |
| FBN1 `gene_associated_with_condition` | 8 rows, correct ids and `source_url`s |

The decisive one is the second row. A graph carrying MedGen's disease set in
which NOT ONE vertex has "syndrome" anywhere in its name is not a graph with
patchy names. The field holds the wrong value everywhere.

### What this means

- NO DISEASE CAN EVER BE FOUND BY NAME IN THE GRAPH. Every disease-name lookup
  must go to Layer 2, and any code that matches on `Disease.name` is matching
  against a vocabulary label such as `GARD`. The gene half is unaffected:
  `Gene.name` is correct (`fibrillin 1`).
- The ids and `source_url`s ARE correct, so the graph remains a sound navigation
  index. This strengthens rather than contradicts worker D's central point that
  the graph holds no values: its one human-readable field holds the wrong value.
- It is a plausible root cause for the historical `MedGen:C0346153` disease-name
  defect that reversed the build ordering on 2026-08-31 and was closed in build
  phase 6.2 by adding a two-call Layer 2 resolution path. That path was the right
  fix. This finding says WHY it was necessary, which was not known then.

### A shipped template that cannot return a row

`tools/cypher_templates.py:253`

    ("Disease", "phenotypes"): _Hop("has_phenotype", "PhenotypicFeature", "out")

Compiles to `MATCH (d:Disease)-[:has_phenotype]->(p:PhenotypicFeature)`, which
the probe shows returns zero rows for every Disease in the graph. Two separate
reasons, either sufficient: no `Disease` vertex has an outgoing `has_phenotype`
edge at all, and every `PhenotypicFeature` vertex is an unpopulated stub.

`tools/graph_schema_constants.py` already holds both halves of this and did not
join them up. Line 87 declares the primary pair as `("Disease",
"PhenotypicFeature")`. Line 108 records the MEASURED pair `("SequenceVariant",
"Disease")` from the 2026-09-14 work, deliberately kept separate, and its
comment says why: widening the primary pair "would silently drop the
Disease-to-PhenotypicFeature expansion". THAT EXPANSION DOES NOT EXIST. The
comment was protecting something that is not there, which is the confident
sentence shape this repository has now been bitten by five times.

### So G-022 is not a routing defect

"What phenotypic features are associated with Marfan syndrome?" refuses "no
evidence" three times of three because it routes to the template above, which
cannot return a row. Worker D's candidate mechanisms (a shape-keyword miss, a
two-shape ambiguity) are both wrong; the query is built correctly and the data
is absent. From the person's chair the refusal reads "there is nothing known
about this", which is false: MedGen carries plenty.

### NOT FIXED TONIGHT, deliberately, and this is the recommendation

The narrow fix is to stop asking the graph a question it cannot answer and let
the question reach Layer 2. That changes what the product ANSWERS, on a
discovery that overturns a standing assumption about the data, so it is the
product owner's call in the morning rather than an unsupervised overnight edit.
It was not on the list they approved before sleeping.

The underlying data fix is not available here at all: writing the graph is
Systems 1 and 2 work in the other repository, which `.claude/rules/file-protection.md`
forbids from this one. That is a blocked stop, and the useful output is this
measurement handed over rather than a change attempted.

## Worker C: defect 12 sweep, n=1000 (sanity check)

Instrument corrected first: the scratchpad setup file could not be loaded by
Vite's module graph from outside the project root (`Cannot find module
'/@fs/private/tmp/.../sweep-setup.ts'`, `fs.allow` boundary), so the sweep
setup moved to `frontend/vitest.sweep.setup.ts` (untracked, throwaway,
alongside `frontend/vitest.sweep.config.ts`, also untracked). Neither is
committed; both will be moved out of `frontend/` before this defect closes,
and are named here now so `/ship`'s stray-file sweep is not the first place
they are noticed.

`SWEEP_TIMEOUT=1000` (testing-library's own default, so this is a sanity
check that the sweep harness itself reproduces the known-green baseline
before trusting any lower `n`):

`Test Files 57 passed (57)`, `Tests 514 passed (514)`, wall 155s, rc=0.

Matches the earlier baseline behavior (all green at the default). The test
and file counts are higher than the 499/54 baseline recorded in this
worker's first report (other workers, B1/B2, have landed new history-answer
test files since). The sweep harness is trusted; proceeding to n=500.

## Worker D: the disease-name defect was known and open since build phase 2.1, as F-2.1-B07

One correction to the planner's entry above, filed the moment it was
established, because the entry as written says the root cause "was not known
then" and the repository's own record says otherwise. The measurement is right;
only its novelty is overstated, and the correction makes the finding stronger
rather than weaker.

What the repository already held before the 2026-09-23 probes:

- `tracker/phase_2.1.md:889` and `:1158`, finding F-2.1-B07, "Vocabulary
  artifacts shipped as asserted primary evidence". Raised at build phase 2.1's
  SECOND adversary pass, recorded with BRCA1's four diseases carrying `name`
  values "MeSH", "MONDO", "MedGen", "MedGen". Its status is still `in progress`,
  never closed, and the file says closing it needs an independent verification
  pass rather than a reading by the party that touched the code.
- `src/system_03_search_agent/core/graph.py` around line 5860, the comment block
  above `_is_vocabulary_token_artifact`. It names the same four values, names
  "SNOMEDCT_US" independently, and explains why the detector is a shape rule
  rather than a lookup table.
- Finding F-2.1-J5-04, in the same comment block: an EXHAUSTIVE CENSUS of all
  200,845 `Disease` rows on 2026-07-31, which found the shape rule still missed
  15,466 of them and lists seven leaked vocabulary names with their row counts
  (`HPO`, `GARD`, `OMIM`, `Orphanet`, `SNOMEDCT_US`, `UMLS`, `ORDO`) plus an
  ETL stub prefix. That census already implies the scale: the rule catching
  185,379 rows means it judged those rows artifacts too.
- `tracker/BOARD.md:96`, build phase 6.2: "Measuring before scoping found the
  root cause ALREADY RECORDED in this codebase as F-2.1-B07 and the CURIE
  fallback DELIBERATE". So the 6.2 fix was built in full knowledge of the cause.

What IS new on 2026-09-23, and it is worth having:

- The graph-wide form. "Zero `Disease` vertices anywhere have `syndrome` in
  their name" settles in one query what a census of leaked tokens could only
  imply. It removes the reading that some names are fine and some leaked.
- The join to a dead template. Nobody had connected the naming defect and the
  absent `Disease` to `PhenotypicFeature` edges to `cypher_templates.py:253`,
  and that join is what explains G-022's refusal.
- The measurement that no `Disease` vertex has an outgoing `has_phenotype` edge
  at all, and that every `PhenotypicFeature` sampled is a `[stub]`.

Why the correction matters rather than being pedantry: "nobody knew" and "it
was filed as high severity, censused across 200,845 rows, defended against in
code, and left open for fourteen months of build phases" lead to different
decisions. The second is the more useful sentence for the product owner,
because it says the constraint is not discovery but that nothing has been able
to act on it from this repository, which is exactly what
`.claude/rules/file-protection.md` predicts.

## Worker D: the same naming defect reaches an answer that currently looks healthy

Established while revising the scoping document against the planner's probes.

`OntologyClass` vertices carry the same shape of defect as `Disease` vertices,
and it is visible in a probe file already in the repository. From
`testing/Developer/reports/2026-09-14_handover_inputs/breadth/graph_probe.jsonl`,
the two-hop MeSH probe, verbatim:

```json
{"id": "MeSH:D000595", "name": "[MeSH] D000595",
 "source": "MeSH (via PubMed)",
 "source_url": "https://meshb.nlm.nih.gov/record/ui?ui=D000595"}
```

The name is the ETL stub form, the same `[stub]`-class placeholder
`_is_vocabulary_token_artifact` already catches by prefix for other labels.

This matters because golden question G-019, "What MeSH terms are assigned to
PMID 11237011?", is in my count one as a healthy hard-edge question. It returns
26 Layer 1 rows and answers on two of three passes, so every instrument reads
it as working. What a person asking which MeSH terms a paper carries can
actually be shown from those rows is a list of MeSH identifiers, not a list of
terms.

NOT VERIFIED, and stated as unverified: I did not open a live G-019 answer to
see what the page renders. Build phase 6.2 added a two-call Layer 2 resolution
path for MedGen concept ids specifically (ESearch on `[ConceptId]`, then
ESummary), and whether anything equivalent exists for MeSH descriptors is not
established here. The check is one live run of G-019 and it is worth doing
before anyone counts G-019 as a working question.

## Worker C: defect 12 sweep, n=500

`SWEEP_TIMEOUT=500`: `Test Files 57 passed (57)`, `Tests 514 passed (514)`,
wall 140s, rc=0. No failure at half the default ceiling.

## Worker C: defect 12 sweep, n=300

`SWEEP_TIMEOUT=300`: `Test Files 57 passed (57)`, `Tests 514 passed (514)`,
wall 143s, rc=0. No failure at 300ms either, less than a third of default.
## Worker B1: alembic 0008's rollback arm assumed it was the head revision

Established 2026-09-23 by running the affected suites after adding revision
0010. `tests/system_03_search_agent/data/test_migration_0008_interactions_
owner_id.py::test_the_downgrade_removes_exactly_that_column` went red with
`before - after` holding three columns instead of one.

The mechanism, not the symptom. That arm calls
`command.downgrade(cfg, "0008_interactions_owner_id-1")` starting FROM HEAD.
The relative `-1` names one revision before 0008, so the step runs every
revision between head and 0007. While 0008 was the newest column-adding
revision that was the same thing as one step, and the arm's claim, "the
downgrade removed more than the column the upgrade added", was true.
Revision 0010 adds two more columns above it, so the same call now reverses
three revisions and the arm reports 0010's columns as 0008's over-removal.

This is `.claude/rules/goal-contracts.md`'s third case, and it is the one
that gets mishandled: the subject is right, the check is right about its own
revision, and the two are measuring different things. Editing my migration
to keep that arm green would have made a true sentence false.

WHAT WAS CHANGED AND WHY IT IS THE CHECK: the arm now steps down to exactly
0008 first, takes its `before` there, and only then steps one revision
further. That measures the single step its own docstring claims and is
robust to every revision added above it, including the next one. The
assertions themselves are untouched, and nothing was weakened: the arm still
demands that the step removes `owner_id` and nothing else.

Its sibling `test_migration_0007_session_memory.py` was checked for the same
shape and does not have it: it names `PREVIOUS_REVISION` explicitly rather
than using a relative offset from head.


## Planner: correction to the entry above, the disease-name defect was NOT new

Appended 2026-09-23, same night, after worker D checked the claim against the
repository's own history and found it false. Corrected here rather than edited
above, so the wrong claim and its correction both stay visible.

WHAT I WROTE: that this finding explains why build phase 6.2's two-call Layer 2
resolution path was necessary, "which was not known then".

WHY THAT IS WRONG. The cause was known, filed and defended against long before
tonight:

- `tracker/phase_2.1.md` lines 889 and 1158, finding F-2.1-B07, "Vocabulary
  artifacts shipped as asserted primary evidence", raised at build phase 2.1's
  second adversary pass, recording BRCA1's four diseases as "MeSH", "MONDO",
  "MedGen", "MedGen". Status still `in progress`, never closed.
- `core/graph.py` carries `_is_vocabulary_token_artifact` specifically for it,
  names SNOMEDCT_US independently, and holds finding F-2.1-J5-04: an exhaustive
  census of all 200,845 Disease rows taken on 2026-07-31, listing seven leaked
  vocabulary names with their row counts.
- `tracker/BOARD.md` line 96 records that build phase 6.2 found the root cause
  already recorded here as F-2.1-B07, and that the CURIE fallback is deliberate.

So build phase 6.2 was built in full knowledge of the cause, and the CURIE
fallback is a considered defence rather than an accident.

WHAT TONIGHT'S PROBES DO ADD, which is narrower and still worth having:

- The graph-wide form. A census of leaked tokens shows the field is often wrong;
  "zero Disease vertices anywhere contain the word syndrome" settles that it is
  wrong everywhere, which a census could only imply.
- The join to the dead template. Nobody had connected the naming defect to
  `cypher_templates.py:253` being unable to return a row, or to G-022's refusal.

WHY THE CORRECTION MATTERS RATHER THAN BEING A DETAIL. "Nobody knew" and "filed
at high severity, censused across 200,845 rows, defended in code, and open
across fourteen months of build phases" lead to different decisions. The
constraint here has never been discovery. It is that nothing in this repository
is allowed to fix it, because writing the graph is Systems 1 and 2 work in the
other repository. That is the blocked stop, and it is the thing to hand over.

A SECOND ITEM, found by worker D while revising and NOT yet verified: the same
naming defect reaches `OntologyClass`. The 2026-09-14 probe file already in this
repository carries `{"id": "MeSH:D000595", "name": "[MeSH] D000595"}`. That
matters because G-019, "What MeSH terms are assigned to PMID 11237011?", returns
26 Layer 1 rows and answers two passes of three, so every instrument reads it as
working, while what a person is shown may be identifiers rather than terms. One
live run settles it and it is worth doing before G-019 is counted as working.
## Worker B1: CI gate 3 will go red on tonight's probe scripts, which are nobody's ticket

Measured 2026-09-23, running gate 3 exactly as CI runs it
(`venv/bin/python -m ruff check`, no path, whole repository): rc=1, ten
errors, ALL TEN in files added tonight under
`testing/Developer/reports/2026-09-23_overnight/`:

- `probe_disease_names.py` (3), `probe_g022.py` (4), `probe_ontology_names.py` (3)
- Two rule classes: `RUF100` unused `# noqa: E402` directives, and `ISC004`
  unparenthesized implicit string concatenation inside a collection.

Zero of the ten are in worker B1's files, which are clean. Raised here for
the planner rather than fixed, because these belong to whoever wrote the
probes and gate 3 is repository-wide: local runs scoped to `src` and `tests`
will look green and CI will not. This is the same shape as F-4.15's lesson,
that gate 3 takes no path while every local habit does.

`ISC004` in particular is worth a look rather than a reformat: it is ruff
asking whether a comma was forgotten, and in a list of Cypher probes a
missing comma silently changes which query ran.


## Planner: MeSH terms are identifiers too, and G-019 only looks like it works

Established 2026-09-23 by `probe_ontology_names.py` in this folder, committed so
it can be re-run. This confirms worker D's flagged-but-unverified observation and
extends it from one vertex to the whole graph.

### What was measured

| Probe | Result |
|---|---|
| Five arbitrary `OntologyClass` vertices | Every `name` is `[MeSH] D000001` shape, `source` `MeSH (via PubMed)` |
| The 26 rows G-019 actually reaches, `Article`-[:has_mesh_annotation]->`OntologyClass` | All 26 named `[MeSH] D000818`, `[MeSH] D002874`, and so on |
| `OntologyClass` names containing a lowercase run of 4 or more letters | ZERO, graph-wide |
| `OntologyClass` names containing "neoplasm" | ZERO, graph-wide |
| CONTROL: `Article {id: PMID:11237011}` | `name` = "Initial sequencing and analysis of the human genome." |

The control is what makes this conclusive rather than suggestive. The graph is
not broadly unpopulated: `Article.name` holds a real title and `Gene.name` holds
`fibrillin 1`. Two labels are wrong and two are right, so this is a per-label
mapping defect in the merge, not a general emptiness.

### Why this one is worse than the Disease case

G-019 is "What MeSH terms are assigned to PMID 11237011?". It returns 26 Layer 1
rows and answers two passes of three, so EVERY INSTRUMENT IN THIS PROJECT READS
IT AS WORKING: the consistency run counts it answered, the citation coverage
counts its rows cited, and worker D's scoping document counted it as a healthy
hard-edge question.

It is not working. The question asks for terms and the graph holds no terms. The
26 rows are 26 identifiers. Whatever the person ends up seeing, they did not get
what they asked for, and no gate in this repository can currently tell.

This is the goal-contracts failure named "rigor about the wrong layer", measured
on our own instruments: every leaf was verified, every row was real and citable,
and the premise that those rows carry the answer was never checked.

### What is NOT established

Whether a person actually sees `[MeSH] D000818` on screen, or sees nothing,
because `core/graph.py`'s `_is_vocabulary_token_artifact` may suppress the
tokens before they render. Those are two different defects with two different
fixes, and one live run of G-019 distinguishes them. I have not run it.

### The shape of the fix, not built tonight

Identical to the one build phase 6.2 already shipped for MedGen disease names: a
Layer 2 lookup that turns the identifier into the term, cited to the record the
term came from. E-utilities carries the MeSH database, so the path exists. It
belongs to whoever picks this up with `core/graph.py` free, since that file is
deliberately unowned tonight while three workers run beside it.

## Worker C: defect 12 sweep, n=200

`SWEEP_TIMEOUT=200`: `Test Files 57 passed (57)`, `Tests 514 passed (514)`,
wall 139s, rc=0. No failure at 200ms, one fifth of default.
## Worker B1: the saved answer will show less than the screen did, because the wire contract has no trust line

Measured 2026-09-23 against the 150 live runs in
`testing/Developer/reports/2026-09-22_10.3_consistency/runs.jsonl`:

- 35 runs ended `answer` or `flag`, which is exactly the set that saves an
  answer under this ticket.
- ALL 35 OF THEM carry a `trust_line` on their `done` event. Not most: all.
- A real example: "Sources disagree on at least one claim".

The pinned wire contract for `GET /v1/history/{trace_id}/answer` carries
`trust_signal: str` and no trust line. `trust_signal` is one of four words
(`answer`, `flag`, `ask`, `refuse`); the trust line is the sentence the
person actually read under their answer, and it is built in code by
`synthesis.trust.answer_trust_line`, never by a model.

So as pinned, a reopened answer reads MORE confident than the one the
person saw: the sentence warning them that sources disagree is the one
thing that does not come back. In a product whose stated worst failure is a
confident wrong answer, that is the wrong direction to lose a line in.

WHAT WAS DONE TONIGHT, and what was deliberately NOT done. The contract was
NOT changed: no field was added to the response, and worker B2's build is
unaffected. But the fact is STORED (`interactions.answer_trust_line`),
because a decision taken tomorrow to show the line cannot be applied to
answers saved tonight without it, and a nullable TEXT column costs nothing.

FOR THE PRODUCT OWNER, one decision: should the saved answer show the trust
line the live answer showed? If yes, it is one additive optional field on
the response and one line in the frontend, and every answer saved from
tonight onward already has the data. If no, the column is harmless and can
be dropped in a later revision.


## Worker E: the graph is deterministic, so L-01's varying row count is a varying QUERY

Established 2026-09-23 by `testing/Developer/reports/2026-09-23_L01_cause/probe_template_counts.py`, five repeats per case against the live graph over the HTTPS query service, each case run through the tool's own `validate_cypher`, `_build_params`, `_build_as_clause` and `execute_cypher` path rather than a hand-written query.

Every case returned the identical row count on all five repeats, in well under two seconds:

- HNF1A `gene_variant_diseases_one`: 100/100 every time, 1.4 to 3.1 seconds.
- HNF1A gene hop `gene_associated_with_condition`: 6/6 every time.
- HNF1A gene record: 1/1 every time.
- BRCA1 `gene_variant_diseases_one`: 100/100 every time, 2.0 to 2.3 seconds.
- BRCA1 gene hop: 4/4 every time.
- BRCA1 gene record: 1/1 every time.

Two consequences. First, the graph does not answer the same query differently run to run, and no query here comes near the 30-second budget, so neither "AGE planner nondeterminism" nor "a timeout presented as empty" survives as an explanation of L-01. Second, the numbers L-01 measured are template row counts: BRCA1's stable 4 is exactly the gene hop template, and HNF1A's 100 is exactly `gene_variant_diseases_one`. The row count varies because the TEMPLATE varies, which means the agent sent a different query, not because the graph wavered.

Correction to the 2026-09-21 report, which read the two graph calls in RESULT emission order: the results arrive out of order because the two calls run concurrently. Re-mapped by `call_id` to start order, the variable call is always start slot 0 and the stable one is always slot 1 (HNF1A 25 in all 10 runs, BRCA1 40 in all 9). So there is one unstable call per run, not an unstable position.

## Planner: FIXED, the leaked-vocabulary filter missed the bracketed form

Built and proven 2026-09-23, `core/graph.py`. This is the one part of tonight's
graph work that was fixable here, and it was fixable because it is OUR control
being wrong rather than the graph's data being wrong.

### What was broken

`_is_vocabulary_token_artifact` exists to stop a leaked controlled-vocabulary
token being presented as a genuine name at full confidence. It tested
`text.startswith("[stub]")` for bracketed placeholders, then fell through to
`if " " in text: return False`.

`[MeSH] D000818` contains a space, so it was declared a genuine name.

Proven by execution rather than by reading, with `probe_artifact_filter.py` in
this folder, which runs the real function over the real strings the live graph
returned tonight. Before the fix: 2 of 13 cases wrong, both the MeSH form. The
eleven others, including every Disease form and the `[stub]` form, were already
correct, which is why this had gone unnoticed; the filter looked like it worked
because for one whole label it did.

### What it cost

All 26 rows golden question G-019 returns for "What MeSH terms are assigned to
PMID 11237011?" are identifiers of that shape, and they reached the answer path
carrying full assertion confidence and no artifact marker. Somebody had already
thought about bracketed ETL placeholders and covered one of the two shapes.

### The fix, and the part not to simplify later

A new `_bracketed_vocabulary_token(text)` returns the vocabulary name inside a
leading `[...]`, or None. `_is_vocabulary_token_artifact` now flags any value
whose bracketed token is `stub`, a known leaked vocabulary, or a CURIE prefix.

IT TESTS THE TOKEN, NEVER THE BRACKET, and that is deliberate. A blanket "starts
with a bracket" rule would have been shorter and wrong: PubMed gives translated
articles bracketed titles such as "[Studies on the effect of interferon on
hepatitis B]", and those are genuine names whose confidence must not be stripped.
Two such titles are now control arms, and they are what make the positive arms
mean anything.

It returns the token rather than a bool so a caller can say WHICH vocabulary
leaked, which is what the next reader of a flagged row actually wants.

### Evidence

| Check | Result |
|---|---|
| `probe_artifact_filter.py`, 13 real values | 13 of 13 correct, was 11 of 13 |
| New arms in `tests/.../core/test_graph.py` | `[MeSH] D000818` and `[MeSH] D000001` added to the artifact list, RED against the old filter by construction; two translated titles added as controls; one dedicated arm with a populate check |
| `pytest tests/.../core/test_graph.py -k "vocabulary or artifact or bracketed"` | rc=0, 33 passed |
| `pytest` over the four files that reference the filter | rc=0, 261 passed, 4 skipped |
| `ruff check` on both changed files | rc=0 |

### What this does NOT fix, stated plainly

The person still does not get MeSH terms, because the graph does not hold them.
This stops an identifier being presented as a term at full confidence; it does
not turn it into a term. The real fix is the one build phase 6.2 already shipped
for MedGen disease names, a Layer 2 lookup that resolves the identifier and
cites the record the term came from. That is a build, not a filter change, and
it is the natural next item.

## Worker C: defect 12 sweep, n=100, FIRST FAILURE, and it is order-dependent not a bare margin

`SWEEP_TIMEOUT=100`: `Test Files 1 failed | 56 passed (57)`, `Tests 1 failed
| 513 passed (514)`, wall 167s, rc=1.

Named arm: `src/App.test.tsx > privacy: the previous person's thread is
cleared on sign-out > does not show the next signed-in person the previous
person's collapsed turns`. Vitest's own error: `Test timed out in 15000ms`,
pointing at the `it(...)` line (1162), not at a specific query, elapsed
15041ms for that test.

MECHANISM, established by isolating the test rather than guessed: reran the
SAME file at the SAME `SWEEP_TIMEOUT=100` with `-t` filtered to only this
one test (36 of 37 sibling tests skipped). It PASSED, 9880ms, comfortably
under both the 100ms per-call ceiling's worst case and the 15000ms global
test timeout. So the failure is NOT this test's own bare `waitFor`/`findBy`
margin against 100ms in isolation; it only appears after roughly 25
preceding tests in the same file have already run in the same worker. That
is an ORDERING / ACCUMULATION dependency, not a simple fixed-timeout-vs-real-
timer race of the kind machine load or the sweep alone was expected to
expose. The bare-timeout hypothesis is not wrong, exactly: this test does
carry several unguarded call sites (`signIn`'s `waitFor(() => expect
(loginMock).toHaveBeenCalled())` and `findByRole("textbox", ...)`, called
twice; the bare `findByRole("heading", { name: "What variants cause it?"
})` at line 1170), any of which could be the one whose margin the
accumulated slowdown finally erodes below 100ms. But WHICH one, and WHAT
accumulates across 25 prior tests to erode it (mock call-count growth,
DOM nodes RTL's auto-cleanup did not fully tear down, `userEvent.setup()`
internal state, or simple real-time cost of 25 real render+effect cycles
in the same jsdom instance) is not yet isolated. That is the next step, not
yet done: bisect by running the full file with an increasing test count
prefix (first 10, first 20, first 25, ...) at `SWEEP_TIMEOUT=100` to find
where the margin actually crosses zero, then read exactly what state that
prefix leaves behind.

This is a real, reproduced result, not a guess: rerunning the isolated
single test at n=100 a second time would strengthen confidence further and
has not yet been done in this pass.

## Worker F: audit of every `_HOPS` template, and the fix for the one dead entry

`tools/cypher_templates.py:253`, `("Disease", "phenotypes"): _Hop("has_phenotype",
"PhenotypicFeature", "out")`, is the only dead entry in `_HOPS`. Every other hop
template was re-probed tonight against the live graph, read only, one column per
probe (matching `execute_cypher`'s single-column `as_clause` default) and every
value as a parameter. Full audit table, probe script and write-up:
`testing/Developer/reports/2026-09-23_zero_row_templates/report.md` and
`probe_all_templates.py` in the same folder.

Verdict counts: 10 of 11 `_HOPS` entries live, 1 dead. The dead one is exactly
the planner's G-022 finding above. Confirmed a second way tonight, with no
filter at all: `MATCH (a:Disease)-[:has_phenotype]->(x:PhenotypicFeature)`
returns zero rows graph-wide.

The fix touches two files, both owned by this worker, and both parts are
needed together:

- `tools/graph_schema_constants.py`: `EDGE_ENDPOINTS["has_phenotype"]` read
  `("Disease", "PhenotypicFeature")`, a pair the graph has never carried a row
  for. It now reads the real, measured pair, `("SequenceVariant", "Disease")`,
  promoted up from `ADDITIONAL_EDGE_ENDPOINTS` (now empty; that table held
  exactly this one entry). This is not cosmetic: `EDGE_ENDPOINTS` also feeds
  `schema_slice.py`, which renders the schema text the plan-tier model reads on
  the GENERATED-query path. The old pair told the model the same false thing
  the dead template acted on, so a generated query for a phenotype question
  could reach the identical dead end. The fix closes both paths at once.
- `tools/cypher_templates.py`: the `("Disease", "phenotypes")` row in `_HOPS`
  and its now-unused `"phenotypes"` shape keyword are removed. Removing only
  the constant and leaving the `_HOPS` entry was not available: the module's
  own import-time guard, `_assert_templates_name_real_labels`, raises for
  every question in the system the moment the endpoint tables stop documenting
  a pair a `_HOPS` entry names, which is the populate check doing its job
  rather than a silent drift.

Rejected: rewriting the template to something else. There is no phenotype data
on any Disease vertex to route to, and inventing a replacement graph query for
absent data is exactly what the brief and `.claude/rules/file-protection.md`
forbid. Removal is the smallest change that stops the product asking the graph
a question it cannot answer.

What a person typing G-022 sees: before, always "I could not find evidence,"
three passes of three, which reads as "nothing is known about this" and is
false. After, `select_template` returns `None` for the same question, the same
fallback four other golden questions (G-017, G-018, G-031, G-032, worker D's
finding above) already reach and get rescued from by Layer 2 today. Whether
G-022 is in fact rescued the same way depends on `core/graph.py`'s act/plan
loop, which this worker does not own and did not touch, so that is left open
rather than asserted fixed.

Red-against-old-code: the existing test asserted G-022 selects
`disease_phenotypes_one`. Run before the fix: `AssertionError: no template for
'What phenotypic features are associated with Marfan syndrome?'`, `1 failed, 54
passed`. After updating the test and adding three populate-check arms (that
`"phenotypes"` no longer matches as a shape for any anchor, that no template
name or Cypher string names `PhenotypicFeature` any more, and that
`has_phenotype`'s real pair is documented exactly once): `58 passed`. `ruff
check` on both changed source files and the test file: `All checks passed!`,
rc=0.

One test outside this worker's ownership now fails, not fixed here:
`tests/system_03_search_agent/tools/test_schema_slice.py::test_build_schema_slice_lookup_stays_bounded_but_reaches_two_hops`
asserted `PhenotypicFeature` is reachable two hops from `Gene`, via `Disease`,
which was true only because of the wrong pair this fix removes. `schema_slice.py`
and its test are not in this worker's owned files
(`tools/cypher_templates.py`, `tools/graph_schema_constants.py`, and their own
test files only). Full run: `tests/system_03_search_agent/tools/`, 1 failed
(that arm), 1629 passed, 99 skipped. The needed fix is narrow and named in
`testing/Developer/reports/2026-09-23_zero_row_templates/report.md`'s last
section, for whoever owns that file: replace the "reaches PhenotypicFeature at
two hops" assertion with one that PhenotypicFeature is correctly absent now
that no edge documents a route to it from Gene, or pick a different label to
prove the two-hop floor with.

Edges carrying real data with no template at all, cross-checked against
worker D's finding above: `cited_in` (3.9M rows, Article to Article) and
`subclass_of` (2.8M rows, OntologyClass to OntologyClass). `close_match` and
`exact_match` are `EDGE_ENDPOINTS`-mixed (no single typical pair), so they are
not hop-table candidates the way the other ten labels are. Not built tonight,
noted per the brief: the ask was to fix what is dead, not add coverage for
edges nothing currently asks about.

## Worker G: the premise holds, MeSH resolves 26 ids in two calls and maps back by its own field

Established live against real E-utilities on 2026-09-23, before writing any
code, because this repository's standing method is to verify the premise
first. Every command below is re-runnable.

The graph half, re-run from `probe_ontology_names.py` (rc=0), confirms
worker D's reading exactly: every `OntologyClass` name is `[MeSH] D000818`,
zero names graph-wide contain a lowercase run of four or more letters, zero
contain "neoplasm", while the `Article` control for PMID:11237011 reads
"Initial sequencing and analysis of the human genome." So two labels are
right and one is an identifier wearing a name field.

The Layer 2 half, four live probes:

- ESummary keyed on a descriptor id is REJECTED, the same way MedGen's is:
  `esummary.fcgi?db=mesh&id=D000818` answers
  `{"error":"Invalid uid D000818 at position= 0","result":{"uids":[]}}`.
  So a one-call shape does not exist and the two-call shape is forced, not
  chosen.
- ESearch on `db=mesh` with `D000818[MHUI]` returns UID `68000818`. `MHUI`
  is NCBI's own MeSH-unique-identifier index, the exact counterpart of
  MedGen's `[ConceptId]`.
- ONE ESearch carrying all 26 of G-019's ids ORed together returns
  `count=26`, all 26 UIDs. The assembled term is 438 characters, inside the
  500-character cap `NcbiEfetchSearchInput.term` already enforces, which is
  why the batch is capped below 26 per call rather than left open.
- ONE ESummary over all 26 UIDs returns all 26 records, each carrying
  `ds_meshui` (its own descriptor id) and `ds_meshterms`, whose first entry
  is the preferred term. D000818 is "Animals", D015894 is "Genome, Human",
  D016045 is "Human Genome Project".

TWO CALLS TOTAL for 26 ids. Same count for 1 id or for 25.

THE EVIDENCE THAT MAPPING BY ORDER WOULD BE A BUG, and it is not
hypothetical: ESearch returned the UIDs in DESCENDING numeric order
(`68030342` first, `68000818` last) while the input term listed them in the
graph's order (`D000818` first). Position `i` of the result is not position
`i` of the request. `ds_meshui` on each record is the join key, the same
lesson `synthesis/disease_names.py` recorded for MedGen's `conceptid`.

`mesh` is ALREADY a legal `SearchDb` value in `tools/ncbi_efetch_schemas.py`
and is NOT a `SummaryDb` value. Adding it to `SummaryDb` is the additive
change `system-design-patterns` pattern 10 permits inside v1, with the
2026-09-22 `taxonomy` addition as the precedent, and it is added only
because the ESummary above actually answered.
## Worker B1: revision 0010 was amended after it had already been applied locally

Recorded 2026-09-23 because it is a hazard for anyone else on this branch,
not because anything shipped wrong.

Revision 0010 was written with two columns, applied to the local
`search_agent_users` database, and then amended to add a third
(`answer_trust_line`) once the trust-line measurement came in. A database
already stamped `0010` therefore had the two-column shape while the file
described three, and `alembic downgrade` failed on `DROP COLUMN
answer_trust_line` for a column that was never added.

Resolved locally the honest way rather than by hand-patching the table to
match: the three constraints and two columns were dropped, the database was
stamped back to `0009`, and `alembic upgrade head` was run again, so the
local schema is exactly what a fresh upgrade from 0009 produces. Verified by
reading `information_schema.columns` and `pg_constraint` afterwards.

WHO ELSE THIS AFFECTS: nobody on develop or production, since neither has
ever seen revision 0010; it lands with this change. Any developer who ran
`alembic upgrade head` on their own database between the two versions will
hit the same failure and needs the same three steps.


## Worker C: defect 12, bisecting the n=100 failure

Three more isolated-subset runs at `SWEEP_TIMEOUT=100`, all read-only against
`frontend/src/App.test.tsx` (no edits):

- The failing test alone (`-t` filtered to it only): PASSED, 9880ms.
- That test plus its one immediately preceding sibling (13 tests total: the
  four `T-4.13-03`, three `F-4.13-A-10`, two `F-4.13-A-07`, one
  `F-4.13-RV-01`, one `F-4.13-FV-01`, one `system notes` test, and the
  target): PASSED, 53.39s wall for the run, target test not individually
  timed in the log but the whole run finished clean.
- The same 13 plus an attempted `App >` prefix match for the file's first
  11 tests: STILL 13 selected, not 24. The `App >` pattern matched nothing;
  a follow-up sanity check (`-t "leaves the landing when a signed-in user
  submits a question"`, one of those 11 by its own title) matched and ran
  fine alone, so `-t` itself works, but this repository's Vitest CLI does
  not accept a `describe`-name-plus-`>` path fragment as the pattern the
  way its own reporter prints it. Not solved; recorded as a real limit of
  this pass rather than smoothed over.

So the load-bearing preceding set is NOT the 13 already tested (that passed
clean), which leaves the file's first 11 tests (`describe("App", ...)`, the
ones exercising full sign-in-then-ask flows through `userEvent`) as the
remaining candidate for what the failing test needs to have run before it
to fail at n=100. That prefix was not reached in this pass; the CLI pattern
problem above is what stopped it, not a decision to stop early. Time-boxed
here to move to the pacing-cluster measurement and the fixes, per the
coordinator's ordering. Left OPEN, not closed: WHICH of the first 11 tests'
side effects erodes the margin (a specific mock's call-count state, DOM
nodes RTL's per-test `cleanup()` does not fully unmount, or plain
accumulated real wall-clock cost across ~13 to 24 real render-and-userEvent
cycles in one jsdom instance) is not isolated. Whoever continues this can
reach the missing prefix with `npx vitest run --config vitest.sweep.config.ts
src/App.test.tsx -t "<regex covering the first 11 test titles individually,
joined with |>"` rather than the `describe` name, since that is the form
proven to work here.

## Worker G: the descriptor-to-UID step cannot be computed, it has to be asked

Worth recording because the first six-digit probe makes it look computable
and a later reader will be tempted to delete the ESearch call.

`D000818` resolves to UID `68000818`, `D015894` to `68015894`, `D002874` to
`68002874`. Six-digit descriptors all look like `68` followed by the digits,
which reads as an arithmetic mapping and would let one ESummary call do the
whole job.

It is not a mapping. The graph holds 30,790 `OntologyClass` vertices and a
probe confirmed every single id matches `MeSH:D<digits>` with no other
shape, but it also confirmed NINE-digit descriptors exist
(`MeSH:D000066388`, `MeSH:D000066428`, `MeSH:D000066448`), which NLM
introduced once six digits ran out. Live: `D000066428` is UID `2009637` and
`D000066388` is UID `2009636`. No prefix, no padding, nothing derivable from
the descriptor. Both resolve correctly through `[MHUI]` and both return a
real term, "Coal Industry" and "Oil and Gas Industry".

So ESearch is load-bearing for a whole class of real ids, and the two-call
shape is the minimum rather than a convention copied from MedGen.

Two smaller live checks, both cheap and both recorded so nobody re-spends
them: `sort=relevance`, which `NcbiEfetchSearchInput` applies to every
ESearch this repository makes, is accepted on `db=mesh` with no
`warninglist` and no reordering; and the source URL a `MeSH:` graph row
already carries, `https://www.ncbi.nlm.nih.gov/mesh/?term=D000818` from
`tools/cypher_provenance.py`, answers HTTP 200 and the page contains
"Animals", so the citation on a resolved term already points at the record
the term was read from and no new URL construction is needed.

## Worker C: defect 12, pacing-cluster durations measured (not swept, timed)

Per the coordinator: these sites carry an explicit `{ timeout: 10000 }`
third argument, so `configure({ asyncUtilTimeout })` never touches them; the
right measurement is their real duration against that fixed ceiling, not a
sweep. Ran `App.test.tsx`, `phase49Premise.test.tsx`, `phase410Premise.test.tsx`,
`threadContinuation.test.tsx` together with the COMMITTED config (no sweep
override), `--reporter=verbose`, on this same machine, unloaded: all 79
tests passed, 95.33s wall.

Worst real elapsed times, read straight from the reporter, all still
comfortably under 10000ms but with a shrinking margin:

- `phase49Premise.test.tsx`, "states the outcome and the elapsed time, not
  counts alone": 7697ms, 23% of the ceiling unused.
- Nine more tests in the same file's "the app presents what the prototype
  presents" block: 6800 to 7219ms each, all in the same tight band.
- `threadContinuation.test.tsx`, "replaces the inline run with its answer
  in place, thread still above" (R22): 6356ms.
- `App.test.tsx`, the SAME test the sweep failed at n=100, "does not show
  the next signed-in person the previous person's collapsed turns": 6135ms
  here, unloaded, with the default 1000ms ceiling in force and no sweep at
  all. That is real, independent corroboration of the earlier bisection
  finding: this test's own real cost is already substantial before any
  accumulation from preceding tests is added, so a modest additional load
  (or a few more real-cost preceding tests, which is what the file already
  gives it) is enough to cross a tight ceiling.

Reading this together with the original bug report's own baseline split
(139s slow run, 5 failed; 50s fast run, 245 passed): this machine's own
unloaded baseline sits at 95 to 155s across every run so far tonight,
already at the slow end of that range, and the worst pacing-cluster test
here used 77% of its 10000ms budget with no load applied at all. A modestly
slower machine, or a few more milliseconds of contention from another
worker's suite running concurrently (which is the actual overnight
condition, not a hypothetical), plausibly pushes one of the 6800 to
7697ms tests over 10000ms. This is corroborating evidence for candidate
mechanism B, not yet a reproduced failure in that cluster specifically:
no run in this pass has yet shown one of these `{timeout: 10000}` sites
actually time out.
## Worker B1: CI gate 4 is red on two tests, and they belong to the graph-schema change

Measured 2026-09-23 running gate 4 exactly as CI runs it
(`pytest -m "not integration" -q`): `2 failed, 5517 passed, 154 skipped,
23 deselected, 1 xfailed`, rc=1.

The two:

- `tests/system_03_search_agent/export/test_kgx_traversal.py::
  TestMultiHopTraversal::test_two_hops_expand_the_frontier_gene_to_disease_
  to_phenotype`
- `tests/system_03_search_agent/tools/test_schema_slice.py::
  test_build_schema_slice_lookup_stays_bounded_but_reaches_two_hops`

Cause, established rather than guessed. Tonight's working tree changes
`tools/graph_schema_constants.py` so that `has_phenotype`'s endpoints move
from `("Disease", "PhenotypicFeature")` to `("SequenceVariant", "Disease")`,
with the comment that the live graph found zero `has_phenotype` edges out of
any Disease. Both failing tests pin the OLD gene to disease to phenotype
two-hop, so they now describe a path the schema no longer claims.

NOT WORKER B1's. Neither test mentions `feedback`, `history`, `capture` or
`interactions` even once (grep count zero in both files), and nothing in
tonight's saved-answer work touches `export/`, `tools/` or any edge label.
Raised for whoever owns the graph-schema change: the two arms need to move
to the new endpoint pair or be retired with a reason, and the second one in
particular is named for reaching two hops, so deleting it would quietly drop
the coverage rather than update it.


## Planner: the two-hop test passed for fourteen months by agreeing with a wrong constant

2026-09-23. Worker F's fix to `EDGE_ENDPOINTS["has_phenotype"]` turned
`test_schema_slice.py::test_build_schema_slice_lookup_stays_bounded_but_reaches_two_hops`
red. Resolved here, and the resolution is the interesting part rather than the
edit.

### Establishing which thing was wrong, before touching anything

`.claude/rules/goal-contracts.md` says a red gate is a question, not an
instruction, and names three cases: the subject is wrong, the check is wrong, or
both are right about different things. Editing a test so the test passes, when
the test was right, is the same failed run as weakening a check.

This is the third case, and it took a probe to establish rather than a reading.

The test's PROPERTY is right and valuable: a lookup slice must reach two hops.
It guards finding F-2.1-A5-03, where a hop floor of 1 was also the ceiling, so
every two-hop question in the system was unanswerable by construction and a
phenotype question came back with four cited diseases instead.

The test's WITNESS was wrong: it used PhenotypicFeature, two hops from Gene via
Disease. That was true of `EDGE_ENDPOINTS` and never true of the graph.

### Why this one is worth recording rather than just fixing

The arm passed for fourteen months by agreeing with a constant that was wrong,
and it could not have failed, because it and the code under test read the same
false table. Meanwhile the SAME constant builds the schema slice handed to the
plan-tier model, so the model was being told the same false thing, which is
`attack-the-constraint`'s rule exactly: when the output is model-generated, read
the input first. Worker F found that second path; it is the larger half of its
fix and it was not in the brief.

Note what this is NOT: not a vacuous arm. It had real assertions that would have
failed against a genuinely broken slice builder. It was rigor pointed at a
premise nobody had checked, which `goal-contracts` names "rigor about the wrong
layer".

### The change

The property stays, the witness moves to a path with real data on both edges:
OntologyClass, two hops from Gene via Article, `mentioned_in` then
`has_mesh_annotation`. Measured: 25 articles for BRCA1, 14 MeSH annotations for
a sampled PMID. Verified the slice really contains it before asserting it.

A counterpart assertion was ADDED rather than the old one merely deleted:
PhenotypicFeature must now be ABSENT from the slice, because offering the
generator a label with no incoming edge invites a query that can only return
zero rows. That turns tonight's measurement into a standing guard instead of a
one-off correction.

The docstring, which already tracked this assertion's first two moves, now
tracks the third and says plainly that the property was right and the witness
was wrong.

### Evidence

| Check | Result |
|---|---|
| `pytest tests/.../tools/test_schema_slice.py -q` | rc=0, 20 passed |
| Slice contents verified directly before asserting | `OntologyClass` present, `PhenotypicFeature` absent, `has_mesh_annotation` present |

## Worker C: defect 12, BLOCKED STOP on the fix step, mechanism named

The coordinator's next step, per-cluster fixes, is BLOCKED by this worker's
own constraints, restated as unchanged in the same message that asked for
the fix: "nothing under `frontend/src/`... if the mechanism turns out to
live in `frontend/src/` after all, that is a blocked stop." It does. Every
test file carrying a named arm is under `frontend/src/`:

- `frontend/src/App.test.tsx`: the bare `waitFor`/`findBy` cluster
  (`signIn`'s `waitFor(() => expect(loginMock).toHaveBeenCalled())` and
  `findByRole("textbox", ...)`, and the bare `findByRole("heading", { name:
  "What variants cause it?" })` at line 1170), and the specific failing test
  named above.
- `frontend/src/phase49Premise.test.tsx`, `frontend/src/phase410Premise.test.tsx`,
  `frontend/src/threadContinuation.test.tsx`: the pacing cluster's
  `findByTestId(..., { timeout: 10000 })` sites, and the fix the coordinator
  named as preferred, `vi.useFakeTimers()` around the reveal the way
  `hooks/usePacedEvents.test.ts` and `hooks/useAnswerReveal.test.ts` already
  do, is itself an edit to those same `frontend/src/` files.

No fix was applied to either cluster. No timeout was raised anywhere
(nothing to disclose under the last-resort rule). No file under
`frontend/src/` was edited; both were read-only for diagnosis, which this
worker's brief allows for reading a file it may not edit (the same posture
Worker A takes with `app.py`). Since no fix landed, no "re-measure to show
the margin moved" was possible either.

Both throwaway sweep files removed from `frontend/` now, ahead of the
confirmation runs below rather than waiting until a close that will not
happen tonight: `frontend/vitest.sweep.config.ts` and
`frontend/vitest.sweep.setup.ts` moved to this session's scratchpad. Neither
was ever committed or staged. `frontend/src/` and `.claude/` remain
untouched; nothing was committed.

RULED IN, with named margins (not ruled out, the hypothesis survives):
the bare-timeout cluster produces a real, reproduced failure at
`SWEEP_TIMEOUT=100` in `App.test.tsx`'s "does not show the next signed-in
person the previous person's collapsed turns", and it is order-dependent,
confirmed reproducible by direct isolation (passes alone, fails after the
full file). The pacing cluster is not yet reproduced as an outright failure
but sits at 61 to 77 percent of its 10000ms budget on this unloaded
machine tonight, which is corroborating rather than conclusive.

Recommended owner for the fix: whoever has write access to
`frontend/src/*.test.tsx` tonight or in the next session. The concrete
recipe is already written above (fake timers for the pacing cluster,
explicit per-site timeouts for the confirmed bare-call cluster, and finish
the interrupted bisection of `App.test.tsx`'s first 11 tests to name the
exact accumulating resource before choosing between those two fixes for
that specific test).
## Worker B1: correcting worker B2's premise, the stored answer DOES contain markdown syntax

Established 2026-09-23 by reading worker B2's finding above ("no design
exists for the saved-answer screen") against worker B1's actual output.
Flagged for the planner because the two halves of item 10.2 currently
disagree about what travels between them, and neither half is wrong on its
own.

B2's finding says the saved-answer screen renders `answer_markdown` as plain
text with `white-space: pre-wrap` and no markdown parser, and reasons that
this is "unlikely to show visible markup in practice" because worker B1's
text is "assembled from typed tokens in code (headings, table rows, list
items), not raw markdown syntax".

THAT PREMISE IS FALSE, and it is false in the one direction that matters.
The text is assembled from typed tokens in code AND the result is markdown
syntax, because markdown is the only single string that can carry a table at
all. `feedback/capture.py::answer_markdown_from` emits exactly four
constructs:

- `## Heading`
- `| Isolate | AMR genes |` followed by `| --- | --- |` and one `| ... |`
  line per row
- `- list item`
- plain paragraphs separated by a blank line

Rendered with `pre-wrap` and no parser, a person reopening the real G-035
answer sees literal `##`, literal pipes and a literal `| --- | --- |`
separator row where they originally saw a heading and a twenty-row table.
Every word and every AMR gene is present and correctly ordered, so nothing is
LOST, but it does not look like the answer they were shown, which is the bar
this ticket set itself.

WHY B1 DID NOT SIMPLY EMIT PLAIN TEXT INSTEAD: measured on that same real
run, a plain text join drops the entire table body, because a `table_row`
token's visible content lives in `cells` and its `text` is the grounded
sentence behind it (1448 characters joined against 3095 of markdown). Plain
text is the lossy option, not the safe one.

THE CHEAP RESOLUTION, for whoever picks this up: no dependency and no
supply-chain review is needed. The producer is code, not a model, so the
renderer only has to handle those four constructs, which is a small function
over the string's own lines rather than a markdown library. That keeps B2's
correct instinct (do not add a parser for untrusted markdown at 1am) and
still shows the person their table.

NOT A BLOCKED STOP for either worker: the backend is correct against the
pinned contract, whose field is named `answer_markdown`, and the frontend is
correct about not adding a dependency tonight. It is a seam, and it needs one
decision rather than two more guesses.


## Worker E: every row count L-01 measured, matched to the query that produces it

Established 2026-09-23. Each number below was reproduced by running the real `cypher_query` against the live graph with the template the code would have chosen, so these are identifications, not inferences.

The stable call, present in every run of both questions, is not the question's own search at all. It is `_build_planned_go_terms_call`'s code-chosen `gene_go_processes_one`, a `context_only` call added on 2026-09-20 that asks for the gene's Gene Ontology terms. It returns exactly 25 rows for HNF1A and exactly 40 rows for BRCA1, which are precisely the two stable numbers, on 2026-09-21 and again on 2026-09-23. It is stable because a code-chosen template runs the same query every time.

The unstable call is the question's own graph search:

- BRCA1 4 rows is `gene_diseases_one`, the `gene_associated_with_condition` hop. Measured 4/4 on five straight repeats.
- HNF1A 100 rows is `gene_variant_diseases_one`, truncated at the row limit out of 1212 variants.
- HNF1A 6 rows would be `gene_diseases_one`, which is what a rewrite that drops the word "variants" selects instead.

So there was never an unstable POSITION and never two unstable calls. There is one search per run whose query is chosen from model-produced inputs, beside one context call whose query is chosen in code, and only the first one moves.

## Worker E: the HNF1A question did not return at all on develop tonight

Established 2026-09-23 at 00:51 by `testing/Developer/reports/2026-09-23_L01_cause/remeasure.py`, raw file `raw/hnf1a_run1.json`.

Six BRCA1 runs immediately before it all completed normally, in 11.6 to 25.9 seconds each. The first HNF1A run ("What diseases are caused by variants in the HNF1A gene?", researcher depth, guest session) then held its event stream open for 1206.5 seconds and ended with "The read operation timed out". No `done` event, no `error` event, no tool result of any kind reached the client. On 2026-09-21 the same question completed in 17.0 to 48.1 seconds on every one of ten runs.

Stated carefully, because I cannot yet separate three candidates: a real regression on the answer path for this question, contention from the other overnight workers running live queries against the same develop deployment, or a deploy in progress. What is certain is the client-visible behaviour, which is the part that matters from the person's chair: the page would have spun for twenty minutes and then shown nothing.

This is logged as a separate observation from L-01, not as its cause. L-01 is about a run that completes and quietly carries fewer sources; this is a run that never completes.

## Worker C: defect 12, pacing cluster fix, threadContinuation.test.tsx

Block lifted by the coordinator for TEST FILES under `frontend/src/` only
(`App.test.tsx`, `phase49Premise.test.tsx`, `phase410Premise.test.tsx`,
`threadContinuation.test.tsx`, any other `*.test.tsx`/`*.test.ts` carrying a
named arm); production source (`App.tsx`, `components/`, `lib/`, `hooks/`)
stays off limits.

Added a local `revealNow(ms = 20000, step = 50)` helper to
`frontend/src/threadContinuation.test.tsx`: `vi.useFakeTimers()`, then
`vi.advanceTimersByTime` in small steps each inside its own `act`, matching
`hooks/useAnswerReveal.test.ts`'s own precedent exactly (small steps because
the reveal schedules its NEXT timer inside a React effect that only runs
once `act` returns; a single large jump only fires whatever was already
scheduled at call time). Called only between two real-timer stretches of a
test, never around a `userEvent` call, so no `userEvent.setup()` in the file
needed a `delay: null` change.

Replaced both pacing sites: `askFirst`'s
`findByTestId("source-1", undefined, { timeout: 10000 })` and the second
test's `findByText(/It is linked to HBOC/, undefined, { timeout: 10000 })`,
each with `await revealNow();` followed by a synchronous `getByTestId`/
`getByText` (no more waiting needed, the state is already settled once
`revealNow` returns).

Before (measured earlier, unloaded, real timers): "replaces the inline run
with its answer in place, thread still above" 6356ms.
After (measured now, same machine): 3537ms. "keeps the answer screen
mounted..." 3788ms (not separately measured before; both pacing sites live
in these same two tests). All 3 tests in the file pass, `rc=0`, file wall
16.23s.

Not literally instant: `revealNow`'s own 400 real `act()` calls (20000ms /
50ms step) cost real JS and React-commit time, so the improvement is
partial rather than total. What changed is the KIND of cost: before, the
test raced real wall-clock time against a fixed 10000ms ceiling, and a
slower machine or a few more milliseconds of contention could cross it.
Now the cost is a bounded amount of synchronous JS work with no dependency
on how fast real timers fire, which is what the coordinator asked for
("removes the race rather than widening it") even though it is not free.
No timeout was raised on this file.

## Worker C: defect 12, pacing cluster fix, phase410Premise.test.tsx

Same `revealNow` helper added locally to `frontend/src/phase410Premise.test.tsx`.
One site: "shows an anonymous visitor no source, citation or NCBI url when
the run cited nothing" (`findByTestId("answer-meta", undefined, { timeout:
10000 })`). Before: 2263ms. After: 1640ms. All 17 tests in the file pass,
`rc=0`, file wall 61.49s. One pre-existing `act(...)` warning on an
unrelated test ("does not mint a guest token merely from mounting the
app") is untouched by this edit and was not introduced by it.

## Worker E: L-01's instability is no longer reproducible on develop for the two measured questions

Established 2026-09-23 by `testing/Developer/reports/2026-09-23_L01_cause/remeasure.py`, twelve live runs against the develop API, raw files under that folder's `raw/`. The same two questions, the same depth, the same guest-per-run method as the 2026-09-21 measurement, with each Layer 1 call joined to its start by `call_id` instead of read in emission order.

Every completed run returned an identical Layer 1 result:

- BRCA1, six of six runs: the question's own call 4 rows, the GO context call 40 rows, 61 sources, 40 distinct Layer 1 citations. On 2026-09-21 this call returned 4 rows in seven runs and 8 in two.
- HNF1A, five of five completed runs: the question's own call 100 rows, the GO context call 25 rows, 86 sources, 63 distinct Layer 1 citations. On 2026-09-21 this call returned 100 rows in seven runs, 12 in two and 0 in one, and sources fell from 86 to 41.

The cause of the improvement is two commits that landed after the measurement and were never re-measured against it: 27d68ae, which gives a shapeless gene question a template instead of a generated query, and 2bc8ec0, which does the same for an exploratory question with no shape. Both narrow the model path, which is where a same-question row count could move. So L-01's own measured signature is closed for gene questions, by work already on develop.

Two things this does NOT establish, and neither should be rounded off:

- The model path still exists and is still reachable: an `aggregate` question whose rewrite matches no shape, and a Disease or Article anchor on the two hop classes. A query drafted by a model on that path can return a different row count, including zero, on the same question.
- One HNF1A run in six did not return at all (see the previous finding), which is a worse outcome for the reader than the one L-01 describes.

## Worker E: L-01's mechanism reproduced on demand, and it is the model-drafted query

Established 2026-09-23 by `testing/Developer/reports/2026-09-23_L01_cause/probe_model_path_spread.py`, five runs per question through the real tool against the live graph.

The probe holds everything fixed that a run can hold fixed: the same question text, the same resolved CURIE, the same query class, the same row limit. The only thing left free is what the plan-tier model writes when `select_template` matches no shape. Five runs of "what is the clinical relevance of BRCA1":

- run 1: 100 rows. The model wrote a query returning `g, d, d.id, d.name` over both the gene edge and the variant path.
- run 2: 1 row. The model wrote `RETURN count(d)`, a single number.
- run 3: status `error`. The tool's overall budget was exceeded before any result returned.
- run 4: 2 rows. Two counts, unioned.
- run 5: 2 rows. The same two counts.

HNF1A over the same five runs returned 1, 2, 1, 1 and 2 rows, drifting between one count and two.

That is L-01's signature, produced to order: one question, one gene, one run to the next, and the graph evidence behind the answer collapses from a hundred cited disease records to a single number, with `error_payload` null and every other tool succeeding. It is not the graph, which answers identically on repeat, and it is not the execution path, which turns every failure into a typed error and never into an empty result. It is that on this path nobody chose the query; a model drafted it fresh each time, and the drafts are not equivalent to one another.

The zero-row case specifically was not reproduced in these five runs, and that is stated rather than rounded off: what was reproduced is the collapse from a rich record set to a near-empty one, plus one hard failure, which covers the 12-row case in L-01's own measurement and makes the 0-row case the same mechanism at its limit rather than a separate one.

## Worker C: defect 12, pacing cluster fix, App.test.tsx (3 of 4 sites; 1 reverted)

Same `revealNow` helper added to `frontend/src/App.test.tsx`. Converted
three of the four sites: "leaves a restored row's own count and date
alone..." kept ITS `source-1` wait unconverted (see below), "renders the
truncation disclosure once the run lands" (`answer-note-0`), and both
`source-1` waits inside "does not show the next signed-in person the
previous person's collapsed turns" (the SAME test the sweep found at
n=100).

ONE SITE REVERTED, not left silently: "leaves a restored row's own count
and date alone when the same question is re-asked" interleaves several
REAL-timer waits (`waitFor` on `createRunMock`, `releaseHistory()`, then
`findByTestId("history-rail")` and `findByRole("9 sources")`) between the
ask and its `source-1` wait. Converting it to `revealNow()` left the run
stuck at `step-Write` after a full 20000ms fake-timer advance, `source-1`
never appearing; confirmed by a temporary debug dump of every
`data-testid` present at that point (removed before this was recorded).
Root cause, as far as diagnosed: `vi.useFakeTimers()` only intercepts
timers scheduled AFTER it installs; the pacing hooks' own first
`setTimeout` is very likely already scheduled, and possibly already fired,
on the REAL clock during those earlier real-timer waits, so
`revealNow`'s advance loop has nothing fake to advance for that first
tick and the chain never completes. A correct fix for this ONE test needs
fake timers installed from the very start (before `ask`), with every
intervening real-timer wait re-verified under that regime, which is a
materially larger and riskier change than the other three sites needed.
Reverted to the original `findByTestId("source-1", undefined, { timeout:
10000 })`, with the reasoning above written into the test file itself as a
comment so the next reader does not "fix" it back to `revealNow()` without
reading why. This is a deliberate exception, not an oversight, and it is
the one timeout left unraised-but-unremoved in this file.

Measured, full file, all 38 tests pass, `rc=0`, wall 59s (vs the
implicit-baseline comparison this worker does not have an exact prior full-
file number for, since earlier runs measured only the sweep's aggregate).
Individual before/after for the three converted sites:

- "renders the truncation disclosure once the run lands": before 3110ms
  (measured earlier), after 1360ms.
- "does not show the next signed-in person the previous person's collapsed
  turns" (the sweep's own failing test): before 6135ms unloaded / 6333ms
  here in full-file context now. NOT meaningfully faster, because only ITS
  TWO `source-1` waits were converted; the test also carries the bare,
  unconverted `findByRole("heading", { name: "What variants cause it?" })`
  at line ~1179, which is the order-dependent arm's own suspected margin
  site and is addressed separately below, not part of the pacing cluster.
- The restored-row test's `source-1` wait (kept real): no change, as
  expected, since it was reverted.

No new timeout was raised in this file. The one 10000ms timeout that
survives here already existed before this pass; it was reverted TO, not
newly introduced.

## Worker E: no path in the graph tool turns a failure into an empty result

Established 2026-09-23 by reading every branch of `tools/graph_connection.py` and `tools/graph_http_transport.py` and by the probes above, which exercised both the success and the failure paths against the live service.

This matters because L-01's brief raises it as a hypothesis, and because the distinction is the whole point: `empty` means "the graph holds nothing", `error` means "we did not find out", and a product that says the first when it means the second has stopped being trustworthy.

What the code actually does:

- `_handle_response` in the HTTPS transport ends every branch in a return or a raise. A 200 whose body cannot be parsed, or is missing `rows` or `total_available`, raises `GraphConnectionError`. 401 and 403 raise `GraphAuthError`, a timeout status or a `timeout` code raises `GraphTimeoutError`, a rate-limit status or code raises `GraphRateLimitedError`, and every remaining status, including a 500 and a 422 carrying `cypher_rejected`, raises `GraphConnectionError`. There is no branch that returns an empty row list for a request that failed.
- `execute_cypher` on the psycopg2 transport classifies `QueryCanceled` as `GraphTimeoutError`, a lost connection as `GraphConnectionError`, and any other driver error as `GraphConnectionError`. A connect-time failure is classified before any query runs.
- `cypher_query` catches `GraphError` around execution and returns `status: "error"` with the message, never `status: "empty"`.
- The two places that deliberately swallow a `GraphError` both return "unknown" rather than a value: `_curie_exists` returns None with a docstring saying in as many words that None is not False, and the count query returns None rather than a fabricated total.

So `status: "empty"` in a shipped run means the query really did match zero rows. Hypothesis two from the L-01 brief, an error misclassified as an empty, is ruled out by construction rather than by absence of evidence. Hypothesis one, a timeout or deadline presented as a successful empty, is ruled out the same way, and separately by measurement: every template query measured tonight returned in under 3.1 seconds against a 90-second budget.

What remains is the query itself, which is hypothesis three in a form the brief did not name: not the graph's planner being nondeterministic, but the agent drafting a different query.

## Worker E: the smallest honest change, and the trap in the obvious version of it

Written 2026-09-23. This is a handover, not a change: every file it names belongs to someone else.

From the person's chair, in priority order.

First, and this is the fix rather than a consolation: stop drafting. A question should run a search someone chose, or say it cannot search and ask for a name. That is what 27d68ae already did for gene questions, and the remaining model-path cases need the same: an `aggregate` question whose rewrite matches no shape, and a Disease or Article anchor on the two hop classes. A search chosen in code gives the same answer to the same question, so a reader who asks twice is not quietly shown half the evidence the second time. This lives in `select_template` and the plan step.

Second, if the model path has to stay, the answer must say so. The data already exists and is already computed: `CypherQueryOutput.template` is None exactly when a model drafted the query, and it is set on every path. What drops it is `_cypher_output_to_structured_fields` in `core/graph.py`, which carries `status` and `error` into the Finding and leaves `template` behind. Carrying it is one line. The answer would then be marked "not yet confirmed", the same treatment an answer with omitted findings already gets, and carry one sentence under it, which is what the reader would see:

"I wrote this search myself rather than using a checked one, so asking again may find more."

The wording is deliberate. The existing `FAILED_SEARCH_NOTE` says "One of the background searches did not finish", which would be false here: the search finished, it was simply not a search anyone had vetted. Reusing it trades one dishonesty for another.

THE TRAP, and it is the part most likely to be assumed away: the degradation measured tonight was `ok` to `ok`, a hundred rows on one run and a single count on the next, never an `empty`. `failed_searches` is built only from calls whose status is `error`, so any rule keyed on a zero-row or failed result misses the case that actually loses the reader their evidence. The signal has to be keyed on the query having been DRAFTED, not on the result having been empty.

Two further observations from the same runs, neither chased down:

- `trust_outcome` is not stable across identical runs. The five completed HNF1A runs carried byte-identical Layer 1 results, 86 sources and 63 Layer 1 citations each, and came back `flag` four times and `ask` once. Same evidence, different badge.
- `CYPHER_QUERY_TIMEOUT_SECONDS` is 90.0, while `.claude/rules/tool-call-budgets.md` and tech spec Section 6.1 both state 30 seconds per `cypher_query` call. One of the two is stale and neither is obviously wrong; recorded rather than resolved.

An instrument bug of my own is recorded rather than tidied away, since it would have produced a confident wrong table. `probe_selection_grid.py`'s first run cached each template's row count under the Cypher text alone. Two genes bind the same parameter name, so the text is identical for both, and BRCA1 silently reused HNF1A's counts: the grid printed "gene_diseases_one: 6 rows" for BRCA1 where the true answer is 4. The cache key now carries the bound CURIE. Same family as the four instrument defects build phase 6.2 recorded, a harness reporting a plausible value where it should have reported that it did not know.

## Planner: the 30 versus 90 second cypher budget is a known divergence, not a defect

Worker E flagged that `CYPHER_QUERY_TIMEOUT_SECONDS` is 90.0 while
`.claude/rules/tool-call-budgets.md` and locked Section 6.1 both say 30. Checked
before acting, because a rule-versus-code conflict is exactly the case where
editing the wrong side produces a green gate certifying a false record.

NEITHER SIDE IS A MISTAKE AND NOTHING SHOULD CHANGE TONIGHT. Commit `9a3f50a`
(2026-07-31, finding F-2.1-B02) raised it deliberately on measurement, and the
constant's own comment already records the divergence and files it as a Step 6.2
reconciliation item.

The measurement behind it is worth keeping visible, because it inverts what the
budget looks like it is for:

- The graph is NOT the expensive part. An indexed CURIE lookup returns in about
  110ms, a labelled multi-hop traversal in about 130ms.
- What consumes the budget is the plan-tier call that WRITES the Cypher. Six
  real generation calls measured 13,169 to 39,378ms, mean 25,472. Two of six
  exceeded 30 seconds on generation alone, before the graph was touched.
- So a budget named for the graph query is mostly spent on drafting the query.

A CONNECTION WORTH NOTING, not chased tonight. That drafting step is the very
path worker E identified as L-01's mechanism: when no template matches, the
plan-tier model writes the Cypher fresh, and two drafts are not equivalent. So
the same step is both the largest consumer of this budget and the source of the
run-to-run variance. Anyone closing the model path should re-measure this
constant afterwards rather than assume it still needs 90 seconds, and the
constant's own comment already asks for a re-measure at build phase 7.0.

Changing either side is out of scope here regardless: the rule lives under
`.claude/` and needs a branch and a pull request, and Section 6.1 is in a locked
document.

## Worker H: the seam between B1 and B2 closed, both defects

Item 10.2's overnight seam: B2's `SavedAnswerScreen.tsx` rendered
`answer_markdown` as plain text on the premise that the stored string is
"not raw markdown syntax", and B1 established that premise false (it IS
markdown, the only single string that can carry a table). Separately, the
pinned wire contract carried no field for `trust_line`, the one plain
sentence a person read under their original answer, so a reopened answer
read more confident than the one they saw. Both closed.

### Defect one: markdown, not a library

New module `frontend/src/components/screens/savedAnswerMarkdown.tsx`
(`SavedAnswerMarkdown` component, `parseSavedAnswerMarkdown` for testing),
a closed-vocabulary renderer matched exactly to what
`feedback/capture.py::answer_markdown_from` can emit, read line by line
before writing this: a heading (`## text`), a paragraph (plain text, no
markers rendered specially), a table (`| header |` + `| --- |` + rows,
cells unescaped from `_cell`'s `\` and `|` escaping), and a bulleted list
item (`- label`, also unescaped, since both `list_item` and the headerless
`table_row` fallback go through `_cell`). No markdown library was added:
the producer is this repository's own code, not arbitrary text, so the
five constructs above are the entire vocabulary, and a general parser would
add nested lists, code fences, raw HTML and link syntax as pure attack
surface with zero payoff. No `dangerouslySetInnerHTML` anywhere in this
change: every block becomes typed React elements, and JSX's default
escaping is the actual control (proven by a dedicated test that renders a
`<script>`-shaped stored string and asserts no `<script>` element exists
and no side effect fired).

What a person now sees reopening a table-bearing answer: real headings,
a real `<table>` with a header row and one row per isolate, a real
bulleted list, and no literal `##`, `|` or `---` anywhere on screen. Proven
against a REAL stored string: `answer_markdown_from`'s actual output on
`testing/Developer/reports/2026-09-22_isolate_search/round2/
tokens_G-035.json`'s real 31 live token events (question G-035), copied
into `savedAnswerMarkdown.test.tsx` as `G_035_MARKDOWN` verbatim, exercising
a paragraph with inline `[n]` markers, two headings, a 20-row table and a
list item all from one real run. A second fixture, `ESCAPED_MARKDOWN`, is
the same builder's output against a synthetic event list built specifically
to carry a literal `|` and a literal `\` inside a cell, generated with
`PYTHONPATH=src venv/bin/python` against the live `Event`/`TokenPayload`
models (script kept in this entry's git history), proving the escape/
unescape round-trip rather than asserting it.

Unknown-construct fallback: `parseSavedAnswerMarkdown`'s default branch
returns the raw block as a plain paragraph, verbatim, for anything matching
none of heading, table or list. Tested with a deliberately unknown line
("An unanticipated construct with `code` and **bold**") and separately with
a `<script>`-shaped string: both render as visible, literal text rather
than vanishing.

Constructs covered, all five `answer_markdown_from` can emit: heading,
paragraph, table (header + rows), list item (both the `list_item` kind and
the headerless `table_row` fallback share one code path since both are
`- label` lines). None found that this file cannot render.

### Defect two: `trust_line`, additive, end to end

One new optional field on the pinned wire contract,
`trust_line: str | None`, additive within v1 per `system-design-patterns`
pattern 10:

- `src/system_03_search_agent/adapters/web_sse/app.py`'s
  `SavedAnswerResponse` gains `trust_line: str | None = Field(None,
  max_length=200)`, the bound mirrored from `DonePayload.trust_line`
  (`contracts/events.py`) rather than invented, and `get_v1_history_answer`
  passes `saved.trust_line` through (the field already existed on
  `feedback.history.SavedAnswer`, built by B1; this ticket only wires the
  endpoint).
- `frontend/src/lib/api.ts`'s `HistoryAnswerResponse` gains `trust_line:
  string | null`, parsed defensively in `fetchHistoryAnswer` (a non-string
  value reads as `null`, never a fabricated string).
- `SavedAnswerScreen.tsx` renders `trust_line` first, in the same place and
  style as the live answer screen's own "ONE PLAIN LINE"
  (`AnswerScreen.tsx`, UI fix set 9 item 9.9): a checkmark only when the
  sentence starts with "Confirmed", plain otherwise. When `trust_line` is
  absent (`null`), the screen falls back to the pre-existing `trust_signal`
  line unchanged, never rendering nothing at all and never rendering both
  at once.

What a person now sees: a reopened answer that hedged when the original did
("Sources disagree on at least one claim.") shows that same hedge, not a
bare checkmark implying full confidence. Tested present
(`test_trust_line_travels_through_when_the_row_has_one` on the backend,
`api.fetchHistoryAnswer.test.ts`'s two new arms, `SavedAnswerScreen.test.
tsx`'s "renders trust_line, not trust_signal") and absent (the endpoint's
existing happy-path test now asserts `body["trust_line"] is None` with a
populate-check comment explaining why, and a screen-level test asserts the
`trust_signal` fallback still renders).

### Files touched

Owned and edited: `frontend/src/components/screens/SavedAnswerScreen.tsx`,
`frontend/src/components/screens/savedAnswerMarkdown.tsx` (new),
`frontend/src/components/screens/savedAnswerMarkdown.test.tsx` (new),
`frontend/src/components/screens/SavedAnswerScreen.test.tsx`,
`frontend/src/lib/api.ts`, `frontend/src/lib/api.fetchHistoryAnswer.test.ts`,
`src/system_03_search_agent/adapters/web_sse/app.py`,
`tests/system_03_search_agent/adapters/web_sse/test_saved_answer_endpoint.py`.

One file outside the owned list was touched, narrowly:
`frontend/src/App.savedAnswer.test.tsx`. Its `SAVED_ANSWER` fixture is typed
`HistoryAnswerResponse`, and adding the new required-shaped `trust_line`
field to that interface made the fixture fail to compile. Added
`trust_line: null` to the one object literal; nothing else in that file was
read or changed. Not a scope violation of the "files you must NOT edit"
list, which names four specific files (`App.test.tsx`,
`phase49Premise.test.tsx`, `phase410Premise.test.tsx`,
`threadContinuation.test.tsx`) that worker C owned tonight;
`App.savedAnswer.test.tsx` is a different file.

### Verification

- `venv/bin/python -m ruff check` over `app.py` and the touched test file:
  rc=0. A full-repository `ruff check .` shows 40 pre-existing errors, all
  in `testing/Developer/reports/*/probe_*.py` scratch scripts from other
  workers tonight; none in any file this ticket touched (checked by name).
- `PYTHONPATH=src venv/bin/python -m pytest
  tests/system_03_search_agent/adapters/web_sse/test_saved_answer_endpoint.py`:
  rc=0, 16 passed (was 14; two new arms added).
- `PYTHONPATH=src venv/bin/python -m pytest
  tests/system_03_search_agent/feedback/test_history.py
  tests/system_03_search_agent/feedback/test_history_saved_answer.py
  tests/system_03_search_agent/feedback/test_capture_saved_answer.py`:
  rc=0, 43 passed, unaffected by tonight's change (read-only verification
  that B1's own layer still holds).
- `npm run build` in `frontend/`: rc=0, `tsc -b && vite build` clean.
- `npx vitest run` on the four touched/added frontend test files: rc=0,
  28 passed.
- Full `npm test` in `frontend/` was still running past this entry's write
  time (`load-dependent unit suite`, worker C's own live concern
  tonight); its result was not in hand when this entry was written, so it
  is reported separately rather than guessed at here.

No `dangerouslySetInnerHTML` anywhere in this change, confirmed by reading
every file touched and by the script-injection test in
`savedAnswerMarkdown.test.tsx`.

## Worker G: FIXED, G-019 now answers with MeSH terms, two calls, 26 of 26 cited

Shipped, and proven by five live runs of the real pipeline against this
working tree rather than by a test alone. Evidence:
`testing/Developer/reports/2026-09-23_mesh_terms/` (`g019_after.txt` is run 1
in full, `run_g019_local.py` re-runs it, `measure_call_cost.py` measures the
budget).

WHAT A PERSON NOW SEES for "What MeSH terms are assigned to PMID 11237011?",
where they previously saw a list of codes:

    Animals, Chromosome Mapping, DNA Transposable Elements, Drug Industry,
    Forecasting, Genes, Genetics, Medical, Humans, Mutation, Proteins,
    Repetitive Sequences, Nucleic Acid, RNA, Species Specificity,
    Genome, Human, Human Genome Project, Databases, Factual,
    Conserved Sequence, Private Sector, Public Sector,
    Sequence Analysis, DNA, CpG Islands, Evolution, Molecular,
    Gene Duplication, Proteome, GC Rich Sequence, Genetic Diseases, Inborn

All 26, each cited to its own MeSH record page
(`https://www.ncbi.nlm.nih.gov/mesh/?term=D000818` and so on, 26 distinct
URLs), each carrying `layer: layer_2_api` because the heading was read live
and saying so is the layer-authority gate rather than a detail.

FIVE CONSECUTIVE LIVE RUNS, every one identical on the facts that matter:

| Run | Terms named | Raw `[MeSH] D...` codes | `layer_calls_used` | Seconds |
|---|---|---|---|---|
| 1 | 26 | 0 | 2 | 11.3 |
| 2 | 26 | 0 | 2 | 23.4 |
| 3 | 26 | 0 | 2 | 11.0 |
| 4 | 26 | 0 | 2 | 16.5 |
| 5 | 26 | 0 | 2 | 31.6 |

THE CALL COST, measured at `harness/call_budget.py` where the ceiling is
actually charged, never from `tool_start` events which cannot see these
calls:

- 26 ids, cold cache: 2 calls, 26 headings back.
- 1 id, cold cache: 2 calls. The floor is two, and it is a floor rather than
  a per-id price.
- Any repeat inside one process: 0 calls.
- A question with no MeSH rows, for example a MedGen disease question: 0
  calls. The resolver declines another vocabulary's CURIE by prefix rather
  than spending a lookup to miss.
- Against the ceiling: worst observed cold pass 17 of 20 becomes 19 of 20.
  Inside the ceiling, and the product's own `done` payload reported
  `layer_calls_used: 2` on all five runs.

The resolution runs AFTER every Act call, so the two calls cannot starve
anything downstream, and `resolve_descriptor_ids` additionally declines to
start when fewer than two calls remain. If it ever were refused, the answer
degrades to the flagged identifiers it showed before, never to a failed
query.

What changed, four files plus two new ones:

- `src/system_03_search_agent/synthesis/mesh_terms.py`, new. Two calls total
  whatever the id count, joined by `ds_meshui`, one-week cache, never invents
  a heading, never raises into the loop.
- `tools/ncbi_efetch_schemas.py`: `mesh` added to `SummaryDb`, additive
  within v1, live-verified before being added.
- `tools/ncbi_eutils_actions.py`: the `mesh` ESummary field allowlist.
  Without `ds_meshui` on it the extractor strips the join key and every
  heading is orphaned, which is build phase 4.7's discontinued-gene defect.
- `core/graph.py`: the resolver merged into the existing
  `apply_resolved_disease_names` call rather than beside it.
- `tests/system_03_search_agent/synthesis/test_mesh_terms.py` and
  `tests/system_03_search_agent/core/test_mesh_term_answer.py`, new.

## Worker G: three things this run turned up that are NOT mine to fix

Recorded rather than left, since all three were visible in the same five
live runs and two are pre-existing.

FIRST, AND THE ONE WORTH SOMEONE'S TIME: the summary sentence undercounts.
All five runs opened with "Found 20 ontology class records for PMID
11237011" and then listed 26, with 26 citations. The sentence counts the
prompt slice (`_MAX_FINDINGS_FOR_MODEL_PROMPT`, 20) while the display list
carries 26. Pre-existing, nothing to do with MeSH, and it fires on any
question returning more than 20 rows. A reader who counts the list finds the
opening sentence wrong.

SECOND: the model's prose did not ground on this question. Every run fell
back with "the written summary of these records could not be verified
against them, so this answer lists the records found instead". The fallback
is the honest path working and the terms reach the reader through it, so
this is a quality gap rather than a defect. It is also pre-existing: the
same fallback fired before this change, on the identifiers.

THIRD, and this one I did fix because it was in a file I own:
`tests/.../tools/test_ncbi_efetch_schemas.py::test_each_action_accepts_every_db_its_spec_enum_lists`
claimed to pin "the full documented vocabulary per action" and pinned 14 of
`SearchDb`'s 15, missing `pmc`, while asserting `len(search_dbs) == 14`. So
the assertion agreed with the list and both disagreed with the code, which
is why nothing caught it: `pmc` was added to `SearchDb` in UI fix set 11 and
this arm was not updated. Now 15, and `pmc` is also the value the
summary-rejection arm uses, since `mesh` stopped being outside `SummaryDb`.
The rejection arm was MOVED to a still-valid example rather than deleted, so
the per-action vocabulary separation it exists to prove is intact.

## Worker G: 40 ruff errors in two other workers' report folders will turn CI red

Not mine and not fixed, flagged because CI gate 3 is `ruff check` with NO
path, over the whole repository, which is exactly the trap build phase 4.15
recorded when a local `ruff check src tests` ran green and CI did not.

`venv/bin/python -m ruff check` at the repository root, exit code 1, 42
errors. 40 of them are in:

- `testing/Developer/reports/2026-09-23_zero_row_templates/probe_all_templates.py` (14)
- `testing/Developer/reports/2026-09-23_L01_cause/probe_selection_grid.py` (7)
- `testing/Developer/reports/2026-09-23_L01_cause/probe_all_shapes.py` (6)
- `testing/Developer/reports/2026-09-23_L01_cause/probe_model_path_spread.py` (4)
- `testing/Developer/reports/2026-09-23_L01_cause/probe_tool_row_count.py` (3)
- `testing/Developer/reports/2026-09-23_L01_cause/probe_template_counts.py` (3)
- `testing/Developer/reports/2026-09-23_L01_cause/probe_go_terms.py` (3)

Mostly ISC001/ISC004, implicit string concatenation inside a list of Cypher
probes, which is the natural way to write a multi-line query and is the
reason it keeps happening in probe scripts. The remaining 2 were mine, in
`measure_call_cost.py`, and are fixed. Whoever owns those folders should run
`venv/bin/python -m ruff check` with no path before the branch ships.

## Worker G: the ruff finding above is CLOSED, re-measured an hour later

The entry above reported 42 whole-repository ruff errors, 40 of them in two
other workers' report folders. Re-run at the end of this worker's session:

    venv/bin/python -m ruff check
    All checks passed!      (exit code 0)

Whoever owns those folders fixed them in the interval. Recorded as closed
rather than deleted, because the reason it was worth flagging still stands:
CI gate 3 runs `ruff check` with NO path over the whole repository, while a
local `ruff check src tests` would have stayed green throughout, which is
the exact gap build phase 4.15 recorded. Anyone adding a probe script to a
report folder tonight should re-run the pathless form before the branch
ships.

## Worker C: defect 12, pacing cluster fix, phase49Premise.test.tsx (all 6 sites)

Same `revealNow` helper added. All six pacing sites converted: `landAnAnswer`
(the shared helper 9+ tests call), the "shows the same reasoning detail
while the run is still going" test's two waits (this run never sends
`done`, so `revealNow` only needed to clear the guard/think/plan dwell, not
a full landing; both its `findByTestId`/content `waitFor` converted to a
single `revealNow()` plus synchronous assertions), and the four remaining
`askIt`-based tests (F-4.9-A-03, F-4.9-A-02, F-4.9-A-04, F-4.9-R-01). All 21
tests in the file pass, `rc=0`, file wall 89s.

Before/after, the worst cases from the original pacing-duration measurement:
"states the outcome and the elapsed time, not counts alone" 7697ms before,
3593ms after. "carries the source's identity on the citation chip" 7005ms
before, 4519ms after. Not uniformly faster in this run: a few tests near
the END of the file (e.g. "states what each figure in the status strip
counts", 10686ms; "never says a number of layers agreed", 9309ms) got
SLOWER than their own earlier real-timer measurement. Read plainly: none of
those failed and none approached the 15000ms per-test ceiling, but
`revealNow`'s own ~400 real `act()` calls per invocation cost real CPU time
that compounds across 21 sequential uses of it in one file, so this
specific fix trades a RACE against real wall-clock waiting for a smaller,
bounded, but nonzero amount of JS overhead that itself grows with how many
times it runs in a row. Recorded honestly rather than only reporting the
improvements.

## Worker C: defect 12, the order-dependent arm is FIXED, not by touching it directly

Re-ran the `SWEEP_TIMEOUT` sweep against `App.test.tsx` alone at `n=100`
(the exact point the earlier sweep found the failure) THREE times after the
pacing-cluster conversions above landed in this same file. All three:
`Test Files 1 passed (1)`, `Tests 38 passed (38)`, `rc=0`. Wall times
129.48s, 51.93s, 33.91s (the first run's extra cost is almost certainly this
machine warming caches/JIT after the earlier long editing session; the next
two are consistent with each other).

"does not show the next signed-in person the previous person's collapsed
turns" (the exact test that failed at n=100 before) is now GREEN at n=100,
reproducibly. The fix was NOT applied to its own bare
`findByRole("heading", { name: "What variants cause it?" })` at line 1222,
which is still there, still bare, still exposed to the swept default. What
changed is everything AROUND it: converting the file's OTHER pacing-cluster
sites (including this same test's own two `source-1` waits) to `revealNow`
removed the accumulated real wall-clock cost that the earlier bisection
had narrowed to "the file's first ~11 to 25 tests." With that accumulation
gone, whatever real-time margin the bare `findByRole` call needed is
apparently available again even at a 100ms ceiling.

This reframes the earlier "order-dependent arm, named-and-open" finding:
the ACCUMULATION mechanism itself is not fully explained (still do not know
the exact resource that was accumulating: real CPU time from the slow
pacing waits themselves is now the leading candidate, since removing them
is what fixed it, rather than a leaked mock, timer, or DOM node), but the
DEFECT IS RESOLVED as a practical matter: the specific reproduced failure
no longer reproduces, three times running, with no timeout raised and no
change to the failing call site itself. Left open only as a "why" question
for intellectual completeness, not as a live risk to this gate.

## Worker C: defect 12, status checkpoint before the 10-run confirmation

All fixes for this round are landed: `revealNow()` added to
`threadContinuation.test.tsx` (2 sites), `phase410Premise.test.tsx` (1
site), `App.test.tsx` (3 of 4 sites, 1 deliberately reverted with reasoning
in the file), and `phase49Premise.test.tsx` (all 6 sites). The
order-dependent arm is confirmed fixed (three clean n=100 sweep runs). No
timeout was raised anywhere in this round; the one 10000ms timeout that
survives (`App.test.tsx`'s restored-row test) already existed before this
pass and was reverted TO, not newly introduced, with the reason recorded
in the test file itself.

Both throwaway sweep files are confirmed OUT of `frontend/` again
(`git status --porcelain frontend` shows nothing sweep-related).

Starting the 10 clean consecutive runs now (`npm test`, committed config,
no artificial load, gated on `$?` directly with output redirected to a
file, never through a pipe), after confirming via `ps` that no other
worker's vitest process was running. Driver script:
`.../scratchpad/d4_final10/run10_clean.sh`, results streaming to
`.../scratchpad/d4_final10/summary.txt`. Recording each run's number, exit
code, wall time, and pass/fail counts as they land, below, appended as each
one completes rather than held until all 10 finish.

## Worker C: defect 12, 10-run confirmation, run 1 FAILED, and it confirms the coordinator's challenge

`run=1 rc=1 dur=163s :: Test Files 1 failed | 57 passed (58) :: Tests 2
failed | 525 passed (527)`. NOT another handback artifact: this is the
first of the 10 clean confirmation runs, full suite, no artificial load,
committed config.

Both failures are in `phase49Premise.test.tsx`, both `Error: Test timed
out in 15000ms`:

- "states the outcome and the elapsed time, not counts alone"
- "reopens the run's own steps behind Show work, and closes them again"

Both are tests whose pacing wait was converted to `revealNow()` this
session. This is the coordinator's challenge landing as a REAL failure
before the targeted load check even started: `revealNow`'s roughly 400
real `act()` calls per invocation are CPU-bound work, and CPU-bound work
is exactly as wall-clock-timeout-sensitive as the real-timer waiting it
replaced, just with a different sensitivity curve. Under ordinary
contention from the other 57 files' worker processes on this actual
machine, two of the newly-converted tests crossed the SAME 15000ms ceiling
the original defect was measured against.

This changes my own prior conclusion, and I am recording that reversal
plainly rather than defending the earlier framing: "the kind of risk
changed" is NOT established. What changed is which mechanism produces the
wall-clock cost (deterministic CPU work vs. waiting on a real timer), not
whether the suite is still load-dependent. It still is. The fix as it
stands trades one load-dependent failure mode for another, on at least
these two tests.

Continuing per the coordinator's instructions: finishing the remaining
9 runs, recording all 10 including this failure, then running the targeted
moderate-load check on `phase49Premise.test.tsx` alone to get a real
worst-case number, then very likely needing to CUT `revealNow`'s own cost
(fewer, larger `advanceTimersByTime` steps) rather than declare this done,
since last night's own instrument test data was 10686ms and 9309ms for two
tests in that file even unloaded, and this run just showed the ceiling can
be crossed for real.

## Worker C: defect 12, 10-run record (running tally, appended as each lands)

- run 1: rc=1, dur=163s, Test Files 1 failed | 57 passed (58), Tests 2
  failed | 525 passed (527). Detail above (both `phase49Premise.test.tsx`,
  both `revealNow`-converted tests, both `Test timed out in 15000ms`).
- run 2: rc=0, dur=128s, Test Files 58 passed (58), Tests 527 passed (527).
- run 3: rc=0, dur=139s, Test Files 58 passed (58), Tests 527 passed (527).

## Planner: FIXED, the opening sentence counted the prompt slice instead of the answer

2026-09-23. Worker G called this "the most worthwhile thing turned up tonight
that nobody owns" while building the MeSH work, and it was right, so it got
built rather than filed.

### What a person saw

Five consecutive live runs of golden question G-019 opened with:

    Found 20 ontology class records ...

above a list of 26, carrying 26 citations. The sentence and the list under it
disagreed, on every run, for any question returning more than twenty rows. It
has nothing to do with MeSH; that question is simply the one that exposed it.

From the person's chair this is worse than it looks. A count that contradicts
the list directly beneath it costs the reader their trust in every other number
on the page, including the ones that are right.

### The cause: one variable, two consumers, two different correct scopes

`write_node` builds `answer_findings` by slicing to
`_MAX_FINDINGS_FOR_MODEL_PROMPT`, and the comment above it gives a good reason:
it feeds `answer_ref_indices` into `build_answer_context_directive`, which the
MODEL reads, so naming a ref_index the model was never shown would be an
instruction about content that is not there. That reasoning is correct and is
untouched.

It does not transfer to `answer_summary_sentence`. That sentence is built in
code, not written by the model, and it cites every record it counts, so its
correct scope is what the READER is shown. The same variable was serving both,
and below twenty rows the two scopes coincide, which is why this survived.

### The fix

`write_node` now derives a second list, `summary_findings`, by the identical
selection over the full display list rather than the prompt slice, and passes it
to `answer_summary_sentence` alone. The filtering inside that function still
runs against `display_slots`, so it can never count a finding the answer did not
actually show.

### Proven red against the old code, by execution

Not asserted. The one-line call was temporarily reverted and the new arm run
against it:

    AssertionError: the opening counted 20, which is exactly the prompt slice,
    while the answer shows 26. This is the G-019 defect:
    'Found 20 disease records for BRCA1 [1][2]...[20]. '

That is the live defect reproduced offline, character for character. The file
was restored immediately and re-verified.

### The arm, and a defect in my own first version of it

`test_the_opening_count_matches_the_list_beneath_it` in
`tests/.../core/test_write_answer_quality.py`, 26 display rows against a prompt
slice of 20.

RECORDED RATHER THAN TIDIED AWAY: the first version of this arm read
`citation_id` off the token payloads to count what was shown, and got zero. It
failed loudly this time, but an arm that measures the shown count as zero would
pass vacuously against almost any subject, which is the same instrument-defect
family build phase 6.2 hit four times in one phase. It now counts the citation
events the answer emits, and asserts that count is above zero before comparing,
so the vacuous path is closed rather than merely avoided.

It also carries a populate check on its own premise: it asserts the row count
exceeds `_MAX_FINDINGS_FOR_MODEL_PROMPT`, because with fewer rows the two scopes
coincide and the arm would prove nothing.

### Evidence

| Check | Result |
|---|---|
| New arm against the fix | rc=0, 1 passed |
| New arm against the reverted call | rc=1, reproduces "Found 20" above 26 shown |
| Whole file | rc=0, 17 passed |
| `ruff check` on `core/graph.py` | rc=0 |

## Worker C: defect 12, revealNow cut down, step size = perItemMs

Killed the 10-run driver and its leftover worker forks first (`pkill -f
run10_clean.sh`, then `pkill -f vitest/dist/workers/forks.js` for two
forks that outlived it), confirmed by `ps` showing no vitest/npm test
process, before touching anything.

Per the coordinator's formula: `useAnswerReveal` needs roughly `minBannerMs`
1500 plus `perItemMs` 110 per item, so advancing by 110ms steps (one
item's worth of reveal per step) rather than a small fraction of one is
enough. Changed `revealNow`'s defaults from `(ms = 20_000, step = 50)`
(400 steps) to `(ms = 8_000, step = 110)` (73 steps) in all four files
(`App.test.tsx`, `phase49Premise.test.tsx`, `phase410Premise.test.tsx`,
`threadContinuation.test.tsx`), a roughly 5.5x cut in the number of real
`act()` calls per invocation, with the total virtual-time budget still well
above any measured real reveal duration (worst real case seen all night was
7697ms) so nothing that previously completed within the wait should now be
cut off early.

`phase49Premise.test.tsx` alone, three consecutive runs, no artificial
load, immediately after the cut:

- run 1: rc=0, 28s wall, 21/21 passed, worst single test 2183ms (down from
  10686ms before the cut, in the SAME position in the file).
- run 2: rc=0, 25s wall, 21/21 passed, worst single test 2459ms.
- run 3: rc=0, 21s wall, 21/21 passed, worst single test 1542ms.

Worst across all three: 2459ms against the 15000ms ceiling, 16 percent.
Comfortably under the coordinator's 7000ms "real margin" line and nowhere
near the 10000ms "still above" line. DECISION RULE APPLIED: keep the fix.
Proceeding to the moderate-load check next to confirm under contention,
per the coordinator's instruction, before calling this closed.

## Worker C: defect 12, moderate-load check, margin confirmed real

`phase49Premise.test.tsx` alone, no other test process running (checked
first), with 3 background `yes > /dev/null` processes started just before
the run and killed immediately after (moderate: 3 of 8 cores kept busy,
not per-core saturation, per the coordinator's instruction). `rc=0`, 35s
wall, 21/21 passed, worst single test 2277ms.

That is within the SAME range as the three unloaded runs (1542-2459ms),
not meaningfully worse. 2277ms against the 15000ms ceiling is 15 percent.
This is a real, load-tested margin, not an assumption: the step-size cut
(400 real `act()` calls down to 73) removed enough of `revealNow`'s own
CPU cost that the file is no longer close to its ceiling either unloaded
or under moderate contention, in direct contrast to the pre-cut version,
which failed for real in an unloaded run (10-run confirmation, run 1) at
the OLD step size.

Confirmed no leftover `yes` process after the run (`ps` clean).

DECISION RULE OUTCOME: worst case (2459ms unloaded, 2277ms under moderate
load) is comfortably under the coordinator's 7000ms "keep it" line. KEEPING
the fix in all four files, unchanged from the prior entry: `App.test.tsx`
(3 of 4 sites, 1 deliberately reverted), `phase49Premise.test.tsx` (all 6
sites), `phase410Premise.test.tsx` (1 site), `threadContinuation.test.tsx`
(2 sites), all now at the cut-down `revealNow(ms = 8_000, step = 110)`.

## Worker C: defect 12, one full-suite confirmation at the cut-down settings

The only full-suite data point on the fix before this was run 1 of the
10-run confirmation, which FAILED at the pre-cut `revealNow` settings. The
coordinator's instruction stopped the 10-run requirement rather than
extending it, so this is ONE bounded full-suite run at the cut-down
`(ms = 8_000, step = 110)` settings, not ten, to have at least one real
full-suite data point on the version actually being kept.

`npm test` (committed config, no artificial load, no other vitest process
running, checked first): `rc=0`, 85s wall, `Test Files 58 passed (58)`,
`Tests 527 passed (527)`. Notably faster than every pre-cut full-suite
measurement tonight (128-163s), consistent with the step-size cut reducing
real CPU cost across all four affected files at once.

FINAL STATE OF DEFECT 12: every affected file is green across every run
actually completed tonight at the final (cut-down) settings: `App.test.tsx`
(individual run, combined run with the other two files, full suite),
`phase49Premise.test.tsx` (3 unloaded + 1 moderate-load + full suite, 5
green runs total), `phase410Premise.test.tsx` and `threadContinuation.test.tsx`
(individual, combined, full suite). No failure at the final settings, in
any run, unloaded or under moderate load.

Per the coordinator's rule, this is enough to say defect 12's fix is
verified for the runs completed, but NOT enough to call the defect fully
CLOSED with the same confidence a full 10-run confirmation would have given
the fixed version (that confirmation was correctly cut short after
establishing the pre-cut version was broken, and was not restarted from
zero for the fixed version). `Developer_workflows.md`'s defect 12 entry is
being marked FIXED with this evidence and this caveat stated plainly,
rather than silently upgraded to a bare "FIXED" the way defect 10 was.
