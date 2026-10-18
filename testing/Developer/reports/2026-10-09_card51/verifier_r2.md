# Card 51 fresh verifier report, round 2

Fresh verifier, 2026-10-09. Checkout detached at d044324304d6976ea7431ec6b0f5c6ed31799fd0 (expected d0443243, matches). Change: `git diff origin/develop...HEAD`, commits 68e9d7d5 and d0443243 (fix round).

## Findings and checks

### Checks run

- Facts checker, `python3 .claude/skills/verify/scripts/check_facts.py`: `facts: 80 | stale 0 | not fully checked 0 | places: PASS 225, FAIL 0, GAP 0, ERROR 0 | PASS`, exit 0.
- `npx vitest run src/components/screens/AboutScreen.test.tsx`: `Test Files 1 passed (1)`, `Tests 12 passed (12)`.
- `npx vitest run src/components/screens` (the directory): `Test Files 18 passed (18)`, `Tests 165 passed (165)`.
- `npx tsc --noEmit -p .`: no output, exit 0.

### V-51-R2-01: the rewritten stop 5 sentence says every word-for-word copy is judged by the model, but a copy of a whole record sentence is shown with no model check

- Severity: major
- Regression of: V-51-04
- What: the fix round replaced "A copied cut is judged the same way" with "A sentence that copies part of a record word for word is judged the same way" (InfoScreens.tsx:1488 to 1489). "The same way" points at the sentence before it, "judged by a model". The code sends a copied clause to the model check only when it is a cut, a piece of one of the record's sentences; a clause that copies a whole sentence of the record word for word is shown with no check (grounding.py:1682 to 1684, "a copied clause shows with no check only when it is a whole sentence of its record, word for word"; `is_cut` at grounding.py:1702 to 1705). A whole record sentence is part of a record, so the new words cover it, and for it they are false. "A copied cut" was jargon but exact; the plain-words rewrite widened it.
- Reproduction: probe calling `run_grounding_pass` on this checkout with one record, "Bronchiolitis is a common lung infection in young children. Treatment is usually symptomatic. Antibiotics are effective only when a bacterial infection is confirmed.", and an empty candidate sink. Output:
  `WHOLE_SENTENCE_COPY | sink: [] | shown: 'Treatment is usually symptomatic [1].'`
  `WHOLE_SENTENCE_COPY_2 | sink: [] | shown: 'Bronchiolitis is a common lung infection in young children [1].'`
  `CUT_FIRST_PASS | sink: [SynthesisCandidate(key=('antibiotics are effective', ...` with nothing shown.
  The empty sink means no model check was asked for; the sentence shows on the first pass. The cut goes to the check, as the page says. The test file's own header agrees: "A whole record sentence still shows with no model call" (tests/system_03_search_agent/synthesis/test_copied_cuts.py:24).
- Why it matters: a reader of About is told that every sentence lifted from a record was also read by a model, and the commonest lifted sentence, a whole sentence of the record, was not. That overstates the check, the exact kind of sentence this card exists to remove, and the page now contradicts itself: the sentence before says a sentence is judged by a model only when it was reworded. Develop's stop 5 said nothing about copies, so on this sentence the branch is less true than develop. The second half, "if any copied part is held back the whole sentence is dropped", is true: probe `CUT_NOTHING_APPROVED` and `WHOLE_PLUS_CUT_NOTHING_APPROVED` both show nothing (`refused=True`), and grounding.py:1816 forces the whole drop on any held copy.
- Smallest fix, for the lead: scope it to a piece of a sentence, for example "A sentence that copies only part of one of a record's sentences is judged the same way, and if any copied part is held back the whole sentence is dropped."
- NOT FIXED

The same wording is in the test query line added for the owner, testing/Test_queries_and_workflows.md:1829 ("Stop 5 says a sentence that copies part of a record word for word is judged by the same model check"), so a tester following it would confirm the overstatement.

### V-51-R2-02: no check reads either changed sentence, so the retired track sentence could come back unnoticed

- Severity: minor
- What: neither the About test nor the facts checker reads the "Cite or refuse" paragraph's last sentence or stop 5's new sentence.
- Reproduction: with develop's track sentence ("The track beside each answer shows one segment per claim, coloured by its layer, so an uncited claim is visible before you read a word.") put back in place of the new one, then restored from a byte backup: `about test with track sentence restored: ['Tests  12 passed (12)']`, `facts with track sentence restored: facts: 80 | stale 0 | not fully checked 0 | places: PASS 225, FAIL 0, GAP 0, ERROR 0 | PASS exit 0`. The green checks above are therefore not evidence that the new sentences are true; the build report says the same.
- Why it matters: the card's promise rests on review only. Not worse than develop, which pinned neither sentence either.
- NOT FIXED

### V-51-R2-03: stop 6 and stop 7 still say every sentence has a source, beside a sentence that now names a framing line with none

