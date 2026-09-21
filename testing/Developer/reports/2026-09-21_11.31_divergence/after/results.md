# Item 11.31 measured live, after the change

Four live runs against develop at `7d7b109`, two questions at both depths,
using the same instrument and the same counter as the baseline so the two are
comparable. Raw captures sit beside this file.

## What changed, in numbers

| Run | Prose words before | Prose words after | Paragraphs before | After |
|---|---|---|---|---|
| BRCA1, plain language | 89 | 206 | 4 | 7 |
| BRCA1, researcher | 164 | 85 | 4 | 4 |
| HNF1A, plain language | 135 | 171 | 6 | 7 |
| HNF1A, researcher | 127 | 127 | 5 | 5 |

The ordering REVERSED, which is the product owner's actual ask. Plain language
was shorter than researcher on BRCA1 before (89 against 164) and is now more
than twice as long (206 against 85). On HNF1A it went from shorter to longer
as well.

Record rows are unchanged at 66 to 67 for BRCA1 and 92 for HNF1A, at both
depths, exactly as intended: removing the evidence trail from plain language
was rejected, so the divergence had to come from the prose growing.

## What a person now sees

Plain language gives each finding its own short everyday sentence, grouped
into paragraphs:

```
The diseases associated with BRCA1 are Familial cancer of breast [1], ...
The gene linked to these diseases is BRCA1 [5]. One disease is called
Familial cancer of breast [1]. Another disease is called ...
```

Researcher keeps its `## Topic` sections and synthesises across records
instead of walking them one at a time.

## The gene summary reaches the page, and is not used to explain

Both halves of this are true and the second is the honest limit of this pass.

It IS retrieved, emitted as its own citeable finding, and rendered: the BRCA1
answer carries `gene name: BRCA1 [12]` from the ESummary row and the summary
itself under `[15]`.

It is NOT used by the model to explain anything. The prose walks the disease,
trial and ClinVar records and never reaches for the summary. Two plausible
reasons, neither confirmed:

- The summary lands at `[15]` among 67 findings, well down the list.
- `build_answer_context_directive` still tells the model to keep context
  findings brief, and the gene record is a context finding. The "except where
  one is a plain description" clause added in this pass may be too weak
  against a directive that names the findings by marker.

So 11.31 delivers the divergence and the retrieval, and does NOT yet deliver
the explanation the product owner asked for. That gap is real and is recorded
rather than rounded up.

## And it is truncated mid-word, which is item 11.33

`[15]` renders as "This gene product associates with RNA polymerase II, and
through the C-terminal d", cut mid-word exactly as the PubMed abstracts are.
So 11.33 now damages this feature too, which raises it from a cosmetic defect
to one that degrades the explanation 11.31 exists to provide.

## One thing worth watching

BRCA1's researcher prose fell from 164 words to 85 in this pass. Nothing in
the change touched the researcher directive, so this is most likely ordinary
run-to-run variance rather than a regression. It is written down because one
run is not a measurement, and a second pass should check it rather than
assume.
