# Grounding gate expressibility: which plain-language shapes survive `run_grounding_pass`

An offline, deterministic probe of `src/system_03_search_agent/synthesis/grounding.py`'s cite-or-refuse gate against an abstract-length finding, to answer one question before a new plain-language depth directive is written: which SHAPES of explanatory sentence actually survive, so the directive never asks the model for a form the gate cannot pass.

## Table of contents

- [Command that produced these results](#command-that-produced-these-results)
- [Fixture data](#fixture-data)
- [Results by shape](#results-by-shape)
- [The three sub-checks, and which one actually fails](#the-three-sub-checks-and-which-one-actually-fails)
- [What a plain-language directive may therefore ask for](#what-a-plain-language-directive-may-therefore-ask-for)
- [What it must not ask for](#what-it-must-not-ask-for)

## Command that produced these results

Every SURVIVED / STRIPPED verdict below comes from an actual call to the real, unmodified `run_grounding_pass`, run offline with no server and no model call:

```bash
# from the repository root
PYTHONPATH=src python3 testing/Developer/reports/2026-09-21_11.31_divergence/probe_grounding.py
```

Full raw output (19 cases, one JSON object each) is saved alongside this report as `probe_output.json`. The probe script is `probe_grounding.py` in this same folder. Nothing in this report was inferred from reading `grounding.py` alone: every verdict is the printed result of the command above, and the `diagnosis` block on each case is a second, direct call to the three sub-checks `run_grounding_pass` composes (`ground_claim`, `numbers_are_supported`, `claim_introduces_no_new_content`), used only to explain a verdict already produced by the real pass, never to substitute for it.

Total: 19 candidate sentences across the 8 required shapes. 3 SURVIVED, 16 STRIPPED.

## Fixture data

`ABSTRACT_FINDING`: a `SynthFinding` whose `field_value` is a whole retrieved PubMed abstract, quoted verbatim from this repository's own shipped test fixture, `tests/system_03_search_agent/synthesis/test_pubmed_abstract_grounding.py`'s module-level `_ABSTRACT` constant (the fixture built for UI fix 11.22, the change that made a whole abstract citeable as one finding):

> Background: BRCA1 encodes a tumor suppressor. Methods: we sequenced 312 tumors. Results: pathogenic BRCA1 variants abolish homologous recombination in this cohort. Conclusion: carriers should be offered enhanced surveillance.

This is real prose already used by the shipped test suite, not synthetic text.

`DISEASE_FINDING`: a Layer 1 graph-record finding in the shape used elsewhere in the test suite, `field_value` "BRCA1 is associated with MedGen:C0346153", `field` "disease_association", `curie` "MedGen:C0346153", `entity_type` "Disease".

## Results by shape

### Shape 1: restates the abstract's mechanism, everyday syntax, only words in the abstract

| Candidate | Verdict |
|---|---|
| "BRCA1 encodes a tumor suppressor [1]." | SURVIVED |
| "Pathogenic BRCA1 variants abolish homologous recombination in this cohort [1]." | SURVIVED |

Both pass all three sub-checks cleanly, `ground_claim_ok`, `numbers_are_supported_ok` and `claim_introduces_no_new_content_ok` all true, with an empty offending-token set. A sentence built entirely from a contiguous run of the abstract's own words, kept in the abstract's own word order, survives.

### Shape 2: a common everyday synonym for a technical word that IS in the abstract

| Candidate | Verdict | Offending tokens |
|---|---|---|
| "BRCA1 acts as a brake on cell growth [1]." | STRIPPED | acts, brake, cell, growth |
| "BRCA1 helps stop tumors from forming [1]." | STRIPPED | forming, helps, stop |

Both fail `ground_claim` (the paraphrase is neither equal to nor a substring of the abstract text) and the content-token allowlist (none of "brake", "cell", "growth", "stop", "forming" appear anywhere in the supporting text). Everyday-language substitution for a technical term is not licensed at all, unlike the four relational-synonym words (see shape 6).

### Shape 3: a general definitional sentence with no source behind it

| Candidate | Verdict | Offending tokens |
|---|---|---|
| "A gene is a stretch of DNA that carries instructions [1]." (marked) | STRIPPED | carries, dna, gene, instructions, stretch |
| "A gene is a stretch of DNA that carries instructions." (unmarked, no marker at all) | STRIPPED | (uncited factual claim, Section 8.1's no-narrative-only-claims rule) |

Neither survives, marked or not. A marked general-knowledge sentence fails the allowlist because none of its content words are in the finding. An unmarked one is stripped outright as an uncited assertion, since it is not recognized as framing (`_is_framing` requires everything after a fixed opener phrase to be function-words-only, and this sentence has no framing opener at all).

### Shape 4: draws on BOTH the question wording and the abstract's or record's wording

| Candidate | Question | Verdict | Notes |
|---|---|---|---|
| "Which mechanism does BRCA1 disrupt in tumors [1]?" | "Which mechanism does BRCA1 disrupt in tumors?" | STRIPPED | `ground_claim_ok=false`; allowlist passes (the question's open wh-content is licensed) but the clause is not itself equal to or a substring of the abstract text |
| "BRCA1 is associated with MedGen:C0346153, which the question asks about [2]." | "Which diseases are associated with BRCA1?" | STRIPPED | offending tokens: about, asks, question. Any exposition ABOUT the question, rather than words drawn from the licensed part of the question itself, is new content |
| "MedGen:C0346153 is associated with BRCA1 [2]." (subject/object reordered vs. the finding) | "Which diseases are associated with BRCA1?" | STRIPPED | `ground_claim_ok=false`; allowlist passes cleanly (offending tokens empty) |

None of the three survived, and each fails for a DIFFERENT reason, which is the finding worth carrying into the directive: the content-token allowlist (`claim_introduces_no_new_content`) is genuinely permissive about pulling in licensed question words, but `ground_claim`, the equality-or-substring check that runs independently, is strict about the clause's own wording and WORD ORDER matching the finding's `field_value` (or the abstract text) exactly. A sentence can pass the allowlist and still fail the gate because it restates the same fact in different word order.

### Shape 5: one dense Layer 1 record finding split into two or three short one-idea sentences, same marker

| Candidate | Verdict |
|---|---|
| "BRCA1 is associated with a disease [2]. That disease is MedGen:C0346153 [2]." (paraphrased split) | STRIPPED (both clauses) |
| "BRCA1 is associated with [2]. MedGen:C0346153 [2]." (verbatim split, each fragment an exact contiguous substring of the field_value) | SURVIVED (both clauses, 2 claims) |

The paraphrased split fails `ground_claim` on both sentences: "BRCA1 is associated with a disease" is neither equal to nor a substring of "BRCA1 is associated with MedGen:C0346153", and neither is "That disease is MedGen:C0346153". The verbatim split survives because each fragment, taken alone, IS an exact contiguous substring of the finding's `field_value`. Splitting a dense finding into short sentences is only safe when each resulting fragment is still a literal contiguous piece of the source text, not a paraphrase of a piece of it.

### Shape 6: a relational synonym where the finding uses a different one of the four

| Candidate | Verdict | ground_claim_ok | allowlist_ok |
|---|---|---|---|
| "BRCA1 is related to MedGen:C0346153 [2]." | STRIPPED | false | true |
| "BRCA1 is linked to MedGen:C0346153 [2]." | STRIPPED | false | true |
| "BRCA1 causes MedGen:C0346153 [2]." (causes is deliberately excluded from the four-word synonym set) | STRIPPED | false | false, offending token: causes |

The content-token allowlist does fold "related" and "linked" onto the same canonical token as "associated" (`_RELATIONAL_SYNONYMS`/`_canonicalize_relational`), exactly as documented, and that check passes for both. But all three still STRIP, because `ground_claim`'s separate equality-or-substring test compares the literal clause text against the literal `field_value`, and "BRCA1 is related to MedGen:C0346153" is not a substring of "BRCA1 is associated with MedGen:C0346153" no matter what the allowlist says. The relational-synonym allowance never actually helps a claim survive on its own; `ground_claim` is the binding constraint. "causes" additionally fails the allowlist, confirming it sits outside the licensed synonym set as documented.

### Shape 7: a framing opener with nothing content-bearing after it, and a framing opener followed by a factual claim

| Candidate | Verdict |
|---|---|
| "In summary, the following was found [1]." (opener, contentless remainder) | STRIPPED (stripped_count=1) |
| "In summary, BRCA1 encodes a tumor suppressor." (opener + factual claim, no marker) | STRIPPED |
| "In summary, BRCA1 encodes a tumor suppressor [1]." (opener + factual claim, marker present) | STRIPPED |

None of the three survives, including the contentless-remainder case, which is worth flagging because it looks like it should pass under `_is_framing`'s own logic. Two different mechanisms are at work:

- The contentless opener ("the following was found") is genuinely pure framing under `_is_framing`, but that function only ever applies to an UNMARKED segment. Here the marker `[1]` sits at the end of the same clause, so the whole span is treated as ONE marked segment and is checked by `ground_claim`/`claim_introduces_no_new_content` instead of `_is_framing`. "in summary, the following was found" is neither equal to nor a substring of the abstract text, so `ground_claim` fails it outright.
- The marked factual-claim case ("In summary, BRCA1 encodes a tumor suppressor [1].") fails the same way: `_clean_claim` only strips leading `",;: "` characters and a small set of leading connective words (`and`, `or`, `but`, `also`, `then`), never the phrase "In summary". The clause `run_grounding_pass` actually evaluates is the full "In summary, BRCA1 encodes a tumor suppressor", which is not a substring of the abstract even though every content word in it ("BRCA1", "encodes", "tumor", "suppressor") is licensed by the allowlist. `ground_claim_ok=false`, `claim_introduces_no_new_content_ok=true`.

The load-bearing fact for shape 7: a framing opener and a citation marker must never sit in the SAME clause. Framing exemption only ever applies to a clause with no marker at all.

### Shape 8: a cautious hedge or an interpretation

| Candidate | Verdict | Offending tokens |
|---|---|---|
| "This suggests BRCA1 encodes a tumor suppressor [1]." | STRIPPED | suggests |
| "This suggests the risk may be higher [1]." | STRIPPED | higher, may, risk, suggests |

Both fail. "suggests" is not in `_FUNCTION_WORDS` and is not licensed by the finding, so it alone is enough to strip an otherwise word-for-word restatement of the abstract. Any hedge, interpretation, or inferential verb ("suggests", "may", "indicates", "implies") is content the gate treats exactly like a fabricated clinical claim, because nothing distinguishes "this suggests X" from "X is definitely true" at the token level, and the gate is deliberately fail-closed on anything it cannot verify.

## The three sub-checks, and which one actually fails

`run_grounding_pass` only reports an aggregate `stripped_count`, so the probe calls the three sub-checks directly on the same claim text to attribute each strip. Across all 16 STRIPPED cases, the pattern is consistent and is the single most important thing this probe surfaces:

- `claim_introduces_no_new_content` (the content-token allowlist) is the check most people would expect to be the bottleneck, and it is the LESS restrictive of the two content checks. It correctly rejects invented content (shape 2's synonyms, shape 3's general knowledge, shape 8's hedges, shape 6c's "causes") but it correctly ACCEPTS several paraphrases and reorderings that still get stripped anyway.
- `ground_claim` (Section 8.2 step 5: equality or substring, in either direction, normalized) is the check that actually blocks most of the paraphrase and reordering cases: shape 4's reordered disease sentence, all three of shape 6's relational-synonym sentences, shape 5's paraphrased split, and shape 7c's opener-plus-claim sentence all pass the allowlist and still fail `ground_claim`.
- `numbers_are_supported` never fails in this data set. No candidate introduced an unsupported standalone number, so it is not the constraint here, though it remains load-bearing for any sentence with counts.

The practical consequence: a directive that only worries about "does the model invent a word" is solving the less binding half of the problem. The gate is closer to "is this clause a literal, contiguous excerpt (or an exact restatement in the source's own word order) of something in the finding" than to "does this clause avoid inventing information."

## What a plain-language directive may therefore ask for

- A short, everyday-syntax sentence built as a contiguous excerpt of the abstract, kept in the abstract's own word order and phrasing (shape 1: both candidates SURVIVED).
- Splitting one dense finding into several short sentences, PROVIDED each resulting sentence is still an exact contiguous substring of that finding's `field_value`, not a reworded piece of it (shape 5b SURVIVED, shape 5 paraphrased did not).
- Drawing content from the licensed (open, wh-) part of the user's own question, but only when the resulting clause's wording still matches the cited finding closely enough to pass `ground_claim`'s equality-or-substring test, not merely close enough to satisfy the token allowlist.

## What it must not ask for

- Substituting an everyday synonym for a technical term in the abstract, even when the technical term itself appears in the source (shape 2: "brake on cell growth" for "tumor suppressor" was STRIPPED). Plain language must reuse the abstract's own vocabulary, not translate it.
- General definitional or background sentences with no finding behind their content words, marked or unmarked (shape 3: both STRIPPED).
- Reordering a finding's own words, even into a still-true sentence (shape 4c, shape 6a, shape 6b: all reordered restatements of the disease finding were STRIPPED by `ground_claim` despite passing the content allowlist). A depth directive must not assume that "every word is licensed" is sufficient; word order relative to the cited finding matters just as much.
- Mixing exposition ABOUT the question into the answer clause (shape 4b: "which the question asks about" added ungrounded tokens and stripped an otherwise-correct sentence).
- Placing a framing opener ("In summary,", "Note:", etc.) in the SAME clause as a citation marker and a factual claim (shape 7c). Framing must be its own, unmarked segment, or the whole clause is checked against `ground_claim` as if it had no framing exemption at all.
- Any hedge, inference, or interpretive verb: "suggests", "may", "indicates", "implies", "this means" (shape 8: both STRIPPED). The gate cannot distinguish a cautious hedge from an invented certainty, and treats both as unlicensed content.
- Using "causes" as a stand-in for the graph's "associated with" or "related to" (shape 6c STRIPPED on both `ground_claim` and the allowlist). This is a deliberate, documented exclusion in `_RELATIONAL_SYNONYMS`, not a gap to route around.
