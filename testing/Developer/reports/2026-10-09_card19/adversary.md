# Card 19 adversary round

Base: `1d46377b` on `fix/card19-act-complete`. Subject: the `actComplete` block of `frontend/src/hooks/useRunView.ts`. Method: vitest probes feeding event sequences into `useRunView`.

## Findings

### A-19-01: A search that starts after another search has finished sends the steps from Write back to Act

- Severity: minor (unsure whether reachable today; see below)
- What: with the fix, Act counts as over once every call that has started has a result. A call whose start frame arrives after an earlier call's result is invisible until it arrives, so the steps show Write in between and then fall back to Act. Before the fix, a planned id already on the wire kept Act open for every planned id, so this order held on Act.
- Reproduction: `useRunView` fed, one prefix at a time, `guard, think, plan(c1, c2), tool_start(c1), tool_result(c1), tool_start(c2), tool_result(c2), done`.
  - At base 1d46377b: after `tool_result(c1)` the active step is `Write` with reached `[Guard,Think,Plan,Act,Write]`; after `tool_start(c2)` it is `Act` with reached `[Guard,Think,Plan,Act]`; after `tool_result(c2)` it is `Write` again.
  - With the pre-fix block restored (`HEAD~1`'s `useRunView.ts`): after `tool_result(c1)` the active step stays `Act`.
- What a person sees: the writing banner ("is writing the answer") appears, then disappears and the handoff lines and a running search come back, then writing appears a second time. The Write step lights and then un-lights.
- Why unsure: `act_node` writes every `tool_start` before any call runs (core/graph.py, the admission loop and the start loop ahead of `_gather_planned_calls`), and pacing never reorders, so the live backend should not produce this order today. The fix moves the whole guarantee onto that backend ordering. See A-19-02 for whether anything pins it.
- NOT FIXED

### A-19-02: Nothing pins the backend order the fix now depends on, so a backend change could make the steps lie with every test green

- Severity: major
- What: the fix is correct only while `act_node` writes every `tool_start` of a run before any `tool_result`. Its own comment says so ("`act_node` writes every start before any call runs"). No backend test asserts that cross-call order; the premise gate's A2 checks each call's start precedes its own result, and the breadth and handoff tests count starts and results. The pre-fix frontend tolerated a late start for a planned id; the fixed one does not (A-19-01).
- Reproduction: in `core/graph.py`'s `act_node`, wrap the start loop as `_emit_starts(group)` and call it as `_emit_starts(first_stage)` before the first `_gather_planned_calls` and `_emit_starts(follow_ups)` right after it, so the follow-up searches announce themselves only once the first stage has returned. Then:
  - `pytest tests/system_03_search_agent/core/test_breadth_wiring.py test_phase_4_16_premise.py test_layer_handoff.py test_phase_4_16_mutation.py`: `87 passed in 15.67s`.
  - A probe running `test_breadth_wiring`'s gene question printed 9 starts, then 9 results, then 4 more starts: `LATE_STARTS ['ne-446f12c0ae0a', 'pa-a40ff51d622b', 'ne-a32e4607e791', 'ne-93f3eecef7dd']`. On the unmutated base the same probe printed `LATE_STARTS []`.
  - Fed to the fixed hook, that order is A-19-01's sequence: Write after the ninth result, back to Act on the tenth start.
- What a person sees: if the backend ever starts follow-up searches when they are built rather than all at once, the screen says "writing the answer" while four searches have not started, then goes back to searching. Nothing would turn red first.
- The frontend test added in this card pins only the skipped-call case. Nothing on either side pins "a start never follows a result".
- NOT FIXED

### A-19-03: When every planned call is skipped, the steps sit on Plan through the whole writing wait

- Severity: major (unsure how often it is reached live)
- What: the card's own case taken to its limit is not covered. `actComplete` needs at least one started call, and `planSelectedNoTool` needs the plan to have named no calls. A plan that names calls, all of which `act_node` skips (the per-query cost cap `break` on the first planned call, or the Layer 2/3 ceiling `continue` when the plan is all Layer 2/3 and the budget is already spent before Act), meets neither, so Write waits for the first text event.
- Reproduction: `useRunView` fed `guard, think, plan(c1, c2)`, then one text event, then `done`. At base 1d46377b the prefix ending at `plan` shows active `Plan`, reached `[Guard,Think,Plan]`, and it stays there until the text event, which gives active `Write`, reached `[Guard,Think,Plan,Write]`. On the backend, `act_node` with zero admitted calls writes no frame at all and hands straight to `write_node`, whose only progress marker is a `step` frame the client drops by name (`FORWARD_COMPATIBLE_EVENT_NAMES`).
- What a person sees: the steps say the search is still being planned for the 2 to 22 seconds the answer takes to write, then jump from Plan to Write with Act never lit. This is the symptom the card names, for the run where the limit bit hardest. The answer that follows carries the cap note, so the person learns afterwards that nothing was searched.
- Reachability not measured: I did not establish how often Think's own NCBI lookups spend the 20-call budget, or how often Think and Plan reach the cost cap before Act.
- NOT FIXED

### A-19-04: The block comment above the fix still says the plan's own calls hold Act open

- Severity: minor
- What: `useRunView.ts`'s comment "WRITE BEGINS WHEN ACT ENDS" (around line 432) still says Write is entered when "every tool call the run opened (by `tool_start`, or by the plan's own `tool_calls`) has a matching `tool_result`". After this card the plan's calls no longer count; only started calls do. The new card 19 comment sits a few lines below and contradicts it.
- Reproduction: `grep -n "by the plan's own" frontend/src/hooks/useRunView.ts` at 1d46377b returns the line.
- Why it matters: the next person to touch this block reads two opposite rules for when Act ends, and the stale one is the one with the measured history attached.
- NOT FIXED

