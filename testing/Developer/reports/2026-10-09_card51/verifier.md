# Card 51 fresh verifier report

Base: HEAD 68e9d7d5 (detached at fix/card51-about-page-truth), diff against origin/develop. Findings are appended as they are established.

## Findings

### V-51-01: the new stop 5 sentence says "any piece held back" drops the sentence whole, which is true only of copied pieces
- Severity: major (a new sentence on this page that is false in a case a reader can meet)
- What: the branch adds to About stop 5 (InfoScreens.tsx:1488 to 1489): "A copied cut is judged the same way, and a sentence with any piece held back is dropped whole." The code drops the whole sentence only when a copied piece is held: `held_for_check` collects "the `segment_kept` positions of copied clauses held back" (src/system_03_search_agent/synthesis/grounding.py:1536 to 1539), and only `if held_for_check:` forces the whole drop (grounding.py:1816). A reworded clause the model check does not approve is stripped on its own and the end strip of T-6.2-15 still shows what came before it. Develop's own test pins that scope: `test_a_sentence_with_no_copied_cut_keeps_developments_end_strip` (tests/system_03_search_agent/synthesis/test_copied_cuts.py:837), whose docstring says "Round 5 changes only sentences holding a copied piece back."
- Reproduction: a probe calling `run_grounding_pass` on this checkout's code with two records, "Drug X was well tolerated." and "Patients given drug X slept longer at night.", and the reply `Drug X was well tolerated [1], and sleep improved with the drug [2: "Patients given drug X slept longer at night"].` First pass: `CASE3 first pass sink ['sleep improved with the drug'] shown ('Drug X was well tolerated [1].',)`. Second pass with the model check approving nothing: `CASE3 second pass, nothing approved, shown ('Drug X was well tolerated [1].',)`. The reworded piece was held back and the sentence was not dropped whole. The same holds for a clause that fails code's own check: `CASE1 sink 0 shown ('Drug X was well tolerated [1].',)`.
- Why it matters: the card's promise is that the About page never describes something the product does not do. A reader told that any held piece drops the whole sentence would read every shown sentence as the writer's complete sentence, and it may not be. Develop's stop 5 said nothing about this, so on this one sentence the branch is less true than develop.
- Smallest fix: one word, "a sentence with any copied piece held back is dropped whole". That keeps the facts checker's sentence untouched.
- NOT FIXED

### V-51-02: the corrected sentence sits next to two that say no claim is ever unsourced
- Severity: minor (the tension is inherited from develop, not new)
- What: the new "Cite or refuse" sentence says "a claim with no source shows in muted ink with no marker after it" (InfoScreens.tsx:1562 to 1563). The sentence right before it says "Every claim is tied to a specific record." Stop 6 says "Every sentence carries a numbered chip pointing at the record behind it" (InfoScreens.tsx:1504) and stop 7 says it "will not ship a sentence with no source behind it" (InfoScreens.tsx:1516).
- Reproduction: `sed -n 1500,1565p frontend/src/components/screens/InfoScreens.tsx` on this checkout. The code does show unsourced text in muted ink: `uncitedInk` applies `designTokens.inkMuted` when `claim.citations.length === 0 && !claim.pendingCitations` (AnswerScreen.tsx:1265 to 1266), which is what framing text kept by grounding without a marker gets.
- Why it matters: a reader can fairly ask which is true, "every claim is tied to a record" or "a claim with no source shows in muted ink". Develop's sentence ("so an uncited claim is visible before you read a word") had the same tension, so this is not worse than develop.
- Smallest fix, if wanted: name what the muted text is, for example "a sentence with no source, such as a line of framing, shows in muted ink with no marker after it". Not needed for merge.
- NOT FIXED

### V-51-03: "each claim's marker carries its layer's colour" has one exception
- Severity: minor (unsure it is worth words on the page)
- What: a marker whose records span more than one layer is drawn in `designTokens.inkMuted`, not a layer colour: `const colour = sharedLayer ? layerColour(sharedLayer).main : designTokens.inkMuted;` (frontend/src/components/answer/CitationMarkers.tsx:271; the header at :47 says "a range spanning several layers reads in `designTokens.inkMuted`").
- Why it matters: muted ink is also the colour the same sentence gives to a claim with no source, though that one has no marker at all, so the two stay distinguishable. True for the common single-layer case.
- NOT FIXED

