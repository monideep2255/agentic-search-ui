"""Run the release job the way release.yml runs it, against a throwaway repository.

Added 2026-09-27, when the release job stopped pushing to `production`. It
closes finding F-4.15-A-13, which recorded that nothing tested what these
scripts DO: the premise gate's P9 and P9b arms read the workflow and the
scripts as text, and every behaviour below had only ever been observed on a
real release.

HOW IT RUNS THE JOB. It reads `.github/workflows/release.yml`, and for each
step in order it evaluates the step's `if:`, builds the step's `env:` from the
earlier steps' outputs, and executes the script the step names, from a clone of
a throwaway `origin` with `production` checked out, as `actions/checkout`
leaves it. So a step added to the workflow, a renamed output, or a variable the
workflow forgets to pass is exercised here rather than on the production line.
`gh` is a stub first on PATH that records its arguments and the notes it is
handed, keeps the releases and pull requests it was asked to create, can be
told to fail, and reaches nothing.

WHAT THIS COVERS, stated so a gap is arguable rather than discovered:

    Covered      The job never moves `production` on `origin`. The tag lands
                 on `origin`, annotated, on `production`'s tip. The changelog
                 commit leaves the job only on the back-merge branch, and the
                 stub sees `gh pr create` into `develop` and `gh release
                 create` with notes that name the new commits. A second
                 release, after the changelog commit reached `production`
                 through `develop`, leaves it out of its notes and its bump,
                 and a release of nothing but that commit releases nothing.
                 A first release with no tag gives v0.1.0. A release cut
                 before the previous back-merge merged carries the previous
                 changelog forward, from either place it can be, resolves a
                 conflict in CHANGELOG.md, and names a section it could not
                 carry. A job that fails at `gh release create`, at the
                 back-merge push, at the tag push or at `gh pr create` is
                 finished by a re-run, with one tag, one GitHub Release and
                 one pull request, and a re-run of a finished release changes
                 nothing.

    NOT covered  GitHub itself: whether the token may push the tag, whether
                 the account permits Actions to open a pull request (the
                 premise gate's P11 arm), what `[skip ci]` does, and whether a
                 ruleset refuses a push to `production`. The stub's failures
                 are the ones these scripts can see, a non-zero exit from
                 `gh`, not GitHub's own error pages.

SPEED. Each release job is about a hundred short processes, so the scenarios
share work: one module-scoped history is released once, and every scenario
that starts from that release works on a copy of it rather than releasing it
again.

Depends on:
    - .github/workflows/release.yml
    - .github/release/*.sh

Writes:
    - Nothing outside pytest's own temporary directories.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"

# Long enough for a clone and a few dozen git calls; short enough that a hung
# script fails the suite rather than stalling it.
_TIMEOUT_S = 60

# The stand-in for the GitHub CLI. Each call writes its arguments, NUL
# separated, to `<n>.args`, and the notes it was piped to `<n>.stdin`. It
# keeps the state the scripts ask about: one line per GitHub Release created in
# `releases`, and one line per pull request opened, its head branch, in `prs`.
# Like GitHub, it refuses a second release for one tag and a second open pull
# request from one branch, so a script that makes a second one fails here.
#
# `fail-<command>-<subcommand>` makes that call fail with a 502, either
# `always` or for the number of calls it holds, counting down.
_STUB_GH = """#!/usr/bin/env bash
set -eu
d="$GH_STUB_DIR"
n="$(ls "$d" | grep -c '[.]args$' || true)"
printf '%s\\0' "$@" > "$d/$n.args"
case " $* " in
  *" --notes-file - "*) cat > "$d/$n.stdin" ;;
esac
fail="$d/fail-${1:-}-${2:-}"
if [ -f "$fail" ]; then
  left="$(cat "$fail")"
  if [ "$left" = always ] || [ "$left" -gt 0 ]; then
    [ "$left" = always ] || echo "$((left - 1))" > "$fail"
    echo "HTTP 502: Bad Gateway (stub)" >&2
    exit 1
  fi
fi
head_of() {
  while [ "$#" -gt 0 ]; do
    if [ "$1" = --head ]; then echo "$2"; return; fi
    shift
  done
}
touch "$d/releases" "$d/prs"
case "${1:-} ${2:-}" in
  "release view")
    grep -qxF -- "$3" "$d/releases" || { echo "release not found" >&2; exit 1; } ;;
  "release create")
    if grep -qxF -- "$3" "$d/releases"; then
      echo "a release for $3 already exists" >&2
      exit 1
    fi
    echo "$3" >> "$d/releases" ;;
  "pr list")
    grep -cxF -- "$(head_of "$@")" "$d/prs" || true ;;
  "pr create")
    head="$(head_of "$@")"
    if grep -qxF -- "$head" "$d/prs"; then
      echo "a pull request for $head already exists" >&2
      exit 1
    fi
    echo "$head" >> "$d/prs" ;;
