# Card 29 judge report, 2026-10-15

Judge, dial position 3, one round. Subject: fix/card29-abstract-sentence at 80b28466, base b25e4c6d. Worktrees: <scratchpad>/j29 (80b28466) and <scratchpad>/j29dev (b25e4c6d). Findings are appended as established. The judge closes nothing.

## Findings

### J-29-01: The sentence never reaches a GraphQL or command-line user
- Severity: minor
- What: `adapters/graphql/types.py` `Citation` has no `snippet` field and `Citation.from_payload` drops it; `adapters/cli/render.py` has no reference to `snippet`. Only the web app shows the sentence, and MCP passes the raw payload through. Nothing breaks: both adapters fold the re-sent citation through `updates_citation` and keep one row.
- Reproduction: `<scratchpad>/judge29probes/p_graphql.py` builds a `CitationPayload(snippet="Caffeine improved performance in trained athletes.")` and calls `Citation.from_payload`. Output: `graphql Citation has snippet attr: False` / `payload snippet: Caffeine improved performance in trained athletes.`. `grep -n snippet src/system_03_search_agent/adapters/cli/render.py` prints nothing.
- Why it matters: The owner's MCP parity row (DECISIONS.md 2026-09-26) says integrations should do what the web does, and the build report claims the sentence "reaches every surface" through `CITATION_UPDATABLE_FIELDS`. That is true for the event stream only. A GraphQL or CLI user sees titles only, as they do today, so this is a gap in the claim and not a regression.
- NOT FIXED

### J-29-02: A browser tab still running develop's bundle drops the whole re-send, its grown record words with it
- Severity: minor (lasts only until a tab reloads after the deploy, or for a third-party SSE client written to the old rule)
- What: The new server re-sends a listing citation with `snippet` set, and when the summary also cites it, with a grown `claim_text`. Develop's `updatesCitation` exempts only `claim_text`, so an old client reads this send as a conflicting redefinition and keeps the first send. It also loses card 57's grown record words for that citation, which the chips match sentences against (`useRunView.ts` around line 633). Nothing crashes and nothing is listed twice.
- Reproduction: In `<scratchpad>/j29dev/frontend` (develop, b25e4c6d), a probe fed `useRunView` two sends with id k1: first `claim_text: "listing words"`, then `claim_text: "listing words plus summary words", snippet: "A sentence."`. Output: `PROBE-OLD sources: 1`. The kept source has no snippet, and the update was ignored because develop's rule rejects any `snippet` difference. The server-side rule probe (`<scratchpad>/judge29probes/p_tokenorder.py`) shows the new rule: `snippet+claim_text True`, `snippet+display_index False`, `snippet+source_url False`, `snippet+field False`, `new unknown key False`, `snippet removed later True`.
- Why it matters: Someone who keeps a tab open across the deploy sees chips matched against fewer words for one answer. The schema change is additive on the wire, but it widens the update rule, and that is a semantic change for any client that follows the old rule. The build report does not mention it. The token_order change itself is tight: it lets only `snippet` and `claim_text` change, and an unknown key or any record field still fails.
- NOT FIXED

### J-29-03: The MCP response allowlist, a manual control that is meant to need approval, was widened to get a test green
- Severity: unsure (process)
- What: `tests/.../adapters/mcp/test_no_cost_and_auth.py` `_ALLOWED_RESPONSE_KEYS` and `_CITATION_KEYS` gain `snippet`. `adapters/mcp/server.py`'s own comment says this allowlist "is a deliberate manual control, so this addition was approved by the product owner ... rather than made to get a test green". The build report says the builder added `snippet` after the test failed and cites no approval. The owner's MCP parity row (DECISIONS.md 2026-09-26) plausibly covers it, but neither the report nor the card 29 row says so.
- Reproduction: `git diff b25e4c6d 80b28466 -- tests/system_03_search_agent/adapters/mcp/test_no_cost_and_auth.py` shows `+    "snippet",` twice. build.md, "Gates": "Two failures along the way, both fixed ... the MCP allowed-keys test".
- Why it matters: The key carries public abstract text, so the data risk is low. The concern is that the control's stated rule was bypassed silently. Whoever closes this should name the approving row, or ask the owner.
- NOT FIXED

