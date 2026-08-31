# Build phase 5.3 adversary report

Round: adversary (independent, unscripted). Started 2026-08-31.
Branch: phase/5.3-golden-dataset-schema-v2
Reviewer has Read/Bash only; no Write or Edit tool. Nothing is fixed or closed here.

Findings appended in the order established.

### F-5.3-A-01: `assert_absent_from_graph` is NEVER CALLED by the builder; the phase's central control is dead code reachable only from its own test

- Severity: critical
- What: T-5.3-03's acceptance reads "Builder refuses a `live_only` fact the GRAPH already contains". The builder does no such thing. `assert_absent_from_graph` is defined in `eval/golden/build_dataset.py:236` and is invoked from exactly two places, both inside this phase's own premise gate. The production build path, `main()` -> `build_row()` -> `build_row_fields()`, never calls it. `build_row_fields` copies the author's `live_only` block into the shipped row verbatim at lines 561-563:

```python
    live_only = spec.get("live_only")
    if live_only is not None:
        row["live_only"] = dict(live_only)
```

  No absence measurement exists anywhere on that path. A `live_only` fact ships into `golden_dataset.json` on the author's word alone, which is exactly the state the function's own docstring says it exists to prevent ("Without it the field is the author's assertion that the graph lacks a value, and build phase 4.15 found four separate defects that were exactly a confident sentence describing a check that was not there").
- Reproduction: exact command and exact output.

```
$ grep -rn "assert_absent_from_graph" ./eval ./tests ./src ./tracker ./docs
eval/golden/build_dataset.py:236:def assert_absent_from_graph(*, fact: str, value: str, curie: str) -> None:
tests/system_03_search_agent/eval/test_phase_5_3_premise.py:391:        assert_absent_from_graph,
tests/system_03_search_agent/eval/test_phase_5_3_premise.py:405:        assert_absent_from_graph(
tests/system_03_search_agent/eval/test_phase_5_3_premise.py:416:    from eval.golden.build_dataset import assert_absent_from_graph, graph_is_reachable
tests/system_03_search_agent/eval/test_phase_5_3_premise.py:421:    assert_absent_from_graph(
```

  One definition, one import and two calls: all four non-definition sites are in the test file. Zero in `build_row`, `build_row_fields` or `main`.
- Why it matters: this is the phase's stated premise. `live_only` is the one of the two new fields that "Cannot be satisfied by a graph-only agent" (goal contract), and the only thing making that true is the absence check. With the check off the build path, `live_only` is a comment. A future author adds a `live_only` fact the graph already holds, the builder emits it, the loader shape-validates it and passes, and the dataset ships a row a graph-only agent satisfies, which is precisely the failure this phase was opened to make impossible. The tracker (T-5.3-03 marked "done"), `tracker/BOARD.md` flag F-5.3-C, and the module docstring all assert a check that is not on the path.
- Note on the gate: the premise gate exercises the function directly, so it stays green while the product control is absent. That is the vacuity shape one level up: the test covers the function, nothing covers that the function is wired in.
- NOT FIXED
### F-5.3-A-02: a graph-satisfiable `live_only` row passes the REAL builder and the REAL loader end to end (executable proof of A-01, and the phase's premise defeated)

- Severity: critical
- What: this is attack 3 from the brief, and it succeeds. A `live_only` fact whose value the live Layer 1 graph provably holds right now is accepted by `build_row()` as `verified`, shipped into the row, and then accepted by `load_golden_dataset()`. The absence check refuses that exact value when called by hand, which proves the check itself works and that nothing calls it.
- Reproduction: script at `scratchpad/attack3.py`, run with `venv/bin/python`. It deep-copies the real `QUESTION_SPECS[0]` (G-001), attaches a `live_only` block, and calls the real `build_row` with a real `Fetcher` against live E-utilities, then the real loader.

  Input (the planted block):

```python
spec["live_only"] = {
    "fact": "the full name of BRCA1",
    "value": "BRCA1 DNA repair associated",
    "observed_from": "NCBI Gene record 672",
    "observed_on": "2026-08-31",
}
```

  The value was read out of the LIVE GRAPH first, so it is graph-satisfiable by construction:

```
$ venv/bin/python scratchpad/probe_graph.py
reachable: True
rows: [
  {
    "props": "{\"id\": \"NCBIGene:672\", \"name\": \"BRCA1 DNA repair associated\", ...}"
  }
]
```

  Exact output:

```
BUILDER VERDICT: verified
live_only shipped in the row: {"fact": "the full name of BRCA1", "value": "BRCA1 DNA repair associated", "observed_from": "NCBI Gene record 672", "observed_on": "2026-08-31"}
LOADER VERDICT: accepted, version 2 rows 1
loaded live_only: LiveOnlyFact(fact='the full name of BRCA1', value='BRCA1 DNA repair associated', observed_from='NCBI Gene record 672', observed_on='2026-08-31')
ABSENCE CHECK (never invoked by the builder) WOULD HAVE SAID: live_only 'the full name of BRCA1': the graph already holds 'BRCA1 DNA repair associated' on NCBIGene:672, so this row does NOT require a live call and would pass against a graph-only agent. Choose a value the snapshot predates.
```

- Why it matters: the brief states "Try to author a row that PASSES every check while still being satisfiable by an agent that only reads the graph. If you can, that is a critical: the phase's entire premise is that such a row is refused." Such a row is authored above in four lines and refused by nothing. The last line is the load-bearing one: the check is correct and would have fired, so this is purely a wiring defect, and the whole distance between "the phase works" and "the phase does nothing" is one uncalled function.
- NOT FIXED
### F-5.3-A-03: the `live_only.observed_from` circularity refusal is a free-text substring scan for ONE literal, defeated by a space

- Severity: major
- What: `_validate_live_only` (`src/system_03_search_agent/eval/dataset.py:360`) refuses circular authoring with
  `if any(token in observed_from.lower() for token in _REFUSED_AUTHORED_FROM)`, and `_REFUSED_AUTHORED_FROM` is `frozenset({"agent_output"})`. It therefore only refuses the exact token `agent_output`. Every plain-English way an author would actually write "I got this from the agent" passes, including the tracker's own phrase "the agent under test".
- Reproduction: `scratchpad/attack4.py`, run with `venv/bin/python`. Each candidate is a complete `live_only` block differing only in `observed_from`.

```
  refused   'agent_output'
  ACCEPTED  'agent output'
  ACCEPTED  'agent-output'
  ACCEPTED  'the agent under test'
  ACCEPTED  "System 3 search agent's answer"
  ACCEPTED  'our own agent'
  ACCEPTED  "the model's response"
  ACCEPTED  'replay() transcript'
  ACCEPTED  'the answer the agent produced on 2026-08-31'
  refused   'Agent_Output'
  ACCEPTED  'agent\xa0output'      <- U+00A0 non-breaking space
  refused   'AGENT_OUTPUT'
```

  A single space defeats it. So does a hyphen, and so does a non-breaking space, which is what a paste out of a rendered document produces.