### V-51-04: "a copied cut" is internal language, and "cut" already means something else one stop earlier
- Severity: minor
- What: the rendered stop 5 says "A copied cut is judged the same way". Nothing on the page says what a copied cut is. Stop 4, one paragraph up, uses "cut" for a different thing: "result is cut to a bounded size and the cut is recorded rather than hidden" (InfoScreens.tsx:1470).
- Reproduction: About rendered in jsdom with a throwaway test (moved out of the checkout after): `A copied cut is judged the same way, and a sentence with any piece held back is dropped whole.` The term comes from the code (`_copied_clause_candidate`, "The check item for a copied cut", grounding.py:1096).
- Why it matters: a reader of About is told how to trust an answer; a term they cannot decode, which on the same page means a truncated tool result, does not tell them anything.
- Smallest fix: say it in the reader's words, for example "A sentence that copies part of a record word for word is judged the same way, and if any copied part is held back the whole sentence is dropped." That also closes V-51-01.
- NOT FIXED

## Answers with evidence

| Question | Answer | Evidence |
|---|---|---|
| Base | HEAD 68e9d7d5, one commit on origin/develop d5dcc02c (merge base equals origin/develop) | `git rev-parse HEAD`, `git merge-base HEAD origin/develop` |
| Track retired, so removing the sentence is right | True | AnswerScreen.tsx:182 "No provenance spine beside each sentence: the citation marker's layer colour carries the layer"; AnswerScreen.tsx:1257 to 1263 "what the retired spine segment carried". Rendered About contains no "track" or "segment": `HAS track: false HAS segment: false`. |
| "Each claim's marker carries its layer's colour" | True for a marker on one layer; a marker spanning several layers is muted (V-51-03) | CitationMarkers.tsx:271 |
| "A claim with no source shows in muted ink with no marker after it" | True | AnswerScreen.tsx:1265 to 1266, `uncitedInk` applies `designTokens.inkMuted` when there are no citations and none pending; `CitationMarkers` renders nothing to mark |
| "A copied cut is judged the same way" | True: copied cuts go to the same model check with the same instruction, and are held when the check cannot run; a cut opening on a bare verdict is held by code without asking, which is stricter, not looser | graph.py:9727 "asking a model about reworded sentences and copied cuts"; grounding.py:1712 to 1735; sentence_check.py:119 `SENTENCE_CHECK_INSTRUCTION`; commits 5c1a9f8b and aa5cea1c are ancestors of origin/develop |
| "A sentence with any piece held back is dropped whole" | Not true as written: only a held copied piece drops the sentence whole (V-51-01) | grounding.py:1536 to 1539 and :1816; my probe output in V-51-01 |
| Any sentence now false or contradicted by another page | One new overstatement (V-51-01); an inherited tension on the same page (V-51-02). No other page, README or the user docs I searched mention the track; the only remaining mentions of the spine are code comments (AnswerScreen.tsx:7 to 12 still describes the spine as "Kept always rendered", a stale comment, not page text) | `grep -rn -i "segment per claim\|track beside\|provenance spine\|coloured track\|before you read a word" frontend/src README.md docs/*.md` |
| Facts checker green | Yes, exit 0: `facts: 80 \| stale 0 \| not fully checked 0 \| places: PASS 225, FAIL 0, GAP 0, ERROR 0 \| PASS`. The protected sentence still passes: `PASS \| loop.sentences_checked_by_code_alone \| About \| says "a model" ... InfoScreens.tsx:1486`. Note that no fact reads either changed sentence, so green here is not evidence that the new sentences are true; a branch that had changed nothing would also pass. | `python3 .claude/skills/verify/scripts/check_facts.py` |
| House style | No em dash, en dash, spaced hyphen or bold in any added line (grep of added lines returned nothing). The copy keeps sentence case. | the added lines of `git diff origin/develop...HEAD` searched for an em dash, an en dash, a spaced hyphen and a double asterisk: no match, exit 1 |
| About test and type check | `Test Files 1 passed (1)`, `Tests 12 passed (12)`; `npx tsc --noEmit -p .` printed nothing, exit 0. No test reads either changed sentence, so reverting the copy would leave both green (build.md says the same). | run in frontend |
| Rendered text | The JSX line break before "rule is called cite or refuse" collapses correctly: `...answering from memory. That rule is called cite or refuse.` | jsdom render, throwaway test |

Verified by my own probes: the rendered text of both changed paragraphs; the absence of "track" and "segment" on the rendered page; the facts checker, the About test and tsc; the held-piece behaviour of grounding on this checkout (V-51-01). Read only: the marker colour rule in `CitationMarkers.tsx` and `uncitedInk` (I did not render an answer with an uncited claim), and that the copied-cut check uses the same instruction as reworded sentences.

The checkout was not edited: two throwaway files (a Python probe kept outside the checkout, a vitest file moved out after each run) and `git status --short` shows only the pre-existing untracked `frontend/node_modules`.

## Verdict

DO NOT MERGE: V-51-01. The branch rightly removes the false track sentence, but it adds "a sentence with any piece held back is dropped whole", which the code does only for copied pieces, so the page now overstates a check, the kind of sentence this card exists to remove. A one-word fix ("any copied piece") or the reader's-words rewrite in V-51-04 clears it; everything else here is minor and need not block.