### J-29-04: The batch call runs beside the writer, but no other cap check counts it, and a cancelled pick is never charged
- Severity: minor (the real call costs about $0.00002 to $0.00005, and its bound is $0.01 against a $0.25 cap)
- What: `pick_snippets` runs in parallel with the writer and the second draft. The cap check in `_ask_batch` does see their in-flight bounds, but the batch never registers its own bound in `Harness.in_flight_usd`, so their checks cannot see it. `cost_control.check_per_query_cap` documents the rule it breaks: "two calls running at once are never each admitted against a total that leaves out the other". When the pick is late and cancelled at the 1 s grace, Jev has still billed the call, but `track_cost` never runs, so that spend is not counted against the question or the daily total. This is the same pattern as the sentence check, but that check runs in series and is awaited, while this pick can be cancelled.
- Reproduction: probe `test_probe_inflight_and_cancel_charge` in `<scratchpad>/j29/tests/system_03_search_agent/zz_judge29/` (a fake batch that sleeps). Output: `PROBE while batch in flight: in_flight_usd=0.0 cost=0.0` / `PROBE after cancel: cost charged=0.0`. The cap check itself works: with $0.245 already spent under a $0.25 cap, `test_probe_cap_near_no_spend` printed `batch_calls=0 decide_calls=0 snippets=[None, None, None] cost=0.245`.
- Why it matters: Each case costs at most a fraction of a cent per answer. Close to the cap, the writer may be admitted against a total that leaves out a call already in flight. The build report says "Cost-cap checked before, charged after", and that is true only when the pick completes.
- NOT FIXED

### J-29-05: The sentence sits inside the card's toggle, so it becomes part of the toggle's spoken name and a click on it opens the card
- Severity: minor (design and accessibility)
- What: The sentence is rendered inside `<summary>` (`AnswerScreen.tsx`, the `source-N-snippet` Typography). A native `<summary>` is the disclosure's button, and its whole text content is its accessible name. A screen reader user therefore hears the full quoted sentence, up to 500 characters, every time focus lands on each of the first five source toggles. A sighted user who clicks or drags to select the quote, for example to copy it, toggles the card open or closed. The build report records no WCAG 2.1 AA check, which `production-standards.md` requires for any UI change ("Any UI change needs a WCAG 2.1 AA accessibility check"). Colour is fine: `inkMuted` #565C65 measured 6.74:1 on #FFFFFF and about 6.2:1 on canvas #F0F0F0 (computed), above 4.5:1. 13px is a foundation size (`foundations/type.html` carries `font-size:13px`). The nearest neighbour the builder cites, `.card-note`, is the design system page's own caption style, not a product component. The values still come from foundations, so the missing design was named and not filled silently, as the rule requires.
- Reproduction: The builder's own test asserts `expect(snippet.closest("summary")).not.toBeNull()`. Probe render in `<scratchpad>/j29/frontend/src/zzJudge29.probe.test.tsx` shows the snippet span inside the source card's summary. No 1280 or 390 pixel screenshot exists (build.md, "Design gaps": "this is unchecked by eye").
- Why it matters: Keyboard and screen-reader users get a long, repeated toggle label, and mouse users cannot select the quote without toggling the card. The owner may accept this, since showing the sentence while the card is closed was the whole goal. It belongs on the design coverage table either way.
- NOT FIXED

Correction to J-29-05: the measured contrast on canvas #F0F0F0 is 5.92:1, not "about 6.2:1". It still passes 4.5:1.

### J-29-06: "Cancels the task on every way out" has no test: delete the `finally` cancel and all 36 card 29 tests stay green
- Severity: minor (the code is right today; the property is not held by any test)
- What: The build report's "Stop" row claims `write_node`'s `finally` cancels the pick on every way out. The judge removed exactly that line, `_drop_snippet_pick(state["harness"])` in `write_node`'s `finally`. The builder's wiring, snippet and contract tests all still passed. Only the judge's exception-exit probe went red.
- Reproduction: Mutation `sed 's/^        _drop_snippet_pick(state\["harness"\])$/        pass  # JUDGE MUTATION/'` on `core/graph.py` line 13737. `pytest tests/.../core/test_abstract_sentence_wiring.py tests/.../synthesis/test_snippets.py tests/.../contracts/test_citation_snippet.py -q` gave `36 passed in 3.89s`. Judge probe `test_probe_exception_exit_cancels` (it makes `build_synth_messages` raise after the pick started) gave `1 failed`. Restored byte for byte from a copy (`git diff --stat` empty). Unmutated, the same probe printed `PROBE exception exit: pick tasks created=1 cancelled=[True] fake_ran=False slot=None`.
- Why it matters: A later edit to `write_node` can drop the cancel without any test noticing. A pick nobody reads would then keep running and keep spending after a failed or stopped answer, and the pick slot would stay set on the run.
- NOT FIXED

