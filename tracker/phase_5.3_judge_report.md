# Build phase 5.3 judge report

Round: judge (independent, fresh context, no Write/Edit tools).
Branch: phase/5.3-golden-dataset-schema-v2
Started: 2026-08-31

Findings numbered F-5.3-J-NN to avoid collision with the lead's F-5.3-01..04.
Nothing here is closed or triaged by this round. The lead verifies and closes.

## Verified by my own probes (before any finding)

Counts confirmed, both files run with `venv/bin/python -m pytest`:

- `tests/system_03_search_agent/eval/test_phase_5_3_premise.py` -> `21 passed in 2.38s`. All 21 arms EXECUTED; the two live P5 arms did not skip on this run, so the graph was genuinely reached.
- `tests/system_03_search_agent/eval/test_phase_5_3_mutation.py` -> `14 passed in 12.37s`, i.e. M1..M12 applied plus `test_harness_rejects_a_mutation_that_does_not_apply` and `test_control_the_gate_is_green_before_any_mutation`. Matches the claimed "12 applied mutations plus 2 guards".

No-regression claim (goal-contract verify item 4) verified INDEPENDENTLY of the phase's own arm, by diffing `git show develop:eval/golden/golden_dataset.json` against the working-tree `eval/golden/golden_dataset.json` field by field in my own script:

```
must_reach            50 rows  example: ('G-001', '<absent>', [])
provenance.read_on    50 rows  example: ('G-001', '2026-08-30', '2026-08-31')
total rows: 50
```

Nothing else changed on any row. The claim is TRUE.

The baseline file is genuinely the v1 payload, not a re-derived copy. `git show develop:eval/golden/golden_dataset.json` is byte-equal (after canonical JSON normalisation) to `eval/golden/golden_dataset_v1_baseline.json`. So the P4 no-regression arm is not circular.

## Findings

### F-5.3-J-01: the `live_only` circularity control is a one-string denylist, not the allowlist its own docstring claims parity with
- Severity: major (LATENT today, not reachable in the shipped dataset: zero rows carry `live_only`)
- What: `_validate_live_only` refuses `observed_from` by `any(token in observed_from.lower() for token in _REFUSED_AUTHORED_FROM)`, and `_REFUSED_AUTHORED_FROM = frozenset({"agent_output"})` (`src/system_03_search_agent/eval/dataset.py:56`). It is a substring denylist containing exactly ONE literal. The sibling control it says it mirrors, `provenance.authored_from`, is an ALLOWLIST (`if authored_from not in _ALLOWED_AUTHORED_FROM: raise`, line 284). Any phrasing other than the literal `agent_output` passes. The field is free text, so every realistic circular phrasing passes.
- Reproduction: my own probe, loading a copy of the shipped dataset with one row given a `live_only` block, through the real `load_golden_dataset`:

```
refused  | live_only observed_from='agent_output'          -> names the agent under test
ACCEPTED | live_only observed_from='system 3 output'
ACCEPTED | live_only observed_from='the model under test'
```

  Exact command: a temp copy of `eval/golden/golden_dataset.json` with `queries[3]["live_only"] = {"fact":"x","value":"y","observed_from":"the model under test","observed_on":"2026-08-31"}`, passed to `load_golden_dataset(path)`. Output: no exception, dataset loaded.
- Why it matters: this is the ONLY control standing between `live_only` and the exact circularity that parked build phase 5.2 (the phase file, line 67, names that as the root defect it is defending against). The premise arm `test_p3_live_only_may_not_be_authored_from_agent_output` asserts the single literal `agent_output`, so the arm passes, mutation M5 turns it red, and the gate reads as green on a general property it does not hold. This is the safety-by-proxy shape: the arm proves "the one spelling in the denylist is refused", the docstring and `tracker/phase_5.3.md` T-5.3-02 claim "`observed_from` refused when it names the agent under test".
- Not reachable today only because no shipped row uses the field. The first SME-authored `live_only` row is where it bites.
- NOT FIXED

