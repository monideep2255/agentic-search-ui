# Card 22 verify, round 2 (fresh verifier)

Branch fix/card22-name-every-total at db04a2e2, base develop d8179c4e. Probes run in detached worktrees verify22b (branch) and verify22b_dev (develop).

## Findings

Progress note (not a finding): confirmed-line probe `p_trust.py` (my scratch), real `trust_for_claims`, `aggregate`, `answer_trust_line`, 23 inputs, same inputs on both worktrees. V-22-01 (case F: cited ClinVar 17661, uncited LitVar2 and dbSNP) branch "Based on 1 source cited, not yet confirmed", develop "Based on 1 source"; addendum case (uncited dbSNP rs999 and PubTator) the same. Genuine agreement holds: ClinVar+LitVar2 docsum 2, ClinVar+dbSNP 2, ClinVar+dbSNP+OMIM 3, plus PubTator 4, two high-risk facts with 3 and 2 databases reads 2. An uncited OMIM beside cited ClinVar and dbSNP stays 2. No input reads a larger N on the branch than on develop.

Progress note (not a finding): restatement gate probe `p_gate.py`, real `run_grounding_pass` and `drop_record_restatements`, both worktrees. V-22-02's sentences ("Gene BRCA1 symbol [1].", "BRCA1 DNA repair associated description [n].") drop on the branch in both orders, as on develop. A relational sentence on the shared page is kept on both. A paper's abstract sentence under its title row is kept on both (item 12.12 holds). Two inputs differ from develop, both in the reader's favour: a sentence citing the graph gene row that only restates the live row on the same page is dropped (develop kept it), and with three records sharing one exact link a sentence restating the first is dropped (develop compared it only against the last). BRCA1 fixture probe `p_brca1.py` (18 citations): trust line "Based on 16 sources cited" (develop 17), rail 16 (develop 18), command line 16 reference lines with "[1][6][9] NCBIGene - .../gene/672/" in reversed citation order (develop 18 lines, gene page three times); gate drops 17 of 18 one-record sentences on both.

### V2-22-01: V-22-04's rebuilt "Confirmed by" tests still name three different variants, not "records of one variant"
- Severity: minor (test text and test data only; no code path reads it). Inside the last round's own fix for V-22-04 (commit adaa2510). Not a regression against develop: develop's test also used three variants.
- Where: `tests/system_03_search_agent/synthesis/test_answer_layout.py:352-358` (`CLINVAR_A`, `CLINVAR_B`, `LITVAR` and the comment "One variant's records"), the docstring at `:366-369`; `fix_round.md` "Last round" row V-22-04 makes the same claim. The card test file's confirmed tests use `/snp/rs80357713` beside ClinVar 17661 the same way.
- What: the three records the comment calls one variant's are three variants. ClinVar variation 17661 is BRCA1 c.181T>G (p.Cys61Gly), dbSNP rs28897672. RCV000019240 belongs to ClinVar variation 17671, BRCA1 c.3607C>T (p.Arg1203Ter), rs62625308. rs80357713 is BRCA1 c.66dup.
- Reproduction: public E-utilities, read only. `esummary db=clinvar id=17661` -> title "NM_007294.4(BRCA1):c.181T>G (p.Cys61Gly)", dbSNP xref 28897672. `esearch db=clinvar term=RCV000019240` -> idlist ['17671']; `esummary db=clinvar id=17671` -> "NM_007294.4(BRCA1):c.3607C>T (p.Arg1203Ter)", dbSNP 62625308. `esummary db=snp id=80357713` -> HGVS "NM_007294.4:c.66dup".
- Why it matters: V-22-04 asked that the tests stop holding different-variant agreement up as confirmation. The code compares by field and value only, so it cannot tell, and behaviour is unchanged. But the test now asserts by name that these are one variant, so the card that adds same-subject matching will find a test whose comment says its data is correct when it is not. The fix is data only: rs28897672 and an RCV of variation 17661 (for example RCV000019229, which `esummary` lists under 17661).
- NOT FIXED