### J-29-07: Nothing pins the write-budget clamp on the 1 s grace either
- Severity: minor
- What: `_attach_snippets` limits its wait to whatever is left of the write budget (`wait_s = min(wait_s, deadline - time.monotonic())`, `core/graph.py` line 12859). The judge replaced that line with `wait_s = wait_s`, so the pick always gets the full 1 s, even after the write budget has run out. Every card 29 test stayed green.
- Reproduction: That single-line mutation, then `pytest` over the three card 29 test files gave `36 passed in 3.80s`. Restored from a copy, and `git diff --stat` was empty.
- Why it matters: On a slow answer whose writer has already used its budget, a regression here adds up to 1 s past the budget, and the 20 s rule is the owner's. Today's code is correct. The finding is only that no test guards it.
- NOT FIXED

### J-29-08: After a rollback, every answer saved while card 29 was live reopens over MCP with all its citations missing
- Severity: minor (it bites only on a revert, but a revert is the remedy a bad release gets)
- What: Every citation event now carries a `snippet` key, `null` included, because `model_dump()` keeps None fields, and capture stores payloads verbatim (`feedback/contracts.py`, "stored exactly as the event carried it"). Develop's `CitationPayload` is `extra="forbid"`. MCP's `_reopened_citations` validates each stored citation strictly. So develop's code, which is what a rollback runs, rejects every citation saved during the card 29 window, including ones whose `snippet` is null. REST reopen types citations as `list[Any]`, so the web is unaffected. Build.md says "no migration is needed", but it never checks rollback.
- Reproduction: `<scratchpad>/judge29probes/p_saved.py` dumps two `CitationPayload`s with the branch code, one with `snippet=None` and one with a sentence, into `saved.json`. Fed to `_reopened_citations` running on develop (`<scratchpad>/j29dev`), the output is `develop MCP reopen of rows saved by card 29: published=0 citations_omitted=2`. The same input on the branch code gives `published=2 citations_omitted=0` (the probe prints the same label for both runs, but the second ran in `<scratchpad>/j29`).
- Why it matters: If card 29 is reverted, an MCP user who reopens a past answer from that window gets the answer text with no sources, so every claim loses its link. The usual mitigation for additive fields, emitting the key only when set (`exclude_none`, or leaving the key off when there is no sentence), would also shrink the window to the first five papers only.
- NOT FIXED

### J-29-09: A reopened answer drops the sentence the person saw when they asked (disclosed by the builder)
- Severity: minor (disclosed in build.md "Saved answers" and query 112, not a regression)
- What: `toHistoryAnswerCitation` in `frontend/src/lib/api.ts` and `SavedAnswerScreen.tsx` do not read `snippet`, so an answer opened from history shows titles only. The stored row does carry the sentence: capture keeps the later send in the earlier send's place via `one_per_citation_id`, and the judge confirmed this from the code path, not from a live save.
- Reproduction: `grep -n snippet frontend/src/lib/api.ts frontend/src/components/screens/SavedAnswerScreen.tsx` in `<scratchpad>/j29` prints nothing.
- Why it matters: From the user's chair, the same answer looks different the second time they open it, and the sentence they relied on is gone. That breaks the owner's "I see" in the history view. It is a small follow-up, and the owner should decide whether it ships with the card or after it.
- NOT FIXED

