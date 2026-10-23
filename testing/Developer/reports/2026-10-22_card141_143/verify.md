# Verification of cards 141 and 143

Fresh verifier, 2026-10-22. Question asked: is anything worse than develop? Findings are appended as they are established.

## Findings

### V-141-01: the suggested next question, asked about "that variant", is admitted but refused as no evidence
- Severity: unsure (copy is new, the refusal path is pre-existing backend behaviour)
- What: card 141's new line says "Ask what the graph holds about a gene, variant, or condition and I can assemble cited evidence." On deployed develop, in one guest session, the follow-up a person would type next is admitted by the guard and then refused as no evidence.
- Reproduction: live, develop API, one guest session: (1) "Which diseases are associated with rs334?" guard ok, answered in 7.5 s, trust_outcome ask; (2) "Remove that variant node from the knowledge graph." guard write_seeking, 0.8 s; (3) "What does the graph hold about that variant?" guard passed ok, done trust_outcome refuse, 11.5 s, text "I could not find grounded evidence for this. Try NCBI's cross-database search: https://www.ncbi.nlm.nih.gov/search/all/?term=What%20does%20the%20graph%20hold%20about%20that%20variant%3F". Script: scratchpad live141.py (not committed).
- Why it matters: "I can assemble cited evidence" is a promise; the first natural follow-up in the card's own scenario breaks it. Not worse than develop in behaviour (develop gives no suggestion at all), but the new sentence is only partly true for this phrasing. Further probes below test whether naming the entity fixes it.
- NOT FIXED
- Follow-up probes on V-141-01, live develop: the same "What does the graph hold about that variant?" straight after the rs334 question, with no refusal between, is also refused as no evidence (6.6 s), so the refusal turn is not the cause; it is a pre-existing follow-up gap with this phrasing. Naming the thing works for all three kinds the sentence lists: "What does the graph hold about rs334?" admitted, records with citations, 9.6 s; "...about BRCA1?" answered, 7.5 s; "...about cystic fibrosis?" admitted, records with citations, 8.5 s. Deterministic screens (prefilter.screen, forbidden.screen) admit every phrasing tried, including "...about the BRCA1 node?" and "...this variant's status?". Verdict on V-141-01: minor, pre-existing, not worse than develop.
### V-141-02: the owner's test queries document still quotes the old two-sentence reply
- Severity: minor (documentation drift, no behaviour)
- What: `testing/Test_queries_and_workflows.md:1112` (query 89) says the refusal shows "the sentence 'This system only reads from NCBI records. It cannot add, change, or remove data.'" After card 141 the block shows a third sentence. The commit does not touch that document. The quoted text is still a true prefix, so the check does not turn false, but the gate document no longer describes the full reply, and query 111's "what it can show" expectation is the one this card meets.
- Reproduction: `git diff origin/develop...HEAD --stat` lists only the two GuardrailBanner files; grep for "only reads from NCBI records" finds the stale line in the test queries document.
- Why it matters: the owner's retest reads that document as the gate; keeping it current is a house rule ("update every place the document states it").
- NOT FIXED

### Card 141 checks run
- Diff read in full: one string in `frontend/src/components/chat/GuardrailBanner.tsx:46` and one new test arm in `GuardrailBanner.test.tsx:72-78`. No other file.
- Where the string shows: the refusal block (`useRunView.ts:1460`) and the reasoning log's Guard line (`useRunView.ts:1105`), both through `CATEGORY_COPY`; label "Read-only system" unchanged. `compute_request` already carries the same "Ask ... and I can assemble cited evidence" shape in both places, so the reasoning log reading is not new.
- No other test or screen pins the old string (grep across frontend, clients, services, eval, tests).
- House text: no em or en dash, no reader identity, no vendor; first person "I" matches the neighbouring off_topic, medical_advice and compute_request entries.
- Break it: removed the new sentence by hand; `GuardrailBanner.test.tsx` went 1 failed of 18 on the write_seeking arm; restored with `git checkout -- <file>`; 18 of 18 pass; `git status` shows only `?? frontend/node_modules`.
- vitest on `src/components/chat/` plus `src/hooks/useRunView.refusal.test.ts`: 5 files, 66 tests, all pass. `npx tsc -b`: exit 0.
- Verified by my own probes: guard screens on ten phrasings; live develop runs above. Only read: that develop's frontend renders the new string, since the frontend change is not deployed.
- Card 141 verdict: PASS, nothing worse than develop. V-141-01 and V-141-02 are minor and pre-existing or documentation only.

