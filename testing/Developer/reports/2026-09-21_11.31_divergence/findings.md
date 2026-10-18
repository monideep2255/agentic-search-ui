# 11.31 is blocked upstream: the gate permits quoting, not explaining

Written 2026-09-21, while scoping item 11.31 (the two answer modes diverging).
The item cannot be built as written, and the reason is not in the depth
directive it names. Recorded here at the moment it was established rather than
at the end of the session.

## Table of contents

- [The finding](#the-finding)
- [How it was established](#how-it-was-established)
- [Why this explains the product owner's verdict](#why-this-explains-the-product-owners-verdict)
- [What it means for 11.31](#what-it-means-for-1131)
- [The obvious fix, and why it is unsafe as stated](#the-obvious-fix-and-why-it-is-unsafe-as-stated)
- [Two defects found on the way](#two-defects-found-on-the-way)

## The finding

`ground_claim` in `src/system_03_search_agent/synthesis/grounding.py` line 127
accepts a claim against the finding it cites only when, after normalization,
`a == b or a in b or b in a`. That is equality or contiguous containment in
either direction.

For a SHORT structured finding the `b in a` direction does the work: the
sentence contains the finding's value verbatim and wraps it in ordinary
English. That path is healthy and is how normal answers are built.

For a LONG free-text finding, such as the whole PubMed abstracts that became
citeable on 2026-09-20 in `9cf8572`, `b in a` is unreachable: a sentence cannot
contain a 400-word abstract. Only `a in b` remains, which means the sentence
must be a VERBATIM CONTIGUOUS EXCERPT of the abstract.

So against abstract material the gate permits quotation and forbids
explanation. A faithful paraphrase that introduces no new word at all, merely
reordering the abstract's own words, is stripped.

## How it was established

Run from the repository root, offline, no model and no server:

```
PYTHONPATH=src python3 testing/Developer/reports/2026-09-21_11.31_divergence/probe_grounding.py
```

That probe ran 19 candidate sentences across 8 shapes through the real
`run_grounding_pass`. 3 survived, 16 were stripped. The surviving 3 were all
literal contiguous excerpts.

The result was then re-checked by hand against `ground_claim` and
`claim_introduces_no_new_content` directly, because the first hand-check used
an incomplete `supporting_text` and produced a false negative on the healthy
short-finding path. The corrected run:

| Claim shape | `ground_claim` | allowlist | Verdict |
|---|---|---|---|
| Short finding wrapped in a sentence | True | True | PASS |
| Abstract, verbatim contiguous excerpt | True | True | PASS |
| Abstract, faithful paraphrase, its own words reordered | False | True | STRIP |
| Abstract, simplified to everyday words | False | False | STRIP |

Row 3 is the load-bearing one: it passes the content-token allowlist and is
stripped anyway, by contiguity alone.

## Why this explains the product owner's verdict

Their verdict on 2026-09-20 was that the answers look surface level and that
general chatbots answer better. This is the mechanism.

The only prose the gate can pass is a restatement of a record or a verbatim
quote. The product is therefore structurally incapable of explaining what its
records mean, at any depth. It is not that the synthesis is written badly; it
is that anything other than restatement is deleted before it reaches the page.

## What it means for 11.31

11.31 asks plain language to explain the concept in simple terms while staying
grounded. The product owner confirmed the constraint directly on 2026-09-21:
"Everything has to have a source. The synthesis can be in simple terms."

Those two halves are not jointly satisfiable under the gate as it stands.
Simple terms means different words; the gate accepts only the same words in the
same order.

Writing a fourth version of the plain-language depth directive would repeat a
failure this repository has already recorded three times in
`_DEPTH_DIRECTIVES`'s own comments: each previous version tried to buy a
property with an instruction about form, and the gate deleted the result.
Version 1 made the depth refuse outright, version 2 made it drop a finding,
version 3 made it refuse with an empty narrative. A version 4 asking for plain
explanation would be stripped the same way.

So 11.31 is BLOCKED pending a product decision about the gate itself, not about
the directive.

## The obvious fix, and why it is unsafe as stated

The obvious move is to drop the contiguity requirement for long free-text
findings and rely on the content-token allowlist alone, which already forbids
any word that is not in the source.

Measured, and it does not hold. With contiguity dropped, these all pass the
allowlist against the BRCA1 abstract used above:

- "Inherited breast cancer can be detected in BRCA1"
- "A tumour suppressor functions as BRCA1 and participates in DNA repair"
- "Families with inherited ovarian cancer can be detected in a substantial
  portion of BRCA1 mutations"

Three of four attempted reorderings ship. Every word is licensed and the
meaning is wrong, which is the confident-wrong-answer failure this product
exists to avoid. The allowlist is a defense against INVENTED words, and it was
never a defense against REARRANGED ones, because contiguity was carrying that
half.

Any relaxation therefore needs a second control to replace what contiguity was
doing. That is a design question with a real safety cost, and it belongs to the
product owner rather than to whoever picks up the next ticket.

## Two defects found on the way

Both are separate from 11.31 and neither has a ticket.

- Abstracts reach the page truncated mid-word. Live on develop at `46fff40`,
  the BRCA1 answer rendered "...families with inherited breast and/or ovarian
  c [29]", "...has been uncle [33]" and "...promotes ferroptosis s [35]". This
  is the visible face of the quotation-only constraint: the system excerpts a
  prefix of the abstract and cuts it at a character bound with no word
  boundary.
- Two of four live runs fell back to listing records because the written
  summary could not be verified against them, both HNF1A runs, at both depths.
  The two BRCA1 runs did not. Evidence in `baseline.md` and `raw/`.

The baseline also quantifies the sameness 11.31 was raised about: at both
depths the record dump is 66 rows for BRCA1 and about 92 for HNF1A, against 89
to 164 words of prose. The part that does not differ is most of the page.
