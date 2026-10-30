# Card 152 build: search a topic's words as one term

Built on branch `fix/card152-topic-words-as-one-term` from `origin/develop` (`15363460`). No model call was made. The only network calls were free read-only PubMed ESearch GETs.

## Table of contents

- [What changed](#what-changed)
- [Tests](#tests)
- [Live counts](#live-counts)

## What changed

| File | Change |
|---|---|
| `src/system_03_search_agent/core/breadth_plan.py` | `build_topic_term` joins the content words with a space, so PubMed can read "cystic fibrosis" as one subject. Word extraction is unchanged; lowercase "or" and "not" stay out as stopwords. Docstrings say why. |
| `src/system_03_search_agent/core/graph.py` | The plan line reads `for: <words as typed>` instead of a comma split on AND. |
| `src/system_03_search_agent/synthesis/refuse.py` | The nothing-found message names the words as typed. |

## Tests

| Check | Result |
|---|---|
| `test_topic_search.py`, `test_breadth_plan.py`, `test_card_17_lead_in_order.py` | 147 passed |
| New: the term for "recent papers on cystic fibrosis" is "cystic fibrosis", and with a window it is that term ANDed with the date clause | Pass |
| New: "or" and "not" never reach the term | Pass |
| New: the plan line reads "for: <term>" and the refusal names the words as typed | Pass |
| Mutation: put " AND " back in `build_topic_term` | 22 failed, then restored to 147 passed |
| `ruff check .` | All checks passed |
| `isort --check-only` as in gate02 | Clean |

## Live counts

ESearch, 2026-10-30, no window, as `build_topic_term` now sends them.

| Term | Hits | Diagnosis reported |
|---|---|---|
| effects caffeine exercise performance | 1,369 | 1,369 |
| coffee exercise effective | 534 | 534 |
| variants people mediterranean descent | 17 | 17 |
| positive negative genes ashkenazi jewish people | 27 | 27 |
| cystic fibrosis (no window) | 69,964 | not reported without a window |
