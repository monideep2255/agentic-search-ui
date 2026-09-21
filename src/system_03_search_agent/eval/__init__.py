"""The offline evaluation harness (build phase 5.1).

Operationalizes `requirements/Evaluation_playbook.md` and technical
specification Section 23: the 50-query golden dataset, the 8-point rubric,
the three hard-fails, the pass@k and pass^k outcome model, the coverage
diagnostic and the cost report.

Depends on:
    - system_03_search_agent.feedback.rubric (the deterministic outcome
      model this package's `rubric_score` half completes)

Reads:
    - The versioned golden dataset file at `eval/golden/golden_dataset.json`

Writes:
    - Nothing. Every module here is pure: it consumes a run record and
      returns a score, never re-executing the agent loop (Section 23).

THE ONE INVARIANT THIS PACKAGE EXISTS TO HOLD: nothing here may re-run the
agent to find out what the right answer is. The dataset's expected values
are authored from live source records, never from agent output, and the
loader refuses a row that says otherwise.
"""

from __future__ import annotations