- Severity: minor (inherited from develop)
- What: the new "Cite or refuse" sentence says "a line of framing with no source shows in muted ink with no marker after it" (InfoScreens.tsx:1563). Stop 6 says "Every sentence carries a numbered chip pointing at the record behind it" (InfoScreens.tsx:1505) and stop 7 says it "will not ship a sentence with no source behind it" (:1515). Grounding keeps framing with no marker (grounding.py:1553 to 1555, `_is_framing`, for example "In summary, the following was found"), so stop 6 and stop 7 are not literally true on develop either.
- Why it matters: the fix round's rewording ("framing" not "claim") removed the clash with "Every claim is tied to a specific record", which was V-51-02; the clash with stop 6 and 7 stays. Not worse than develop, whose own sentence ("an uncited claim is visible") had the same tension.
- NOT FIXED

### Each fix-round finding

| Finding | Status | Evidence |
|---|---|---|
| V-51-01 ("any piece held back") | Fixed | Now "if any copied part is held back the whole sentence is dropped". True: grounding.py:1737 adds only held copied clauses to `held_for_check`, :1816 forces the whole drop; probe `WHOLE_PLUS_CUT_NOTHING_APPROVED` shows nothing (`refused=True`) |
| V-51-04 ("a copied cut" is jargon) | Fixed as jargon, but the rewrite overstates | Rendered: "A sentence that copies part of a record word for word is judged the same way". False for a whole record sentence: V-51-R2-01, Regression of: V-51-04 |
| V-51-02 (claim with no source vs every claim tied) | Fixed for that pair | Rendered: "Each claim's marker carries its layer's colour, and a line of framing with no source shows in muted ink with no marker after it." Uncited text in muted ink: AnswerScreen.tsx:1265 to 1266, applied at :1373, :1438, :1504; unmarked text grounding keeps is framing only (grounding.py:1545 to 1558). Stop 6 and 7 remain (V-51-R2-03) |
| V-51-03 (multi-layer marker is muted) | Open, no worse than develop | CitationMarkers.tsx:271; develop said nothing about marker colour |

### Every changed sentence, against today's code

| Sentence | True? | Evidence |
|---|---|---|
| "A sentence that copies part of a record word for word is judged the same way" | No, for a whole record sentence | V-51-R2-01 probe; grounding.py:1682 to 1705 |
| "if any copied part is held back the whole sentence is dropped" | Yes | grounding.py:1737, :1816; probe |
| "Each claim's marker carries its layer's colour" | Yes for a single-layer marker; a multi-layer marker is muted | CitationMarkers.tsx:271 (V-51-03, open) |
| "a line of framing with no source shows in muted ink with no marker after it" | Yes | AnswerScreen.tsx:1265 to 1266; useRunView.ts:810 to 820 gives a token with no marker an empty `citations` list |
| Track sentence gone | Yes | Rendered page: `HAS track: false HAS segment: false HAS copied cut: false`; AnswerScreen.tsx:1257 to 1263 names the spine as retired |

Rendered About text (jsdom, a throwaway test moved out of the checkout after): `A sentence that copies part of a record word for word is judged the same way, and if any copied part is held back the whole sentence is dropped. If nothing citeable survives, ... That rule is called cite or refuse.` and `Every claim is tied to a specific record. When nothing supports an answer, the system says so and stops rather than answering from memory. Each claim's marker carries its layer's colour, and a line of framing with no source shows in muted ink with no marker after it.`

House style: the added lines of the diff searched for an em dash, an en dash, a spaced hyphen and a double asterisk, no match (grep exit 1).

### Items left open, against develop

- V-51-03: no worse; develop said nothing about marker colour.
- V-51-R2-02, V-51-R2-03: no worse; both inherited.

### What I verified and what I only read

- Verified by my own probes: the grounding behaviour behind both halves of the stop 5 sentence (five `run_grounding_pass` cases), the rendered text of both paragraphs, the absence of the track wording, that no check pins either sentence (mutation), the facts checker, the About test, the screens directory and tsc.
- Only read: the marker colour rule (CitationMarkers.tsx:271) and that framing tokens reach the screen as claims with no citations (useRunView.ts); I did not render an answer with a framing line.

The checkout was restored after every probe; `git status --short` shows only `?? frontend/node_modules`.

## Verdict

DO NOT MERGE: V-51-R2-01, Regression of: V-51-04. The fix round's plain-words rewrite of stop 5 says every word-for-word copy from a record is judged by the model, while a copy of a whole record sentence is shown with no model check, so the page overstates the check and contradicts its own sentence before. Develop said nothing false here. Scoping the sentence to a part of one of the record's sentences (and the matching test query line) clears it; the rest of the fix round holds.

Correction to V-51-R2-03's line numbers: stop 6's "Every sentence carries a numbered chip" is InfoScreens.tsx:1504 and stop 7's "will not ship a sentence with no source behind it" is :1517.
