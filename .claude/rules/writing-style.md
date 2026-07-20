---
scope: portable
---

## Writing style

Rules for all documentation, Confluence pages, and external-facing content.

### Formatting
- No em dashes, en dashes, or mid-sentence hyphens as punctuation. These are a strong AI-written signal. Instead, use transition words (additionally, next, also, specifically, in particular), commas, relative clauses ("which", "where", "who"), or restructure into separate sentences. Use colons for lists. Hyphens with spaces ( - ) are acceptable only in tables and bullet labels (e.g. "Label - description")
- **Sentence case in headings and document titles** - not title case. Capitalize only:
  - The first word of the heading
  - Proper nouns (people: Dalio, Kahneman, Kimberly; places: China, Suez; organizations: Stanford, NATO)
  - Names of months (January, March) and days of the week (Monday, Thursday)
  - Proper adjectives derived from proper nouns (British, Chinese, American, Dutch)
  - Acronyms and initialisms (AI, ML, NLP, RAG, LLM, SVMs, APIs)
  - Named technologies and tools (PostgreSQL, AGE, KGX, BioLink, LinkML, Cypher)
  - Mixed-case technical terms exactly as written (MLOps, kNN, t-SNE, aman.ai)
  - Examples: "Why does it exist?", "Key trade-offs", "How the economic machine works", "Ray Dalio's power index"
- No bold text. Use "word:" format instead (e.g. "What worked:" not "**What worked:**"). Bold looks LLM-generated
- When listing labeled items, use "Label: description" not "**Label.** Description"
- After a colon, capitalize the first word if what follows is a complete sentence. Lowercase if it is a fragment or continuation.
- No line breaks/horizontal rules between sections unless specifically needed
- No literal `\n` or `<br/>` in Mermaid diagrams. Keep node labels short (under 30 chars) or split into separate nodes
- Table of contents on every doc with 3+ major (##) sections or more than ~100 lines. Place after the title and one-paragraph intro, before the first content section. Use a plain markdown bullet list linking to `##` headings only (subsection anchors break when headings get reworded). Heading label: "Table of contents" (sentence case). For append-only files like DECISIONS.md where the body is a single table, use an "Index by date" or "Index by theme" bullet list instead of a ToC to anchors.
- For docs that qualify for a ToC: use the first-principles agent (`.claude/agents/first-principles.md`) to explain concepts, and include Mermaid diagrams where they help the reader understand relationships, flows, or architecture. The goal is that every substantial doc is both navigable (ToC) and visually clear (diagrams).

### Branding and attribution
- Never mention specific LLM vendors or products (e.g. no brand names, no CLI tool names)
- Use generic terms: "LLM", "LLM via CLI tooling", "LLM-assisted"
- When AI disclosure is needed, use a step-by-step workflow table format

