# Release fix review record

The release job change in both repositories, pull requests #125 (System 3) and #9 (data engineering). The robot tags `production`'s tip and never pushes to it. The changelog reaches `develop` through a back-merge pull request.

The change had one judge round and one adversary round. One fix round followed, then a fresh verifier. This file records the verifier's verdicts, filed by the lead from its final message on 2026-09-27. The probes it ran lived in a temporary folder and are not kept.

## Table of contents

- [Verdicts](#verdicts)
- [Findings fixed in the fix round](#findings-fixed-in-the-fix-round)
- [Findings left open](#findings-left-open)
- [What the owner decided](#what-the-owner-decided)

## Verdicts

| Round | Verdict | Blocking |
|---|---|---|
| Judge and adversary | FAIL | F-REL-A04, the same as F-REL-J01 |
| Fix round | every finding in the brief addressed, each with a test red on the old scripts and green on the new | none claimed |
| Fresh verifier, at d172e1e7 and 5cf2376 | DO NOT MERGE, both repositories | F-REL-V05, inside the fix |

The verifier ran every test file against the base scripts and the head:

- System 3: 13 failed and 18 passed at base, 31 passed at head.
- Data engineering: 13 failed and 19 passed at base, 32 passed at head.
- Mutations on System 3's head: 24 of 25 went red.
- Gates: System 3 `pytest tests/ci` 412 passed; ruff, isort and the doc drift check exit 0. Data engineering: 262 passed.
- The only pushes in either copy are the back-merge branch by `refs/heads/` and the tag by `refs/tags/`. Nothing pushes to `production`.
- With comments stripped, the two copies differ only in `write_changelog.sh`'s preamble and `open_backmerge_pr.sh`'s no-CI paragraph.

## Findings fixed in the fix round

- F-REL-A04 and F-REL-J01: a failure after the tag push lost the changelog, and a re-run did nothing. Now the back-merge branch is pushed before the tag, and a re-run finishes the release with exactly one tag, one GitHub Release and one pull request.
- F-REL-A05 and F-REL-J13: the carry step finds the previous changelog commit on its back-merge branch or on `develop`.
- F-REL-J03, for one unmerged back-merge only: a changelog conflict keeps both sections, and a missing one is named in the pull request.
- F-REL-J11: a release's notes stop at the next changelog heading.
- F-REL-A09 and F-REL-J02: a commit that borrows the robot's subject is still counted.
- F-REL-J08: a `!` or a breaking-change footer raises the major version.
- F-REL-J04 and F-REL-A10: the tag is pushed by its full name, and a tag on a commit that is not on `production` is refused.
- F-REL-A02: both release documents say to merge into `production` with a merge commit.
- F-REL-A06 and F-REL-J10: data engineering's document says to push the hand-made v1.0.0 tag before `production` exists.

## Findings left open

- F-REL-V05, major, inside the J03 fix (System 3 2f1ef6fd, data engineering d27215a): with two back-merges in a row left unmerged, and the changelog edited on `develop` in between, the carry step keeps only the previous release's section. The older section drops out of `CHANGELOG.md` for good, and nothing warns. Its GitHub Release notes survive. Measured with v0.2.0 and v0.2.1 unmerged, then v0.2.2 released: the back-merge carried v0.2.2, v0.2.1 and v0.1.0, and v0.2.0 was gone.
- F-REL-V01, minor, inside the fix: carrying or resuming from a squash-merged back-merge checks out `develop`'s tree, so a release then runs `develop`'s unreleased scripts. The documents say to merge back-merges with a merge commit, which avoids it.
- F-REL-V02, minor, inside the fix: a re-run of a failed release, after `production` has moved on, picks up the newer release and exits cleanly, so the older version never gets its GitHub Release. `docs/build/Release_flow.md` says a moved `production` stops the re-run, which holds only for a failure before the tag.
- F-REL-V03, minor: the borrower test's docstring says unanchoring either end of either subject pattern turns it red, but removing the `^` from the squash pattern leaves it green.
- F-REL-V04, a note: the push-list test reads only lines that begin with `git push`, so a push hidden behind `: &&` is caught only by the end-to-end tests.
- Carried from the fix round as notes: J05, J06, J07, J12, J14, A07, A08 and A11.

Card 65 on `testing/UI_fix_plan.md` carries the five verifier findings above. It must land before the next release of either repository.

## What the owner decided

On 2026-09-27 the owner chose to merge both pull requests with these findings named open, and to fix them before the next release (`DECISIONS.md`, the same day). V05 needs two releases to happen, so it cannot occur before that fix lands.
