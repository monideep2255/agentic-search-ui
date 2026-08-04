"""The Section 10 guardrail: admission control for the agent loop.

The only step every query passes through before any Think, Plan, or Act work
happens. Its job is to decide whether a query is allowed in at all.

Module map, one per Section 10 subsection:

    verdict.py     The shared result type every screen returns.
    prefilter.py   Section 10.2, the cheap non-LLM pre-filter. No model call.
    classifier.py  Section 10.4, Guard-tier injection classification.
    forbidden.py   Section 10.5, forbidden query types and read-only.

Section 10.3 (Pydantic boundary validation) has no module here: it is enforced
by `contracts/query.py` at the FastAPI boundary, before any code in this
package runs. Section 10.6 (rate and cost pre-checks) likewise lives in
`harness/cost_control.py`, which predates this package.

The load-bearing asymmetry, stated once here because every module in this
package inherits it: a guardrail has no safe direction of failure. Letting a
hostile query through is a security hole, and refusing a legitimate one is a
product-killing defect that no security test can see. `return False` scores
perfectly against every attack in the suite. Whenever a check here is
tightened, the question to ask is which legitimate question is now one token
away from being refused.

Section 11 covers the companion problem, defending the loop against untrusted
content retrieved AFTER admission. This package never sees that content:
Section 10.4 is explicit that "Guardrail only ever sees the user's own input."
"""

from system_03_search_agent.guardrail.verdict import (
    GuardCategory,
    GuardVerdict,
    admitted,
    refused,
)

__all__ = ["GuardCategory", "GuardVerdict", "admitted", "refused"]
