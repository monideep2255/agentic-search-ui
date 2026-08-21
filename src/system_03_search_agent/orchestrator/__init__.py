"""The orchestrator's few-shot routing pool (Section 17).

Created by build phase 4.6 (T-4.6-11) to hold `few_shot_examples.json`,
the versioned pool file Section 17 places at
`system_03_search_agent/orchestrator/few_shot_examples.py` "or an
equivalent JSON file loaded once at process start". This package is
deliberately empty otherwise: build phase 4.6 owns writing to the pool
file (`feedback.promotion.promote_candidate`), and build phase 4.7 owns
wiring Think and Plan to read it, per
`.claude/rules/prompt-cache-discipline.md`'s "loaded once at process
start, never per request" rule. Nothing in this package imports the pool
file yet; that loader is build phase 4.7's deliverable, not this one's.
"""

from __future__ import annotations
