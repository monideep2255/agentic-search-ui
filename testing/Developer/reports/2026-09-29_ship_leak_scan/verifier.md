# Fresh verifier: public-repository leak scanner

Date: 2026-09-30. Branch `chore/ship-leak-scan` at 7e6c62ad. Role: fresh verifier, no prior context. Files findings, fixes and closes nothing. Probes run in throwaway repositories under the session scratchpad `verscan/`.

## Verdicts and findings

### Mandated runs (run once, to exit)

- System 3 `tests/ci/test_check_public_leaks.py`: `232 passed in 61.75s`.
- Data engineering `tests/scripts/test_check_public_leaks.py`: `232 passed in 61.47s`.
- `cmp` of the two `check_public_leaks.py` copies: no output, rc 0 (byte-identical).

These are the author's tests and are reported only as run; every verdict below rests on my own probes.

### History probes (own throwaway repositories `verscan/p01` to `p13`, bare origin plus clone, fetched)

- J02 / A03 added then removed: FIXED. `p01` (edited away) `FAIL commit feff98f8 cfg.txt:1 [aws-access-key] A***(20 chars)`, rc=1. `p02` (file deleted later) same, rc=1.
- Merge of a side branch that added then removed: caught, `p03` rc=1.
- Evil two-parent merge (new file only in the merge commit): caught, `p04` rc=1. Conflict resolution adding a line: caught, `p05` `FAIL commit 595b89ac c.txt:2`, rc=1.
- Rebase onto a moved develop: caught, `p07` rc=1.
- Secret in a commit message: caught, `p08` `message:3 [github-token] g***(40 chars)`, rc=1.
- Secret in a new file name: caught and the name hidden, `p09` `file name <file name hidden, k***(29 chars)>`, rc=1.
- Untracked file content: caught, `p11` rc=1. Staged then cleaned in working copy (A18): FIXED, `p12` rc=1.
- Allow marker on a line carrying an AWS id, a URL password and a `PASSWORD=` value: all three still fire, `p13` rc=1 (J12 marker half FIXED, A11 FIXED for secrets).

### F-LS-V01: a change made only in an octopus merge commit is never read, and the scan passes
- Severity: major
- What: `scan_commits` reads merges with `--diff-merges=remerge`. For a merge with three or more parents git's remerge diff is empty, so a file added only in the octopus merge commit is never scanned. The first-parent fallback runs only when the remerge command fails, which it does not.
- Reproduction: `verscan/p06`: branches `a` and `b` off `work`, one commit on `work`, then `git merge --no-ff --no-commit a b`, add `oct.txt` = `k A***(20 chars)` (AWS-shaped, assembled at run time), commit. `git cat-file -p HEAD` shows 3 parents; `git log -p --diff-merges=remerge -1 HEAD` output is 98 bytes and does not contain `oct.txt`; `--diff-merges=first-parent` does. The scanner: `scanned 7 lines, 3 file names and 4 commit(s) ... 0 finding(s)` / `PASS: nothing to publish looks like a secret or a private value.` / rc=0.
- Why it matters: a secret reaches the push with exit 0. Octopus merges are rare in this project, so the path is narrow, but it is the exact "a merge" route the brief names, and it sits in this round's new merge handling.
- Inside a fix made during this phase: yes (the remerge reading was added by the fix round for J02).
- NOT FIXED

### F-LS-V02: a token or AWS id glued to a word character by `_` is missed, including in file and directory names
- Severity: minor
- What: the vendor shapes open with `\b`, and `_` is a word character, so `backup_` + an AWS id, or `d_` + a GitHub token, never matches.
- Reproduction: `scan_line` on the bare GitHub token returns `['github-token']`; on `d_` + the same token returns `[]`; `backup_` + an AWS-shaped id + `.txt` returns `[]`, while `backup-` + the same id returns `['aws-access-key']`. Repository `verscan/p10`: a commit adding `d_<github token>/x.txt`, then a commit deleting it: rc=0, `PASS`. `p11`: an untracked file named `n_<github token>`: the name is not reported.
- Why it matters: file and directory names are where a snake_case join is normal (`backup_<id>.txt`); the token is published in the path with exit 0.
- NOT FIXED

