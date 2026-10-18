# Card 56 follow-up: judge round 1

Judge for `fix/card56-empty-extraction` (58ef6d46, 127e7dff on 5efef45d). Findings are appended as established; checklist verdicts follow at the end.

## Findings

### J-56-01: a hyphen-joined word with a digit is now a disease candidate, so "type-2" binds unrelated MedGen records

- Severity: blocking
- Inside this phase's fix: yes, part 3 (`_gene_shaped_fallback_candidates`, src/system_03_search_agent/core/graph.py:3587-3616, rule at 3605-3613).
- In the user's words: a person asks "What causes type-2 diabetes?", Think's model returns no entity (the habit this card measured at 5 in 26 on another question), and the answer is built on up to eight MedGen records whose names merely contain "type", such as "Type I radial ray deficiency" and "GSTP1 polymorphism, type A". On develop the same reply bound nothing.
- Evidence: the candidate rule now offers any whole hyphen-joined word of 12 characters or less that starts with a letter and carries a digit. Probe of the pure function: "What causes type-2 diabetes?" gives `['type-2']` (develop `[]`); "Results of phase-3 trials at day-14" gives `['phase-3', 'day-14']` (develop `[]`); "CD4-positive T cells in HIV-1" gives `['CD4-positive', 'CD4', 'HIV-1']`. `resolve_disease_mention_to_curies` (graph.py:3192) splits on hyphens and drops one-character words, so "type-2" is searched as `type[title]`: live MedGen ESearch for that term returned count 4293 (a free NCBI call, no model). Rule 2 binds up to `_MAX_DISEASE_CURIES_PER_MENTION` (8) of the first 20, title phrase hits first, then any name-index hit. End to end through `think_node` with the test file's own fakes and three of those live titles served for `type[title]`, reply `{"entities": [], "record_type": "none"}`: this branch printed `RESOLVED [('type-2', 'MedGen:C6066810'), ('type-2', 'MedGen:C6055347'), ('type-2', 'MedGen:C6065968')]` and narrative "(type-2: 3 MedGen records matched by name)"; the same probe against develop's graph.py printed `RESOLVED []`, `SEARCHED []`. The builder's own reason for the leading-letter rule ("the disease fallback binds by-name hits, so each would be a new chance of a confident wrong record") applies equally to "type-2", "phase-3", "day-14", "grade-3", "stage-4", none of which the digit-and-letter rule stops.
- Suggested fix: try a whole hyphen-joined word only as a gene candidate, not a disease candidate, or require the whole word's disease binding to be rule 1 (exact title) or a title phrase hit only (no by-name tier); or require each hyphen-separated part of at least two characters, so the digit cannot be a lone one-character suffix that the MedGen search then drops.
- NOT FIXED

### J-56-02: whole hyphen-joined words take fallback slots and all-capital pieces are dropped, so gene and disease questions lose names develop found

