"""F-8.6-V06: half of the completeness repair's revert (T-8.6-07) was
protected by no test. The RULE half, `_code_built_lines_will_cite` folding
a page's siblings by `source_url` in place of counting a view cited only
by its own citation id, turns 7 tests red on its own (see
`test_write_completeness.py`). The CALL-SITE half, `write_node` passing
`lists_every_finding=query.audience_depth == "researcher"` to that
function (`core/graph.py`, the completeness-repair trigger), was not
covered by anything: forcing `lists_every_finding=True` at every depth
still passed the whole core suite, `1210 passed, 56 skipped`.

It matters because a Plain language answer displays only the findings tail
(the omitted findings alone), never the full Researcher listing, so the
call site must probe the tail's own rendering when deciding whether the
repair still has a job. Probing the Researcher listing instead, on a
question where the two renderings disagree about what gets cited, brings
back an unneeded second writing call on a plain-language answer: the exact
regression this file pins.

`_code_built_lines_will_cite` itself already has full-coverage arms in
`test_write_completeness.py`, so this file does not attempt to reconstruct
a real finding set that makes the ORGANIC PubMed/graph rendering disagree
between the two listing modes (the verifier measured six such cases with
`probes/p14_listing_mode.py`, none committed). Instead it stubs
`_code_built_lines_will_cite` to answer according to the `lists_every_
finding` kwarg it actually receives, which is exactly what "the two modes
disagree" means for the CALL SITE'S purposes: whichever boolean the call
site passes decides whether the repair runs. That isolates the wiring
this ticket is about from the grounding internals another file already
covers.

MUTATION PROOF (also run by hand and reverted; see the builder's report):
forcing `lists_every_finding=True` in `write_node`'s call to
`_code_built_lines_will_cite`, regardless of `query.audience_depth`, turns
this red: the stub then answers as the Researcher listing would (`skip=
False`), the repair fires a second writing call, and `dispatched == [False]`
fails with `[False, True]`.
"""
from __future__ import annotations

import pytest

from system_03_search_agent.core import graph as graph_module
from tests.system_03_search_agent.core.test_write_completeness import (
    _record_synth_dispatches,
    _write_state,
    synth_pair,
)

__all__ = ["synth_pair"]


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same environment `test_write_completeness.py` sets for its own
    tests. Its `_env` fixture is function-scoped and autouse, so it does
    not reach across files; this file needs the same models and cost caps
    for the real `write_node` path it drives."""
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")


def _install_disagreeing_gate(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    """Stand in for a question where the Researcher listing and the
    findings tail disagree: the tail (omitted findings alone,
    `lists_every_finding=False`) already cites everything the repair would
    add, but the Researcher listing (`lists_every_finding=True`) does not.
    Records the `lists_every_finding` value the call site actually passed.
    """
    seen: list[bool] = []

    def _stub(
        omitted_findings: object,
        synth_findings: object,
        *,
        tool_outcome: str,
        model_grounded: bool,
        lists_every_finding: bool,
        question: str,
    ) -> bool:
        seen.append(lists_every_finding)
        if tool_outcome != "ok" or not model_grounded:
            return False
        # The disagreement itself: the tail already covers every omission,
        # the Researcher listing does not.
        return not lists_every_finding

    monkeypatch.setattr(graph_module, "_code_built_lines_will_cite", _stub)
    return seen


@pytest.mark.asyncio
async def test_plain_language_skips_the_repair_when_only_the_tail_disagrees(
    synth_pair, monkeypatch: pytest.MonkeyPatch
) -> None:
    """At Plain language, `query.audience_depth != "researcher"`, so the
    call site must pass `lists_every_finding=False`. On the disagreeing
    stub above that reads as the tail already citing every omission, so
    the repair is skipped and no second writing call is made.
    """
    synth_pair(first={1, 2}, repaired={1, 2, 3, 4, 5})
    seen = _install_disagreeing_gate(monkeypatch)
    dispatched = _record_synth_dispatches(monkeypatch)

    await graph_module.write_node(_write_state(audience_depth="plain_language"))

    assert seen == [False], seen
    assert dispatched == [False], dispatched


@pytest.mark.asyncio
async def test_researcher_depth_still_probes_the_full_listing(
    synth_pair, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other side of the same wiring: at Researcher depth the call site
    must pass `lists_every_finding=True`, which the disagreeing stub reads
    as the Researcher listing NOT citing every omission, so the repair
    still runs. This is the arm that would stay green under the V06
    regression on its own; paired with the Plain-language arm above, the
    pair is what actually pins the call site's own choice of boolean.
    """
    synth_pair(first={1, 2}, repaired={1, 2, 3, 4, 5})
    seen = _install_disagreeing_gate(monkeypatch)
    dispatched = _record_synth_dispatches(monkeypatch)

    await graph_module.write_node(_write_state(audience_depth="researcher"))

    assert seen == [True], seen
    assert dispatched == [False, True], dispatched
