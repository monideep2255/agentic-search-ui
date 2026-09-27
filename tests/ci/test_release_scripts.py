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
handed, and reaches nothing.

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
                 changelog forward, from either place it can be.

    NOT covered  GitHub itself: whether the token may push the tag, whether
                 the account permits Actions to open a pull request (the
                 premise gate's P11 arm), what `[skip ci]` does, and whether a
                 ruleset refuses a push to `production`. The stub accepts
                 anything, so `gh` failures are not exercised either.

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
# separated, to `<n>.args`, and the notes it was piped to `<n>.stdin`.
_STUB_GH = """#!/usr/bin/env bash
set -eu
n="$(ls "$GH_STUB_DIR" | grep -c '[.]args$' || true)"
printf '%s\\0' "$@" > "$GH_STUB_DIR/$n.args"
case " $* " in
  *" --notes-file - "*) cat > "$GH_STUB_DIR/$n.stdin" ;;
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

    # -- the release job -----------------------------------------------------

    def run_release_job(self) -> ReleaseRun:
        """Run release.yml's steps in order, as GitHub would on a push to production."""
        self._runs += 1
        checkout = self.tmp / f"runner-{self._runs}"
        before = set(self.gh_dir.glob("*.args"))

        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        steps = workflow["jobs"]["release"]["steps"]
        outputs: dict[str, dict[str, str]] = {}
        ran: list[str] = []
        log: list[str] = []

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
        return ReleaseRun(outputs=outputs, ran=ran, gh_calls=calls, log="\n".join(log))


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