- Why it matters: this is the same losing shape the brief names. Build phase 5.0 spent FOUR rounds on a credential scan defeated four times by inputs of the same family, and the reversal that worked was to stop scanning free text and BOUND what may enter. The sibling field twenty lines up already does exactly that: `provenance.authored_from` has a CLOSED vocabulary (`_ALLOWED_AUTHORED_FROM`), so anything not on the allowlist is refused, and the docstring on this very function says it is "The same refusal `authored_from` already makes on provenance, applied here." It is not the same refusal. `authored_from` is an allowlist; `observed_from` is a denylist of one token over unbounded prose. The confident sentence describes a control that is not the one in the body, which is build phase 4.15's four-defect pattern.
- Severity note: I am filing this major rather than critical because no shipped row uses `live_only` today, so it is latent rather than presently reachable. It becomes reachable the moment SME review lands and the first `live_only` row is authored, which is the stated purpose of the field.
- NOT FIXED
### F-5.3-A-04: the absence check is a casefolded substring over a JSON blob, so it matches KEY NAMES and punctuation; it is wrong in both directions

- Severity: major
- What: `assert_absent_from_graph` serialises the whole graph row with `json.dumps(rows[0], default=str).casefold()` and asks `value.casefold() in haystack`. The haystack therefore contains the JSON structural characters, the double-escaped inner payload, the `source_url`, and every PROPERTY KEY NAME. A value that is a key name, a URL fragment, or a short token is reported PRESENT even though the graph does not hold it as a fact. Conversely a value the graph genuinely holds but spelled with different whitespace or punctuation is reported ABSENT.
- Reproduction: `scratchpad/attack1.py`, run with `venv/bin/python` against the LIVE graph on `NCBIGene:672`. The haystack the check builds, printed verbatim:

```
{"props": "{\"id\": \"ncbigene:672\", \"name\": \"brca1 dna repair associated\", \"xrefs\": \"hgnc:1100|omim:113705|ensembl:ensg00000012048\", \"source\": \"ncbi gene\", \"agent_type\": \"\", \"source_url\": \"https://www.ncbi.nlm.nih.gov/gene/672\", \"knowledge_level\": \"\"}"}
```

  FALSE POSITIVES, the graph does not hold these as facts but the row is refused:

```
  PRESENT(refused)  value='source_url'        <- a KEY NAME
  PRESENT(refused)  value='knowledge_level'   <- a KEY NAME
  PRESENT(refused)  value='gene'              <- inside "ncbi gene" and inside the URL path
  PRESENT(refused)  value='nlm'               <- inside the source_url host
  PRESENT(refused)  value='id'                <- a KEY NAME, and inside "source_url"
  PRESENT(refused)  value='a'                 <- one character
  PRESENT(refused)  value='672'               <- inside the URL path
  PRESENT(refused)  value='1100'              <- inside "hgnc:1100"
  PRESENT(refused)  value='https'             <- the URL scheme
```

  FALSE NEGATIVES, the graph DOES hold the fact but the row is allowed:

```
  ABSENT(allowed)  value='BRCA1  DNA repair associated'   <- one extra space
  ABSENT(allowed)  value='BRCA1-DNA repair associated'    <- a hyphen
  ABSENT(allowed)  value='OMIM 113705'                    <- space instead of colon; graph holds omim:113705
  ABSENT(allowed)  value='OMIM:113705|HGNC:1100'          <- same two xrefs, reordered
  ABSENT(allowed)  value='  BRCA1 DNA repair associated  '<- untrimmed, as pasted from a document
  ABSENT(allowed)  value='BRCA1 DNA repair associated.'   <- a trailing period
```

- Why it matters: the brief asks whether this is build phase 5.2's substring anchor defect wearing new clothes, where "gene" matched inside "generate" and the check was ANTI-CORRELATED with correctness. It is the same defect and `gene` is literally the reproducing token again: `probe(value="gene")` is refused on BRCA1 because the substring sits inside `"ncbi gene"` and inside the URL path, not because the graph holds the fact "gene". The check has no notion of a property VALUE versus a property KEY versus URL text, and no notion of a token boundary. Two independent consequences: a legitimate live-only fact gets refused for a spurious reason (blocking correct authoring, and the blocked-stop then says "the row does not get the field", so real coverage is lost), and a graph-satisfiable fact gets admitted whenever it is spelled slightly differently from the graph's own rendering (the failure the check exists to prevent). The whitespace and trailing-period cases are not exotic; they are what a value pasted out of a rendered NCBI page looks like.
- Note: `value.strip()` is checked for emptiness by the loader but the value is never NORMALISED before the comparison, so the untrimmed case above survives the loader too.
- NOT FIXED
### F-5.3-A-05: the absence check inspects ONE node's own properties, so any fact on a neighbour or an edge is certified "absent" while the graph answers it in one hop

- Severity: major
- What: `assert_absent_from_graph` runs exactly `MATCH (n) WHERE n.id = $curie RETURN properties(n) AS props` with `_GRAPH_ROW_LIMIT = 1`. That establishes only that ONE node's own property bag lacks the string. It says nothing about neighbouring nodes, edge properties, or differently-keyed nodes, all of which a graph-only agent traverses freely. The docstring claims the function decides whether "the Layer 1 graph already contains" the value; it decides whether one node's properties contain it.
- Reproduction: `scratchpad/attack2b.py` then `attack2c.py`, both against the live graph.

  Step 1, what the graph holds ONE HOP from BRCA1 over a real edge label:

```
$ venv/bin/python scratchpad/attack2b.py
FULL PROPERTIES of the disease node one hop from BRCA1:
[
  {
    "props": "{\"id\": \"MedGen:C0346153\", \"name\": \"MeSH\", \"xrefs\": \"\", \"source\": \"MedGen\", \"agent_type\": \"\", \"source_url\": \"https://www.ncbi.nlm.nih.gov/medgen/C0346153\", \"knowledge_level\": \"\"}"
  }
]
```

  Step 2, ask the absence check about those same values, anchored on BRCA1:

```
$ venv/bin/python scratchpad/attack2c.py
  ACCEPTED as live_only : the MedGen CURIE of a disease linked to BRCA1
      value='MedGen:C0346153'
  ACCEPTED as live_only : that disease's source URL
      value='https://www.ncbi.nlm.nih.gov/medgen/C0346153'
  ACCEPTED as live_only : the bare MedGen concept id
      value='C0346153'
```

  All three are certified absent from the graph. All three are held by the graph, reachable from the anchor CURIE by a single `gene_associated_with_condition` traversal, which is the most ordinary query the agent makes.
