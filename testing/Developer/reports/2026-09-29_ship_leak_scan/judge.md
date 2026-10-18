# Judge round 1: public-repository leak scanner (/ship)

- Date: 2026-09-29
- Role: judge, one round, independent. Files findings, closes nothing.
- Subject: `git diff origin/develop...HEAD` on `chore/ship-leak-scan` (commits 2e37ca02, 11ff3312, 3d1a31ba).
- Method: own probes in scratch repositories under the session scratchpad; mutation of scratch copies of the script. Values are masked throughout.
- Fix round, 2026-09-30: two quoted paths in F-LS-J18 are split with `+` so this file passes the scan it reviews. No finding changed.

## Findings

### F-LS-J01: only one of three subprocess calls has a timeout
- Severity: minor
- File: `.claude/skills/ship/scripts/check_public_leaks.py:401` (`_git`, every git call) and `:413` (`repo_root`); only `:637-638` (the private check) passes `timeout=120`.
- Evidence: `grep -n "subprocess.run\|timeout" check_public_leaks.py` prints 401, 413, 637, 638 and no other timeout. No `shell=True` anywhere (grep for `shell=` empty), so the argv-list form is sound.
- Why it matters: the brief's quality bar is a timeout on every subprocess. A git call blocked on a lock, a credential prompt or a slow filesystem hangs /ship with no message, and `_git` has no `TimeoutExpired` handler to turn that into the documented exit 2.
- NOT FIXED
### F-LS-J02: a secret added in one unpushed commit and removed in the next is published and the scan says PASS
- Severity: critical
- File: `.claude/skills/ship/scripts/check_public_leaks.py:565-570` scans only the NET diff `git diff <base>...HEAD`; the docstring at `:8-10` and SKILL.md ("reads exactly what a push would publish") claim it scans what a push publishes. A push publishes every commit in `<base>..HEAD`, including each intermediate blob.
- Reproduction (scratch repository `judgescan/p1`, bare upstream plus clone, `origin/develop` current): commit 1 adds `conf.txt` with `cfg AK***(20 chars)` (an AWS-shaped id assembled at run time); commit 2 replaces the line with `cfg clean`. `git log -p origin/develop..HEAD | grep -c AKIA` prints `2` (the value is in the outgoing history). The scan prints:
  `scanned 3 lines and 2 commit(s) against origin/develop; 0 finding(s) ...` / `PASS: nothing to publish looks like a secret or a private value.` / `rc=0`
