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

### Branding and attribution
- Never mention specific LLM vendors or products (e.g. no brand names, no CLI tool names)
- Use generic terms: "LLM", "LLM via CLI tooling", "LLM-assisted"
- When AI disclosure is needed, use the step-by-step workflow table format (see git-history-analysis.md for an example)

