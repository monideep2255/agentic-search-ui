# Phase 8.7 judge round

Base: 72ab2cd9f85745e91c9ea839a04fd2c773b65bb4 (origin/phase/8.7-answers-sooner). Reviewer: independent judge, one round. Findings appended as established.

## Findings

### Test runs (judge's own, at base 72ab2cd9)

- core: 1437 passed, 56 skipped, 1 deselected, 2 warnings in 58.47s
- synthesis: 745 passed, 10 skipped, 1 xfailed in 4.66s
- adapters: 857 passed, 2 warnings in 34.61s
- contracts: 214 passed in 0.28s
- harness: 447 passed in 23.34s
- guardrail: 347 passed in 67.34s
- vitest (hooks, screens, the two App stop files): Test Files 32 passed (32), Tests 253 passed (253)
- tsc --noEmit -p .: exit 0

Green suites are part of what is under review; they are not evidence on their own.

### F-8.7-J01: The honest-gap clause says a record lacks clinical features when its own definition describes them
- Severity: major
- File: src/system_03_search_agent/synthesis/answer_layout.py (`records_lack_field`), wired from core/graph.py `_asked_field`
- What: `records_lack_field` looks only for a non-empty `clinical_features` field. A MedGen record whose `definition` (a field `ncbi_eutils_actions.py:878` and `graph.py:7547` carry for MedGen) describes the features still reads as lacking them, so the opening line tells the reader the record "does not give clinical features" while that same record [1] describes them. With the lead sentence (card 2), the model's grounded sentence quoting that definition can open the answer and the count line right after it then denies it.
- Reproduction (offline, the module's own functions): a Disease finding titled "Marfan syndrome", its row `{"title": "Marfan syndrome", "definition": "A systemic disorder of connective tissue with ocular features (ectopia lentis), skeletal features (arachnodactyly, tall stature) and aortic root dilatation.", ...}` and a `definition` finding in `all_findings`. Output: `lack: True` and `Found 1 disease record for Marfan syndrome: Marfan syndrome [1], which does not give clinical features.` The same holds for an Article finding whose abstract lists features (`lack: True`, "... none of which gives clinical features.").
- Why it matters: the brief's own bar, "the gap clause never claims a record lacks something it has". A reader is told the evidence is silent when the cited record is not; a confident wrong statement about the record, on the exact question type (features) the clause exists for.
- Smallest fix: say what was checked, not what the record contains ("MedGen lists no clinical features for it"), which is the existing true statement; or suppress the clause whenever any counted record carries free-text descriptive fields (definition, summary, abstract), or whenever a model sentence leads.
- NOT FIXED

### F-8.7-J02: The gap clause speaks about features that were never read, undoing F-8.1-J11
- Severity: major
- File: src/system_03_search_agent/synthesis/answer_layout.py (`records_lack_field`); core/graph.py `_asked_field`
- What: graph.py's feature-row builder (around line 7850) distinguishes three cases on purpose (F-8.1-J11): features listed, "read and lists none" (a stated-absence row), and "could not be read" (no row at all: "Nothing is said about its features, because nothing is known"). `records_lack_field` sees no `clinical_features` value in the third case and the opening line then says "which does not give clinical features". The same happens for a Disease record that came from a source the features lookup never touched (a graph-only answer), since the clause fires on `think.asks_features` alone, not on a lookup having run.
- Reproduction: the J01 probe with the definition removed, a Disease finding and row with no `clinical_features` key, `asked_field=FEATURES`: output `Found 1 disease record for Marfan syndrome: Marfan syndrome [1], which does not give clinical features.` That row shape is exactly what the builder produces for an unreadable `conceptmeta` (no feature row added).
- Why it matters: a statement of absence where the product knows nothing; the trust moat line "a confident wrong record is worse than a missing one". Only the "read and lists none" row (the `NO_CLINICAL_FEATURES_PREFIX` finding) proves absence; the test `test_the_lists_none_statement_is_not_a_feature` covers that case, and no test covers the unread case.
- Smallest fix: require positive evidence of absence: fire the clause only when a stated-absence finding (`is_no_clinical_features_finding`) exists for each counted disease record, never on a missing field.
- NOT FIXED

### F-8.7-J03: Option B (the second draft beside the first) can never start at the 25-cent cap with the Opus writer
- Severity: major (goal miss, not a correctness fault)
- File: src/system_03_search_agent/core/graph.py (`_two_drafts_fit_cap`), src/system_03_search_agent/harness/cost_control.py (`_PRICED_TOKEN_PROFILE`)
- What: `_two_drafts_fit_cap` needs running cost + 2 x 0.132 <= cap. At `PER_QUERY_COST_CAP_USD=0.25`, 0.264 > 0.25 before anything is spent, so the branch is unreachable on develop's planned configuration. Every option B arm in the suite (S8, the repair-keep arms of `test_check_every_rewording.py`) runs at a $1.00 cap, so the suite is green on code that will never run in the deployed setting.
- Reproduction (judge's probe, cap 0.25, default synth model `anthropic/claude-opus-5.5`): `per-call estimate: 0.132`; `spent 0.0: two drafts fit cap? False`; `spent 0.01: two drafts fit cap? False`; `spent 0.05: two drafts fit cap? False`.
- Why it matters: card 50's "the written summary arrives sooner" (plan step 6: write step median 14.2 s to 11.7 s, over-20 s runs from 21 of 54 to 2) is not delivered; the step's complexity (task registry, cancellation, metering of a dropped draft) ships live but dormant. Builder W reported this as an open question; it needs an owner decision, not a silent merge.
- Smallest fix: an owner decision (raise the cap, price the second draft by a measured figure, or remove option B), and one arm at cap 0.25 that pins which of these holds.
- NOT FIXED

### F-8.7-J04: The 25-cent cap is an estimate, not a bound: one Opus call can cost more than the check priced it
- Severity: minor
- File: src/system_03_search_agent/harness/cost_control.py (`_PRICED_TOKEN_PROFILE["synth"] = (23_000, 2_000)`) against harness.py `_TIER_MAX_TOKENS["synth"] = 4_000`
- What: the pre-flight check prices a writer call at 2,000 output tokens; the call may write up to 4,000. A question at $0.118 is admitted to a writer call that can cost $0.172.
- Reproduction (judge's probe): `spent 0.118: writer call admitted; worst end total 0.29`; `worst single Opus call at max_tokens 4000 and 23k prompt: 0.172`. The bench's largest output was 1,869 tokens, so this is a tail, not the median.
- Why it matters: the owner's words are "never over 25 cents a question". The cancelled-call metering (4,000 tokens) and the admitted-call estimate (2,000) disagree about the same ceiling.
- Smallest fix: send `max_tokens=2000` on the Opus writer call (the profile's own figure), or price the output at the tier ceiling.
- NOT FIXED

Correction to F-8.7-J03, established after filing: `test_write_answers_sooner.py:826` `test_two_opus_drafts_never_start_together_under_a_25_cent_cap` does pin the behaviour at 0.25, so "no arm at 0.25" above is wrong. The finding stands as a goal miss: the arm pins that option B is off, which is the opposite of what step 6 set out to deliver.

### Hand-merge points: judge's own mutation checks (graph.py mutated, restored byte for byte with cmp after each)

| Point | Mutation | Result |
|---|---|---|
| 1 repair-keep | keep rule reduced to `reported_after > reported_before` | 2 failed, 80 passed (test_write_completeness.py:442) |
| 2 cost limit | cap at writer after listing returns `_partial_result_for_cap` | 1 failed (test_write_answers_sooner.py:713) |
| 2 cost limit | cap at writer after listing marked `writer_failed` | 1 failed (same arm, wrong note) |
| 3 draft pricing | `_two_drafts_fit_cap` on static `estimate_call_cost_usd("synth")` | 1 failed (test_write_answers_sooner.py:840) |
| 4 dropped draft | `_drop_second_draft` never cancels | 2 failed |
| 5 one row per record | final answer builds the listing again when sent | 2 failed (test_write_answers_sooner.py:628) |
| 6 numbering | prose claims first in the merge | 1 failed (test_write_answers_sooner.py:590) |
| 6 numbering | listing citations re-sent at the end | 2 failed (10 == 5 at :579) |
| 6 numbering | the sent-payload substitution `citations = [sent_by_id.get(...)]` removed | 0 failed over core, adapters, feedback (2514 passed) |
| 7 nothing taken back | writer failure after listing emits error and refuses | 1 failed (:679) |
| 7 nothing taken back | writer-failed note replaced by the fallback note | 1 failed (:682) |
| card 2 lead | marker filter removed from `_lead_candidates` | 0 failed over core and synthesis (2182 passed) |

So all seven named points hold and go red when broken. Two protections claimed in comments are unpinned (see F-8.7-J05).

### F-8.7-J05: Two citation and lead protections have no test that goes red
- Severity: minor
- File: src/system_03_search_agent/core/graph.py (`_write_answer` `sent_by_id` substitution; `_lead_candidates` marker filter)
- What: removing `citations = [sent_by_id.get(c.citation_id, c) for c in citations]` leaves core, adapters and feedback green (2514 passed); removing the `_MARKER_PATTERN.search(sentence)` filter from `_lead_candidates` leaves core and synthesis green (2182 passed). Probed: `run_grounding_pass` already strips an unmarked sentence (`('BRCA1 is linked to familial cancer of breast [1].',)` from a two-sentence input), so the marker filter is defense in depth today, and the substitution only affects internal uses since sent citations are not re-emitted.
- Why it matters: both are named in comments as what makes "a number shown early never changes" and "a lead always carries its markers" true; the next refactor can remove either silently.
- Smallest fix: one arm each: a lead candidate list built from a grounding result carrying an unmarked sentence; an assertion that the `citations` used for conflict flags and `done` equals the sent payloads.
- NOT FIXED

### F-8.7-J06: Step 3's name prefetch is dead after step 8, and the arms that compare it are now vacuous
- Severity: minor
- File: src/system_03_search_agent/core/graph.py (`_prefetch_answer_names` at line 8562, `_one_lookup_holds` at 8540, about 110 lines); tests/system_03_search_agent/core/test_act_name_lookups.py (`test_a_question_makes_the_same_ncbi_calls_as_before` and the arms at lines 312, 363, 427)
- What: `grep` finds no caller of `_prefetch_answer_names` in src; its only remaining reference is a comment (graph.py:8886). The test arms still monkeypatch it with `raising=False` to compare "prefetch on" against "prefetch off", but with no caller both iterations run the same code, so `counts == [2, 2]` and `answers[0] == answers[1]` would pass on a subject that does nothing. Its docstring ("while the reader pass runs, so the time hides behind it") and the comments builder R listed (module docstring F-2.1-J4-06 note, `_execute_planned_call`'s "reader-bound pair") now describe a path that does not run.
- Why it matters: the split question in the brief. Steps 3 and 8 each passed alone; together, option H's 0 to 0.7 s on disease questions is gone (builder R: the listing now waits on Write's own lookups), and the suite still reports the comparison as proven. Not a user-visible fault.
- Smallest fix: delete `_prefetch_answer_names` and `_one_lookup_holds` and the comparison arms, or keep option H by running the lookups in Act beside the searches' tail; refresh the three stale comments.
- NOT FIXED

### F-8.7-J07: The contract documents say the count line is sent as "listing"; the code sends it as "summary"
- Severity: minor
- File: src/system_03_search_agent/contracts/events.py:423, visualizations/Schema_visualization.md (the `placement` bullet), frontend/src/lib/events.ts:199, frontend/src/hooks/useRunView.ts:671, frontend/src/components/screens/AnswerScreen.tsx:1452
- What: all five say `listing` is "the code-built count line and the record listing, sent the moment the searches end". In `_answer_parts` (graph.py) the count line sits in `parts.summary`, and `build_listing` passes `summary_sentence=None`; the step's own test asserts `summary[0]["text"].startswith(COUNT_LINE_START)` with `placement == "summary"` (test_write_answers_sooner.py:479). Notes (cap note, writer-failed note, medical-advice note) are sent as `listing`, which no document mentions.
- Why it matters: the schema document is the public contract for agents and the CLI; a consumer following it will look for the count line at 8 seconds and not find it, and will not expect notes in the listing region.
- Smallest fix: reword the five comments and the schema bullet: "listing" is the record listing and the notes under it; the count line belongs to the summary.
- NOT FIXED

### F-8.7-J08: At 25 cents the completeness repair is refused whenever the question has spent more than $0.118 by the end of the first Opus draft; the replay that says otherwise has no saved artefact
- Severity: unsure (could be major)
- File: src/system_03_search_agent/harness/cost_control.py (comment above `_PRICED_TOKEN_PROFILE`)
- What: the repair's pre-flight check needs running cost + 0.132 <= 0.25, so running cost <= $0.118 after the first writer call. The comment cites writer bench 3: first Opus call median $0.0855, maximum $0.1219. Any question whose first draft costs more than about $0.118 minus its pre-Write spend (guard, plan, Think, Jev) gets no repair and carries the repair cap note instead. The same comment says "Replayed on the bench's 54 Opus questions at a 25-cent cap: no first writer call refused, all 24 repairs admitted". `grep -rn "repairs admitted"` over testing/, tracker/ and DECISIONS.md finds nothing: the replay exists only as a code comment, and it is not stated whether it counted the pre-Write spend.
- Reproduction (judge's arithmetic with the module's own numbers): estimate 0.132 (probe output above); 0.25 - 0.132 = 0.118; 0.1219 > 0.118, so the bench's own largest first draft would have its repair refused at zero pre-Write spend.
- Why it matters: the brief's bar "no question refused by the cap that answers on develop with today's writer at today's cap". A refused repair is not a refused question, but it is a less complete answer under a "resource limit" note where develop gives the full one; that is the no-degradation rule. Could not be settled offline; it needs the step 6 probe's metered `done.total_cost_usd` per question, which the plan already asks for.
- Smallest fix: save the replay script and its output beside the bench, including pre-Write spend, or measure it live in the lead's check before setting develop's cap.
- NOT FIXED

### Merge with today's develop (judge's own check)

The phase branch is behind origin/develop by six pull requests (#212 to #215, cards 32, 36, 37, 71). `git merge-tree --write-tree HEAD origin/develop` is clean (tree 6fbae7af). Extracted with `git archive` to scratch (no repository change) and run there: core 1453 passed, 56 skipped; synthesis 745 passed; contracts 214 passed; tools 1672 passed; tsc clean; vitest 32 files, 266 tests passed. feedback (17 failed) and adapters (11 failed) fail identically on plain origin/develop in the same scratch setup (17 and 11), a local database without card 71's column (`ProgrammingError`), so not caused by the merge.

### F-8.7-J09: The screen's writer-failed note has no committed test, and the frontend fixtures send the count line as "listing"
- Severity: minor
- File: frontend/src/components/screens/AnswerScreen.listingFirst.test.tsx (fixture `listingEvents`, lines 57 to 63); frontend/src/hooks/useRunView.ts (`SYSTEM_NOTE_PREFIXES`, lines 81 to 82)
- What: no frontend test mentions "Note: the written summary could not be finished" (grep over frontend/src). The listingFirst fixture sends "Found 2 disease records for BRCA1 [1][2]." with `placement: "listing"`, while the server sends the count line as `summary` (F-8.7-J07), so the screen arms pin a stream shape the server never produces.
- Reproduction: the judge's temporary probe (written, run, then moved out of the tree; `git status --short` shows only the node_modules link) fed `useRunView` and `AnswerScreen` the server's real order for a writer failure after the early listing (listing break, heading, two list items, two citations, the summary count line, a listing break, the note with `kind: "note"`, `done`). Result: 1 passed, with the note found on screen and the count line before the first `data-placement="listing"` element. So the behaviour holds today; only its pin is missing.
- Why it matters: the brief's "the screen shows that note" holds by the generic `kind: "note"` path alone; one edit to `HIDDEN_NOTE_PATTERNS` or the region note handling could hide it with every arm green.
- Smallest fix: add the probe as an arm in `AnswerScreen.listingFirst.test.tsx`, and move the count line in the fixture to `summary`.
- NOT FIXED

## Checklist summary

| Item | Holds | How established |
|---|---|---|
| Seven hand-merge points | Yes, each red when broken | Own mutations, table above |
| Citations: early number never changes, no double send, one row per record | Yes | Own mutations (merge order, re-send, rebuild); read of the merge branch for every path with `listing_sent` |
| Every shown record cited | Yes | Read plus the step's own arm at test_write_answers_sooner.py:479 (citations 1 to 5) |
| Nothing shown is taken back, server | Yes | Own mutations M2, M7; read of every return after the listing (trust can no longer reach refuse: `trust_for_claims` marks every claim grounded, `DECISION_TABLE` has no grounded refuse) |
| Nothing shown is taken back, screen | Yes | Own probe (F-8.7-J09) |
| Stop after records | Yes | Own frontend mutation (3 failed in useAnswerReveal.test.ts); read of App's stop slice and `status` override for the fatal `cancelled` event |
| Lead decision through decide.py, no word list | Yes | Read (`_lead_sentence_choice`, `lead_sentence_*`) |
| Lead sentence is checked and carries markers | Yes, defense in depth unpinned | Own probe of the grounding pass; F-8.7-J05 |
| Gap clause never claims a missing fact a record has | No | F-8.7-J01, F-8.7-J02 |
| 25-cent cap with the Opus price before every call | Holds as an estimate, not a bound | Own probe; F-8.7-J04 |
| Dropped second draft metered within the estimate | Yes ($0.08 against $0.132) | Read of harness.py cancel path; moot at 0.25 (F-8.7-J03) |
| No question refused by the cap that answers on develop | Could not verify offline | F-8.7-J08 |
| `placement` additive, optional, bounded, documented | Yes, documentation wrong in content | Own probe (unknown value rejected, no field joins in arrival order); F-8.7-J07 |
| Every surface reads summary above listing | Yes | Read of MCP, GraphQL, CLI (both renderers), capture, trace_source; older CLI drops unknown keys (client.py T-8.10-02) |
| Step 8 keeps every protection | Yes | Own mutations R1 (4 failed), R2 (2 failed) |
| The split | Step 3's option H is dead after step 8 | F-8.7-J06 |
| Lead decision runs on develop | Could not verify | Needs `CLASSIFIER_PROVIDER=jev` on develop; not readable offline |

Not verified at all (live only, the lead's check): records at about 8 seconds, the summary slotting in above them in a browser, any live cost figure.

## Verdict

FIX FIRST: F-8.7-J01 and F-8.7-J02 (the honest-gap clause can tell a reader a record lacks clinical features when it describes them, or when nothing was read; both small fixes in `records_lack_field`). F-8.7-J03 needs the owner's decision before merge, since step 6's speed gain is off at the planned cap. The rest are minor and may follow.

None of these sits inside a fix round of this phase; J01 and J02 sit in step 5's new code, J06 in the interaction of steps 3 and 8.