- Why it matters: "I pasted the key, noticed, and deleted it in the next commit" is the most common way a secret reaches a public repository, and it is exactly the case this gate passes. The same gap covers a merge of another unpushed branch whose history added then removed a value. Scanning `git log -p <base>..HEAD` (every commit's added lines) instead of the net diff closes it.
- NOT FIXED
### F-LS-J03: anything after character 20,000 of a line is silently unscanned, and the run reports PASS
- Severity: major
- File: `check_public_leaks.py:330` (`text = text[:MAX_LINE_CHARS]`, `:58` sets 20000). Nothing counts or reports the truncation; SKILL.md's "What it cannot catch" list does not mention it.
- Reproduction (`judgescan/p2`): commit `min.json` holding one line of 20,001 `x` characters, a space, then an AWS-shaped id. Output: `scanned 2 lines and 1 commit(s) ...; 0 finding(s), 0 file(s) not scanned` / `PASS: ...` / `rc=0`.
- Why it matters: minified JSON, a saved HTML report, a notebook output cell or a pasted log is one long line; a token deep inside it passes with a PASS line that says nothing was left unread. At minimum the truncation should be a NOT SCANNED line; better, scan the line in overlapping windows.
- NOT FIXED

### F-LS-J04: a file over 2 MB is "NOT SCANNED" yet the scan exits 0 and prints PASS
- Severity: major
- File: `check_public_leaks.py:502-504` appends to `not_scanned`; `:682` sets the exit code from `findings` only; `:710-711` prints PASS when `exit_code == 0` whatever `not_scanned` holds.
- Reproduction (`judgescan/p3`): commit `big.log`, about 2.2 MB of short lines ending in an AWS-shaped id. Output: `NOT SCANNED big.log (larger than 2 MB, commits)` / `... 1 file(s) not scanned ...` / `PASS: nothing to publish looks like a secret or a private value.` / `rc=0`.
- Why it matters: SKILL.md tells the lead to "Gate on that code" and push "only on exit 0". A gated caller reading only the code pushes the file. The skill does list "a file over 2 MB (reported as not scanned)" as a limitation, so this is disclosed, but the same run's last line saying PASS contradicts the NOT SCANNED line above it. An unscanned published file should make the run non-zero (or at least suppress PASS), the same fail-closed stance the private-name check takes. The builder's test `test_oversized_file_is_reported_not_silently_skipped` (test file `:409-413`) asserts the report line but never the exit code, so it cannot catch this.
- NOT FIXED

### F-LS-J05: a text file git judges binary (a NUL byte) is neither scanned nor counted
- Severity: major
- File: `check_public_leaks.py:565-567` runs `git diff` without `--text`; for a file git classifies as binary it emits `Binary files ... differ` and no `+` lines, so `parse_added_lines` (`:444-473`) records nothing, and neither `binary_skipped` nor `not_scanned` moves. The untracked path handles NUL bytes (`:530-532`, counted) but the committed path does not.
- Reproduction (`judgescan/p4`): commit `dump.txt` = `head\0\ncfg AK***(20 chars)\n`. Output: `scanned 1 lines and 1 commit(s) ...; 0 finding(s), 0 file(s) not scanned, 0 binary file(s) skipped by name` / `PASS` / `rc=0`.
- Why it matters: a database dump, a log with a stray control byte or a UTF-16 file (Windows exports are often UTF-16, which is NUL-heavy) publishes with a clean PASS and no trace in the summary. SKILL.md says binaries are "skipped by name"; this one is skipped by content and not reported at all.
- NOT FIXED

### F-LS-J06: a `.gitattributes` `-diff` (or `binary`) rule hides whole file types from the scan
- Severity: major
- File: `check_public_leaks.py:565-567` and `:571-573` (no `--text`, no `--no-textconv`); `--no-ext-diff` alone does not neutralise attributes.
- Reproduction (`judgescan/p5`): one commit adds `.gitattributes` = `*.cfg -diff` and `app.cfg` = `cfg AK***(20 chars)`. Output: `scanned 2 lines ...; 0 finding(s), 0 file(s) not scanned, 0 binary file(s) skipped by name` / `PASS` / `rc=0`.
- Why it matters: the diff of the committed `.gitattributes` line itself is scanned, but the file it hides is not. Any repository attribute (or a `diff=<driver>` with a textconv that rewrites content) changes what the scanner sees without changing what the push publishes. `git diff --text --no-textconv` reads the published bytes.
- NOT FIXED
### F-LS-J07: file and directory names are published but never scanned
- Severity: minor
- File: `check_public_leaks.py:444-473` (`parse_added_lines` keeps names only as labels) and `:511-536` (untracked names used only as labels). No detector ever runs on a path.
- Reproduction (`judgescan/p6b`): commit `mail/j***@gmail.com/notes.txt` (a personal address as a directory name) with content `clean`. Output: `0 finding(s)` / `PASS` / `rc=0`. The same string passed to the script's own `scan_line` returns `['personal-email']`, so the detector would have caught it had the path been scanned.
- Why it matters: evidence folders and exported reports are often named after a person, a host or an address, and the path is as public as the content.
- NOT FIXED

### F-LS-J08: a commit message containing the byte 0x1E crashes the scan with a traceback
- Severity: minor
- File: `check_public_leaks.py:540-546`: records are split on `\x1e`, then `record.split("\x1f", 3)` is unpacked into four names with no guard; `main` (`:671-676`) catches only `CannotRun`.
- Reproduction (`judgescan/p7`): a commit whose message body is `record<0x1E>separator`. Output tail: `sha, author, committer, message = record.split("\x1f", 3)` / `ValueError: not enough values to unpack (expected 4, got 1)` / `rc=1`.
- Why it matters: it fails closed (non-zero), but exit 1 is documented as "a finding", so the lead is told there is a leak to remove when the tool crashed; the documented crash code is 2. Use NUL-separated records or catch the parse error as `CannotRun`. No value was printed by the traceback.
- NOT FIXED
### F-LS-J09: a PGP armoured private key is not detected
- Severity: minor
- File: `check_public_leaks.py:224`: the pattern requires the two words for a private key to be followed directly by five dashes, so the PGP armour header, which adds the word BLOCK before the closing dashes, never matches.
- Reproduction (`judgescan/p8`): commit `k.asc` whose first line is the five-dash PGP private key armour header (assembled at run time). Output: `0 finding(s)` / `PASS` / `rc=0`.
- Why it matters: SKILL.md says it catches "private key blocks" without qualification. Allow an optional trailing word before the closing dashes.
- NOT FIXED
### F-LS-J10: at both points /ship runs it, the private-name check reads an empty staged diff and prints PASS
- Severity: major
- File: `check_public_leaks.py:627` always runs the private check with `--staged`; `:686` prints `private-name check: PASS (machine-local check ran on the staged diff)`. SKILL.md runs the scan at Step 0 "before anything is staged" (`SKILL.md:20`, `:44`) and at Step 2 "after the commit" (`SKILL.md:224`), where the staged diff is empty in both cases. SKILL.md `:224` says the second run "now sees the commit message, the author identity and any file docs-sync edited", which is true of the shape scan but not of the private-name check.
- Reproduction (`judgescan/p9`): a stand-in check installed through the hook's `exec` line fails on a stand-in private term in `git diff --cached`. With the term staged: `private-name check: FAIL: staged: owner-term` / `rc=1` (the wiring works). After `git commit --no-verify` (the Step 2 position, and the case the hook was bypassed): `private-name check: PASS (machine-local check ran on the staged diff)` / `0 finding(s)` / `PASS: nothing to publish looks like a secret or a private value.` / `rc=0`, and the term is in the outgoing commit.
- Honesty of the statement: `builder.md:65` states it plainly ("Run in Step 0 before anything is staged, it mostly proves the check exists on this machine"). SKILL.md `:69` says only "on the staged diff" and never says that at /ship's two positions that diff is empty, so a reader of the skill and of the PASS line will believe names were checked. Neither file says untracked files and commit messages never reach this check (the real check has a message mode, per its own argument list, which the scan does not call).
- Why it matters: the owner's request names "PII such as name" first. The only name check in the gate is vacuous where the gate runs; the real protection is the commit-time hook, which `--no-verify`, a commit made elsewhere, or a hook not installed in a fresh clone bypass. Either run the check over the outgoing range (its slower `--all`, or feed it the range diff) or make the PASS line and SKILL.md say "staged diff was empty; names in the outgoing commits were not checked".
- NOT FIXED
### F-LS-J11: a stale `origin/develop` after the remote was force-pushed hides commits the push re-publishes; /ship never fetches first
- Severity: minor
- File: `check_public_leaks.py:429-434` checks only that the base ref exists; `:541` and `:566` trust the local tracking ref. SKILL.md contains no `git fetch` before either scan (`grep -n fetch SKILL.md` finds only the scan's own exit-2 advice).
- Reproduction (`judgescan/p10`): clone pushes commit C (AWS-shaped id in `leak.txt`); a second clone force-pushes `develop` back to the commit before C; the first clone, not fetched, adds commit D. Scan: `scanned 2 lines and 1 commit(s) ...; 0 finding(s)` / `PASS` / `rc=0`. `git rev-list <real remote tip>..HEAD --count` prints `2`, and `git push --dry-run` shows a fast-forward, so C (removed from the remote on purpose) would be published again. After `git fetch origin` the same scan prints `1 finding(s)` / `BLOCKED` / `rc=1`.
- Why it matters: the brief names the force-pushed base case. It is exactly the history-rewrite-to-remove-a-leak scenario the SKILL.md says "needs the owner", and a teammate or second session on the old tip would silently undo it. A `git fetch origin` immediately before the scan (or `git ls-remote` for the true tip) closes it.
- Also verified, no defect: a new branch with no upstream (`judgescan/p11`, `fatal: no upstream configured`) still scans against `origin/develop` and reports `FAIL a.txt:1 [aws-access-key] A***(20 chars)`.
- NOT FIXED
### F-LS-J12: the path allow marker also exempts secrets, and a URL password under 8 characters is never a finding
- Severity: unsure (design choices worth the owner's eye rather than proven defects)
- File: `check_public_leaks.py:328-329` returns no findings for the whole line when `local-refs: allow` is present, before any secret detector runs; `:283-284` treats every value under 8 characters as a placeholder, and `:357` applies that to URL passwords.
- Reproduction (`judgescan/p13` and a direct `scan_line` call): a committed line `cfg AK***(20 chars)  # local-refs: allow` produces no finding for line 1 (only line 2 is reported). `scan_line` on `postgres://app:<6-char mixed password>@db:5432/app` returns `[]`; the same with an 8-character password returns `['url-password']`. With a dotted host the 6-character case is caught only by accident, as `[personal-email]` on `X***(23 chars)`.
- Why it matters: the marker belongs to the owner's local-reference hook, whose meaning is "this path or name is public"; letting it silence the private key and token detectors widens a privacy escape hatch into a secret escape hatch. Real service passwords are often short. Neither is stated in SKILL.md.
- Verified, no defect: a merge commit of an unpushed side branch (`judgescan/p12`) is caught through the net diff: `FAIL s.txt:1 [aws-access-key] A***(20 chars)`.
- NOT FIXED
### F-LS-J13: builder.md calls the address in data engineering commit 7c064578 "private style"; it is a public, globally routable address on a line about the server
- Severity: major (a report inaccuracy that understates a live exposure the owner must decide on)
- File: `testing/Developer/reports/2026-09-29_ship_leak_scan/builder.md:150` ("One commit message (`7c064578`) carries a private style IPv4 address").
- Evidence: my own wide run in the data engineering worktree, `check_public_leaks.py --base HEAD~60 --allow-missing-private-check`, prints `FAIL commit 7c064578 message:8 [ipv4-address] 4***(14 chars)`. Checking that value with the stdlib `ipaddress` module, printing only booleans: `is_private False is_global True len 14`, and the same message line contains the word server or hetzner (`mentions server/hetzner: True`), no `ssh`. So it is very likely the graph server's public address, sitting in already public history, not an RFC 1918 fixture value.
- Why it matters: "private style" reads as harmless test noise; a public server address beside the word server is the privacy rule's server-address category and an attack-surface pointer. The owner should see it described correctly before deciding on a history rewrite. The other two incidental items check out: 41 distinct commits with a non-noreply identity (my run: 82 identity lines over 41 commits; each at a work domain, matching `builder.md:148`), and `docs/learnings.md:997` is a home path in an rsync example (`rsync: True`, written with forward slashes after a drive letter, which is why both the unix and Windows detectors fire on it: `/***(11 chars)` and `C***(13 chars)`).
- NOT FIXED

### F-LS-J14: builder.md's System 3 "true positive" is located correctly but characterised loosely
- Severity: minor
- File: `builder.md:63` and `:119`.
- Evidence: my own run in the System 3 worktree with `--base HEAD~150` prints `FAIL tests/services/graph_query_service/test_forwarded_address.py:38 [ipv4-address] 1***(8 chars)`; line 38 is `request = _request(peer="<203.x.x.x>", forwarded="<10.x.x.x>")` (masked by me), a forwarded-header unit test using a documentation address and an RFC 1918 address. Location and value class match the report. Calling it "a true positive under the rule" overstates it: the privacy rule's category is employer-internal IP addresses, and a generic 10.x value in a proxy test is not one. It is the scanner's intended policy hit, which is a different claim. The same run also counted `549 commit(s) against HEAD~150`, so "a 150 commit wide run" (`builder.md:64`) was 150 first-parent steps, not 150 commits.
- Side observation for the lead, not a defect in this change: the same run flags `testing/Developer/reports/2026-09-29_ship_leak_scan/adversary.md:93` and `:121` `[ipv4-address] 1***(8 chars)`; that untracked report would block /ship if committed as it stands.
- NOT FIXED

### F-LS-J15: builder.md, a public file, names the work-address domains found in the other repository's history
- Severity: unsure
- File: `builder.md:148` (the builder named the two work domains and a count for each; the fix round removed the names, so they are not quoted here either).
- Evidence: counts verified above. The addresses themselves are not repeated, as the brief required.
- Why it matters (unsure): the privacy rule lists the owner's work identity as never-commit. Naming the employer domains, next to "The privacy rule calls a work address the owner's work identity", tells a reader of this public repository where the work addresses are and whose they are. The addresses are already public in the other repository's history, so the marginal exposure may be nil; the owner should decide whether "a non-noreply work domain" is the safer wording.
- NOT FIXED
### F-LS-J16: five of my sixteen mutations of the script survive the whole test file
- Severity: major (the masking survivor); minor (the other four)
- Method: `judgescan/mutate.py` copies the script, applies one exact-anchor replacement (anchor count checked to be 1), points `CHECK_PUBLIC_LEAKS_SCRIPT` at the copy and runs `tests/ci/test_check_public_leaks.py -x`. Baseline: `93 passed in 19.69s`. Eleven mutations went red (range diff not scanned, working-tree diff not scanned, commit messages not scanned, committer email not checked, private-check findings not failing, private exit 2 treated as pass, findings exit 0, hunk line numbers off by one, CannotRun exit 1). One of mine was a bad mutation (an allow-marker variant keyed on a word the fixtures never contain) and is discarded, not counted. Survivors, all `GREEN`:
  - `mask` changed to print the last six characters of the value (`check_public_leaks.py:269`). Against an AWS-shaped id it printed `FAIL a.txt:1 [aws-access-key] A***<6 chars shown>(20 chars)`, and the real tail was in the output (`grep -c` = `1`). The masking test (`test_check_public_leaks.py:213-222`) asserts only the full value and `secret[1:7]`, so any mask that reveals a tail, or a middle slice, passes. The brief's "no path prints a full matched value" holds today (my own all-category probe below), but nothing pins it.
  - `_redact` made a no-op (`:587-593`): no test relays a home path through the private check.
  - `10.0.0.0/8` and `192.168.0.0/16` allowed (`:310`): the only planted address is `172.16.x.x` (test `:88`).
  - Untracked NUL-byte detection removed (`:530-532`): untested.
  - The committed-file size cap removed (`:502-504`): `test_oversized_file_is_reported_not_silently_skipped` plants an UNTRACKED file, so the committed path's cap is untested. (The builder's list at `builder.md:71-93` has no size-cap row.)
  - The private check invoked without `--staged` (`:627`): the stand-in ignores its arguments, so the flag that decides what the real check reads is untested.
- Why it matters: the masking property is the one the brief names as a hard requirement, and it is guarded only against the two most obvious failures.
- NOT FIXED

### Masking, verified by my own probe (no finding)
- `judgescan/p14`: fourteen values, one per category, planted in a committed file, the commit message and an untracked file, with a non-noreply author email. Output: `rc 1`, `finding lines 46`, all fourteen categories plus `identity-email`. A search of the output for any five-character run of any value (after its first character) found one hit, which was my probe matching the category label `personal-email` against a planted home-directory name; no value run appears. Exit-2 messages (`:405-406`, `:424`, `:433`) print only the git subcommand, git's first stderr line and the `--base` argument. The private-check relay (`:642-651`) prints the external check's lines verbatim after home redaction; the owner's real check prints only file, line and check name (per its own docstring line 63 and its `FAIL: {location}: {name}` print), so the relay does not leak today but depends on that script's discipline.
### F-LS-J17: the pre-push scan lives only in a context bullet handed to the git-sync agent, whose own push sequence does not contain it
- Severity: minor
- File: `SKILL.md:208-214` lists what git-sync "will" do (status, show files, stage, commit, push) with no scan between commit and push; the scan appears only as a context bullet at `SKILL.md:224`. `.claude/agents/git-sync.md:39-55` (its Push and Full sync sequences) and `:73-90` contain no scan (`grep -n -i "leak\|scan"` on it prints nothing).
- Evidence: the greps above. Not run end to end, since running git-sync would push.
- Why it matters: the Guards (`SKILL.md:277`) say never push with the scan unrun, but the step that pushes is performed by an agent whose definition does not know about the scan, and a plain "push" or "sync" request dispatches the same agent outside /ship with no scan at all. Putting the scan in the numbered list (between 4 and 5) and in git-sync's own Push section, or as a local pre-push hook, would make the gate hold wherever a push happens. The latter is a hook change and needs the owner.
- NOT FIXED
### F-LS-J18: the local-path detector misses the dash-encoded home paths this project's agents write into reports
- Severity: minor
- File: `check_public_leaks.py:240-243`: only a slash-delimited `/Users/<name>/`, `/home/<name>/` or drive-letter form matches.
- Reproduction (direct `scan_line` calls with a synthetic name): an agent scratchpad path `/private/tmp/claude-501/-Users-<name>-Desktop-proj/scratchpad/x.txt` returns `[]`; an agent project path `~/`+`.claude/projects/-Users-<name>-Desktop-proj/memory/a.md` returns `[]`; a pytest temp path `/var/folders/.../pytest-of-<name>/x` returns `[]`; a home-relative `~/`+`Desktop/<folder>/<private-repo>/notes.md` returns `[]`. Controls: the plain `/Users/<name>/x` and `file:///Users/<name>/x.html` both return `['local-path']`.
- Why it matters: the privacy rule says evidence artifacts are where local paths leaked before, and these are the exact shapes an agent's report or a pasted pytest failure carries (this judge's own scratchpad path has the first shape). None is tracked today (`git grep -E -- '-Users-[A-Za-z0-9]+-'` and `pytest-of-` count 0), so this is a gap, not a live leak. SKILL.md's wording ("a home directory that names a person") is accurate about the slash forms, but a reader would expect these covered. Home-relative paths naming a private repository fall to the private-name check, which is vacuous at /ship's positions (F-LS-J10).
- NOT FIXED

### F-LS-J19: SKILL.md's Output list never asks for the leak scan's result, its NOT SCANNED lines or its private-check status
- Severity: minor
- File: `SKILL.md:280-293`: item 1 covers "Step 0 gate results: each command and its exit code"; nothing covers the Step 2 re-run, a `NOT SCANNED` line (which exits 0, F-LS-J04) or a `private-name check NOT RUN` line accepted with the flag.
- Why it matters: the two conditions that pass with exit 0 but mean "not checked" are exactly what the owner would want surfaced in the ship report.
- NOT FIXED
### F-LS-J20: the scanner blocks on RFC 1918 range names written as CIDR, including in this very report
- Severity: minor (false positive, fails closed)
- File: `check_public_leaks.py:247` and `:304-312`: a network address such as the first address of the 10/8 or 192.168/16 range, followed by `/8` or `/16`, is an ipv4-address finding.
- Reproduction: the default-base scan of this worktree, run as /ship would, reports `FAIL testing/Developer/reports/2026-09-29_ship_leak_scan/judge.md:115 [ipv4-address] 1***(8 chars)` and `... 1***(11 chars)`: those are the two range names in my F-LS-J16 bullet, not host addresses. The same run reports 17 findings in the untracked `adversary.md` (lines 93 to 161), and `rc=1`. Real-run context: `scanned 1862 lines and 3 commit(s) against origin/develop; 19 finding(s)`, private-name check PASS.
- Why it matters: any document explaining the privacy rule's internal-address category trips the gate, which trains people to reach for `local-refs: allow`. For the lead: this report and the adversary's both need the marker or a rewording before they are committed through /ship. I cannot edit my own earlier line (append only).
- NOT FIXED

## Verdict: FIX FIRST

The scan's headline claim, that it reads exactly what a push publishes, is false for the most common leak pattern (F-LS-J02, a value added then removed in unpushed history), and four more paths publish content under a PASS line (J03 long lines, J04 files over 2 MB with exit 0, J05 NUL-byte text files, J06 a `-diff` attribute). The name check the owner asked for first is vacuous at both /ship positions (J10). Round 1, so no finding sits inside a fix made during this phase; the stop condition does not fire.

Must fix before merge: J02, J03, J04, J05, J06, J10 (code or, at minimum, honest SKILL.md and PASS wording), J13 (report correction), and the masking survivor in J16. The rest (J01, J07, J08, J09, J11, J12, J14, J15, J17 to J20) can be named items.

### Verified with my own probes
- Outgoing range: J02, J11 and the no-upstream and merge cases (scratch bare remote plus clone, `judgescan/p1`, `p10`, `p11`, `p12`).
- Silent passes: J03 to J07, J09 (`p2` to `p8`, `p6b`); the J08 crash (`p7`).
- Private-name check wiring, fail-closed and vacuous pass: J10 (`p9`, stand-in check through a hook `exec` line).
- Masking across fourteen categories and four sources (`p14`), and the mask survivor's tail leak (`p15`).
- Sixteen mutations of a scratch copy against the test file (J16).
- The builder's System 3 wide-run hit, and all three data engineering incidental items, by rerunning the scan in both worktrees and checking values with booleans only (J13, J14).
- Gate counts: `tests/ci` and `tests/tracker` `553 passed`, the new file `93 passed`, `ruff` clean, `gate02` exit 0, `check_doc_drift.py --check` exit 0; `cmp` confirms the data engineering copy is byte-identical.

### Only read, not run
- The owner's real private-name check: its output format was taken from a grep of its print statements and docstring; reading its body was refused by the permission layer, so I did not read further.
- The git-sync agent's behaviour (J17): read, not run, since running it pushes.
- The data engineering ship skill proposal in the builder's scratchpad (`builder.md:140`): not read.
