---
name: doc-readability
description: "Make one named markdown document easy to read in this repository's house style, in two modes: optimize restructures an existing document, author writes a new one born compliant. TRIGGER on \"make this doc readable\", \"restructure this document\", \"fix the prose walls in X\", \"add a ToC and diagrams to X\", \"write a new doc in house style\", \"doc-readability\". Distinct from skill-adapt-verify, which checks a file copied from another repository and only ever touches .claude/: this runs on any markdown document in the repository. Distinct from tracker/check_doc_drift.py and /precommit, which check whether a stated fact has gone stale against source: this checks whether a fact survived a rewrite, and never judges whether it was true. Distinct from /phase-checkpoint, which is a shallow hygiene pass across every artifact one checkpoint touched: this is a deep single-document rewrite asked for by name. Runs on exactly one document per invocation and refuses the two locked requirements documents."
scope: project
argument-hint: "[--optimize <path>] [--author <path>]"
depends_on:
  - .claude/rules/writing-style.md
  - .claude/agents/first-principles.md
  - .claude/agents/doc-auditor.md
  - tracker/check_doc_drift.py
  - tracker/doc_readability_runs.md
depended_by:
  - CLAUDE.md
  - AGENTS.md
---

# /doc-readability - make one document easy to read, in house style

Purpose: take one named markdown document, either an existing one that needs restructuring or a new one that needs to be written, and produce a version that is easy to read in this repository's house style: no prose walls, a current table of contents, diagrams where a relationship or flow needs one, and first-principles explanation where a concept is used but never explained. Every restructure is proven to have lost no fact, by a bundled script and a fresh-context auditor agent, both of which must pass before the run is done.

## Why this exists

Punctuation linting is not the value here. Across 171 markdown files and 48,906 lines in this repository there are zero em dashes and bold text in only 5 files, so the mechanical writing-style checks are already close to universally followed. The defect this skill exists to fix is prose walls: `requirements/Plan.md` has 64 paragraph lines over 600 characters, the longest 1,580; `requirements/phase_6/Continuation_prompt.md` has 22 such lines in 621, the longest 1,441; `CLAUDE.md` line 16 is a single table cell of roughly 12,000 characters. Nothing enforced the house style before this skill existed: `tracker/check_doc_drift.py` checks facts against source, not style, by its own docstring, and `skill-adapt-verify`'s `verify_adaptation.py` checks style but only inside `.claude/`. No script and no skill closed that gap for the rest of the repository until now.

## Table of contents

