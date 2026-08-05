# Build documentation

How a build phase actually runs: the loop, the roles, the model tiering, and what the build has taught us so far. This folder answers "how do we build", not "what are we building". For what the system does, start at `docs/data-engineering/Project_overview_A_to_Z.md`; for the build order itself, read `requirements/Technical_specification.md` Section 25.

## Table of contents

- [The files, grouped by what you need](#the-files-grouped-by-what-you-need)
- [A folder you may see locally that is not in git](#a-folder-you-may-see-locally-that-is-not-in-git)
- [Why these files are not in subfolders](#why-these-files-are-not-in-subfolders)

## The files, grouped by what you need

### The cadence: how one phase runs

| File | What it is | Read when |
|------|-----------|-----------|
| `Build_workflow_cadence.md` | The twelve stages, who acts at each, the model tier and effort per stage, and where every file gets written. Also the provider mapping table, the single place a provider name appears | Before opening any build phase, and any time the model tiering is in question |
| `Phase_6_execution_flow.html` | The same cadence as a visual page, openable in a browser. Also published as an artifact | When explaining the loop to someone, or checking the flow at a glance |

These two are one thing in two forms. If they ever disagree, the markdown is the source and the page is regenerated from it.

Stage 5, the premise gate, is mandatory and blocking for any phase whose deliverable is model-generated. That is the stage this repo added after build phase 2.1, and it is the one most likely to feel skippable and least safe to skip.

### Running the harness

| File | What it is | Read when |
|------|-----------|-----------|
| `Agent_teams_tmux_quickstart.md` | Launch guide so parallel builders appear in live tmux panes | Before running `/bossman-mode` with 2 or more builder tasks |

### What the build has taught us

| File | What it is | Read when |
|------|-----------|-----------|
| `Build_velocity_post_mortem.md` | Where the time actually went across the completed phases, and what changed as a result | When planning a phase estimate, or when a phase is running long and you want to know whether that is normal |

For failures and their fixes rather than velocity, read `LEARNINGS.md` at the repo root, in particular the build phase 2.1 retrospective. For choices between alternatives, read `DECISIONS.md`.

## A folder you may see locally that is not in git

`multi-model-harness/` holds everything for running the build on an alternate, metered model backend when the primary provider's weekly budget is exhausted. It is gitignored on purpose: it names specific providers, model identifiers and prices, which `writing-style` keeps out of tracked documentation and which would go stale within weeks. Its sibling is `docs/Claude_Code_model_fallback_setup.md`, ignored for the same reason.

What is in it:

| File | What it is |
|------|-----------|
| `Multi_model_harness_plan.md` | The plan, the activation runbook, the model choices and why, the overnight requirements |
| `Mixed_model_cadence.html` | The visual version: the twelve stages across two engines, and where a phase parks |
| `Verification_record.md` | Evidence the setup works, and the three defects testing found |
| `setup/claude-build`, `setup/claude-review` | Copies of the launch wrappers that live on PATH |
| `setup/build-models.env` | Copy of the model set with prices and read date |
| `setup/probe_candidates.sh` | Re-runnable tool-use probe for any candidate model |
| `setup/probe_tools.sh` | The same probe pinned to the currently configured three |
| `setup/insert_build_key.py` | Adds the key variable to `.env` without reading the file's secrets |

None of those files contains a credential. The key lives in `.env` and is read at launch.

What is tracked, because it governs the cadence rather than the configuration, is the alternate-backend column in `Build_workflow_cadence.md`'s provider mapping table, plus the rule beside it: the fallback is scoped by role, and the Depth-tier stages do not fail over.

If you do not see that folder, nothing is wrong. It only exists on a machine where the fallback has been set up.

## Why these files are not in subfolders

Considered and rejected on 2026-08-04. Four documents do not need a directory tree, and the two obvious grouping candidates are the two most heavily referenced files in the folder: `Build_workflow_cadence.md` is referenced from 14 places including two premise-gate test files, and `Phase_6_execution_flow.html` from 6 including a publish script. Moving them would mean roughly 25 reference edits, with test breakage as the failure mode, to save a reader one glance at a five-line listing.

The grouping lives in this README's headings instead, which delivers the navigability at no risk. Revisit if this folder passes roughly ten files.

Last updated: 2026-08-04