esac
exit 0
"""

_CHANGELOG_PREAMBLE = "# Changelog\n\nEvery release, newest first.\n\n"


@dataclass
class GhCall:
    args: list[str]
    stdin: str


@dataclass
class ReleaseRun:
    outputs: dict[str, dict[str, str]]
    ran: list[str]
    gh_calls: list[GhCall] = field(default_factory=list)
    log: str = ""
    failed: str = ""


class ReleaseRepo:
    """A bare `origin`, the owner's working clone, and a runner for the job."""

    def __init__(self, root: Path, *, copy_of: ReleaseRepo | None = None) -> None:
        self.tmp = root
        self.origin = root / "origin.git"
        self.owner = root / "owner"
        self.bin = root / "bin"
        self.gh_dir = root / "gh-calls"
        self.home = root / "home"

        if copy_of is None:
            self._pull_request = 0
            self._runs = 0
            self._edits = 0
            self._build_tools()
        else:
            self._pull_request = copy_of._pull_request
            self._runs = copy_of._runs
            self._edits = copy_of._edits
            shutil.copytree(copy_of.tmp, root, symlinks=True, dirs_exist_ok=True)
        self.env = self._environment()

        if copy_of is None:
            self._run(["git", "init", "--quiet", "--bare", str(self.origin)], cwd=root)
            self._run(["git", "clone", "--quiet", str(self.origin), str(self.owner)], cwd=root)
            self.git("symbolic-ref", "HEAD", "refs/heads/develop")
        else:
            # The copy's clone still names the original's `origin` by path.
            self.git("remote", "set-url", "origin", str(self.origin))

    def fork(self, root: Path) -> ReleaseRepo:
        """An independent copy of this repository, history and remote alike."""
        return ReleaseRepo(root, copy_of=self)

    def _build_tools(self) -> None:
        for directory in (self.bin, self.gh_dir, self.home):
            directory.mkdir(parents=True)
        stub = self.bin / "gh"
        stub.write_text(_STUB_GH, encoding="utf-8")
        stub.chmod(0o755)
        # Isolated from the machine's own git configuration: a global hook, a
        # signing requirement or a default branch name must not reach here.
        (self.home / ".gitconfig").write_text(
            "[user]\n\tname = Repository Owner\n\temail = owner@example.invalid\n"
            "[init]\n\tdefaultBranch = develop\n",
            encoding="utf-8",
        )

    def _environment(self) -> dict[str, str]:
        environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        environment.update(
            {
                "HOME": str(self.home),
                "XDG_CONFIG_HOME": str(self.home / ".config"),
                "GIT_CONFIG_GLOBAL": str(self.home / ".gitconfig"),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_TERMINAL_PROMPT": "0",
                "GH_STUB_DIR": str(self.gh_dir),
                "RELEASE_RETRY_DELAY_S": "0",
                "PATH": f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}",
            }
        )
        return environment

    # -- plumbing ----------------------------------------------------------

    def _run(self, argv: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run(
            argv,
            cwd=str(cwd),
            env=self.env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
        if check and result.returncode != 0:
            raise AssertionError(
                f"{' '.join(argv)} exited {result.returncode}:\n{result.stdout}\n{result.stderr}"
            )
        return result

    def git(self, *args: str) -> str:
        return self._run(["git", *args], cwd=self.owner).stdout.strip()

    def origin_git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return self._run(["git", "--git-dir", str(self.origin), *args], cwd=self.tmp, check=check)

    def origin_ref(self, ref: str) -> str:
        """The commit or object a ref names on `origin`, or "" if it does not exist."""
        result = self.origin_git("rev-parse", "--verify", "--quiet", ref, check=False)
        return result.stdout.strip()

    def changelog_on(self, ref: str) -> str:
        return self.origin_git("show", f"{ref}:CHANGELOG.md").stdout

    def is_ancestor(self, older: str, newer: str) -> bool:
        return self.origin_git("merge-base", "--is-ancestor", older, newer, check=False).returncode == 0

    # -- the owner's actions -------------------------------------------------

    def commit(self, subject: str, *, changelog: str | None = None) -> None:
        """Commit on the current branch: a source edit, or a CHANGELOG.md body."""
        if changelog is None:
            self._edits += 1
            path = self.owner / f"module_{self._edits}.py"
            path.write_text(f"VALUE = {self._edits}\n", encoding="utf-8")
        else:
            path = self.owner / "CHANGELOG.md"
            path.write_text(changelog, encoding="utf-8")
        self.git("add", path.name)
        self.git("commit", "--quiet", "-m", subject)

    def push(self, *refs: str) -> None:
        self.git("push", "--quiet", "origin", *refs)

    def merge_pull_request(self, head: str, base: str) -> None:
        """What GitHub's merge button does: a merge commit on `base`, pushed."""
        self._pull_request += 1
        # Only the robot's branches arrive from origin. `develop` and
        # `production` are written by this clone alone, as by the owner's
        # account alone on GitHub, so this clone is never behind on them.
        if head.startswith("origin/"):
            self.git("fetch", "--quiet", "origin")
        self.git("checkout", "--quiet", base)
        branch = head.removeprefix("origin/")
        message = f"Merge pull request #{self._pull_request} from owner/{branch}"
        self.git("merge", "--quiet", "--no-ff", "-m", message, head)
        self.push(base)
        self.git("checkout", "--quiet", "develop")

    def release(self, source: str = "develop") -> None:
        """Merge a release into `production` the way the owner does."""
        self.merge_pull_request(source, "production")

    def merge_back_merge(self, version: str) -> None:
        """Merge the robot's back-merge pull request into `develop`, then delete its branch."""
        branch = f"chore/back-merge-{version}"
        self.merge_pull_request(f"origin/{branch}", "develop")
        self.git("push", "--quiet", "origin", "--delete", branch)

    def squash_merge_back_merge(self, version: str) -> None:
        """GitHub's squash button on the back-merge: one commit under the pull request's title."""
        self._pull_request += 1
        branch = f"chore/back-merge-{version}"
        self.git("fetch", "--quiet", "origin")
        self.git("checkout", "--quiet", "develop")
        self.git("merge", "--quiet", "--squash", f"origin/{branch}")
        title = f"chore: back-merge {version} into develop (#{self._pull_request})"
        self.git("commit", "--quiet", "-m", title)
        self.push("develop")
        self.git("push", "--quiet", "origin", "--delete", branch)

    # -- the release job -----------------------------------------------------

    def run_release_job(self, *, check: bool = True) -> ReleaseRun:
        """Run release.yml's steps in order, as GitHub would on a push to production.

        With `check=False`, a failing step ends the run the way it ends a job
        on GitHub, skipping every later step, and the run records its name.
        """
        self._runs += 1
        checkout = self.tmp / f"runner-{self._runs}"
        before = set(self.gh_dir.glob("*.args"))

        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        steps = workflow["jobs"]["release"]["steps"]
        outputs: dict[str, dict[str, str]] = {}
        ran: list[str] = []
        log: list[str] = []
        failed = ""

        for index, step in enumerate(steps):
            if "uses" in step:
                # The one step this runner stands in for. It must still be the
                # checkout this runner models, or every assertion below is
                # about a job the workflow no longer describes.
                settings = step.get("with", {})
                assert step["uses"].startswith("actions/checkout@"), step
                assert settings.get("ref") == "production", step
                assert settings.get("fetch-depth") == 0, step
                self._run(
                    [
                        "git",
                        "clone",
                        "--quiet",
                        "--branch",
                        "production",
                        str(self.origin),
                        str(checkout),
                    ],
                    cwd=self.tmp,
                )
                continue

            condition = step.get("if")
            if condition is not None and not _condition_holds(condition, outputs):
                continue

            step_output = self.tmp / f"output-{self._runs}-{index}"
            step_output.write_text("", encoding="utf-8")
            environment = {**self.env, "GITHUB_OUTPUT": str(step_output)}
            for key, value in (step.get("env") or {}).items():
                environment[key] = _resolve(value, outputs)

            script = step["run"].strip()
            result = subprocess.run(
                [str(REPO_ROOT / script)],
                cwd=str(checkout),
                env=environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_S,
                check=False,
            )
            log.append(f"$ {script}\n{result.stdout}{result.stderr}")
            if result.returncode != 0 and not check:
                failed = script
                break
            assert result.returncode == 0, (
                f"release step {step.get('name', script)!r} exited {result.returncode}:\n"
                + "\n".join(log)
            )
            ran.append(script)
            if "id" in step:
                outputs[step["id"]] = _read_outputs(step_output)

        calls = []
        for args_file in sorted(self.gh_dir.glob("*.args"), key=lambda p: int(p.stem)):
            if args_file in before:
                continue
            args = args_file.read_text(encoding="utf-8").split("\0")[:-1]
            stdin_file = args_file.with_suffix(".stdin")
            stdin = stdin_file.read_text(encoding="utf-8") if stdin_file.exists() else ""
            calls.append(GhCall(args=args, stdin=stdin))
        return ReleaseRun(
            outputs=outputs, ran=ran, gh_calls=calls, log="\n".join(log), failed=failed
        )

    # -- faults, and the state GitHub would hold -----------------------------

    def fail_gh(self, command: str, times: str = "always") -> None:
        """Make `gh <command>` answer 502, `always` or for `times` calls."""
        (self.gh_dir / f"fail-{command.replace(' ', '-')}").write_text(times, encoding="utf-8")

    def heal_gh(self) -> None:
        for fault in self.gh_dir.glob("fail-*"):
            fault.write_text("0", encoding="utf-8")

    def refuse_pushes(self, prefix: str) -> None:
        """Make `origin` refuse every push to a ref starting with `prefix`."""
        (self.tmp / "refuse").write_text(prefix, encoding="utf-8")
        hook = self.origin / "hooks" / "pre-receive"
        hook.write_text(
            "#!/usr/bin/env bash\n"
            f'prefix="$(cat "{self.tmp / "refuse"}" 2>/dev/null || true)"\n'
            "while read -r old new ref; do\n"
            '  if [ -n "$prefix" ] && [ "${ref#"$prefix"}" != "$ref" ]; then\n'
            '    echo "push to $ref refused (test)" >&2\n'
            "    exit 1\n"
            "  fi\n"
            "done\n",
            encoding="utf-8",
        )
        hook.chmod(0o755)

    def accept_pushes(self) -> None:
        (self.tmp / "refuse").write_text("", encoding="utf-8")

    def gh_state(self, name: str) -> list[str]:
        """What the stub recorded: `releases` created, or `prs` opened, by head branch."""
        path = self.gh_dir / name
        return path.read_text(encoding="utf-8").split() if path.exists() else []


def _condition_holds(condition: str, outputs: dict[str, dict[str, str]]) -> bool:
    match = re.fullmatch(r"steps\.(\w+)\.outputs\.(\w+) == '([^']*)'", condition.strip())
    assert match, f"this runner cannot evaluate the condition {condition!r}; teach it or simplify"
    step_id, name, expected = match.groups()
    return outputs.get(step_id, {}).get(name, "") == expected


def _resolve(value: object, outputs: dict[str, dict[str, str]]) -> str:
    text = str(value)
    match = re.fullmatch(r"\$\{\{\s*(.+?)\s*\}\}", text)
    if match is None:
        return text
    expression = match.group(1)
    if expression == "secrets.GITHUB_TOKEN":
        return "stub-token-reaches-nothing"
    output = re.fullmatch(r"steps\.(\w+)\.outputs\.(\w+)", expression)
    assert output, f"this runner cannot resolve ${{{{ {expression} }}}}; teach it or simplify"
    # GitHub resolves a missing output to the empty string, and so does this.
    return outputs.get(output.group(1), {}).get(output.group(2), "")


def _read_outputs(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            values[key] = value
    return values


def _call(run: ReleaseRun, *prefix: str) -> GhCall:
    matches = [c for c in run.gh_calls if c.args[: len(prefix)] == list(prefix)]
    assert len(matches) == 1, (
        f"expected one `gh {' '.join(prefix)}` call, saw {[c.args for c in run.gh_calls]}"
    )
    return matches[0]


def _headings(changelog: str) -> list[str]:
    return [line.split(" ")[1] for line in changelog.splitlines() if line.startswith("## ")]


# ---------------------------------------------------------------------------
# One history, released once: v0.1.0 tagged, two new commits, then v0.2.0
# ---------------------------------------------------------------------------


@dataclass
class Released:
    repo: ReleaseRepo
    run: ReleaseRun
    tip: str


@pytest.fixture(scope="module")
def released(tmp_path_factory: pytest.TempPathFactory) -> Released:
    """A released v0.1.0, a feat and a fix merged to production, and the job run once."""
    repo = ReleaseRepo(tmp_path_factory.mktemp("released"))
    repo.commit("chore: scaffold the package")
    repo.commit("feat: the first capability")
    repo.commit(
        "docs: the first changelog",
        changelog=_CHANGELOG_PREAMBLE
        + "## v0.1.0 (2026-01-01)\n\n### Features\n\n- the first capability\n",
    )
    repo.git("branch", "production")
    repo.git("tag", "-a", "v0.1.0", "-m", "Release v0.1.0")
    repo.push("develop", "production", "refs/tags/v0.1.0")

    repo.commit("feat(api): answer a question about two genes")
    repo.commit("fix: keep the citation beside its sentence")
    repo.push("develop")
    repo.release()
    tip = repo.origin_ref("refs/heads/production")
    return Released(repo=repo, run=repo.run_release_job(), tip=tip)


class TestOneRelease:
    """A release after v0.1.0: what reaches origin, what reaches GitHub."""

    def test_it_derives_v0_2_0_from_the_previous_tag(self, released: Released) -> None:
        version = released.run.outputs["version"]
        assert version["previous_tag"] == "v0.1.0", released.run.log
        assert version["version"] == "v0.2.0", released.run.log

    def test_production_does_not_move(self, released: Released) -> None:
        assert released.repo.origin_ref("refs/heads/production") == released.tip, (
            "the release job moved `production` on origin. It must never push to "
            "`production`: the owner's account is the only writer of that branch.\n"
            + released.run.log
        )

    def test_the_tag_is_annotated_and_on_production(self, released: Released) -> None:
        repo = released.repo
        assert repo.origin_ref("refs/tags/v0.2.0^{commit}") == released.tip, (
            "the v0.2.0 tag on origin is not on production's tip, so the release "
            "names code that is not what shipped.\n" + released.run.log
        )
        assert repo.origin_git("cat-file", "-t", "refs/tags/v0.2.0").stdout.strip() == "tag", (
            "the tag is lightweight; derive_version.sh relies on an annotated tag"
        )

    def test_the_changelog_commit_rides_the_back_merge_branch(self, released: Released) -> None:
        repo = released.repo
        branch = "refs/heads/chore/back-merge-v0.2.0"
        head = repo.origin_ref(branch)
        assert head, "the back-merge branch was not pushed to origin\n" + released.run.log
        subject = repo.origin_git("log", "-1", "--format=%s", head).stdout.strip()
        assert subject == "docs(changelog): release v0.2.0 [skip ci]"
        assert repo.origin_ref(f"{head}^") == released.tip, (
            "the changelog commit is not built on the production commit that was tagged"
        )
        assert _headings(repo.changelog_on(branch)) == ["v0.2.0", "v0.1.0"]

    def test_gh_opens_the_back_merge_into_develop(self, released: Released) -> None:
        pull_request = _call(released.run, "pr", "create")
        args = pull_request.args
        assert args[args.index("--base") + 1] == "develop"
        assert args[args.index("--head") + 1] == "chore/back-merge-v0.2.0"

    def test_gh_publishes_notes_naming_the_new_commits(self, released: Released) -> None:
        release = _call(released.run, "release", "create", "v0.2.0")
        assert "--verify-tag" in release.args
        assert "answer a question about two genes" in release.stdin, release.stdin
        assert "keep the citation beside its sentence" in release.stdin, release.stdin
        assert "the first capability" not in release.stdin, (
            "the notes list a commit from before the previous tag"
        )


# ---------------------------------------------------------------------------
# The changelog commit reaches production through develop, one release late
# ---------------------------------------------------------------------------


@dataclass
class NextReleases:
    repo: ReleaseRepo
    second: ReleaseRun
    second_tip: str
    second_after: str
    third: ReleaseRun
    third_tip: str


@pytest.fixture(scope="module")
def next_releases(released: Released, tmp_path_factory: pytest.TempPathFactory) -> NextReleases:
    """v0.2.0's back-merge merged, then a fix released, then nothing but the changelog."""
    repo = released.repo.fork(tmp_path_factory.mktemp("next"))
    repo.merge_back_merge("v0.2.0")
    repo.commit("fix: a sentence no longer loses its source")
    repo.push("develop")
    repo.release()
    second_tip = repo.origin_ref("refs/heads/production")
    second = repo.run_release_job()
    second_after = repo.origin_ref("refs/heads/production")

    repo.merge_back_merge("v0.2.1")
    repo.release()
    third_tip = repo.origin_ref("refs/heads/production")
    third = repo.run_release_job()
    return NextReleases(repo, second, second_tip, second_after, third, third_tip)


class TestTheNextRelease:
    def test_the_previous_tag_is_found_on_a_production_merge_commit(
        self, next_releases: NextReleases
    ) -> None:
        version = next_releases.second.outputs["version"]
        assert version["previous_tag"] == "v0.2.0", next_releases.second.log
        assert version["version"] == "v0.2.1", next_releases.second.log

    def test_the_changelog_commit_is_not_in_the_notes(self, next_releases: NextReleases) -> None:
        notes = _call(next_releases.second, "release", "create", "v0.2.1").stdin
        assert "a sentence no longer loses its source" in notes, notes
        assert "changelog" not in notes.lower(), (
            f"the v0.2.0 changelog commit is listed in the v0.2.1 notes:\n{notes}"
        )
        assert "internal" not in notes, (
            f"the v0.2.0 changelog commit was counted as an internal change:\n{notes}"
        )

    def test_it_tags_production_and_leaves_it_alone(self, next_releases: NextReleases) -> None:
        repo = next_releases.repo
        assert next_releases.second_after == next_releases.second_tip, next_releases.second.log
        assert repo.origin_ref("refs/tags/v0.2.1^{commit}") == next_releases.second_tip
        assert _headings(repo.changelog_on("refs/heads/develop")) == ["v0.2.1", "v0.2.0", "v0.1.0"]

    def test_a_release_of_only_the_changelog_commit_releases_nothing(
        self, next_releases: NextReleases
    ) -> None:
        """Counted as a commit, the changelog alone would publish a patch version."""
        third = next_releases.third
        repo = next_releases.repo
        assert third.outputs["version"]["should_release"] == "false", third.log
        assert third.ran == [".github/release/derive_version.sh"], third.ran
        assert third.gh_calls == [], [c.args for c in third.gh_calls]
        assert repo.origin_ref("refs/tags/v0.2.2") == ""
        assert repo.origin_ref("refs/heads/production") == next_releases.third_tip


# ---------------------------------------------------------------------------
# No tag at all: the whole history is the first release
# ---------------------------------------------------------------------------


def test_a_first_release_with_no_tag_is_v0_1_0(tmp_path: Path) -> None:
    repo = ReleaseRepo(tmp_path)
    repo.commit("chore: scaffold the package")
    repo.commit("feat: the first capability")
    repo.commit("fix: the first repair")
    repo.git("branch", "production")
    repo.push("develop", "production")
    tip = repo.origin_ref("refs/heads/production")

    run = repo.run_release_job()

    assert run.outputs["version"]["previous_tag"] == ""
    assert run.outputs["version"]["version"] == "v0.1.0", run.log
    assert repo.origin_ref("refs/tags/v0.1.0^{commit}") == tip
    assert repo.origin_ref("refs/heads/production") == tip
    notes = _call(run, "release", "create", "v0.1.0").stdin
    assert "the first capability" in notes and "the first repair" in notes, notes
    changelog = repo.changelog_on("refs/heads/chore/back-merge-v0.1.0")
    assert changelog.startswith("# Changelog"), changelog
    assert _headings(changelog) == ["v0.1.0"]


# ---------------------------------------------------------------------------
# The next release is cut before the owner merged the previous back-merge
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("where", ["branch still open", "merged after the cut"])
def test_an_unmerged_back_merge_is_carried_forward(
    released: Released, tmp_path: Path, where: str
) -> None:
    repo = released.repo.fork(tmp_path / "repo")
    carried = repo.origin_ref("refs/heads/chore/back-merge-v0.2.0")
    repo.commit("fix: a follow-up question keeps its gene")
    repo.push("develop")
    if where == "branch still open":
        repo.release()
    else:
        repo.git("branch", "release/v0.2.1", "develop")
        repo.push("release/v0.2.1")
        repo.merge_back_merge("v0.2.0")
        repo.release(source="origin/release/v0.2.1")
    tip = repo.origin_ref("refs/heads/production")

    run = repo.run_release_job()

    assert run.outputs["version"]["version"] == "v0.2.1", run.log
    assert repo.origin_ref("refs/heads/production") == tip
    assert repo.origin_ref("refs/tags/v0.2.1^{commit}") == tip, (
        "the tag is not on production's tip; it may have moved onto the carry merge"
    )
    branch = "refs/heads/chore/back-merge-v0.2.1"
    assert _headings(repo.changelog_on(branch)) == ["v0.2.1", "v0.2.0", "v0.1.0"], (
        "the v0.2.0 section is missing from the v0.2.1 changelog\n" + run.log
    )
    assert repo.is_ancestor(carried, repo.origin_ref(branch)), (
        "the v0.2.1 back-merge does not contain the v0.2.0 changelog commit"
    )

    notes = _call(run, "release", "create", "v0.2.1").stdin
    assert "a follow-up question keeps its gene" in notes, notes
    assert "answer a question about two genes" not in notes, (
        f"the v0.2.1 notes list v0.2.0's commits:\n{notes}"
    )
    assert "changelog" not in notes.lower(), notes

    # And the owner can merge the new back-merge without a conflict.
    repo.merge_back_merge("v0.2.1")
    assert _headings(repo.changelog_on("refs/heads/develop")) == ["v0.2.1", "v0.2.0", "v0.1.0"]


def test_a_squash_merged_back_merge_is_carried_forward(released: Released, tmp_path: Path) -> None:
    """Findings F-REL-A05 and F-REL-J13: the carry and the notes read one subject list.

    commit_lib.sh recognises a back-merge squash-merged into `develop`, under
    the pull request's title, as the changelog commit it is. The carry step
    used to look only for the robot's own subject, so a release cut before
    that squash merge landed lost the previous section, and its back-merge then
    conflicted on CHANGELOG.md.
    """
    repo = released.repo.fork(tmp_path / "repo")
    repo.commit("fix: a follow-up question keeps its gene")
    repo.push("develop")
    repo.git("branch", "release/v0.2.1", "develop")
    repo.push("release/v0.2.1")
    repo.squash_merge_back_merge("v0.2.0")
    repo.release(source="origin/release/v0.2.1")
    tip = repo.origin_ref("refs/heads/production")

    run = repo.run_release_job()

    assert run.outputs["version"]["version"] == "v0.2.1", run.log
    assert repo.origin_ref("refs/heads/production") == tip
    assert repo.origin_ref("refs/tags/v0.2.1^{commit}") == tip
    branch = "refs/heads/chore/back-merge-v0.2.1"
    assert _headings(repo.changelog_on(branch)) == ["v0.2.1", "v0.2.0", "v0.1.0"], (
        "the squash-merged v0.2.0 section was not carried into v0.2.1\n" + run.log
    )
    notes = _call(run, "release", "create", "v0.2.1").stdin
    assert "a follow-up question keeps its gene" in notes, notes
    assert "back-merge" not in notes and "changelog" not in notes.lower(), notes

    repo.merge_back_merge("v0.2.1")
    assert _headings(repo.changelog_on("refs/heads/develop")) == ["v0.2.1", "v0.2.0", "v0.1.0"]


def _pr_body(run: ReleaseRun) -> str:
    args = _call(run, "pr", "create").args
    return args[args.index("--body") + 1]


def test_a_carry_that_conflicts_keeps_both_sections(released: Released, tmp_path: Path) -> None:
    """Finding F-REL-J03: a conflicting carry dropped the previous section in silence.

    The owner corrects the v0.1.0 heading on `develop` while the v0.2.0
    back-merge is still open, so carrying the v0.2.0 changelog commit
    conflicts on the lines around that heading. The previous changelog commit
    changes CHANGELOG.md and nothing else, and all it adds is its own section,
    so the correct resolution is known: this checkout's file, the owner's
    correction included, with the v0.2.0 section placed above the newest one.
    """
    repo = released.repo.fork(tmp_path / "repo")
    carried = repo.origin_ref("refs/heads/chore/back-merge-v0.2.0")
    repo.commit(
        "docs: correct the v0.1.0 date",
        changelog=_CHANGELOG_PREAMBLE
        + "## v0.1.0 (2026-01-02)\n\n### Features\n\n- the first capability\n",
    )
    repo.commit("fix: a follow-up question keeps its gene")
    repo.push("develop")
    repo.release()
    tip = repo.origin_ref("refs/heads/production")

    run = repo.run_release_job()

    assert repo.origin_ref("refs/heads/production") == tip
    assert repo.origin_ref("refs/tags/v0.2.1^{commit}") == tip
    branch = "refs/heads/chore/back-merge-v0.2.1"
    changelog = repo.changelog_on(branch)
    assert _headings(changelog) == ["v0.2.1", "v0.2.0", "v0.1.0"], (
        "the v0.2.0 section was lost when carrying it conflicted\n" + run.log
    )
    assert "## v0.1.0 (2026-01-02)" in changelog, "the owner's correction was lost"
    assert "\n\n\n" not in changelog and "\n## " not in changelog.replace("\n\n## ", ""), (
        f"a section seam is not exactly one blank line:\n{changelog}"
    )
    assert repo.is_ancestor(carried, repo.origin_ref(branch))
    assert "has no v0.2.0 section" not in _pr_body(run)

    repo.merge_back_merge("v0.2.1")
    repo.merge_back_merge("v0.2.0")
    develop = repo.changelog_on("refs/heads/develop")
    assert _headings(develop) == ["v0.2.1", "v0.2.0", "v0.1.0"], develop
    assert "## v0.1.0 (2026-01-02)" in develop


def test_a_previous_section_that_cannot_be_carried_is_named_out_loud(
    released: Released, tmp_path: Path
) -> None:
    """Finding F-REL-J03, the other half: when nothing can be carried, say so.

    The owner deleted the v0.2.0 back-merge branch without merging it, so its
    changelog commit is on no branch the job can read. The release still goes
    out, and both the job's log and the v0.2.1 back-merge pull request name
    the missing section and say how to add it.
    """
    repo = released.repo.fork(tmp_path / "repo")
    repo.git("push", "--quiet", "origin", "--delete", "chore/back-merge-v0.2.0")
    repo.commit("fix: a follow-up question keeps its gene")
    repo.push("develop")
    repo.release()

    run = repo.run_release_job()

    assert run.outputs["version"]["version"] == "v0.2.1", run.log
    branch = "refs/heads/chore/back-merge-v0.2.1"
    assert _headings(repo.changelog_on(branch)) == ["v0.2.1", "v0.1.0"]
    assert (
        "::warning title=CHANGELOG.md is missing v0.2.0::No changelog commit for v0.2.0"
        in run.log
    ), run.log
    body = _pr_body(run)
    assert "has no v0.2.0 section" in body, body
    assert "v0.2.0 GitHub Release" in body, body


# ---------------------------------------------------------------------------
# A commit that borrows the robot's subject is still a commit
# ---------------------------------------------------------------------------


def _repo_at_v0_1_0(root: Path) -> tuple[ReleaseRepo, str]:
    """v0.1.0 tagged on `production`, with its changelog section, and nothing since."""
    repo = ReleaseRepo(root)
    repo.commit("chore: scaffold the package")
    changelog = (
        _CHANGELOG_PREAMBLE + "## v0.1.0 (2026-01-01)\n\n### Features\n\n- the first capability\n"
    )
    repo.commit("docs: the first changelog", changelog=changelog)
    repo.git("branch", "production")
    repo.git("tag", "-a", "v0.1.0", "-m", "Release v0.1.0")
    repo.push("develop", "production", "refs/tags/v0.1.0")
    return repo, changelog


def test_a_commit_borrowing_the_robots_subject_is_counted(tmp_path: Path) -> None:
    """Findings F-REL-A09 and F-REL-J02: the second half of "left out" had no test.

    The release job leaves its own changelog commit out of the next release,
    recognised by its subject AND by it changing CHANGELOG.md alone. Each
    commit below fails one of those two conditions, so each must be counted:
    one takes the exact subject but changes code, and three change only
    CHANGELOG.md under a subject that merely contains the robot's. Replacing
    the file check with `true`, or unanchoring either end of either subject
    pattern in commit_lib.sh, hides one of them and turns this red.
    """
    repo, changelog = _repo_at_v0_1_0(tmp_path)
    repo.commit("docs(changelog): release v0.2.0 [skip ci]")
    repo.commit(
        "docs(changelog): release v0.2.0 [skip ci] and the answer cites two genes",
        changelog=changelog + "\nOne.\n",
    )
    repo.commit("fix: docs(changelog): release v0.2.0 [skip ci]", changelog=changelog + "\nTwo.\n")
    repo.commit(
        "chore: back-merge v0.2.0 into develop (#7) and a new tool",
        changelog=changelog + "\nThree.\n",
    )
    repo.push("develop")
    repo.release()

    run = repo.run_release_job()

    version = run.outputs["version"]
    assert version["should_release"] == "true", run.log
    assert version["version"] == "v0.1.1", run.log
    assert "(4 commits)" in run.log, run.log
    notes = _call(run, "release", "create", "v0.1.1").stdin
    assert "docs(changelog): release v0.2.0 \\[skip ci\\]" in notes, (
        f"the `fix:` commit that quotes the robot's subject is missing:\n{notes}"
    )
    assert "Plus 3 internal changes" in notes, (
        f"a commit that borrows the robot's subject was hidden from the notes:\n{notes}"
    )


# ---------------------------------------------------------------------------
# A release's notes are its own section, and only its own
# ---------------------------------------------------------------------------


def test_the_notes_stop_at_the_next_heading_even_one_for_the_same_version(
    tmp_path: Path,
) -> None:
    """Finding F-REL-J11: a second heading for the same version doubled the notes.

    The owner drafts a section by hand under the version the release will get.
    The job then writes its own section above it, so CHANGELOG.md carries two
    headings for one version. The notes are the job's section alone: the
    reader stops at the next `## ` heading whatever that heading says.
    """
    repo, changelog = _repo_at_v0_1_0(tmp_path)
    draft = changelog.replace(
        "## v0.1.0",
        "## v0.1.1 (draft)\n\n- a note written by hand before the release\n\n## v0.1.0",
    )
    repo.commit("docs: draft the next release's notes", changelog=draft)
    repo.commit("fix: keep the citation beside its sentence")
    repo.push("develop")
    repo.release()

    run = repo.run_release_job()

    assert run.outputs["version"]["version"] == "v0.1.1", run.log
    notes = _call(run, "release", "create", "v0.1.1").stdin
    assert "keep the citation beside its sentence" in notes, notes
    assert "a note written by hand" not in notes, (
        f"the notes ran on into a second v0.1.1 section:\n{notes}"
    )


# ---------------------------------------------------------------------------
# A release that fails part way is finished by re-running it
# ---------------------------------------------------------------------------


def _repo_ready_for_v0_2_0(root: Path) -> tuple[ReleaseRepo, str]:
    """v0.1.0 released; a feat and a fix merged to `production`; the job not yet run."""
    repo, _ = _repo_at_v0_1_0(root)
    repo.commit("feat(api): answer a question about two genes")
    repo.commit("fix: keep the citation beside its sentence")
    repo.push("develop")
    repo.release()
    return repo, repo.origin_ref("refs/heads/production")


_TAG_AND_RELEASE = ".github/release/tag_and_release.sh"
_OPEN_BACKMERGE = ".github/release/open_backmerge_pr.sh"


@pytest.mark.parametrize(
    ("fault", "stops_at", "left_behind"),
    [
        # What the failed first run leaves on origin and on GitHub:
        # (tag, back-merge branch, GitHub Release).
        ("gh release create answers 502", _TAG_AND_RELEASE, (True, True, False)),
        ("the back-merge push is refused", _TAG_AND_RELEASE, (False, False, False)),
        ("the tag push is refused", _TAG_AND_RELEASE, (False, True, False)),
        ("gh pr create answers 502", _OPEN_BACKMERGE, (True, True, True)),
    ],
)
def test_a_release_that_failed_part_way_is_finished_by_a_re_run(
    tmp_path: Path, fault: str, stops_at: str, left_behind: tuple[bool, bool, bool]
) -> None:
    """Findings F-REL-A04 and F-REL-J01: a failure after the tag lost the changelog.

    The job used to push the tag, then publish the GitHub Release, and push the
    changelog commit only in the next script. A 502 from `gh release create`
    left a tag with no release and a changelog commit on the discarded runner,
    and a re-run saw the tag, released nothing and reported success.

    Now, whatever fails: the changelog commit is on origin whenever the tag is,
    `production` never moves, and a re-run finishes the release with exactly
    one tag, one GitHub Release and one pull request, reusing the changelog
    commit an earlier run pushed rather than writing a second one.
    """
    repo, tip = _repo_ready_for_v0_2_0(tmp_path)
    branch = "refs/heads/chore/back-merge-v0.2.0"
    if fault.startswith("gh release create"):
        repo.fail_gh("release create")
    elif fault.startswith("gh pr create"):
        repo.fail_gh("pr create")
    elif "back-merge" in fault:
        repo.refuse_pushes("refs/heads/chore/")
    else:
        repo.refuse_pushes("refs/tags/")

    first = repo.run_release_job(check=False)

    assert first.failed == stops_at, first.log
    assert repo.origin_ref("refs/heads/production") == tip, first.log
    tag = repo.origin_ref("refs/tags/v0.2.0")
    pushed = repo.origin_ref(branch)
    assert (bool(tag), bool(pushed), repo.gh_state("releases") == ["v0.2.0"]) == left_behind, (
        first.log
    )
    if tag:
        assert _headings(repo.changelog_on(branch)) == ["v0.2.0", "v0.1.0"], (
            "the tag reached origin without the changelog beside it\n" + first.log
        )
    assert repo.gh_state("prs") == []

    repo.heal_gh()
    repo.accept_pushes()
    second = repo.run_release_job()

    assert repo.origin_ref("refs/heads/production") == tip, second.log
    assert repo.origin_ref("refs/tags/v0.2.0^{commit}") == tip, second.log
    if tag:
        assert second.outputs["version"]["bump"] == "resume", second.log
        assert repo.origin_ref("refs/tags/v0.2.0") == tag, "the re-run made a second tag"
    if pushed:
        assert repo.origin_ref(branch) == pushed, (
            "the re-run wrote a second changelog commit instead of reusing the pushed one"
        )
        assert ".github/release/write_changelog.sh" not in second.ran, second.ran
    assert _headings(repo.changelog_on(branch)) == ["v0.2.0", "v0.1.0"], second.log
    assert repo.gh_state("releases") == ["v0.2.0"], "not exactly one GitHub Release"
    assert repo.gh_state("prs") == ["chore/back-merge-v0.2.0"], "not exactly one pull request"
    creates = [c for c in first.gh_calls + second.gh_calls if c.args[:2] == ["release", "create"]]
    assert "answer a question about two genes" in creates[-1].stdin, creates[-1].stdin
    assert "keep the citation beside its sentence" in creates[-1].stdin, creates[-1].stdin


def test_the_github_release_waits_out_a_tag_the_api_has_not_seen_yet(tmp_path: Path) -> None:
    """Finding F-REL-A04: `--verify-tag` can race the tag push, so it retries, boundedly."""
    repo, tip = _repo_ready_for_v0_2_0(tmp_path)
    repo.fail_gh("release create", "2")

    run = repo.run_release_job()

    creates = [c for c in run.gh_calls if c.args[:2] == ["release", "create"]]
    assert len(creates) == 3, [c.args for c in run.gh_calls]
    assert all("--verify-tag" in c.args for c in creates)
    assert repo.gh_state("releases") == ["v0.2.0"]
    assert repo.origin_ref("refs/tags/v0.2.0^{commit}") == tip


@pytest.mark.parametrize("back_merge", ["still open", "merged"])
def test_re_running_a_finished_release_changes_nothing(
    released: Released, tmp_path: Path, back_merge: str
) -> None:
    """A re-run of a release that already finished creates nothing and moves nothing."""
    repo = released.repo.fork(tmp_path / "repo")
    if back_merge == "merged":
        repo.merge_back_merge("v0.2.0")
    refs = ("refs/tags/v0.2.0", "refs/heads/chore/back-merge-v0.2.0", "refs/heads/production")
    before = {ref: repo.origin_ref(ref) for ref in refs}
    releases, prs = repo.gh_state("releases"), repo.gh_state("prs")

    run = repo.run_release_job()

    assert run.outputs["version"]["bump"] == "resume", run.log
    assert {ref: repo.origin_ref(ref) for ref in refs} == before, run.log
    made = [c.args for c in run.gh_calls if c.args[1:2] == ["create"]]
    assert made == [], made
    assert (repo.gh_state("releases"), repo.gh_state("prs")) == (releases, prs)


def test_a_tag_made_by_hand_on_production_is_not_released_again(tmp_path: Path) -> None:
    """Only a tag this job made is picked up; the owner's hand tag still means nothing to do.

    The data engineering repository's first release, v1.0.0, is tagged by hand
    on the commit `production` is created from, so that the robot releases
    nothing on that first push. Picking a release up by its tag must not
    change that.
    """
    repo = ReleaseRepo(tmp_path)
    repo.commit("Phase 1.0: schema scaffolding")
    repo.commit("fix: CITATION.cff states no version")
    repo.git("tag", "-a", "v1.0.0", "-m", "Release v1.0.0")
    repo.push("refs/tags/v1.0.0")
    repo.git("branch", "production")
    repo.push("develop", "production")

    run = repo.run_release_job()

    assert run.outputs["version"]["should_release"] == "false", run.log
    assert run.ran == [".github/release/derive_version.sh"], run.ran
    assert run.gh_calls == []


def test_a_changelog_left_for_another_production_commit_is_not_reused(tmp_path: Path) -> None:
    """A run that failed before tagging, then a new push to `production`.

    The first run pushed the v0.2.0 back-merge branch for production commit A,
    then its tag push failed. Before anyone re-ran it, another release moved
    `production` to B, whose run also computes v0.2.0. The changelog on the
    branch lists A's commits only, so reusing it would publish notes that miss
    B's. The run stops before anything permanent, and says which branch to
    delete; once it is deleted, the re-run releases v0.2.0 with both.
    """
    repo, first_tip = _repo_ready_for_v0_2_0(tmp_path)
    repo.refuse_pushes("refs/tags/")
    first = repo.run_release_job(check=False)
    assert first.failed == _TAG_AND_RELEASE, first.log
    left = repo.origin_ref("refs/heads/chore/back-merge-v0.2.0")
    assert left, first.log
    repo.accept_pushes()

    repo.commit("fix: a follow-up question keeps its gene")
    repo.push("develop")
    repo.release()
    tip = repo.origin_ref("refs/heads/production")

    second = repo.run_release_job(check=False)

    assert second.failed == ".github/release/resume_release.sh", second.log
    assert "Stale changelog for v0.2.0" in second.log, second.log
    assert "delete that branch on GitHub" in second.log, second.log
    assert repo.origin_ref("refs/tags/v0.2.0") == ""
    assert repo.origin_ref("refs/heads/chore/back-merge-v0.2.0") == left
    assert repo.gh_state("releases") == []

    repo.git("push", "--quiet", "origin", "--delete", "chore/back-merge-v0.2.0")
    third = repo.run_release_job()

    assert repo.origin_ref("refs/tags/v0.2.0^{commit}") == tip, third.log
    assert repo.origin_ref("refs/heads/production") == tip
    notes = _call(third, "release", "create", "v0.2.0").stdin
    assert "answer a question about two genes" in notes, notes
    assert "a follow-up question keeps its gene" in notes, notes
    assert first_tip != tip
