## No prose walls

A prose wall is one dense paragraph that crams three or more distinct facts, steps, or items into running text. It is hard to scan, hard to update, and easy to lose a fact inside. This is the expanded treatment of the "no walls of text" line in `writing-style.md`. Whenever a block carries more than one thing a reader will scan for or compare, break it into structure.

### The rule

- Three or more distinct facts, items, or steps in a paragraph: convert to a bullet list, one item per line.
- Items with a name and a detail: use the "Label: detail" bullet form (for example "Layer 1: the AGE graph, read-only", "TTL: gene one week").
- Several things that each carry their own facts (several tools, layers, or decisions): give each its own sub-heading with bullets under it, not one paragraph per thing.
- One idea per bullet. Do not rebuild the wall inside a bullet by chaining clauses with commas and semicolons.
- A status summary is a table. A changelog or "what changed" block is a dated bullet list, newest first. A multi-item description is bullets.
- Keep a paragraph only when the sentences flow as one argument or narrative. Facts a reader scans, compares, or edits belong in a list.

### The smell test

If you are writing ", a X that does A, a Y that does B, and a Z that does C" inside a sentence, that is a list wearing a paragraph. Break it out. The specific failure this most often prevents is a "Last updated" or "what changed" block that crams every update into a single paragraph.

### When to apply

- Any documentation, requirements doc, reference doc, PRD, technical specification, or decision writeup.
- Any passage that enumerates decisions, steps, sources, options, tools, or dispositions.

### When NOT to apply

- Meeting notes and session notes (capture, not argument).
- A genuine single flowing argument or narrative paragraph.
- Content inside code blocks, mermaid diagrams, or existing tables and lists.

### Three-state permissions

Allow:
- Restructure a prose wall into a list, a table, or "Label: detail" bullets while preserving meaning exactly, without asking.

Ask:
- Before restructuring a locked document (for example the PRD, frozen until the Step 6.2 reconciliation), because even a meaning-preserving reformat touches a frozen artifact.

Deny:
- Never add, remove, or reword facts under cover of a formatting pass. A wall fix is structure only.
- Never ship a substantial doc whose "Last updated" or multi-item block is a single crammed paragraph.

The test: does any paragraph in my doc cram three or more distinct facts a reader would scan or compare, instead of using a bullet list or a table?