V2-22-01 addendum: the same in the card's own test file, `tests/system_03_search_agent/synthesis/test_trust_line_names_its_count.py:127-135` ("The records below are about one variant"): `_CLINVAR` variation 17661, `_SNP` rs80357713 (c.66dup) and `_OMIM` `113705#0003`, where the ClinVar record of 17661 cross-references OMIM 113705.0002 (`esummary db=clinvar id=17661`, variation_xrefs). Still minor, data only.

### V2-22-02: two mutations of the code the last round touched survive, each with a behaviour change I could show
- Severity: minor (test gap; the shipped code behaves correctly on both inputs). G4 is inside the last round's own new line (commit 3a5f1919); T4 is fix-round code (488999b5) inside the function the last round rewrote. Not a regression against develop.
- Where: G4, `src/system_03_search_agent/synthesis/answer_layout.py:886-888` (the `or [None]` fallback in `drop_record_restatements`). T4, `src/system_03_search_agent/synthesis/trust.py:604-607` (`finding.field == claim_finding.field` in `_databases_backing`).
- What: each mutation applied alone in a scratch worktree of db04a2e2, `pytest -m "not integration" tests/system_03_search_agent/synthesis tests/system_03_search_agent/core`, restored with `git checkout -- src`, `git status` clean after.
  - G4, drop `or [None]`: "2004 passed, 66 skipped", same as unmutated. Behaviour it changes, my probe `p_g4t4.py`: a finding with no link, field `symbol` value `BRCA1`, narrative "Gene BRCA1 symbol [1].": branch and develop drop it (`dropped 1`); mutated keeps it (`dropped 0 ['Gene BRCA1 symbol [1].']`), so a restatement of a link-less record would sit above the list row that repeats it.
  - T4, drop the same-field check: "2004 passed, 66 skipped". Behaviour it changes: cited ClinVar 17661 and dbSNP rs28897672 both `clinical_significance` "Pathogenic", plus a cited OMIM record whose `title` is "Pathogenic": branch "Confirmed by 2 independent databases"; mutated "Confirmed by 3 independent databases". (develop on the same input: "Confirmed by 3 independent sources".)
- Why it matters: the same shape as V-22-03 and J-22-07, rules nothing holds. T4 is the overclaim this card exists to stop, one field-name check away, with no test on it. Each needs one small test: a link-less restatement dropped, and a different-field "Pathogenic" not counted.
- NOT FIXED

### V2-22-03: the W1 survivor is reachable: eight write steps in the existing suite leave prepared findings uncited, and W1 changes their trust line
- Severity: minor (test gap; the shipped call is correct). Inside the last round's fix for V-22-03 (commit adaa2510): the new spy test's docstring says "a call that passes the pool, or claims built from it, fails here", and `fix_round.md`'s Last round says W1 survived because "in every write path I could drive, the findings tail cites every prepared finding". Both are false. Not a regression against develop.
- Where: `src/system_03_search_agent/core/graph.py:13871`; `tests/system_03_search_agent/core/test_graph.py:1633-1677` (`test_the_trust_line_is_computed_from_the_cited_claims_only`).
- What: in a scratch worktree I wrapped the call at `graph.py:13871` so it returned the real line and also logged the line W1 would give (claims built from every `synth_findings` entry), then ran the whole unit suite (`pytest -m "not integration" tests/`). 429 write steps logged; 31 had prepared findings left uncited (abstract, pmid and `name` fields); in 8 the line differs. Examples: `test_write_completeness.py::test_a_repair_on_the_same_records_with_more_sentences_is_kept` real "Based on 2 sources cited, not yet confirmed", W1 "Based on 5 sources cited, not yet confirmed"; `test_write_findings_tail.py::test_a_tail_the_pass_strips_leaves_the_incompleteness_note` real "Based on 1 source cited, not yet confirmed", W1 "Based on 3 ...". The other six are in `test_write_completeness.py` (repair discarded, cost cap during repair, incomplete note, fallback note). The W1 mutation itself: "2004 passed, 66 skipped" on synthesis and core, same as unmutated.
- Why it matters: the reachable path is an incomplete answer, when the grounding pass strips part of the findings tail or a repair is discarded. There a W1-style change would make "Based on N sources cited" count records the reader cannot open, the exact count this card defines. The spy test pins "no keyword, three arguments, claims equal the citation events" on one scenario where the two sets happen to be equal, so it does not hold the property its docstring claims. One assertion on the trust line in an existing incomplete-answer test (for example the two above) would.
- NOT FIXED