### V-143-01: the About mock shows the trust line as a green bordered pill; the app shows a plain muted line
- Severity: minor (pre-existing on develop; card 143 changed the words only)
- What: `frontend/src/components/screens/InfoScreens.tsx:1175-1192` renders the example inside a rounded pill, weight 600, `layer2Wash` fill and a `designTokens.ok` (green) border. The live answer (`AnswerScreen.tsx:2566-2611`) renders `trust_line` as one plain span, weight 400, `inkMuted` colour, no border; a "Based on" line is kind "plain" (`useRunView.ts:1017`), and only a "Confirmed" line gets the green check. So the About page dresses a "Based on 1 source cited" line in the green treatment the app keeps for confirmed answers. The AnswerMock docstring (`InfoScreens.tsx:1124-1130`) still says each part copies "the trust pill" shape its component renders, untrue since item 9.9.
- Reproduction: read both style blocks side by side; `useRunView.ts:1017`: `kind: summary.startsWith("Confirmed") ? "good" : "plain"`.
- Why it matters: the card's title is "show the trust line the app shows today"; the words now match, the look does not, and the green border implies more confidence than the line states. Not worse than develop.
- NOT FIXED
### V-143-02: the changed stop 6 sentence is not tested, and describes only the common "Based on" line
- Severity: minor
- What: `InfoScreens.tsx:1512` now says "a trust line says how many sources the answer rests on and which database they come from". Two of the three line shapes in `trust.py:780-797` do not do that: "Sources disagree on at least one claim" gives no count and no database, and "Confirmed by N independent databases" counts databases and names none. "which database" is singular where the line can name several ("from MedGen and OMIM"). Still truer than develop's "whether the whole answer was grounded".
- Reproduction: break it, case 3: I put develop's sentence back by hand and `npx vitest run src/components/screens/AboutScreen.test.tsx` stayed 12 of 12 green. Only the mock line is pinned.
- Why it matters: a reader who sees "Sources disagree" after reading the About page was told to expect a count; small. The untested sentence can drift again unseen.
- NOT FIXED

### V-143-03: the test pins the example's shape to a regex, not to the backend
- Severity: minor (unsure it is worth a parity test)
- What: `AboutScreen.test.tsx:181-183` checks `ABOUT_TRUST_LINE_EXAMPLE` against `/^Based on 1 source cited, from [A-Za-z ]+$/`, a copy of today's backend wording held in the frontend. If `answer_trust_line` changes its words again (as card 8 and card 22 did), this test stays green and the About page goes stale the way card 143 found it. The docstring at `InfoScreens.tsx:92-94` also says the live line reads "all from <database>", which is the wording for two or more sources, not for this one-source example.
- Reproduction: my own call of `answer_trust_line` with one cited MedGen page (`https://www.ncbi.nlm.nih.gov/medgen/C0677776`) returned exactly "Based on 1 source cited, from MedGen" for outcomes ask and answer, risk low and high; with two MedGen pages, "Based on 2 sources cited, all from MedGen". So the example is correct today; the guard against drift is the gap.
- NOT FIXED

### Card 143 checks run
- Diff read in full: new constant at `InfoScreens.tsx:91-97`, its use in the mock at `:1191`, the stop 6 sentence at `:1512`, test changes at `AboutScreen.test.tsx:52,180-184`. No other file.
- The old string still lives on purpose in `lib/riskTag.ts:27` (saved answers with no trust line) and in `useRunView.ts:1026` (older backend with no trust_line); untouched, and their tests still pass.
- House text: no em or en dash, no reader identity, no vendor in the new prose or constant. The "·" removed was a middle dot, not a dash.
- Break it: (1) mock text back to "Grounded · every claim cited": 1 failed of 12; (2) constant to "Based on 1 source, from MedGen": 1 failed of 12; (3) stop 6 sentence back to develop's: 12 of 12 green (V-143-02). Restored each with `git checkout -- <file>`; afterwards 12 of 12 pass and `git status` shows only `?? frontend/node_modules`.
- vitest on `src/components/screens/` plus `src/set9AnswerStructure.test.tsx` and `src/lib/riskTag.parity.test.tsx`: 22 files, 232 tests, all pass. `npx tsc -b`: exit 0.
- Verified by my own probes: the example string against the real `answer_trust_line`; the three break-its. Only read: the live answer's styling (V-143-01), not rendered in a browser.
- Card 143 verdict: PASS, nothing worse than develop. V-143-01 to V-143-03 are minor; V-143-01 is pre-existing.

## Verdict
- Card 141: PASS. Card 143: PASS. No finding sits inside a fix made earlier in this phase; none is a regression against develop.
