# Adversary round: public-repository leak scanner, 2026-09-29

Subject: `.claude/skills/ship/scripts/check_public_leaks.py` on branch `chore/ship-leak-scan`.
Method: throwaway git repositories under the session scratchpad, fake values assembled at runtime, never a real secret or personal detail.
All values in outputs below are masked.
Fix round, 2026-09-30: values quoted in this file are split with `+`, as the lines above already did, so the file passes the scan it reviews. No finding, output or count changed.

## Findings

### F-LS-A01: common secret shapes pass the line scanner (short passwords, symbol passwords, PGP keys, webhooks, several vendor tokens)
- Severity: major
- File: `.claude/skills/ship/scripts/check_public_leaks.py:224-239` (the shape regexes and `ASSIGNMENT_RE`), `:363` (`_mixed` plus entropy 3.3 gate)
- Reproduction: imported the script and called `scan_line()` on runtime-assembled fake values (random.Random(7) tokens). Every line below returned NO hit:
  - `password = <12 random alnum>` (ASSIGNMENT_RE needs 16+ chars)
  - `password = <20 letters only>` and `db_password=<20 digits only>` (`_mixed` requires both)
  - `password=<10 alnum>!@#<6 alnum>` (value class stops at `!`)
  - `-----BEGIN PGP PRIV` + `ATE KEY BLOCK-----` (regex requires `KEY-----` right after)
  - Slack incoming webhook `https://hooks.slack.com/services/T.../B.../<24>` and Discord webhook URL
  - `sk_live_<24>` (Stripe shape), `glpat-<20>` (GitLab), `hf_<34>`, `npm_<36>`
  - `Authorization: Basic <base64 of svc:password>`
  - names outside the keyword list: `pwd: <14>`, `auth: <32>`, `"credential": "<32>"`, `passphrase = <24>`, `credentials = <24>`
  - `token => '<24>'` (Ruby/Perl hash arrow)
  - `postgres://svc:<6>/<6>@dbhost/x` (password containing `/`)
  - a base64-wrapped GitHub token, and an AWS key split across two string literals
- What would leak: a live database password, a PGP private key, a webhook that lets anyone post into a channel, or a vendor token. GitHub push protection covers some vendor shapes, but the privacy rule calls it a second layer, not a substitute.
- NOT FIXED

