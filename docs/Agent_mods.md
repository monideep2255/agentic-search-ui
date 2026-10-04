# Agent mods guide

Quick answer: type `/mods` in a session to list every mod with its trigger.
This file is the full reference: what each mod does, how it starts, what it blocks, and where it lives.

## Contents

- [How mods load](#how-mods-load)
- [The mods](#the-mods)
- [Slash commands at a glance](#slash-commands-at-a-glance)
- [Turning one off](#turning-one-off)
- [What a mod is not](#what-a-mod-is-not)
- [Known limits](#known-limits)
- [Maintenance](#maintenance)

## How mods load

A mod is a folder under `.claude/skills/mod-<name>/` that holds a plugin manifest. Claude Code loads it automatically as `mod-<name>@skills-dir`.

- Trust: you trust the repository once, when Claude Code asks.
- Start location: start the session at the repository root, not in a subfolder.
- Version: the CLI must be 2.1.287 or later.
- Check: run `/plugin` to see which mods loaded.
- Meaning of Auto: the mod runs on its own, and there is nothing to call.

## The mods

Fourteen mods: six shared with the other agentic search repositories, and eight built for this repository.

### Shared (in all three repositories)

| Mod | What it does | How it starts | What it blocks | Notes |
|-----|--------------|---------------|----------------|-------|
| mod-blast-radius | Dry-runs a risky Bash command, shows what it would touch in a pane, and asks before it runs | Auto, then asks Proceed or Cancel | A risky command until you press Proceed: recursive or forced delete, `find -delete`, destructive git commands, `alembic` migrations, `psql` with DROP or TRUNCATE | Extra rules here: `railway down`, `delete`, `redeploy`, `up`, and variable changes on the live service. The dry run is `railway status` |
| mod-context-weather | Shows context fullness as a weather band above the prompt, with a sparkline, last-turn change, and cache warmth. Nudges you to compact when you step away while the cache is warm | Auto, and `/precompact` | Nothing | Cache window is 5 minutes here, and the nudge fires after 4 idle minutes above 60,000 tokens |
| mod-help | Lists the installed mods, warns when an unknown plugin auto-loads from `.claude/skills`, and reminds you once a day | `/mods` or `/mods <mod-name>` | Nothing | Points at this guide |
| mod-public-repo-guard | Guards `git commit` and `git push` in the public repositories | Auto, and asks Proceed or Cancel before a push to `develop` | Skipped hooks (`--no-verify`, `-n`), force pushes, `--all` and `--mirror`, pushes to `production` or `main`, and any commit or push when the leak scanner fails or is missing | The leak scanner is the one under `.claude/skills/ship/scripts/`. A push to `develop` is allowed only after you confirm |
| mod-replay-theater | Records the file edits of each turn and steps through them one diff at a time in a pane | Auto hint after a turn with edits, or `/replay` | Nothing | Keeps the last 100 steps and 200 diff lines per step |
| mod-secrets-scan | Denies tool calls that carry secret-shaped text, and toasts when a tool result shows one | Auto | Bash, Edit, Write, and NotebookEdit calls holding a key, token, or private key header, in any file type | Read and WebFetch results only toast. No extra patterns or allowed paths are set here |

### This repository only

| Mod | What it does | How it starts | What it blocks | Notes |
|-----|--------------|---------------|----------------|-------|
| mod-citation-drift | After an edit under the synthesis, contracts, or answer components, compares the allowed citation host lists in the frontend, the end to end spec, and the Python contract, and toasts when they disagree | Auto | Nothing | Checks that the lists agree. It does not check that any answer is grounded or any citation is true |
| mod-design-tokens | Runs the design token check after an edit under `frontend/src` and toasts only the findings that are new | Auto | Nothing | Waits 20 seconds between runs and shows up to 3 toasts |
| mod-requirement-trace | Spots a card or phase reference in your prompt and shows its title in the status line. `/trace` lists the source files behind it, with heading lines only | Auto on prompt submit, or `/trace` with a card or phase number | Nothing | Reads card titles from the card table and phase steps from the build board |
| mod-route-capture | Tracks which frontend screens a turn changed, offers a one-line band, and runs the screen capture checks on request, listing pass or fail per check in a pane | Auto band after a turn that edits `frontend/src`, or `/capture [all]` | Nothing | Output goes to the gitignored `logs/capture/` folder |
| mod-stack-status | Shows whether the local API, the Vite dev server, and PostgreSQL are answering, refreshed every 30 seconds | Auto | Nothing | Stays quiet until something has been up |
| mod-test-triple | When a turn ends, looks at route decorators added to web adapter files and toasts any route whose tests show no valid, invalid, or empty input case | Auto | Nothing | A name based heuristic |
| mod-tool-budgets | After an edit to a search agent tool, compares the tool's declared timeout with the per tool timeout table in the tool call budgets rule and toasts on a missing or differing value | Auto | Nothing | A row marked provisional or unsettled gives an informational toast only |
| mod-unescaped-output | Warns when an edit adds unescaped HTML output, a non-literal redirect, an unsafe external link, or SQL built from strings | Auto | Nothing | Warns only. Files with an audited use of a pattern are on an allowlist |

## Slash commands at a glance

- `/mods`: list every mod with its trigger, or `/mods <mod-name>` for one.
- `/replay`: step through the last turn's file edits.
- `/precompact`: compact the conversation now, while the cache is warm.
- `/capture [all]`: screenshot and check the changed frontend screens, or all of them.
- `/trace [card N | phase N.N]`: list the source files behind the current card or phase reference.

## Turning one off

Add `"mod-<name>@skills-dir": false` under `enabledPlugins` in one of two files:

- `.claude/settings.local.json`: this machine only.
- `.claude/settings.json`: everyone who uses the repository.

Example: `{ "enabledPlugins": { "mod-stack-status@skills-dir": false } }`.

## What a mod is not

A guard reads command text. It is a safety net and not a security boundary, because a determined command can be written to slip past a text match. Commit hooks, branch protection, and CI stay the real controls.

Shell hooks in `.claude/settings.json` that each guard complements:

| Mod | Shell hook or control it complements |
|-----|--------------------------------------|
| mod-blast-radius | `block-bash-delete.sh` and the deny list for `rm`, `rmdir`, `sudo`, `dd`, and similar commands |
| mod-secrets-scan | `scan-write-secrets.sh` on Edit and Write, `scan-secrets.sh` on Bash, and `block-sensitive-read.sh` on Read |
| mod-public-repo-guard | The leak scan in `/ship`, the pre-commit and commit-message hooks, and the branch protection on `develop` and `production` |
| mod-unescaped-output | The production standards rule and the CI gates |

## Known limits

- Context weather: cache warmth is an estimate from the cache window setting and the time since the last turn, not a reading from the server.
- `/precompact`: it compacts on a short timer after it replies, because the engine refuses a compaction started inside the command. If no after count follows, run `/compact`.
- Replay theater: it does not record notebook edits.
- mod-help: it marks a mod loaded only when that mod registers a slash command. A mod with no command shows "not seen" even when it is running.
- Guards that ask: they ask through the engine's question dialog. Dismissing the dialog counts as Cancel, and a run with no one to ask also cancels.
- Public repository guard: it fails closed. A missing or failing leak scanner holds the commit or push.
- `/capture`: it writes screenshots and results to `logs/capture/`, which is gitignored, so a capture never adds files git would track and never reaches GitHub.
- Citation drift: it currently reports `omim.org` present in the Python citation pattern but absent from the frontend list. That is an open product question about which hosts may be cited, not a bug in the mod.
- Test triple: it matches test names, so it cannot tell whether a test named "invalid" sends invalid input.
- Tool budgets: it checks that two numbers agree, not that the code enforces the timeout at run time.
- Stack status: ports come from the repository defaults, so a changed port needs an edit in the mod's `config.ts`.
- Design tokens and unescaped output: both scan edited text with patterns, so an unusual construction can pass unseen.
- Requirement trace: a bare number followed by a unit word, such as "3.5 seconds", is read as a measurement and not a phase.

## Maintenance

The six shared mods are maintained in a separate source and copied into this repository. Edit them through that source, not here, or the next copy overwrites the change. The `hooks/config.ts` file in each shared mod holds this repository's own settings and is never overwritten by the copy. The eight mods listed under This repository only are built and edited here.

Each mod must pass `claude plugin validate` and `claude plugin test` before it is committed.
