# Card 48 judge, round of 2026-10-15 (dial position 2)

Bases: branch worktree `<scratchpad>/j48` at fc218c0c; develop worktree `<scratchpad>/j48dev` at b25e4c6d (origin/develop). Judge files only, closes nothing.

## Findings

### J2-48-01: Real isolate questions of four or more words are asked which aspect on every run; develop searches them
- Severity: blocking
- What: on the branch, the longer opening message path asks back terse organism and isolate questions that name what is wanted (isolates, genes). On develop no message of four or more words is ever asked back, so each of these is a new ask-back of a real question. `ESBL E. coli isolates?` is test queries document query 44 ("The shortest version a person would type"), whose expected outcome is an isolate list. The build report calls it "pre-existing, not changed"; that is true only of the card's own 2026-10-09 spec, not of develop.
- Reproduction: own probe `<scratchpad>/probe/decide_probe.py`, live `graph._decide_point(Harness(t), t, graph._ASK_BACK, text)` then the branch's gate (pick `ask_back`, `_names_a_record` False, decision within `_LONG_ASK_BACK_WAIT_S` for four or more words), `CLASSIFIER_PROVIDER=jev`, five runs per text, branch fc218c0c. Output pasted:
```
5/5 asked | L | {'ask_back': 5} | max 0.42s | ESBL E. coli isolates?
5/5 asked | L | {'ask_back': 5} | max 0.35s | ESBL E. coli isolates in Pathogen Detection
5/5 asked | L | {'ask_back': 5} | max 0.49s | Klebsiella pneumoniae isolates with carbapenemase genes
5/5 asked | L | {'ask_back': 5} | max 0.42s | Tell me about Salmonella isolates.
5/5 asked | L | {'ask_back': 5} | max 0.27s | Tell me about E. coli isolates.
```
  Develop b25e4c6d, same probe: every one of these is four or more words, so develop's `_think` never asks the decision for them (it has no longer-message path); the five are searched.
- Why a person would care: a microbiologist who types the short form of an isolate question, which query 44 says "most people type", gets a menu instead of the isolate list, every time. `Klebsiella pneumoniae isolates with carbapenemase genes` names an organism, a kind of record and a gene family; nothing about it is a bare subject. This is exactly the bar's failure: a real question asked back that develop searches.
- NOT FIXED

