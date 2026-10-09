# Card 48 verifier report, fix round, 2026-10-09

Fresh verifier, branch fix/card48-ask-which-aspect at d27a9e0c, compared with develop b01dee92. Findings are appended as they are established; the verdict is at the end.

## Table of contents

- [Findings](#findings)
- [Checks run](#checks-run)
- [Verdict](#verdict)

## Findings

### V-48-01: Live, none of 40 fresh real questions was asked back, and 14 of 15 broad subjects were (record)
- Severity: unsure (record only)
- What: the branch's real `think_node` was run once per call with a fresh session id, only `think.ask_back` live (`CLASSIFIER_PROVIDER=jev`), every other decision, Think's classification (1.0 s sleep), the choices writer and the live accession and window lookups stubbed. The outcome counted is what `think_node` returned, so the gate, the 1.0 s bound and the named-record check are all in the path. The 55 texts were written for this round; none is in the fix agent's sets, the test queries document or the prompt.
- Reproduction: 165 calls, three runs per text.

| Set | Texts | Calls | Classifier picked ask_back | Asked back |
|---|---|---|---|---|
| Real opening questions, four or more words (genes, variants, diseases, drugs, trials, isolates, papers, plain-language health) | 40 | 120 | 3 (all `Tell me about rs7412 please.`) | 0 (0 %) |
| Broad subjects, four or more words | 15 | 45 | 42 | 42 (93.3 %), 14 of 15 texts on every run |

  The one broad subject searched on every run: `What can you tell me about hemoglobin?` (proceed x3). The rs7412 text was picked ask_back on every run and searched by the code's record check. Shapes the first round failed on now proceed on new subjects: `What is known about the LRRK2 gene?`, `What does the research say about long QT syndrome?`, `What does the literature say about ketamine for depression?`, `My son was diagnosed with type 1 diabetes, what now?`.
- Why it matters: the merge bar for real questions holds on this set. Decision latency, 161 answered calls: median 0.33 s, 90th percentile 0.45 s, maximum 0.94 s.
- NOT FIXED
### V-48-02: The 1.0 s bound cut 4 of 165 live decisions, ten times the rate the build states
- Severity: minor
- What: `_LONG_ASK_BACK_WAIT_S` (1.0 s) stopped 4 of 165 live Jev decisions in V-48-01 before they answered (2.4 %); each was searched. The build's fix-round section states "about one call in 400 passes the 1.0 s bound". My run held eight decisions in flight at once, which may slow the tail; the build's own run concurrency is not stated.
- Reproduction: `out_jev.json` rows with no recorded pick and the decision cancelled: `Which drugs target the EGFR protein?` run 1, `How many Klebsiella pneumoniae isolates carry KPC genes?` run 2, `What did PMID 31747580 find?` run 3, `Papers about CRISPR off-target effects in human embryos.` run 1. Think wall time on each 1.00 s, the stubbed classification's own length.
- Why it matters: nothing worse than develop for a person (a cut decision searches, as develop does). It lowers the broad-subject catch rate in production by the share of slow decisions, and the stated figure understates it. If the classifier is the guard tier (the code default), the share is likely much larger; see V-48-03.
- NOT FIXED
### V-48-03: With the code-default classifier (guard tier, which production runs), the 1.0 s bound cuts most decisions and 1 of 15 broad subjects is asked back
- Severity: minor (nothing worse than develop; the card mostly does nothing there)
- What: `docs/architecture/Model_architecture.md` records that production runs the code default `CLASSIFIER_PROVIDER=guard`, with Jev only on develop. With the guard tier deciding, 48 of 55 live decisions were still running at the 1.0 s bound and were searched. The build's "Left open" names this case and says "Not measured".
- Reproduction: same probe as V-48-01, `CLASSIFIER_PROVIDER=guard`, one run per text, 55 calls: real questions 0 of 40 asked back (35 cut by the bound, 5 proceed); broad subjects 1 of 15 asked back (`What can you tell me about hemoglobin?`), 13 cut by the bound, 1 proceed. Guard decisions that did answer: median 0.72 s, maximum 0.99 s, 7 calls.
- Why it matters: when this reaches production, a person typing `Tell me about the immune system.` there will almost always be searched, as on develop today. The owner's expectation of the card, set from develop with Jev, will not carry over until production runs Jev or the bound changes. Not a regression, so not a merge blocker under the bar.
- NOT FIXED
### V-48-04: Inside this round's fix: a named variant, a ClinVar accession, a PMC id, a DOI or "the paper <PMID>" is still asked which aspect, every run
- Severity: major. This sits inside the fix-round change `_names_a_record` (the fix for A-48-01), so it fires the review loop's stop condition.
- What: `_names_a_record` covers only what `resolve_exact_identifiers`, `parse_accession` and `parse_coordinate_window` recognise. Many single-record forms a person types are outside them, and the branch's `_ASK_BACK` picks `ask_back` on them with "Tell me about", so the person who named one exact record gets a menu. On develop each of these (four or more words) was searched. The DECISIONS row of 2026-10-09 states the intended outcome: "a named record (a PMID, an rs number, an accession) is searched whatever the classifier picks", and calls a named record answered with a menu "worse than develop's search".
- Reproduction: live `_decide_point(..., _ASK_BACK, text)` on the branch, `CLASSIFIER_PROVIDER=jev`, three runs each, and `_names_a_record(text)` offline (False for every row below):

| Text | Picks, 3 runs |
|---|---|
| `Tell me about BRCA1 c.68_69delAG.` | ask_back x3 |
| `Tell me about CFTR p.Phe508del.` | ask_back x3 |
| `Tell me about VCV000017661.` | ask_back x3 |
| `Tell me about PMC7096066.` | ask_back x3 |
| `Tell me about doi 10.1056/NEJMoa2034577.` | ask_back x3 |
| `Tell me about the paper 33057194.` | ask_back x3 |
| `Tell me about HGNC:1100.` | ask_back x3 |
| `Tell me about OMIM 113705.` | ask_back x3 |
| `Tell me about GSE12345.` | ask_back x3 |
| `Tell me about MESH:D003920.` | ask_back x3 |
| `Tell me about PubChem CID 2244.` | ask_back x2, proceed x1 |
| `Tell me about NCT04280705.` | ask_back x1, proceed x2 |
| Controls: `Tell me about trial NCT04368728.`, `Tell me about ClinVar variant 17661.` | proceed x3 each |

  Offline, the real `think_node` with an `ask_back` pick stubbed: `Tell me about HGNC:1100 please.` was ASKED; `Tell me about PMID 33057194.`, `rs334`, `NM_000546.6`, a chr17 window and `PRJNA257197` were searched. The docstring of `_names_a_record` says it covers "a CURIE", but `HGNC:1100` and `MESH:D003920` are not recognised.
- Why it matters: a clinician who types one exact variant in HGVS (`BRCA1 c.68_69delAG`, `CFTR p.Phe508del`) or a ClinVar accession is asked which aspect they mean, every time, where develop searched it. That is the A-48-01 outcome the fix round says it closed, on the most clinical inputs the product takes. Either the record check needs the variant parsers the search already has (an HGVS parse, ClinVar VCV, PMC, DOI), or the decision's criterion must treat one exact identifier as a request; which is the owner's or the lead's call, not mine.
- NOT FIXED
### V-48-05: When the record of begun conversations is lost, a typed reply is asked which aspect again, worse than develop, not "develop's behaviour" as the DECISIONS row says
- Severity: minor
- What: `clarify._BEGUN` lives in one process. After a server restart (Railway redeploys the develop API on every push to `develop`, per `docs/build/Handoff_history.md`), after 4096 newer conversations, after an hour idle, or on a second worker or replica, the next message of an ongoing conversation is an opening message again. If the earlier turn stored no memory (any ask-back turn), that message reaches the longer decision. The DECISIONS row of 2026-10-09 says both costs "fall back to develop's behaviour, never to a worse one"; develop never asked a message of four or more words, so this falls back to the first build's behaviour instead.
- Reproduction: offline, `clarify.begin_turn` on 5000 keys: size 4096, the first key reads as a first turn again (True), the last as begun (False). Live, `_ASK_BACK`, Jev, two runs each, the replies a person types after a menu: `Tell me more about the second one.` ask_back x2, `What about BRCA2 then?` ask_back x2, `Can you tell me more about this gene?` ask_back x2, `Tell me more about that.` ask_back x2. Writer-style clicked choices on 15 subjects (`What does recent research say about X?`, `Which genes or diseases are linked to X?`, 30 texts, 60 calls) were all proceed, so a lost record hurts a typed reply, not a click.
- Why it matters: rare in production (one process, few restarts), more likely on develop during an overnight run of merges, which is exactly when the owner tests. Query 112 does state the restart case; the DECISIONS row understates it. Not a merge blocker on its own.
- NOT FIXED

### V-48-06: Longer small talk outside the exact list is picked ask_back, but the guardrail refuses it first with Jev (record)
- Severity: unsure
- What: `Hi, what can you do?`, `What kind of questions can you answer?`, `How do I use this search tool?` and `Thanks, that was really helpful!` are not in `CONVERSATIONAL_TEXTS`, so they pass the gate, and the branch's decision picks ask_back x3 on each. With Jev, `guardrail.relevancy` picks off_topic x3 on each and none clears the biomedical allowlist, so none reaches Think, as on develop. With the guard tier as classifier (production) the relevancy verdict was not measured, and a guard ask-back decision is usually cut by the 1.0 s bound (V-48-03).
- Reproduction: live decision probe, Jev, three runs each, both decisions; `prefilter.clears_biomedical_allowlist` False and `prefilter.screen` None for all four.
- Why it matters: no change for a person in the measured mode.
- NOT FIXED

### V-48-07: Offline checks that held (record)
- Severity: unsure (record only)
- What and reproduction: own script outside the checkout, the branch's real `think_node`, `decide` stubbed to pick ask_back (or to hang), writer and classification stubbed, no network.

| Check | Observed |
|---|---|
| One session: `Tell me about the immune system.` then a clicked choice, a typed reply, a new broad subject | ASKED (decide, writer), then searched with no decision and no writer call, three times |
| Same session id, owners `user-2` and `user-3` | each ASKED on its first message; `user-2`'s second message searched with no decision: no leak between users |
| Same owner, new session id | ASKED: a new conversation opens again |
| Session memory present, new session id | searched, no decision |
| `What can you do?` as `What can you do?`, `what can you do`, `WHAT CAN YOU DO!!!`, `What can you do ?`, `What... can you do?`, extra spaces, a full-width question mark, curly quotes | searched, no decision, every spelling |
| `What-can-you-do?`, `Who are you?`, `Thank you!`, `Thanks!!`, `Hello there friend!` | take the unchanged one-to-three-word path, as on develop (not this card) |
| Hung decision, classification 0.2 s / 0.0 s / 2.0 s | Think 1.0 s / 1.0 s / 2.0 s, searched: a hung decision adds at most 1.0 s |
| Bound of the per-session record | 4096 entries, least recently used evicted, each kept an hour after its last turn; keys are owner id (at most 128 characters) and session id (at most 64), so well under a few megabytes |
| Empty session id | every message opens a conversation; the web endpoint requires `min_length=1`, the MCP surface falls back to the run id, the CLI to a fresh UUID |

- NOT FIXED
### V-48-08: No test notices if the begun-conversation record stops separating users
- Severity: minor
- What: the record is keyed by `_offer_key`, owner id plus session id. Dropping the owner from the key leaves the card's two test files green, so a later edit could let one caller's turn mark another caller's conversation as begun. Today's code separates them (V-48-07, own probe).
- Reproduction: mutations of `core/graph.py`, each restored with `git checkout`, run on `test_bare_topic_clarification.py` and `test_clarify.py`:

| Mutation | Result |
|---|---|
| `_offer_key` returns the session id only | 111 passed (not caught) |
| Opening gate dropped (`opening` replaced by `True`) | 3 failed |
| Exact small-talk check restored | 3 failed |
| `_names_a_record` returns False | 4 failed |
| Bound raised to 3.0 s | 1 failed |
| Every message treated as opening | 3 failed |

- Why it matters: the effect of such a leak is small (a person's opening message searched as on develop), and session ids are random, so this is a guard against a future edit, not a present defect.
- NOT FIXED
### V-48-09: Query 112 promises two things beyond what was measured
- Severity: minor
- What: query 112 in `testing/Test_queries_and_workflows.md` mostly matches my measurements: the two broad subjects were picked ask_back x3 each; `How do birds fly?`, `What is Marfan syndrome?` and `what does the literature say about metformin` proceed x3; `Tell me about PMID 33057194.` was picked ask_back 2 of 3 and searched by the record check; `Tell me about TP53.` ask_back x3, as its Known line says; a hung decision adds at most 1.0 s (V-48-07). Two promises go further than any measurement:
  - "The four controls are searched ... each asks something of its own, or names one exact record" invites a tester to read any exact record as searched. A named variant, a ClinVar, PMC or DOI identifier and "the paper <PMID>" are asked back on every run (V-48-04).
  - "`What can you do?` is never asked which aspect, however it is punctuated." `What-can-you-do?` and `what_can_you_do` are admitted by the guardrail as conversational (`prefilter._is_conversational` True), are one word, take the one-to-three-word path, and are picked ask_back x3 live; my offline probe shows develop does the same, so this is not a regression, only an overbroad promise.
  - "A clicked choice or a typed reply is never asked which aspect again" holds while the server keeps its record; the restart line beneath it covers the gap, the word "never" does not (V-48-05).
- Reproduction: live decision probe, Jev, three runs per text; offline `think_node` probe against the branch and against develop b01dee92's source.
- Why it matters: the owner's gate document should not teach a tester to expect a search on `Tell me about BRCA1 c.68_69delAG.`.
- NOT FIXED

## Checks run

| Check | Result |
|---|---|
| `test_bare_topic_clarification.py` and `test_clarify.py` | 111 passed |
| The 20 core test files that mention `_think`, `think_node` or `ask_back` | 771 passed, 34 skipped |
| `ruff check` (no path) | All checks passed, exit 0 |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | exit 0 |
| Prompt check: every backticked query in the test queries document and every quoted text in the card's test file, whole and as any five-word run, against `_ASK_BACK`'s text | no test question; no subject name or identifier in the prompt; its examples are kinds of information, as on develop, plus "mutations" and the misspelling instruction, which the build says were added after probe texts failed |
| Identifier check | `_names_a_record` calls only `resolve_exact_identifiers`, `accession.parse_accession` and `coordinate_window.parse_coordinate_window`, all existing |

Spend: OpenRouter "left" 31.4462 before, 31.4155 after, about 0.03 USD for about 330 decision calls and no writer or full-run calls. The account is shared, so the difference is an upper bound.

## Verdict

HOLD, on V-48-04, which sits inside this round's fix (`_names_a_record`, the fix for A-48-01) and so fires the review loop's stop condition: it goes to the product owner, not into another round.

Against the overnight bar, nothing worse than develop for a person: real questions hold (0 of 40 fresh real questions asked back over 120 calls, V-48-01), clicks, typed replies, follow-ups and `What can you do?` in any punctuation never reach the decision, a hung decision adds at most 1.0 s, and the per-session record is separated by user and bounded. What fails the bar is a person naming one exact record in a form the existing parsers do not recognise, most visibly a variant in HGVS (`Tell me about BRCA1 c.68_69delAG.`, `Tell me about CFTR p.Phe508del.`) or a ClinVar, PMC or DOI identifier: asked which aspect on every run, where develop searched. The lead's own DECISIONS row names that outcome as worse than develop.

Verified with my own probes: the live real-question and broad-subject rates through the real `think_node` (V-48-01), the bound's cut rate with Jev and with the guard tier (V-48-02, V-48-03), the named-record gaps (V-48-04, live picks plus the offline record check and an offline `think_node` run), typed replies after a lost record (V-48-05), longer small talk and its relevancy verdict (V-48-06), every offline check in V-48-07 against the branch and, as a control, against develop b01dee92's source, the mutations in V-48-08, the query 112 texts (V-48-09), the prompt scan, the tests, ruff and isort. Only read, not run: what the choices writer shows for any text (no writer calls), the guard tier's relevancy verdict, any full agent run, the web client's handling of "New search", and the production worker and replica count beyond `railway.json`'s single `uvicorn` start command.
