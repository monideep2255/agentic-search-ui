# Card 152 diagnosis: a topic papers question searches its words separately

Card 152, in the person's words: "A topic papers question searches its words separately, so `recent papers on cystic fibrosis` lists papers on choledochal cysts, bacterial overgrowth, polycystic kidney disease and fibrosis in general: 2 of PubMed's top 5 and 4 of its top 10 for the term `cystic AND fibrosis`." Read-only diagnosis, 2026-10-30, source read as on `origin/develop` (`fa37d18c`). No model call was made. The live evidence is free NCBI E-utilities GETs, at most 3 a second, with `sort=relevance` as the tool sends it.

## Table of contents

- [Summary](#summary)
- [How the term is built](#how-the-term-is-built)
- [Which questions take this path](#which-questions-take-this-path)
- [What PubMed does with each term shape](#what-pubmed-does-with-each-term-shape)
- [Recommended fix](#recommended-fix)
- [Could Think supply the phrase](#could-think-supply-the-phrase)
- [Options not recommended](#options-not-recommended)
- [Owner decision](#owner-decision)
- [Overlap with other cards](#overlap-with-other-cards)

## Summary

| Question | Answer |
|---|---|
| Cause | `build_topic_term` joins the question's content words with an explicit ` AND `. PubMed's automatic term mapping then maps each word on its own, so `cystic` and `fibrosis` never meet as the concept "cystic fibrosis", and relevance ranking rewards papers that hold the two words anywhere. |
| Cause clear | Yes. ESearch's own `querytranslation` shows the split, and the top 10 matches the product check's off-topic rows. |
| Fix | Join the same words with a space instead of ` AND `. PubMed already requires every word in a space-joined term, and it first looks the whole string up as a concept, so "cystic fibrosis" maps to its MeSH heading. No list of phrases, no model call. |
| Fix small | Yes, about 10 source lines across `core/breadth_plan.py`, `core/graph.py` and `synthesis/refuse.py`, one area (the topic search), plus test updates. |
| Owner decision needed | No. The four measured questions keep their exact hit counts; one ranking shifts slightly (below). |
| Build tonight | Yes: the cause is measured, the fix is small, deterministic and free, and it touches no prompt. |

## How the term is built

| Step | Code (on `origin/develop`) | For `recent papers on cystic fibrosis` |
|---|---|---|
| 1 | `core/graph.py:7108` to `7120` | No gene resolved, and the `plan.literature` classifier says the question asks for papers, so the topic path runs even though "cystic fibrosis" resolves to MedGen. |
| 2 | `core/breadth_plan.py:630` to `655`, `topic_search_words` | Lowercases, drops grammar, meta ("papers"), filler, judgement and recency ("recent") words, keeps order, caps at 8: `["cystic", "fibrosis"]`. |
| 3 | `core/breadth_plan.py:694`, `build_topic_term` | `" AND ".join(words)` gives `cystic AND fibrosis`. |
| 4 | `core/breadth_plan.py:697` to `718`, `plan_topic_search` | ANDs the picked window: `cystic AND fibrosis AND ("2021/10/30"[dp] : "3000"[dp])`, retmax 10 with a window. |
| 5 | `core/graph.py:7312` and `synthesis/refuse.py:103` | Split the term back on ` AND ` to show the words in the plan narrative and in the "nothing found" refusal. |

Why ` AND `: the docstring (`breadth_plan.py:658` to `690`) defends leaving the words untagged, so PubMed's mapping can expand them, and it was right about that. The explicit ` AND ` was never measured against a space; it was taken as the way to say "every word is required". But a space already means that in PubMed, and the explicit operator is what stops the mapping from seeing two words as one concept.

## Which questions take this path

| Question shape | Path | Affected |
|---|---|---|
| A topic with no gene or disease (`papers on caffeine and exercise`) | Topic path | Yes, for multiword concepts |
| A disease named in a papers question (`recent papers on cystic fibrosis`) | Topic path, by step 1 | Yes: the card's case |
| A topic with a picked window | Topic path with the date limit ANDed on | Yes; the limit is unchanged |
| A multiword gene name with no symbol resolved (`sonic hedgehog signalling`) | Topic path | Shape changes, results do not (PubMed maps no phrase there) |
| A disease question not asking for papers | Disease path, `"<MedGen title>"[Title/Abstract]` (`build_pubmed_term`) | No |
| A gene question | Gene path, `SYMBOL[Title/Abstract]` | No (that is card 122) |

## What PubMed does with each term shape

Live ESearch, `sort=relevance`, 2026-10-30. "On topic" means the title is about the asked subject.

| Term | Hits | PubMed's reading | Top 10 on topic |
|---|---|---|---|
| `cystic AND fibrosis` + 5-year window (today) | 13,392 | `cystic` in any field AND `fibrosis` MeSH or any field | 6 of 10: rows 3, 5, 6 and 10 are general fibrosis, choledochal cysts, bacterial overgrowth, polycystic kidney disease |
| `cystic fibrosis` + 5-year window | 13,356 | `"cystic fibrosis"[MeSH Terms] OR (cystic AND fibrosis) OR "cystic fibrosis"[All Fields]` | 10 of 10 |
| `"cystic fibrosis"[Title/Abstract]` + window | 10,585 | Exact phrase in title or abstract, mapping off | 9 of 10 (row 4 is a bare "Correction."); editorials crowd the top |
| `"cystic fibrosis"[MeSH Terms]` + window | 5,597 | Indexed papers only | 10 of 10, but misses papers not yet indexed, the newest ones |
| `breast AND cancer` + window | not counted with window; 600,318 without | `breast` AND any neoplasm | 8 of 10 (a general HER2 paper and a profile of a surgeon) |
| `breast cancer` + window | 595,192 without | `"breast neoplasms"[MeSH Terms]` first | 10 of 10 |
| `effects AND caffeine AND exercise AND performance` | 1,369 | Each word mapped | Top 5: 5 of 5; top 10: 8 of 10 |
| `effects caffeine exercise performance` | 1,369 | Identical translation | Top 5: 4 of 5 (a creatine review first); top 10: 7 of 10 |
| Same two caffeine terms + 5-year window | not compared | Identical translation | About the same: both lists are half supplement reviews; the order shuffles |
| `"caffeine and exercise performance"` (quoted) | 1,572 | Not in PubMed's phrase index, so split anyway | Similar to the unquoted term |
| `tree AND life` and `tree life` | 34,576 each | `trees` AND `life` | Mostly forest ecology. Today's word extraction drops "of", so neither is "tree of life" |
| `"tree of life"` (quoted) | 5,366 | `"tree of life"[All Fields]` | On topic, with one synagogue shooting paper at row 1 |

The measured questions in `tests/system_03_search_agent/core/test_topic_search.py` keep their exact hit counts under a space join: caffeine 1,369, coffee 534, Mediterranean 17, Ashkenazi 27. The translation is identical where no word pair is a concept; only the ranking order can move.

Two traps measured while checking alternatives:

- PubMed treats lowercase `or` and `not` as operators: `aspirin or ibuprofen` translates to an OR and `aspirin not ibuprofen` to a NOT. Today's stopword list drops both, so a space-joined term cannot carry them. Keeping grammar words inside the term would.
- Keeping an inner word PubMed does not ignore narrows the search: `coffee exercise more effective` gave 146 hits against 534.

## Recommended fix

From the person's chair: a question about "cystic fibrosis" searches for cystic fibrosis, not for anything with "cystic" in it and "fibrosis" in it.

The change: `build_topic_term` returns the same content words joined with a single space instead of ` AND `. PubMed's own mapping then finds multiword concepts (cystic fibrosis, breast cancer, quality of life when typed with its "of") from the person's words in their order. The words, their order, the 8-word cap, the window and the untagged choice all stay.

| Part | File and place | Change | Lines |
|---|---|---|---|
| 1 | `core/breadth_plan.py:694` and the docstrings at `32` to `37` and `658` to `690` | `" ".join(words)`; state why (a space is PubMed's AND and lets the mapping see a concept), with today's measurements | 1 code, about 8 comment |
| 2 | `core/graph.py:7312` | Show the words as typed: `f"{why} for: {topic_term}"` instead of splitting on ` AND ` | 1 |
| 3 | `synthesis/refuse.py:95` to `107` | Same: show the term's words with spaces; update the docstring | 2 to 4 |

What the person sees after: `recent papers on cystic fibrosis` lists ten cystic fibrosis papers (live top 10: epidemiology, CFTR modulators, genome editing, carriers, adults); the plan line reads "searching the literature for: cystic fibrosis" where it read "cystic, fibrosis"; a breast cancer papers question loses its general cancer and biography rows. A caffeine question gets the same papers, with one creatine review moved up into the top 5.

Tests:

- Update the expected terms in `test_topic_search.py` (`MEASURED_TERMS` at line 91, lines 126, 175, 190, 919, the refusal text at 350 and the empty case at 387), `test_breadth_plan.py:489` (`long covid`), and the fixture `test_card_17_lead_in_order.py:257` if its wording is asserted.
- New: `build_topic_term("recent papers on cystic fibrosis") == "cystic fibrosis"`, with no ` AND ` in it; with a window, the term ends in the date clause joined by ` AND `.
- Keep the operator test (line 169): a typed `OR`, brackets and quotes still never reach the term.
- Mutation check: putting ` AND ` back turns the new test red.
- Live check after deploy: the card's question on develop, five runs, counting off-topic rows in the ten listed (today 4 of 10).

Cost: about 10 source lines and about 20 test lines, no model spend, no new network call. The search stays a pure function of the question text, so one question still shows one source set.

## Could Think supply the phrase

It could, at a price the fix does not need to pay:

- Think's disease span is a model sample whose boundaries move between runs, which is why item 11.21 bars it from search inputs (`core/graph.py:5262` to `5266`). A phrase taken from it would break "the same question shows the same sources".
- The resolved MedGen record's title is deterministic, but it only exists for diseases and it is not always the subject: MedGen binds "caffeine" to caffeine disorders, which is the defect the topic path was built to escape (`core/graph.py:7075` to `7088`).
- PubMed's mapping already recognises the concept from the words in order, deterministically and for free, for every kind of subject, not only diseases.

So no: the person's own words, handed to PubMed without an operator between them, are enough.

## Options not recommended

| Option | Why not |
|---|---|
| Quote the whole word string | A string not in PubMed's phrase index is split anyway (the caffeine case), and a quoted phrase with the "of" dropped (`"tree life"`) finds nothing useful. |
| Tag `[Title/Abstract]` | Turns the mapping off; measured 2026-09-23 as 27 hits to zero on the Ashkenazi question. |
| Keep grammar words between content words, so "tree of life" survives | Lowercase `or` and `not` become PubMed operators, and words like "more" become required (534 hits to 146). A safe version needs a second word list of PubMed's own stopwords; not worth it for this card. |
| A list of known phrases | Hardcoded and endless; ruled out by the project's rule. |

Known gap after the fix: a concept whose name holds a grammar word ("tree of life", "theory of mind", "quality of life") is still split, as today, because the word extraction drops "of". It is no worse than today, and a later card can take it on if a person notices it.

## Owner decision

None needed. The change keeps every measured hit count, makes the card's question and breast cancer lists fully on topic, and shuffles one caffeine ranking within the same paper set. If the owner wants a say, the question would be: "Join topic words with a space so PubMed can see multiword terms such as cystic fibrosis (recommended: fixes this card, one caffeine list reorders), or keep the explicit AND (no change, the card stays open)?"

## Overlap with other cards

| Card | Overlap |
|---|---|
| 122 (gene literature search) | None in code. Card 122 is `build_pubmed_term`'s `SYMBOL[Title/Abstract]` on the gene path; this card is `build_topic_term` on the topic path. Both live in `core/breadth_plan.py`, so build them as separate commits. |
| 56 (question reading redesign, with 129 folded in) | None in code. Card 56 is how a question's subject is read and bound (organism and disease reading); this card is how already-chosen words are sent to PubMed. If card 56 later routes disease papers questions through the disease path, that question would use the MedGen title instead and this fix would still serve every other topic question. |
| 119 (ten papers in a window) | Card 119 raised the list from 5 to 10 and so exposed rows 6 to 10; it did not cause the split. |