### Encoding, size and attribute probes (`verscan/p20` to `p36`)

- J04 / A04 over 2 MB: FIXED. `p20` committed 2.2 MB text: `TOO LARGE commit c99552e4 big.log (2200023 bytes ...)`, rc=1. `p21` untracked: rc=1.
- J05 / A06 NUL-byte text: FIXED, `p25` `FAIL commit 28210966 dump.txt:2 [aws-access-key]`, rc=1. UTF-16 with BOM and BOM-less LE: FIXED, `p26` both files FAIL, rc=1.
- J06 / A17 `.gitattributes`: FIXED. `p27` with `*.json -diff`, `*.ipynb binary` and a `diff=foo` textconv that rewrites the key: all three files FAIL, rc=1.
- A05 text under `.pdf` and `.db`: FIXED, `p28` rc=1.
- J03 / A07 long line: FIXED, `p29` value after 150,000 characters found, rc=1.
- A09 notebook escaping: FIXED, `p30` `[secret-assignment] N***(32 chars)`, rc=1.
- A10 CR-only file with one marker: FIXED, `p31` the email and the address on the other CR-separated lines fire, rc=1 (both reported at `cr.txt:1`, git's line, which is a cosmetic location only).
- A20 working copy grew: FIXED, `p32` the committed 23-byte key is found (`FAIL commit 88bffaa6 run.log:1`), rc=1.
- A committed symlink whose target is a home path: caught, `p34` rc=1.
- Binary between 2 and 16 MB with a key in a printable run: caught, `p22b` rc=1.
- Non-noreply author identity: caught, `p36` `[identity-email] z***(17 chars)`, rc=1.
- Base64-wrapped key (A01 part, named open): OPEN AS NAMED, `p35` rc=0 PASS.

### F-LS-V03: a binary file never changes the exit code, so a key inside a file over 16 MB, a compressed file or UTF-32 text is published with exit 0 and PASS
- Severity: major
- What: `report.binaries` only prints `NOT SCANNED ... a person must look at it` and never sets `exit_code`; the final line still says `PASS: nothing to publish looks like a secret or a private value.` Over `MAX_BINARY_BYTES` (16 MB) not even the printable runs are read. Content that is text to a person but binary to `classify` (UTF-32, gzip) is never decoded.
- Reproduction:
  - `verscan/p22`: commit `blob.bin`, 17 MB of random bytes with `k A***(20 chars)` in the middle. Output: `NOT SCANNED commit d6cbb157 blob.bin: binary, a person must look at it (only its text runs were read)` / `0 finding(s) ... 1 binary file(s) for a person to look at` / `PASS: ...` / rc=0. (The same shape at 6 MB, `p22b`, is caught, so the 16 MB cap is the gate.)
  - `p23`: `u32.txt` = two lines encoded UTF-32-LE without a BOM, the second carrying the key: `NOT SCANNED`, `PASS`, rc=0.
  - `p24`: `env.txt.gz` = gzip of the key line: `NOT SCANNED`, `PASS`, rc=0.
- Why it matters: the owner's hard line is that no secret is pushed. /ship gates on the exit code, and the last line of the output says PASS. The docstring ("the scan cannot read a picture") covers screenshots, but a compressed export, a large data file or a UTF-32 log carries readable text a secret can sit in. At minimum a binary the scan could not read should block unless a person confirms it, the same fail-closed stance the TOO LARGE path now takes; the PASS line should never follow a NOT SCANNED line.
- NOT FIXED

### F-LS-V04: a UTF-32 file with a BOM is decoded as UTF-16, read as noise, and is neither found nor listed
- Severity: major
- What: `classify` tests `data.startswith((b"\xff\xfe", b"\xfe\xff"))` first. The UTF-32-LE BOM is `ff fe 00 00`, so the file is decoded as UTF-16, every character comes out followed by a NUL character, no detector matches, and because it counts as text it is not listed as NOT SCANNED either.
- Reproduction: `verscan/p23b`: commit `u32b.txt` = `"note\n" + "k <AWS-shaped id>\n"` encoded with Python's `utf-32` codec (BOM included). Output: `scanned 4 lines, 1 file names and 1 commit(s) ...; 0 finding(s), 0 file(s) too large to scan, 0 binary file(s) for a person to look at` / `PASS: ...` / rc=0. The file is named nowhere in the output.
- Why it matters: a silent pass with exit 0 and no trace, the class of defect the fix round set out to close (J05, A06). UTF-32 files are uncommon, so the reach is narrow; the silence is the problem.
- Inside a fix made during this phase: yes (the UTF-16 decoding added for A06).
- NOT FIXED

### F-LS-V05: a file tracked by git LFS is read as its pointer, so its content is published with exit 0
- Severity: minor (unsure of reach: neither repository tracks a file with LFS today, `git ls-files '*.gitattributes'` is empty in both; git-lfs 3.3.0 is installed on this machine with `filter.lfs.required=true` in the global config)
- What: the scan reads commit blobs. For an LFS-tracked path the blob is the three-line pointer; the real content is uploaded by git-lfs's own pre-push hook to the LFS store, which is public for a public GitHub repository.
- Reproduction: `verscan/p37`: `git lfs track "*.dat"`, then `key.dat` = `k <AWS-shaped id>`, committed together with `.gitattributes`. `git cat-file -p HEAD:key.dat` is a pointer (`starts with version https://git-lfs: True`, key in blob: False); the working file holds the key. Scanner: `0 finding(s) ... 0 binary file(s)` / `PASS` / rc=0.
- Why it matters: one `git lfs track` line for a large data file, the natural answer to "TOO LARGE: shrink or split it", moves that file's content outside the scan with no line in the output. A cheap guard: treat an LFS pointer blob as NOT SCANNED and read the working-tree file, or block on it.
- NOT FIXED

### Private-name check probes (`verscan/q1` to `q9` with a stand-in named `verify_no_local_refs.py`; `r1` to `r6` with the owner's real check reached through a copy of the real hook's exec line, a known private repository name as the planted term, throwaway repositories only)

- J10 / A13 the check never saw the outgoing commits: FIXED.
  - Stand-in: a line added then removed (`q1`) `FAIL private-name check: commit 572e2ecb a.txt:1 [private-word]`, rc=1; a message line (`q2`) `commit ce3872c7 message:3`, rc=1; an untracked file name (`q3`) and a committed directory name (`q3b`) both reported with the name hidden, rc=1.
  - Real check: a line added then removed (`r1`), the same line starting `# ` (`r2`), `## ` (`r3`) and indented `  # ` (`r4`) are all caught in message mode, `FAIL private-name check: commit <sha> n.md:1 [owner-term]`, rc=1; a tracked line (`r5`) caught in both modes; a tracked file name (`r6`) caught with the name hidden. The real check prints repository-relative paths (`n.md:1`).
- A14 any exec script trusted: FIXED as designed. A check on a non-exec line then `exec true` (`q6`): `NOT RUN ... names verify_no_local_refs.py but not on its exec line`, rc=1. A missing script (`q8`): NOT RUN, rc=1. The `/usr/bin/env python3` form (`q9`) runs. Residual, by design: any script whose name is exactly `verify_no_local_refs.py` and exits 0 is trusted (`q5`: PASS, rc=0, with the private term committed).
- A15 raw output relayed: FIXED. A check that crashes with a traceback carrying a planted name and a home path (`q4`): `NOT RUN ... exited 1 in message mode without a finding line it could name`, rc=1, and neither value appears in the output. Residual: a check that printed an absolute path in its own `FAIL: <path>:<n>: <name>` format would have that path relayed verbatim (`q7` printed the full scratchpad path, which carries the account name in dash-encoded form); the owner's real check prints relative paths (`r5`), so this does not leak today.

### F-LS-V06: a git timeout prints the repository's absolute path, and names the wrong command
- Severity: minor
- What: `_run` builds `what` from the first two non-flag arguments. Every `_git` call starts `git -C <root> -c core.quotePath=false <subcommand>`, so the two arguments are the absolute repository root and `core.quotePath=false`; the subcommand that hung is never named.
- Reproduction: `verscan/p6.py` imports the script, makes `subprocess.run` raise `TimeoutExpired` for `git log`, and calls `main(["--allow-missing-private-check"])` in `verscan/p01/w`: rc=2, output `CANNOT RUN: \`git <ROOT> core.quotePath=false\` took longer than 180 s and was stopped. ...` where `<ROOT>` is the full path (output has root path: True; has account name: True, since the path runs through the owner's home folder).
- Why it matters: the docstring promises the output carries only a location, a category and a mask. /ship output is pasted into reports and ledgers in this project, and this line puts a home path, a never-commit category, into that paste. It also tells the reader nothing about which git command hung. The fix round added this wrapper for J01.
- Inside a fix made during this phase: yes (J01).
- NOT FIXED

### F-LS-V07: a real password containing the word "secret" or "passw", or starting `$` or `my_`, is treated as a placeholder and passes
- Severity: major
- What: `PLACEHOLDER_SUBSTRINGS` carries `secret` and `passw`, and `_is_stand_in` also exempts any value starting `$` or matching `^(?:your|my)[-_ ]`. These apply to password assignments and URL passwords (and, through `is_placeholder`, to every shape but the private key). Human-chosen passwords very often contain exactly these words.
- Reproduction: `verscan/p7.py`, `scan_line` on runtime-assembled values, each with 6 random characters `k` inside. Written here with the variable name and the scheme elided so this file does not trip the secret hook:
  - a whole-line env assignment `DB_<P-WORD-NAME>` set to `MySecret` + k + `7` returns `[]`; set to `Passw0rd` + k + `9` returns `[]`; the control set to `Qz` + k + `81x` returns `['password-assignment']`.
  - a database URL whose password is `Passw0rd` + k, host `db.prod.acme.io`, returns only `['personal-email']`, caught by accident because `app:<pw>@<host>` also reads as an address; the control with `Qz` + k + `81` returns `['url-password', 'personal-email']`. If the pending owner request to make emails warnings lands, this line passes with exit 0.
  - a YAML password value starting `$` returns `[]`; an API token assignment whose value starts `my_prod_` returns `[]`.
- Why it matters: a live database password of the kind people actually choose is published with exit 0. The stand-ins the filter was meant to spare (`<your-key>`, `changeme`, `sentinel`, `do-not-leak`) do not need a bare `secret` or `passw` substring to be spared.
- NOT FIXED

### F-LS-V08: credentials in ordinary command lines and headers are not detected
- Severity: minor (A01 was filed on the assignment and vendor forms, which are fixed; these forms were not in it)
- What: no detector covers a password passed as a command argument or a non-Bearer authorization scheme, and a password under 8 characters or a letters-only key is never a finding.
- Reproduction (`verscan/p7.py`, `scan_line`, each returns `[]`): `curl -u deploy:` + a 10-character value; the Postgres password environment variable set inline before `psql` (10 characters, not a whole line); `mysql -u app -p` + a 10-character value; an authorization header using the `Token` scheme with 40 random characters; a quoted 7-character password assignment; an exported secret-key variable holding 40 random letters with no digit.
- Why it matters: pasted shell history and runbooks, a common route into evidence files in this project, carry exactly these forms.
- NOT FIXED

### Shape re-derivation (`verscan/p8.py`, `scan_line`, values assembled at run time; `p40` in a commit)

- A01 missing secret shapes: NOT FIXED for the adversary's first line, the rest FIXED.
  - Still `[]`: `<pw> = <12 random alnum>` and `<pw> = <20 random letters>`, exactly the adversary's first two reproductions. `PASSWORD_BARE_RE` accepts `=` only with no space around it, `PASSWORD_QUOTED_RE` needs quotes, and `ASSIGNMENT_RE` needs 16 or more mixed characters. In a commit (`p40`): `alembic.ini` line `<pw> = <12 chars>` and `app.properties` line `db.<pw> = <12 chars>` are not reported, while the control `b.cfg` line `<pw>=<same value>` is (`FAIL commit 3a96550a b.cfg:1 [password-assignment] x***(12 chars)`). INI, `.properties` and `.cfg` files write exactly this spaced, unquoted form.
  - Now fire: digits-only, symbol password, PGP header, Slack and Discord webhooks, Stripe, GitLab, Hugging Face, npm, Basic auth, `pwd:`, `auth:`, `"credential":`, `passphrase =`, `credentials =`, `token =>`, a URL password containing `/`.
  - Named open and still open: a base64-wrapped key (`p35`), a key split across literals (not probed).
- J09 PGP key: FIXED (`['private-key']`).
- J12 short URL password: FIXED, a 6-character URL password returns `['url-password']`.
- A02 home path forms: FIXED, all eight adversary forms return `['local-path']`.
- J18 dash-encoded and pytest paths: FIXED, the agent projects path and `pytest-of-<name>` both return `['local-path']`.
- A19 address and host gaps: FIXED for `.md` and `.py` domains, `git@` on a non-forge host, a `noreply` label, `[at]`, `%40`, IPv6 and an internal URL host. OPEN AS NAMED: an address spelled in words and a dash-encoded IP both return `[]`.
- J20 CIDR range names: FIXED, `[]`.

### Ordinary clean pushes (false-block check)

- System 3 worktree, branch `chore/ship-leak-scan`, default run (fetches `origin/develop`, still `d143747f` after the fetch), with the real private check and my untracked `verifier.md` present: `private-name check: PASS (... in 9 commit(s) and the working tree, and every tracked file)` / `scanned 3729 lines, 7 file names and 9 commit(s) ...; 0 finding(s)` / `PASS`, rc=0.
- Data engineering worktree, branch `chore/ship-leak-scan`: `... in 4 commit(s) ...` / `scanned 2853 lines, 3 file names and 4 commit(s) ... (merge base 97ce835e); 0 finding(s)` / `PASS`, rc=0.
- Scratch clones of both repositories (`verscan/clean_s3`, `verscan/clean_de`), the branch pushed to a scratch bare remote as its `develop` (the state after merge), a copy of the real hook, one plain sentence appended to `README.md` and committed: both `private-name check: PASS`, `scanned 2 lines ... 0 finding(s)`, `PASS`, rc=0.
- The configured commit email in both repositories matches the noreply rule, and so do the last five authors (booleans only), so ordinary commits do not trip `identity-email`.
- Caveat, not a defect: before this branch merges, `--all` over develop's tree finds the six (System 3) and five (data engineering) lines the branch removes, so a push from develop as it stands blocks until the merge. The branch itself carries the fix.

No item found blocks every ordinary push.

Caveat above now verified by probe, not read: `verscan/clean_s3`, a branch from pre-merge `origin/develop` (`d143747f`) plus one plain sentence: six `FAIL private-name check: <path>:<n> [<check>] (already on the base: remove it here and tell the owner)` lines (the rule header, two lines of `verify_adaptation.py`, the tmux quickstart, the GraphQL test fixture, `tracker/phase_1.1.md`), rc=1. So until this branch merges, every push from develop is blocked by design; after the merge a plain push passes (above). Any later term added to the owner's list that matches the tracked tree will likewise block every push until that line is removed; that is the intended whole-tree stance, stated here so it does not surprise.

### Remaining re-derivations

- J01 timeouts: FIXED. `grep -n "subprocess\.\|Popen\|os.system"` on the script finds one `subprocess.run`, inside `_run`, which always passes `timeout`; a timeout is exit 2 (`p6.py`, rc=2). See V06 for what that message prints.
- J08 control bytes in a message: FIXED, `p50` message with 0x1E, 0x1F, 0x01 and 0x7F plus a key: `FAIL commit af016323 message:3 [aws-access-key]`, rc=1, no traceback.
- J11 stale base after a force push: FIXED, `p51`: a second clone force-pushed develop back past the leak commit; the first clone, not fetched, still showed the old tip. The default run fetched and reported `FAIL commit ac0f4d6a leak.txt:1 [aws-access-key]`, rc=1.
- A21 remove-the-line advice: FIXED for the unpushed case (the BLOCKED text now says take the finding out of the commit that added it), but see V09 for a branch that was already pushed.

### F-LS-V09: the BLOCKED advice says "Nothing in the range is pushed yet" even when the flagged commit is already on a remote branch, so a published secret is not sent to rotation
- Severity: major
- What: the BLOCKED text is fixed wording. The scan range is `<base>..HEAD` against `origin/develop`, which includes every commit already pushed to the branch's own remote copy, so the sentence "Nothing in the range is pushed yet, so for example `git reset --soft <merge base>`, fix the files, and make one fresh commit" is false for any branch pushed earlier, which is the normal state of a phase branch with an open pull request (this branch has `origin/chore/ship-leak-scan` itself).
- Reproduction: `verscan/p52`: commit a key on `work`, `git push -u origin work`, then a commit that removes the line. `git branch -r --contains HEAD~1` prints `origin/work`. Scan: `FAIL commit 4973e70b leak.txt:1 [aws-access-key] A***(20 chars)`, rc=1, then `BLOCKED. A finding in a commit is in the history this push would publish ... Nothing in the range is pushed yet, so for example \`git reset --soft 6c59ef96\` ...`.
- Why it matters: the key is already public on the remote branch. The advice tells the person it is not, never mentions rotation for this case (only "a secret already in a pushed commit needs the owner and a rotation", which they have just been told does not apply), and the rewrite it suggests needs a force push, which `git-workflow` forbids. The owner's hard line is exactly this case: a leaked secret must be rotated. A `git branch -r --contains <sha>` check per flagged commit would let the line say "already pushed to <ref>: rotate it now and tell the owner".
- Inside a fix made during this phase: yes (the A21 wording).
- NOT FIXED

### F-LS-V10: git-sync's push block pushes even when the scan fails, if run as written
- Severity: major
- What: the new shell block in `.claude/agents/git-sync.md` (Push section) is `python3 .../check_public_leaks.py > /tmp/leak_scan.txt 2>&1`, `rc=$?`, `tail -40 ...`, `if [ $rc -ne 0 ]; then echo "LEAK SCAN rc=$rc: do not push"; fi`, then `git push  # only when rc was 0`. The `if` only echoes; nothing stops the next line. The gate is a comment.
- Reproduction: `verscan/p60`: a throwaway repository with a copy of the script at the same relative path and a committed AWS-shaped key. The block was cut from `git-sync.md` verbatim and run with `sh -c`, changing only the interpreter (the venv, quoted), the output file (into the scratchpad) and the push target (`git push -q origin work`, since the scratch branch has no upstream). Output: `FAIL commit a355b86f leak.txt:1 [aws-access-key] A***(20 chars)`, `LEAK SCAN rc=1: do not push`, then the push ran: `sh rc 0`, `origin now has branch work: True`, `key is on the remote: True`.
- Why it matters: an agent that executes the code block as one command, the most literal reading of it, publishes the secret it was just told about, and the shell reports success. It is the exact step J17 asked to add. Also minor: the fixed path `/tmp/leak_scan.txt` is shared by any two sessions running at once and is readable by other local users.
- Inside a fix made during this phase: yes (J17).
- NOT FIXED

### F-LS-V11: a NOT SCANNED line says "only its text runs were read" for a file over 16 MB, where nothing was read, and SKILL.md repeats it
- Severity: minor (the exit-code half is V03)
- What: `_add_whole` skips `printable_runs` above `MAX_BINARY_BYTES`, and untracked files above it are listed without being opened, but the output line is the same fixed text. SKILL.md line 68 says a NOT SCANNED file is one "whose printable text was read".
- Reproduction: `verscan/p22` (17 MB, key in the middle): `NOT SCANNED commit d6cbb157 blob.bin: binary, a person must look at it (only its text runs were read)`, `0 finding(s)`, `PASS`, rc=0; the 6 MB twin `p22b` found the key in text run 700.
- Why it matters: the person told to look at the file is also told the text in it was already checked, so they look at the picture and not for a key.
- NOT FIXED

- J17 git-sync: FIXED in the sense the scan is now numbered step 5 in SKILL.md and appears in git-sync's Push and Full sync sequences, but see V10: the git-sync block does not stop the push.
- J19 Output section: FIXED, SKILL.md Output item 2 asks for both runs' exit code, summary line, the private-check line, every NOT SCANNED file and any opt-out flag.

### Report corrections, masking, false alarms and named-open items

- J13 builder.md address: FIXED, `builder.md:150` now says "a public, globally routable IPv4 address on a line that mentions the server" with no value; no dotted quad other than documentation ranges remains in the file.
- J14 fixture characterisation: FIXED, `builder.md:63` now calls it "the scanner's intended policy hit".
- J15 work domains: FIXED, `builder.md:148` says "each at a work domain" and names none; the only domains left in the three review files are GitHub's noreply domains and a public webmail domain inside a masked judge quote.
- J16 masking survivors: FIXED for the one that mattered. My own mutation, `mask` printing the last six characters (`verscan/mut/tail.py`), makes the test file go red (`1 failed, 32 passed`, `-x`). Across every probe above, no six-character run of any planted value appeared in any output (the `leaked_runs=[]` column).
- A16 false alarms: FIXED in the main. SVG path data, `Section 5.2.2.3`, a storage key constant, an SRI hash, an eval `"key"` field, the SQL refresh-hash line, `you@institute.edu`, `x@x.com`, `test@test.com`, `user@company.com`, `Python 3.11.4.1` and public DNS all return `[]`. Still firing: `ssh deploy` + `@build-01` and a Docker bridge address (by the private-range policy), and a four-part version with a two-digit part, `upgrade to 10.12` + `.1.3` (`['ipv4-address']`, a residual false alarm). The before and after count table in `fix.md` was read, not re-run.
- A12 author display names: OPEN AS NAMED (not scanned by the owner's decision; read, not probed). Annotated tag messages: OPEN AS NAMED.
- J07 / A08 file and directory names: FIXED (`p09`, `q3`, `q3b`, `r6`), except the `_` join in V02.

### F-LS-V12: one allow marker exempts private values after a form feed, vertical tab, NEL or Unicode line separator on the same line
- Severity: minor
- What: `physical_lines` splits on `\r\n`, `\r` and `\n` only, while `\x0b`, `\x0c`, `\x85`, ` ` and ` ` are line breaks to Python's `splitlines` and to many editors and renderers. The A10 fix closed CR-only files; these other separators still let one marker cover the text after them.
- Reproduction: `verscan/p16.py`, `scan_line` on `note <marker><sep>mail zelda.q@<webmail>` for each separator: LF control gives `['personal-email']`; VT, FF, NEL, LS and PS each give `[]`. In a commit (`p61`, form feed): `0 finding(s)`, `PASS`, rc=0. Secrets are not affected (the marker never exempts a secret, `p13`).
- Why it matters: a marker placed for one public host also publishes an email or path on what a reader sees as the next line. Narrow, since these separators are rare in hand-written files.
- Inside a fix made during this phase: yes (the A10 line splitting).
- NOT FIXED

## Verdict table

| Status | Findings |
|--------|----------|
| FIXED, by my own probe | J01, J02, J03, J04, J05, J06, J07, J08, J09, J10, J11, J12, J13, J14, J15, J16, J18, J19, J20; A02, A03, A04, A05, A06, A07, A08, A09, A10, A11 (secrets), A13, A14, A15, A16 (main cases), A17, A18, A20 |
| FIXED, with a new defect inside the fix | J17 (V10), A21 (V09), A10 line splitting (V12), J02 merge reading (V01), A06 UTF-16 decoding (V04), J01 timeout wrapper (V06) |
| NOT FIXED | A01, its first reproduction: `<pw> = <value>` unquoted with spaces around `=` (and letters-only) still passes (`p40`) |
| REGRESSED | none of the J or A cases went backwards |
| OPEN AS NAMED | A01 base64 and split literal; A12 author names (owner decision) and tag messages; A19 email in words and dash-encoded IP; J17 pre-push hook |

## New findings

| Id | Severity | Inside this phase's fix | One line |
|----|----------|-------------------------|----------|
| V01 | major | yes | octopus merge change never read, PASS |
| V02 | minor | no | token after `_` missed, including names |
| V03 | major | no | binaries never block: over 16 MB, gzip, UTF-32 pass with PASS |
| V04 | major | yes | UTF-32 with BOM decoded as UTF-16, silent PASS |
| V05 | minor, unsure | no | LFS content outside the scan |
| V06 | minor | yes | git timeout prints the home path |
| V07 | major | no | passwords containing secret, passw, or starting `$` or `my_` pass |
| V08 | minor | no | curl, mysql, inline env and Token-scheme credentials pass |
| V09 | major | yes | BLOCKED says "nothing is pushed yet" for an already pushed branch, no rotation |
| V10 | major | yes | git-sync's push block pushes after a failed scan |
| V11 | minor | no | NOT SCANNED claims text runs were read above 16 MB |
| V12 | minor | yes | marker spans form feed and Unicode line separators |

Six new findings sit inside fixes made during this phase (V01, V04, V06, V09, V10, V12). That fires the review loop's stop condition: escalate to the product owner rather than run another round.

## Does anything block every ordinary push?

No. Both branches pass against their fetched develop, and a one-line change on a scratch clone of each, with the real private check, passes. Before this branch merges, every push from develop is blocked by the six private lines the branch removes (verified), which is the intended behaviour.

## Verified by my own probes versus only read

- Verified by probe: every FIXED, NOT FIXED and OPEN AS NAMED verdict above except the three below; all twelve V findings; both branch runs and both clean one-line pushes; the owner's real private check through the scanner in throwaway repositories (`r1` to `r6`); masking across every probe output; the mask-tail mutation.
- Only read: A12 author display names (the decision and its test), the `fix.md` false-alarm count table (67 to 14), and the 28-row mutation table in `fix.md`. The author's two test files were run once to exit as briefed (232 and 232 passed) and are not relied on for any verdict.

## Final verdict: DO NOT MERGE as it stands

- Blocking item: V10. git-sync's new push block runs `git push` after the scan exits 1, so an agent that runs the block as written publishes the secret the scan just named. It does not block any ordinary push; it fails open. The fix is one line (stop the block on a non-zero code).
- Next, in the owner's order of "secrets are a no-no": V07 and the A01 spaced form (common real passwords pass), V03 and V04 (keys in a file the scan cannot read still end on PASS and exit 0), V09 (a published key is described as unpushed, so it is not rotated), V01.
- Note for the owner: every one of these is a gap in a gate that develop does not have at all today, so merging would still stop more than it lets through. Whether to merge with V10 fixed and the rest named is the owner's call, since six findings sit inside this phase's fixes.

Note for the lead: this report does not pass the scan as written. Line 178 (the A16 bullet) quotes the fake `ssh deploy@` host and the four-part version, giving `FAIL ...verifier.md:178 [ipv4-address] 1***(9 chars)` and `[ssh-host] s***(19 chars)` in a `--no-fetch` run. Both are fake and public-safe; split them with `+` before committing, as the judge and adversary files were. Everything else in the file passed (`private-name check: PASS`). I append only, so I have not changed the line.