### F-5.3-J-02: `live_only.observed_on` accepts any non-empty string, so the field the shelf-life argument rests on need not be a date
- Severity: minor (unsure whether the lead considers this in scope)
- What: `_validate_live_only` checks only `isinstance(value, str) and value.strip()` for all four keys. `observed_on` is accepted as arbitrary text.
- Reproduction: same probe harness. `queries[3]["live_only"] = {"fact":"x","value":"y","observed_from":"E-utilities","observed_on":"whenever"}` -> `ACCEPTED | live_only observed_on is nonsense text`. No exception from `load_golden_dataset`.
- Why it matters: the coverage statement (`tracker/phase_5.3.md` line 125) and the loader docstring both argue `live_only` "ages as the graph snapshot moves" and that its shelf life is bounded. Nothing can compute an age from `"whenever"`. The field reads as a date and is not one.
- NOT FIXED

### F-5.3-J-03: `assert_absent_from_graph` has NO caller on the build path; the phase's central control is exercised only by the gate
- Severity: critical
- What: `eval/golden/build_dataset.py` defines `assert_absent_from_graph` and never calls it. `build_row` and `build_row_fields` copy `spec["live_only"]` straight into the row (`build_dataset.py:561-563`) with no absence check. The only two callers in the repository are the two premise arms `test_p5_a_graph_satisfiable_fact_is_refused_by_the_builder` and `test_p5_control_a_fact_the_graph_lacks_is_accepted`. The control is TESTED AND UNWIRED.
- INDEPENDENTLY ESTABLISHED. I reached this before being told the adversary round had filed F-5.3-A-01 on the same defect. Two rounds with separate contexts converged on it. I CONFIRM the adversary's finding; I do not merely concur.
- Reproduction, my own probe, run with the graph live:

```
$ venv/bin/python  # spec carrying a deliberately graph-satisfiable live_only fact
graph reachable: True
checker refuses directly: live_only 'gene_symbol': the graph already holds 'BRCA1' on NCBIGene:672, so this row does
BUILDER OUTPUT live_only: {'fact': 'gene_symbol', 'value': 'BRCA1',
                           'observed_from': 'E-utilities esummary db=gene id=672',
                           'observed_on': '2026-08-31'}
```

  The exact same fact, `gene_symbol=BRCA1` on `NCBIGene:672`, is REFUSED when `assert_absent_from_graph` is called directly and is ACCEPTED into a built row when it goes through `build_row_fields`. Grep evidence: `grep -rn "assert_absent_from_graph" eval/golden/build_dataset.py` returns exactly one line, `236:def assert_absent_from_graph(...)`, the definition. No call site.
- Why it matters: the goal contract's done-when is "two independent mechanisms, with the second protected against silently becoming false". That protection is the absence check, and it is not on the path that produces the dataset. `tracker/phase_5.3.md` T-5.3-03 is marked "done: `assert_absent_from_graph` over raw `urllib`, proven live against BRCA1's real property set, with a paired control". Proven as a FUNCTION, never wired as a CONTROL. Verify item 2 of the contract asks for "a mutation that plants a graph-satisfiable fact and requires THE BUILD to fail"; mutations M8 and M9 mutate the function's body and are noticed by arms that call the function directly, so no arm and no mutation ever runs a `live_only` spec through the build path.
- What else would produce this same green: exactly this. Every P5 green, and both M8/M9 reds, are produced identically by a correct wired builder and by a builder that never calls the checker. That is the question `.claude/rules/self-eval-loop.md` says to ask of any number, and the gate does not survive it.
- NOT FIXED

### F-5.3-J-04: the coverage statement does not merely omit F-5.3-J-03, it asserts the opposite in three places
- Severity: critical (this is the concealment, and it is the answer to "is there a fourth gap the coverage statement does not name")
- What: my brief asked whether the coverage statement is true and complete. It is NOT TRUE. Three separate sentences positively assert that the builder performs the absence check, and the builder never calls it.
  - `tracker/phase_5.3.md:125`: "The `live_only` shelf life is bounded by T-5.3-03 at BUILD time only. A System 1/2 re-ingest between two builder runs makes a shipped row graph-satisfiable, and nothing re-checks it until the builder runs again." The stated gap is the WINDOW BETWEEN builder runs. The actual gap is that a builder run checks nothing at all.
  - `tests/.../test_phase_5_3_premise.py:65-69`: "THE `live_only` SHELF LIFE IS CHECKED AT BUILD TIME ONLY. P5 proves the builder refuses a fact the graph already holds, at the moment it runs." P5 proves the FUNCTION refuses. It does not touch the builder.
  - `tracker/phase_5.3.md:113`, T-5.3-03 status: "done: `assert_absent_from_graph` over raw `urllib`, proven live against BRCA1's real property set".