- [Why this exists](#why-this-exists)
- [Two modes](#two-modes)
- [When to run](#when-to-run)
- [When not to run](#when-not-to-run)
- [Refusals](#refusals)
- [Inputs the skill needs](#inputs-the-skill-needs)
- [Steps, optimize mode](#steps-optimize-mode)
- [Steps, author mode](#steps-author-mode)
- [What the two scripts cover, and what they do not](#what-the-two-scripts-cover-and-what-they-do-not)
- [The additions manifest](#the-additions-manifest)
- [Three-state permissions](#three-state-permissions)
- [Constraints](#constraints)
- [Exit checklist](#exit-checklist)
- [Output](#output)

## Two modes

| | Optimize mode | Author mode |
|---|---|---|
| Input | `--optimize <path>`, one existing markdown file | `--author <path>`, a target filename that does not yet exist, plus named source material |
| Before version | `git show HEAD:<path>`, captured before any edit | Not applicable, there is no prior version |
| Preservation gate | `check_preservation.py --before <captured> --after <path>`, must exit 0 | Not applicable, and the skill says so out loud rather than skipping silently: a document with no before version has nothing to prove no loss against |
| Style gate | `check_style.py <path>`, must exit 0, run once before editing to confirm there is a real defect and again after | `check_style.py <path>`, must exit 0, run once after drafting since the document is written structured from the start |
| Auditor | `doc-auditor` sub-agent, fresh context, dispatched after both gates pass | `doc-auditor` sub-agent, fresh context, dispatched after the style gate passes, told it is grading an authored document with no before version |
| Additions manifest | `check_preservation.py --additions`, every row classified | Not applicable, the preservation gate that produces it does not run. The whole document is new by definition, so a manifest of "added" units carries no information |
| May invent facts | Never. Structure only changes; no new claim, number, date, or fact enters the document | Never. Every claim traces to the named source material; the skill refuses to draft from model memory alone |

## When to run

- A reviewer or the product owner names a specific document as hard to read, or asks for it to be restructured.
- A new document is needed and should be written compliant with the house style from the first draft rather than fixed up afterward.
- `check_style.py --dir` (report-only) surfaces a document as a priority candidate and the owner picks it for a real run.

## When not to run

- Meeting notes, session notes, or continuation prompts. `writing-style.md`'s own "When NOT to apply" list exempts capture documents from the no-prose-walls rule, and this skill follows that exemption rather than overriding it.
- More than one document at a time. There is no batch mode, by design, see Refusals below.
- The two locked requirements documents, `requirements/PRD.md` and `requirements/Technical_specification.md`.

## Refusals

Three hard stops. Each is a stop, not a workaround, and the first is enforced by more than this document.

- Locked documents: `requirements/PRD.md` and `requirements/Technical_specification.md` are frozen until the Step 6.2 reconciliation. Both `check_preservation.py` and `check_style.py` refuse these paths themselves, exit code 3, so the guarantee is structural rather than an instruction the model could be talked out of. This is `system-design-patterns.md` pattern 8: the strongest constraint is removing the ability, not asking the model not to use it.
- Batch requests: "clean up all the docs" is refused. Offer `check_style.py --dir` instead, which sweeps a directory in report-only mode and never edits, producing a prioritized list the owner picks from. A read is not a rewrite, and this skill only ever performs the latter on a single named target.
- Capture documents: meeting notes, session notes, and continuation prompts are exempt from the no-prose-walls rule by `writing-style.md`'s own exemption list. Ask before proceeding if the named target is one of these, since the exemption is a default, not an absolute bar the owner cannot waive for a specific file.

## Inputs the skill needs

Confirm before writing. Ask if unclear from context.

- Which mode: `--optimize <path>` or `--author <path>`.
- Optimize mode: the exact path, and confirmation that it is not one of the two locked documents.
- Author mode: the target filename, chosen per `writing-style.md`'s file-naming table, the intended audience, and the named source material the draft will be built from. Author mode refuses to proceed with no source named.

## Steps, optimize mode

### Step 1: resolve and lock the target

Exactly one path. Reject a glob, a directory, or a locked document. Run `git status --short <path>` and stop to ask if the file is dirty: an ambiguous baseline is a gate that proves nothing, since the preservation gate needs to know exactly what "before" means.

### Step 2: capture the before baseline

Capture `git show HEAD:<path>` into the session scratch directory, outside the repository, so the untouched committed version survives every later edit to the working file.

### Step 3: watch the style gate fail

Run `check_style.py <path>` on the untouched file and record the defect inventory. Exit 0 means there is nothing to optimize, so stop. State why rather than silently proceeding: a gate whose first observed state is green tells you nothing, the same discipline this repository's premise gates already apply, per `goal-contracts.md`'s "a verify surface must state its own coverage".

### Step 4: write the goal contract

Write the five elements from `goal-contracts.md`: done when, verify, output, constraints, blocked-stop, specific to this document and this run.

### Step 5: build the fact ledger

Read the whole document and list every number, date, path, identifier, and standalone claim, section by section. This is deliberately a separate pass from Step 6: the model that restructures while it reads is the model that drops a clause mid-edit. Building the ledger first gives Step 6 something to check itself against.

### Step 6: restructure, structure only

No new prose. No rewording. Cut only at clause boundaries the sentence already has. A status summary becomes a table. A changelog becomes a dated bullet list, newest first. A multi-item description becomes bullets. This is the edit the preservation gate exists to prove did not lose anything.

### Step 7: first preservation gate

Run `check_preservation.py --before <captured> --after <path>`. Resolve every finding by restoring the missing atom verbatim, in the document, never by loosening `--lex-threshold` or `--claim-coverage`. A loosened threshold is refused by the script itself, exit code 2, so this is enforced twice.

### Step 8: add the structure the document needs

Add a table of contents where the document's section count crosses `writing-style.md`'s 3-plus-`##`-sections or roughly-100-line threshold. Add Mermaid only where a relationship, flow, or architecture genuinely exists in the content. A decorative diagram is a defect, not a bonus: if a section is a list of independent items, it stays a table, not a graph.

### Step 9: add first-principles explanation

Add explanation only where a concept is used in the document but never explained, in the four-part shape from `.claude/agents/first-principles.md`. Never re-explain something the document already explains; a repeated explanation is exactly the kind of unclassifiable addition Step 11's manifest is built to catch.

### Step 10: second preservation gate plus the style gate

Re-run both `check_preservation.py` and `check_style.py` here, rather than carrying forward the Step 7 result, because Steps 8 and 9 changed the file after that gate ran. Both must exit 0.

### Step 11: build the additions manifest

Run `check_preservation.py --additions`. Classify every row into exactly one of five buckets: first-principles explanation, Mermaid diagram, table of contents entry, structural scaffolding, unclassified. An unclassified row is a blocker: it means prose appeared that the skill cannot account for, which is the shape of an accidental invention, and the run does not proceed past it uninvestigated.

### Step 12: dispatch the auditor

Dispatch the `doc-auditor` sub-agent (`.claude/agents/doc-auditor.md`) and wait for it to complete before proceeding.

It receives: the before and after versions of the document, and the additions manifest with classifications.

It must not receive: the script output or exit codes, the goal contract from Step 4, the fact ledger from Step 5, conversation history from this run, or a prior verdict. This is the fresh-context requirement `self-eval-loop.md` names: a grading agent that inherits the author's context inherits the author's blind spots.

On FAIL, fix the specific issue and dispatch a new auditor with fresh context. Never show one auditor its own prior verdict, per the same rule. Cap at two rounds; on a second FAIL, stop and ask the owner rather than running a third round, per `self-eval-loop.md`'s "Ask" state.

### Step 13: close the run

Append the run row to `tracker/doc_readability_runs.md`. Run `python tracker/check_doc_drift.py --check` and confirm it exits 0. Present the diff summary and the additions manifest. Do not commit; hand off to `/ship`.

## Steps, author mode

### Step A1: resolve the filename

Choose the target filename per `writing-style.md`'s file naming table (meeting notes, explanations, decisions, questions, discussion notes each have their own pattern). Confirm it does not already exist; author mode is for a document that does not yet exist.

### Step A2: collect source material and audience

Ask for the named source material and the intended audience if not already given. Refuse to proceed with no source named: a document generated from model memory alone is not what this skill produces, and there is nothing for the auditor or a reader to trace a claim back to.

### Step A3: outline before drafting

Outline the `##` sections first, from the source material and the audience's needs, then generate the table of contents from that outline. The outline exists so the document is structured from the first decision, not drafted as prose and broken up afterward.

### Step A4: draft each section directly in structured form

Write each section directly as the structure calls for: a table where the content is comparable rows, a bulleted list where it enumerates items, prose only where the content is a genuine flowing argument. Never draft a paragraph intended to be broken up later; that is optimize mode's job, and doing it here would just reintroduce the prose-wall defect one step removed.

### Step A5: diagram a flow if the source material has one

Add a diagram only where the source material actually describes a relationship, flow, or architecture. Same rule as Step 8: a decorative diagram over a list of independent items is a defect.

### Step A6: add first-principles explanation for the named audience

Add explanation, in the four-part shape from `.claude/agents/first-principles.md`, for any concept the named audience will not already know. Skip concepts the audience is expected to know; over-explaining is its own readability defect.

### Step A7: run the style gate, and say the preservation gate does not apply

Run `check_style.py <path>` and confirm it exits 0. Then state out loud, in the run output, that the preservation gate does not apply and why: there is no before version for a newly authored document, so there is nothing to prove no loss against. Stating this is required, never an implicit skip: `anti-rationalization.md` names silently skipping a step that "does not seem to apply" as exactly the shortcut this rule exists to block.

### Step A8: dispatch the auditor and close the run

Dispatch the `doc-auditor` sub-agent, told explicitly that it is grading an authored document with no before version, so it checks internal coherence and source-traceability of claims rather than before-after preservation. Same fresh-context rule as Step 12: no script output, no outline, no source-collection notes, no prior verdict. On FAIL, fix and redispatch fresh, capped at two rounds then ask the owner. Append the run row to `tracker/doc_readability_runs.md`, run `python tracker/check_doc_drift.py --check`, confirm exit 0, and report. Do not commit; hand off to `/ship`.

## What the two scripts cover, and what they do not

`check_preservation.py`, by its own docstring, proves a fact survived a rewrite. It does not check: truth (a wrong number preserved perfectly still passes), scope inversion or attribution swap ("A depends on B" rewritten as "B depends on A" keeps every atom and passes, asserted as a known miss in its own `--mutation-test`), ordering semantics (a reordered list keeps every atom), whether added prose is accurate, style, or whether a Mermaid block actually parses, since no renderer is bundled. It also only ever runs on the one document named on the command line; there is no sweep mode.

`check_style.py` covers house-style structure: prose-wall length, heading case, missing table of contents entries, and (as an advisory, non-blocking category) missing-Mermaid suggestions. It does not judge correctness, source-traceability, or whether an addition belongs.

The gap between what both scripts cover and what a document actually needs to be trustworthy, truth, correct attribution, source-traceability of a new claim, whether a Mermaid diagram is the right call rather than merely present, is exactly what the `doc-auditor` sub-agent closes in Steps 12 and A8. Neither script alone, nor the two together, is sufficient without it.

## The additions manifest

Every row in `check_preservation.py --additions` output is an after-unit whose content is mostly absent from the before document, computed in the opposite direction from a finding and never able to change the gate's exit code. The restructure (Steps 6 and 7) and the additions (Steps 8 through 11) are disjoint sets by construction: an addition is defined as an after-unit with no before-anchor, so nothing that merely moved during the restructure can appear in this table. That is what lets the owner accept the restructure on the script's proof alone while reading only the additions table to judge everything new.

| After line | Kind | Classification | First 120 characters |
|---|---|---|---|
| line number | heading / bullet / table / fence / prose | one of the five buckets from Step 11 | excerpt |

## Three-state permissions

Allow:
- Run `check_style.py` and `check_preservation.py` in read-only report modes, including `--dir`, without asking.
- Restructure a single named, non-locked document once the owner has confirmed the target, without asking at each step.
- Add a table of contents, Mermaid diagrams, and first-principles explanation per Steps 8, 9, A5, and A6, without asking, as long as every addition is classified in the manifest.

Ask:
- Before proceeding against a capture document (meeting note, session note, continuation prompt) that the writing-style exemption covers.
- Before a third auditor round, per `self-eval-loop.md`.
- Before treating a `check_style.py --dir` finding as authorization to restructure; the sweep is report-only, the owner still picks the target.

Deny:
- Never touch `requirements/PRD.md` or `requirements/Technical_specification.md`.
- Never reword, merge, or drop a fact under cover of a formatting pass.
- Never loosen `--lex-threshold`, `--claim-coverage`, or `check_style.py`'s wall-length threshold, or pass a relaxed value to make a gate pass; both scripts refuse a loosened threshold themselves.
- Never accept a restructure on the script alone or the auditor alone; both must pass.
- Never run across more than one document per invocation.

## Constraints

- Optimize mode never introduces a new claim, number, date, path, or fact; only structure changes.
- Author mode never drafts from model memory alone; every claim traces to named source material.
- Follow `writing-style.md` in full: no em dashes, sentence case headings, no bold, "Label: detail" bullets, no prose walls, current table of contents.
- Do not commit or push. Hand off to `/ship`.
- If a required input is missing (mode, path, source material, audience), ask before writing.

## Exit checklist

Before declaring the run done, verify:

- [ ] Optimize mode: the style gate was observed FAILING on the untouched file before any edit (Step 3), not merely assumed to fail.
- [ ] Optimize mode: `check_preservation.py --before <captured> --after <path>` exits 0, re-run after Steps 8 and 9, not only carried forward from Step 7.
- [ ] `check_style.py <path>` exits 0 on the final version, in both modes.
- [ ] No threshold was loosened: neither a relaxed flag value nor a below-default number appears in any command actually run this session.
- [ ] Every row in the additions manifest carries one of the five classifications; zero unclassified rows.
- [ ] Optimize mode: zero new claims, numbers, dates, paths, or facts entered the document; only structure changed.
- [ ] Author mode: every claim in the draft traces to the named source material, and the run states out loud that the preservation gate does not apply and why, rather than skipping it silently.
- [ ] The `doc-auditor` sub-agent graded from fresh context: it received the document versions and the additions manifest, and did not receive script output, exit codes, the goal contract, the fact ledger, conversation history, or a prior verdict.
- [ ] The auditor round reached PASS within two rounds, or the run stopped and asked the owner rather than running a third round.
- [ ] `tracker/doc_readability_runs.md` has a new row for this run.
- [ ] `python tracker/check_doc_drift.py --check` exits 0.

## Output

Report: which mode ran, the target path, the before-and-after style gate results, the preservation gate result (optimize mode) or the stated non-applicability (author mode), the additions manifest, the auditor's final verdict and how many rounds it took, and the new `tracker/doc_readability_runs.md` row. Suggest running `/ship` next to commit and push.
