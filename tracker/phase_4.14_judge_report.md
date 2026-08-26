# Build phase 4.14 judge report

VERDICT: FAIL

Reviewed: commit `4ea0778` on `phase/4.14-ci-gates`, 47 files. Every claim below carries either an exact `file:line` or pasted command output from this machine. Nothing was fixed; findings only.

The phase's product is good and the three findings it filed are real. It fails on three things: one recorded premise is false and was written into four durable artifacts as measured fact, the gate suite misses 16 of 16 independent mutations I wrote, and the phase's own board records none of the work it claims.

## Table of contents

- [Findings](#findings)
- [What I verified and how](#what-i-verified-and-how)
- [What I could NOT verify](#what-i-could-not-verify)
- [Premise check](#premise-check)
- [Note on the working tree at the time of this review](#note-on-the-working-tree-at-the-time-of-this-review)

## Findings

| ID | Severity | Where | What is wrong |
|----|----------|-------|---------------|
| F-4.14-J-01 | critical | `pyproject.toml:101-102`, `DECISIONS.md` 2026-08-26 row 1, `LEARNINGS.md` 2026-08-26 row 2, `tests/ci/test_ci_workflow_premise.py:414-427` | The import-order premise is false. Ruff never policed import order in this repository, `ignore = ["I001"]` is a no-op, and the arm that guards it verifies a correlate |
| F-4.14-J-02 | critical | `tests/ci/test_ci_workflow_premise.py`, `tests/ci/test_ci_workflow_mutation.py` | 16 of 16 independent mutations pass the whole 49-test gate suite, including making every gate non-blocking and re-scoping gate 3 back to the exact defect T-4.14-03 fixed |
| F-4.14-J-03 | major | `.github/scripts/assert_no_db_skips.py:64-71` | The durable half of F-4.14-03 misses 36 of 46 real database-caused skips, measured |
| F-4.14-J-04 | major | `tests/ci/test_ci_workflow_premise.py:279-287` | P5's two populate-checks are correlates: a `redis:7` service passes, and `USER_DB_URL: ""` passes |
| F-4.14-J-05 | major | `tracker/phase_4.14.md:70-81`, `tracker/BOARD.md:77` | The board is committed at its phase-open state. All ten tickets `todo`, zero evidence, and the goal contract's "recorded mutation run per gate" does not exist anywhere |
| F-4.14-J-06 | major | repository root, `tracker/check_doc_drift.py --check` | The repository's own drift gate is RED on this commit: 9 stale facts |
| F-4.14-J-07 | minor | `.github/scripts/assert_required_paths_ran.py:126-130` | Gate 9's "both paths covered" check is a name-substring correlate; a synthetic two-test report exercising neither path passes |
| F-4.14-J-08 | minor | `.github/workflows/ci.yml:116-117` | Gate 1 is named "Python compiles and imports cleanly"; `compileall` never imports anything |
| F-4.14-J-09 | minor | `pyproject.toml:58` | isort is pinned by floor while it is now the sole owner of import order. The exact argument used to pin ruff exactly was not applied to the tool that owns the property |
| F-4.14-J-10 | minor | `src/system_03_search_agent/adapters/web_sse/app.py:22` | The mechanical formatting pass mangled a three-line explanatory comment into a 184-character semicolon-joined line |
| F-4.14-J-11 | minor | `tracker/phase_4.14.md:91` vs `tracker/BOARD.md:96` | F-4.16-02 was declared out of scope by the lead while the board still assigns it to this phase. No product-owner decision is recorded |
| F-4.14-J-12 | minor | commit `4ea0778` message | Two counts in the commit message are wrong, and it claims to close a flag in a locked document it did not touch |

### F-4.14-J-01, critical. The import-order premise is false, and the arm guarding it checks a correlate

`pyproject.toml:81-102` states, and `DECISIONS.md`, `LEARNINGS.md` and the commit message all repeat as measured fact:

> "this repository's ruff rule set already enables the `I` rules, so both tools policed import order ... one of the two gates is red no matter what anyone commits, permanently."

Ruff's `I` rules are not enabled in this repository and never were. This repository sets no `select`, and `I` is not in ruff's default rule set. Measured:

```
$ ./venv/bin/ruff check --no-cache --show-settings | grep -c "unsorted-imports (I001)"
0

$ ./venv/bin/ruff check --no-cache --show-settings | sed -n '/linter.rules.enabled = \[/,/^]/p' | grep -oE "\(I[0-9]+\)" | sort -u
(nothing)
```

414 rules are enabled and not one of them is an `I` rule. So removing the new `ignore = ["I001"]` line changes nothing, which is the pre-commit configuration exactly:

```
$ ./venv/bin/ruff check --no-cache --config 'lint.ignore=[]' --output-format=concise
All checks passed!
```

`ignore = ["I001"]` at `pyproject.toml:102` is a no-op. Before this phase, ruff was not policing import order and isort was neither configured nor installed, so *neither* tool policed it. The 23-versus-26 oscillation the decision records was produced by running `ruff check --select I001`, which is not what gate 3 runs.

Second half, the "irreconcilable" claim. It is reconcilable, by one line, and the reconciliation is the option `DECISIONS.md` records as rejected for being "an unbounded ongoing tax":

```
$ ./venv/bin/ruff check --select I001 --no-cache --output-format=concise
Found 23 errors.

$ ./venv/bin/ruff check --select I001 --no-cache --output-format=concise \
    --config 'lint.isort.known-third-party=["alembic"]'
src/system_03_search_agent/adapters/web_sse/app.py:3:1: I001
src/system_03_search_agent/core/graph.py:444:1: I001
Found 2 errors.
```

21 of the 23 dissolve on one config key. A genuine oscillation does remain, and I confirmed it by experiment in a scratch copy (ruff's fix on those two files then fails `isort --check-only`), but it is two files over aliased-import splitting, not "23 files, each fix re-breaks the other, permanently red".

Third half, and this is the shape the brief asked me to hunt for. `tests/ci/test_ci_workflow_premise.py:414-427`:

```python
def test_p13_import_order_has_exactly_one_owner():
    """... If someone re-enables it, this fails and says why ..."""
    assert re.search(r'ignore\s*=\s*\[[^\]]*"I001"', pyproject), (
        "ruff's I001 is not ignored, so both ruff and isort police import order ..."
    )
```

The property is "only one tool polices import order". The arm checks that the literal string `I001` appears inside an ignore list. That string has no effect on ruff's behaviour here, so the arm verifies a correlate of a property that is not true in either direction. `test_m18_re_enabling_ruffs_import_rules_is_caught` mutates the same string in a temp file and proves only that the arm reads it.

Failure scenario: a future engineer adds `select = ["E", "F", "I"]` to get real lint coverage, hits the 23 errors, reads the pyproject comment and `DECISIONS.md`, and believes the conflict is unfixable. The one-line fix is right there and is documented as rejected.

Direction of the fix, per `goal-contracts`' "the check is wrong, fix the check and say so out loud": the outcome (isort owns gate 2) is defensible. The recorded reason for it is not, and it now lives in `pyproject.toml`, `DECISIONS.md`, `LEARNINGS.md` and the commit message.

### F-4.14-J-02, critical. 16 independent mutations, 16 missed

I wrote a mutation harness of my own that calls the real premise arms against a mutated workflow, with a control. Control first, so this is not an always-green instrument:

```
CONTROL red arms on the UNMUTATED workflow: []
```

Then 16 mutations. `CAUGHT` means at least one of the 14 workflow-reading premise arms went red:

```
*** MISSED *** every gate step set continue-on-error: true (no gate can block a merge)
*** MISSED *** gate 4's pytest suffixed with `|| true`
*** MISSED *** gate 3 re-scoped from whole-repo `ruff check` to `ruff check src`
*** MISSED *** gate 4 narrowed to `pytest tests/ci -q` (3900 tests silently dropped)
*** MISSED *** gate 1 replaced with `true`
*** MISSED *** gate 6 `pip-audit -r requirements.txt || echo warn`
*** MISSED *** gate 7 relaxed from --audit-level=high to --audit-level=critical
*** MISSED *** a secret moved to WORKFLOW-level env (every gate now needs it)
*** MISSED *** USER_DB_URL set to the empty string
*** MISSED *** USER_DB_URL pointed at db.example.com (service unreachable)
CAUGHT   the `alembic upgrade head` schema step deleted  -> p1, p7
*** MISSED *** postgres service image swapped to redis:7 (key still named postgres)
*** MISSED *** pull_request trigger restricted to branches: [no-such-branch]
*** MISSED *** gate 9's assert_required_paths_ran.py call removed
*** MISSED *** gate 10 step given `if: false`
*** MISSED *** gate 2 loses --check-only (isort prints a diff and exits 0)
```

The one `CAUGHT` is spurious and I am recording it as such rather than counting it: my mutation deleted every step whose `run` body contains the string `alembic`, which also deletes gate 1 and gate 2, because both name `alembic` as a path. Effectively 16 of 16 missed.

Six of these matter enough to name individually.

1. `continue-on-error: true` on every gate step. The phase's done-when is "each gate is a separately-named, separately-**failing** step". Nothing in 49 tests checks the failing half. One line per step turns the whole workflow into decoration while every check stays green and every step keeps its name.
2. `ruff check src`. `tracker/phase_4.14.md:74` records the branch-point measurement that gate 3 "passes only because nobody had pointed it at `tests/`", and T-4.14-03 exists to fix exactly that. There is no arm on gate 3's command at all, so the fix can be undone silently. Gate 2 got `test_p7` for its paths; gate 3 got nothing.
3. `npm audit --audit-level=critical`. Section 24 names `--audit-level=high` in the row the premise gate parses out of the specification, and `test_p8` only checks `npm run <script>` names, never `npm audit` flags.
4. `isort --diff` without `--check-only`. isort then prints a diff and exits 0. `test_p7` asserts `"isort" in body` and that the path tokens exist; it never asserts the flag that makes the command a check.
5. A secret at workflow-level `env`. `test_p11:381-393` iterates jobs and dumps each job, so a secret hoisted one level up is invisible to it while every gate now depends on a credential a fork cannot have. That is the precise failure P11 was written to prevent.
6. `if: false` on the gate 10 step, and `pull_request: branches: [no-such-branch]`. Both leave a green check that ran nothing, which is the one failure mode this entire phase exists to remove.

The premise gate's own coverage statement (`tests/ci/test_ci_workflow_premise.py:31-34`) says catching is "not covered" here and lives in the mutation file. The mutation file mutates only the same 11 arms. So the gap is declared in one file and not closed in the other, and the goal contract's "every gate has been mutation-proven to go red when the thing it exists to catch is broken" is not satisfied for any of gates 1, 3, 5, 7, 8 or 10.

### F-4.14-J-03, major. The no-DB-skip script misses 36 of 46 real database skips

`.github/scripts/assert_no_db_skips.py:64-71` matches six hand-written substrings against the skip message. I ran the real F-4.14-03 scenario: the database-backed suites against a dead `USER_DB_URL`, then the script against the resulting report.

```
$ USER_DB_URL="postgresql://nobody:nobody@127.0.0.1:59999/nope" pytest -m "not integration" -q -rs \
    --junitxml=/tmp/j414/deadb.xml <the db-backed suites>
212 passed, 46 skipped, 4 warnings, 25 errors in 8.96s

$ ./venv/bin/python .github/scripts/assert_no_db_skips.py /tmp/j414/deadb.xml
FAIL: 10 test(s) skipped because the database was unreachable.
SCRIPT_EXIT=1
```

Then I counted what it saw versus what was there, reusing the script's own `_DB_SKIP_MARKERS`:

```
total skipped: 46 caught: 10 UNCAUGHT: 36
  x36: user database unreachable at postgresql://nobody:nobody@127.0.0.1:59999/nope; the guest al...
```

Every one of the 36 is `tests/system_03_search_agent/adapters/web_sse/test_phase_4_10_premise.py:225`:

```python
reason=f"user database unreachable at {USER_DB_URL}; the guest allowance is a server-side count",
```

"user database unreachable" matches none of the six markers, and the `USER_DB_URL` in the f-string interpolates the *value*, so the literal token the first marker looks for never appears. That file is the premise gate for the anonymous guest allowance, a server-side abuse control.

The gate exits 1 today only because `auth/test_router.py` and the feedback suites happen to word their skips differently. Remove or reword those and the largest single block of database-backed tests skips silently with the script reporting `ok`. The script's docstring argues substrings were chosen over exact strings so it "stays quiet about the skips that are supposed to be there and loud about the ones that are not" (lines 61-63); measured, it is quiet about 78 percent of them.

This is the same coverage-hole shape `goal-contracts`' "a verify surface must state its own coverage" section describes: the script states its design rationale but never states which skip wordings in this repository it actually matches, so the gap was not arguable until someone ran it.

### F-4.14-J-04, major. P5's populate-checks are correlates

`tests/ci/test_ci_workflow_premise.py:279-287`:

```python
assert any("postgres" in str(spec).lower() for spec in services.values()), (...)
assert "USER_DB_URL" in str(job.get("env") or {}), (...)
```

The property is "the unit job has a reachable PostgreSQL and the tests are pointed at it". The checks are "the string `postgres` appears somewhere in a service spec" and "the string `USER_DB_URL` appears somewhere in the env mapping". Both are correlates and both survive mutations that destroy the property:

- image swapped to `redis:7`: MISSED. `str(spec)` still contains `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` from the service's `env` block, so the substring is satisfied by the environment variable names rather than by there being a PostgreSQL.
- `USER_DB_URL: ""`: MISSED. The key name is present; the value is empty.
- `USER_DB_URL: postgresql://u:p@db.example.com:5432/x`: MISSED. Points at a host the service is not on.

`test_m2_the_postgres_service_removed_is_caught` deletes the whole `services` key, which is the one mutation these correlates do survive correctly. This is the exact shape build phase 4.7 shipped, quoted in this file's own header at lines 36-39.

### F-4.14-J-05, major. The board records none of this work

`tracker/phase_4.14.md` is `+103` lines in this commit, i.e. created here, and every one of its ten tickets at lines 72-81 reads `todo` with an empty Owner and an empty Evidence column, for work that is finished and committed in the same commit. `tracker/BOARD.md:77` also still carries build phase 4.14 as `todo`. Nothing in the repository records a judge round, an adversary round, or the phase's own "Verify" clause at `tracker/phase_4.14.md:60`:

> "plus a recorded mutation run per gate"

There is no recorded mutation run per gate anywhere. The mutation file records arm-level mutations of the premise gate, which is a different artifact from a per-gate mutation run, and F-4.14-J-02 shows six gates have neither.

### F-4.14-J-06, major. The repository's drift gate is red on this commit

```
$ ./venv/bin/python tracker/check_doc_drift.py --check
AGENTS.md:32: says 4107 python tests (computed: 4156)
AGENTS.md:32: says 121 learnings.md entries (computed: 124)
CLAUDE.md:32: says 4107 python tests (computed: 4156)
CLAUDE.md:32: says 121 learnings.md entries (computed: 124)
requirements/Plan.md:20: says 418 decisions.md rows (computed: 421)
requirements/phase_6/Continuation_prompt.md:155: says 4107 python tests (computed: 4156)
requirements/phase_6/Continuation_prompt.md:182: says 418 decisions.md rows (computed: 421)
requirements/phase_6/Continuation_prompt.md:183: says 121 learnings.md entries (computed: 124)
requirements/phase_6/Continuation_prompt.md:540: says 4107 python tests (computed: 4156)
error: 10 facts computed | 9 stale | 0 structural
```

The commit adds 3 DECISIONS rows, 3 LEARNINGS rows and 49 tests, and updates none of the four documents that state those counts. `CLAUDE.md`'s own Current focus cell asserts these numbers are "all computed and verified by `python tracker/check_doc_drift.py --check`". A phase whose subject is merge-blocking gates left the one gate this repository already had in a failing state.

### F-4.14-J-07, minor. Gate 9's coverage check is a name-substring correlate

`.github/scripts/assert_required_paths_ran.py:56-59, 126-130` decides "both required paths are covered" by looking for substrings in test *names*. `refus` is a substring of `cite_or_refuse`, and `citation` is generic. `_MINIMUM_CASES = 2` against a file that currently holds 27 tests.

Measured, against a synthetic report with two passing tests that exercise neither path:

```xml
<testcase classname="t.fake" name="test_citation_refuses_placeholder"/>
<testcase classname="t.fake" name="test_totally_unrelated_thing"/>
```

```
$ ./venv/bin/python .github/scripts/assert_required_paths_ran.py /tmp/j414/fake.xml
ok: 2 required-path tests ran, none skipped, both paths covered.
rc=0
```

One test name satisfies both required paths at once. The script's docstring (lines 15-21) says case 3, a file "renamed, moved, or emptied", is the dangerous one it exists to catch; a file emptied to two tests is certified as covering both paths. Full deletion is caught; partial gutting is not.

For the record, the gate does work on the real file: `27 passed`, then `ok: 27 required-path tests ran, none skipped, both paths covered.`

### F-4.14-J-08, minor. Gate 1 does not do what its own name says

`.github/workflows/ci.yml:116-117`:

```yaml
      - name: "Gate 1: Python compiles and imports cleanly"
        run: python -m compileall -q src services tests alembic
```

`compileall` byte-compiles; it never imports a module, so the "imports cleanly" half of Section 24's gate 1 is unverified. It also omits `tracker/` and `.github/scripts/`, so the two helper scripts CI depends on are not in gate 1's subject (ruff at gate 3 does parse them, which mitigates but does not close it). No premise arm asserts anything about gate 1's command, which is why mutation 5 above ("gate 1 replaced with `true`") passes.

### F-4.14-J-09, minor. The pin argument was applied to the wrong tool

`pyproject.toml:57-58`:

```
    "ruff==0.16.0",
    "isort>=5.13",
```

`test_p12`'s reasoning is that an unpinned tool lets "a minor bump change what gate 3 enforces without anyone editing a line of configuration". After F-4.14-J-01, isort is the *sole* owner of import order and gate 2's entire meaning, and it is on a floor. The argument applies at least as strongly to it, and there is no arm pinning it.

### F-4.14-J-10, minor. The mechanical pass mangled a comment

`src/system_03_search_agent/adapters/web_sse/app.py:22`, 184 characters against a configured `line-length = 100`:

```python
    Query as FastAPIQuery,  # Aliased: `Query` is already this module's domain request model; (contracts.query.Query). Importing FastAPI's under its own name would; shadow it silently.
```

Before the commit this was a three-line comment above the import. The line breaks became semicolons, producing "domain request model; (contracts.query.Query)" and "under its own name would; shadow it silently". No behaviour change, but a formatting pass rewrote prose into nonsense, and `.claude/rules/writing-style.md` governs this repository's comments as much as its documents.

### F-4.14-J-11, minor. A finding was moved out of scope without an owner

`tracker/phase_4.14.md:91` declares F-4.16-02 not covered, and states plainly: "The board assigns it to this phase." `tracker/BOARD.md:96` still assigns it here. No product-owner decision is recorded in `DECISIONS.md` or in the phase History. The reasoning given (it is a property of the e2e mock backend, not of CI) is sound, but the disposition is the lead reassigning its own inherited ticket, and the board was left contradicting the phase file.

The other three out-of-scope declarations at lines 88-90 (CD, the live premise gates, the Playwright suite) I judge honest: each names a reason and a successor phase, and each is consistent with Section 24 and `tracker/BOARD.md:78`.

### F-4.14-J-12, minor. Three inaccuracies in the commit message

- "49 gate tests of which 34 are mutation arms". Measured: `tests/ci/test_ci_workflow_mutation.py` collects 33, and 12 of those are control arms (`test_m0_*` parametrized 11 ways, plus `test_m0b_*`). Actual mutations: 21.
- "Measured: against a dead database that suite prints '1 skipped' and exits 0 with 62 real tests gone" is accurate for `auth/test_router.py` alone, and reads in context as a statement about the suite.
- "Closes the Section 24 open flag on the stale pull request template." The commit does not touch `requirements/Technical_specification.md`, which is locked, and its flags table still reads "Still open". The template *was* rewritten correctly; the flag cannot be closed until the Step 6.2 reconciliation, and the message should say so.

## What I verified and how

| Check | Evidence | Result |
|-------|----------|--------|
| F-4.14-01 diagnosis: is a bare `pip-audit` a false alarm, or a dodged dependency problem? | `pip show cryptography` reports `Required-by:` empty. `grep` finds no `cryptography` in `requirements.txt` or `pyproject.toml`. The only crypto-adjacent declared dependency is `PyJWT>=2.13`, and `auth/tokens.py:35` and `auth/guest.py:51` pin `HS256` on every mint and every decode, which PyJWT implements with `hmac` and needs no `cryptography` | CORRECTLY DIAGNOSED. Not a dodge |
| Both audit invocations, run by me | `pip-audit` → `Found 2 known vulnerabilities: cryptography 49.0.0 PYSEC-2026-3552, pip 26.1.2 PYSEC-2026-3721`. `pip-audit -r requirements.txt` → `No known vulnerabilities found` | Matches the phase's record exactly |
| Does the scoped invocation still resolve transitive dependencies? | `pip-audit --help`: `--no-deps  don't perform any dependency resolution`, not passed by the workflow. Confirmed it catches a declared vulnerable package: `pip-audit -r <file with cryptography==49.0.0>` → `Found 1 known vulnerability` | Scope is legitimate, not a narrowing |
| F-4.14-02 diagnosis | `grep -rn "def test_cite_or_refuse_compliance\|def test_zero_retrieval_refusal" tests/` → 0 hits. Both strings exist only as section comments at `tests/system_03_search_agent/synthesis/test_required_paths.py:73` and `:398` | CORRECTLY DIAGNOSED |
| F-4.14-03 diagnosis | Reproduced against a dead `USER_DB_URL`: 46 skips and 25 errors where a live database gives 212 passed. The phenomenon is exactly as described | CORRECTLY DIAGNOSED. The fix is partial, see F-4.14-J-03 |
| Import-order claim, by experiment not by reading | Four `ruff` runs pasted in F-4.14-J-01, plus a scratch-copy oscillation experiment in `/tmp/j414/proj` | Claim is FALSE as recorded; see F-4.14-J-01 |
| Gate suite passes as shipped | `pytest tests/ci/ -q` → `49 passed in 0.12s`. Collection: 16 premise + 33 mutation | Passes |
| Independent mutation of every premise arm | My own harness with a control, output pasted in F-4.14-J-02 | 16 of 16 missed |
| Gate 9 end to end | `pytest tests/.../test_required_paths.py` → `27 passed`, then `assert_required_paths_ran.py` → `ok: 27 ... both paths covered` | Works on the real file. Correlate hole at F-4.14-J-07 |
| `npx --prefix frontend playwright install` is a real invocation | `npx --prefix frontend playwright --version` from the repository root → `Version 1.62.0`, identical to `cd frontend && npx playwright --version`. Resolves the local `frontend/node_modules/.bin/playwright`, does not fetch from the registry | VALID. No finding |
| Playwright `webServer` under CI | `frontend/playwright.config.ts:62,86` set `reuseExistingServer: !process.env.CI`; the accessibility job sets `CI: "true"` at `ci.yml:291`, so Playwright starts both servers itself. Playwright merges `process.env` into `webServer.env`, and `tests/e2e_support/mock_llm_backend.py:265-272` uses `os.environ.setdefault`, so the job's `USER_DB_URL` (with credentials) wins over the module's credential-free default, and `AUTH_SECRET` is supplied by the module. `accessibility.spec.ts:39-52` does sign up, so it needs both | Coherent. No finding |
| `alembic upgrade head` can run | `alembic.ini` exists at the root; `alembic/env.py:53` resolves the URL from `get_user_db_url()` at runtime rather than from the ini; `alembic>=1.13` is in `requirements.txt` so the CLI is installed | Works. Ordering nit at F-4.14-J-08 |
| Accessibility path filter on a `push` event | `ci.yml:314-318`: empty `BASE_SHA` takes the `touched=true` branch and says so. `fetch-depth: 0` at line 295 makes both PR SHAs reachable for the `git diff` at line 319 | Correct as designed |
| Shell-injection surface in the filter step | `ci.yml:308-310` passes both SHAs through `env:` rather than interpolating `${{ }}` into the script body | Correct, and correctly reasoned in its comment |
| Alembic migration diffs, the highest-risk mechanical change | `git show 4ea0778 -- alembic/`. All eight files: import reordering and blank-line removal only. No `revision`, `down_revision`, `op.*` call, column, index, constraint or DDL string touched | NO BEHAVIOUR CHANGE |
| Other mechanical fixes | `verify_adaptation.py` nested-`if` flattened to `and` (equivalent, `continue` semantics preserved). `check_style.py` `startswith("#") or startswith("|")` → `startswith(("#","\|"))` (equivalent). `check_preservation.py` `zip(cuts, cuts[1:])` → `itertools.pairwise` (equivalent). `preflight.py` `socket.timeout` → `TimeoutError` (an alias since 3.10, repository is 3.11+). `typing.Callable` → `collections.abc.Callable` under `from __future__ import annotations`. `subprocess.run(..., check=False)` made explicit (was already the default) | NO BEHAVIOUR CHANGE, except the comment loss at F-4.14-J-10 and a deleted `# noqa: E402` explanatory note in `tracker/check_doc_drift.py:196` |
| Scope against `v1-scope-boundary` | Nothing here appears on the PRD out-of-scope list or Section 25's fast-follow table. CI is Section 24 work pulled forward with a product-owner decision recorded at `tracker/BOARD.md:7` | NO SCOPE VIOLATION |
| Gate order against locked Section 24 | Section 24's table at `requirements/Technical_specification.md` parses to ten rows; the workflow runs 1,2,3,4,6,9 in ascending order in one job and splits 5, 7-8 and 10 into concurrent jobs, with the reason stated at `ci.yml:48-53`. Gate 3 is run repository-wide, which is stricter than the specification, not weaker | FAITHFUL |
| PR template against Section 24 | `.github/pull_request_template.md` lists all ten gates with the exact commands, keeps the security scan as a human gate per Section 24's own instruction, and drops the stale BioLink and KGX rows | CORRECT. Closes the substance of the flag, see F-4.14-J-12 on the wording |
| Gate coverage gaps between gates 1, 2 and 3 | Four tracked `.py` files sit outside gate 2's isort path list: both `.github/scripts/*.py` and two under `docs/build/design/`. They are clean today (`isort --check-only .github` exits 0) but the path list is hand-maintained | Informational, folded into F-4.14-J-08 |

## What I could NOT verify

These are FAILS, not passes. I could not produce evidence for any of them, and none should be counted as verified by this report.

1. That `.github/workflows/ci.yml` runs green on a GitHub-hosted runner. Nothing offline can establish it. The premise gate says the same at its lines 24-29. It remains the phase's only real proof and it has not happened.
2. That `pytest -m "not integration"` passes against a runner-shaped PostgreSQL with only `USER_DB_URL`, `AUTH_SECRET` and `ANON_DAILY_RUN_CAP` set. The commit claims `3993 passed, 136 skipped, zero failed` against a fresh migrated database. I did not re-run the full suite, per the brief. Collection agrees to within a plausible margin: `4133/4156 tests collected (23 deselected)`. The passing count itself is unverified.
3. That gate 10's Playwright run succeeds end to end on a runner. Every ingredient I could check offline is sound (see the table), but the composition of `playwright install --with-deps`, both webServers, a fresh database and axe has never been executed anywhere.
4. That `npm ci`, `npm audit --audit-level=high` and `npm run build` pass on Node 22. The branch-point measurement in `tracker/phase_4.14.md:41-42` is the lead's, taken on macOS, and I did not re-run it.
5. That gate 5's `secrets.GRAPH_QUERY_URL` path behaves as designed. It cannot be exercised without repository secrets. The workflow's blocked-stop handling for it (`ci.yml:210-226`, a `::warning` annotation plus a `NOT RUN` summary, then `exit 0`) is the honest treatment `goal-contracts` asks for and `test_p15` guards it, but the path itself is untested.
6. Whether the two remaining ruff-versus-isort files in F-4.14-J-01 could be reconciled by a per-file `# noqa`/`# isort: skip`. I proved the oscillation exists on those two; I did not attempt a reconciliation, because that would mean editing files, which the brief forbids.

## Premise check

The phase's done-when, `tracker/phase_4.14.md:58`:

> "a pull request against `develop` runs all ten of Section 24's gates, in Section 24's order; each gate is a separately-named, separately-failing step; every gate has been mutation-proven to go red when the thing it exists to catch is broken; and the unit-suite gate fails rather than skips if its database is absent."

Clause by clause.

- "runs all ten gates, in Section 24's order": SATISFIED on the file's face, unverified on a runner. The workflow declares all ten, parsed against the locked table at test time rather than against a copy, which is the right construction.
- "each gate is a separately-named ... step": SATISFIED. Ten named steps, and the naming convention is what the whole premise gate keys off.
- "... separately-**failing** step": NOT SATISFIED, and nothing measures it. `continue-on-error: true` on all ten, or `|| true` on any one, passes all 49 tests (F-4.14-J-02).
- "every gate has been mutation-proven to go red when the thing it exists to catch is broken": NOT SATISFIED for gates 1, 3, 5, 7, 8 and 10, which have no arm on their command at all. The mutation harness proves the *premise arms* go red when the *workflow* is mutated; it does not prove any gate goes red when the *code* is broken, and the goal contract's "a recorded mutation run per gate" does not exist (F-4.14-J-05).
- "the unit-suite gate fails rather than skips if its database is absent": PARTIALLY SATISFIED. It fails today, and I proved that by running it. It fails on 10 of 46 real skips, and the largest single group of database-backed tests is invisible to it (F-4.14-J-03).

So: did every ticket succeed at its own task while the phase missed its stated outcome? Close to it, in a specific and recognisable way.

Nine of the ten tickets produced good, real work. The workflow is thoughtfully built, the three findings are genuine and were found the right way (by asking what the command would do on the runner, before writing the YAML, which is `attack-the-constraint` applied correctly and is the single best thing in this phase). The reasoning is written into the artifacts beside the code rather than into a document nobody opens.

T-4.14-09 is the ticket that missed, and it is the one the whole contract rests on. Its acceptance criteria are "Every arm carries a populate-check. Each gate is mutation-proven to go red." Every arm does carry a populate-check, and three of them check a correlate rather than the property (P5's two, P13's one). Each gate is not mutation-proven; six have no arm at all. The suite is 49 tests that verify the workflow *says* the right things, and almost nothing that verifies it *does* them, which is the same distance between "passed" and "did not run" that F-4.14-03 was filed about, moved up one layer to the gate that grades the gates.

And T-4.14-02 shipped on a premise that is not true. The outcome is fine; the recorded reason is false and is now in four durable places, one of them a decision row whose whole purpose is to stop the question being reopened. Under `goal-contracts`' three-way test, this is the second case: the check was wrong, and it should be fixed and said out loud, not routed around.

Recommendation: FAIL, with F-4.14-J-01 and F-4.14-J-02 as blockers and F-4.14-J-03 through -J-06 to be fixed or explicitly accepted before merge. F-4.14-J-01's fix is documentation and one arm, not a rollback: keep isort as gate 2's owner, delete or correct the false premise, and either make P13 assert something real or retire it. F-4.14-J-02 needs arms on gates 1, 3, 5, 7, 8 and 10, and one arm asserting no gate step carries `continue-on-error` or a swallowing `|| true`.

## Note on the working tree at the time of this review

At the end of this review `git status` showed two files modified that I did not modify:

```
 M src/system_03_search_agent/adapters/web_sse/app.py
 M src/system_03_search_agent/core/graph.py
```

The diff is ruff's `I001` autofix applied in place, reverting isort's ordering on exactly the two files named in F-4.14-J-01, so the working tree currently fails `isort --check-only` (gate 2). My own oscillation experiment ran in a scratch copy at `/tmp/j414/proj`, never in the repository, so this is another agent's in-place experiment running concurrently. I have deliberately NOT reverted it, because the brief forbids editing any file but this report and because reverting could break a run still in progress. Someone must `git checkout` those two paths before this branch is committed or `verify` is run.