- Reproduction: the grep and the probe under F-5.3-J-03. `grep -rn "assert_absent_from_graph" eval/golden/build_dataset.py` -> one line, the `def`. `build_row_fields` with a graph-satisfiable `live_only` returns the row unchanged.
- Why it matters: `goal-contracts` says a verify surface must state its own coverage so a gap is arguable. Here the coverage statement makes the gap UNARGUABLE by describing a narrower one, and it is the exact build phase 4.15 shape recorded in CLAUDE.md: "FOUR defects were a CONFIDENT SENTENCE DESCRIBING A CHECK THAT WAS NOT THERE." A reader auditing this phase for holes reads line 125, sees the shelf-life window named honestly, and stops looking. I nearly did.
- NOT FIXED

### F-5.3-J-05: two of the phase's own four findings are fixes to a code path with no production caller, and neither fix round noticed
- Severity: major (process and decomposition, not a line of code; filed because it is the transferable result of this round)
- What: F-5.3-02 (the graph error message blamed the credential for every HTTP status) and F-5.3-04 (the two live arms skipped because `_graph_request` read only `os.environ`) are both fixes INSIDE `_graph_request`. `_graph_request` is called only by `graph_is_reachable` and `assert_absent_from_graph`, and neither of those has a caller outside `tests/system_03_search_agent/eval/test_phase_5_3_premise.py`. The whole ~130-line "Layer 1 absence check" section of `eval/golden/build_dataset.py` (lines 107 to 268) is reached only from the test file.
- Reproduction: `grep -rn "_graph_request\|graph_is_reachable\|assert_absent_from_graph" eval/golden/build_dataset.py` shows definitions plus two internal calls and no other call site; the same grep across `eval/` and `src/` finds no further caller. The only external callers are the two P5 arms.
- Why it matters: THIS IS A FINDING INSIDE THIS PHASE'S OWN FIXES, which per my brief and `.claude/rules/self-eval-loop.md` fires the review loop's stop condition and escalates to the product owner rather than continuing into another round. It is also build phase 5.0's recorded lesson repeating exactly: "four rounds hardened the LOCAL audit sink's error field while the identical string shipped OFF-BOX with no control at all... because every round was scoped from the file the previous round had been editing rather than from where credentials actually flow." Here two rounds hardened the DIAGNOSTICS of a control that is not on the path, because both were scoped from the arm that was failing rather than from what produces the dataset.
- NOT FIXED

### F-5.3-J-06: one gate arm has no mutation case, and it is the arm that satisfies goal-contract verify item 4
- Severity: minor (established by reading, as my brief requires; the arm is NOT vacuous, which I proved separately)
- What: the goal contract's verify item 1 requires "every arm paired with a named mutation APPLIED by a harness in the same edit as the arm". I mapped all 18 arm functions against the `MUTATIONS` tuple. Four arms are named by no mutation. Three are deliberate controls whose job is to stay green (`test_p2_control_the_baseline_row_validates`, `test_p3_control_a_complete_live_only_block_validates`, `test_p6_control_the_scan_actually_reads_the_builder`) and need none. The fourth is not a control: `test_p4_no_shipped_row_changed_meaning_under_the_schema_bump`, the arm that discharges verify item 4, the no-regression proof.
- Reproduction: parsed both files and printed the arm-to-mutation map. Result, abridged:

