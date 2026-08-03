---
scope: portable
---

## Writing style

Rules for all documentation and external-facing content in this repo.

### Formatting
- No em dashes, en dashes, or mid-sentence hyphens as punctuation. These are a strong AI-written signal. Instead, use transition words (additionally, next, also, specifically, in particular), commas, relative clauses ("which", "where", "who"), or restructure into separate sentences. Use colons for lists. Hyphens with spaces ( - ) are acceptable only in tables and bullet labels (e.g. "Label - description")
- **Sentence case in headings and document titles** - not title case. Capitalize only:
  - The first word of the heading
  - Proper nouns (people: Monideep; organizations: NCBI, NIH, Hetzner)
  - Names of months (January, March) and days of the week (Monday, Thursday)
  - Proper adjectives derived from proper nouns (British, Chinese, American, Dutch)
  - Acronyms and initialisms (AI, ML, NLP, RAG, LLM, SVMs, APIs)
  - Named technologies and tools (PostgreSQL, AGE, KGX, BioLink, LinkML, Cypher)
  - Mixed-case technical terms exactly as written (MLOps, kNN, t-SNE, aman.ai)
  - Examples: "Why does it exist?", "Key trade-offs", "How the agent loop works", "Build phase 2.1 retrospective"
- No bold text. Use "word:" format instead (e.g. "What worked:" not "**What worked:**"). Bold looks LLM-generated
- When listing labeled items, use "Label: description" not "**Label.** Description"
- After a colon, capitalize the first word if what follows is a complete sentence. Lowercase if it is a fragment or continuation.
- No line breaks/horizontal rules between sections unless specifically needed
- No literal `\n` or `<br/>` in Mermaid diagrams. Keep node labels short (under 30 chars) or split into separate nodes
- Table of contents on every doc with 3+ major (##) sections or more than ~100 lines. Place after the title and one-paragraph intro, before the first content section. Use a plain markdown bullet list linking to `##` headings only (subsection anchors break when headings get reworded). Heading label: "Table of contents" (sentence case). For append-only files like DECISIONS.md where the body is a single table, use an "Index by date" or "Index by theme" bullet list instead of a ToC to anchors.
- For docs that qualify for a ToC: use the first-principles agent (`.claude/agents/first-principles.md`) to explain concepts, and include Mermaid diagrams where they help the reader understand relationships, flows, or architecture. The goal is that every substantial doc is both navigable (ToC) and visually clear (diagrams).
- No walls of text. When a passage enumerates three or more distinct items (decisions, steps, sources, options, dispositions), render it as a bulleted list or a table, not as one run-on sentence chained by semicolons or commas. A status summary is a table; a changelog is a dated bullet list, newest first; a multi-item description is bullets. The test: if you cannot scan the structure at a glance, restructure it. The specific failure this prevents is a "Last updated" or "what changed" block that crams every update into a single paragraph. The full treatment, with the "Label: detail" form, the smell test, and the locked-doc exception, is in the "No prose walls" section below.
- Keep the structure current as the document grows. When you add a `##` section, add its table-of-contents entry in the same edit, so the ToC never lags the body. When a phase, count, status, or date changes, update every place the document states it. A ToC that omits later sections, a status line that calls a finished phase "next", a filename or title that names fewer steps than the file now covers, or a stale count is a defect, not a cosmetic nit.

### No prose walls

A prose wall is one dense paragraph that crams three or more distinct facts, steps, or items into running text. It is hard to scan, hard to update, and easy to lose a fact inside. This is the expanded treatment of the "no walls of text" line above. Whenever a block carries more than one thing a reader will scan for or compare, break it into structure.

The rule:

- Three or more distinct facts, items, or steps in a paragraph: convert to a bullet list, one item per line.
- Items with a name and a detail: use the "Label: detail" bullet form (for example "Layer 1: the AGE graph, read-only", "TTL: gene one week").
- Several things that each carry their own facts (several tools, layers, or decisions): give each its own sub-heading with bullets under it, not one paragraph per thing.
- One idea per bullet. Do not rebuild the wall inside a bullet by chaining clauses with commas and semicolons.
- A status summary is a table. A changelog or "what changed" block is a dated bullet list, newest first. A multi-item description is bullets.
- Keep a paragraph only when the sentences flow as one argument or narrative. Facts a reader scans, compares, or edits belong in a list.

The smell test: if you are writing ", a X that does A, a Y that does B, and a Z that does C" inside a sentence, that is a list wearing a paragraph. Break it out. The specific failure this most often prevents is a "Last updated" or "what changed" block that crams every update into a single paragraph.

When to apply:

- Any documentation, requirements doc, reference doc, PRD, technical specification, or decision writeup.
- Any passage that enumerates decisions, steps, sources, options, tools, or dispositions.

When NOT to apply:

- Meeting notes and session notes (capture, not argument).
- A genuine single flowing argument or narrative paragraph.
- Content inside code blocks, mermaid diagrams, or existing tables and lists.

Three-state permissions for prose walls:

Allow:
- Restructure a prose wall into a list, a table, or "Label: detail" bullets while preserving meaning exactly, without asking.

Ask:
- Before restructuring a locked document (for example the PRD, frozen until the Step 6.2 reconciliation), because even a meaning-preserving reformat touches a frozen artifact.

Deny:
- Never add, remove, or reword facts under cover of a formatting pass. A wall fix is structure only.
- Never ship a substantial doc whose "Last updated" or multi-item block is a single crammed paragraph.

The test: does any paragraph in my doc cram three or more distinct facts a reader would scan or compare, instead of using a bullet list or a table?

### File naming conventions

Use sentence case, the same rules as headings. Capitalize only the first word, proper nouns, acronyms, and named tools. Use underscores between words.

| Type | Format | Example |
|------|--------|---------|
| Meeting notes (simple) | `Month_Day.md` | `January_06.md` |
| Meeting notes (numbered) | `{number}_Meeting:{topic} {Month} {Day}.md` | `2_Meeting:technical_refinement_January_20.md` |
| Meeting notes (person) | `{number}_Meeting_{Person}_{Month}_{Day}.md` | `2_Meeting_Kimberly_January_22.md` |
| Meeting prep | `Prep_for_{Month}_{Day}.md` | `Prep_for_January_20.md` |
| Explanations | `Concept_explained.md` | `NCBI_project_explained.md` |
| Decisions | `Topic_decision.md` | `Neo4j_vs_ArangoDB_decision.md` |
| Questions | `Questions_for_X.md` | `Questions_for_first_WG_meeting.md` |
| Discussion/insight | `Topic_description_Month_Day.md` | `AI_as_programming_language_discussion_March_20.md` |

### Same-day sessions go in one file

When multiple working sessions or steps happen on the same day, keep them in a single dated file and append each new session as a section. Do not create a separate file per step. Name the file for the day and the span of steps it covers.

| Type | Format | Example |
|------|--------|---------|
| Same-day working session (meetings/) | `YYYY-MM-DD_Phase_N_steps_X-Y.md` | `2026-07-21_Phase_1_steps_1.6-1.7.md` |
| Same-day detailed record (phase_N/) | `Session_Month_Day.md` (one file per day, append each step as a section) | `Session_July_21.md` |

### Branding and attribution
- Never mention specific LLM vendors or products (e.g. no brand names, no CLI tool names)
- Use generic terms: "LLM", "LLM via CLI tooling", "LLM-assisted"
- When AI disclosure is needed, use a step-by-step workflow table format