- Why it matters: this is the brief's attack 2 and it lands. A `live_only` row pinning "the MedGen concept associated with BRCA1" would pass the absence check and then be satisfied by an agent that never left Layer 1. Combined with F-5.3-A-01 (the check is not even on the build path) the field carries no guarantee at all, but this finding is independent: even after A-01 is wired up, the check would still admit this row. The two must be fixed separately.
- Related: `_GRAPH_ROW_LIMIT = 1` also means that where more than one node shares the anchor id, only the first is examined and the rest are unexamined by construction.
- Also observed and worth recording: the check requires the anchor node to exist and raises a clear error otherwise, which is correct. But a `live_only` fact does not have to be about an entity the graph holds at all. The function signature forces every live-only fact to be anchored on a CURIE the graph already has, so the class of fact the field most obviously exists for, one about an entity the snapshot predates entirely, cannot be expressed without tripping the "anchor is not in the graph at all" refusal.
- NOT FIXED
### F-5.3-A-06: the gate arm named `..._is_refused_by_the_builder` never invokes the builder, which is why F-5.3-A-01 shipped

- Severity: major
- What: `tests/system_03_search_agent/eval/test_phase_5_3_premise.py:388`, `test_p5_a_graph_satisfiable_fact_is_refused_by_the_builder`, calls `assert_absent_from_graph` directly. It imports neither `build_row` nor `build_row_fields` nor `main`. Its name states a property of the builder that the body never tests, and the section comment above it says "This is the arm that makes live_only mean anything."
- Reproduction: the whole body, verbatim:

```python
def test_p5_a_graph_satisfiable_fact_is_refused_by_the_builder() -> None:
    from eval.golden.build_dataset import (
        VerificationFailed,
        assert_absent_from_graph,
        graph_is_reachable,
    )
    if not graph_is_reachable():
        pytest.skip(...)
    with pytest.raises(VerificationFailed, match="graph already"):
        assert_absent_from_graph(
            fact="gene_symbol",
            value="BRCA1",
            curie="NCBIGene:672",
        )
```

  The word "builder" appears in the test's name and in no executable line of it. F-5.3-A-02 shows what the builder actually does with the same class of input: it accepts it and prints `BUILDER VERDICT: verified`.
- Why it matters: the goal contract's verify item 2 reads "The builder REFUSES a `live_only` fact that the live graph already contains, proven by a mutation that plants a graph-satisfiable fact and requires the build to fail." No such proof exists. The test name is what a reader checks the contract against, and the name is the only place the claim is made. This is the mechanism by which F-5.3-A-01 reached merge review with T-5.3-03 marked done: the arm reads as the required proof and is a unit test of a helper.
- Contrast that makes it sharper: the sibling arms P7 DO test the builder, by calling `build_row_fields` and reading the emitted row, and they are the reason `must_reach` is genuinely wired. There is no equivalent arm for `live_only`, and that missing arm is precisely the hole the defect sits in.
- NOT FIXED

### F-5.3-A-07: the gate's live arms genuinely execute (F-5.3-04 verified fixed), recorded as a negative result

- Severity: not a defect. Recorded because the brief asked it be confirmed.
- What: attack 5 asked whether the two live arms still silently skip. They do not.
- Reproduction:

```
$ venv/bin/python -m pytest tests/system_03_search_agent/eval/test_phase_5_3_premise.py \
    tests/system_03_search_agent/eval/test_phase_5_3_mutation.py -v -rs --no-header
...
tests/.../test_p5_a_graph_satisfiable_fact_is_refused_by_the_builder PASSED
tests/.../test_p5_control_a_fact_the_graph_lacks_is_accepted PASSED
...
============================= 35 passed in 14.62s ==============================
```

  No `s` markers, no short skip summary emitted under `-rs`, and the 14.62s wall time is consistent with real network calls rather than a short-circuit. Independently, my own probes in F-5.3-A-02, A-04 and A-05 reached the live graph through the same `_graph_request` path and returned real BRCA1 property bags, so the transport is genuinely live from this session.
- Caveat that keeps this from being reassurance: both arms still call `pytest.skip` when `graph_is_reachable()` is false, so on a machine without `GRAPH_QUERY_URL` the only arms covering `live_only` vanish and the file still reports all-green. Under CI, where build phase 4.14 recorded that a clean machine lacks roughly thirty environment values, that is the default state. See F-5.3-A-08.
### F-5.3-A-08: this phase's gate goes RED in CI, on two separate gates, because the unit job holds no graph credential

- Severity: major (reachable: it fires on the pull request that merges this phase)
- What: the phase 5.3 premise and mutation files carry NO `integration` marker, so CI gate 4 (`pytest -m "not integration"`, `.github/gates/gate04_unit_suite.sh`, no path argument, the whole suite) collects and runs them. The unit job in `.github/workflows/ci.yml` sets no `GRAPH_QUERY_URL`; only the separate integration job at line 193 does, and `.env` is untracked so it does not exist on a runner. The graph is therefore unreachable in gate 4, and two independent gates fail as a result.
- Reproduction 1, gate 4 fails. Simulating a machine with no reachable graph:

```
$ GRAPH_QUERY_URL="https://127.0.0.1:9" venv/bin/python -m pytest \
    tests/system_03_search_agent/eval/test_phase_5_3_premise.py \
    tests/system_03_search_agent/eval/test_phase_5_3_mutation.py -rs --no-header -q
...
E           AssertionError: M9: make the graph absence check refuse everything: the arms ['test_p5_control_a_fact_the_graph_lacks_is_accepted'] stayed GREEN with the control they name deleted, so they are vacuous.
E             s                                                                        [100%]
E             1 skipped, 20 deselected in 0.04s
...
SKIPPED [1] tests/system_03_search_agent/eval/test_phase_5_3_premise.py:396: graph query service unreachable; this arm is a live measurement and a skip is NOT a pass (see the phase file's blocked-stop)
SKIPPED [1] tests/system_03_search_agent/eval/test_phase_5_3_premise.py:419: graph query service unreachable; a skip is NOT a pass
2 failed, 31 passed, 2 skipped in 8.66s
```

  The mutation harness cannot tell a skipped arm from a vacuous one: it asserts a non-zero return code, and a skip returns zero.

- Reproduction 2, gate 4b fails independently. `.github/gates/gate04b_no_unsanctioned_skips.sh` runs `assert_no_db_skips.py`, which is DENY-BY-DEFAULT over a closed allowlist. Neither 5.3 skip message matches any sanctioned pattern:

```
$ venv/bin/python scratchpad/attack_ci.py
None <- graph query service unreachable; this arm is a live measurem
None <- graph query service unreachable; a skip is NOT a pass
```

  The near miss is worth naming: the allowlist pattern is `graph service`, and the message says `graph query service`. The two words are not contiguous, so the regex does not match. That is a one-word difference between green and red, and nothing in either file points at the other.

- Why it matters: build phase 4.15 and build phase 5.0 each shipped a defect CI found that no local run could, and the recorded lesson is that a green local run is not evidence about CI. This phase has that shape again, in the opposite direction: local is green (35 passed) and CI is red on two gates. The goal contract's verify item 5 names doc drift, ruff and isort but never names running the gate under CI's environment, so nothing in the contract would have caught it.
- Note on the correct fix direction: adding the phrase to `_SANCTIONED_SKIPS` would make gate 4b green while leaving gate 4 red on M9, and would also be the exact act that script's own docstring warns against ("Do not add one to make a red build go green without establishing that the skip is genuinely a sanctioned opt-in rather than a dependency CI was supposed to provide and did not").
- NOT FIXED