```
NONE test_p2_control_the_baseline_row_validates                    []   <- control, fine
NONE test_p3_control_a_complete_live_only_block_validates          []   <- control, fine
NONE test_p4_no_shipped_row_changed_meaning_under_the_schema_bump  []   <- NOT a control
NONE test_p6_control_the_scan_actually_reads_the_builder           []   <- control, fine
```

  Root cause is structural: the harness only mutates `LOADER` and `BUILDER`, and this arm's subject is two JSON data files, which the harness has no mechanism to mutate.
- I then tested the arm for vacuity myself rather than assuming, transcribing its body verbatim into a probe and perturbing in-memory copies:

```
NOT CAUGHT  | control: unmutated
caught      | row 0 must_cite replaced
caught      | shipped file never rebuilt (read_on stays at baseline)  (only 0 of 50 re-verified)
caught      | row 3 question replaced
caught      | row 5 expected_outcome flipped
caught      | row 7 provenance.signed_off_by rewritten
caught(err) | row 9 loses must_resolve entirely
```

  Six of six meaning-changing perturbations caught, including the hollow-measurement case where the rebuild never ran. THE ARM IS SOUND. The finding is that its soundness rests on my probe rather than on the harness, and the contract said the harness.
- NOT FIXED

### F-5.3-J-07: `must_reach` accepts `cypher_query`, the Layer 1 tool, so the mechanism's vocabulary admits a value that states the opposite of the done-when
- Severity: minor (unsure; this may be a deliberate design choice, but it is undisclosed either way)
- What: the goal contract's done-when is "a golden row can state, and the loader can enforce, that answering it requires a live Layer 2 or Layer 3 call". `ALLOWED_MUST_REACH` is the full seven-tool roster including `cypher_query`, which is the Layer 1 graph tool. A row saying `must_reach: ["cypher_query"]` requires no live call at all, and the loader accepts it. `test_p2_every_registered_tool_is_accepted_in_must_reach` asserts this acceptance explicitly, so the gate pins the behaviour rather than flagging it.
- Reproduction, through the real validator:

```
roster: ['clinicaltrials_search', 'cypher_query', 'litvar2_lookup', 'ncbi_dbsnp',
         'ncbi_efetch', 'pathogen_detection', 'pubtator_annotate']
ACCEPTED must_reach = ['cypher_query']
ACCEPTED must_reach = ['cypher_query', 'cypher_query']
```

  Duplicates are also accepted, which is cosmetic but is the same absence of normalisation.
- Why it matters: `must_reach` is one of the phase's two deliverable mechanisms, and by itself it cannot express the phase's own done-when. Nothing in the coverage statement says so. If it is deliberate (`must_reach` being a generic path constraint, with `live_only` carrying the live-reach requirement), that sentence belongs in the coverage statement, because the commit message and the phase file both frame `must_reach` as the layer-reach mechanism.
- NOT FIXED

### F-5.3-J-08: the P6 independence scan matches only literal `import`/`from` lines, so every dynamic import form passes it
- Severity: minor, latent
- What: `test_p6_the_dataset_builder_does_not_import_the_agent_it_grades` tests `stripped.startswith(("import ", "from "))`. My brief asked me to verify this arm can actually fail; it can, mutation M10 turns it red and I confirmed M10 passes. But its REACH is narrow.
- Reproduction, the scan body transcribed verbatim and run over synthetic lines:

```
CAUGHT     | plain import (what M10 injects)
CAUGHT     | import inside a function
NOT CAUGHT | importlib.import_module("system_03_search_agent.eval.dataset")
NOT CAUGHT | __import__("system_03_search_agent.eval.dataset", fromlist=["x"])
NOT CAUGHT | exec("import system_03_search_agent.tools.cypher_query")
NOT CAUGHT | subprocess.run([sys.executable,"-c","import system_03_search_agent.tools.cypher_query as c; c.run()"])
```

  M10 injects the one shape the scan catches, so the mutation confirms the arm is non-vacuous and says nothing about its reach. The non-recursive `glob("*.py")` is NOT currently a gap: `glob` and `rglob` return the same three files today, `eval/golden/` having no source subdirectory.
- Why it matters: the arm is described in the phase file as making the independence rule "structural, so it cannot depend on anyone remembering". It is structural against the accidental case and not against the determined one. That is fine, and it should be the arm's stated coverage rather than an inference. Low severity because the realistic failure here is an ordinary import written by someone who forgot the rule, which the arm does catch.
- NOT FIXED