### J2-48-02: The shared spec change makes develop's existing one-to-three-word path ask back two real questions develop searches, one of them a gate query
- Severity: blocking
- What: `_ASK_BACK` is read by both paths. The redesign rewrote its instructions and criteria, so the one-to-three-word path that develop already ships (item 12.3) now decides with the new text. Two short real questions that develop's spec proceeds on are now asked back. `recent-onset diabetes treatment` is query 84's control, whose expected outcome reads "is not asked back".
- Reproduction: same probe, five runs per text, branch versus develop worktree (each worktree's own `_ASK_BACK`):
```
branch : 5/5 asked | S | {'ask_back': 5} | max 0.30s | recent-onset diabetes treatment
develop: 0/5 asked | S | {'proceed': 5} | max 0.22s | recent-onset diabetes treatment
branch : 4/5 asked | S | {'ask_back': 4, 'proceed': 1} | max 0.23s | Lyme disease treatment
develop: 0/5 asked | S | {'proceed': 5} | max 0.22s | Lyme disease treatment
```
  Every other short text of the 32 in `<scratchpad>/probe/short_real.txt` had the same asked count on both (see the record finding below).
- Why a person would care: a person typing `Lyme disease treatment` names the kind of information they want (treatment), the very shape the criterion says is a request, and now gets a menu where develop searched. It also fails an owner gate query (84). The change is invisible to the card's own tests, which only exercise four or more words.
- NOT FIXED

### J2-48-03: Record: 69 real questions, five runs each, branch versus develop; seven regress, 17 short ones are asked back on both
- Severity: minor (record; the 17 are pre-existing, not caused by this card)
- What: the full regression set behind J2-48-01 and J2-48-02. 69 real questions (31 of one to three words, 38 of four or more; shapes: terse, organism and isolate, gene plus kind, plain-language health, test queries document queries 1, 33 to 44, 58, 84, 112 and others), 345 live Jev calls per side.
- Reproduction: own comparison of `<scratchpad>/probe/real_b.json` with `real_d.json`, pasted:
```
DIFF ESBL E. coli isolates? branch asked 5 develop asked 0
DIFF recent-onset diabetes treatment branch asked 5 develop asked 0
DIFF Lyme disease treatment branch asked 4 develop asked 0
DIFF Tell me about Salmonella isolates. branch asked 5 develop asked 0
DIFF ESBL E. coli isolates in Pathogen Detection branch asked 5 develop asked 0
DIFF Klebsiella pneumoniae isolates with carbapenemase genes branch asked 5 develop asked 0
DIFF Tell me about E. coli isolates. branch asked 5 develop asked 0
branch asked texts 24 of 69
develop asked texts 17
```
  Asked back 5 of 5 on both sides, so pre-existing on develop's short path: `TP53 mutations`, `Salmonella AMR genes`, `Klebsiella carbapenemase isolates`, `CRISPR off-target effects`, `Lynch syndrome genes`, `E. coli genomes`, `Listeria outbreak isolates`, `MRSA resistance genes`, `diabetes in pregnancy`, `BRCA1 breast cancer`, `HIV drug resistance`, `Tuberculosis genome assemblies`, `E. coli isolates?`, `Salmonella isolates`, `Listeria monocytogenes isolates`, `GEO datasets TP53`, `SARS-CoV-2 Illumina runs`.
  Long real questions that held (0 of 5 asked on the branch), among others: `How do birds fly?`, `What is Marfan syndrome?`, `Which Salmonella isolates carry blaCTX-M-15?`, query 33's full ESBL question, `My father has Parkinson's, what should we know?`, `Tell me about MRSA resistance.`, `Tell me about antibiotic resistance in Salmonella.`, `Explain what a gene is.`
- Why a person would care: the pattern is one thing: an organism or subject followed by a collection word (isolates, genes, genomes, runs) reads to the classifier as "a subject alone", although the branch's own `ask_back` criterion says "A subject followed by a word for things that belong to it ... is not a subject alone". The card widens that existing short-path weakness to every opening message.
- NOT FIXED

### J2-48-04: Record: the redesign's record judgement holds on 14 record texts, and also fixes develop's short path asking back a bare identifier
- Severity: minor (record, in the change's favour)
- What: every record text was picked `names_a_record` by the classifier itself on every run; the five broad subjects were asked back on every run. On develop the one-to-three-word path asks back a bare identifier, so for those the branch is better than develop.
- Reproduction: same probe, five runs each, Jev, pasted (branch, then develop):
```
branch : 0/5 asked | S | {'names_a_record': 5} | rs334 / PMID 33057194 / BRCA1 c.68_69delAG / CFTR p.Phe508del / VCV000017661 / PMC7096066 / 10.1056/NEJMoa2034577 / GSE12345 / SAMN02147118 / NM_000546.6:c.215C>G (each line 0/5, names_a_record x5)
branch : 0/5 asked | L | {'names_a_record': 5} | Tell me about CFTR p.Phe508del. / Tell me about VCV000017661. / Tell me about doi 10.1056/NEJMoa2034577. / Tell me about RCV000077146.
branch : 5/5 asked | L | {'ask_back': 5} | Tell me about the tree of life. / Tell me about apple trees. / Tell me about the immune system. / Tell me about photosynthesis. / Can you tell me about diabetes?
develop: 5/5 asked | S | {'ask_back': 5} | every one of the ten bare identifiers above
```
- Why a person would care: on the branch a person who pastes `rs334` or `VCV000017661` alone is searched, where develop's decision picks ask_back on every run. Whether develop actually shows a menu for those depends on the choices writer, not probed here.
- NOT FIXED

### J2-48-05: End to end, the four regressed questions show a menu on the branch 12 of 12 times and are searched on develop 12 of 12
- Severity: blocking (the evidence a person sees, for J2-48-01 and J2-48-02)
- What: through the real `run_streaming` with a fresh session each run (guardrail, Think, the choices writer all live, Jev deciding), the branch ends Think with a clarifying question on every run of the four texts; develop goes on to Plan on every run.
- Reproduction: own probe `<scratchpad>/probe/e2e_probe.py`, three runs per text per side, stopping at the first `think` event carrying `clarifying_question` (ASKED) or the first `plan`/`tool_start` (SEARCHED). Pasted, trimmed to the first line of each:
```
branch : {"text": "ESBL E. coli isolates?", "outcome": "ASKED", "think_s": 4.26, "question": "What would you like to know about ESBL-producing E. coli isolates?", ...}   (3 of 3 ASKED)
branch : {"text": "Klebsiella pneumoniae isolates with carbapenemase genes", "outcome": "ASKED", "think_s": 4.72, "question": "What would you like to know about Klebsiella pneumoniae isolates with carbapenemase genes?", ...}   (3 of 3)
branch : {"text": "Lyme disease treatment", "outcome": "ASKED", "think_s": 3.84, "question": "What would you like to know about Lyme disease treatment?", "options": ["What are the recommended treatments for Lyme disease?", ...]}   (3 of 3)
branch : {"text": "recent-onset diabetes treatment", "outcome": "ASKED", "think_s": 4.75, "question": "What would you like to know about treatment for recent-onset diabetes?", ...}   (3 of 3)
develop: {"text": "ESBL E. coli isolates?", "outcome": "SEARCHED", "think_s": 5.03, "plan_s": 5.03}   (3 of 3 SEARCHED; same for the other three texts)
```
- Why a person would care: the menu's own first choice for `Lyme disease treatment` is "What are the recommended treatments for Lyme disease?", which is what the person already asked: one extra click and a second wait to get what develop gives at once.
- NOT FIXED

### J2-48-06: Where the regressions come from: the card's own rewrite of `_ASK_BACK`, already present before today's redesign, which neither caused nor fixed them
- Severity: major (provenance; it puts J2-48-01 and J2-48-02 inside this pull request's own change)
- What: the pre-redesign head of the same branch, 36b5747d, asks back all seven regressed texts on every run. So today's commit fc218c0c did not introduce them, but they are inside this card's change to the shared `_ASK_BACK` text (built 2026-10-09 and rewritten in its fix round), not pre-existing on develop. The build report's line "Pre-existing, not changed: `ESBL E. coli isolates?` ... is asked back by the as-built spec on every run" compares with the card's own earlier text, not with develop; against develop it is a regression. None of the 2026-10-09 reviews compared the one-to-three-word path with develop, and their real-question sets had no terse isolate or "subject treatment" shapes.
- Reproduction: worktree `<scratchpad>/j48prev` at 36b5747d, same probe, five runs, pasted:
```
5/5 asked | L | {'ask_back': 5} | max 0.34s | ESBL E. coli isolates?
5/5 asked | S | {'ask_back': 5} | max 0.32s | recent-onset diabetes treatment
5/5 asked | S | {'ask_back': 5} | max 0.22s | Lyme disease treatment
5/5 asked | L | {'ask_back': 5} | max 0.26s | Tell me about Salmonella isolates.
5/5 asked | L | {'ask_back': 5} | max 0.23s | ESBL E. coli isolates in Pathogen Detection
5/5 asked | L | {'ask_back': 5} | max 0.26s | Klebsiella pneumoniae isolates with carbapenemase genes
5/5 asked | L | {'ask_back': 5} | max 0.26s | Tell me about E. coli isolates.
```
- Why a person would care: the owner was told this text was pre-existing and unchanged; it is new with this card. Any fix must be measured against develop's short path as well as the longer one, since one text serves both.
- NOT FIXED

### J2-48-07: Five more noun-phrase real questions asked back 5 of 5, including ones with a time, a group of people and a second subject the criterion itself says are requests
- Severity: blocking (same defect as J2-48-01, wider shape)
- What: a typed request without a question word, an organism or condition followed by a collection word and a qualifier, is asked back on every run, although the `ask_back` criterion excludes "a second subject, ... a group of people, ... a time". On develop all five are four or more words and so searched. The 27 numbered test queries document questions in the same batch all held (0 of 5 asked; nine picked `names_a_record`).
- Reproduction: same probe, branch, Jev, five runs each, pasted:
```
5/5 asked | L | {'ask_back': 5} | max 0.23s | Salmonella Typhimurium isolates from poultry
5/5 asked | L | {'ask_back': 5} | max 0.23s | Carbapenem-resistant Klebsiella isolates in 2024
5/5 asked | L | {'ask_back': 5} | max 0.32s | Campylobacter isolates with tetO genes
5/5 asked | L | {'ask_back': 5} | max 0.29s | MRSA isolates from hospitals
5/5 asked | L | {'ask_back': 5} | max 0.25s | Breast cancer genes in young women
0/5 asked | L | {'proceed': 5} | max 0.25s | Mycobacterium tuberculosis genome assemblies please
0/5 asked | L | {'proceed': 5} | max 0.53s | Vitamin D and COVID-19 outcomes
calls 170 median 0.22 p90 0.313 max 0.73 over1.0 0 nopick 0
```
- Why a person would care: search-box shorthand ("MRSA isolates from hospitals", "Breast cancer genes in young women") is how many people type. Each of these names a subject, the kind of record and a filter; the person gets a menu, every time, where develop searches. In total this round found 12 real questions asked back that develop searches (J2-48-01, 02, 07), every one of them on every run or 4 of 5.
- NOT FIXED

### J2-48-08: With the guard tier deciding (the code default), 47 of 51 decisions run past the 1.0 s bound; no regression measured there, and the card does almost nothing
- Severity: minor (record; matches V-48-03)
- What: `CLASSIFIER_PROVIDER=guard`, `deepseek/deepseek-v4-flash`. On the longer path almost every decision is cut by `_LONG_ASK_BACK_WAIT_S` and searched, so neither the regressions above nor the broad-subject ask-back happen; on the short path the four regressed short texts proceed with the guard tier on both sides.
- Reproduction: same probe, `PROBE_PROVIDER=guard`, three runs each, three in flight, pasted (branch, then develop):
```
branch : calls 51 median 1.428 p90 2.279 max 3.133 over1.0 47 nopick 0
branch : 0/3 asked | L | {'proceed': 3} | max 1.47s | Tell me about the tree of life.
branch : 0/3 asked | S | {'proceed': 3} | max 2.53s | Lyme disease treatment
branch : 0/3 asked | S | {'names_a_record': 2, 'proceed': 1} | max 0.92s | BRCA1 c.68_69delAG
develop: calls 51 median 1.414 p90 2.854 max 11.861 over1.0 46 nopick 0
develop: 2/3 asked | S | {'ask_back': 2, 'proceed': 1} | max 1.82s | BRCA1 c.68_69delAG
develop: 3/3 asked | S | {'ask_back': 3} | max 1.69s | rs334
```
- Why a person would care: on production (guard tier, per V-48-03) a person typing `Tell me about the tree of life.` will be searched as today, so the owner's test of the card on develop with Jev will not carry over. The short path's record judgement does carry over and helps there (`rs334` 0 of 3 asked versus 3 of 3 on develop).
- NOT FIXED

### J2-48-09: Record: offline, only an `ask_back` pick asks, the record check only forces a search, late or failed decisions search, and the first-message gate holds
- Severity: minor (record of properties that held)
- What: the branch's real `think_node`, with `_decide_point` (only `think.ask_back` answering), the choices writer and Think's classification stubbed, no network. Every property in checklist item 1 held. A first draft of my stub built an invalid `DecisionRecord` that raised inside the decision task; every one of those runs searched, which is the fail-open rule on an exception.
- Reproduction: own script `<scratchpad>/probe/offline_think.py`, output (outcome, Think seconds, decisions asked), pasted in part:
```
ask_back | Tell me about the immune system. | ('ASKED', 0.0, 1)
names_a_record | Tell me about the immune system. | ('SEARCHED', 1.0, 1)
names_a_record | immune system | ('SEARCHED', 1.0, 1)
None | Tell me about the immune system. | ('SEARCHED', 1.01, 1)
ask_back | Tell me about PMID 33057194. | ('SEARCHED', 1.04, 1)
ask_back | rs334 | ('SEARCHED', 1.02, 1)
proceed | rs334 | ('SEARCHED', 1.01, 1)
classify 1.0 delay 0.95 | ('ASKED', 0.99, 1)
classify 1.0 delay 1.05 | ('SEARCHED', 1.03, 1)
classify 0.1 delay 3.0 | ('SEARCHED', 1.02, 1)
classify 0.1 delay 30.0 | ('SEARCHED', 1.0, 1)
same session | Tell me about the immune system. | ('ASKED', 0.0, 1)
same session | What does recent research say about it? | ('SEARCHED', 1.0, 0)
same session | Tell me about apple trees. | ('SEARCHED', 1.0, 0)
```
  Lengths through the seam's own limit: instructions 884, criteria ask_back 480, proceed 881, names_a_record 482 characters, all under `_DESCRIPTION_MAX_CHARS` 1000; every one of the 610 live Jev calls in this round returned `decided_by` jev with no fallback reason, so no call was refused by the limit.
- Why a person would care: the wiring is sound; the defect in this round is the classifier's reading (J2-48-01, 02, 07), not the code around it. A slow decision adds at most about 0.9 s when Think's own classification is fast (0.1 s classification, 3.0 s decision: Think 1.02 s).
- NOT FIXED

### J2-48-10: Record: no word list and no test question in the prompt; the only overlap is the generic phrase "what is known about"
- Severity: minor (record, checklist item 2 holds)
- What: the decision is made by the classifier; code only checks the pick and runs the existing identifier parsers. The prompt names no subject from the test material.
- Reproduction: own scan, every four-word run of `_ASK_BACK`'s instructions and three criteria against 932 sources (every backticked text in `testing/Test_queries_and_workflows.md` and every quoted string in the card's test file), plus 15 subject names. Output pasted:
```
('what is known about', 'Compare what is known about MLH1 and MSH2 in colorectal cancer risk.')
('what is known about', 'What is known about EGFR mutations in non-small cell lung cancer, and what trial')
('what is known about', 'What is known about Salmonella isolate SAMN02147118 in Pathogen Detection?')
n sources 932
NAME IN PROMPT: isolate
```
  "isolate" appears only as a kind of record ("a trial, an isolate or a dataset given by its own code"). Unsure, not a breach: the `proceed` criterion has grown a clause per failed probe shape (what is known, what the research says, how or why, a patient or case, a pasted text). That is shape-by-shape tuning, and J2-48-07 shows an unlisted shape (subject, collection word, filter) falling through to ask_back.
- NOT FIXED

### J2-48-11: Latency: the decision costs no measurable wait on a real question with Jev; the end-to-end difference is inside the noise
- Severity: minor (record, checklist item 4)
- What: Jev decision time on the branch's longer spec is the same as develop's spec; the bound holds; whole-turn timings vary far more than any effect of the card.
- Reproduction: decision time, Jev, 345 calls per side (J2-48-03 runs), pasted: branch `calls 345 median 0.221 p90 0.345 max 1.075 over1.0 1 nopick 0`; develop's spec `calls 345 median 0.218 p90 0.335 max 1.46 over1.0 4 nopick 0`. Guard tier: `median 1.428 p90 2.279 max 3.133 over1.0 47` of 51 (J2-48-08). End to end through `run_streaming`, four real questions three times per side, Think step seconds (think event minus guard event): `branch ... think step median 2.67 max 7.95 to plan median 5.48 max 16.80`; `develop ... think step median 2.21 max 5.26 to plan median 4.62 max 11.00`. The 16.80 s branch run had a 10.82 s guardrail step before Think started; the develop run of the same text took 11.00 s with a 5.74 s guardrail. Offline (J2-48-09) the most the decision can add is about 0.9 s, and only when Think's own classification is faster than the decision.
- Why a person would care: no slower answer to a real question was attributable to the card. Twelve runs a side cannot rule out a few hundred milliseconds; the offline bound is the stronger evidence.
- NOT FIXED

### J2-48-12: Query 112 and the build report tell the owner real questions are not asked back; the gate document's own queries 44 and 84 now fail
- Severity: major
- What: query 112's Known line says the classifier "asked back none of 118 real questions", and the build report files `ESBL E. coli isolates?` under "Pre-existing, not changed". Query 44 (`ESBL E. coli isolates?`) and query 84's control (`recent-onset diabetes treatment` "is not asked back") fail on the branch on every run (J2-48-05). Neither document mentions isolate or "subject treatment" shapes.
- Reproduction: J2-48-01, J2-48-02, J2-48-05 output above; `testing/Test_queries_and_workflows.md` lines 883 to 894 and 1627 to 1639 at fc218c0c.
- Why a person would care: the owner tests from that document. Its new query says real questions are safe while two of its older queries now regress, so a tester following query 112 alone would pass a change that breaks queries 44 and 84.
- NOT FIXED

## Gates and mutations

| Check | Result |
|---|---|
| `ruff check` (no path), branch worktree | All checks passed, exit 0 |
| `isort --check-only src tests services tracker alembic .claude .github` | exit 0 ("Skipped 2 files") |
| `pytest tests/system_03_search_agent/core tests/system_03_search_agent/harness -m "not integration" -q` | 2132 passed, 56 skipped, 1 deselected |
| Card tests baseline (`test_bare_topic_clarification.py`, `test_clarify.py`) | 117 passed |
| M1: `_cancel_if_pending(long_ask_task)` replaced by `pass` | 1 failed, 116 passed; restored |
| M2: `long_ask_deadline = step_deadline` (1.0 s bound dropped) | 1 failed, 116 passed; restored |
| M3: longer path asks on `names_a_record` too | 2 failed (`test_a_names_a_record_pick_searches_and_never_asks[Tell me about the immune system.]`, `test_a_names_a_record_pick_writes_no_choices_on_the_longer_path`); restored |
| Production standards | no new dependency, no endpoint, log lines carry the trace id and class names only, the person's text reaches the classifier only as the bounded user message, `_BEGUN` bounded at 4096, the owner's redesign row is in DECISIONS.md (2026-10-15); no local path or private value in the diff |

No unit test can catch J2-48-01, 02 or 07: they are the live classifier's reading, so only live probes against develop find them.

Spend: OpenRouter account usage 93.774792012 before, 93.958202598 after, 0.18 USD on a shared account (an upper bound): about 1,100 decision calls, 24 end-to-end runs stopped at Plan or at the question back, 12 latency runs.

## Verdict

FIX FIRST: J2-48-01, J2-48-02, J2-48-07 (blocking), with J2-48-05 as their end-to-end evidence, and J2-48-12 (major).

Against the bar, nothing worse than develop for a person: twelve real questions that develop searches are asked which aspect on the branch, eleven of them on every run of five and one on four of five. Two are the owner's own gate queries (44 and 84). The shapes are terse isolate questions (`ESBL E. coli isolates?`, `Klebsiella pneumoniae isolates with carbapenemase genes`, `MRSA isolates from hospitals`), a subject with "treatment" (`Lyme disease treatment`, `recent-onset diabetes treatment`, both on develop's own one-to-three-word path, changed because both paths read the same `_ASK_BACK` text) and a subject with a filter (`Breast cancer genes in young women`). Today's redesign did not cause them: the pre-redesign head 36b5747d asks back all seven first-batch texts 5 of 5 (J2-48-06). But they sit inside this pull request's own rewrite of `_ASK_BACK`, built and fixed during this card, and the build report presents the lead example as pre-existing. Under the review loop's stop condition this goes to the product owner, not into another round.

What held: the redesign's record judgement (24 record texts, every one `names_a_record` and searched; better than develop on bare identifiers, J2-48-04), the broad subjects (5 of 5 asked, 25 calls), 26 of the test queries document's numbered questions and 44 other real questions (0 asked), the wiring (J2-48-09), the latency bound (J2-48-11), the prompt (J2-48-10) and every gate.

Verified with my own probes: every pick and asked count above (live `_decide_point` against each worktree's own `_ASK_BACK`, Jev and the guard tier, five runs per text with Jev); the four regressions end to end through `run_streaming` on both sides (J2-48-05); the pre-redesign comparison (J2-48-06); the wiring, fail-open, bound and first-message properties (offline `think_node`); the 1,000-character limit (measured lengths and 610 live Jev calls with no fallback); the prompt scan; the three mutations; ruff, isort and the unit suite. Only read, not run: production's worker count and the persistence of `_BEGUN` across restarts (covered by V-48-05), the web client's handling of clicked choices, and the guard tier's relevancy verdict on these texts.
