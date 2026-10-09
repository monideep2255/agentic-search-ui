# Card 51 diagnosis: the page claims the facts checker does not yet check

Diagnosis only, 2026-10-08 overnight, read against `develop` at `c916cfa3`. Paths are relative to `<repo-root>`. No code was changed and no model was called.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [The unchecked claims, page by page](#the-unchecked-claims-page-by-page)
- [The smallest fix](#the-smallest-fix)
- [Overlap with phase 8.7 and the guardrail](#overlap-with-phase-87-and-the-guardrail)
- [Needs the owner](#needs-the-owner)
- [Proposed test query](#proposed-test-query)

## Status today

Still happens, and one unchecked claim is false today.

The checker is `.claude/skills/verify/scripts/check_facts.py` with its registry `facts_registry.py`. On develop: `facts: 80 | stale 0 | not fully checked 0 | places: PASS 225, FAIL 0, GAP 0, ERROR 0 | PASS`. #156 (2026-10-05) only repaired two patterns.

Coverage, from the checker's own `--map` (every screen line a fact reads) set against the prose blocks of each page file. The prose-block count is a rough line scan, so read it as an order of size:

| Page file | Screen lines a fact reads | Prose blocks | Blocks with no checked line |
|---|---|---|---|
| `frontend/src/components/screens/ArchitectureScreen.tsx` | 18 | 18 | 8 |
| `frontend/src/components/screens/InfoScreens.tsx` (About and Integrations) | 42 | 35 | 27 |
| `frontend/src/components/screens/HomeScreen.tsx` | 2 | 6 | 6 |

Several uncounted blocks are code comments the scan mistook for prose. The real product claims with no fact are listed below.

The false one: the About page's "Cite or refuse" section (`InfoScreens.tsx:1559` to `1562`) says "The track beside each answer shows one segment per claim, coloured by its layer, so an uncited claim is visible before you read a word." The answer screen retired that track on 2026-09-14: `AnswerScreen.tsx:182` ("No provenance spine beside each sentence") and `:1260` ("what the retired spine segment carried"). An uncited claim is now shown in muted ink with no marker.

## What a person sees

A reader opens About to learn how to trust an answer, reads that a coloured track beside each answer shows every claim's source, then looks for it on the answer and finds nothing. The page they were told to trust is wrong about the trust feature itself.

## The cause

The registry only checks sentences someone named. Its facts were written for counts, tool names, budgets and layer triggers. Whole prose sentences about how answers are checked, written and shown have no fact, so `/verify` passes whatever they say (the card 53 verifier's F-53-V05; see `card85_diagnosis.md` in this folder for the three edits that still pass).

## The unchecked claims, page by page

| Page | Line | Claim, shortened | True today? |
|---|---|---|---|
| About | `InfoScreens.tsx:1559` | "The track beside each answer shows one segment per claim, coloured by its layer" | No: the track was retired 2026-09-14 |
| About | `InfoScreens.tsx:1484` | "Code checks each sentence ... One that passes but was reworded is then judged by a model" | Incomplete since #204: a copied cut is also judged by the model, and a sentence with any held piece is dropped whole |
| About | `InfoScreens.tsx:1391` | "A call that reaches its limit stops there and says which limit it hit" | Not checked; true by reading |
| About | `InfoScreens.tsx:1350` | "A tier's model is read from configuration once at the start of your question and held there" | Not checked |
| About | `InfoScreens.tsx:1469` | "Every tool returns typed data checked against its own schema ... the cut is recorded" | Not checked |
| About | `InfoScreens.tsx:1475` | "handed to the Synth tier as material to read, labelled as data rather than as instructions" | Not checked |
| About | `InfoScreens.tsx:1493` | The stream's events: "each step ..., each tool call, the answer text ..., each citation, a trust signal, then done" | Not checked |
| About | `InfoScreens.tsx:1502` | "Every sentence carries a numbered chip ... a trust line ... a follow-up field ... kept in your history" | Not checked |
| About | `InfoScreens.tsx:1513`, `1518` | What it will not do; the scientist's name never changes tools, records or the trust line | Not checked |
| About | `InfoScreens.tsx:1599` | "Layers 2 and 3 are stored nowhere" | Not checked; a saved answer does keep what it cited, so the wording needs a look |
| Architecture | `ArchitectureScreen.tsx:513` | "Each carries its own time limit in code rather than one the model chooses" | Not checked (edit passes, card 85) |
| Architecture | `ArchitectureScreen.tsx:517` to `522` | The citation stop: every fact arrives with a link; "a claim with no such link is not cited ... refused rather than written" | Not checked (reversal passes, card 85) |
| Architecture | `ArchitectureScreen.tsx:274`, `320`, `395`, `410` | Every row keeps its source link; the graph is a snapshot; why counts differ from NCBI's; the shape of a graph query | Not checked |
| Integrations | `InfoScreens.tsx:259`, `261`, `835` | What `s3 mcp` and `s3-kgx-export` do; "what the system will refuse to do" | Not checked |
| Home | `HomeScreen.tsx:269` | "Answered from the NCBI knowledge graph and live NCBI APIs. Every claim carries its source." | Not checked; ClinicalTrials.gov, one of the live sources, is not an NCBI API |

## The smallest fix

Two parts, which ship on different dials.

| Field | Part 1: correct the false sentence | Part 2: give the claims facts |
|---|---|---|
| Change | Rewrite the About "Cite or refuse" sentence to what the answer shows: each claim's marker carries its layer colour, and an uncited claim shows in muted ink with no marker. Reword stop 5 to say copied cuts are judged too. | A fact per claim above in `facts_registry.py`, each read from the code that makes it true and each with a break-it edit. The retired track gets a fact that reads `AnswerScreen.tsx`, so the page cannot claim a component the answer no longer renders. |
| Files and functions | `frontend/src/components/screens/InfoScreens.tsx`, `AboutScreen` | `.claude/skills/verify/scripts/facts_registry.py` |
| Answer path | No | No |
| Dial position | 1, copy | 3, `.claude/` |
| Size | S | M: about 15 facts |
| Migration, package, event schema | None | None |

## Overlap with phase 8.7 and the guardrail

| Fence | Phase 8.7 | Guardrail |
|---|---|---|
| `InfoScreens.tsx`, `ArchitectureScreen.tsx`, `HomeScreen.tsx` | None | None |
| `.claude/skills/verify/scripts/` | None | None |
| A fact reading `AnswerScreen.tsx` (part 2) | It reads the file only; 8.7 rewrites it, so write that fact after 8.7 merges | None |

Part 1 can be built tonight.

## Needs the owner

Part 1, no: a copy fix to a false sentence. Part 2, yes: it changes `.claude/`, so it needs the owner's itemized approval before it is built.

## Proposed test query

Existing query 102 ("The pages say what the system actually does", card 53). Proposed line to add under it:

```markdown
- About, "Cite or refuse": every sentence there describes something you can see on an answer. It does not mention a coloured track beside the answer, which the answer screen no longer has.
```