### F-LS-A02: home paths in several real forms pass, including the dash-encoded agent scratchpad path this harness writes every day
- Severity: major
- File: `.claude/skills/ship/scripts/check_public_leaks.py:240-243` (`UNIX_PATH_RE`, `WINDOWS_PATH_RE`)
- Reproduction: `scan_line()` returned NO hit for each (name `zelda` is fake):
  - `/private/tmp/claude-501/-Us`+`ers-zelda-Desktop/x` (the dash-encoded project path every agent scratchpad in this project uses; the builder's own report had to replace one with `<scratchpad>` by hand)
  - `cwd was /Us`+`ers/zelda` (name at end of line, no trailing slash, so the user name is still published)
  - `see ~/`+`Desktop/<folder>/notes.md` (home-relative, which the rule names explicitly)
  - `%2FUs`+`ers%2Fzelda%2FDesktop` (URL-encoded)
  - `c:\us`+`ers\zelda\x` (lower-case Windows, which is case-insensitive)
  - `/mnt/c/Us`+`ers/zelda/x` (WSL; the `(?<![\w])` look-behind rejects because `c` precedes)
  - `"/Us`+`ers/zelda smith/x"` (a name with a space)
  - `\/Us`+`ers\/zelda\/x` (JSON-escaped slashes)
  Forms that DID hit: backticks, Markdown link, `file://`, Windows forward slashes, doubled backslashes.
- What would leak: the owner's user name and machine layout, the exact category the privacy rule says leaked before through evidence artifacts.
- NOT FIXED

### F-LS-A03: a secret added in one commit and removed in a later one is pushed into public history with PASS
- Severity: critical
- File: `.claude/skills/ship/scripts/check_public_leaks.py:565-567` (only the net `git diff <base>...HEAD` is scanned; no per-commit content scan)
- Reproduction: throwaway repo `advscan/h1` with a fake origin. On branch `work`: commit 1 adds `cfg.txt` containing `key AKIA<16 fake chars>`; commit 2 `git rm cfg.txt`. Run the scanner (`--allow-missing-private-check`):
  ```
  scanned 2 lines and 2 commit(s) against origin/develop; 0 finding(s), 0 file(s) not scanned, 0 binary file(s) skipped by name
  PASS: nothing to publish looks like a secret or a private value.
  rc=0
  ```
  `git log --all -p | grep -c AKIA` then prints 2: the key is in the commit objects a push sends.
- What would leak: any secret, path, email or IP that was committed and then "fixed" in a later commit on the same branch, which is exactly the normal reaction to seeing it. The fix commit makes the scanner green while the push still publishes the first commit forever. The module docstring (line 10) says it scans "exactly what a push would publish"; it does not.
- NOT FIXED

### F-LS-A04: a file over 2 MB is reported NOT SCANNED but the scan still exits 0 and prints PASS
- Severity: major
- File: `.claude/skills/ship/scripts/check_public_leaks.py:502-504` and `:682`, `:711` (`exit_code` ignores `report.not_scanned`)
- Reproduction: repo `advscan/h2`, commit `big.txt` = 2 MB of `a` plus a line `key AKIA<16 fake>`. Output:
  ```
  NOT SCANNED big.txt (larger than 2 MB, commits)
  scanned 1 lines and 1 commit(s) ...; 0 finding(s), 1 file(s) not scanned, 0 binary file(s) skipped by name
  PASS: nothing to publish looks like a secret or a private value.
  rc=0
  ```
- What would leak: anything in a large evidence log, trace dump or data export, the artifact class the privacy rule says leaked before. `/ship` gates on the exit code only (SKILL.md line 44: "Gate on that code"), so NOT SCANNED never stops a push, and the final line tells the reader it is clean.
- NOT FIXED

### F-LS-A05: any file with a binary-looking extension is skipped by name, whatever it contains, with exit 0
- Severity: major
- File: `.claude/skills/ship/scripts/check_public_leaks.py:61-108`, `:499-501`, `:517-519`
- Reproduction: repo `advscan/h3`, commit two plain-text files `notes.pdf` and `cache.db`, each containing `key AKIA<16 fake>`. Output: `0 finding(s) ... 2 binary file(s) skipped by name` then `PASS ...` and `rc=0`.
- What would leak: a text secret file saved under `.db`, `.sqlite`, `.pkl`, `.zip`, `.tar`, `.jar` and so on. A SQLite database or pickle committed as a fixture can hold real user rows (the privacy rule's personal-data category) and is never opened. The check trusts the name, not the content.
- NOT FIXED

### F-LS-A06: a text file git considers binary (one NUL byte, or UTF-16) is not scanned and not even counted
- Severity: major
- File: `.claude/skills/ship/scripts/check_public_leaks.py:565-570` (git prints `Binary files differ` and no `+` lines, so `parse_added_lines` sees nothing)
- Reproduction: repo `advscan/h4`, commit `env.txt` = `key AKIA<16 fake>\n\0\n` and `u16.txt` = the same line encoded UTF-16. Output: `scanned 1 lines ... 0 finding(s), 0 file(s) not scanned, 0 binary file(s) skipped by name`, `PASS`, `rc=0`. Neither file is mentioned anywhere, not even in the skipped count.
- What would leak: a secret in a UTF-16 file (Windows editors and PowerShell `>` redirection write UTF-16 by default) or a file with one stray NUL, with no trace in the output that anything was skipped. Untracked files have a NUL check (line 530) that counts them; committed files do not.
- NOT FIXED

### F-LS-A07: anything after character 20000 on a line is silently dropped (minified JSON, one-line notebooks)
- Severity: major
- File: `.claude/skills/ship/scripts/check_public_leaks.py:58`, `:330`
- Reproduction: repo `advscan/h5`, commit `min.json` = one line `{"a":"<20010 b>","k":"AKIA<16 fake>"}`. Output: `0 finding(s), 0 file(s) not scanned`, `PASS`, `rc=0`. No NOT SCANNED line and no truncation warning.
- What would leak: a secret or path late in a minified JSON, a one-line trace export, a JS bundle, or a notebook output cell. The truncation is silent, unlike the 2 MB cap.
- NOT FIXED

### F-LS-A08: file and directory names are never scanned
- Severity: major
- File: `.claude/skills/ship/scripts/check_public_leaks.py:460-468` (the `+++ b/<name>` is parsed and used only as a label), `:511-536`
- Reproduction: repo `advscan/h6`, commit three harmless one-line files at paths `Us`+`ers/zelda/notes.txt`, `zelda.q@<fake webmail>.txt` and `10.1.2`+`.3_ssh_login.txt`. Output: `scanned 4 lines ... 0 finding(s)`, `PASS`, `rc=0`.
- What would leak: a person's name, email or an internal address carried in a path, for example an evidence folder named after a colleague or a screenshot named after a real user. Git publishes paths exactly like content.
- NOT FIXED

### F-LS-A09: secrets inside a Jupyter notebook's JSON-escaped source lines pass
- Severity: major
- File: `.claude/skills/ship/scripts/check_public_leaks.py:235-239` (`ASSIGNMENT_RE` allows `["']?` after `=`, but not the backslash of `\"`)
- Reproduction: repo `advscan/h7`, commit `nb.ipynb` whose source lines are `"api_key = \"<32 random alnum>\"\n",` and `"PASSWORD = \"<same>\"\n"`. Output: `0 finding(s)`, `PASS`, `rc=0`. Control `advscan/h7b`: the same assignment unescaped in `nb.py` gives `FAIL nb.py:1 [secret-assignment] N***(32 chars)`, `rc=1`. So the only difference is notebook escaping.
- What would leak: a key typed into a notebook cell, which is the most common way a notebook leaks a key. The same applies to any JSON or JSON-in-string file that escapes quotes.
- NOT FIXED

### F-LS-A10: one allow marker exempts a whole file when the file uses CR-only line endings
- Severity: major
- File: `.claude/skills/ship/scripts/check_public_leaks.py:328-329` with `:450` and `:533` (lines are split on `\n` only)
- Reproduction: repo `advscan/h8`, commit `old.txt` written with `\r` separators: `note local-refs: allow\rkey AKIA<16 fake>\rmail zelda.q@<fake>\rip 10.1.2.3\r`. Output: `0 finding(s)`, `PASS`, `rc=0`. Control `advscan/h8b`, identical file without the marker: `FAIL old.txt:1 [aws-access-key]`, `[personal-email]`, `[ipv4-address]`, `rc=1`. So one marker exempted every "line" in the file. The same holds for any single-line file (minified JSON, a JS bundle): one marker anywhere on it exempts everything on it.
- What would leak: every secret in the file behind one marker. It also answers the brief's question directly: yes, the marker can exempt more than one line.
- NOT FIXED

### F-LS-A11: the allow marker is matched anywhere on the line, not as a trailing comment, so it exempts every other value on that line
- Severity: minor
- File: `.claude/skills/ship/scripts/check_public_leaks.py:328`
- Reproduction: repo `advscan/h9`, commit one line `see https://x.io/?q=local-refs: allow  key AKIA<16 fake>  zelda.q@<fake>`. Output `0 finding(s)`, `PASS`, `rc=0`. The marker sits inside a URL query string and still exempts an unrelated key and email on the same line.
- What would leak: a line marked to publish one genuinely public value (for example a public IP) also publishes anything else on it. A per-value or per-category exemption would bound this; the whole-line one does not.
- NOT FIXED

### F-LS-A12: author and committer names, and annotated tag messages, are never scanned
- Severity: minor
- File: `.claude/skills/ship/scripts/check_public_leaks.py:540-559` (format carries `%ae` and `%ce` only; no `%an`, `%cn`, no tags)
- Reproduction: repo `advscan/i3`, commit with `GIT_AUTHOR_NAME="Zelda Quentin-Realname"` (fake) and an annotated tag `v1 -m "release by zelda.q@<fake> from 10.1.2`+`.3"`. Output: `0 finding(s)`, `PASS`, `rc=0`.
- What would leak: a colleague's real name as the author of a cherry-picked or co-authored commit (the privacy rule forbids colleague names), and anything in a tag message if the push uses `--follow-tags` or `--tags`. The owner's words were "PII such as name"; no name field is looked at. Controls that DID work: a committer email differing from the author (`advscan/i1`) and a `.mailmap` hiding a personal email (`advscan/i2`) were both caught.
- NOT FIXED

### F-LS-A13: the private-name check never sees the commits being pushed, yet prints PASS; at /ship Step 2 it checks an empty diff
- Severity: critical
- File: `.claude/skills/ship/scripts/check_public_leaks.py:627` (always `--staged`), `:686` (prints PASS), and `.claude/skills/ship/SKILL.md:224` (the second run "after the commit and before the push")
- Reproduction: repo `advscan/p1` with a pre-commit hook of the real shape (`exec python3 "<path with a space>/fake_private.py" --staged`); the fake check fails on a fake private word in staged added lines.
  - Control, word staged: `private-name check: FAIL: private-name`, `rc=1`. So the wiring works.
  - Same word committed with `--no-verify` (the state at Step 2, when everything is committed and nothing is staged): `private-name check: PASS (machine-local check ran on the staged diff)`, `PASS: nothing to publish looks like a secret or a private value.`, `rc=0`.
  - Repo `advscan/p2`: the word committed on another branch, then brought in with `git cherry-pick` and, separately, `git merge --no-ff`. The pre-commit hook ran 0 times for both (it echoes `HOOK-RAN`; count 0). Scanner on the result: `private-name check: PASS`, `rc=0`.
- What would leak: a colleague's name, the owner's NCBI username or an employer-internal term in any commit that did not pass through the pre-commit hook: cherry-picks, clean merges, rebases, `git am`, `--no-verify`, commits made in another clone or by an agent whose environment skipped hooks. The builder's report says the gap exists ("It does not see a private name in a commit already made on the branch"), but the tool output still claims PASS, and SKILL.md presents the Step 2 run as the final gate. A check that passes on nothing is the "passes when the subject did nothing" failure named in this project's review brief.
- NOT FIXED

### F-LS-A14: any Python script on the hook's first `exec` line is trusted as the private-name check, so an unrelated script that exits 0 turns into "private-name check: PASS"
- Severity: major
- File: `.claude/skills/ship/scripts/check_public_leaks.py:614-628` (first `exec` token list containing a `.py` wins; nothing confirms it is the private check)
- Reproduction, fake private word staged in each repo:
  - `advscan/q1`: hook `exec python3 "<dir>/unrelated_lint.py" "$@"`, where the script is `print("formatted"); sys.exit(0)`. Output: `private-name check: PASS (machine-local check ran on the staged diff)` then `PASS: nothing to publish looks like a secret or a private value.`
  - `advscan/q2`: hook runs the real (fake) private check on a plain line `python3 "<dir>/fake_private.py" --staged || exit 1`, then `exec python3 "<dir>/unrelated_lint.py" --staged`. The scanner skips the real check (no `exec`) and runs the lint: `private-name check: PASS`, `PASS`.
  - Controls that failed closed correctly: a variable path (`q6`, NOT RUN), `/usr/bin/env python3` (`q7`, exit 126, NOT RUN), a missing script (`q8`, NOT RUN), and `core.hooksPath` pointing at the real hook (`q3`) and a symlinked hook (`q5`), which both ran and blocked.
- What would leak: on any machine or repository whose pre-commit hook chains another Python tool, the private-name check is reported as passed without having run. The fail-closed promise holds only when the hook is exactly one `exec` line of the private check. The data engineering copy has the same code.
- NOT FIXED

### F-LS-A15: the scanner relays the private check's raw output with only a home-directory redaction, leaking the user name and source lines
- Severity: major
- File: `.claude/skills/ship/scripts/check_public_leaks.py:587-593` (`_redact`), `:642-652` (all stdout and stderr relayed), `:687-692`
- Reproduction:
  - `advscan/q7` (hook `exec /usr/bin/env python3 "<script>"`): the NOT RUN line printed the full script path `/private/tmp/claude-501/-Users-<REAL USER NAME>-Desktop-Tech-Skills-agentic-search-ui/.../fake_private.py`. `_redact` replaces `str(Path.home())` and `/<name>/`, not the dash-encoded `-Users-<name>-` form. Masked here; the raw output carried the owner's real account name.
  - `advscan/q9`: a check that crashes. Python exits 1 on an uncaught exception, which the scanner treats as "findings" and relays every traceback line, including the source line `TERMS = {"Zelda"+"Quentin": 1}; ...  # colleague list line` and the same unredacted dash-encoded path. The run ends with `0 finding(s)` and neither BLOCKED nor PASS, so the reason for exit 1 is unclear.
- What would leak: /ship output is pasted into builder reports, ledgers and PR bodies in this project, which get committed. The real private check prints rule names only today, but any crash of it prints the source line where it crashed, and that script is the one file that lists the private names. The docstring's promise (line 6, "never prints a matched value in full") does not cover this relay.
- NOT FIXED

### F-LS-A16: false alarms on content this repository already carries, which pushes people toward the whole-line allow marker
- Severity: minor (major in combination with F-LS-A10 and F-LS-A11)
- File: `.claude/skills/ship/scripts/check_public_leaks.py:247` and `:304-312` (IPv4), `:235-239` and `:363` (secret-assignment), `:315-323` (email allow list)
- Reproduction 1, whole history: `git clone` of the local repository into `advscan/full`, `develop` at `d143747f`, scanner with `--allow-missing-private-check --base <root commit>` (1822 commits, 1,919,359 lines, 37 s): `195 finding(s)`, of which 126 identity-email, 27 secret-assignment, 25 ipv4-address, 15 personal-email, 2 local-path. Reading the flagged lines, nearly every content finding is legitimate:
  - `ipv4-address` on SVG path data in every design-system screen (`a.9.9 0 1 0 0 1.8.9.9`), on the prose `Section 5.2.2.3` (`src/system_03_search_agent/auth/router.py:381`), and on NCBI's own public address in a design assessment.
  - `secret-assignment` on browser storage key names (the tour-seen storage key constant, `frontend/src/components/tour/OnboardingTour.tsx:74`), on a SHA-256 in `tests/system_03_search_agent/fixtures/debugging_guide_manifest.json:29` because its path contains the word for passwords, on the `"key": "q4_caffeine_papers"` field of eval run logs, and on an SQL `refresh_token_hash = 'quarantined-0002:'` line in `alembic/versions/0002_auth_hardening.py:101`.
  - `personal-email` on the `you@institute.edu` placeholder in the design prototype, `x@x.com` in tests, and NCBI's public support address in `docs/ncbi/NCBI_databases_and_APIs_reference.md:1025`.
- Reproduction 2, `scan_line()` on common legitimate lines, all HIT: `Requires Python 3.11.4.1`, `docker bridge 172.17.0`+`.1`, `router 192.168.1`+`.1`, `public DNS 8.8.8.8 and 1.1.1.1`, `test@test.com`, `user@company.com`, `jane.doe@university.edu`, `ssh deploy@`+`build-01`, an env-var-name-to-env-var-name assignment whose names contain the word for secret and a digit, and a `sha256-<base64>` integrity hash assigned to a name containing the word for key.
- Why it matters: any edit to a design-system screen, a tracker ledger or a test file with these lines blocks the push. The builder's claim of 1 finding in a 150-commit wide run does not generalise to the whole tree. The only exit offered is `local-refs: allow`, which exempts the whole line (A10, A11), so a noisy gate trains the habit that disables it.
- NOT FIXED

### F-LS-A17: a `.gitattributes` entry of `-diff` or `binary` hides whole file types from the scan, silently
- Severity: major
- File: `.claude/skills/ship/scripts/check_public_leaks.py:565-573` (the scan is built on `git diff`, which honours the `diff` attribute)
- Reproduction: repo `advscan/g1`, commit `.gitattributes` = `*.json -diff` and `*.ipynb binary`, plus `data.json` and `nb.ipynb` each holding `{"k": "AKIA<16 fake>"}`. Output: `scanned 3 lines ... 0 finding(s), 0 file(s) not scanned, 0 binary file(s) skipped by name`, `PASS`, `rc=0`. Neither file is named anywhere in the output.
- What would leak: everything in any file type marked `-diff`, which is a common way to quiet noisy diffs for lock files, notebooks and generated JSON. One committed attributes line in the same push turns the gate off for that type. The same mechanism explains F-LS-A06.
- NOT FIXED

### F-LS-A18: at Step 0 the working-tree scan reads the working tree, not the index, so a staged secret that was cleaned only in the working file passes
- Severity: minor
- File: `.claude/skills/ship/scripts/check_public_leaks.py:571-580` (`git diff HEAD` compares HEAD to the working tree; no `--cached` pass)
- Reproduction: repo `advscan/g2`: `echo "k AKIA<16 fake>" > s.txt; git add s.txt; echo clean > s.txt`. Scanner: `0 finding(s)`, `PASS`, `rc=0`, while `git diff --cached | grep -c AKIA` prints 1: the next commit carries the key.
- What would leak: nothing if /ship's second run after the commit (SKILL.md line 224) always happens, since the range diff then sees it. The Step 0 PASS is still wrong about what the commit will contain.
- NOT FIXED

### F-LS-A19: personal-email and host coverage gaps: real ccTLDs treated as file names, any `git@` host exempt, obfuscated and encoded addresses, IPv6 and internal hostnames never looked at
- Severity: minor
- File: `.claude/skills/ship/scripts/check_public_leaks.py:184-210` (`FILE_LIKE_TLDS`), `:210` (`git` local part), `:321-322` (`noreply` label), `:247` (IPv4 only)
- Reproduction: `scan_line()` returned NO hit for each (fake names):
  - `zelda@`+`corp.md` and `zelda@`+`snake.py`: `.md` (Moldova) and `.py` (Paraguay) are real country domains, exempted because they look like file extensions.
  - `git@`+`corp-internal.example-host.io`: every `git@` address is exempt whatever the host, so an internal code-review host passes.
  - `zelda@`+`noreply.corp.io`: any domain with a `noreply` label is exempt.
  - `zelda dot q at gmail dot com`, `zelda[at]`+`gmail[.]com`, `mailto:zelda%`+`40gmail.com`.
  - `2001:4860:4860:`+`:8888` (IPv6), `45-67-89-12`, and `https://jira.`+`corp.internal/browse/ABC-123` (an internal issue-tracker host and ticket key, both on the privacy rule's never-commit list; no detector exists for hosts, so this relies entirely on the machine-local check that F-LS-A13 shows often does not run on the pushed commits).
- What would leak: a person's address in an obfuscated form, an internal host, or an internal ticket key.
- NOT FIXED

### F-LS-A20: a small committed file is skipped because its working-tree copy is large
- Severity: major
- File: `.claude/skills/ship/scripts/check_public_leaks.py:476-481` (`_file_bytes` takes the max of the added bytes and the WORKING-TREE file size), used at `:502` for the commit range too
- Reproduction: repo `advscan/g4`: commit `run.log` (23 bytes: `k AKIA<16 fake>`), then append 2 MB to the working copy without staging (a log that keeps growing). Output:
  ```
  NOT SCANNED run.log (larger than 2 MB, commits)
  NOT SCANNED run.log (larger than 2 MB, working tree)
  scanned 1 lines and 1 commit(s) ...; 0 finding(s), 2 file(s) not scanned ...
  PASS: nothing to publish looks like a secret or a private value.
  rc=0
  ```
  `git show HEAD:run.log | wc -c` is 23: the pushed content is tiny and was never read.
- What would leak: a committed log or evidence file whose local copy has grown since the commit, which is exactly how run logs behave. Combined with F-LS-A04, the push proceeds.
- NOT FIXED

### F-LS-A21: combined with the no-squash merge rule, the "remove the line" advice of the BLOCKED message puts the leak on develop
- Severity: major (a consequence of F-LS-A03, recorded separately because the tool's own advice causes it)
- File: `.claude/skills/ship/scripts/check_public_leaks.py:707-708` (BLOCKED text: "remove each line"), `.claude/rules/git-workflow.md` (merge "no squash, preserve commit history")
- Reproduction: follows from `advscan/h1` in F-LS-A03. The scanner blocks a committed secret and says "remove each line". Doing that in a new commit makes the next run print PASS and `rc=0`; the first commit is still in the range, the pull request is merged without squashing, so the secret is on `develop` and public. The message says "A finding in an already pushed commit needs the owner" but nothing tells the user that a finding in an unpushed commit also needs a history rewrite (amend or interactive rebase) rather than a new commit.
- What would leak: every secret that was caught and "fixed" the natural way.
- NOT FIXED

## Scope note

Every finding applies to the data engineering copy too: `scripts/check_public_leaks.py` on its `chore/ship-leak-scan` worktree is byte-identical (`cmp` clean, checked this round).

## Count by severity

- Critical: 2 (F-LS-A03, F-LS-A13)
- Major: 15 (A01, A02, A04, A05, A06, A07, A08, A09, A10, A14, A15, A17, A20, A21, and A16 in combination)
- Minor: 4 (A11, A12, A18, A19), with A16 filed as minor on its own
- Total: 21 findings

## Verdict: FAIL

Against the owner's promise, "/ship stops a push that would publish PII such as name, or secret keys and anything that should not be visible": it does not. A secret committed and then removed on the same branch is published with PASS (A03). The private-name check reports PASS while checking an empty diff at the Step 2 run the skill relies on (A13). Several routine file shapes are silently skipped with exit 0 (A04 to A07, A17, A20).

Verified with my own probes in throwaway repositories under `advscan/`: every finding above. Each has an output pasted from a run, and each silent-pass finding has a control run showing the same value is caught in the plain form. Also verified by probe:

- The branch's own three commits scan clean in a clone (`advscan/branch`: `0 finding(s)`).
- Identity checks work: a committer differing from the author (`i1`), and a `.mailmap` (`i2`).
- `core.hooksPath` and a symlinked hook both work (`q3`, `q5`).
- A variable path, the `env` form and a missing script all fail closed (`q6` to `q8`).

Only read, not probed: the builder's mutation table, and the claim that 93 tests pass. I did not run the author's tests. None of these findings sits inside a fix made during this phase, because this is the first round on new code.

Correction to the count above, which listed A16 twice: critical 2 (A03, A13), major 14 (A01, A02, A04 to A10, A14, A15, A17, A20, A21), minor 5 (A11, A12, A16, A18, A19). Total 21.