Correction to A-19-04's reproduction: the phrase wraps across two lines, so that grep returns nothing. The stale text is lines 435 to 437 of `frontend/src/hooks/useRunView.ts` at 1d46377b: "every tool call the run opened (by `tool_start`, or by the plan's / own `tool_calls`) has a matching `tool_result`". `grep -n "plan's own" ` does not match either; `sed -n 435,437p` shows it.

### A-19-05: A repeated start for a call that already returned shows Write while the hook's own chip says the search is running

- Severity: minor (pre-existing, same at HEAD~1; filed because the brief asked for duplicate starts)
- What: `actComplete` is set membership, so a second `tool_start` for an id already closed changes nothing, while the chip upsert sets that chip back to `running`.
- Reproduction: `useRunView` fed `guard, think, plan(c1), tool_start(c1), tool_result(c1), tool_start(c1)`; then `RunProgress` rendered from that view. Observed: `step=Write chips=["running"] banner="Mendel is writing the answer...Found 1 record"`. Identical before the fix.
- What a person sees: nothing wrong today, because the writing banner hides the chips. Any surface that shows chips during Write would show a running search under "writing the answer".
- NOT FIXED

### A-19-06: Any text event before Act's last result shows Write while a search is still running

- Severity: minor (pre-existing; not reachable from today's backend)
- What: `writing` is `has("token") || ...`, so one text event, including a phase 8.7 listing line, enters Write whatever the open calls are.
- Reproduction: `guard, think, plan(c1, c2), tool_start(c1), tool_start(c2), tool_result(c1)`, then one text event with `placement: "listing"`, then `tool_result(c2)`. Observed: `Act` after `tool_result(c1)`, `Write` after the text event while c2 is open. Same at HEAD~1.
- Why unsure: the listing is emitted in `write_node`, which runs only after `act_node` returns, so the backend does not produce this order today. Filed because 8.7 moved text earlier once already, and nothing on the frontend checks for open calls when text arrives.
- NOT FIXED

Addendum to A-19-03, run rather than read: the cost-cap path always skips every call, never some.

- `check_per_query_cap` reads the spend so far plus one estimate, and nothing is spent between iterations of `act_node`'s admission loop, so it gives the same answer for every planned call. When it refuses one, it refuses all of them. The Layer 2/3 ceiling is the same: `calls_made()` cannot change during admission, so it skips every Layer 2/3 call or none. The card's partial case needs a plan that also holds a Layer 1 graph call; without one, the ceiling gives A-19-03's empty Act too.
- Probe: `test_breadth_wiring`'s gene question, with `cost_control.check_per_query_cap` patched to raise `QueryCapExceededError` only when called from `act_node`. The event types were `guard, cost, think, cost, plan, cost, step, token, done`, with a plan of 13 calls, no `tool_start` and no `tool_result`. `done.layer_calls_used` was 0.
- `cost` is not sent to a browser and `step` is dropped by name, so the hook sees plan, then one text event, then done. In the hook that is Plan, then Write (A-19-03's reproduction).

### A-19-07: The build report and the new test-queries line name a trigger that, by my reading, cannot skip a call

- Severity: unsure (read, not run)
- What: `build.md` says "a question that plans more than 20 live lookups left the progress steps on Act". The new line under query 98 says "a question so broad that some of the planned lookups are skipped at the 20-call limit". In `act_node`'s admission loop the ceiling test reads `call_budget.calls_made()`, and no call runs during admission, so the count is the same for every planned call. A plan of 25 Layer 2/3 calls on a fresh budget admits all 25, writes 25 starts, and the calls past 20 are refused at the transport and closed with an error result (`CallBudgetExceededError` in `_execute_planned_call`). They have start frames and results. Act closed for them before this card as well.
- When a call really is skipped with no start frame: the budget was already spent before Act began (Think's own NCBI lookups count against it), and then every Layer 2/3 call is skipped together while Layer 1 graph calls still run. With no graph call in the plan, the result is A-19-03's empty Act.
- What a person sees: the owner retesting "a broad question" per query 98 will most likely see no difference before and after, because that path never had the gap. The line will read as passing without exercising the fix.
- Reproduction: by reading only. `core/graph.py` admission loop (the `already_made = call_budget.calls_made()` check above `admitted.append(planned)`) and the transport's `call_budget.charge_one_call` at `tools/ncbi_transport.py` line 1605. I did not run a plan of more than 20 calls.
- NOT FIXED

## Verdict

PASS on the card's narrow claim, with A-19-03 a major gap in the same symptom and A-19-02 a major gap in what holds the fix in place. No finding sits inside a fix made during an earlier round of this card; A-19-01 and A-19-02 are about the fix itself.

Verified with my own probes:
- The partial skip is real and the fix moves it to Write. With `calls_made()` patched to 20 inside `act_node`, the gene question planned 13 calls, started only the 2 graph calls, and closed both before any text. Fed the same shape, the fixed hook shows Write after the last result; the pre-fix block shows Act until the first text event.
- Old and new outcomes, prefix by prefix, over 16 hand-built sequences. They differ in four: the intended skip case, A-19-01's late start, a result for an id never started while a planned id is open, and a result with no start at all.
- A-19-02's backend mutation: 87 backend tests green, and a stream with 4 starts after 9 results.
- A-19-03 on the backend: cost cap at admission gives a plan of 13 and zero tool frames.
- Emptying `idsToClose` turns 2 of 405 frontend tests red, so the existing Write-state tests do bite on the hook.

Read only, not run: A-19-07's claim that a plan of more than 20 calls skips nothing; the claim that Think's own lookups count against the 20-call budget; that no browser surface other than `App.tsx` feeds `useRunView`.

Probe files were kept outside the checkout and `git status --short` shows only the `node_modules` link.
Correction to the verdict's last line: the probe files were written inside the review checkout while they ran and were moved out afterwards (deletion is blocked by the hook). `core/graph.py` and `useRunView.ts` were restored with `git checkout` after each mutation. At the end, `git status --short` shows only the `node_modules` link, at HEAD `1d46377b`.
