# Build phase 4.14 re-verification report

VERDICT: FAIL (F-4.14-RV-03, a critical inside the round-1 fix; stop-the-phase)

Fresh-context re-verification (round 2) of the round-1 fixes on `phase/4.14-ci-gates`.
Subject commits: `4ea0778` (original), `b2dfda5`, `8675147`, `36adf16`, `e2bc2ac`.

A SIXTH commit, `153ddca` ("stop two test files hardcoding the database DSN", F-4.14-CI-04's fix),
landed on the branch while this review was running. Every measurement below was taken at `e2bc2ac`
unless it names a CI run. I checked whether it invalidates anything and it does not: it changes
`tests/system_03_search_agent/data/test_models.py` and
`tests/system_03_search_agent/harness/test_cost_control.py` from a hardcoded DSN to
`os.environ.get("USER_DB_URL", ...)`, which can only turn silent skips into loud failures. The
dead-database measurement in Priority 1 would move in the direction of MORE unsanctioned failures,
never fewer, and cannot move a skip from unsanctioned to sanctioned. None of the nine findings
touches either file.
Re-verifier did not file the round-1 findings. Everything below is re-derived from
code and from commands run in this session. Written incrementally.



---

## Priority 1: `.github/scripts/assert_no_db_skips.py` (the deny-list to allowlist inversion)

### Both directions verified. Both hold.

RED on a dead database. Command run:

```
USER_DB_URL="postgresql://postgres:postgres@127.0.0.1:59999/nope" \
  ./venv/bin/python -m pytest -m "not integration" -q --junitxml=/tmp/rv_dead.xml -p no:randomly
```
```
55 failed, 3578 passed, 184 skipped, 23 deselected, 1 xfailed, 4 warnings, 25 errors in 87.94s
```
```
$ ./venv/bin/python .github/scripts/assert_no_db_skips.py /tmp/rv_dead.xml
FAIL: 51 test(s) skipped for a reason nothing sanctions. The gate cannot certify what it did not run.
...
51 of these mention a database. Check that the `postgres` service in .github/workflows/ci.yml is healthy...
EXIT=1
```

It catches the skip the round-1 adversary said the DENY-list version missed. Confirmed by
re-derivation, not by reading the claim:

```
tests.system_03_search_agent.adapters.web_sse.test_phase_4_10_premise.TestAdmitArm::...
  user database unreachable at postgresql://postgres:postgres@127.0.0.1:59999/nope;
  the guest allowance is a server-side count
```
That message contains none of the six phrasings the first version listed, and it is now caught.

Leak check, which was the specific risk the inversion creates. I re-ran the script's own
`classify()` and `sanctioned_reason()` over the dead-database report and cross-matched every
SANCTIONED skip against the script's own `_LIKELY_DATABASE` regex:

```
total 3843  unsanctioned 51
sanctioned {'the live premise-gate opt-in': 101,
            'a live Layer 1 graph or model credential CI does not hold': 32,
            'a known open finding, deliberately skipped and tracked': 1}
count of DB-mentioning sanctioned skips: 0
```

Every distinct sanctioned message was printed and inspected. The 32 admitted by the broad
`live graph|layer 1 graph|graph tunnel|graph service|real model key` pattern reduce to five
distinct messages, none of which is a database skip:

```
Layer 1 graph unreachable: open the tunnel and re-run
needs the Layer 1 graph tunnel, which cannot be opened from this environment (T-3.0-07)...
the premise gate needs the live graph AND a real model key, since its whole purpose is to exercise cross-layer...
the premise gate needs the live graph AND a real model key, since its whole purpose is to exercise generation...
the premise gate needs the live graph AND a real model key, since its whole purpose is to exercise synthesis...
```

So on today's suite the answer to "could a database skip match a sanctioned pattern and be
silently re-admitted" is measured NO, not asserted no. Two residual observations below.

### F-4.14-RV-01: MINOR. The allowlist is not conjunctive, so one future message re-admits a database skip

`.github/scripts/assert_no_db_skips.py:135-152` (`_SANCTIONED_SKIPS`), `:171-176`
(`sanctioned_reason`).

`sanctioned_reason` returns on the FIRST pattern that appears anywhere in the message. Nothing
requires that the message be ONLY about the sanctioned dependency. A skip message that names
both a sanctioned dependency and the database is admitted whole. Demonstrated:

```
>>> sanctioned_reason("search_agent_users PostgreSQL is not reachable, and the live graph is down")
'a live Layer 1 graph or model credential CI does not hold'
```

This is not hypothetical shaped: eight files in this repository already skip on a graph-or-model
condition, and several premise gates already need BOTH a database and a graph. The day one of them
words its message with both, the gate re-admits it and prints `ok`. The `_LIKELY_DATABASE` regex
that would have caught it is deliberately advisory only ("Matching this changes nothing about the
verdict") and never consulted on the sanctioned path.

The cheap durable fix, which I am not applying (I edit no file but this report): consult
`_LIKELY_DATABASE` on the sanctioned path too, and treat a message that matches BOTH as
unsanctioned. That makes the allowlist conjunctive without enumerating phrasings.

### F-4.14-RV-02: MINOR. `_MINIMUM_TESTCASES = 500` is defensible in direction, near-useless in magnitude

`.github/scripts/assert_no_db_skips.py:127`.

Measured: the report carries 3843 test cases. The floor is 500, i.e. 13% of reality. It catches
total collection collapse and nothing else. Concretely, EVERY database-backed test in this
repository disappearing at collection is about 500 cases; the floor would still see 3300+ and pass.
The docstring's stated purpose ("well above zero so a collection failure does [trip it]") is met
only for a whole-suite collection failure, not for a directory-scale one. It is arbitrary in the
weak sense: no measurement ties 500 to anything. A floor derived from the drift-checked figure
`tracker/check_doc_drift.py` already computes (4107) would be a real populate-check; 500 is a
smoke alarm in the next building. Not a blocker, and the direction is right.


---

## Priority 2: `command_text` and the mutation that no arm catches

### F-4.14-RV-03: CRITICAL. `command_text` strips only whitespace-preceded `#`, so eight of the ten gates can be neutralised with every arm green

**Regression of: the round-1 "a commented-out command still counts as a command" finding. This is a
stop-the-phase signal: the worst defect in this round sits INSIDE round 1's fix, in the exact shape
round 1 set out to close.**

`tests/ci/test_ci_workflow_premise.py:105-127` (`command_text`), specifically line 122:

```python
without_comment = re.sub(r"(?<!\S)#.*$", "", raw)
```

`command_text` was introduced by `b2dfda5`, the round-1 fix commit (confirmed:
`git log -S"def command_text"` returns `b2dfda5` and nothing earlier). It exists for exactly one
reason, quoted from its own docstring:

> A `run:` body of `true  # ruff check` contains the string "ruff check" and runs nothing at all.
> Every arm below matches against this rather than against the raw body, so a command preserved
> only in a comment does not count as a command.

The `(?<!\S)` lookbehind treats a `#` as a comment ONLY when it is at the start of a line or
preceded by whitespace. Bash does not agree. Bash starts a comment at any `#` that begins a word,
and `;`, `&&`, `||`, `(` and a newline all end a word. So `:;#ruff check` is, to bash, a no-op
followed by a comment, and to `command_text` it is executable text containing `ruff check`.

Proved directly:

```
$ ./venv/bin/python -c "import re; print(repr(re.sub(r'(?<!\S)#.*$','',':;#ruff check')))"
':;#ruff check'

$ bash -c ':;#ruff check' ; echo "exit=$?"
exit=0
```

Nothing ran. Exit 0. (Control: the same probe with `true;#echo SHOULD_NOT_PRINT` printed nothing,
so the `#` really is a comment to bash and not an argument.)

**The mutation no arm catches.** In a clean detached worktree of `HEAD`
(`git worktree add --detach /tmp/rv_wt2 HEAD`), baseline first:

```
$ pytest tests/ci -q -p no:randomly
97 passed in 0.38s
```

Then I rewrote EIGHT gate bodies to `:;#<the original command>`, gate 3 (lint), gate 4 (the whole
unit suite), gate 4-cont (`assert_no_db_skips.py`, this phase's own headline deliverable), gate 6
(pip-audit), gate 7 (npm audit), gate 8 (frontend build and tests), gate 9 (the never-skippable
required paths), gate 10 (WCAG). Every one of them now executes nothing. Result:

```
$ pytest tests/ci -q -p no:randomly
97 passed in 0.33s
```

All 97 arms green, including all of `tests/ci/test_ci_workflow_mutation.py`, the file whose entire
job is to prove these arms can fail. A CI configuration in which the lint gate, the entire test
suite, the database-skip proof, both dependency audits, the frontend build and the accessibility
gate all execute nothing is certified correct by this phase's premise gate.

Bash proof that the mutated gate-9 body is inert, run exactly as GitHub's default shell would
(`bash -e -o pipefail`):

```
$ bash -e -o pipefail -c ':;#pytest .../test_required_paths.py -q
:;#python .github/scripts/assert_required_paths_ran.py required-paths.xml'
exit=0
```

Gate 2 is the only body that resists, and it resists by accident: `test_p7` requires every non-flag
token in gate 2's command to be an existing path, and the token `:;#isort` is not one.

```
E            +  where False = exists()
E            +    where exists = (PosixPath('/private/tmp/rv_wt2') / ':;#isort').exists
tests/ci/test_ci_workflow_premise.py:547: AssertionError
```

No arm is checking for neutralisation. `test_p19_no_gate_is_neutralised`
(`tests/ci/test_ci_workflow_premise.py:322-368`) is the arm that should own this. It checks
`continue-on-error`, `if: false`, `|| true` and `set +e`, four named tricks, and misses the fifth.
That is the enumerate-the-instances shape that `.github/scripts/assert_no_db_skips.py`'s own
docstring, four files away in the same commit, correctly identifies as the losing move ("Every
attempt to fix that by adding a seventh phrasing loses to the eighth"). The lesson was applied to
the script and not to the gate that grades the workflow.

The durable fix is not a fifth named trick. It is to stop deciding what is executable with a
lookbehind: tokenize the `run:` body with `shlex` (which knows `#` and quoting), or at minimum
widen the lookbehind to something like `(?<![^\s;&|(])`. Whichever is chosen,
`tests/ci/test_ci_workflow_mutation.py` must gain an arm that applies exactly the `:;#`
substitution above and asserts it goes red, otherwise the fix to this finding is itself unverified.

### F-4.14-RV-04: MINOR. `command_text`'s documented "safe direction" is real, and it is the wrong half of the problem

`tests/ci/test_ci_workflow_premise.py:123-127`. The docstring claims naivety about `#` inside quotes
is "the safe direction: a stripped-too-much body makes an arm FAIL". Measured, it is true:

```
'echo "# not a comment"'  -> 'echo "# not a comment"'   (# preceded by ", kept, correct)
'curl https://x/y#frag'   -> 'curl https://x/y#frag'    (# preceded by y, kept, correct)
'echo "hello # world"'    -> 'echo "hello '             (# preceded by space, over-stripped, fails loudly)
```

So the two cases the docstring worried about (quoted `#`, URL fragment) are the two it gets RIGHT,
and the case it never considered (`;#`) is the one that breaks the file. I record this because the
reasoning in that docstring reads as thorough and is the reason nobody looked further. Per this
repository's own `self-eval-loop` rule: a comment that asserts a safety property is a claim to be
tested, not documentation.

---

## Priority 3: import order, and lead correction #1

### Lead correction #1 is CORRECT. The round-1 judge was wrong.

The lead claims ruff's `I001` WAS enabled before this phase and that
`ignore = ["I001"]` at `4ea0778` was NOT a no-op. Verified by experiment, not by reading.

The judge's position is the one most people would hold: ruff's classic default `select` is
`["E4","E7","E9","F"]`, which contains no `I`, so ignoring `I001` without selecting `I` does
nothing. That is false for the ruff this repository pins. `ruff 0.16.0` ships a broad default rule
set. Probe, with a `pyproject.toml` containing nothing but `[tool.ruff]` / `line-length = 100`:

```
$ ruff check pkg/ble.py --no-cache
S110 `try`-`except`-`pass` detected, consider logging the exception
```

`S110` is flake8-bandit and is nowhere near the classic default set. (Corroborating evidence in
this repository's own source, independent of my probe: `harness/harness.py` carries
`# noqa: BLE001, S112`, which would be pointless if those rules were off.)

The decisive measurement, on a real checkout of `4ea0778` in a detached worktree:

```
# pyproject.toml exactly as 4ea0778 had it, i.e. [tool.ruff.lint] ignore = ["I001"]
$ ruff check --no-cache
All checks passed!

# the same tree, the same commit, with ONLY the `ignore = ["I001"]` line deleted
$ ruff check --no-cache --statistics
21	I001	[*] unsorted-imports
Found 21 errors.
```

21 real errors were being suppressed. The ignore was load-bearing. The lead is right and the
round-1 judge's premise was wrong. I record this plainly because the correction was contested.

### Current state: both tools clean

```
$ ./venv/bin/ruff check --no-cache
All checks passed!

$ ./venv/bin/isort --check-only src tests services tracker alembic .claude
Skipped 2 files
isort exit=0
```

`[tool.ruff.lint]` now carries no `ignore` key at all; `known-third-party = ["alembic"]` is present;
`extend_skip` names the two files, both of which exist.

### F-4.14-RV-05: MAJOR. `test_p13` does not defend the property it says it defends: a file can still be checked by NEITHER tool

`tests/ci/test_ci_workflow_premise.py:625-660` (`test_p13_import_order_is_checked_by_at_least_one_tool_everywhere`).

Its docstring: *"what this arm defends is the real property: no file is skipped by BOTH."* It does
not. It checks exactly one way of disabling `I001`, the `ignore` list, and ruff offers several
others. The cheapest is `per-file-ignores`, and it composes with `extend_skip` to hit precisely the
two files isort already skips.

Demonstrated in the detached worktree. Mutation applied to `pyproject.toml`:

```toml
[tool.ruff.lint.per-file-ignores]
"src/system_03_search_agent/core/graph.py" = ["I001"]
"src/system_03_search_agent/adapters/web_sse/app.py" = ["I001"]
```

The premise gate does not notice:

```
$ pytest tests/ci -q -p no:randomly
97 passed in 0.32s
```

And the property really is gone. I then inserted a blatantly unsorted, fully-used import block into
`src/system_03_search_agent/core/graph.py`:

```
import zipfile
import abc
import json
_unused = (zipfile, abc, json)
```

Both gates stay green:

```
$ ruff check --no-cache src/system_03_search_agent/core/graph.py
All checks passed!
$ isort --check-only src tests services tracker alembic .claude
Skipped 2 files
isort exit=0
$ pytest tests/ci -q -p no:randomly
97 passed
```

Control, which is what makes this a finding rather than a guess, delete only the two
`per-file-ignores` lines, change nothing else:

```
$ ruff check --no-cache --statistics src/system_03_search_agent/core/graph.py
1	I001	[*] unsorted-imports
Found 1 error.
```

So the file WAS I001-dirty the whole time and `per-file-ignores` was the only thing hiding it.

Two further routes to the same gap, same shape, not separately demonstrated:
`[tool.ruff] exclude` / `extend-exclude` naming an isort-skipped file, and a narrowing
`[tool.ruff.lint] select` that omits `I` (`ignore` stays empty, so the arm's assertion still passes).

The arm can only defend the stated property by computing it: for each path in
`isort`'s `extend_skip`, run ruff on that path and assert `I001` is actually enforced there, for
instance by asserting the path appears in `ruff check --show-settings`'s enabled rules for that
file, or simply by asserting no `per-file-ignores`, `exclude` or narrowing `select` touches it.
Asserting the absence of one spelling of "off" is the enumerate-the-instances shape again.

### F-4.14-RV-06: MINOR. Gate 2's path list omits `.github`, so `.github/scripts/*.py` rests on ruff alone

`.github/workflows/ci.yml:173` runs `isort --check-only --diff src tests services tracker alembic .claude`.
`.github/scripts/` holds three Python files this phase created, and it is not in that list. They are
covered today only because gate 3 is `ruff check` with no path. Not a defect on its own, but it is
the coupling that makes F-4.14-RV-05 worse than it looks: narrowing ruff's `I` rules would take
this phase's own scripts unchecked along with the two `extend_skip` files. `test_p7` asserts gate 2's
paths exist; nothing asserts they are sufficient.

---

## Priority 4: `e2bc2ac`, the barrier fix. VERIFIED SOUND, with one recorded caveat

`tests/system_03_search_agent/core/test_cq_routing_mutation.py:481-501`.

Stability: 10 consecutive runs of the whole file, no instability.

```
run 1: 43 passed in 3.18s      run 6:  43 passed in 3.22s
run 2: 43 passed in 2.75s      run 7:  43 passed in 2.53s
run 3: 43 passed in 2.48s      run 8:  43 passed in 3.19s
run 4: 43 passed in 2.48s      run 9:  43 passed in 3.91s
run 5: 43 passed in 2.63s      run 10: 43 passed in 2.60s
```

`--durations=3` never once named `test_p11_*`, so the 5-second barrier timeout was not being paid
in any run. No deadlock, no hang, no broken barrier leaking into a sibling.

Does it force the interleaving it claims, or merely happen to work here? It forces it, and the
mechanism is sound by construction rather than by timing. Both threads execute `read_text` and
`document["examples"].append(entry)` BEFORE `read_barrier.wait()`, so both necessarily hold a copy
of the same original document when the barrier releases; whichever `os.replace` lands second
overwrites the other's entry. That is hardware-independent. I confirmed the barrier really pairs
(rather than timing out and falling through) by instrumenting a worktree copy:

```
RV-PROBE: barrier paired
RV-PROBE: barrier paired
1 passed, 42 deselected in 2.12s
```

Exactly two pairings, zero breaks.

Sibling contamination: none possible. `read_barrier` is a function-local, the mutated
`append_example` is installed with `monkeypatch.setattr` and reverted at teardown, and both
`Barrier.wait` calls carry a 5s timeout against a `thread.join(timeout=10)`, so the worst case is
bounded well inside the join.

### F-4.14-RV-07: MINOR. The barrier fix's own justification is factually wrong, and its safety net silently restores the flaky behaviour

The comment says the timeout exists because "a single-threaded caller (which is how
`_assert_arm_is_falsifiable` runs the arm clean) does not hang". That is not what happens.
`_assert_arm_is_falsifiable` (`:243-268`) runs the arm clean BEFORE calling `mutate()`, so the clean
run uses the real, locked `few_shot_pool.append_example` and never enters `_unlocked_append` at all.
My probe confirms it: two prints, both from the mutated run, none from the clean one.

So `except threading.BrokenBarrierError: pass` guards a case that does not occur, and what it
actually does is absorb, with no signal, any failure of the two writers to pair up, at which point
the mutation silently degrades back to exactly the nondeterministic behaviour that produced
F-4.14-CI-03 in the first place. The fix would be strictly better with the timeout raised or the
fallback made loud (`pytest.fail` on a broken barrier), since a genuinely single-threaded caller
does not exist on this path. Filed as MINOR because the current behaviour is correct on every run
I measured; the concern is that its failure mode is invisible.

---

## Priority 5: gate 5. No money, no live NCBI, propagation correct, and NEVER EXERCISED

Money and live-network risk: **none, measured.** `-m integration` selects 23 tests, and every one of
them is in `tests/system_03_search_agent/tools/test_cypher_query_e2e.py` or
`test_graph_connection.py`. No model call, no NCBI endpoint:

```
$ pytest -m integration --collect-only -q
23/4204 tests collected (4181 deselected)
```

`RUN_PREMISE_GATE=1` does lift `tests/conftest.py`'s session-wide outbound-HTTP block
(`_premise_gate_is_active`, `:88-90`), which is a real widening, but the marker filter, not the
block, is what bounds this job, and the gate-5 job sets no `OPENROUTER_API_KEY`, no `GUARD_MODEL`,
`PLAN_MODEL` or `SYNTH_MODEL`, and no `NCBI_API_KEY`. A model call could not be constructed even if
one were reachable.

I also checked the worry that gate 5's job omits the cost-cap variables that F-4.14-CI-02 showed
the suite RAISES without. Simulated in the detached worktree, which has no `.env` (so it is a real
runner-shaped environment), with exactly gate 5's env and nothing else:

```
$ env -i PATH=... HOME=... GRAPH_QUERY_URL=... GRAPH_QUERY_TOKEN=x GRAPH_PG_HOST= RUN_PREMISE_GATE=1 \
    pytest -m integration -q --collect-only
23/4204 tests collected (4181 deselected) in 14.36s
```

Collection succeeds. The concern is disproved.

Shell propagation: correct in both directions. GitHub's default `run` shell is
`bash --noprofile --norc -e -o pipefail`, and `set -uo pipefail` does not clear `-e`. I ran the
gate's exact control flow both ways with a failing stand-in for pytest:

```
with    -e : exit=1   (aborts at the pytest line; the assert line is never reached)
without -e : exit=1   (status captured, assert runs, `exit "$status"` fires)
```

Under `-e` the `status=$?` / `assert_status=$?` dance is unreachable dead code and
`assert_gate_ran.py`'s diagnostic never prints on a pytest failure, but the verdict is right either
way. Not a finding; recorded so the next reader does not assume the dance is doing work.

### F-4.14-RV-08: MAJOR. Gate 5's strict path has never executed, so the fix for F-4.14-A-03 ships unverified and renders as a green check

CI evidence from PR #68, run 33012234446, job "Integration suite (5)":

```
  GRAPH_QUERY_URL:
  GRAPH_QUERY_TOKEN:
  GRAPH_PG_HOST:
  RUN_PREMISE_GATE: 1
##[warning]The integration suite did not run: no graph credential is available to this
           context. It is not passing, it is unverified.
```

and `gh pr checks 68` reports:

```
Integration suite (5)	pass	42s
```

The not-run branch is the only branch that has ever run. `pytest -m integration`,
`assert_gate_ran.py`, and the `status`/`assert_status` propagation are all untested on a runner.
The warning annotation is real and is the honest half; the dishonest half is that the check still
reads `pass` in the checks list, which is the exact "green check that means could not run"
confusion the workflow's own comment (`.github/workflows/ci.yml:276-280`) says it exists to remove.
The comment acknowledges this and accepts it. I record it as MAJOR rather than accept it, because
combined with F-4.14-A-04 (nothing is merge-blocking, OPEN) gate 5 currently contributes no signal
at all, and the code that would give it signal has never been executed anywhere.

---

## Priority 6: the CI env block in `36adf16`. CLEAN

No real credential reached a committed file. I extracted all 30 variables from the working-tree
`.env`, took every value of length >= 16 that is not a local DSN, and searched the whole committed
tree for each:

```
.env variable count: 30
CI placeholder values colliding with a real .env value: none
real .env secret values present in committed files:
   LANGSMITH_PROJECT, GUARD_MODEL, PLAN_MODEL, POSTHOG_HOST, GRAPH_QUERY_URL
```

Every one of those five is a non-secret: a project name, three model/tier identifiers already
public in `DECISIONS.md` and `src/system_03_search_agent/harness/tiers.py`, and two hostnames.
`OPENROUTER_API_KEY`, `NCBI_API_KEY`, `LANGSMITH_API_KEY`, `POSTHOG_API_KEY`, `GRAPH_QUERY_TOKEN`
and `GRAPH_PG_PASSWORD` values appear in no committed file. The committed CI values
(`ci-placeholder-not-a-real-key`, `ci/placeholder-*`, `ci-not-a-real-secret-...`,
`ci@example.invalid`) collide with nothing real.

Can a gate make a real outbound model call with them? No, on two independent grounds, either of
which alone suffices: `tests/conftest.py` blocks the transport unless `RUN_PREMISE_GATE` is set, and
the python-gates job does not set it (proved by the CI log itself, which reports
`104 the live premise-gate opt-in` skips); and `ci/placeholder-guard` is not a resolvable provider
route, so a call would fail rather than bill.

Fourteen `.env` variables are still not provided to the python-gates job
(`NCBI_API_KEY`, `LANGSMITH_*`, `POSTHOG_*`, `GRAPH_*`, `PORT`, `BUILD_OPENROUTER_API_KEY`). CI is
green with them absent, so they are genuinely optional on this path. Noted, not a finding.

---

## Priority 7: `assert_required_paths_ran.py`

### F-4.14-RV-09: MAJOR. Gate 9 is satisfied by a file that tests nothing, because it checks two SYMBOL NAMES appearing anywhere in the source, including in prose

**Regression of: F-4.14-A-06.** That finding was "gate 9's assertion was satisfied by two
`assert True` tests named `test_the_citation_widget_renders_a_blue_border`...". The fix moved the
anchor from test NAMES to the module identity plus a source scan for `REFUSAL_TEXT` and
`ground_claim` (`.github/scripts/assert_required_paths_ran.py:49-52`, `:181-190`). The scan is
`if symbol not in source`, a plain substring test over the whole file, docstrings and comments
included. That is the safety-by-proxy shape: it measures a correlate of "this file exercises the
required paths" rather than the property.

Demonstrated in the detached worktree. I replaced
`tests/system_03_search_agent/synthesis/test_required_paths.py` entirely with:

```python
"""Gutted. Mentions REFUSAL_TEXT and ground_claim in prose only."""


def test_nothing_0() -> None:
    assert True
...   (16 of these)
```

Then ran gate 9 exactly as the workflow does:

```
$ pytest tests/system_03_search_agent/synthesis/test_required_paths.py -q --no-header \
    -p no:cacheprovider -rs --junitxml=/tmp/rv_req.xml
16 passed in 0.02s

$ python .github/scripts/assert_required_paths_ran.py /tmp/rv_req.xml
ok: 16 required-path tests ran from test_required_paths, none skipped, and the source
    still exercises both required paths.
assert exit=0
```

The gate prints "the source still exercises both required paths" about a file containing sixteen
`assert True` statements. And the premise gate does not notice either, `test_p4` requires only
`source.count("def test_") >= 2`:

```
$ pytest tests/ci -q -p no:randomly
97 passed
```

The `_MINIMUM_CASES = 15` floor is the only thing that made me write sixteen tests instead of two;
it costs an attacker one loop. A real check would import the module and assert the symbols are
actually REFERENCED (via `ast`), or assert the test bodies call `ground_claim`, not that the
characters appear somewhere in the file.

### `_module_source_path` and cwd: fails closed, no finding

`.github/scripts/assert_required_paths_ran.py:73-91` returns `Path(*parts).with_suffix(".py")`,
a RELATIVE path resolved against the process cwd. The workflow runs gate 9 from the repository root
with no `working-directory:`, so it resolves. If it ever did not (a `working-directory:` added, a
different pytest `rootdir` producing a shorter `classname`), the very next line is
`if source_path is None or not source_path.exists(): ... return 1`. It fails, loudly, in the safe
direction. Verified by reading, and corroborated by the real CI run, which printed
`ok: 27 required-path tests ran from test_required_paths`.

---

## Priority 8: CI on PR #68. All four jobs green, and gate 4's evidence is real

```
$ gh pr checks 68
Accessibility (10)               pass  35s
Frontend gates (7, 8)            pass  1m41s
Integration suite (5)            pass  42s
Python gates (1, 2, 3, 4, 6, 9)  pass  4m10s
```

No job failed, so there is no workflow-versus-code question to answer. The substantive result is
that this phase's headline deliverable demonstrably worked on a real runner, which no amount of
local measurement could have shown:

```
Gate 4:  4044 passed, 136 skipped, 23 deselected, 1 xfailed in 132.38s
Gate 4 (cont.): ok: 4181 test cases, every skip sanctioned
                (1 a known open finding, 32 a live Layer 1 graph or model credential
                 CI does not hold, 104 the live premise-gate opt-in)
Gate 9:  ok: 27 required-path tests ran from test_required_paths, none skipped
```

Zero failures with a live PostgreSQL service, and zero unsanctioned skips. That is the property
F-4.14-03 was filed about, and it holds. Note incidentally that 4181 collected against a floor of
500 is the measurement behind F-4.14-RV-02.

The one caveat is F-4.14-RV-08: "Integration suite (5) pass" is a not-run.

---

## The two lead corrections

### Correction #1 (ruff's `I001` was enabled; the ignore was not a no-op): the lead is RIGHT.

Measured above, in Priority 3. Deleting `ignore = ["I001"]` from `4ea0778`'s own `pyproject.toml`,
changing nothing else, turns `All checks passed!` into `21 I001 unsorted-imports`. The round-1
judge's premise (ruff's classic default `select` has no `I`) does not apply to `ruff 0.16.0`, which
ships a broad default set: a config containing only `line-length` flags `S110`, a bandit rule.
I set out to catch the lead being wrong twice and could not: this correction survives measurement.

### Correction #2 (F-4.14-03 was overstated; it measured one file and generalised): the lead is RIGHT.

`tracker/phase_4.14.md:129` claims the original finding's "an identical, confident green" is false,
and that a dead database instead produces "56 failed, 25 errors, and gate 4 goes RED", with the real
defect surviving as 51 silent skips. Independently re-measured, without seeing that number first:

```
55 failed, 3578 passed, 184 skipped, 23 deselected, 1 xfailed, 25 errors in 87.94s
...
FAIL: 51 test(s) skipped for a reason nothing sanctions.
```

25 errors exactly, 51 unsanctioned skips exactly, failures 55 against a claimed 56 (within
run-to-run variation on a suite this size; either way, non-zero and RED). Gate 4 does go red on a
dead database. The correction is accurate, including the narrower surviving form.

Both corrections stand. Recorded plainly, since the instruction was to say so if either were wrong
again, neither is.

---

## Round-1 findings: does the fix close it?

| ID | Round-1 claim | Closed? | How I checked | Residue |
|----|---------------|---------|---------------|---------|
| F-4.14-A-01 | The headline guard missed `test_phase_4_10_premise.py`'s "user database unreachable at ..." wording; 36 tests vanished, exit 0 | YES | Ran the whole suite against `127.0.0.1:59999`, then the guard on that report. Exit 1, and those exact arms are named in the failure list | None on this wording |
| F-4.14-A-02 | The six-phrasing marker list was enumerate-the-instances | YES, direction inverted | Cross-matched all 133 sanctioned skips against the script's own database regex: 0 overlap. 51 of 51 unsanctioned caught | F-4.14-RV-01: the allowlist is not conjunctive, so a message naming BOTH a sanctioned dependency and the database is admitted whole. Proved by calling `sanctioned_reason` directly |
| F-4.14-J-01 | The import-order decision was a gate turned off with a story attached | YES | `ruff check` and `isort --check-only` both clean on the same tree; `[tool.ruff.lint]` has no `ignore` key; `known-third-party = ["alembic"]` present | F-4.14-RV-05: `test_p13` defends only the `ignore` spelling. `per-file-ignores` on the two `extend_skip` files leaves them checked by NEITHER, all 97 arms green |
| F-4.14-J-02 | 16 mutations passed all 49 gate tests | NO, reopened | Re-ran the mutation class against the new arms | **F-4.14-RV-03, CRITICAL. `:;#<command>` neutralises 8 of 10 gates with 97/97 arms green. `command_text`, the round-1 fix, is where the hole is** |
| F-4.14-A-05 | Gate bodies replaced by `true` with the command in a comment left 15 of 16 arms green | PARTLY | The whitespace-preceded form is closed; the word-boundary form is not | Same as F-4.14-RV-03. This is the identical attack, one character of separator different |
| F-4.14-A-03 | Gate 5 with a credential present but unreachable: 0 passed, exit 0, green | CODE WRITTEN, NEVER EXERCISED | Read the CI log for gate 5 on run 33012234446 | F-4.14-RV-08: only the not-run branch has ever executed, and the check still reads `pass` |
| F-4.14-A-06 | Gate 9 satisfied by two `assert True` tests with plausible names | NO, reopened in a new shape | Replaced the required-path file with 16 `assert True` tests plus the two symbol names in the docstring | **F-4.14-RV-09, MAJOR. The gate prints "the source still exercises both required paths"** |
| F-4.14-A-07 | Gate 10's path filter failed OPEN | YES | Read the filter: three `touched=true` error paths, `git cat-file -e` guards, no `if git diff`. `test_p20` asserts all three | None found. Gate 10 ran and passed on CI |
| F-4.14-A-08 | Neither assertion script had a single test | YES | `tests/ci/test_assert_scripts.py` exists, 248 lines, part of the 97 | The tests do not cover F-4.14-RV-03, RV-05 or RV-09, which is how those survived |
| F-4.14-J-04 | P5's populate-checks were correlates (`redis:7` passed, `USER_DB_URL: ""` passed) | YES | Read `test_p5`: checks `image.startswith("postgres")` and `url.startswith("postgresql://")` | None |
| F-4.14-A-10 | P12/P13 matched raw text, so a commented-out pin satisfied them | YES | Both now go through `tomllib` | P13's other gap is F-4.14-RV-05, unrelated to this |
| F-4.14-A-11 | `assert_no_db_skips.py` had no populate-check | YES, weakly | `_MINIMUM_TESTCASES = 500`; measured 3843 local / 4181 on CI | F-4.14-RV-02: a floor at 13% of the real figure catches only total collapse |
| F-4.14-A-12 | M20 verified a correlate | Not re-derived |, | See "What I could NOT verify" |
| F-4.14-A-13 | Gate 1 never imported anything | YES | `.github/workflows/ci.yml:161-164` imports three entry points; gate 1 passed on CI | None |
| F-4.14-J-05 | Board committed at phase-open state | YES | `tracker/phase_4.14.md` carries evidence per ticket and a findings table | Tickets read `in-review`, correctly |
| F-4.14-J-06 | `check_doc_drift.py --check` red with 9 stale facts | Not re-run |, | See "What I could NOT verify" |
| F-4.14-A-04 | Nothing makes these gates merge-blocking | OPEN, correctly escalated | `gh pr checks 68` shows four checks and the PR is mergeable | Unchanged, and it compounds F-4.14-RV-08 |
| F-4.14-CI-01 | `pip install -e .` broken for the life of the project | YES | CI installed successfully on run 33012234446 | None |
| F-4.14-CI-02 | The job env block was missing most of what the suite needs | YES | Gate 4 on CI: 4044 passed, 0 failed | 14 `.env` variables still unset; CI green without them |
| F-4.14-CI-03 | P11 mutation nondeterministic, hardware-dependent | YES | 10/10 clean runs, barrier instrumented and proved to pair | F-4.14-RV-07: the fix's stated justification is wrong and its fallback is silent |
| F-4.14-CI-04 | `test_models.py` / `test_cost_control.py` hardcoded their DSN and skipped forever | YES | Against a dead `USER_DB_URL` they now ERROR loudly rather than skip (25 errors in my run, both files named) | None |

---

## What I could NOT verify

Stated as fails, not passes.

- **Whether the fix for F-4.14-RV-03 will hold**, because there is no fix yet. Any repair must be
  re-attacked, not read: the whole point of this finding is that the previous repair was read and
  believed.
- **F-4.14-A-12 (M20's populate-check) and F-4.14-J-06 (`check_doc_drift.py` staleness).** I ran out
  of budget before re-deriving either. I did NOT confirm the drift checker is currently green, and
  the phase's evidence for J-06 is "synced at phase checkpoint", which I did not test. Treat both
  rows as unverified rather than closed.
- **Whether gate 5's strict path works at all.** F-4.14-RV-08 says only that it has never run. I
  could not run it: this environment has no graph credential, and the graph service is the exact
  thing being credentialed. The failure mode if it is broken is a red gate, not a silent green, so
  the risk direction is acceptable, but "acceptable risk" is not "verified".
- **Gate 7 and gate 10's runtime behaviour under mutation.** I mutated their workflow bodies and
  showed the premise arms do not catch neutralisation (F-4.14-RV-03 covers both), but I did not run
  `npm audit`, `npm run build`, `npm test` or Playwright locally, so I cannot say what those gates
  do on a real failure, only that CI reported them green.
- **Whether ruff `0.16.0`'s broad default rule set is stable across the pin.** `ruff==0.16.0` is
  pinned exactly and `test_p12` enforces that, which is the right control. But my conclusion in
  correction #1 rests on that version's defaults; I did not check what a future ruff would do,
  and neither `select` nor `extend-select` is set anywhere, so the enabled rule set IS the version.
  `test_p12`'s own docstring says exactly this. It is a correct control over a fragile premise.
- **Anything about the frontend gates' content**, `.github/pull_request_template.md`, or
  `tests/ci/test_ci_workflow_mutation.py`'s 493 lines read line by line. I ran that file (it passes,
  including under the eight-gate neutralisation, which is itself the finding) but did not audit each
  of its arms individually.

---

## Verdict

FAIL.

One CRITICAL, F-4.14-RV-03, and it is inside `b2dfda5`, the round-1 fix commit, in the exact defect
class round 1 was convened to close. Under this repository's own Rule 4 that is a stop-the-phase
signal, not a finding to fix and continue past. Two MAJORs, F-4.14-RV-05 and F-4.14-RV-09, are each
a round-1 finding reopened in a shape one step sideways from the one that was closed
(F-4.14-J-01 and F-4.14-A-06 respectively), and a third, F-4.14-RV-08, is a fix that has never been
executed anywhere.

What is genuinely good, and should not be lost in the above: the allowlist inversion works and is
measured working on a real runner (4181 cases, every skip sanctioned, 4044 passed against a live
database); both of the lead's contested corrections survive independent measurement; the barrier fix
is sound and stable over 10 runs; and the first CI run in this repository's history found three real
defects (`pip install -e .` broken for the life of the project, a missing env block, and two test
files that could never have run in CI) that no amount of local review had found in twenty phases.
The phase's premise, that nothing was checking, is vindicated. Its verify surface is not yet.

The common shape across RV-01, RV-03, RV-05 and RV-09 is one thing, worth naming once:
each is a control that enumerates the ways a property can be violated instead of computing whether
the property holds. `assert_no_db_skips.py`'s docstring diagnoses this precisely and the diagnosis
was not carried across to the four controls in the same commit that needed it.
