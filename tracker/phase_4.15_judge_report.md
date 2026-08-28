# Build phase 4.15: judge report

Round 1. Graded 2026-08-27 on `phase/4.15-release-environments`, starting from `682de3f` plus the working tree. The branch advanced to `5dea231` during the round, adding `fd1432c` (commits `docs/build/Release_flow.md`) and `5dea231` (widens the two `/health` assertions). Both were already present in the working tree I read, and `git diff --stat 682de3f HEAD` over `.github/`, `tests/.../tools/`, `app.py` and `env.example` is empty, so nothing graded here moved under the round. `tracker/phase_4.15.md` and the `DECISIONS.md` entry remain uncommitted; the branch is not pushed and no pull request exists.

Verdict: FAIL. Six of the seven graded items fail. Thirteen findings filed, two critical, six major, five minor, all written to `tracker/phase_4.15.md` under `## Findings` as F-4.15-J-01 through F-4.15-J-13.

## Table of contents

- [Verdict per item](#verdict-per-item)
- [Item 1: the premise, not only the leaves](#item-1-the-premise-not-only-the-leaves)
- [Item 2: the release scripts](#item-2-the-release-scripts)
- [Item 3: GitHub Actions injection](#item-3-github-actions-injection)
- [Item 4: mutation-test every gate arm](#item-4-mutation-test-every-gate-arm)
- [Item 5: the commands, with real output](#item-5-the-commands-with-real-output)
- [Item 6: scope](#item-6-scope)
- [Item 7: the document against the code](#item-7-the-document-against-the-code)
- [What is genuinely good](#what-is-genuinely-good)
- [Findings filed](#findings-filed)

## Verdict per item

| Item | What it graded | Verdict |
|---|---|---|
| 1 | Finished tickets against the goal contract's five done-when items | FAIL |
| 2 | The four release scripts, line by line | FAIL |
| 3 | GitHub Actions script injection, both workflows | PASS |
| 4 | Mutation-test every arm P1 to P9 | FAIL |
| 5 | Run the four named commands and paste real output | PASS on execution, FAIL on what one of them reveals |
| 6 | Scope against `.claude/rules/v1-scope-boundary.md` | PASS |
| 7 | `docs/build/Release_flow.md` against the shipped code | FAIL |

## Item 1: the premise, not only the leaves

FAIL. Twelve tickets are `in-review` and the stated outcome is not met, because the outcome statement was never updated through two mid-phase redesigns.

Three of the five done-when items in `tracker/phase_4.15.md:82-88` are literally false against what shipped:

| Done-when | Says | Shipped |
|---|---|---|
| 1 | "Two Railway environments exist in `system3-search-agent`" | Two PROJECTS. The fixture records `project_id` `0f85f78e-1ffc-4a62-b3d8-a03dcae9b585` and `4879a10f-d4ae-4d67-8274-bec6cbc15038` |
| 2 | "`production` the environment watches `main`" | Production watches `production` |
| 3 | "`main` exists on origin" | `git ls-remote --heads origin` returns exactly `develop` and `production`. T-4.15-12 deleted `main` |
| 4 | The release flow written down in one document | Met, with defects, see item 7 |
| 5 | "every arm is proven able to fail by a mutation harness" | Not met. P6 and P9 have no mutation case, see item 4 |

The same staleness runs through "What the refinement settled" (line 70, "A second environment in the existing project"), the Coverage bullet at line 153 ("merge-blocking on `main`"), and the arms table at lines 99-108, which lists eight arms while nine ship. The tickets table was rewritten for the redesign; the contract that grades it was not. Filed as F-4.15-J-02.

The verify surface has a fourth element, "CI green on the pull request", which cannot be evaluated: `git ls-remote --heads origin "phase/*"` returns nothing and `gh pr list` shows no pull request for this branch. That is sequencing rather than a defect, and it is recorded here rather than scored, but done-when item 5 stays unmet on the mutation half regardless.

## Item 2: the release scripts

FAIL. Four measured defects. Two things the brief asked about specifically came back clean and are stated as such below.

### Clean: version derivation cannot compute a wrong version

The F-4.15-05 hardening is real and complete. Measured by running the shipped `derive_version.sh` in a scratch git repository across six tag shapes:

```
### CASE A: only a non-semver tag exists (baseline/pre-drift-fix)
no previous tag: this is the first release
bump=minor -> v0.1.0
--out-- should_release=true | previous_tag= | version=v0.1.0 | bump=minor

### CASE B: prerelease tag v1.2.3-rc1
previous tag: v1.2.3-rc1
previous tag v1.2.3-rc1 does not parse as vMAJOR.MINOR.PATCH
EXIT NONZERO   --out-- (empty)

### CASE C: four-part tag v1.2.3.4
previous tag v1.2.3.4 does not parse as vMAJOR.MINOR.PATCH
EXIT NONZERO   --out-- (empty)

### CASE D: proper tag v1.2.3 then a feat commit
bump=minor -> v1.3.0

### CASE E: no commits since tag
no commits since v1.3.0; nothing to release
--out-- should_release=false

### CASE F: BREAKING CHANGE in body
bump=major -> v2.0.0
```

`--match` filters the non-semver tag, and the belt-and-braces digit loop aborts rather than coercing. No input produced a wrong version; the two malformed cases stop the release, which is the stated trade-off. Against the real repository the script prints `bump=minor -> v0.1.0`, matching what `Release_flow.md:65` promises.

### Clean: no infinite trigger loop, and nothing touches develop

The loop is prevented twice over. `tag_and_release.sh:22` carries `[skip ci]`, and both the push (line 23) and the pull request use `secrets.GITHUB_TOKEN`, whose events do not start workflow runs. The tag push at line 30 matches no trigger either: both workflows key on `push: branches:`, and a tag ref is not a branch ref.

No script pushes to or rewrites `develop`. `open_backmerge_pr.sh` pushes only `chore/back-merge-<version>` (line 34) with no `--force`, and reaches `develop` only as a pull-request base. A stale remote branch from a failed prior run makes line 34 fail non-fast-forward under `set -e`, which is a stopped job, not a destructive one.

### Defect: the changelog is glued to the preamble, and the comment says it is not

`write_changelog.sh:84-87` claims a structural split "cannot drift when the preamble is reworded" and that the glued-heading defect was the OLD behaviour. Running the shipped script against the shipped `CHANGELOG.md`:

```
     8	No release has been cut yet. The first push to `production` creates `v0.1.0`
     9	and writes its section directly below this line.
    10	## v0.1.0 (2026-08-28)
```

No blank line between 9 and 10. The checked-in `CHANGELOG.md` has no trailing blank, and the split copies `head.md` verbatim without emitting a separator. It repeats on every later release, since `split_at` then lands on `## v0.1.0` and lines 1 to 9 are copied unchanged again. F-4.15-J-07.

The same run shows the preamble sentence at lines 8 and 9 surviving forever, denying the release printed directly beneath it, because the script only writes its own preamble when the file is absent (lines 72-82). F-4.15-J-08.

### Defect: word-splitting on a pipe in a commit subject

The log format is `%s|%h` and the split is `subject="${line%%|*}"`, cutting at the first pipe rather than the last. Measured with a commit subject `chore: a subject with a | pipe in it`:

```
Maintenance

- a subject with a  (1cddf63)
```

"pipe in it" is dropped with no warning. F-4.15-J-09.

### Defect: `set -euo pipefail` does not reach the `git log` calls

`derive_version.sh:55`, `derive_version.sh:66` and `write_changelog.sh:51` all read `git log` through `< <(...)`. Process substitution runs in a subshell whose exit status neither `set -e` nor `pipefail` observes. A failing `git log` there yields an empty stream, so `derive_version.sh` proceeds with `bump` at its `patch` default and publishes a permanent tag, which is precisely the outcome its own lines 36 to 39 say it will not accept. F-4.15-J-11.

The `[skip ci]` marker itself is untested and its comment names the weaker of the two loop-prevention mechanisms as the load-bearing one. F-4.15-J-13.

`bash -n` is clean on all four:

```
bash -n .github/release/derive_version.sh: OK
bash -n .github/release/open_backmerge_pr.sh: OK
bash -n .github/release/tag_and_release.sh: OK
bash -n .github/release/write_changelog.sh: OK
```

`shellcheck` is not installed on this machine, so no static shell analysis was run. Stated as a gap rather than counted as a pass.

## Item 3: GitHub Actions injection

PASS. Every `${{ }}` expression in both workflows, enumerated:

```
ci.yml:63   github.workflow, github.ref          (concurrency key, not a shell)
ci.yml:64   github.event_name == 'pull_request'  (concurrency key, not a shell)
ci.yml:138,185,218,280,286  env.PYTHON_VERSION / env.NODE_VERSION  (action inputs)
ci.yml:193-195  secrets.GRAPH_*                  (env:, into a script)
ci.yml:273  github.event.pull_request.base.sha   (env: BASE_SHA)
ci.yml:274  github.event.pull_request.head.sha   (env: HEAD_SHA)
release.yml:31  github.ref                       (concurrency key)
release.yml:62,63,69,76  steps.version.outputs.*  (env:)
release.yml:70,77  secrets.GITHUB_TOKEN          (env:)
```

The only two `github.event.*` values anywhere are commit SHAs, and both reach `gate10_filter.sh` through `env:` rather than through interpolation into a body. That script reads them as `"${BASE_SHA:-}"` and `"${HEAD_SHA:-}"` and quotes them at every use (lines 20-21, 30-31, 37, 43, 51). No `${{ github.head_ref }}`, no `github.event.head_commit.message`, no `github.event.commits`, no `github.event.issue` or `.comment` in either file. `grep -rn '\$\{\{' .github/gates/ .github/release/` returns only two comment lines, no live interpolation.

## Item 4: mutation-test every gate arm

FAIL, and this is the item that carries the two criticals.

### P6 and P9 have no mutation case at all

The harness ships 14 cases: P1 x3, P2, P3, P4 x2, P5 x2, P7, P8 x3, plus one structural check on the skip marker. `grep -n "def test_"` on the mutation file returns six functions, and neither the parametrised lists nor any function names `test_p6_...` or `test_p9_...`. So T-4.15-09's acceptance ("every arm proven red under its own mutation") and done-when item 5 are both false, and the harness's own docstring line 3 ("Every arm ... is asserted here to go RED") is a claim its contents do not support. Its coverage statement admits only a narrower gap, "it does not mutate P6's `railway` subprocess boundary beyond its parse", which reads as partial coverage where there is none. F-4.15-J-03, critical.

I mutated both arms myself, since the brief makes this a checklist item rather than an optional dispatch.

P9, driven against nine variants of `release.yml`:

```
GREEN  control (unmutated)
RED    M1 inline shell appended to a run:
RED    M2 the :;# trick from 4.14
RED    M3 head_commit.message interpolated into env
RED    M4 block scalar run
RED    M5 script renamed to one that does not exist
GREEN  M6 github.actor interpolated into env
GREEN  M7 permissions widened with actions: write
GREEN  M8 push trigger widened to develop too
```

M1 to M5 are the two rules P9 claims, and it catches all five including build phase 4.14's exact `:;#` defeat. M6 to M8 are outside its stated scope, so they are recorded rather than filed. P9's logic is sound; it simply has no case in the shipped harness.

P6, driven with `_service_variable_names` substituted:

```
GREEN  control: identical sets
RED    M1 develop missing AUTH_SECRET  -> "is missing 1 variable(s) that production has: ['AUTH_SECRET']"
GREEN  M2 develop has an EXTRA var (green by design, per the arm's docstring)
RED    M3 both read ZERO names (CLI output format changed)
RED    M4 production reads zero, develop full
```

P6's logic is also sound, including its populate-check. Both arms work; neither is proven by the harness that claims to prove them.

### The fake transport is not faithful where it matters most

`_World` is faithful enough for P1, P2, P4 and P5. It is not faithful for P3, and P3 is the arm the phase file calls "the arm that carries the most weight".

On the real system `GET /auth/me` runs `resolve_user_from_bearer_token`, which decodes the token AND THEN looks the subject up in that deployment's own database (`src/system_03_search_agent/auth/dependencies.py:109-111`, `select(User).where(User.id == user_id)`), returning the same 401 when the row is absent. The two deployments have separate Postgres instances. So a token minted on develop is refused by production on the missing user row whether or not the signing key is shared.

`_World.get`'s `/auth/me` branch (`test_release_environments_mutation.py:140-148`) returns `200 if minted_by == env or self.shared_auth_secret` and never consults `self.accounts` or `_owns`. It models a token check with no database lookup at all, which is the one difference that makes P3 look like it detects a shared secret.

Measured. P3 re-run unchanged against a `_World` subclass whose `/auth/me` also requires the user row to exist in the environment being asked:

```
=== P3 against the harness's own _World, shared_auth_secret=True ===
AssertionError("a token minted on develop was ACCEPTED by production with 200. ...")

=== P3 against a FAITHFUL world (token check does a DB lookup), shared_auth_secret=True ===
result: GREEN - arm did NOT detect the shared secret

=== control: faithful world, healthy ===
result: GREEN (correct)
```

P3 measures database separation, which is already P2's property, and asserts `AUTH_SECRET` separation, which is a correlate of it. That is the safety-by-proxy shape the premise gate's own docstring (lines 19-27) says it exists to avoid. F-4.15-J-04, critical.

### Two further arms assert less than they claim

P1's docstring states "the service ids reported by the two deployments are compared too, because two hostnames can still front one service" and calls it "the half that matters". The body (lines 185-208) compares `prod["api"] != dev["api"]`, `prod["web"] != dev["web"]` and each `/health` status. No service id is read, and `/health` does not return one. F-4.15-J-01.

P7's property, per the goal contract line 107 and the gate's own arms table, is "`env.example` names every non-Railway variable the API service is given". What it asserts is that `env.example` names every variable in a hardcoded 26-name literal snapshotted 2026-08-27. Add a 27th variable to the service tomorrow and omit it from `env.example` and P7 stays green, which is F-4.15-01 recurring undetected. The docstring's mitigation, "the live equivalent is P6", is false and measured so: `inspect.getsource(test_p6_...)` contains no reference to `env.example`, `_ENV_EXAMPLE` or `_documented_variable_names`. No arm compares the live deployment to `env.example`, and the Coverage section does not name the gap. F-4.15-J-06.

## Item 5: the commands, with real output

The four commands ran. Three are green. The fourth is green and is what exposed the P6/P9 gap once the case count was compared against the arm count.

```
$ python -m pytest tests/.../test_release_environments_premise.py tests/.../test_release_environments_mutation.py -q -p no:randomly
ssssss.................                                                  [100%]
17 passed, 6 skipped in 0.05s
```

Six skips are P1 to P6 behind `RUN_PREMISE_GATE`, as designed. Eleven of the 17 passes are the mutation harness; three are P7, P8 and P9; three are the extra offline mutation functions.

```
$ ruff check src services
All checks passed!
exit=0

$ python tracker/check_doc_drift.py --check
ok: 10 facts computed | 0 stale | 0 structural
exit=0
```

Re-run after my thirteen findings were appended: still `0 stale | 0 structural`.

```
$ bash -n on each of the four release scripts
derive_version.sh: OK   open_backmerge_pr.sh: OK
tag_and_release.sh: OK  write_changelog.sh: OK
```

`RUN_PREMISE_GATE=1` was not set, per the brief. So P1 to P6 have not been observed against the live deployments by me; the only evidence they pass live is the lead's claim, which under this brief's own rule is not evidence.

## Item 6: scope

PASS. Nothing here touches the PRD out-of-scope list or the technical specification's fast-follow table: no BLAST, no sequence similarity, no VCF, no UCSC enrichment, no non-NCBI graph federation, no distillation, no ensemble panels, no sub-query decomposition, no persistent cross-session memory, no automated mining. Two Railway environments with per-environment variable sets are Section 24's own wording pulled forward; the branch flow and the release automation are additions taken by explicit product-owner decision on 2026-08-24 and 2026-08-27 and recorded at `tracker/phase_4.15.md:8`. `env.example`'s new `RUN_MIGRATIONS_ON_STARTUP`, `NIXPACKS_NO_CACHE` and `NIXPACKS_NODE_VERSION` document what was already deployed. The `/health` field is additive under `system-design-patterns` pattern 10 and `tests/.../test_health.py:34` pins the key set so a third field cannot arrive silently.

## Item 7: the document against the code

FAIL, on one substantive omission and three smaller drifts.

The substantive one. `Release_flow.md` step 8 says "Review and merge the automated back-merge pull request", and the "What this flow does not protect against" section lists five gaps. It does not say that the back-merge pull request will carry no checks at all. `open_backmerge_pr.sh` runs `gh pr create` under `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` (`release.yml:77`), and GitHub does not start workflow runs from events that token raises, so `ci.yml`'s unfiltered `pull_request` trigger never fires for it. With F-4.14-A-04 still open, the phase adds an automated, permanently uncheckable path into the default branch. F-4.15-J-10.

The smaller drifts:

- Line 61 and step 8 say the pull request is opened "from `production`". It is opened from a new `chore/back-merge-<version>` branch cut at `origin/production` (`open_backmerge_pr.sh:33-38`). Anyone looking for `production` as the head branch will not find it.
- Line 65 and `CHANGELOG.md` lines 8-9 both say "No release has been cut yet", a sentence nothing removes after the first release. F-4.15-J-08.
- Step 2 introduces a `release/<version>` branch prefix that `.claude/rules/git-workflow.md` does not name. Recorded, not filed.

Everything else in the document checks out against the code. The two projects, their ids and their four URLs match `fixtures/release_environments.json` exactly. The `app_env` line reference to `app.py` line 354 is correct: `return HealthResponse(status="ok", app_env=os.environ.get("APP_ENV", "unknown"))` is on line 354. The four scripts and their order match `release.yml:55-78`. The bump rules match `derive_version.sh`. The statement that a pull request into `production` already runs every gate matches the unfiltered `pull_request` trigger. `v0.1.0` as the first version is what the script actually computes.

Separately, the comment this phase added at `ci.yml:44-48` drops a word and inverts itself: "with change needed" where the measurement it cites says no change is needed. F-4.15-J-12.

## What is genuinely good

Stated because a report that only lists defects misrepresents the phase.

- The version derivation is correct under every tag shape I could construct, and the F-4.15-05 hardening does what its comment says it does, which is not something this report was able to say about several other comments here.
- The premise gate's departure from house convention, failing rather than skipping when an environment is absent, is right, and it is asserted structurally at `test_the_premise_gate_gates_on_the_flag_alone_and_not_on_reachability` rather than left in a docstring.
- P4's and P5's mutation cases document that the arm fires at an EARLIER assertion than the author predicted, and the harness was corrected to the message that actually fires rather than the arm being reshaped to produce the predicted one. That is the right call and it is recorded rather than hidden.
- P6's populate-check ("read zero variable names ... so the comparison below would pass against anything") caught two of my four mutations on its own.
- No `${{ }}` injection sink anywhere in either workflow, and `gate10_filter.sh` routes even commit SHAs through `env:` rather than judging case by case which fields are probably fine.
- Nothing in the release line pushes to, force-pushes, or rewrites `develop`.

## Findings filed

All thirteen are in `tracker/phase_4.15.md` under `## Findings`.

| ID | Severity | One line |
|---|---|---|
| F-4.15-J-04 | critical | P3 cannot detect a shared `AUTH_SECRET` on the real deployments; `_World` hides it by modelling `/auth/me` with no database lookup |
| F-4.15-J-03 | critical | P6 and P9 have no mutation case; done-when 5 and T-4.15-09's acceptance are both false |
| F-4.15-J-02 | major | Three of five done-when items are false against what shipped; the contract was never updated through two redesigns |
| F-4.15-J-01 | major | P1's docstring claims a service-id comparison the body does not perform |
| F-4.15-J-06 | major | P7 asserts a hardcoded 2026-08-27 snapshot, not the live deployment, and the named live equivalent does not exist |
| F-4.15-J-07 | major | The changelog heading is glued to the preamble; the comment above the split claims it cannot be |
| F-4.15-J-08 | major | `CHANGELOG.md` and `Release_flow.md` both say "No release has been cut yet" forever |
| F-4.15-J-10 | major | The back-merge pull request runs no CI, and nothing says so |
| F-4.15-J-05 | minor | `get_health`'s docstring cites F-4.15-02, which is an unrelated finding |
| F-4.15-J-09 | minor | A `|` in a commit subject silently truncates its changelog entry |
| F-4.15-J-11 | minor | `set -euo pipefail` does not reach the `git log` process substitutions |
| F-4.15-J-12 | minor | `ci.yml`'s new comment drops "no" and inverts its own meaning |
| F-4.15-J-13 | minor | `[skip ci]` is untested and is not the mechanism that actually terminates the loop |
