---
description: "Before disabling the sandbox for a failed command, classify the failure (filesystem deny, Layer-7 HTTPS block, Layer-4 SSH) and apply the durable fix that keeps the security boundary intact."
scope: portable
alwaysApply: true
---

## Diagnose before disabling the sandbox

The sandbox is a security boundary. `dangerouslyDisableSandbox: true` removes it for one command. Reaching for it on the first failure trades that boundary for convenience and hides a fixable root cause. Before you disable anything, classify the failure. Most sandbox failures have a durable fix that keeps the boundary intact.

### The three failure classes

| Symptom | Class | Durable fix | Override needed? |
|---------|-------|-------------|------------------|
| "Operation not permitted", "could not lock", write blocked to a path outside the allowlist | Filesystem deny | Write to an allowed path (scratchpad, repo dir). If a protected path legitimately must change (e.g. `.git/config`), that one write needs the override. A `git pull` whose incoming commits rewrite protected paths is one named operation and takes the override for the whole pull. | Only for the single protected-path write, or a named protected-path operation such as a pull |
| Connection refused or blocked to an `https://` host | Network Layer-7 | The proxy allows HTTPS to allowlisted hosts. Add the host with `/sandbox`. | No |
| Connection fails to a raw TCP or SSH endpoint (e.g. `git@github.com:22`) | Network Layer-4 | The HTTP proxy cannot tunnel raw SSH regardless of allowlist. Switch the tool to HTTPS (e.g. `git remote set-url` to `https://`). | Only as a last resort if no HTTPS path exists |

The load-bearing line: `/sandbox` tunes the HTTPS allowlist. It cannot make SSH work. If the failure is SSH, do not add hosts to the allowlist and do not disable the sandbox. Switch to HTTPS.

### Worked example: git push over SSH

`git push` failed under the sandbox because `origin` was an SSH remote (`git@github.com:...`). SSH is Layer-4, and the sandbox proxy is Layer-7, so it could never tunnel the connection. The durable fix was one command:

```bash
git remote set-url origin https://github.com/<owner>/<repo>.git
```

After that, pushes ride the already-allowlisted HTTPS path with no override. `github.com` and `api.github.com` are allowlisted for HTTPS. The `.git/config` write itself was filesystem-denied and needed the override once, which is correct: `.git/config` is protected precisely because it controls the push destination.

A `git pull` whose incoming commits rewrite sandbox-write-protected paths is the filesystem-deny class, not a network problem, so `/sandbox` does nothing for it. Like the `.git/config` write above, it is a single named operation and takes the override once.

### Prove the fix, do not assert it

After a durable fix, verify with evidence from the actual command path, not a claim that it works. For a push over HTTPS, the proof is that the remote actually advanced: push, then compare the local and remote commit hashes.

```bash
git push origin HEAD
git rev-parse HEAD origin/main   # both hashes must be identical
```

Identical hashes prove the push authenticated (a rejected or read-only credential leaves `origin/main` behind) and reached the remote through the sandbox proxy. To check auth before pushing without touching the remote, `git ls-remote origin >/dev/null && echo reachable` returns exit 0 only when the credential works. This is the same discipline as `goal-contracts`: stop on verified evidence, not on feel.

Do not capture a verbose HTTPS auth trace to prove a push. `GIT_CURL_VERBOSE=1` and `GIT_TRACE_CURL=1` print the request headers, and `GIT_TRACE_REDACT` masks only the older HTTP/1.1 log format, not the HTTP/2 frame trace curl emits when the server negotiates `h2` (the default for GitHub). A verbose push captured for handshake evidence can print the `Authorization: Basic <token>` header in cleartext into the session transcript, forcing a credential rotation. The hash comparison above proves the same thing and leaks nothing.

### Three-state permissions

Allow:
- Classify a sandbox failure into one of the three classes before acting
- Add an HTTPS host to the allowlist via `/sandbox` for a Layer-7 block
- Apply a durable protocol switch (SSH to HTTPS) for a Layer-4 block
- Retry once with `dangerouslyDisableSandbox` for a single, named, protected-path write that legitimately must happen (e.g. `.git/config`), or a named protected-path operation such as a `git pull` whose incoming commits rewrite protected paths

Ask:
- Before disabling the sandbox for anything broader than a single named command

Deny:
- Never reach for `dangerouslyDisableSandbox` as the first move on a network failure
- Never add hosts to the allowlist to "fix" an SSH failure (the allowlist does not touch Layer-4)
- Never claim a fix worked without evidence from the actual command path
- Never capture a verbose HTTPS auth trace (`GIT_CURL_VERBOSE`, `GIT_TRACE_CURL`) to prove a push; `GIT_TRACE_REDACT` does not cover the HTTP/2 frame trace, so the token leaks in cleartext. Prove with the hash comparison instead.

The test: before disabling the sandbox, did I classify the failure (filesystem, Layer-7 HTTPS, or Layer-4 SSH) and try the durable fix that keeps the boundary intact?