### V2-22-04: a record with a CURIE and no link names its database in a different namespace from the same database's page, so one ClinVar record can read "Confirmed by 2"
- Severity: unsure, probably minor (reachability not established; `tools/cypher_provenance.py` says a graph row with no `source_url` is dropped by the cite-or-refuse gate, so the graph side may never produce one). Fix-round code (488999b5), not the last round's. Not a regression against develop: develop reads "Confirmed by 2 independent sources" on all three inputs below.
- Where: `src/system_03_search_agent/synthesis/trust.py:537-583` (`record_database`: a page gives `ncbi.nlm.nih.gov/clinvar`, the CURIE fallback gives `clinvar`).
- Reproduction: my probe `p_curie.py`, real `trust_for_claims`, `aggregate`, `answer_trust_line`. Cited graph row `clinical_significance` "Pathogenic", `source_url=""`, `curie="ClinVar:17661"`, plus a live `ncbi_efetch` of `.../clinvar/variation/17661/`: branch "Confirmed by 2 independent databases". The same pair with the graph row's link present: "Based on 1 source cited, not yet confirmed". `dbSNP:rs28897672` with no link beside the dbSNP page of the same rs: "Confirmed by 2 independent databases".
- Why it matters: if any surface can cite a link-less record with a CURIE, the reader sees two cards for one ClinVar record and "Confirmed by 2 independent databases". Mapping the CURIE prefix to the same key the page gives (ClinVar to `ncbi.nlm.nih.gov/clinvar`, dbSNP to `ncbi.nlm.nih.gov/snp`, NCBIGene to `ncbi.nlm.nih.gov/gene`) would close it.
- NOT FIXED

## The verifier's four findings, re-run

| Finding | Status at db04a2e2 | How I checked |
|---|---|---|
| V-22-01 (one cited ClinVar read "Confirmed by 3") | Fixed | `p_trust.py` cases F and F2, verify.md's exact shapes: "Based on 1 source cited, not yet confirmed" (develop "Based on 1 source"). Case H (graph row and live fetch of one record, uncited LitVar2): "not yet confirmed". No input of 23 gives a larger N than develop. |
| V-22-02 (gate compares against the wrong row) | Fixed | `p_gate.py`: both sentences dropped in both orders, as on develop. Mutations G1, G2, G3 caught. |
| V-22-03 (gate key and pool wiring untested) | Fixed for what it named; one gap left | Mutation G5 (gate keyed by exact link) caught; W3-shape and W4 (claims before the tail merge) caught. W1 survives and is reachable: V2-22-03. G4 survives: V2-22-02. |
| V-22-04 (tests pin different variants as one fact) | Partly | The LitVar2 record now uses the `/snp/` link the tool builds. The records named "one variant" are still three variants: V2-22-01. |

## Earlier fixes, spot-checked

