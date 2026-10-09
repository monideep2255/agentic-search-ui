# Card 53 judge round, 2026-09-29

Judge, one round, branch `fix/card53-stale-facts`. Findings appended as established. Local only, no request to deployed apps.

## Findings

### F-53-J01: catalogue.py still says its timeouts are "copied literally" from the rule table, which 0eb3ca83 made false
- Severity: should-fix (inside this card's newest fix)
- Where: `src/system_03_search_agent/tools/catalogue.py:41-44` (module docstring: "Every action's `timeout_s` ... are read from `.claude/rules/tool-call-budgets.md`'s per-tool timeout table, copied here as literal values (that rule's table is the source of truth; this module restates it, it does not compute it)") and `catalogue.py:119-122` ("Per-tool timeout and rate-limit pool, copied literally from `.claude/rules/tool-call-budgets.md`'s table"). Test name `tests/system_03_search_agent/tools/test_catalogue.py` `test_timeouts_match_tool_call_budgets_rule` now asserts 120.0.
- Evidence: `.claude/rules/tool-call-budgets.md:26` reads "pathogen_detection | 60 seconds or more". `catalogue.py:141` now reads `120.0`. The 120 s itself is true: `pathogen_detection.py:284` `_TOTAL_BUDGET_S: Final[float] = 120.0`, applied to every action at `pathogen_detection.py:1374`, and `core/graph.py:4261` gives the Act ceiling 150.0 "the tool's own 120-second FTP budget plus snapshot resolution". The catalogue value is descriptive only: nothing outside `catalogue.py` reads `timeout_s` from it (grep of `src/` and `services/`), so no runtime behaviour changed.
- What a reader notices: the card fixed one stale fact and, in the same file, left two sentences that now state a false provenance (the rule is the source of truth, copied literally). The rule's own table still says 60, so a reader of the rule and a reader of the catalogue get two numbers, and the file says they are the same. Either the rule row gets the 120 s (a `.claude/` change, own branch) or the two comments say the pathogen value comes from the code, not the rule.
- NOT FIXED
### F-53-J02: the new layer 3 sentences say no decision gates layer 3; a model decision removes ClinicalTrials.gov from a disease question
- Severity: blocking (a new false claim on a shipped page, written by this card; the card's acceptance is that every page fact matches the code)
- Where: user-facing `frontend/src/components/screens/ArchitectureScreen.tsx` Layer 3 stop ("Plan adds them in code rather than on request: PubTator3 and ClinicalTrials.gov for every question that names a gene or a disease"), `frontend/src/components/screens/InfoScreens.tsx` JOURNEY_LAYERS n=3 ("added in code rather than on request whenever a question names a gene, a disease or an rs variant"), `frontend/src/lib/architectureFacts.ts` LAYERS[2].summary ("Added in code rather than on request"); code comments in the same three files: "No decision and no request gates them".
- Evidence (code): `core/graph.py:6278-6288`: when no gene resolved, Plan reads `_literature_choice` (the `plan.literature` classifier, a model decision) and on `wants_literature` sets `topic_term`, which sends the run down the topic branch (`graph.py:6387-6405`) that never calls `_build_layer_tool_calls` (only reached in the `else` branch, `graph.py:6501`). The repository's own test says so: `tests/system_03_search_agent/core/test_topic_search.py:1052` "the classifier not the words decides a disease question's path".
- Evidence (my probe): a scratch pytest in the scratchpad reusing that test module's stubs, question "Any trials for GERD?", disease resolved to `MedGen:C5563728`, only the literature decision varied:
  `PROBE not_literature planned tools: ['cypher_query', 'pubtator_annotate', 'clinicaltrials_search', 'ncbi_efetch', 'ncbi_efetch', 'ncbi_efetch', 'pubtator_annotate', 'ncbi_efetch']`
  `PROBE wants_literature planned tools: ['ncbi_efetch', 'ncbi_efetch', 'pubtator_annotate']`
  Same question, same disease, and ClinicalTrials.gov is gone when the model decides the reader wants papers. So both "no decision gates them" and "every question that names a disease" are false. The same branch also drops LitVar2 for a no-gene question naming an rs id when the decision says papers.
- What a reader notices: the Architecture and About pages promise trial evidence for every question naming a disease; a reader who asks "papers on GERD" or whose question the classifier reads as a literature request gets no trials leg, contrary to the page. Also "each rs variant id" is capped at the first two (`graph.py` `for rsid in rsids[:2]`); the comments say two, the page text says "each".
- NOT FIXED
### F-53-J03: the layer 2 list reader passes a negated manifest sentence that says Pathogen Detection is NOT in layer 2 (the PR122-01 shape)
- Severity: should-fix (a check this card relies on, `layers.l2_apis`, cannot see a negation)
- Where: `.claude/skills/verify/scripts/facts_registry.py`, fact `layers.l2_apis`, place `src/system_03_search_agent/export/manifest.py:72` (the KGX manifest, shipped to users inside every export).
- Reproduction: in a scratch copy made by `git archive HEAD` (never the tracked file), I replaced `"Layer 2 (live NCBI APIs: E-utilities, Datasets, PubChem, dbSNP and " "Pathogen Detection)` with `"Layer 2 (live NCBI APIs: E-utilities, Datasets, PubChem and dbSNP, not " "Pathogen Detection)` and ran `check_facts.py --root <copy> --reference <data-engineering> --all`. Output:
  `PASS | layers.l2_apis | code copy | says "Layer 2 (live NCBI APIs: E-utilities, Datasets, PubChem and dbSNP, not " "Pathogen Detection)" | true: Datasets, E-utilities, Pathogen Detection, PubChem, dbSNP | src/system_03_search_agent/export/manifest.py:72`
  Summary `places: PASS 202, FAIL 0, GAP 0, ERROR 0 | PASS`, exit 0. The reader collects API names present in the sentence and ignores the "not".
- Scope of my breaking run: 15 mutations across 9 files (InfoScreens.tsx, architectureFacts.ts, ArchitectureScreen.tsx, CLAUDE.md, AGENTS.md, README.md, Architecture_diagram.md, System_3_deep_dive.md, catalogue.py, manifest.py). 14 of 15 made the checker exit non-zero (FAIL exit 1, or ERROR "pattern finds nothing" exit 2 with NOT PASSED). Only this one stayed PASS.
- What a reader notices: a later edit that reintroduces a wrong layer 2 list with a negation in it ships green. Low likelihood of that exact wording, but it is exactly the defect class PR122-01 named.
- NOT FIXED
#### F-53-J03 addendum: the same hole in both list facts, in two more files
Second breaking run, 9 more mutations, same scratch-copy method. Two more stayed PASS, exit 0:
- `CLAUDE.md:46` changed to `Layer 3: Enrichment APIs (PubTator3, LitVar2, never ClinicalTrials.gov)`: `PASS | layers.l3_apis | document | says "Layer 3: Enrichment APIs (PubTator3, LitVar2, never ClinicalTrials.gov)" | true: ClinicalTrials.gov, LitVar2, PubTator3 | CLAUDE.md:46`.
- `README.md:120` changed to `... Datasets, dbSNP and Pathogen Detection (PubChem excluded)`: `PASS | layers.l2_apis | document | says "30+ databases reached ... Datasets, dbSNP and Pathogen Detection (PubChem excluded)" | true: Datasets, E-utilities, Pathogen Detection, PubChem, dbSNP | README.md:120`.
The other seven failed as they should (the false arms of the `l3_in_code` and `layer_one_read_first` alternations read as FAIL, dropping PubChem outright from CLAUDE.md FAIL, dropping `"citation"` from `events.ts` FAIL, a reworded deep-dive graph row ERROR). So both `layers.l2_apis` and `layers.l3_apis` readers are negation-blind in every place they read, while the dropped-name case is caught. Running total for my probes: 24 mutations, 11 files, 21 caught, 3 passed, all 3 in the two list readers.
#### F-53-J02 addendum: the checker certifies the false sentence
`check_facts.py --all` on the branch prints `PASS | layers.l3_in_code | Architecture | says "Plan adds them in code rather than on request" | true: yes (plan_node reaches _build_layer_tool_calls, which plans clinicaltrials_search, litvar2_lookup, pubtator_annotate)` and the same PASS for `InfoScreens.tsx:950` and `architectureFacts.ts:177`. The truth reader `layer3_planned_in_code` (`facts_registry.py:663-694`) proves reachability only, and its docstring says the conditions "(a gene or disease for PubTator3 and ClinicalTrials.gov, an rs id for LitVar2) was read from the function by hand on 2026-09-27". Reachability is also true of a call that a model decision gates, which is the case here (`graph.py:6278-6288`), so this fact cannot tell "in code rather than on request" from "when a classifier says so". The hand-read was the part that was wrong.
### F-53-J04: README still says the product caches in Redis; no code uses Redis
- Severity: note (a stale fact outside card 53's listed rows, in a file this card edited; the card's acceptance says "every fact")
- Where: `README.md:73` ("redis (for caching)" under Quick start prerequisites) and `README.md:155` ("| Caching | Redis |" in the stack table).
- Evidence: `grep -rln -i "import redis\|from redis\|REDIS_URL" --include="*.py" .` finds one file, `tests/system_03_search_agent/tools/test_release_environments_premise.py`, and nothing under `src/` or `services/`. `grep -rn -i redis src` hits only comments, two of which say the opposite: `synthesis/disease_names.py:70` "It is NOT the Section 4.3 Redis ..." and `synthesis/mesh_terms.py:115` "NOT the Section 4.3 Redis response cache". Redis is declared (`pyproject.toml:27`, `requirements.txt:15`, `env.example:94`) and provisioned on Railway (`README.md:275-277`), but the code does not read it.
- What a reader notices: a developer following Quick start installs and runs Redis for a cache that does not exist; a reader of the stack table believes Layer 2 and 3 responses are cached. The facts checker has no line for it.
- NOT FIXED
### F-53-J05: two always-loaded rules still state the layer lists card 53 corrected in CLAUDE.md
- Severity: note (outside the card's named files; same stale fact, and these load into every session and agent)
- Where: `.claude/rules/ai-security-standards.md:19` "Layer 2 tools call live NCBI APIs (EFetch, ELink, dbSNP), and Layer 3 tools call enrichment APIs (PubTator3, LitVar2, LitSense, ClinicalTrials.gov)"; `.claude/rules/tool-call-budgets.md:35` "each of the four enrichment APIs (PubTator3, LitVar2, LitSense, ClinicalTrials.gov v2)".
- Evidence: `tools/ncbi_transport.py:391-399` `_LAYER_BY_FAMILY` has eutils, datasets, pubchem, variation at layer 2 and pubtator, litvar2, clinicaltrials at layer 3; no LitSense anywhere in `src/` (only `guardrail/prefilter.py:448` as a vocabulary word and the manifest comment). The registry's own `NOT_CALLED = ("LitSense",)` (`facts_registry.py:164`) encodes that. CLAUDE.md:45-46 now says the corrected lists, so the always-loaded rules and CLAUDE.md now disagree.
- What a reader notices: an agent reading the security rule is told the tools call LitSense and omit Datasets, PubChem and Pathogen Detection from its untrusted-content surface. Changing `.claude/` needs its own branch and PR per git-workflow, so this may be deliberately deferred; I did not find it named in the builder's "Not done".
- NOT FIXED
### F-53-J06: "no layer is read before another" overstates Act; follow-up calls run in a second stage after the first finishes
- Severity: note (the user-facing sentences are near-true; the card's new code comment is not)
- Where: new comment `frontend/src/components/screens/InfoScreens.tsx` (the block beginning "All three layers go out together (card 53, 2026-09-27)"): "awaits them with `asyncio.gather`, so no layer is read before another". Related page text, guarded by `loop.layer_one_read_first`: `ArchitectureScreen.tsx:483-485` "the tools Plan chose go out together, so the graph query and any live layer 2 and 3 calls run in parallel rather than one after another".
- Evidence: `core/graph.py:7988-7990` runs only `first_stage` (calls that are not `_PlannedFollowUpCall`) through `_gather_planned_calls`; `graph.py:7992-8035` then builds `second_stage` from the first stage's outcomes and gathers it after. `_BREADTH_FOLLOW_UPS` (`graph.py:~4640`) makes `pubmed_search` feed `ncbi_efetch` abstracts (layer 2) and `pubtator_annotate` publications (layer 3), and `clinvar_search`, `omim_search`, `gds_search`, `medgen_search` feed summaries. So some layer 2 and layer 3 reads start only after the first stage, graph query included, has finished. The fact checker's truth reader reports "Act runs every planned call at once with asyncio.gather", which describes stage one only.
- What a reader notices: nothing wrong on the page for most questions; the comment misleads the next editor, and "rather than one after another" is not true of the follow-ups.
- NOT FIXED

## Security and privacy scan

A grep of `git diff origin/develop...HEAD` for a home-directory path prefix, an email domain and `password` returned nothing (exit 1). A second pass for IP addresses, the owner's name, `token`, `secret` and `api_key` found only `token` as an event name and `designTokens`. No local path, secret or private name in the diff.

## Verified by my own probes versus only read

Verified by running:
- J02: scratch pytest reusing `test_topic_search.py`'s stubs; planned tool lists for "Any trials for GERD?" under `not_literature` and `wants_literature` (pasted in J02).
- J03: 24 mutations across 11 files on a `git archive HEAD` scratch copy, checker run with `--root` and `--reference`; 21 caught, 3 passed (pasted in J03 and its addendum). The tracked files were never edited.
- Checker on the branch: `facts: 67 | stale 0 | not fully checked 0 | places: PASS 202, FAIL 0, GAP 0, ERROR 0 | PASS`; `--self-test`: `202 of 202 comparisons proven to pass and to fail; ... 0 failures`. The self-test passes while three negated sentences also pass, so "proven to fail" does not cover negation.
- `tests/system_03_search_agent/tools/test_catalogue.py`: 6 passed.

Verified by reading code at the cited lines (not executed): the 30 s graph budget (`graph_schema_constants.py:208`), Pathogen Detection 120 s (`pathogen_detection.py:284,1374`, `graph.py:4261`), the layer families (`ncbi_transport.py:391-399`), no LitSense caller in `src/`, the four MCP tools (`adapters/mcp/server.py`), the `s3 mcp` subcommand (`adapters/cli/main.py`, `mcp_bridge.py`), the guardrail second attempt (`graph.py:1835-1860`), the relevancy decision starting only off the allowlist (`graph.py:1753-1765`), the guard tier ask-back choices in Think (`_write_clarify_choices`, called from `_think`), the guard reader on graph article rows in Act (`graph.py:7735-7768`, `coordinator_worker._reader_pass`), the synth repair and guard sentence check in Write, gate04's `pytest -m "not integration"`, `frontend/package.json` `"node": ">=22"`.

Not verified: README's GitHub rulesets and releases claims (would need a GitHub API call; they landed on develop before this branch, not in this diff).

## Verdict

FIX FIRST. F-53-J02 is a new false claim written by this card (commit `aa7cc3a1`) on three shipped page surfaces, and the facts checker certifies it. That sits inside a fix made during this card, which is the review loop's stop condition. F-53-J01 also sits inside the newest fix, `0eb3ca83`.