### J-29-10: A long abstract is cut at 2,000 characters, and its cut-off tail can be shown in quotes as "the sentence"
- Severity: major (a quoted, half-finished sentence presented as the paper's own words can change what the paper says)
- What: `_snippet_papers` takes the abstract from `synth_findings`. `SynthFinding.field_value` is clipped at `MAX_FIELD_VALUE_CHARS = 2000` (`synthesis/findings.py:91`, `_clip` is `value[:limit]`), which can cut mid-sentence. `split_abstract_sentences` keeps the last piece whenever it has at least 8 words and a verb-like token. `candidate_window` always keeps the LAST 8 sentences of a long abstract, which is the builder's own change ("the closing sentences state the finding"). So the cut fragment is always offered, and it is usually where the conclusion sits. `verified_sentence` passes it, because it IS a substring of the clipped text. The card then shows it in straight double quotes, as a complete verbatim sentence.
- Reproduction: Probe `test_probe_clipped_abstract_fragment` in `<scratchpad>/j29/tests/system_03_search_agent/zz_judge29/` runs the real `write_node` path (`_papers_state` builds an efetch record, then structured fields, then findings) with one 2,028-character abstract whose last sentence is "Conclusion: caffeine improved time trial performance in trained cyclists but this benefit disappeared entirely in participants who habitually consumed more than three cups daily." The fake classifier picks whichever option does not end in a period. Output: `PROBE last offered option: 'Conclusion: caffeine improved time trial performance in trained cyclists but this benefit disappeared entirely in participants who habitually consumed'` and `PROBE shown: {'https://pubmed.ncbi.nlm.nih.gov/30000000/': 'Conclusion: caffeine improved time trial performance in trained cyclists but this benefit disappeared entirely in participants who habitually consumed'}`. A real classifier asked for "the sentence that most directly answers the question" has every reason to pick a conclusion fragment.
- Why it matters: Many PubMed abstracts, especially structured clinical ones, run past 2,000 characters, and the cut falls in the conclusions. A reader sees a quoted claim that stops before its qualifier, for example before "...only in the subgroup" or "...although not significant". That is exactly the "confident wrong record" the owner ranks worse than a missing one. The substring check cannot catch it, because the text is word for word, just incomplete. Nothing in the builder's tests uses an abstract over 2,000 characters. The builder's 11 live runs showed only sentences ending in a full stop, which this neither confirms nor rules out.
- Inside this phase's new code: yes. The tail-weighted window is the builder's change to the lifted splitter.
- NOT FIXED

J-29-10, real-data addendum: the judge ran two live runs, `Does fish oil prevent heart attacks?` (Plain language) and a vitamin D question (Researcher), then fetched the ten cited papers' abstracts from E-utilities (`<scratchpad>/judge29probes/abs.xml`). Joined AbstractText lengths: 2 of 10 exceed 2,000 characters (40982278: 2632; 41851014: 2394). Both were cited in the live fish oil answer. Run through the branch's own `candidate_window(split_abstract_sentences(text[:2000]))`, PMID 40982278's last offered candidate is the cut fragment `'For Viadin H, those shown a label stating "Heart Health" or "Supports Heart Function" were more likely to report the supplement prevents heart attack or heart failure, while those shown a label stating "Brain Health" or "Supports Cog'`. That is a mid-word cut, offered to the classifier in a real answer. In that live run the classifier picked "none" for this paper, so nothing wrong was shown that time. The tool's real abstract text may carry section labels, so these lengths approximate.

### J-29-11: Under the guard classifier the card does nothing, so production shows no sentence until the switch flips (disclosed deviation)
- Severity: unsure (disclosed in build.md "Deviations"; the owner's row of 2026-10-15 does not mention this condition)
- What: `_start_snippet_pick` returns at once unless `_jev_decides()`. The code default for `CLASSIFIER_PROVIDER` is the guard tier, and build.md says production runs on that default. Develop sets `jev` (HANDOFF.md line 18).
- Reproduction: Probe `test_probe_guard_classifier_off` ran `write_node` over 2 papers. Output: `CLASSIFIER_PROVIDER=None: batch_calls=0 snippets=0`, `'guard': batch_calls=0 snippets=0`, `'JEV': batch_calls=1 snippets=2`, `' jev': batch_calls=1 snippets=2`. The gate behaves as claimed, and it is case- and space-tolerant.
- Why it matters: The owner's words are "I see the sentence". When this ships to production, users will not see it, and nothing in the product says so. The reason is sound (a guard-tier call takes about 2 s and would breach the 1 s grace). The owner should know the card takes effect only with the classifier switch, and the release note should say so.
- NOT FIXED

### J-29-12: A review's "this review covers..." sentence can be shown as the sentence that answers the question
- Severity: minor (disclosed by the builder; the judge's own live runs did not reproduce it)
- What: `_NONE_CRITERION` asks for "none" only when the closest sentence is "off-topic, too general, or about a different aspect". A scope sentence ("This review focuses on metformin's mechanisms...") passes that bar. The builder's own reading counted 3 of 10 shown sentences as scope or background, not findings (build.md, "Live proof"). The judge did not re-read those runs; this is evidence the judge read, not reproduced. In the judge's two live runs all 8 shown sentences were finding statements. Vitamin D, Researcher: 5 of 5 papers, 14.18 s, $0.0180. Fish oil, Plain language: 3 of 5 papers, 7.53 s, $0.0101. For example: "The meta-analysis showed that vitamin D supplementation had a significant effect on overall reduction in depression symptom scores (SMD = -0.15, 95 % CI [-0.26, -0.04])."
- Reproduction: build.md table rows for "Benefits of Metformin in Attenuating the Hallmarks of Aging" and "Metformin: A Review of Potential Mechanism...", both marked "Weak". Judge live output is pasted in the verdict section below.
- Why it matters: Under the user's words "the one sentence ... that answers my question", a scope sentence is a mild letdown, not a wrong fact. The fix is a criteria-text change, which is the owner's call. No word list would be needed.
- NOT FIXED

## Verdict

FIX FIRST: J-29-10. A long abstract's cut-off tail can be shown in quotes as the paper's own sentence. This is in the card's new code, the builder's tail-weighted window over the 2,000-character clip. It is round 1, so it sits in no earlier review fix. Cheap to fix alongside it: J-29-08 (send `snippet` only when set), J-29-06 and J-29-07 (two missing tests). Everything else is minor, unsure, or a disclosed deviation for the owner.

### Gates (judge's own runs, <scratchpad>/j29 at 80b28466)

| Gate | Result |
|---|---|
| `ruff check` (no path) | All checks passed! |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | exit 0 (Skipped 2 files) |
| `pytest tests/system_03_search_agent -m "not integration" -q` | 6985 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 277.51s; exit 0 |
| `npm run build` | built in 299ms, exit 0, only the existing large-chunk warning |
| `npx vitest run` | Test Files 71 passed (71), Tests 645 passed (645) |

### Verified with the judge's own probes

- Five-paper mapping: each paper got its own abstract's sentence, "none" and an out-of-range option showed nothing (`PROBE paper 0..4`). An off-by-one mutation of the mapping turned 2 builder tests and 1 judge probe red, and was restored.
- Late pick: answer took 1.052 s with the default 1.0 s grace against 0.055 s when the pick was fast. The task was cancelled (`task_cancelled=True`). An exception exit cancels it too (`cancelled=[True]`, `slot=None`).
- Cost cap near ($0.245 of $0.25): no batch, no fallback, no sentence. A normal pick is charged (`cost=2e-05`).
- Guard classifier: no call. `jev`, any case: one call.
- Wire: a listing send then a re-send with the sentence gives one source with it. A conflicting re-send (new number) is ignored. GraphQL fold, CLI renderer and `one_per_citation_id` each keep one citation, with no warning.
- token_order: only `snippet` and `claim_text` may change. A changed `display_index`, `source_url`, `field` or an unknown key is still rejected.
- Old clients: develop's CLI lenient decoder reads the new frame, develop's web bundle does not double-list (J-29-02 for what it loses), and develop's strict model rejects the new frame (J-29-08 for the rollback effect).
- Security: a hostile snippet (`<img onerror>`, a markdown link, a javascript: link) renders as inert text, with 0 img, 0 a and 0 strong elements. The model can only return an option id, which maps back to code-held text from the same paper.
- No hardcoded decisions: no test-question word in the new source. The prompt is fixed and generic. The splitter's abbreviation and auxiliary-verb lists filter sentence shape only, and choose no meaning.
- Live, develop's settings, $0.028 total. Vitamin D, Researcher: 14.18 s, $0.0180, 5 of 5 papers with a sentence, 3 re-sends. Fish oil, Plain language: 7.53 s, $0.0101, 3 of 5, 3 re-sends. All shown sentences were complete finding statements.

### Only read, not probed

- The builder's 11-run timing table and their sentence-quality judgement (J-29-12).
- That the batch's fallback (`decide()` per paper, Jev then guard tier) behaves live.
- 1280 and 390 pixel rendering. No screenshot was taken by the builder or the judge (J-29-05).
- That a live saved row holds the sentence (only the code path was read, J-29-09).

### Is anything worse than develop for the person asking?

- Speed: no measurable change in the judge's two live runs. The worst case adds 1 s when the pick is slow and the writer fast.
- Wrong sentence: J-29-10 can show a quoted, cut-off claim on long abstracts. The fix is cheap.
- Broken card: none found.
- History and production: a reopened answer and production (guard classifier) look as they do today (J-29-09, J-29-11).