| Fix | Result | How |
|---|---|---|
| Two-layer card | Holds | My own vitest probe (not the author's test): one page cited from layers 2, 3 and 1 in that order, plus a trial. Heading 2; one card "[1][2][3] NCBIGene 672", "L1 · graph, L2 · live, L3 · literature", under Knowledge graph; Live NCBI APIs and Enrichment groups each show "one card for this page, listed under Knowledge graph". `citedSourceCounts` pages 2, layers 3. The author's e2e passes at 1280 and 390. |
| Saved-answer screen | Holds | Same probe: slash pair across layers 1 and 2 plus a link-less row reads two rows, "1, 2. NCBIGene graph · live" and "3. x". |
| History rail count | Holds | `p_brca1.py`, `_citation_count` on the 18 fixture citations: 16 (develop 18). Not driven through a real reload. |
| Command line | Holds | `p_brca1.py`, citations fed in reverse order: 16 reference lines, "[1][6][9] NCBIGene - .../gene/672/" (develop 18 lines, gene page three times). |

## Mutations of the last round

Each alone in a scratch worktree of db04a2e2 (`verify22b_mut`), synthesis and core suites, restored with `git checkout -- src`, `git status` clean after every one.

| Mutation | Result |
|---|---|
| W1 claims from every prepared finding | Survived, 2004 passed (reachable, V2-22-03) |
| W4 claims before the tail merge | Caught, 2 failed |
| T1 agreement only with the claim itself | Caught, 8 failed |
| T2 confirmed at one database | Caught, 5 failed |
| T3 max instead of min | Caught, 1 failed |
| T4 same-field check dropped | Survived, 2004 passed (V2-22-02) |
| G1 any to all | Caught, 3 failed |
| G2 last row per page | Caught, 2 failed |
| G3 first row per page | Caught, 1 failed |
| G4 `or [None]` dropped | Survived, 2004 passed (V2-22-02) |
| G5 gate keyed by exact link | Caught, 1 failed |
| G6 compare against the cited finding only | Caught, 5 failed |

## Gates, exact CI commands, clean checkout of db04a2e2

| Gate | Result |
|---|---|
| gate02 `isort --check-only --diff src tests services tracker alembic .claude .github` | Pass, "Skipped 2 files", exit 0 |
| gate03 `ruff check` | Pass, "All checks passed!" (a clean checkout has no `raw/adversary/` probes; I did not run anything in asu-card22) |
| gate04 `pytest -m "not integration" -q -rs --junitxml=unit-results.xml`, PYTHONPATH=src | Pass, "7078 passed, 143 skipped, 24 deselected, 1 xfailed" in 533.85s; gate04b "every skip sanctioned" |
| Frontend gate08 `npm run build && npm test` plus the licence check | Pass, "Test Files 59 passed (59), Tests 513 passed (513)", licence check ok |
| `CI=1 npx playwright test e2e/card22-name-every-total.spec.ts`, ports 5273 and 8931 free first | Pass, "4 passed (26.0s)" |
| `check_public_leaks.py --base origin/develop` | PASS, 0 findings over 16 commits, merge base d8179c4e |

## Verdict

PASS on the card's goal, with no regression against develop.

- The confirmed line, on 26 inputs against develop: never names more databases than the cited records state, never more than develop, and genuine two-, three- and four-database agreement still confirms.
- The restatement gate drops V-22-02's sentences in both orders, keeps relational and abstract sentences, and on two inputs drops a restatement develop kept.
- Every gate passes on a clean checkout.

Stop condition, said plainly: three of my four findings sit inside fixes made in this last round. V2-22-01 is in V-22-04's test data. V2-22-02 G4 is in the new `or [None]` line. V2-22-03 is the new spy test's docstring and the builder's W1 reachability claim. All three are test-level gaps. None changes what a reader sees on this branch. V2-22-04 is fix-round code, unsure, and the same on develop. Under the review-loop rule, findings inside a phase fix go to the owner rather than into another round. None is a regression against develop or a defect a reader would see, so in my judgement none blocks the merge. They are better as a follow-up card.

What I verified with my own probes: the confirmed line (`p_trust.py`, `p_g4t4.py`, `p_curie.py`), the restatement gate (`p_gate.py`), the BRCA1 fixture end to end through trust line, gate, rail count and command line (`p_brca1.py`), the Sources list and saved screen (my vitest probe), 12 mutations, W1 reachability by instrumenting the whole suite, the ClinVar and dbSNP identities over public E-utilities, and every gate.

What I only read: the MCP and GraphQL surfaces, the history rail after a real browser reload, and the full write path on a real BRCA1 run. I did not drive `write_node` with the BRCA1 fixture. The full-answer check is component level.
