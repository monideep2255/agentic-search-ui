# Claude security plugin usage

On-demand deep security scanning for any repository, installed at user scope so every session of the LLM CLI tooling, in every project, can reach it. This file replaced a link into the owner's private notes on 2026-10-17 (`DECISIONS.md`); its path stays fixed because the locked technical specification names it.

## Table of contents

- [What it is](#what-it-is)
- [How to run a scan](#how-to-run-a-scan)
- [How to apply fixes](#how-to-apply-fixes)
- [The always-on sibling: security-guidance](#the-always-on-sibling-security-guidance)
- [Where this fits](#where-this-fits)

## What it is

The `claude-security` plugin is an on-demand, multi-agent security scanner from the official plugin marketplace (`claude-plugins-official`). It is installed at user scope, so it is available in every repository without per-project setup. You trigger it yourself when you want a scan. It does not run in the background.

It is one of four separate security tools in the LLM CLI tooling. Keep them straight:

| Tool | When it runs | Install needed |
|------|--------------|----------------|
| /security-review | Single pass on your branch, when you ask | No, built in |
| security-guidance plugin | In session, reviews as code is written and on commit | Yes, sibling plugin |
| claude-security plugin | On demand, deep multi-agent scan | Yes, this one |
| Code Review | At pull request time | Some paid plans only |

## How to run a scan

After `/reload-plugins`, run `/claude-security` and pick Scan codebase, or say "scan commit abc1234" or "scan my branch".

## How to apply fixes

Fixes are delivered as patch files, not applied automatically. This keeps a human in the loop before any code changes, which matches the AI security standard of requiring approval for anything that changes code.

1. Run `/claude-security` again and pick Suggest patches.
2. The plugin writes patches to a timestamped folder: `CLAUDE-SECURITY-<timestamp>/patches/`.
3. Review the patch before applying it. Read what it changes.
4. Apply one with git: `git apply CLAUDE-SECURITY-<timestamp>/patches/F1.patch`.

Each finding gets its own patch file (F1, F2, and so on), so you apply only the fixes you agree with.

## The always-on sibling: security-guidance

The `security-guidance` plugin is enabled at user scope alongside `claude-security`. Both are global, so every repository sees both.

### What security-guidance is

Where `claude-security` waits for you to ask, `security-guidance` reviews code continuously as it is written. It is the in-session layer: it watches edits as they happen, reviews the diff at the end of a turn, and does a deeper pass at commit or push time. You do not invoke it. It runs on its own whenever code changes.

### How the two complement each other

They cover different moments in the same workflow. One catches problems as you write, the other audits the whole surface on demand. Running both means a fast pass on every change plus a deep pass when you want certainty.

| | security-guidance | claude-security |
|--|-------------------|-----------------|
| Trigger | Automatic, on every code change | Manual, when you run /claude-security |
| Depth | Fast per-change and per-commit review | Deep multi-agent scan of the codebase, a commit, or a branch |
| Output | Inline warnings in session | Findings plus patch files you apply with git |
| Best for | Catching issues the moment they appear | A full audit before a production gate or pull request |
| Standing cost | Model usage on file-changing turns | None until you call it |

The mental model: security-guidance is the seatbelt that is always on, claude-security is the full inspection you book before a long trip. Use the sibling to stay clean as you build, and run the scanner before you ship.

### Token cost of the always-on layer

security-guidance costs model usage in three layers:

- Per-edit pattern check: no model call, so no token cost. It is a plain string match on each edit.
- End-of-turn diff review: one background model review per turn that actually changes files, covering up to 30 changed files, firing at most three times in a row. It uses the strongest model tier by default.
- Commit or push review: a deeper agentic review that can take several model turns per commit, capped at 20 per rolling hour. It also uses the strongest model tier by default.

What this means in practice:

- It does not fill your conversation context every turn the way an MCP server does. The reviews run as separate background calls.
- It only fires on turns that change files. Read-only turns, conversation, and documentation-only work almost never trigger it.
- In heavy coding sessions it adds roughly one extra review per file-changing turn plus one per commit, bounded by the caps above.
- You can point it at a cheaper model or disable individual layers through environment variables if the cost matters.

The on-demand `claude-security` plugin has none of this standing cost. It runs only when you call it.

## Where this fits

Use it before shipping any code that touches user input, queries, redirects, secrets, or agent-to-agent payloads, where an unvalidated cross-agent payload is exactly what a deep scan catches before it reaches a production gate. In this repository, the pull request template and the `release-workflow` skill name it.
