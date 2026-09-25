"""Bin the overnight build of 2026-09-25, whole or one phase at a time.

The product owner's instruction, 2026-09-25: "do not completely destroy what
we have on develop today. Build a mechanism that if I do not like what you
built overnight, we can bin it."

How it works:
    - The rollback point is the git tag `pre-overnight-2026-09-25`, pushed to
      GitHub before any overnight code landed. Develop's product code at that
      tag is identical to `f3aaf6f`, where the session started.
    - `--all` puts every product path back exactly as it was at the tag, as
      ONE new commit on develop. Nothing is force-pushed and no history is
      lost. Documents (DECISIONS.md, the plan, the board) are not product
      paths, so the record of what was tried stays.
    - `--phase 8.N` reverts only that phase's merge commit, so one phase can
      be binned and the others kept.
    - Railway settings changed overnight are logged in
      `testing/Overnight_settings_log.json` with their value before; binning
      puts each back (or deletes it, if it did not exist before).
    - Tonight's work adds no database migration, by the plan's own rule, so
      restoring the code is a complete undo.

Usage, from the repository root, on an up-to-date `develop` with a clean tree:
    python3 testing/Developer/scripts/bin_overnight.py --list
    python3 testing/Developer/scripts/bin_overnight.py --all            # shows the plan only
    python3 testing/Developer/scripts/bin_overnight.py --all --yes      # does it
    python3 testing/Developer/scripts/bin_overnight.py --phase 8.2 --yes

Develop redeploys on the push. Confirm with `railway deployment list
--service search-agent-api` and `--service search-agent-web`: the newest
deployment reads SUCCESS. The deployments serving develop at the rollback
point were API `008542c2-d69c-4bb5-9398-ef1ad0efe8ec` and web
`88ccc316-dea5-4589-9053-aaded1d20ee2`; any deployment of a commit at or
before the tag serves the same product.

Depends on: git, and the `railway` command-line tool for settings.
Writes: one commit on develop, pushed to origin; Railway variables on the
develop environment only, never production.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

TAG = "pre-overnight-2026-09-25"
PRODUCT_PATHS = [
    "src",
    "frontend",
    "tests",
    "services",
    "eval",
    "alembic",
    "alembic.ini",
    "requirements.txt",
    "requirements",
    "pyproject.toml",
    "railway.json",
    "env.example",
    ".github",
]
SETTINGS_LOG = Path("testing/Overnight_settings_log.json")


def git(*args: str, check: bool = True) -> str:
    out = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if check and out.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout.strip()


def preflight(no_push: bool) -> None:
    if git("rev-parse", "--abbrev-ref", "HEAD") != "develop":
        sys.exit("Switch to develop first: git checkout develop")
    if git("status", "--porcelain"):
        sys.exit("The working tree has changes. Commit or set them aside first.")
    if not git("rev-parse", "-q", "--verify", f"refs/tags/{TAG}", check=False):
        git("fetch", "-q", "origin", f"refs/tags/{TAG}:refs/tags/{TAG}")
    if not no_push:
        git("fetch", "-q", "origin", "develop")
        if git("rev-parse", "HEAD") != git("rev-parse", "origin/develop"):
            sys.exit("Local develop differs from origin/develop. Run: git pull --ff-only origin develop")


def existing_paths(ref: str) -> list[str]:
    listed = set(git("ls-tree", "--name-only", ref).splitlines())
    return [p for p in PRODUCT_PATHS if p in listed]


def overnight_merges() -> list[tuple[str, str]]:
    log = git("log", "--merges", "--format=%H %s", f"{TAG}..HEAD")
    return [tuple(line.split(" ", 1)) for line in log.splitlines() if line]


def load_settings(phase: str | None) -> list[dict]:
    if not SETTINGS_LOG.exists():
        return []
    rows = json.loads(SETTINGS_LOG.read_text())
    return [r for r in rows if phase is None or r.get("phase") == phase]


def restore_settings(rows: list[dict], yes: bool) -> None:
    # Undo newest first, so a setting changed twice lands on its first value.
    for r in reversed(rows):
        svc, name, before = r["service"], r["name"], r.get("before")
        if before is None:
            cmd = ["railway", "variable", "delete", name, "--service", svc, "--environment", "develop"]
        else:
            cmd = ["railway", "variable", "set", f"{name}={before}", "--service", svc, "--environment", "develop"]
        print("  " + " ".join(cmd))
        if yes:
            subprocess.run(cmd, check=True)


def push(no_push: bool) -> None:
    if no_push:
        print("Not pushed (--no-push).")
        return
    git("push", "-q", "origin", "develop")
    git("fetch", "-q", "origin", "develop")
    local, remote = git("rev-parse", "HEAD"), git("rev-parse", "origin/develop")
    if local != remote:
        sys.exit(f"Push did not land: local {local[:7]}, origin {remote[:7]}")
    print(f"Pushed. develop and origin/develop are both {local[:7]}. Develop redeploys now.")


def bin_all(yes: bool, no_push: bool) -> None:
    paths = sorted(set(existing_paths(TAG)) | set(existing_paths("HEAD")))
    changed = git("diff", "--name-status", TAG, "HEAD", "--", *paths)
    settings = load_settings(None)
    if not changed and not settings:
        print("Nothing to bin: develop's product code already matches the rollback point.")
        return
    print(f"Product files that differ from {TAG}:")
    print("\n".join("  " + line for line in changed.splitlines()) or "  none")
    print("Railway settings to put back:")
    restore_settings(settings, yes=False) if settings else print("  none")
    if not yes:
        print("\nNothing changed. Re-run with --yes to bin the overnight build.")
        return
    added = git("diff", "--name-only", "--diff-filter=A", TAG, "HEAD", "--", *paths).splitlines()
    if added:
        git("rm", "-q", "--", *added)
    git("restore", f"--source={TAG}", "--staged", "--worktree", "--", *existing_paths(TAG))
    if not git("diff", "--cached", "--name-only"):
        print("No product change to commit.")
    else:
        git("commit", "-q", "-m", f"revert: bin the overnight build, product code back to {TAG}\n\n"
            "The product owner's call after reviewing the overnight build of 2026-09-25.\n"
            "Documents and decisions are kept; product paths match the tag exactly.")
    if git("diff", "--stat", TAG, "HEAD", "--", *paths):
        sys.exit("Product paths still differ from the tag after the restore. Stop and inspect.")
    print(f"Verified: every product path matches {TAG}.")
    restore_settings(settings, yes=True)
    push(no_push)


def bin_phase(phase: str, yes: bool, no_push: bool) -> None:
    hits = [(sha, subj) for sha, subj in overnight_merges() if f"phase/{phase}-" in subj]
    if len(hits) != 1:
        sys.exit(f"Expected one merge for phase {phase} since {TAG}, found {len(hits)}: {hits}")
    sha, subj = hits[0]
    settings = load_settings(phase)
    print(f"Will revert {sha[:7]}: {subj}")
    print("Railway settings to put back:")
    restore_settings(settings, yes=False) if settings else print("  none")
    if not yes:
        print("\nNothing changed. Re-run with --yes to bin this phase.")
        return
    git("revert", "-m", "1", "--no-edit", sha)
    restore_settings(settings, yes=True)
    push(no_push)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="show the rollback point, the overnight merges and logged settings")
    g.add_argument("--all", action="store_true", help="bin the whole overnight build")
    g.add_argument("--phase", help="bin one phase, for example 8.2")
    ap.add_argument("--yes", action="store_true", help="actually do it; without this only the plan is shown")
    ap.add_argument("--no-push", action="store_true", help="for testing: commit locally, do not push")
    args = ap.parse_args()
    preflight(args.no_push)
    if args.list:
        print(f"Rollback point: {TAG} = {git('rev-parse', '--short', TAG + '^{commit}')}")
        merges = overnight_merges()
        print(f"Overnight merges on develop since then: {len(merges)}")
        for sha, subj in merges:
            print(f"  {sha[:7]} {subj}")
        rows = load_settings(None)
        print(f"Railway settings changed overnight: {len(rows)}")
        for r in rows:
            print(f"  phase {r.get('phase')}: {r['service']} {r['name']}, before {r.get('before')!r}, after {r.get('after')!r}")
    elif args.all:
        bin_all(args.yes, args.no_push)
    else:
        bin_phase(args.phase, args.yes, args.no_push)


if __name__ == "__main__":
    main()
