"""The orchestrator's few-shot routing pool (Section 17).

Created by build phase 4.6 (T-4.6-11) to hold `few_shot_examples.json`,
the versioned pool file Section 17 places at
`system_03_search_agent/orchestrator/few_shot_examples.py` "or an
equivalent JSON file loaded once at process start". Build phase 4.6 owns
writing to the pool file (`feedback.promotion.promote_candidate`, via the
atomic, lock-serialized `few_shot_pool.append_example` as of build phase
4.7's T-4.7-03). Build phase 4.7 (T-4.7-02) adds `few_shot_pool.py`, the
loader that reads `few_shot_examples.json` exactly once per process and
holds it in memory, per `.claude/rules/prompt-cache-discipline.md`'s
"loaded once at process start, never per request" rule (obligation 3).
Threading `load_pool()`'s output into the Think and Plan calls' assembled
prompt is T-4.7-07, inside `harness/cache.py`'s `build_stable_prefix`.
"""

from __future__ import annotations
