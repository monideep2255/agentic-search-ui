# Build phase 4.14: adversary report

Round: adversary, unscripted half. Run 2026-08-26 against `phase/4.14-ci-gates` at commit `4ea0778`.

Did I find a way to make this CI report green while verifying nothing?

YES. Four separate ways, three of them reachable without anybody acting in bad faith, and one of them live in the tree at this commit.

The shortest statement of the result: the phase's own headline finding, F-4.14-03, is not fixed. `assert_no_db_skips.py` is silent about 36 database-unreachable skips that exist in the repository today, and prints `ok: 36 skipped test(s) in the report, none of them for a database reason` while saying it.

## Table of contents

- [Summary](#summary)
- [Findings](#findings)
- [Attacks that found nothing](#attacks-that-found-nothing)
- [Coverage of this report](#coverage-of-this-report)

## Summary

| ID | Severity | What |
|----|----------|------|
| F-4.14-A-01 | critical | `assert_no_db_skips.py` misses 36 database-unreachable skips that exist in the tree today. F-4.14-03 is not fixed |
| F-4.14-A-02 | critical | The marker list is an enumeration of instances. Six of six plausible phrasings evade it. Its own docstring claims it is not this shape |
| F-4.14-A-03 | critical | Gate 5 reports a plain green check having run zero tests, and cannot ever run one, because the workflow never sets `RUN_PREMISE_GATE` |
| F-4.14-A-04 | critical | Nothing makes any gate merge-blocking. Branch protection is unavailable on this repository's plan. The done-when is not achievable as written |
| F-4.14-A-05 | high | The premise gate reads step names and substrings. Every gate body can be replaced by `true` with all 16 arms staying green |
| F-4.14-A-06 | high | Gate 9's required-path assertion is satisfied by two `assert True` tests named for a blue border and horizontal scrolling |
| F-4.14-A-07 | high | Gate 10's path filter fails OPEN on any git error, skips the WCAG gate, and prints a false summary line. Nothing guards it |
| F-4.14-A-08 | high | Neither assertion script has a single test. They are the only new executable logic in the phase |
| F-4.14-A-09 | medium | The `alembic` premise that justified disabling ruff `I001` repository-wide is overstated by a factor of ten. 274 files left unpoliced |
| F-4.14-A-10 | medium | P12 and P13 match raw text, not TOML. A commented-out `ignore = ["I001"]` passes P13 |
| F-4.14-A-11 | medium | `assert_no_db_skips.py` has no populate-check. A zero-testcase report exits 0 saying `ok` |
| F-4.14-A-12 | low | M20 claims to prove the populate-check works but verifies a correlate, never the property |
| F-4.14-A-13 | low | Gate 1 is named "compiles and imports cleanly" and never imports |

## Findings

### F-4.14-A-01: the phase's own headline finding is not fixed, and it is live today

Severity: critical
File: `.github/scripts/assert_no_db_skips.py` lines 64 to 71, `_DB_SKIP_MARKERS`
Reachable: NOW, at this commit, with no change by anybody

`tests/system_03_search_agent/adapters/web_sse/test_phase_4_10_premise.py` line 223 carries a module-level skipif whose reason is:

```
user database unreachable at {USER_DB_URL}; the guest allowance is a server-side count
```

That phrase contains none of the six markers. The file is not marked `integration` and is not gated behind `RUN_PREMISE_GATE`, so it runs inside gate 4. It holds 35 test functions covering the anonymous run path and the guest allowance, which is the surface every unauthenticated visitor to the live product touches.

What I did, and what came back:

```
$ USER_DB_URL="postgresql://postgres:postgres@127.0.0.1:65432/search_agent_users" \
  ./venv/bin/python -m pytest tests/system_03_search_agent/adapters/web_sse/test_phase_4_10_premise.py \
  -q -rs --junitxml=/tmp/adv414/live-dead-db.xml
SKIPPED [1] .../test_phase_4_10_premise.py:1914: user database unreachable at postgresql://postgres:postgres@127.0.0.1:65432/search_agent_users; the guest allowance is a server-side count
...
36 skipped, 2 warnings in 3.19s

$ ./venv/bin/python .github/scripts/assert_no_db_skips.py /tmp/adv414/live-dead-db.xml
ok: 36 skipped test(s) in the report, none of them for a database reason.
SCRIPT EXIT CODE: 0
```

Why it matters: this is verbatim the scenario F-4.14-03 describes, run against the script written to catch it, and the script certifies the opposite of the truth. If the PostgreSQL service block is misconfigured, unhealthy, or reachable-but-wrong, gate 4 goes green and 36 guest-allowance tests are gone. The commit message states the script was "proven in BOTH directions". It was proven in both directions against one phrasing.

To be precise about the blast radius today: the tests in `auth/`, `feedback/`, `data/` and `harness/` do all match, via the `user_db_url` and `database is not reachable` markers. The 4.10 premise file is the one that does not, and nothing in the phase enumerated the set.

### F-4.14-A-02: the marker list is the enumerate-the-instances shape its own docstring disclaims

Severity: critical
File: `.github/scripts/assert_no_db_skips.py` lines 56 to 71

Lines 58 to 63 state that substrings rather than exact strings were chosen so the check "stays quiet about the skips that are supposed to be there and loud about the ones that are not", and that an exact-match list "would be the enumerate-the-instances shape `bossman-mode`'s Rule 2 rejects". A list of six substrings is still an enumeration of six instances. It fails the same way, one wording later.

I wrote six database skips in six phrasings a developer would plausibly write, none of them contrived:

```
$ cat /tmp/adv414/test_dbskips.py    # six tests, six reasons
    "requires a running database"
    "PostgreSQL is not available"
    "no database configured for this environment"
    "connection refused on 127.0.0.1:5432"
    "db not reachable"
    "needs postgres"

$ ./venv/bin/python -m pytest /tmp/adv414/test_dbskips.py -q -rs --junitxml=/tmp/adv414/unit-results.xml
6 skipped in 0.01s

$ ./venv/bin/python .github/scripts/assert_no_db_skips.py /tmp/adv414/unit-results.xml
ok: 6 skipped test(s) in the report, none of them for a database reason.
SCRIPT EXIT CODE: 0
```

Six of six. Note that `postgres is not running` and `postgresql is not running` are markers, while `PostgreSQL is not available` and `PostgreSQL is not reachable` are not, and one of the repository's own existing files already writes `PostgreSQL is not reachable` (it survives only because the same sentence happens to also say `USER_DB_URL`).

Why it matters: every future build phase that adds a database-backed test is one wording away from reopening F-4.14-03, and nothing will say so. The property the gate wants is "this test stood down because a dependency was absent", which the JUnit report cannot express directly, so an enumeration is doing work a structural signal should do (a registered marker, a shared `requires_db` helper with one canonical reason string, or an assertion on the count of tests that ran in the database-backed directories).

### F-4.14-A-03: gate 5 renders a green check and cannot ever have run

Severity: critical
File: `.github/workflows/ci.yml` lines 204 to 228

The escape hatch is `if [ -z "$GRAPH_QUERY_URL" ] && [ -z "$GRAPH_PG_HOST" ]`. That branch is honest: it prints NOT RUN and raises a `::warning`. The problem is the other branch. With the credential present but pointing anywhere that does not answer, the suite's own arms skip and `pytest` exits 0 with no warning at all.

```
$ cat /tmp/adv414/gate5.sh     # ci.yml lines 209-228 verbatim, GRAPH_QUERY_URL set to https://127.0.0.1:9/cypher
$ /tmp/adv414/gate5.sh
credential present -> the not-run branch is skipped, the suite runs:
SKIPPED [1] .../test_cypher_query_e2e.py:678: live graph unavailable: RUN_PREMISE_GATE is not set, so tests/conftest.py is blocking outbound HTTP and these arms cannot reach the graph service whether or not it is up
... (10 more of the same)
SKIPPED [1] .../test_graph_connection.py:539: GRAPH_PG_HOST is not set, or :15432 is not reachable ...
23 skipped, 4133 deselected, 2 warnings in 3.57s
GATE 5 STEP EXIT CODE: 0
```

Zero passed. Twenty-three skipped. Exit 0. On GitHub that is an ordinary green check named "Integration suite (5)".

The second half is worse than a misconfiguration, because it is structural. `tests/conftest.py` blocks outbound HTTP unless `RUN_PREMISE_GATE` is set. The workflow never sets it, and says so deliberately at line 86: "RUN_PREMISE_GATE stays unset so the 136 live arms stay out." So the moment somebody adds the `GRAPH_QUERY_URL` secret in the belief that gate 5 will start verifying something, gate 5 will report green having verified nothing, permanently, with the not-run warning switched off by the very act of adding the credential.

```
$ grep -n "RUN_PREMISE_GATE" .github/workflows/ci.yml
86:      # provider, and RUN_PREMISE_GATE stays unset so the 136 live arms stay out.
```

Why it matters: gate 5 is the one gate where the phase reasoned explicitly about the difference between "passed" and "could not run", wrote a warning annotation for it, and wrote a premise arm (P15) to defend it. P15 checks that the string `::warning` appears in the run body. It does not check that the warning fires on the path that actually occurs. This is the safety-by-proxy shape build phase 4.3 shipped as a critical twice and build phase 4.7 repeated: the arm verifies a correlate of the property.

Adding a credential should make a gate stricter. Here it makes it silent.

### F-4.14-A-04: nothing makes any of these gates merge-blocking

Severity: critical
File: the phase as a whole. `tracker/phase_4.14.md`, goal contract and coverage statement

Section 24's table marks all ten gates `Blocking: Yes`. The deliverable is described throughout as "Section 24's ten merge-blocking gates". A GitHub Actions workflow does not block anything. Required status checks under branch protection do, and nothing in this phase configures, documents, or even mentions configuring them.

```
$ grep -rn "required_status_checks|branch protection|required check" .github requirements/Technical_specification.md
.github/workflows/ci.yml:300:      # request, and a required check that vanishes is indistinguishable from one
```

That single hit is a comment about a different subject. And on this repository the block cannot be configured at all right now:

```
$ gh repo view --json isPrivate,visibility
{"isPrivate":true,"name":"agentic-search-ui","visibility":"PRIVATE"}

$ gh api repos/monideep2255/agentic-search-ui/branches/develop/protection
{"message":"Upgrade to GitHub Pro or make this repository public to enable this feature.","status":"403"}
```

Why it matters: this is the largest gap between what the phase claims and what exists. A red CI run on a private repository on this plan is a red mark next to a Merge button that still works. The phase's stated purpose is that "the only thing between a bad commit and the demo is a person choosing to run pytest"; after this phase the only thing between a bad commit and the demo is a person choosing to look at a check mark. That is a real improvement and it is not the claim. Either the coverage statement should say so plainly, or the plan or visibility has to change.

### F-4.14-A-05: every gate body can be replaced by `true` with all sixteen premise arms green

Severity: high
File: `tests/ci/test_ci_workflow_premise.py`, whole file

The premise gate reads step NAMES to find gates, and then greps a handful of substrings out of `run:` bodies. It never asserts that a gate runs the command Section 24 names. Gates 1, 3, 4, 7 and 10 have no content assertion of any kind. The substring arms that do exist (P3, P7, P9, P15, and the `assert_no_db_skips.py` half of P5) match text anywhere in the body, including inside a `#` comment, which is exactly the defect build phase 4.16 shipped.

I constructed the maximally gutted workflow: every gate body replaced with a no-op, every magic substring preserved inside a shell comment, the PostgreSQL assertion step reduced to a comment.

```
$ ./venv/bin/python  # calling the real arms against the mutated workflow dict
step_for(b,1)["run"]  = "true"
step_for(b,2)["run"]  = "isort --check-only --diff --skip-glob=* src tests services tracker alembic .claude"
step_for(b,3)["run"]  = "true"
step_for(b,4)["run"]  = "true"
step_for(b,5)["run"]  = "# exit 0 ::warning NOT RUN\ntrue"
step_for(b,6)["run"]  = "# pip-audit -r requirements.txt\ntrue"
step_for(b,7)["run"]  = "true"
step_for(b,8)["run"]  = "# npm run build\ntrue"
step_for(b,9)["run"]  = "# pytest .../test_required_paths.py\n# .github/scripts/assert_required_paths_ran.py\ntrue"
step_for(b,10)["run"] = "# npx playwright test e2e/accessibility.spec.ts\ntrue"
# and the assert_no_db_skips step -> "# .github/scripts/assert_no_db_skips.py unit-results.xml\ntrue"

PREMISE ARMS RED: 0 of 16 -> []
```

Zero of sixteen. On a first pass, with the comments written naively, it was 1 of 16 red: only P7 resisted, and only because it tokenises the isort line and requires every non-flag token to be a real path. P7 filters out anything starting with `-` by design, so one flag defeats it while leaving every path in place:

```
$ ./run.sh
--- baseline: the file IS mis-sorted ---
exit=1
--- identical path list, one extra flag that P7 filters out by design ---
Skipped 1 files
exit=0
```

Why it matters: `tracker/phase_4.14.md`'s coverage statement says "each mutation-proven", and the goal contract says "every gate has been mutation-proven to go red when the thing it exists to catch is broken". Neither is true for gates 1, 3, 4, 5, 7 or 10, whose bodies no arm and no mutation ever reads. The mutation harness is well built for what it covers: all 16 arms have a mutation and there is a real control. What it covers is the arms, not the gates. A reader of the board will believe otherwise.

The practical version of this, not the adversarial one: someone speeding up CI writes `pytest -m "not integration" -q --junitxml=unit-results.xml -x --ignore=tests/system_03_search_agent` and nothing in the 49-test suite notices.

### F-4.14-A-06: gate 9's required-path check is satisfied by tests about a blue border

Severity: high
File: `.github/scripts/assert_required_paths_ran.py` lines 56 to 61 and 126 to 130

`_REQUIRED_PATHS` matches substrings including `"citation"` and `"refus"` against test NAMES, and the check is `any(marker in name for marker in markers for name in names)`: any single test in the whole collected set satisfies a path. `_MINIMUM_CASES` is 2.

```
$ cat /tmp/adv414/g9/test_required_paths.py
def test_the_citation_widget_renders_a_blue_border():
    assert True

def test_the_settings_page_refuses_to_scroll_horizontally():
    assert True

$ ./venv/bin/python -m pytest /tmp/adv414/g9/test_required_paths.py -q --no-header -p no:cacheprovider -rs --junitxml=.../required-paths.xml
2 passed in 0.01s

$ ./venv/bin/python .github/scripts/assert_required_paths_ran.py .../required-paths.xml
ok: 2 required-path tests ran, none skipped, both paths covered.
SCRIPT EXIT CODE: 0
```

Two `assert True` bodies, one about CSS and one about scrolling, and the gate that `production-standards` calls "the single highest-leverage correctness gate in this system" says both paths are covered.

The realistic version does not require anyone to write that file. In the real target, `test_citation_id_is_stable_across_renumbering` (line 384, about marker renumbering) satisfies the cite-or-refuse path all on its own. Delete every genuine grounding test and keep that one, and the gate stays green.

Why it matters: the docstring correctly diagnoses that pytest exits 0 on an empty collection, then fixes only that. It asserts tests ran, none skipped, none failed, and that some test name contains one of eight substrings. None of those is the property. The property is that the cite-or-refuse and zero-retrieval behaviours are still exercised, and a name is not evidence of behaviour. A structural signal exists and was not used: pytest markers, or asserting a minimum count per path against the count measured at this commit.

### F-4.14-A-07: gate 10's filter fails open, and prints a false statement when it does

Severity: high
File: `.github/workflows/ci.yml` lines 302 to 325

```bash
if git diff --name-only "$base" "$head" | grep -qE '^frontend/'; then
  echo "touched=true" >> "$GITHUB_OUTPUT"
else
  echo "touched=false" >> "$GITHUB_OUTPUT"
  echo "No file under \`frontend/\` changed in this pull request." >> "$GITHUB_STEP_SUMMARY"
fi
```

The pipeline's exit status is grep's. If `git diff` fails for any reason, it writes to stderr, emits nothing on stdout, grep exits 1, and control falls to the else branch. `set -e` does not help: a failing command inside an `if` condition is explicitly exempt from errexit, and GitHub's default shell for `run:` on Linux is `bash -e {0}`, not `-eo pipefail`, so the git failure inside a pipeline is invisible twice over.

I reproduced it against real git repositories, with a pull request that changes two files under `frontend/`:

```
$ ./sim.sh
### Case 1: full history (fetch-depth: 0) -- the intended path
  touched=true   -> gate 10 RUNS
  step exit code: 0

### Case 2: SAME pull request, shallow clone (fetch-depth line removed)
fatal: bad object ef78abcb9ebb297518b5b5038f39d32767b53e5e
  touched=false  -> gate 10 SKIPPED
  step summary:  'No file under `frontend/` changed in this pull request.'
  step exit code: 0

### Case 3: base SHA garbage-collected / force-pushed away
fatal: bad object 0000000000000000000000000000000000000000
  touched=false  -> gate 10 SKIPPED
  step summary:  'No file under `frontend/` changed in this pull request.'
  step exit code: 0
```

The gate does not merely skip. It reports, in the step summary a reviewer reads, that no frontend file changed, on a pull request that changed two.

The only thing holding this shut is `fetch-depth: 0` on line 295, and nothing guards it:

```
$ grep -n "fetch-depth|filter|touched|git diff" tests/ci/*.py
  (no match: nothing in the 49-test gate suite mentions them)
```

Why it matters: `fetch-depth: 0` on a repository this size is a slow full-history fetch and is the most obvious thing to remove in a "speed up CI" commit. Doing so silently disables the WCAG 2.1 AA gate on every pull request while printing a reassuring, false line. The comment at lines 298 to 301 argues that computing the filter in-job rather than with `on.paths` is safer because "a required check that vanishes is indistinguishable from one that passed". The in-job version reintroduces the same ambiguity one layer down: a job that reports green having decided not to look.

The fix is one line, `|| { echo "touched=true"; }` on the git failure, or splitting the diff out of the condition and checking its exit status. Fail toward running the gate.

### F-4.14-A-08: neither assertion script has a single test

Severity: high
Files: `.github/scripts/assert_no_db_skips.py`, `.github/scripts/assert_required_paths_ran.py`

These two scripts are the only new executable logic the phase produced. Everything else is configuration. They are the pieces on which gate 4 and gate 9 depend for meaning. Across `tests/ci/` and the whole repository, nothing invokes either one with any input:

```
$ grep -rn "assert_no_db_skips|assert_required_paths_ran" --include="*.py" . | grep -v "^./.github/scripts/"
tests/ci/test_ci_workflow_premise.py:290:    assert "assert_no_db_skips.py" in step_bodies, (
tests/ci/test_ci_workflow_mutation.py:154:        step for step in job["steps"] if "assert_no_db_skips.py" not in ...
tests/ci/test_ci_workflow_mutation.py:236:        "assert_required_paths_ran.py", "assert_nothing_at_all.py"
```

All three are substring checks on the workflow text. Not one feeds either script a JUnit report.

Why it matters: this is the root cause of A-01, A-02, A-06 and A-11. A single parametrised test over a handful of hand-written JUnit fixtures, one per marker plus a few near-misses, would have found A-01 in the time it takes to write it. The phase built a careful mutation harness for the configuration file and none at all for the code.

### F-4.14-A-09: the `alembic` premise that justified disabling ruff `I001` is overstated by a factor of ten

Severity: medium
Files: `pyproject.toml`, `[tool.ruff.lint] ignore = ["I001"]` and the comment block above it

The argument in `pyproject.toml` and in the commit message is that ruff and isort disagree on 23 files, each fix re-breaks the other, so one gate would be red permanently, and therefore `I001` is turned off repository-wide. The largest cause is named correctly: ruff sees a root directory called `alembic/` and classifies `from alembic import op` as first-party.

The diagnosis is right. The conclusion does not follow, because ruff has a setting for exactly this and it was not tried.

```
$ ./venv/bin/ruff --version
ruff 0.16.0

$ ./venv/bin/ruff check --no-cache --select I001 --statistics
23	I001	[*] unsorted-imports

$ ./venv/bin/ruff check --no-cache --select I001 --config 'lint.isort.known-third-party = ["alembic"]' --output-format=concise | wc -l
       4          # i.e. 2 findings + 2 summary lines

$ ./venv/bin/ruff check --no-cache --select I001 --config 'lint.isort.known-third-party = ["alembic"]' --output-format=concise
src/system_03_search_agent/adapters/web_sse/app.py:3:1: I001 Import block is un-sorted or un-formatted
src/system_03_search_agent/core/graph.py:444:1: I001 Import block is un-sorted or un-formatted
```

Twenty-three becomes two with one configuration line. The two survivors are genuine style disagreements about aliased and parenthesised imports, and they are two files, so the scoped remedy reaches zero:

```
$ ./venv/bin/ruff check --no-cache --select I001 \
    --config 'lint.isort.known-third-party = ["alembic"]' \
    --config 'lint.per-file-ignores = {"src/.../app.py" = ["I001"], "src/.../graph.py" = ["I001"]}'
All checks passed!
```

What the repository-wide ignore costs:

```
$ find src tests services tracker alembic -name '*.py' | wc -l
274
```

Why it matters: `goal-contracts` forbids weakening a verify surface to make it pass, and the pyproject comment anticipates the objection ("This does not leave import order unchecked, which would be weakening a gate. It moves the check to the tool Section 24 names for it"). That defence holds only if the two tools genuinely cannot coexist, and they can, on two files rather than 274. Gate 2's isort does still police import order, so this is not a hole so much as a decision whose stated premise does not survive measurement, and which was recorded in a commit message and a config comment as settled fact. P13 now locks the wrong conclusion in place: re-enabling `I001` correctly, with the third-party declaration, makes the premise gate go red.

### F-4.14-A-10: P12 and P13 match raw text, not configuration

Severity: medium
File: `tests/ci/test_ci_workflow_premise.py` lines 397 to 427

Both arms read `pyproject.toml` as a string and run a regex over it. `tomllib` has been in the standard library since 3.11 and this project targets 3.11.

```
P12 (ruff pinned exactly):
  GREEN  real file
  GREEN  unpinned, old value left in a COMMENT
         ("ruff>=0.16",  # was "ruff==0.16.0")

P13 (import order has exactly one owner):
  GREEN  real file
  GREEN  the ignore line COMMENTED OUT (ruff I001 live again)
         (# ignore = ["I001"]  -- re-enabled, see #123)
  GREEN  ignore moved to a table that does not exist
         ([tool.ruff.lint.typo-nobody-reads])
```

Why it matters: the second P13 case is the exact oscillation P13's own docstring says it exists to prevent. Someone re-enables ruff's import rules by commenting out one line, leaves a note saying why, and P13 certifies that import order still has exactly one owner while gate 2 and gate 3 start fighting. The third case is the likelier accident: a table rename or a refactor that moves the key somewhere ruff never reads.

The corresponding mutations (M17, M18, M19) all mutate by string replacement, which is why they pass: they delete the substring, so the substring check goes red. A mutation that moves the substring into a comment would have caught this, and is the mutation the phase's own build-phase-4.16 lesson calls for.

### F-4.14-A-11: `assert_no_db_skips.py` has no populate-check, unlike its sibling

Severity: medium
File: `.github/scripts/assert_no_db_skips.py` lines 130 to 157

`assert_required_paths_ran.py` has `_MINIMUM_CASES = 2` and refuses a report with too few testcases. Its sibling has nothing equivalent.

```
$ printf '<testsuites><testsuite name="pytest" tests="0" .../></testsuites>' > zero_cases.xml
$ ./venv/bin/python .github/scripts/assert_no_db_skips.py zero_cases.xml
ok: 0 skipped test(s) in the report, none of them for a database reason.
exit=0
```

Same result for a namespaced document, where `tree.iter("testcase")` matches nothing:

```
$ ./venv/bin/python .github/scripts/assert_no_db_skips.py namespaced.xml
ok: 0 skipped test(s) in the report, none of them for a database reason.
exit=0
```

Reachability, stated honestly: gate 4's `pytest` step runs first and exits non-zero on an empty collection, so today the preceding step catches this. The check is therefore protected by a neighbour rather than by itself, and the neighbour is one of the gate bodies nothing asserts (A-05). pytest does not emit namespaced JUnit, so the namespace case is not currently reachable at all; it is listed because it shows the same missing guard from a second direction.

The asymmetry is the finding: the premise gate file requires a populate-check on every arm, per build phase 4.11's durable fix, and the two scripts were written to a different standard than the tests that grade them.

### F-4.14-A-12: M20 verifies a correlate of the populate-check, not the populate-check

Severity: low
File: `tests/ci/test_ci_workflow_mutation.py` lines 363 to 380

M20's docstring says it "proves the populate-check itself works, which is the arm build phase 4.7 found could survive its own repair by verifying a correlate instead". What it actually asserts is that `parse_spec_gates` returns `[]` on two reworded inputs, and that the real document parses to ten. It never exercises the `spec_gates` fixture, which is where the populate-check lives, and never asserts that a run against a reworded specification goes red.

The populate-check does work; I read it and it fires. That is not the point. M20 is written in the shape it names as the failure mode, in the sentence that names it. If someone later changes the fixture from `assert len(rows) == EXPECTED_GATE_COUNT` to `if rows:`, M20 stays green.

The commit message's claim, "including a probe confirming the mutation harness itself catches a vacuous arm", rests on this test and overstates it.

### F-4.14-A-13: gate 1 is named for something it does not do

Severity: low
File: `.github/workflows/ci.yml` lines 116 to 117

```
$ # a file whose import cannot resolve
$ cat src/broken_import.py
import a_module_that_does_not_exist_anywhere
CONFIG = a_module_that_does_not_exist_anywhere.value

$ python -m compileall -q src
exit=0     # step is named "Gate 1: Python compiles and imports cleanly"
```

`compileall` is a syntax check. It byte-compiles and never executes a module, so no import is ever resolved. It does correctly go red on a syntax error (verified, exit 1). Section 24 itself names the gate "Python compiles and imports cleanly" and the tool `python -m py_compile`, which has the same property, so the specification carries the same gap.

Also worth noting: gate 1 compiles `src services tests alembic`, while gates 2 and 3 lint `src tests services tracker alembic .claude`. The `tracker/` and `.claude/` trees carry Python that gate 1 never compiles.

Low severity because gate 4 imports everything under `src/` in the course of running, so a genuinely broken import is caught one step later. The finding is the label, which invites a reader to believe an import check exists.

## Attacks that found nothing

Recorded so the next reader does not repeat them. This is real coverage and the phase should get credit for it.

| Attack | Result |
|--------|--------|
| Empty JUnit report to both scripts | Both fail closed, exit 1, with a clear message |
| Truncated JUnit report | Both fail closed, exit 1 |
| Missing report file | Both fail closed, exit 1, naming the path |
| Billion-laughs and any `<!ENTITY` declaration | Rejected before the parser sees the body, in both scripts, exit 1. The reasoning in the docstrings is correct about stdlib ElementTree |
| Namespaced JUnit against `assert_required_paths_ran.py` | Fails closed via `_MINIMUM_CASES` |
| Skipped or failed tests in gate 9's report | Both correctly detected and reported by name |
| Does any premise arm lack a mutation? | No. All 16 arms are covered: 11 in the parametrised control plus M1 to M21. The M0 control is real and does what it claims |
| Naive comment-substring attack on P7 (gate 2's paths) | Resisted. P7 requires every non-flag token to be an existing path, which defeats `#`, `:`, `exit 0`, `|| true` and `true` prefixes. A flag was needed instead (A-05) |
| Does `ruff check` with no path actually pass repository-wide today? | Yes. `All checks passed!` The claim in the commit message holds |
| Does `compileall` go red on a syntax error? | Yes, exit 1 |
| Does `npm test` hang in watch mode? | No. `frontend/package.json` defines `"test": "vitest run"` |
| Do gate 8's npm scripts exist? | Yes, `build` and `test` are both defined |
| Are the 49 gate tests currently green? | Yes, `49 passed in 0.07s`. Every finding above is a coverage gap, not an existing failure |
| Does `testpaths = ["tests"]` exclude `tests/ci`? | No, the gate suite is collected by gate 4 |
| Gate 5's empty-credential branch | Correct and honest. It prints NOT RUN, writes the step summary, and raises a `::warning` annotation. The defect is the other branch (A-03) |
| `permissions: contents: read` and secret handling | Correct. No `pull_request_target`, no secret reaches a fork, SHAs passed through `env:` rather than interpolated |
| Ordering across the four concurrent jobs | Not a defect. The premise gate's docstring and P2 both state the check is per-job, and no cross-job ordering is claimed. Gate 5 running beside gate 4 changes no verdict, since neither reads the other's output |

## Coverage of this report

What I did not attack, stated so a gap here is arguable too:

- I did not run the workflow on GitHub. Every reproduction above is the workflow's own shell and commands executed locally, which is the closest available proxy and is not the same thing. Whether the `postgres` service block is healthy on a real runner is unverified by me and by the phase.
- I did not run the full 4000-test suite, per instruction. Gate 4's real behaviour under a real CI-shaped database is taken from the commit message, not re-measured.
- I did not attack `frontend/e2e/accessibility.spec.ts` itself, only whether gate 10 reaches it.
- I did not attack the pull request template changes or the three `.claude/skills` script edits in the same commit.
- I did not test `npm audit --audit-level=high` or `pip-audit -r requirements.txt` for false-negative behaviour on a planted vulnerable dependency.
- Branch protection state (A-04) could not be read directly; the 403 is from GitHub refusing the endpoint on this plan, which is itself the evidence, but it does not rule out some other mechanism I cannot see.
