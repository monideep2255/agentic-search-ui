# First impressions of the UI, 2026-09-12

The product owner's feedback, from memory, before running `testing/Product/Product_workflows.md`. Kept in their words. Not yet discussed or acted on.

1. When the user asks the question, the transition from think to plan to act is ridiculous. The box size suddenly increases, and there is no loading circle moving.
2. The scientist feels off. Naming the agent after a specific scientist is meant to give it some character and a feel-good factor.
   - Clarified the same day: what feels off is that the scientist has no real character in how answers are written.
   - Question asked: can the persona also show in how the agent thinks, plans and acts, or is that not possible?
   - Idea: replace the loading icon with the scientist's name doing the step, for example "[scientist] is understanding…", "[scientist] is searching…", "[scientist] is synthesizing…".
   - DECIDED by the product owner, 2026-09-12: build this. It is not held for a separate design decision. It matches technical specification Section 12.7, which already describes a caption like "Mendel is checking ClinVar for pathogenic variants". Section 14.2 also says a user keeps the same scientist, while develop showed a different one on every page load.
3. The formatting of the answer is horrible and the synthesis is abysmal. The answer that comes out should be beautifully formatted and easy to parse.
4. It is super hard to understand the difference between the three types of searches: clinical, researcher and deep technical. Maybe a small info button that guides the user.
5. It only searches the knowledge graph, not Layers 2 and 3. Every layer of search must be done.

Overall: "IT was horrible." "So far it is so clunky and feels horrible."

## What happens next, as instructed

1. The assistant finishes browser testing and updates what the product owner should test.
2. The product owner tests.
3. Only after that does work on improving the UI experience start.