### F-5.3-A-09: the phase 5.3 gate makes live network calls inside the UNIT suite, because `tests/conftest.py` blocks only `httpx` and `requests`, not `urllib`

- Severity: major
- What: `tests/conftest.py`'s session-scoped autouse fixture `_forbid_live_http_in_the_unit_suite` exists so that "if a test needs to reach live NCBI, it belongs in the RUN_PREMISE_GATE=1 gate ... not the plain unit run". It enforces that by patching three entry points and only three:

```python
    httpx.AsyncHTTPTransport.handle_async_request = _blocked_async_handle_request
    httpx.HTTPTransport.handle_request = _blocked_sync_handle_request
    requests.adapters.HTTPAdapter.send = _blocked_requests_send
```

  `eval/golden/build_dataset.py` reaches both NCBI E-utilities and the graph query service through `urllib.request.urlopen`, which is patched by nothing. The new gate therefore transits the block untouched and makes real outbound calls during an ordinary `pytest` run with no opt-in.
- Reproduction: the 35-test run in F-5.3-A-07 took 14.62s and my probes confirm real BRCA1 property bags came back over that same `_graph_request` path, with `RUN_PREMISE_GATE` unset. The fixture's docstring says it is "Session-scoped so the patch is installed once and every test in the run, regardless of file, is covered, including test files written after this fixture was added." That sentence is false for any file using `urllib`, and this phase is the file that makes it false.
- Why it matters: three consequences, each independent. First, the hermetic-unit-suite property the fixture was written to guarantee (build phase 4.14's Finding 4) is now broken, and broken silently. Second, every developer's plain `pytest` run now spends live NCBI and live graph quota. Third, it is the direct cause of F-5.3-A-08: had the file been marked `integration` or gated behind `RUN_PREMISE_GATE`, gate 4 would never have collected it.
- This is a defect in code new in this phase interacting with an existing control; the existing control's docstring makes a completeness claim that this phase falsifies, which is build phase 4.15's "confident sentence" family again.
- NOT FIXED
### F-5.3-A-10: the four-way parametrized `live_only` arm cannot tell which key the loader named, because the message always lists all four

- Severity: minor
- What: `test_p3_live_only_missing_any_required_key_is_refused` (premise gate line 234) asserts `assert missing in str(excinfo.value)`. The loader's message enumerates the whole required-field tuple every time:

```python
            raise DatasetValidationError(
                f"row {row_id}: live_only is missing a non-empty {name!r}. "
                f"All of {list(_REQUIRED_LIVE_ONLY_FIELDS)} are required."
            )
```

  Every one of the four parametrized cases therefore matches on the trailing enumeration alone, regardless of which field the loader actually named. The parametrisation buys four IDs and one bit of information.
- Reproduction: `scratchpad/attack_p3.py`. Simulating a loader mutated to always name `'fact'` (an ordinary copy-paste defect), the arm stays green on all four parameters:

```
  mutated message: row G-TEST: live_only is missing a non-empty 'fact'. All of ['fact', 'value', 'observed_from', 'observed_on'] are required.
    param fact           -> assertion `'fact' in msg` = True
    param value          -> assertion `'value' in msg` = True
    param observed_from  -> assertion `'observed_from' in msg` = True
    param observed_on    -> assertion `'observed_on' in msg` = True
```

- Why it matters: this is the shape F-5.3-01 was filed for one arm above it, unrepaired here. The gate's own P2 comment states the principle ("each negative arm asserts the SPECIFIC message, not merely that some error arrived") and this arm does not follow it: it asserts a substring that the message contains unconditionally. It still proves an error is raised for each deletion, which is why I file it minor rather than major, but it proves nothing about attribution, and attribution is the whole reason the arm is parametrized.
- Unsure flag: I have not confirmed a mutation case exists targeting this specific arm; M-numbering is reviewed separately below.
- NOT FIXED
### F-5.3-A-11: the mutation harness passes a case whose `expect_red` names an arm that does not exist, because pytest's "no tests collected" exit code is also non-zero

- Severity: major
- What: `test_each_arm_goes_red_under_its_own_mutation` decides a case with `assert result.returncode != 0`. `_run_arms` selects arms with `-k "<name> or <name>"`. When no arm matches the selector, pytest deselects everything and exits 5, which is non-zero, so the case passes having executed no assertion about any control. The harness guards the OTHER side of this hazard carefully (`occurrences == 1`, plus `test_harness_rejects_a_mutation_that_does_not_apply`) but has no guard at all on the arm-name side.
- Reproduction, two steps.

  Step 1, pytest's exit code when `-k` matches nothing:

```
$ venv/bin/python -m pytest tests/system_03_search_agent/eval/test_phase_5_3_premise.py \
    -k "test_p9_an_arm_that_does_not_exist" -q --no-header
21 deselected in 0.03s
EXIT CODE = 5
```

  Step 2, feed the real harness a real mutation whose named arm has one extra letter (`scratchpad/attack_mut.py`):

```python
bogus = mut.Mutation(
    name="MX: a real control deleted, but the named arm is a typo",
    path=mut.LOADER,
    old="    unknown = [name for name in raw if name not in ALLOWED_MUST_REACH]",
    new="    unknown = []",
    expect_red=("test_p2_unknown_tool_in_must_reach_is_refusedd",),  # one extra 'd'
)
```

  Output:

```
HARNESS VERDICT: PASSED, proving nothing.
  The named arm does not exist; pytest deselected everything and
  exited 5, which satisfies the harness's `returncode != 0`.
```

- Why it matters: this is a vacuous assertion in the very harness whose job is proving other assertions are not vacuous, which is build phase 4.14's recorded lesson that "a mutation harness proves only what it mutates". Concretely: any of the twelve `expect_red` tuples could be misspelled, or could name an arm that is later renamed or deleted, and the case stays green forever while covering nothing. Arm renames are ordinary maintenance, so this is a live decay path rather than a hypothetical. The two-line repair is to assert the selector actually collected the expected number of arms, or to assert on `result.returncode == 1` specifically rather than on non-zero.
- I verified the twelve shipped `expect_red` names all currently resolve (all 12 cases went red for real reasons in the clean run), so no shipped case is presently vacuous through this hole. The defect is the missing guard, not a current miss.
- Working tree confirmed clean after this probe: `git status --porcelain` shows only my two untracked report files.
- NOT FIXED
### F-5.3-A-12: the goal contract requires a mutation for EVERY arm; the phase's strongest backward-compatibility arm has none

- Severity: minor
- What: the phase file's verify item 1 reads "a premise gate ... every arm paired with a named mutation APPLIED by a harness in the same edit as the arm". Four of the eighteen arm functions have no mutation naming them. Three are controls-of-controls, which is defensible. The fourth, `test_p4_no_shipped_row_changed_meaning_under_the_schema_bump`, is the arm that discharges verify item 4 ("Every one of the 50 existing rows survives the schema change with its meaning unchanged, proven by diffing the v1 and v2 rows field by field"), and it is the most consequential arm in the file after P5.
- Reproduction: mapping the arm functions against every name appearing in an `expect_red` tuple:

```
18 arm functions in the premise gate
14 distinct arms named in expect_red

  NO MUTATION -> test_p2_control_the_baseline_row_validates
  NO MUTATION -> test_p3_control_a_complete_live_only_block_validates
  NO MUTATION -> test_p4_no_shipped_row_changed_meaning_under_the_schema_bump
  NO MUTATION -> test_p6_control_the_scan_actually_reads_the_builder
```

- Why it matters: nothing has demonstrated that the field-by-field diff can go red. Its `moved_forward == 50` populate-check is well-designed on paper, but well-designed on paper is exactly what the eleven prior vacuity instances also were. The mutation harness file explicitly refuses to make a completeness claim, and that refusal is correct, but the CONTRACT makes the completeness claim on its behalf, so the two documents disagree and the phase file is the one a reviewer checks against.
- NOT FIXED

### F-5.3-A-13: the v1 baseline is genuine (negative result, recorded)

- Severity: not a defect.
- What: I suspected `eval/golden/golden_dataset_v1_baseline.json` might have been derived from the new build, which would make the backward-compatibility diff circular. It was not.
- Reproduction:

```
$ git show 332da84:eval/golden/golden_dataset.json > scratchpad/v1_from_git.json
$ venv/bin/python ...
git v1 version: 1 rows: 50
baseline version: 1 rows: 50
baseline == the v1 payload at the branch point: True
```

  The baseline is byte-equivalent as parsed JSON to the shipped v1 dataset at the branch-point commit `332da84`. Verify item 4's comparison is therefore against an independent artefact, as claimed.
- Residual risk worth one line: nothing pins the baseline to that commit. If a future rebuild overwrites it, the diff silently becomes a comparison of the file against itself and stays green. A hash assertion or a `git show` in the arm would close that.
### F-5.3-A-14: schema v2 backward compatibility independently confirmed (negative result, recorded)

- Severity: not a defect.
- What: I diffed the branch-point v1 payload against the shipped v2 file myself rather than trusting the phase's arm or its claim.
- Reproduction, my own script over `git show 332da84:eval/golden/golden_dataset.json` versus the working tree:

```
version: 1 -> 2
rows: 50 -> 50

fields that differ, and on how many rows:
   must_reach: 50
   provenance.read_on: 50

first 4 differing values:
   ('G-001', 'must_reach', '<absent>', [])
   ('G-001', 'provenance.read_on', '2026-08-30', '2026-08-31')

rows with a NON-EMPTY must_reach: NONE
rows with a live_only block: NONE
```

  The phase file's T-5.3-05 claim ("The ONLY change is `provenance.read_on` moving 2026-08-30 to 2026-08-31, plus the additive `must_reach`") holds exactly.
- The last two lines are the load-bearing part for the rest of this report: NO shipped row uses either new field. That is honestly disclosed in the coverage statement, and it means the `live_only` path has never executed on a real build even once, which is why F-5.3-A-01 could ship undetected.

### F-5.3-A-15: the dataset loader now drags 26 agent modules in, including the database session layer, and its docstring still says it depends on nothing but the standard library

- Severity: minor
- What: this phase added `from system_03_search_agent.harness.cache import REGISTERED_TOOL_SCHEMAS` to `src/system_03_search_agent/eval/dataset.py`. The module docstring's dependency block, unchanged, still reads:

```
Depends on:
    - Nothing beyond the standard library.
```

  It was already inaccurate before the phase (`tools.cypher_schemas` was imported at `332da84`), but the new import widens the footprint substantially.
- Reproduction: importing only the dataset loader:

```
import took 0.45s
26 system_03_search_agent modules pulled in by importing the DATASET LOADER:
    ... system_03_search_agent.data.session
    ... system_03_search_agent.feedback.promotion
    ... system_03_search_agent.harness.cache
    ... system_03_search_agent.orchestrator.few_shot_pool
    ... plus all seven tool schema modules
```

- Why it matters: two things, neither fatal. First, `.claude/rules/dependency-tracking.md` makes the module docstring the dependency record for Python modules under `src/system_03_search_agent/`, and this one is now materially wrong, which is the class of drift that rule exists to prevent. Second, the dataset loader is the artefact that is supposed to be independent of the agent, and it now transitively imports the session layer and the few-shot pool. I checked for import-time side effects (no engine construction, no `os.environ` read at module scope in `data/session.py`, and `few_shot_pool` only defines a lock and a constant), so I found no functional break, and I am filing this as minor drift rather than as a correctness defect.
- Unsure: I did not test the loader in an environment with no `.env` and no database configuration, so I cannot rule out an import-time failure there.
- NOT FIXED
### F-5.3-A-16: `must_reach` pins a vocabulary that NO observable record in this system uses, so the constraint is ungradeable as specified

- Severity: major
- What: `must_reach` names entries from `REGISTERED_TOOL_SCHEMAS`, the seven registry tool names. The only place a tool call is durably recorded is build phase 5.0's audit log, and its hook sits at the TRANSPORT chokepoints by deliberate design, not at `act_node`. The transport records a different vocabulary. So a row saying `must_reach: ["litvar2_lookup"]` can never be matched against anything the system writes down, because nothing writes `litvar2_lookup`.
- Reproduction: the two vocabularies, side by side.

  What `must_reach` may name:

```
$ venv/bin/python -c "...REGISTERED_TOOL_SCHEMAS..."
    clinicaltrials_search
    cypher_query
    litvar2_lookup
    ncbi_dbsnp
    ncbi_efetch
    pathogen_detection
    pubtator_annotate
```

  What the audit hook actually records as the `tool` field:

```
$ grep -rn "tool=" src/system_03_search_agent/tools/graph_connection.py src/system_03_search_agent/tools/ncbi_transport.py
src/system_03_search_agent/tools/graph_connection.py:719:            tool="cypher_query",
src/system_03_search_agent/tools/graph_connection.py:738:        tool="cypher_query",
src/system_03_search_agent/tools/ncbi_transport.py:1312:            tool="ncbi_transport:" + family,
src/system_03_search_agent/tools/ncbi_transport.py:1336:        tool="ncbi_transport:" + family,
```

  And `family` comes from a closed, DIFFERENT vocabulary:

```
RATE_LIMIT_FAMILIES = ("eutils", "datasets", "pubchem", "variation",
                       "pubtator", "litvar2", "clinicaltrials")
```

  Exactly one of the seven registry names (`cypher_query`) is recoverable from an audit line. The other six map onto transport families that do not carry the tool identity: `ncbi_efetch` and `ncbi_dbsnp` BOTH reduce to `ncbi_transport:eutils`, and `ncbi_dbsnp` additionally produces `ncbi_transport:variation`, so even the family is not a function of the tool.
- Why it matters: the phase's deliverable is explicitly "a better SPECIFICATION LANGUAGE" whose value is realised when build phase 5.2 is unparked. A specification language whose terms cannot be resolved against any recorded fact is not deferred work, it is a design gap that this phase locks in. The coverage statement says "NOTHING CHECKS `must_reach` AT GRADING TIME ... That happens when build phase 5.2 is unparked", which frames the gap as timing. It is not timing: `ncbi_efetch` and `ncbi_dbsnp` are not distinguishable in the audit log at all, so unparking 5.2 does not make them gradeable without a change to either this vocabulary or the audit hook's placement, and the audit hook's placement was itself a hard-won product-owner decision in build phase 5.0 (five call sites reach a data layer without passing through `act_node`).
- Why I file this rather than leaving it to 5.2: the whole justification for shipping `must_reach` now, ungraded, is that the language will be usable later. That claim is testable today and it does not hold.
- Unsure flag: I did not exhaustively enumerate every audit call site in the repository, so a third recording path with the registry vocabulary may exist. I searched the two transport chokepoints named in CLAUDE.md's build-phase-5.0 row and found only the two forms above.
- NOT FIXED

### F-5.3-A-17: `eval/` is outside CI gate 1 and gate 2's path lists, so the phase's main new file is compiled and import-order-checked by nothing

- Severity: minor
- What: `.github/gates/gate01_compile_and_import.sh` runs `compileall -q src services tests alembic`, and `.github/gates/gate02_import_order.sh` runs `isort --check-only --diff src tests services tracker alembic .claude .github`. Neither list includes `eval`. `eval/golden/build_dataset.py` is where 228 of this phase's changed lines live.
- Reproduction: the two scripts, read verbatim above; `eval` appears in neither path list. Gate 3 (`ruff check`, no path) does cover it, which is why the exposure is limited to compile and import order rather than lint.

```
$ venv/bin/isort --check-only --diff eval
isort on eval/ exit=0
$ venv/bin/ruff check .
All checks passed!
```

- Why it matters: no live defect today, both checks pass when pointed at `eval` by hand. It is the exact hazard build phase 4.15 recorded, a gate whose narrower path list silently excludes real code, and this phase is the first to put substantial production logic under `eval/`. Pre-existing rather than introduced here, but newly consequential.
- NOT FIXED
### F-5.3-A-18: the loader validates the new fields' SHAPE and nothing about whether a row contradicts itself

- Severity: minor (unsure on severity; several of these are arguably majors once rows are authored)
- What: the existing loader already refuses self-contradictory rows in several places, and those refusals are exactly what makes it trustworthy: an `expected_outcome` missing from `acceptable_outcomes` ("or the row contradicts itself"), a discovery row with no follow-ups, a non-discovery row carrying follow-ups, a kisses row not forbidding truncation, an `answer` row with an empty `must_cite`. The two new fields get none of that treatment.
- Reproduction: `scratchpad/attack_semantics.py`. Every one of these rows is ACCEPTED:

```
  ACCEPTED  a REFUSE row that also requires a live tool call
  ACCEPTED  a REFUSE row carrying a live_only FACT it must never state
  ACCEPTED  must_reach with the same tool five times
  ACCEPTED  must_reach naming all seven tools on a one-line lookup
  ACCEPTED  a live_only fact whose value contradicts a forbidden constraint
  ACCEPTED  live_only present but must_reach EMPTY: needs a live call, requires no tool
  ACCEPTED  observed_on in the future / not a date at all
  ACCEPTED  observed_on before the graph snapshot it claims to postdate
```

- The two I would argue hardest for:
  - `expected_outcome: "refuse"` plus `live_only`. The row demands the agent refuse to answer AND demands the answer contain a specific fact. It can never pass. Group D is ten refusal rows, so this is the combination an author is most likely to reach for by accident, and the loader's own stated principle ("A row requiring a tool that does not exist can never be satisfied, so it would fail forever while looking like an agent defect") applies word for word.
  - `observed_on` is required to be a non-empty string and is never parsed. `"tomorrow-ish"` is accepted. The field exists to record when the value was seen live, which is the only thing that lets a later reader judge whether a `live_only` fact has aged past the graph snapshot, and the phase's own shelf-life flag (F-5.3-C on the board) depends on exactly that judgement. An unparseable date makes that flag undischargeable. `provenance.read_on` has the same weakness, which is pre-existing.
- NOT FIXED
### F-5.3-A-19: `docs/build/Golden_dataset_method.md` is the named authority on the row schema and was not touched by this phase, so it documents v1 only

- Severity: minor
- What: CLAUDE.md's reference table designates `docs/build/Golden_dataset_method.md` as "The complete method behind the 50-query golden dataset ... Read when: Before adding, removing or editing any golden row, and before changing the eval harness's expectations." Its field table enumerates every row field. `must_reach` and `live_only` are absent from it, and the file does not appear in this phase's commit at all.
- Reproduction:

```
$ grep -n "must_reach\|live_only" docs/build/Golden_dataset_method.md
(no matches)

$ git show --stat 93cea0b
... eval/golden/build_dataset.py, eval/golden/golden_dataset.json,
    eval/golden/golden_dataset_v1_baseline.json, src/.../eval/dataset.py,
    tests/.../test_phase_5_3_{premise,mutation}.py, tracker/*, requirements/*
    (docs/build/Golden_dataset_method.md is not in the list)
```

  The doc's field table currently ends at `notes` and its schema discussion says "Two schema choices are worth explaining", which is now three.
- Why it matters: this phase's entire deliverable is a specification LANGUAGE for a future author, and the document that author is instructed to read before touching a row does not mention either new term. Doc drift is normally cosmetic; here it lands on the one artefact the phase exists to serve. `tracker/check_doc_drift.py` reports 0 stale because it computes counts, not schema coverage, so nothing catches this.
- NOT FIXED

### F-5.3-A-20: the gate claims it was "watched failing" before implementation, and the repository cannot corroborate that

- Severity: minor (unsure; this is a process claim, not a code defect)
- What: `test_phase_5_3_premise.py` line 3 states "Written at cadence stage 5, BEFORE any implementation, and watched failing." The branch carries exactly one implementation commit, `93cea0b`, which contains the gate, the mutation harness, the loader change, the builder change and the regenerated dataset together. There is no commit in which the gate exists and the implementation does not.
- Reproduction:

```
$ git log --oneline develop..HEAD
93cea0b feat(eval): golden dataset schema v2, so a row can require a live Layer 2 or 3 call
3430367 docs(tracker): open build phase 5.3 after the product-owner review of the golden 50
```

- Why it matters: I am not alleging the step was skipped, and the phase file's own finding log (F-5.3-01 through F-5.3-04, all caught by mutation) reads like a gate that genuinely ran. I file it because it is a confident sentence about a check, in a repository whose recorded worst-defect family is exactly confident sentences about checks, and because the claim is the kind that costs one extra commit to make verifiable and nothing to assert falsely.
- NOT FIXED
### F-5.3-A-21: ANY non-ASCII `live_only` value is certified absent from the graph unconditionally, because `json.dumps` escapes it and the value does not

- Severity: major
- What: the absence check builds its haystack with `json.dumps(rows[0], default=str)`. `json.dumps` defaults to `ensure_ascii=True`, so every non-ASCII character in a graph property becomes a `\uXXXX` escape sequence in the haystack. The needle, `value.casefold()`, is the raw string. A value containing even one non-ASCII character therefore CANNOT match, no matter what the graph holds, and the check returns "absent" every time.
- Reproduction: the two lines under test, taken from `git show HEAD:eval/golden/build_dataset.py` so the result is immune to any in-flight mutation:

```python
    haystack = json.dumps(rows[0], default=str).casefold()
    if value.casefold() in haystack:
```

  Applied to graph rows that literally contain the value:

```
--- non-ASCII values, on a graph row that DEMONSTRABLY HOLDS them ---
  ABSENT (row accepted as live_only)  graph row literally contains 'Müller-Weiss disease'
  ABSENT (row accepted as live_only)  graph row literally contains 'TNF-α'
  ABSENT (row accepted as live_only)  graph row literally contains 'β-globin'
  ABSENT (row accepted as live_only)  graph row literally contains '5′ UTR variant'
  ABSENT (row accepted as live_only)  graph row literally contains 'Sjögren syndrome'

--- an ASCII control, same construction ---
  PRESENT (row refused)               graph row contains 'Muller-Weiss disease'

--- why: json.dumps defaults to ensure_ascii=True ---
    {"name": "TNF-α"}
```

  The ASCII control is the load-bearing half: the identical construction with the umlaut removed IS caught, so the failure is attributable to the escaping and to nothing else.
- Why it matters: this is not an exotic input class in a biomedical dataset. Greek letters are standard in protein and receptor nomenclature (TNF-α, β-globin, γ-secretase), eponymous disease names carry diacritics (Sjögren, Behçet, Münchausen), and NCBI record text uses typographic primes and dashes (5′ UTR, en dashes in coordinate ranges). Every one of those values silently defeats the check. Combined with F-5.3-A-04 (whitespace and punctuation false negatives) and F-5.3-A-05 (one-node scope), the check's actual guarantee is much narrower than "the graph does not contain this value": it is roughly "this exact ASCII byte-run does not appear in this one node's serialised property bag".
- Answering the brief's own question, "what else would produce this same number": a check that always returned "absent" would produce an identical result on all five inputs above. The gate's live control (`ZZQXFAKE1-not-a-real-symbol`) is pure ASCII, so it does not distinguish the two.
- NOT FIXED
### F-5.3-A-22: full suite independently re-run, no regression (negative result, recorded)

- Severity: not a defect.
- Reproduction, my own run rather than the author's reported figure:

```
$ venv/bin/python -m pytest -m "not integration" -q --no-header -p no:cacheprovider
4515 passed, 148 skipped, 23 deselected, 1 xfailed, 8 warnings in 146.10s (0:02:26)
[exited with code 0]
```

  4515 passed matches the commit message exactly. My skip count is 148 against the reported 171 because the graph was reachable from this session and the author's run apparently had fewer live credentials available; that difference is in the safe direction. `ruff check` over the whole repository: `All checks passed!`. `isort --check-only` via `.github/gates/gate02_import_order.sh`: exit 0. `tracker/check_doc_drift.py --check`: `ok: 10 facts computed | 0 stale | 0 structural`.
- I also confirmed the mutation harness cannot corrupt a concurrent run: `pytest-xdist` is not installed and `pyproject.toml` sets no parallel `addopts`, so the on-disk source mutations are serial.
- Working tree clean throughout: every `git status --porcelain` during this round showed only my own untracked report file and the judge's.

### F-5.3-A-23: the phase's motivating measurement is independently confirmed (negative result, recorded)

- Severity: not a defect.
- What: the phase rests on the claim that `must_cite` is satisfiable straight from a Layer 1 node's own `source_url`, so a citation constraint cannot distinguish a federating agent from a graph-only one. I checked it against the live graph rather than reading it.
- Reproduction: G-001's `must_cite` contains `https://www.ncbi.nlm.nih.gov/gene/672`, and the live graph node `NCBIGene:672` carries:

```
"source_url": "https://www.ncbi.nlm.nih.gov/gene/672"
```

  Byte-identical. A graph-only agent satisfies that constraint with one Cypher read. The problem statement is real, which is why the failure of the fix matters rather than being academic.
### F-5.3-A-24: the critical SURVIVES the obvious fix; wiring the absence check in does not close it

- Severity: critical
- What: F-5.3-A-01's repair is one line, calling `assert_absent_from_graph` from the build path. I simulated exactly that repair and re-ran the attack. Graph-satisfiable `live_only` rows still ship. This matters because it is the difference between "one uncalled function" and "the control does not work", and a fix round that only wires the call would report the phase closed while the premise is still defeated.
- Reproduction: `scratchpad/attack_postfix.py`. It defines the fixed builder:

```python
def build_row_WITH_THE_FIX(fetcher, spec):
    lo = spec.get("live_only")
    if lo is not None:
        bd.assert_absent_from_graph(fact=lo["fact"], value=lo["value"],
                                    curie=spec["absence_anchor"])
    return bd.build_row(fetcher, spec)
```

  and runs three rows through it against the LIVE graph. Exact output:

```
  STILL ACCEPTED (verified): a fact on a NEIGHBOUR node (F-5.3-A-05)
      value='MedGen:C0346153'
  STILL ACCEPTED (verified): the same node's own name, one extra space (F-5.3-A-04)
      value='BRCA1  DNA repair associated'
  STILL ACCEPTED (verified): the same node's own name, trailing period (F-5.3-A-04)
      value='BRCA1 DNA repair associated.'
```

  All three are answerable by a graph-only agent. The first is one `gene_associated_with_condition` hop from the anchor. The second and third are the anchor's OWN `name` property, differing from the graph's rendering by one space and by one period.
- Why it matters: this fires the review loop's stop condition in its strongest form. The defect is not merely inside a fix made during this phase, it is inside the fix that has not been written yet and is the one a fix round would obviously reach for. Three independent repairs are needed, not one: wire the call (A-01), stop deciding presence by ASCII substring over a JSON blob (A-04, A-21), and stop scoping the question to a single node's own properties (A-05).
- NOT FIXED
### F-5.3-A-25: THE SUBJECT CHANGED UNDER THIS ROUND. A fix round edited three tracked files while this review was still running, and its fix for F-5.3-A-01 does not close F-5.3-A-04, A-05 or A-21

- Severity: critical (process, and it directly implicates a fix made during this phase)
- What: at the start of this round `git status --porcelain` showed a clean tree. Near the end it showed three tracked files modified, none of them by me (I have no Write or Edit tool):

```
 M eval/golden/build_dataset.py
 M src/system_03_search_agent/eval/dataset.py
 M tests/system_03_search_agent/eval/test_phase_5_3_premise.py
 3 files changed, 138 insertions(+)
```

  The new code cites MY OWN finding identifiers, `F-5.3-A-01` and `F-5.3-A-03`, so a fix agent is reading this report and patching against it while the round is still open. Every measurement above was taken against commit `93cea0b` with a clean tree, and the earlier findings should be read against that commit, not against the working tree as a later reader will find it.
- Why this is itself a finding, not just a note: this repository's review loop depends on the reviewed artefact holding still. A fix landing mid-round means no report in this phase describes a single coherent subject, and the reviewer cannot tell which of their own results are still reproducible. It also means the fix has NOT been reviewed by anyone: the round that would have reviewed it is the one being patched.
- The substantive half, and the reason this is critical rather than procedural. The in-flight fix for F-5.3-A-01 wires the absence check onto the build path like this:

```python
        for curie in must_resolve:
            assert_absent_from_graph(
                fact=live_only["fact"], value=live_only["value"], curie=curie
            )
```

  That is the exact repair F-5.3-A-24 predicted and pre-tested. It changes WHICH nodes are inspected, from one hand-passed anchor to the row's `must_resolve` CURIEs, and changes NOTHING about how presence is decided. So:

  - F-5.3-A-21 stands untouched: `assert_absent_from_graph` still builds its haystack with `json.dumps(...)`, so any non-ASCII value is still certified absent unconditionally.
  - F-5.3-A-04 stands untouched: the comparison is still a casefolded substring over a serialised blob, so `'BRCA1  DNA repair associated'` (one extra space) and `'BRCA1 DNA repair associated.'` (trailing period) still pass while the graph holds the value, and key names like `source_url` are still false positives.
  - F-5.3-A-05 is only PARTIALLY addressed and the new code says so in its own comment ("a value sitting on a node this row never names is not detected here"). A fact on a node one hop from a `must_resolve` CURIE, such as `MedGen:C0346153` from `NCBIGene:672`, is still certified absent unless that neighbour happens to be in `must_resolve` too.

  I have NOT re-run my probes against the working-tree version, deliberately: the tree is being written to concurrently and any result I got could be from a half-written file. The three conclusions above are read from the diff, and I flag them as read rather than measured.
- What I am asking for, since I close nothing: this fires the review loop's stop condition. Per the harness, a finding located inside an earlier fix stops the phase mid-round and escalates to the product owner rather than continuing into another fix. The specific question for the product owner is whether the absence check's COMPARISON should be rebuilt (structured property-value equality after normalisation, over a defined node scope) rather than patched again, which is `attack-the-constraint` applied to a check and the same reversal that ended build phase 5.0's four-round loop.
- NOT FIXED

## Verdict: FAIL

Against the phase's goal contract: "a golden row can state, and the loader can enforce, that answering it requires a live Layer 2 or Layer 3 call, by two independent mechanisms, with the second protected against silently becoming false."

The second mechanism is not protected against silently becoming false. It IS silently false, today, in four independent ways.

Blocking:

- F-5.3-A-01 / F-5.3-A-02 (critical): `assert_absent_from_graph` was never called by the builder. A graph-satisfiable `live_only` row passes the real builder and the real loader end to end. Proven by execution.
- F-5.3-A-24 (critical): the obvious repair does not close it. Rows satisfiable one hop away, or differing from the graph's own rendering by one space, still ship after the check is wired in.
- F-5.3-A-25 (critical, and INSIDE A FIX MADE DURING THIS PHASE): a fix round patched three tracked files while this round was still running, citing my own finding IDs. Its fix wires the call and leaves the comparison untouched, so A-04, A-21 and most of A-05 survive it by inspection. This is the review loop's stop condition, and it should escalate to the product owner rather than proceed to another fix round.
- F-5.3-A-21 (major): every non-ASCII value is certified absent unconditionally, because `json.dumps` escapes the haystack and not the needle. Greek letters and diacritics are ordinary in this domain.
- F-5.3-A-08 (major, reachable): the phase's gate goes red on CI gates 4 and 4b, because the unit job holds no graph credential and the mutation harness cannot distinguish a skipped arm from a vacuous one.
- F-5.3-A-16 (major): `must_reach` pins a vocabulary no recorded artefact uses. `ncbi_efetch` and `ncbi_dbsnp` are not distinguishable in the audit log at all, so the deferral to build phase 5.2 does not make the constraint gradeable.

The brief's six attacks, answered:

1. Break the substring absence test: BROKEN, both directions, F-5.3-A-04 and F-5.3-A-21. It is the same defect build phase 5.2 shipped, and `gene` is literally the reproducing token again.
2. Does the one-node query establish graph absence: NO, F-5.3-A-05, proven with a real one-hop traversal on the live graph.
3. Author a passing, graph-satisfiable row: YES, in four lines, F-5.3-A-02. And it still works after the obvious fix, F-5.3-A-24.
4. Defeat the `observed_from` refusal: DEFEATED by a single space, F-5.3-A-03. Same losing shape as build phase 5.0's credential scan, and the sibling field twenty lines up already uses the allowlist form the docstring claims parity with.
5. Do the live arms genuinely execute: YES locally, F-5.3-A-07, no `s` markers in a 35-test run. But they skip on any machine without the credential, and that turns CI red rather than green, F-5.3-A-08.
6. Assertions that cannot fail: THREE more found. F-5.3-A-11 (the mutation harness itself passes a case naming a non-existent arm, because pytest exits 5 and 5 is non-zero), F-5.3-A-06 (the arm named `..._is_refused_by_the_builder` never invokes the builder), F-5.3-A-10 (the four-way parametrized arm cannot tell which key was named).

What I verified with my own probes, against commit `93cea0b` with a clean tree:

- That `assert_absent_from_graph` has no call site outside its own test (grep, then execution through the real `build_row` and `load_golden_dataset`).
- That a graph-satisfiable `live_only` row is accepted, and that the absence check refuses the same value when called by hand.
- The absence check's behaviour on 22 hand-built values against the LIVE graph, both false positives and false negatives.
- That a fact one `gene_associated_with_condition` hop from BRCA1 is certified absent, by first reading the neighbour out of the live graph.
- That `observed_from` accepts 9 of 13 circular-sounding strings, including a non-breaking space variant.
- That pytest exits 5 on an empty `-k` selection, and that the real mutation harness passes a case exploiting it.
- The v1-to-v2 diff, computed myself from `git show 332da84:eval/golden/golden_dataset.json`, and the baseline file's equivalence to it.
- The full unit suite (4515 passed, 0 failed, my own run), ruff over the whole repository, gate 2's isort invocation, and doc drift.
- The two tool-name vocabularies, and that `eval/` imports nothing from the agent.

What I only READ and did not measure:

- The three conclusions in F-5.3-A-25 about the in-flight fix. I read the diff; I deliberately did not run probes against a tree being written to concurrently.
- The claim in F-5.3-A-16 that no third audit call site uses the registry vocabulary. I searched the two transport chokepoints named in CLAUDE.md's build-phase-5.0 row; I did not enumerate every call site.
- F-5.3-A-15's residual risk about importing the loader with no `.env` and no database configuration.
- F-5.3-A-20's process claim about the gate being watched failing; git cannot corroborate it either way.

Closed: nothing. Fixed: nothing. Every finding above is NOT FIXED and is for a separate role to verify and close.
