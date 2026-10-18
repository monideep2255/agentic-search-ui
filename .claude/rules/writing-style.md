---
scope: portable
---

## Writing style

The core, for all documentation and external-facing content. Full text, with the capitalization list, the prose-wall permissions, the file naming tables and the same-day session rule: `.claude/rules-reference/writing-style.md`. Read it before naming a new file or restructuring a document.

- No em dashes, en dashes, or mid-sentence hyphens as punctuation. Use commas, colons, relative clauses, transition words or separate sentences. Spaced hyphens ( - ) only in tables and bullet labels.
- Sentence case in headings and document titles. Capitalize the first word, proper nouns, months and days, proper adjectives, acronyms, and named tools as written.
- No bold text. Use "Label: description".
- After a colon, capitalize a complete sentence and lowercase a fragment.
- No horizontal rules between sections unless needed. No literal `\n` or `<br/>` in Mermaid diagrams, and node labels under 30 characters.
- A table of contents on every document with three or more `##` sections or more than about 100 lines: after the intro, a plain bullet list linking `##` headings only, titled "Table of contents". An append-only single-table file uses an "Index by date" or "Index by theme" list instead. Add the entry in the same edit that adds the section.
- A substantial document explains from first principles and uses Mermaid where it helps the reader.
- No prose walls. Three or more distinct facts in a paragraph become bullets or a table. A status summary is a table, and a changelog is a dated list, newest first. A formatting pass never adds, removes or rewords a fact. Ask before restructuring a locked document.
- Keep the structure current: when a phase, count, status or date changes, update every place the document states it.
- File names: sentence case with underscores between words. Same-day sessions go in one dated file.
- Never mention a specific LLM vendor or product. Use "LLM", "LLM via CLI tooling" or "LLM-assisted".

The test: does any paragraph in my document cram three or more distinct facts a reader would scan or compare, and does the document carry an em dash, bold text, a title-case heading, a vendor name, or a stale table of contents?