- Severity: non-blocking (reachable only when Think names no usable gene span; a regression all the same, inside this phase's fix)
- Inside this phase's fix: yes, part 3, graph.py:3587-3616 with the cap `_MAX_FALLBACK_CANDIDATES` (3).
- In the user's words: "Compare TP53-mutant and KRAS-mutant and EGFR-mutant tumours" with no entity from Think now looks up "TP53-mutant" and "TP53" and never KRAS or EGFR; develop looked up all three genes. "What diseases are linked to MERS-CoV?" now offers nothing at all (develop offered "MERS"), and "SARS-CoV" (the SARS virus itself) now offers nothing where develop offered "SARS", which was correct for that question.
- Evidence: my probe calling `_gene_shaped_fallback_candidates(q, [])` on this branch and on develop's graph.py (copied to a scratch tree):
  - "Compare TP53-mutant and KRAS-mutant and EGFR-mutant tumours": branch `['TP53-mutant', 'TP53']`, develop `['TP53', 'KRAS', 'EGFR']`.
  - "What diseases are linked to MERS-CoV?": branch `[]`, develop `['MERS']`.
  - "Find SRA runs of SARS-CoV": branch `['SRA']`, develop `['SRA', 'SARS']`.
  - "NKX2-5 variants": branch `['NKX2-5', 'NKX2']`, so a single gene costs two of the three live slots.
  The build report names the residual only as "CFTR-related"; it does not say a whole word spends a slot ahead of its own piece, nor that disease acronyms (MERS, SARS for SARS-CoV, ALS in "ALS-linked") are lost the same way.
- Suggested fix: offer the whole word and its digit-bearing piece as one slot (try the whole, fall to the piece only if the whole fails), and state the disease-acronym residual beside the gene one, or have the owner decide whether "MERS-CoV" losing MERS is acceptable.
- NOT FIXED

### J-56-03: the contradiction retry also fires on accession and gene SRA questions, where it cannot change the answer

- Severity: non-blocking (speed and spend; the owner's no-degradation rule covers speed)
- Inside this phase's fix: yes, part 1, graph.py:4050-4053 and `_wants_organism_records_but_names_none` at 4057-4068.
- In the user's words: "Which SRA runs come from BioSample SAMN02604091?" waits for a second Think call (the build report measured 1.6 to 3.1 s, median 2.4 s) whenever the model sets `record_type` "sra" and tags no organism, which is the natural reply to an accession question. The accession path then ignores the model's entities, so the extra wait buys nothing. The same holds for "Find SRA runs of BRCA1 knockout cells" with BRCA1 tagged as a gene: the gene resolves and the organism route is shut by `not model_resolution.curies` (4497) whatever the second reply says.
- Evidence: probe through `think_node` with the test file's fakes, first and second reply identical:
  - "Which SRA runs come from BioSample SAMN02604091?", reply `entities: [], record_type: sra`: `think calls 2`.
  - "Which genome assemblies come from GCF_000001405.40?", `record_type: assembly`: `think calls 2`.
  - "Find SRA runs of BRCA1 knockout cells", BRCA1 tagged gene: `think calls 2`, resolved `['NCBIGene:672']`.
  The check reads only the reply (by design), but `accession_plan`, `window` and `isolate_question` are all known in `_think` before `classify_task` starts (4342-4366), and `organism_unnamed` already excludes them (4449-4455), so the retry and the gate disagree about when an organism is missing.
- Suggested fix: pass a flag into `_run_think_classification` so the retry is skipped when a window, accession or isolate shape was parsed, and consider skipping it when the reply tags a gene or disease span (the case `organism_unnamed and not resolved_entities` can never ask about).
- NOT FIXED

### J-56-04: both adjacent defects the builder flagged are real, and together they route an SRA question around this card's fix

- Severity: non-blocking for this card's merge (the code is from #173, outside this diff), but it reopens part 1 and part 2 on the parse-retry path, so it should be fixed with the card rather than filed away
- Location: graph.py:4019-4030 (the parse retry message) and graph.py:2652 (`known_keys = {"query_class", "narrative", "entities"}`).
- In the user's words: when Think's first reply is malformed, the second reply is told to use exactly three keys, so a model that obeys drops "record_type"; the question then reads as "not an SRA question", neither the organism retry nor the organism question happens, and the person who typed SARS-CoV-2 is asked "which gene, variant or condition do you mean?".
- Evidence, both confirmed by probe:
  - Parse retry: first reply `not json`, second reply `{"query_class", "narrative", "entities": []}`. The captured retry message ends `using exactly these keys: "query_class", "narrative", "entities". No other key name for the reasoning field is accepted.` Outcome: 2 calls, no contradiction retry, gene lookups `['SRA', 'SARS-CoV-2']`, MedGen searches `SRA[title]` and `SARS[title] AND CoV[title]`. Both return count 0 on live MedGen (checked with two free ESearch calls), so live the person gets `CLARIFICATION_QUESTION` (graph.py:6569), a gene question, rather than the organism question.
  - Repair: `_parse_think_classification` on `{"query_class": "exploratory", "why": "x", "entities": [{"text": "SARS-CoV-2", "entity_type": "organism"}], "record_type": "sra"}` raised `ThinkClassificationUnavailableError ... (narrative: Field required; why: Extra inputs are not permitted)`: the synonym repair refuses because `record_type` is not a known key, so a well-formed SRA reply goes to the parse retry above and can lose its record type there.
  - Does it undermine the fix: yes, on that subset only. It does not bring back the SARS disease answer (the whole name binds nothing live), but it does bring back a wrong question to the person. The build's live run 4 needed the parse retry and kept "sra", so the model does not always obey; the rate is unmeasured.
- Suggested fix: add "record_type" to the parse retry's key list and to `known_keys`; add a test that a parse-retried reply keeps its SRA route.
- NOT FIXED

### J-56-05: an SRA question that names a gene but no organism now asks which organism, and a mistyped gene loses its refusal by name

- Severity: blocking (it contradicts the brief's "a mistyped gene keeps its refusal" whenever the question names no organism; the builder recorded it as a choice, "the organism question is asked even beside a failed gene span", so the lead or owner may accept it instead)
- Inside this phase's fix: yes, part 2, graph.py:4449-4461 (the gate on the gene fallback) and 4675-4680 (the question overrides the refusal).
- In the user's words: "SRA runs of BRCA9 knockouts" used to answer "BRCA9 was not recognised as a gene"; now it asks "which organism's SRA sequencing records do you want? ... for example "Escherichia coli SRA sequencing records"", so the typo is not pointed out until a later turn. "SRA runs of BRCA1 knockout cells", when Think's reply tags nothing, used to find BRCA1 through the token fallback; now the fallback is skipped and the person is asked for an organism, with an E. coli example, about a human gene.
- Evidence: probe through `think_node`, both replies identical, gene resolver faked (BRCA1 resolves, BRCA9 does not), on this branch and on develop's graph.py:
  - "SRA runs of BRCA9 knockouts", reply BRCA9 tagged gene, `record_type: sra`: branch `calls 2`, `unresolved ['BRCA9']`, clarify = the organism question; develop `calls 1`, `unresolved ['BRCA9']`, clarify None (the BRCA9 refusal).
  - "SRA runs of BRCA1 knockout cells", reply `entities: []`, `record_type: sra`: branch `calls 2`, `genes asked []`, `resolved []`, clarify = the organism question; develop `calls 1`, `genes asked ['SRA', 'BRCA1']`, `resolved ['NCBIGene:672']`.
  The builder's mistyped-gene test (`test_a_mistyped_gene_keeps_its_refusal`) only uses "... in human cells", where an organism is named, so it cannot see this.
- Suggested fix: when a model gene span failed, keep the refusal that names it (or name it in the organism question: "BRCA9 is not a recognised gene, and which organism ..."); and let the gene-shaped fallback run, without the disease fallback, when the organism is unnamed, so a real gene still resolves.
- NOT FIXED

### J-56-06: part 3 knows only the ASCII hyphen, so "SARS-CoV-2" typed with a Unicode hyphen or a space is still cut to "SARS"

- Severity: non-blocking (unchanged from develop on these inputs; the SRA path is covered by part 2's gate, the record-type "none" path is not)
- Inside this phase's fix: yes, part 3's pattern `_HYPHEN_JOINED_WORD_PATTERN`, graph.py:3490. It enumerates one character, `-`, where the class is any dash or hyphen (Review rounds rule 2, "fix by category").
- In the user's words: a person who pastes "SARS‑CoV‑2" from a web page or paper (U+2011 non-breaking hyphen, U+2010 hyphen, U+2013 en dash) or types "SARS CoV 2" still has "SARS" offered as a gene and disease candidate when Think tags nothing and the question is not read as an SRA question.
- Evidence: `_gene_shaped_fallback_candidates(q, [])` with "Find SRA runs of SARS<X>CoV<X>2 sequenced on Illumina": U+2011 gives `['SRA', 'SARS']`, U+2010 `['SRA', 'SARS']`, U+2013 `['SRA', 'SARS']`, a space `['SRA', 'SARS']`, "SARS-CoV-2_omicron" `['SRA', 'SARS']`. ASCII "SARS-CoV-2" gives `['SRA', 'SARS-CoV-2']`. Live MedGen `SARS[title]` binds the three SARS records the diagnosis measured.
- Suggested fix: normalise Unicode dash punctuation (category Pd, plus U+2212) to `-` before the candidate scan, and decide whether a space-separated "SARS CoV 2" is in scope.
- NOT FIXED

### J-56-07: a second reply that drops the record type is taken, which turns the SRA question into a gene question

- Severity: non-blocking (unsure; the builder chose it deliberately and tests it as a populate check)
- Inside this phase's fix: yes, part 1, graph.py:4133-4136.
- In the user's words: if the model answers the contradiction retry by changing "sra" to "none" instead of naming the organism, the person who asked for SARS-CoV-2's sequencing runs is asked "which gene, variant or condition do you mean?" rather than which organism, and the question never reaches the SRA search.
- Evidence: probe, first reply `entities: [], record_type: sra`, second `entities: [], record_type: none`: 2 calls, then both fallbacks run (`genes ['SRA', 'SARS-CoV-2']`, MedGen `SRA[title]` and `SARS[title] AND CoV[title]`); both MedGen terms return count 0 live, so the run ends at `CLARIFICATION_QUESTION`. Keeping the first reply would have asked the organism question, which is the more accurate ask. The retry message tells the model only that the two fields disagree, so dropping the record type is an equally obedient answer.
- Suggested fix: use the second reply only when it names an organism; a second reply that resolves the contradiction by dropping the record type keeps the first, so the person is asked which organism.
- NOT FIXED

### J-56-08: the retry gets a fresh 45-second budget, not what is left of Think's, so its docstring's "Think's step budget applies" is not true

- Severity: non-blocking (tail latency; the owner's 20-second answer rule)
- Inside this phase's fix: yes, part 1, graph.py:4124-4132 and the docstring at 4096-4098.
- In the user's words: on the path that needs both retries (a malformed first reply, then a contradictory second), Think can now make three plan-tier calls in a row, each allowed the full 45 seconds, where develop allowed two.
- Evidence: `_retry_contradictory_classification` calls `_dispatch_tier_call(..., budget_s=budget_for_step("think", "lookup"))`, which is `_TIER_STEP_BUDGET_S["plan"]` = 45.0 (harness/harness.py:479-483), passed to `enforce_timeout` as a per-call timeout; `step_deadline` (graph.py:4174) is not passed in and `outcome = await classify_task` (graph.py:4390 area) is not bounded by it. My probe with first reply `not json`, second contradictory, third naming SARS-CoV-2 made 3 calls (`PARSE+CONTRA calls 3`). A slow retry also spends the deadline that `_failed_spans_that_are_conditions` later waits on, so part 4 then fails to the refusal (safe, but a lost answer).
- Suggested fix: give the retry `max(0, step_deadline - now)` as its budget (pass the deadline into `_run_think_classification`), and skip the retry when the parse retry already ran; or correct the docstring.
- NOT FIXED

### J-56-09: the test fake binds the SARS disease records for the whole name "SARS-CoV-2", which live MedGen does not

- Severity: non-blocking (instrument, not product)
- Location: tests/system_03_search_agent/core/test_think_empty_extraction.py, `_install_ncbi`, `params.term.startswith("SARS[title]")`.
- What: since part 3 sends "SARS-CoV-2" whole, the disease fallback's term is `SARS[title] AND CoV[title]`, which the fake answers with the three SARS records (prefix match). Live MedGen returns count 0 for that term (checked). So `test_with_no_record_type_the_fallbacks_still_run` binds the SARS disease records without saying so, and no test pins the property the brief states, that the SARS-CoV-2 question on the record-type "none" path never binds SARS. My probe with record type "none" printed `resolved ['MedGen:C1519126', 'MedGen:C4302012', 'MedGen:C4302019']` under the fake.
- Suggested fix: match the fake on the exact term `SARS[title]`, and assert in the populate check that no SARS record is bound.
- NOT FIXED

### J-56-10: two of the fix's three bounds on model text have no test that can fail

- Severity: non-blocking (the code is right today; nothing would notice if it stopped being right)
- Inside this phase's fix: yes, parts 1 and 4.
- What: I broke each bound on a scratch copy of `src/` (the worktree was not touched, since the adversary may be probing it) and ran both test files with `-o pythonpath=<copy> .`:
  - Mutant E, the contradiction retry's echo unbounded (`first_content` in place of `first_content[:_THINK_RETRY_ECHO_CHARS]`, graph.py:4108): `48 passed`. The test at test_think_empty_extraction.py:204 asserts `echo == first[:_THINK_RETRY_ECHO_CHARS]`, but `first` is a short reply, so the slice is a no-op and the assertion holds with or without the bound.
  - Mutant C, the condition span in the narrative unbounded (`span` in place of `_bounded_one_line(span, _MAX_CONDITION_SPAN_CHARS)`, graph.py:3077-3081): `48 passed`. No test passes a long or multi-line span.
- Why it matters: both strings are model output placed in a prompt (the echo) or in user-visible text that a later model reads (the narrative); the bound is the production-standards bounded-context obligation, and the file's comments assert it.
- Suggested fix: feed a 1,000-character first reply and assert the echo is 300; feed a 200-character span with a newline and assert the narrative clause carries one line of at most 60 characters plus the elision note.
- NOT FIXED

### J-56-11: the lint gate fails in the worktree today, on the adversary's untracked probe

- Severity: non-blocking for the builder's commits; blocking for any commit that adds that file as it stands
- Location: testing/Developer/reports/2026-10-06_card56/raw/adversary/offline_probe.py:14-17 (untracked, not in 58ef6d46 or 127e7dff).
- Evidence: `PATH=<main venv>/bin:$PATH bash .github/gates/gate03_lint.sh` exited 1 with "Found 4 errors. [*] 4 fixable", all four in that file (unused `noqa: E402` and import order). `ruff check src tests testing/Developer/reports/2026-10-06_card56/raw/think_probe.py` printed "All checks passed!", so the committed change is clean. Report folders count as source for this gate.
- Suggested fix: `ruff check --fix` on the adversary's probe before it is committed, as the builder did for `think_probe.py`.
- NOT FIXED

### J-56-12: part 4's "not applied" clause is the only notice that Illumina was ignored, and the 500-character cut removes it

- Severity: non-blocking (the cut is from before this card, but part 4 is the first path that relies on the tail of the narrative to say a named condition was dropped)
- Inside this phase's fix: yes, part 4 depends on it; the cut is graph.py:4702-4707 (`[:500]` after the disclosures are appended).
- In the user's words: when Think's own narrative runs long, the person reads "... by organism alone, so Illumina and any other cond" and is never told that their Illumina condition was not applied to the records they are shown.
- Evidence: probe through `think_node`, SARS-CoV-2 tagged organism, Illumina tagged gene and called a condition, model narrative of n characters: n=30 gives a 225-character narrative with "not applied" present; n=250 gives 445 with it present; n=350 gives 500 with "not applied" absent and "Illumina" present. The schema allows a 500-character model narrative (graph.py:2422 area, `max_length=500`). The live runs' rows do not record the narrative, so how often this happens was not measured; the build report says Act and Write were not run, so whether the answer text restates it is also unseen.
- Suggested fix: put the disclosures ahead of the model's narrative, or cut the model's narrative, never the disclosures, so the 500 limit can only trim the model's prose.
- NOT FIXED

### J-56-13: the decision state carries model-written span text unnormalised

- Severity: non-blocking (minor; low harm)
- Inside this phase's fix: yes, part 4, graph.py:3122-3123 (`f"Question: {query_text}\nSpan: {span}"`).
- What: `decide`'s contract (harness/decide.py:437-438) says the state "stays the person's bounded text only"; this point adds the model's span, which is up to 200 characters, may carry a newline copied from the question, and is not passed through `_bounded_one_line` as the narrative copy is. A question written so the model copies "Illumina\nSpan: sequencing platform" as one span shows the classifier two "Span:" lines. The worst outcome is a mistyped gene released as a condition, which runs the organism search with a disclosure naming it as not applied, so the harm is a lost refusal rather than a wrong record. The overall length is safe: 2,000 (Query.text max) plus 200 plus labels is under decide's 4,000 cut.
- Suggested fix: pass the span through `_bounded_one_line(span, _MAX_CONDITION_SPAN_CHARS)` before it enters the state, and note in the spec's docstring that the state carries one model span.
- NOT FIXED

### Line corrections to the findings above

Exact lines on 58ef6d46, from `grep -n`: J-56-13's state string is graph.py:3120; J-56-12's cut is graph.py:4704-4709; J-56-08's unbounded wait is `outcome = await classify_task` at graph.py:4362 and the retry's budget at 4130; J-56-01's whole-word rule is graph.py:3610-3616; the narrative schema bound is graph.py:2422.

## Checklist verdicts

| Item | Verdict | Evidence |
|---|---|---|
| 1a. Part 1, contradiction retry | Pass with findings | Fires once and only on the contradiction (graph.py:4050, 4057-4068); cap hit, call failure and unusable reply keep the first reply (4137-4142), read and covered by the tests' three cases. Mutant B (trigger reads "no entities" instead of "no organism") went red in 2 tests. Findings: J-56-03 (fires where it cannot help), J-56-07 (a "none" second reply is taken), J-56-08 (fresh 45 s budget). After a parse retry the contradiction retry is a third call (probe: `PARSE+CONTRA calls 3`, resolved `NCBITaxon:2697049`) |
| 1b. Part 2, ask instead of guessing | Fail | J-56-05: a named but mistyped gene loses its refusal and a real gene is no longer found when no organism is named. Taxonomy-rejected span: asked, by reading `organism_spans` at 4402 and the test |
| 1c. Part 3, never cut a name | Fail | J-56-01 (blocking, new confident-wrong disease bindings), J-56-02, J-56-06. 12-character cap: "SARS-CoV-2-positive" gives `[]` (probe). Whole words starting with a digit: "5-HTTLPR" gives `[]`, "2020-2021" stays out |
| 1d. Part 4, gene or condition | Pass with findings | All-or-nothing at 3135; at most 3 decisions, more spans release nothing (3112); deadline-bounded and fail-open to the refusal (`_usable_choice`, 1278). Mutant A (first record only, in place of all) went red. Findings: J-56-12, J-56-13 |
| 2. No regression for gene, disease, window, accession, isolate | Fail | Gene and disease regress through part 3 (J-56-01, J-56-02) and part 2 (J-56-05). Window, accession and isolate are excluded from the gate (4449-4455) and from part 4 (4494-4502) but not from the retry (J-56-03, extra call measured by probe on two accession questions) |
| 3. Decision cap and schema | Pass | No file under `contracts/` in the diff (`git diff --stat`). Points: relevancy, injection, ask_back, recent_years, literature, asks_features, paper_links, and at most 3 gene_or_condition (3112) = 10, under `max_length=16` (contracts/events.py:604); `_done_decisions` also slices to 16 (graph.py:1245), so no path can exceed it. A cancelled decision is never appended (1274 runs after the await) |
| 4. Security and production gates | Pass with findings | Ask-back text is fixed strings plus a schema-literal record type (`_which_organism_question`, `_ORGANISM_RECORD_WORDS`); the retry message interpolates only the literal record type; the log line carries the bounded error text only. No Cypher, SQL or URL built. Cite-or-refuse not loosened: a released condition still routes to Taxonomy-cited SRA records with a disclosure. Gaps: J-56-10 (two bounds untested), J-56-12, J-56-13 |
| 5. The two adjacent #173 defects | Both confirmed | J-56-04, with probe output for each. They undermine the fix on the parse-retry path: the person is asked for a gene instead of an organism. They do not bring back the SARS disease answer, because the whole name binds nothing on live MedGen |
| 6. Tests run and broken | Partly | `48 passed in 2.72s` for the two files. Four single-property mutants on a scratch copy of `src/` (the worktree untouched): A red (1 test), B red (2 tests), C green, E green (J-56-10). `git status` after: only the untracked judge.md and the adversary's files |
| 7. Lint gate | Fails in the worktree, clean on the commits | J-56-11: 4 errors, all in the adversary's untracked probe; `ruff check src tests .../raw/think_probe.py` printed "All checks passed!" |

## Verified by my own probes, versus only read

- Probed: J-56-01 (end to end through `think_node` on this branch and on develop's graph.py, plus one live MedGen ESearch and ESummary), J-56-02 and J-56-06 (pure function, branch and develop), J-56-03, J-56-04, J-56-05, J-56-07, J-56-08's three-call path, J-56-10 (mutants), J-56-12 (narrative cut), the decision-cap arithmetic's per-span cap (by reading 3112, with mutant A for the all-or-nothing rule), the two test files and the lint gate. NCBI was called four times in all (free E-utilities, no model): MedGen `SARS[title] AND CoV[title]` 0, `type[title]` 4293, `phase[title]` 101, `SRA[title]` 0; Gene `SRA[sym] AND human[orgn]` and `SARS[sym] AND human[orgn]` 3 ids each, so neither resolves under the one-id rule.
- Read only: the cost-cap and call-failure handling in the retry (covered by the builder's tests, which I ran but did not mutate), the two-organism and Taxonomy-rejected paths, `_ORGANISM_RECORD_WORDS` wording, the claim that Write or Show work states "not applied" (nobody has run it), and the builder's live-run outcomes (I read the jsonl rows; the retry path's Guardrail-to-Plan time was a median 6.5 s against 4.2 s for a plain run, from those rows).

## Not covered

- No live model call, so the rate at which the model drops "record_type" on the parse retry, or answers the contradiction retry with "none", is unmeasured.
- Act and Write, so the answer text on the released-condition path.
- Other plan models.
- Whether `resolve_organism` handles two named organisms correctly on the part 4 path beyond the builder's one test.

## Verdict

FAIL against the card's intent. Blocking: J-56-01 (part 3 binds unrelated MedGen records for "type-2" and similar words, a new confident wrong record) and J-56-05 (part 2 replaces a mistyped gene's refusal, and a real gene's answer, with an organism question when no organism is named; the builder chose this, so the lead may accept it instead). Both sit inside fixes made in this phase, which is Review rounds rule 4's stop condition: escalate to the owner rather than start another round.
