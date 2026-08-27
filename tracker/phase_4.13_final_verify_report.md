# Build phase 4.13 final verification report

Branch: `phase/4.13-durable-history`, verified at `2533911`.
Run 2026-08-27 from fresh context, against the code, the live database, a real browser and the tests, never against a summary. Every mutation ran in a throwaway git worktree at `HEAD` and was restored byte-identically with a SHA-256 assertion.

## Verdict: FAIL

One reachable major, F-4.13-FV-01, reproduced through the real UI: a rail row restored from an earlier day has its own source count and date overwritten with the counts of a run it does not represent. That is the F-4.8-J-01 fabrication class, and it is the very outcome F-4.13-A-07 was filed for, reached by a route A-07's fix cannot close.

Everything the product owner authorised round 3 to fix is fixed, and every claim round 3 made about its own work held up when re-derived. F-4.13-RV-01, RV-02 and RV-03 are closed with measured evidence. The defect below is not in round 3's code and not in any fix commit; `git blame` puts it two weeks before this phase opened, made reachable by T-4.13-03's original build.

## Table of contents

- [Verdict: FAIL](#verdict-fail)
- [The stop condition, and why it did not fire](#the-stop-condition-and-why-it-did-not-fire)
- [Check 1: F-4.13-RV-01, the rail row's identity](#check-1-f-413-rv-01-the-rail-rows-identity)
- [Check 2: the two invariants the fix claims to preserve](#check-2-the-two-invariants-the-fix-claims-to-preserve)
- [Check 3: F-4.13-RV-02, what a JSONB column can actually hold](#check-3-f-413-rv-02-what-a-jsonb-column-can-actually-hold)
- [Check 4: per-field honesty at the fetch boundary](#check-4-per-field-honesty-at-the-fetch-boundary)
- [Check 5: mutation testing every arm round 3 added](#check-5-mutation-testing-every-arm-round-3-added)
- [Check 6: the three suites](#check-6-the-three-suites)
- [Judgement on the limitation round 3 declared](#judgement-on-the-limitation-round-3-declared)
- [Findings filed by this round](#findings-filed-by-this-round)
- [Findings closed by this round](#findings-closed-by-this-round)
- [Ticket dispositions](#ticket-dispositions)
- [Tree cleanliness](#tree-cleanliness)

## The stop condition, and why it did not fire

Two of the five findings below sit inside code round 3 wrote. Neither is a defect in the shipped product, and the reasoning is stated here rather than buried, so the product owner can overrule it without reconstructing it.

- F-4.13-FV-03, inside `7778ea5`: the `local-` namespace cannot collide with a server `trace_id` because every shipped surface mints a UUID. That premise is true, and it is enforced nowhere and written down nowhere. No caller can reach it; the trigger is a direct database write.
- F-4.13-FV-04, inside `2be37b3`: the `Number.isFinite` half of the new type guard is pinned by no arm. The guard is present and correct; the server cannot emit a non-finite count.

The stop condition exists for a fix whose APPROACH is wrong, which is what F-4.13-RV-01 was: filter-then-unshift was structurally incompatible with a positional id, and the outcome was reachable by ordinary use. Neither of these two is that. Both are the trigger class this phase has already twice merged open with product-owner knowledge (F-4.13-A-02, F-4.13-RV-02), and both leave the product strictly better than before the fix. The round therefore completed rather than halting, and the FAIL rests on F-4.13-FV-01, which is in nobody's fix.

## Check 1: F-4.13-RV-01, the rail row's identity

PASS, with one residual filed as F-4.13-FV-03.

The regression arm is not vacuous, re-derived rather than accepted. Reverting `id: entryId` to `id: ${current.length}` in a throwaway worktree:

```
MI1 rail id reverts to String(current.length) -> Tests 1 failed | 19 passed (20)
   RESTORED-OK a9ca758c6974b307be5e3deffedab6b5b47487eca9934602717d080eb6f79e4d
```

The two id spaces cannot collide for any `trace_id` a shipped surface can produce. All four surfaces were read, not assumed: `web_sse/app.py:1268`, `mcp/server.py:765`, `graphql/schema.py:306` and the CLI each mint `str(uuid.uuid4())`, and none accepts a caller-supplied `run_id`. `interactions.trace_id` is `UNIQUE`, so two restored rows cannot share an id either.

They CAN collide for a `trace_id` that is not a UUID, and nothing in the product says they cannot. Measured with one server row whose `trace_id` is the string `local-1`:

```
AssertionError: expected 'MY OWN NEW QUESTION' to be 'HOSTILE RESTORED ROW'
```

That is F-4.13-RV-01's exact user-visible outcome, reproduced through the fix that closed it. Filed as F-4.13-FV-03, latent.

The counter cannot reset or repeat within a session, measured rather than reasoned:

- Unmount and remount, then the full ask, re-ask, ask sequence: each row runs its own question. PASS.
- Under `<StrictMode>`, the same sequence: each row runs its own question. PASS. The mint sits outside the state updater, so React's double invocation of the updater cannot advance it, and the counter is module-scoped so a remount cannot reset it while stale rows are on screen.
- Across a full page reload the counter does reset, and that is safe for the same reason the id spaces are separate: after a reload the only rows present come from the server and carry `trace_id` ids.

The F-4.13-A-07 fix was not undone. A restored row re-asked from the rail moves to the top:

```
before: ['ROW A', 'ROW B', 'ROW C']
click ROW C, createRun receives "ROW C"
after:  ['ROW C', 'ROW A', 'ROW B']
```

## Check 2: the two invariants the fix claims to preserve

One holds. One does not, and the one that does not is where the FAIL comes from. The code comments were treated as claims to test, not as evidence, which is the discipline F-4.13-RV-01 was filed for.

`mergeServerHistory`'s de-duplication on `traceId`: HOLDS. A run this tab took is not shown twice when the server echoes it back, and the merge is idempotent under a double-mounted effect, measured under `<StrictMode>` where the seeding effect runs twice:

```
rail after two seeding passes: ['SERVER ROW ONE', 'SERVER ROW TWO']
```

"At most one item exists per question text": DOES NOT HOLD. `mergeServerHistory` keys on `traceId` and never on question text, deliberately and for a good reason its own docstring gives, so the same question asked on two days is restored as two rows:

```
rail rows sharing one question text: 2
```

Only one consumer of that invariant is safe, and it is safe for a reason the comment does not give: `ask`'s `traceId` write is additionally guarded on `item.traceId === undefined`, and every restored duplicate carries a `traceId`. The unguarded consumer is the meta effect at `App.tsx:543-556`, and it fabricates. Measured end to end with a hand-driven stream, so the seeding fetch resolves between the ask and the `done` frame:

```
before the run lands: ['REPEATED QUESTION',
                       'REPEATED QUESTION9 sources · Aug 1']
after  the run lands: ['REPEATED QUESTION4 tools · 3 sources from 2 layers',
                       'REPEATED QUESTION4 tools · 3 sources from 2 layers']
```

The 1 August row's own source count and date are gone, replaced by a claim about a different run. Filed as F-4.13-FV-01, major, live-reachable.

A second, milder consequence of the same broken invariant, measured separately: re-asking a repeated question collapses the rail from three rows to two, silently dropping a distinct historical run. Filed as F-4.13-FV-02, minor.

## Check 3: F-4.13-RV-02, what a JSONB column can actually hold

PASS, at both layers.

`list_history` called DIRECTLY, not through the endpoint, against the real `search_agent_users` database. Sixteen stored `citations` shapes, each seeded beside a well-formed sibling by direct parameterised INSERT:

```
scalar int              -> no raise | bad.citation_count=None | sibling survives=True (count=2)
scalar negative int     -> no raise | bad.citation_count=None | sibling survives=True (count=2)
scalar float            -> no raise | bad.citation_count=None | sibling survives=True (count=2)
huge int (30 digits)    -> no raise | bad.citation_count=None | sibling survives=True (count=2)
string                  -> no raise | bad.citation_count=None | sibling survives=True (count=2)
empty string            -> no raise | bad.citation_count=None | sibling survives=True (count=2)
bool true               -> no raise | bad.citation_count=None | sibling survives=True (count=2)
bool false              -> no raise | bad.citation_count=None | sibling survives=True (count=2)
JSON literal null       -> no raise | bad.citation_count=None | sibling survives=True (count=2)
nested object           -> no raise | bad.citation_count=None | sibling survives=True (count=2)
empty object            -> no raise | bad.citation_count=None | sibling survives=True (count=2)
deeply nested array     -> no raise | bad.citation_count=1    | sibling survives=True (count=2)
array of scalars        -> no raise | bad.citation_count=3    | sibling survives=True (count=2)
empty array             -> no raise | bad.citation_count=0    | sibling survives=True (count=2)
array of objects        -> no raise | bad.citation_count=2    | sibling survives=True (count=2)
array with nulls        -> no raise | bad.citation_count=3    | sibling survives=True (count=2)

FAILURES: none
```

No shape raises. Every non-list yields `None` rather than a guess. The JSON literal `null` is unreadable rather than zero, which is the distinction the fix argues for and which it actually delivers.

The docstring's claim that only `citations` needed a guard is true rather than merely confident. `\d interactions` shows `trace_id`, `created_at`, `query_text` and `trust_signal` all `NOT NULL`, so no other column this module reads can hand back a value it did not expect.

Through the real endpoint with a real caller, ten scenarios:

```
3 good + JSONB scalar 5                              -> 200 count=3 omitted=1
3 good + JSONB string "abc" (the fabrication probe)  -> 200 count=3 omitted=1
3 good + JSONB null                                  -> 200 count=3 omitted=1
3 good + JSONB object                                -> 200 count=3 omitted=1
3 good + JSONB bool                                  -> 200 count=3 omitted=1
3 good + 3000-char query_text                        -> 200 count=3 omitted=1
2 good + scalar + over-long (two drop reasons)       -> 200 count=2 omitted=2
ALL FOUR rows bad                                    -> 200 count=0 omitted=4
5 rows, newest 2 bad, limit=2                        -> 200 count=0 omitted=2
all-good control (populate-check)                    -> 200 count=3 omitted=0
   control citation_counts: [1, 1, 1]

FAILURES: none
```

The fabricated `citation_count: 3` for a JSONB string `"abc"` is gone. No bad row costs a sibling on any path. `omitted_count` cannot under-report, and that is proven by mutation rather than by reading: deleting its increment from the new none-branch turns the disclosure arm red.

## Check 4: per-field honesty at the fetch boundary

PASS on the property the fix claims. Sixteen raw JSON bodies through the real `fetchHistory`:

```
citation_count 1e999 (Infinity)  -> [{"trace_id":"a","question":"q"}]
citation_count -1e999            -> [{"trace_id":"b","question":"q"}]
citation_count null              -> [{"trace_id":"e","question":"q"}]
citation_count []                -> [{"trace_id":"f","question":"q"}]
citation_count "3"               -> [{"trace_id":"g","question":"q"}]
citation_count true              -> [{"trace_id":"h","question":"q"}]
citation_count 0                 -> [{"trace_id":"i","question":"q","citation_count":0}]
asked_at 1                       -> [{"trace_id":"l","question":"q"}]
asked_at true                    -> [{"trace_id":"m","question":"q"}]
asked_at "not-a-date"            -> [{"trace_id":"k","question":"q","asked_at":"not-a-date"}]
trust_signal 7                   -> [{"trace_id":"n","question":"q"}]
question 42 (required field)     -> []
trace_id null (required field)   -> []
```

A bad optional field costs that field and nothing else: every row keeps its question. A bad REQUIRED field drops that row and never the response. Nothing is coerced: `citation_count: 0` survives as `0`, not as absent, and `asked_at: "not-a-date"` is kept as a string and refused one layer later by the validity guard, which is the division of labour the corrected comment describes and it is accurate.

`citation_count` can no longer render a count nothing counted, for the shapes round 3 named. It still can for two it did not, measured through the rendered rail:

```
NEG COUNT-5 sources
FLOAT COUNT2.5 sources
STRING COUNT
INF COUNT
ZERO DATEJan 1
NUM DATE
GOOD ROW3 sources · Aug 27
```

A count of sources cannot be `-5` or `2.5`, and `asked_at: "0"` produces a real-looking `Jan 1` because `new Date("0")` is a valid date. All three are refused by the server's own response model, so they are latent. Filed as F-4.13-FV-05. The last line is the populate-check: a well-formed row still renders correctly.

## Check 5: mutation testing every arm round 3 added

Thirteen mutations, one at a time, in a throwaway worktree. Every product file was restored byte-identically before the next, asserted by SHA-256. Baselines: backend `45 passed` across the two history test files, `src/lib/api.fetchHistory.test.ts` `8 passed`, `src/App.test.tsx` `20 passed`.

| Mutation | Result |
|---|---|
| MB1 `_citation_count` reverts to `len(stored or [])` | CAUGHT, 6 failed |
| MB2 `_citation_count` returns 0 instead of `None` | CAUGHT, 6 failed |
| MB3 handler's `citation_count is None` branch disabled with `if False` | MISSED, 45 passed |
| MB4 that branch drops the row WITHOUT disclosing it | CAUGHT, 1 failed |
| MB5 `HistoryItem.trace_id` `max_length` 64 to 63 | CAUGHT, 1 failed |
| MB6 `HistoryItem.citation_count` drops `ge=0` | CAUGHT, 1 failed |
| MB7 `HistoryItem.citation_count` becomes nullable | CAUGHT, 1 failed |
| MF1 drop `.map(withValidatedOptionalFields)` | CAUGHT, 1 failed |
| MF2 `asked_at` type check always true | CAUGHT, 1 failed |
| MF3 `citation_count` drops `Number.isFinite` | MISSED, 8 passed |
| MF4 all three optional fields dropped unconditionally | CAUGHT, 1 failed |
| MF5 `trust_signal` type check always true | CAUGHT, 1 failed |
| MI1 rail id reverts to `String(current.length)` | CAUGHT, 1 failed |

Where this agrees with round 3's own report: every arm round 3 added is attributable to at least one mutation it catches, and the RV-01 regression clause, the RV-02 clauses and the two RV-03 boundary arms are all non-vacuous. MB3 reproduces the limitation round 3 declared for itself, at a wider scope (45 green across both files, against the 28 round 3 measured in one).

Where it disagrees: round 3 reported no undeclared misses. MF3 is one. The `Number.isFinite` half of the new guard carries a comment stating its entire reason and no arm can distinguish it from its own absence, because the clause that owns the function tests `"abc"` and `{}`, and the bare `typeof` half alone catches both. Filed as F-4.13-FV-04.

Every restore verified:

```
src/system_03_search_agent/feedback/history.py      f769932e...4c85d
src/system_03_search_agent/adapters/web_sse/app.py  cad05f79...7433c
frontend/src/App.tsx                                a9ca758c...9e4d
frontend/src/lib/api.ts                             3fa78189...8692
```

Those four hashes are identical to the same files' hashes in the main checkout and to their `HEAD` blobs.

## Check 6: the three suites

All three re-derived by this round, not taken as reported.

Backend, run in the worktree at `HEAD`:

```
4126 passed, 159 skipped, 1 xfailed, 5 warnings in 117.25s (0:01:57)
```

Frontend vitest:

```
Test Files  18 passed (18)
      Tests  234 passed (234)
```

`tsc --noEmit` exit 0. `npm run build` exit 0, `dist/assets/index-Dzl-dErW.js 394.31 kB`.

Playwright, against the real browser and the real backend on the fixed e2e ports:

```
1 failed
2 skipped
47 passed (1.1m)
```

The one failure is the documented pre-existing one, confirmed still that one and still for that reason:

```
[chromium] › e2e/query-stream-and-stop.spec.ts:100:3 › a signed-in query streams
  through the pipeline and produces an answer
  Error: expect(locator).toBeVisible() failed
  Locator: getByTestId('answer-cap')
  Error: element(s) not found
  > 119 |     await expect(page.getByTestId("answer-cap")).toBeVisible({ timeout: 30_000 });
```

The two skips are the two live diagnostics that skip without `RUN_LIVE_DIAGNOSTICS=1`.

## Judgement on the limitation round 3 declared

Round 3 kept an `if entry.citation_count is None` branch in the handler that no black-box arm can distinguish from `HistoryItem.citation_count`'s non-nullable `int` refusing the same row, measured it, declared it, and pinned the annotation the redundancy rests on.

Agreed. It is the right call, and it is not an untested branch dressed as defense in depth, for three reasons that were checked rather than assumed:

- The measurement reproduces, wider than round 3 claimed: `if False` leaves 45 green across both history test files.
- The fallback the redundancy rests on is genuinely pinned, and I proved that with a mutation round 3 did not run: widening `citation_count` to a nullable `int` turns `test_citation_count_is_not_nullable` red. So if the annotation were ever loosened, an arm fires, and the explicit branch is then the thing still withholding the row. The two are not independent controls, they are a control and a guard on the assumption that control depends on, which is the honest shape.
- The declaration is in the gate's own file, not only in the commit message, which is what `goal-contracts` asks for.

The one correction: "defense in depth" overstates it, because the two paths are not independent. Calling it what it is, the decision stated at the point the decision is made, is the framing the docstring already uses, and it is the accurate one.

## Findings filed by this round

| ID | Severity | Reachability | One line |
|---|---|---|---|
| F-4.13-FV-01 | major | LIVE-REACHABLE, reproduced | A restored row from an earlier day is relabelled with the current run's counts. Incomplete fix of F-4.13-A-07; the defective line predates the phase |
| F-4.13-FV-02 | minor | LIVE-REACHABLE, reproduced | The "at most one item per question text" rule is false after a merge, and re-asking then silently drops a distinct historical row |
| F-4.13-FV-03 | minor | LATENT | The `local-` and `trace_id` id spaces rest on an unenforced, unwritten premise. Inside round 3's fix `7778ea5` |
| F-4.13-FV-04 | minor | LATENT | `Number.isFinite` is pinned by no arm. Inside round 3's fix `2be37b3` |
| F-4.13-FV-05 | minor | LATENT | `-5`, `2.5` and `"0"` still render a count or a date nothing measured |

## Findings closed by this round

Closed with pasted evidence, each in its own row in `tracker/phase_4.13.md`: F-4.13-RV-01, F-4.13-RV-02, F-4.13-RV-03, F-4.13-J-01, F-4.13-J-02, F-4.13-J-03, F-4.13-J-04, F-4.13-A-01, F-4.13-A-02, F-4.13-A-03, F-4.13-A-08, F-4.13-A-10.

Two of those twelve, F-4.13-A-01 and F-4.13-A-03, are closed on the strength of arms that round 2 mutation-proved and that ran green in this round's own full suite, rather than on a live re-trigger this round performed. That distinction is stated in their rows rather than blurred.

Left open, and correctly so: F-4.13-02 and F-4.13-A-04, both recorded product-owner decisions and not re-litigated here; F-4.13-A-05 and F-4.13-A-06, neither in scope for round 3, with A-06 confirmed still live (the coverage section still says fifty rows where the shipped default is twenty); F-4.13-A-07 and F-4.13-A-09.

## Ticket dispositions

| Ticket | Disposition | Reason |
|---|---|---|
| T-4.13-01 | `in-progress` to DONE | `list_history`'s whole contract is correct and mutation-proven. Owner scoping, the NULL-owner refusal, the total order and the real SQL `LIMIT` were proven by earlier rounds; this round added the stored-value contract, sixteen JSONB shapes with no raise and no guess, and both reverting mutations caught |
| T-4.13-02 | `in-progress` to DONE | Every bound the response model claims is pinned by an arm that fires when it is removed (MB5, MB6, MB7). Degradation is honest and `omitted_count` cannot under-report (MB4). The guest-liveness refusal and the duplicate-`limit` refusal are held by arms round 2 mutation-proved and this round ran green |
| T-4.13-03 | NOT done, BLOCKED | F-4.13-FV-01 is a defect in this ticket's own deliverable: `mergeServerHistory` puts two rows carrying one question text in the rail, and the rail then states one run's numbers about another run |
| T-4.13-04 | DONE, unchanged | Closed by the judge round |
| T-4.13-05 | `in-progress` to DONE | Round 3's frontend arms are real and non-vacuous: MF1, MF2, MF4, MF5 and MI1 all caught. One gap in them is filed as F-4.13-FV-04 rather than left in the ticket |
| T-4.13-06 | `todo`, unchanged | Doc drift is expected red while this ticket is open |

## Tree cleanliness

Every mutation, every probe and every suite in this round ran inside a throwaway git worktree at `HEAD`, created for this round and removed at the end of it. No product file in the main checkout was written at any point, and the four files the round mutated are byte-identical to their `HEAD` blobs:

```
IDENTICAL  src/system_03_search_agent/feedback/history.py      f769932e...
IDENTICAL  src/system_03_search_agent/adapters/web_sse/app.py  cad05f79...
IDENTICAL  frontend/src/App.tsx                                a9ca758c...
IDENTICAL  frontend/src/lib/api.ts                             3fa78189...
```

`git status` on the main checkout, before this report and its two tracker edits were written:

```
On branch phase/4.13-durable-history
Untracked files:
	required-paths.xml
	unit-results.xml
```

Both untracked files predate this round (timestamps 12:07 and 12:09, against a round that started after 15:00) and are junit artifacts left by an earlier gate run. They are not this round's and were left alone.