### F-5.3-J-09: the false build-time claim appears a FOURTH time, on tracker/BOARD.md, the most-read surface
- Severity: critical (same defect as F-5.3-J-04; filed separately because this copy is on the board and will outlive the phase file)
- What: `tracker/BOARD.md:99`, open flag F-5.3-C, states: "`assert_absent_from_graph` asks the live graph whether it already holds a `live_only` value and refuses the row if it does, which is what makes the field mean anything rather than being the author's assertion. It runs when the BUILDER runs."
- Reproduction: it does not run when the builder runs. `grep -rn "assert_absent_from_graph" eval/golden/build_dataset.py` returns only the definition at line 236. See F-5.3-J-03's probe: the identical `gene_symbol=BRCA1` fact is refused by the function and accepted by `build_row_fields`.
- Why it matters: the claim is now in four places (the phase file's coverage bullet, the phase file's T-5.3-03 status, the gate docstring, and this board flag), each written independently, none true. CLAUDE.md records this exact escalation from build phase 4.15: "the mutation harness claimed to cover every arm TWICE, the second time INSIDE THE FIX for the first... and the board made the same claim a third time, written while the second was being fixed." The recorded durable fix there was DELETION of the completeness claim rather than a better sentence.
- The flag also frames the residual risk as the re-ingest window and names an owner for it ("whoever next owns the re-ingest handshake"). That owner would inherit a gap that is not the one described.
- NOT FIXED

### F-5.3-J-10: the new `_SUPPORTED_VERSIONS` refusal has no arm anywhere in the suite
- Severity: minor
- What: `load_golden_dataset` gained a refusal for a schema version outside `{1, 2}` (`dataset.py:517-523`). Nothing tests it. `grep -rn "is not supported\|_SUPPORTED_VERSIONS" tests/` returns nothing.
- Reproduction: `grep` as above, empty. I confirmed the control itself works by my own probe (`version: 3` -> `schema version 3 is not supported, expected one of [1, 2]`), so this is an untested control rather than a broken one.
- Fair note in the other direction, established rather than assumed: the "loader accepts BOTH v1 and v2" half of T-5.3-05 IS covered, though not by this phase's gate. Build phase 5.1's premise gate writes `{"version": 1, ...}` files and loads them through `load_golden_dataset` at `test_phase_5_1_premise.py:115,130,147,165,184`, so narrowing `_SUPPORTED_VERSIONS` to `{2}` would go red there. I verified those arms still pass: `tests/system_03_search_agent/eval/` runs `144 passed, 1 skipped`.
- NOT FIXED

## Wiring sweep: is any OTHER control in this phase tested-but-unwired?

I was asked not to concur with the adversary but to check the class myself. I enumerated every control this phase introduces and EXECUTED each one through its production entry point rather than reading for a call site.

| Control | Defined in | On a production path? | How I established it |
|---|---|---|---|
| `ALLOWED_MUST_REACH` roster refusal | `dataset.py` | YES | `load_golden_dataset` on a temp copy with `must_reach: ["blastn"]` -> refused |
| `must_reach` type check | `dataset.py` | YES | same route, `must_reach: {"a":1}` -> "got a bare dict" |
| `_validate_live_only` shape | `dataset.py` | YES | same route, list -> "must be an object"; int `value` -> "missing a non-empty 'value'" |
| `live_only` circularity denylist | `dataset.py` | YES, but one literal wide (F-5.3-J-01) | same route |
| `_SUPPORTED_VERSIONS` | `dataset.py` | YES | same route, `version: 3` -> refused; `version: 1` -> accepted |
| `build_row_fields` must_reach carry-through | `build_dataset.py` | YES, `build_row` calls it | all 50 shipped rows carry `must_reach` |
| `_SCHEMA_VERSION` in `main()` | `build_dataset.py` | YES | shipped file is `version: 2` |
| `assert_absent_from_graph` | `build_dataset.py` | NO | F-5.3-J-03 |
| `_graph_request` | `build_dataset.py` | NO, reachable only via the two graph helpers | F-5.3-J-05 |
| `graph_is_reachable` | `build_dataset.py` | NO, gate-only and stated as such in its docstring | not a defect on its own |

Result: exactly ONE tested-but-unwired control, `assert_absent_from_graph`, plus the two functions that exist only to serve it. Every other control in the phase is genuinely on the load or build path and I proved each by executing it. I therefore CONFIRM the adversary's F-5.3-A-01 rather than deferring to it, and I found no second instance of the class.

## Verdict

FAIL.

What drove it:

- F-5.3-J-03 (critical): `assert_absent_from_graph` is never called by the builder. The phase's done-when requires two mechanisms "with the second protected against silently becoming false". That protection is not on the production path. Independently reached here and separately filed by the adversary as F-5.3-A-01.
- F-5.3-J-04 and F-5.3-J-09 (critical): the coverage statement does not disclose that gap, it asserts the opposite, in four independently written places including `tracker/BOARD.md`. My brief asked whether there is a fourth gap the coverage statement does not name. There is, and it is the phase's central control.
- F-5.3-J-05 (major): TWO OF THE PHASE'S OWN FOUR FINDINGS, F-5.3-02 and F-5.3-04, ARE FIXES INSIDE `_graph_request`, A FUNCTION WITH NO PRODUCTION CALLER. This finding sits inside fixes made during this phase, which fires the review loop's Rule 4 stop condition. Per my brief and `.claude/rules/self-eval-loop.md` this escalates to the product owner rather than continuing into another round.

Recorded, not blocking: F-5.3-J-01 (latent major, the one-literal circularity denylist, unreachable today because no row uses `live_only`), F-5.3-J-02, F-5.3-J-06, F-5.3-J-07, F-5.3-J-08, F-5.3-J-10.

## What I verified with my own probes versus what I only read

Verified by running something I wrote, or by executing the subject directly:

- The 21 premise arms and the 12 mutations plus 2 guards. All 21 arms EXECUTED; the two live P5 arms did not skip.
- The no-regression claim, diffed field by field from develop's `golden_dataset.json` against the working tree, in my own script and not through the phase's arm. Only `must_reach` added (empty on all 50) and `provenance.read_on` moved 2026-08-30 to 2026-08-31. TRUE.
- That `golden_dataset_v1_baseline.json` really is develop's v1 payload, so the phase's own no-regression arm is not circular.
- That `test_p4_no_shipped_row_changed_meaning_under_the_schema_bump` is not vacuous, by transcribing its body and perturbing in-memory copies: 6 of 6 meaning-changing perturbations caught, including the case where the rebuild never ran.
- Every loader control, by loading temp copies of the shipped dataset through the real `load_golden_dataset`.
- F-5.3-J-03, by invoking `assert_absent_from_graph` and `build_row_fields` with the SAME graph-satisfiable fact and observing one refuse and the other accept, against the live graph.
- The P6 scan's reach, by transcribing its body and running it over six import forms.
- Gate 3, ruff over the whole repository with no path argument: all checks passed. Gate 2, isort check-only on the four changed Python files: clean. Doc drift: 10 facts computed, 0 stale, 0 structural. The eval subtree: 144 passed, 1 skipped.

Read only, NOT independently executed, and therefore weaker evidence:

- That the 50 rows were rebuilt against live NCBI in 10.1s across 43 calls. I did not re-run the builder. Corroborating but not conclusive: `verification_log.json` moved `elapsed_seconds` 6.4 to 10.1 while `live_calls` stayed 43, which editing `read_on` by hand would not produce.
- The full-suite figure of 4515 passed, 171 skipped, in the commit message. I ran only the eval subtree.
- The claim that the replay harness is parked, so nothing grades `must_reach`. I did confirm by grep that `must_reach` and `live_only` appear nowhere outside `dataset.py` and this phase's own two test files, and that the only `as_dict()` consumer is `replay.py:206`.
- The frontend and Playwright counts. Not touched by this phase and not run.

Nothing in this report is closed, triaged or reprioritised. The lead verifies and closes.
