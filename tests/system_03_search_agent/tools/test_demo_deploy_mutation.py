"""Mutation coverage for build phase 4.12's premise gate: can each arm FAIL?

## Why this file exists, in this phase specifically

The continuation prompt's instruction to build phase 4.12 is explicit:

    EVERY GATE ARM IT WRITES GETS A POPULATE-CHECK AND A MUTATION FROM THE
    FIRST LINE. Three phases running have now produced vacuous arms, and in
    this one the repair for a vacuous arm was itself vacuous. Copy the
    mutation harness pattern rather than trusting a read.

That instruction earned itself twice inside this phase before this file
existed, and both are recorded rather than quietly repaired, because they are
the argument for the harness:

- P4's populate-check knew only `skipif` and reported a false failure against
  `test_cypher_query_e2e.py`, which gates via `pytest.skip()` in a fixture. A
  populate-check narrower than its subject reports a problem that is not
  there, which is the same class of noise as a skip reason that is false.
- P6's parser split on the first `)`, so it truncated at
  `_model_is_configured(` the moment the condition became a compound
  expression, and reported a false failure against a correct fix.

Neither was found by reading. Both were found by running.

## The mutation this file must contain above all others

M7. Build phase 4.12 CAUSED a regression while fixing the thing P4 grades:
correcting the stale tunnel probe made it answer truthfully, and arms that had
been silently skipping began to RUN in the offline suite and FAIL against
conftest's block. `test_write_grounding_premise.py` went from a clean skip to
`6 failed, 4 passed, 2 skipped in 169.73s`.

An arm was added (P7) to pin the category. A mutation for that arm is what
proves P7 can actually notice, and without it P7 is a comment that happens to
be shaped like a test.

## How it runs

Entirely offline. No model call, no network, no graph. Mutations that need
altered file content write it to `tmp_path` and repoint the gate module's own
path constants, so the arm reads exactly what a mutated repository would hand
it, rather than being handed a pre-digested string.

## Coverage

Mutated: P1 (3), P2 (2), P3 (2), P4 (1), P5 (1), P6 (1), P7 (1), plus the
`graph_gate` helper's own two-facts contract (3). Fourteen mutations.

NOT mutated, and why:

- The parametrised arms P4, P5 and P7 are mutated once each rather than eight
  times. The assertion body is identical across the eight parameters and the
  file under test is the only thing that varies, so eight copies would grade
  the parametrisation rather than the assertion.
- Caddy's runtime behaviour is not mutated, because the gate does not assert
  it. Proving Caddy actually replaces the header needs a live proxy and a
  forged request, which is named in the gate's own coverage statement as out
  of scope rather than left to be assumed.
"""

import pathlib

import pytest

from tests.system_03_search_agent import graph_gate
from tests.system_03_search_agent.tools import test_demo_deploy_premise as gate

REAL_CADDYFILE = gate.CADDYFILE.read_text(encoding="utf-8")
REAL_DRIFT = gate.DRIFT_SCRIPT.read_text(encoding="utf-8")
REAL_APP = gate.SERVICE_APP.read_text(encoding="utf-8")


def _repoint(monkeypatch, tmp_path, attr, content):
    """Write `content` to a temp file and point the gate's constant at it."""
    target = tmp_path / attr.lower()
    target.write_text(content, encoding="utf-8")
    monkeypatch.setattr(gate, attr, target)
    return target


# ---------------------------------------------------------------------------
# M1: P1's control is the Caddyfile directive.
# ---------------------------------------------------------------------------


def test_m1a_p1_goes_red_when_the_directive_is_absent(monkeypatch, tmp_path):
    """The pre-fix state: no directive at all, so Caddy's default appends.

    This is the exact repository state F-4.11-RV-02 was filed against.
    """
    without = REAL_CADDYFILE.replace(
        "\t\theader_up X-Forwarded-For {remote_host}\n", ""
    )
    # Checks the DIRECTIVE is gone, not the substring: the explanatory comment
    # above it also contains "header_up", so a substring check would fail here
    # against a mutation that worked perfectly. It did, on the first run.
    import re as _re

    assert not _re.search(r"^\s*header_up\s+X-Forwarded-For", without, _re.MULTILINE), (
        "the mutation did not remove the directive"
    )
    _repoint(monkeypatch, tmp_path, "CADDYFILE", without)

    with pytest.raises(AssertionError):
        gate.test_p1_caddyfile_replaces_the_forwarded_for_header()


def test_m1b_p1_goes_red_when_the_directive_appends_instead_of_replacing(
    monkeypatch, tmp_path
):
    """`+X-Forwarded-For` APPENDS and reads almost identically.

    One character. An arm asserting only that the header is mentioned passes
    this completely, which is why P1 asserts the exact form.
    """
    appending = REAL_CADDYFILE.replace(
        "header_up X-Forwarded-For {remote_host}",
        "header_up +X-Forwarded-For {remote_host}",
    )
    assert "+X-Forwarded-For" in appending, "the mutation did not take"
    _repoint(monkeypatch, tmp_path, "CADDYFILE", appending)

    with pytest.raises(AssertionError):
        gate.test_p1_caddyfile_replaces_the_forwarded_for_header()


def test_m1c_p1_goes_red_when_the_value_is_derived_from_the_incoming_header(
    monkeypatch, tmp_path
):
    """A directive that sets the header from what the caller sent.

    It is present, it replaces rather than appends, and it preserves exactly
    the attacker-controlled value the fix exists to remove. Only the VALUE
    assertion catches it.
    """
    derived = REAL_CADDYFILE.replace(
        "header_up X-Forwarded-For {remote_host}",
        "header_up X-Forwarded-For {http.request.header.X-Forwarded-For}",
    )
    _repoint(monkeypatch, tmp_path, "CADDYFILE", derived)

    with pytest.raises(AssertionError):
        gate.test_p1_caddyfile_replaces_the_forwarded_for_header()


# ---------------------------------------------------------------------------
# M2: P2's control is that the FIRST layer survives.
# ---------------------------------------------------------------------------


def test_m2a_p2_goes_red_when_the_rightmost_rule_is_dropped(monkeypatch, tmp_path):
    """The trade this arm exists to prevent: add the proxy directive, then
    relax the service to trust the whole header because "the proxy sanitises
    it now". P1 still passes. The service is back to one layer, and the one
    it kept is the one that is not under this repository's control.
    """
    relaxed = REAL_APP.replace('rsplit(",", 1)[-1]', 'split(",", 1)[0]')
    assert 'rsplit(",", 1)[-1]' not in relaxed, "the mutation did not take"
    _repoint(monkeypatch, tmp_path, "SERVICE_APP", relaxed)

    with pytest.raises(AssertionError):
        gate.test_p2_the_service_still_reads_the_rightmost_element()


def test_m2b_p2_goes_red_when_the_trusted_peer_check_is_dropped(
    monkeypatch, tmp_path
):
    """Without it the header is honoured from any caller reaching the service
    directly, so the proxy directive protects nothing: a caller that bypasses
    the proxy sets its own value.
    """
    open_to_all = REAL_APP.replace("_TRUSTED_PROXY_HOSTS", "_ANY_HOST_AT_ALL")
    _repoint(monkeypatch, tmp_path, "SERVICE_APP", open_to_all)

    with pytest.raises(AssertionError):
        gate.test_p2_the_service_still_reads_the_rightmost_element()


# ---------------------------------------------------------------------------
# M3: P3's control is the drift pair.
# ---------------------------------------------------------------------------


def test_m3a_p3_goes_red_when_the_caddyfile_leaves_the_drift_check(
    monkeypatch, tmp_path
):
    """The pre-fix state: the security control is deployed and unwatched."""
    without = REAL_DRIFT.replace(
        '    "/etc/caddy/Caddyfile|services/graph_query_service/deploy/Caddyfile"\n',
        "",
    )
    # Same trap as M1a: the comment block explaining the pair also names the
    # path, so the check is that no PAIR line remains, not that the string is
    # absent from the file.
    assert not any(
        line.strip().startswith('"/etc/caddy/Caddyfile|')
        for line in without.splitlines()
    ), "the mutation did not remove the drift pair"
    _repoint(monkeypatch, tmp_path, "DRIFT_SCRIPT", without)

    with pytest.raises(AssertionError):
        gate.test_p3_the_drift_check_covers_the_caddyfile()


def test_m3b_p3_goes_red_when_the_pair_names_no_local_counterpart(
    monkeypatch, tmp_path
):
    """A remote path with nothing to compare it against.

    It satisfies a substring check for `/etc/caddy/Caddyfile` completely, and
    compares nothing. P3 asserts both halves for that reason.
    """
    half = REAL_DRIFT.replace(
        '"/etc/caddy/Caddyfile|services/graph_query_service/deploy/Caddyfile"',
        '"/etc/caddy/Caddyfile|"',
    )
    _repoint(monkeypatch, tmp_path, "DRIFT_SCRIPT", half)

    with pytest.raises(AssertionError):
        gate.test_p3_the_drift_check_covers_the_caddyfile()


# ---------------------------------------------------------------------------
# M4 to M6: the eight gates.
# ---------------------------------------------------------------------------


def _fake_repo(monkeypatch, tmp_path, relative_path, content):
    target = tmp_path / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    return target


SAMPLE = gate.STALE_TUNNEL_PROBE_FILES[0]


def test_m4_p4_goes_red_when_a_gate_socket_probes_the_tunnel_again(
    monkeypatch, tmp_path
):
    """Reinstate the exact probe build phase 4.11 orphaned."""
    reinstated = (
        "import os, socket\n"
        "import pytest\n"
        "def _graph_is_reachable() -> bool:\n"
        '    host = os.environ.get("GRAPH_PG_HOST")\n'
        '    port = os.environ.get("GRAPH_PG_PORT")\n'
        "    try:\n"
        "        with socket.create_connection((host, int(port)), timeout=3):\n"
        "            return True\n"
        "    except (OSError, ValueError):\n"
        "        return False\n"
        "gate = pytest.mark.skipif(not _graph_is_reachable(), reason='x')\n"
        "live_graph_arms_enabled = None\n"
    )
    _fake_repo(monkeypatch, tmp_path, SAMPLE, reinstated)

    with pytest.raises(AssertionError):
        gate.test_p4_no_gate_decides_liveness_by_probing_the_deleted_tunnel(SAMPLE)


def test_m5_p5_goes_red_when_a_skip_reason_names_the_tunnel_again(
    monkeypatch, tmp_path
):
    """The half a reader actually sees.

    Separated from P4 because a fix can correct the CONDITION and leave the
    MESSAGE, and this mutation is that fix: the probe is modern, the sentence
    still sends the reader to reopen something that does not exist.
    """
    modern_probe_stale_message = (
        "import pytest\n"
        "from tests.system_03_search_agent.graph_gate import live_graph_arms_enabled\n"
        "def _graph_is_reachable() -> bool:\n"
        "    return live_graph_arms_enabled()\n"
        "gate = pytest.mark.skipif(\n"
        "    not _graph_is_reachable(),\n"
        "    reason='needs the graph. Reopen the tunnel with: ssh -L 5455:localhost:5432 box',\n"
        ")\n"
    )
    _fake_repo(monkeypatch, tmp_path, SAMPLE, modern_probe_stale_message)

    # POPULATE-CHECK: P4 is satisfied by this file, so what follows is P5
    # failing on the message rather than P4 failing on the condition.
    gate.test_p4_no_gate_decides_liveness_by_probing_the_deleted_tunnel(SAMPLE)

    with pytest.raises(AssertionError):
        gate.test_p5_no_skip_reason_tells_the_reader_to_reopen_the_tunnel(SAMPLE)


def test_m6_p6_goes_red_when_live_only_gates_on_a_credential_alone(
    monkeypatch, tmp_path
):
    """Revert the fix that removed this repository's six-failure baseline."""
    reverted = (
        "import pytest\n"
        "live_only = pytest.mark.skipif(\n"
        "    not _model_is_configured(),\n"
        "    reason='needs a live network path to NCBI; no model key found in .env',\n"
        ")\n"
        "@live_only\n"
        "def test_x():\n"
        "    pass\n"
    )
    _fake_repo(
        monkeypatch,
        tmp_path,
        "tests/system_03_search_agent/synthesis/test_citation_trust_full_premise.py",
        reverted,
    )

    with pytest.raises(AssertionError):
        gate.test_p6_a_live_network_mark_requires_the_live_network_to_be_permitted()


def test_m7_p7_goes_red_when_a_gate_checks_reachability_without_permission(
    monkeypatch, tmp_path
):
    """THE MUTATION THIS FILE EXISTS FOR.

    This is the regression build phase 4.12 caused and then fixed: a gate
    with a truthful reachability probe and no permission check. Its arms RUN
    in the offline suite and FAIL against conftest's block instead of
    skipping, which is how one file went from a clean skip to `6 failed` in
    169 seconds.

    P4 passes on this file completely, because the probe is modern. P5 passes,
    because the message is clean. Only P7 notices, and this mutation is what
    proves P7 can.
    """
    reachable_but_unpermitted = (
        "import pytest\n"
        "from tests.system_03_search_agent.graph_gate import graph_is_reachable\n"
        "def _graph_is_reachable() -> bool:\n"
        "    return graph_is_reachable()\n"
        "gate = pytest.mark.skipif(not _graph_is_reachable(), reason='needs the graph')\n"
    )
    _fake_repo(monkeypatch, tmp_path, SAMPLE, reachable_but_unpermitted)

    # POPULATE-CHECKS: both weaker arms are entirely satisfied, which is the
    # whole point. A fix that only ran P4 and P5 would ship this.
    gate.test_p4_no_gate_decides_liveness_by_probing_the_deleted_tunnel(SAMPLE)
    gate.test_p5_no_skip_reason_tells_the_reader_to_reopen_the_tunnel(SAMPLE)

    with pytest.raises(AssertionError):
        gate.test_p7_a_graph_gate_requires_the_network_to_be_permitted_too(SAMPLE)


# ---------------------------------------------------------------------------
# M8: the helper's own two-facts contract.
# ---------------------------------------------------------------------------


def test_m8a_live_graph_arms_enabled_is_false_without_permission(monkeypatch):
    """Reachable but not permitted must be False.

    Asserted against the helper directly rather than through a gate, because
    this is the contract every one of the eight now depends on.
    """
    monkeypatch.setattr(graph_gate, "graph_is_reachable", lambda timeout=8.0: True)
    monkeypatch.setattr(graph_gate, "live_network_is_permitted", lambda: False)
    assert graph_gate.live_graph_arms_enabled() is False


def test_m8b_live_graph_arms_enabled_is_false_without_reachability(monkeypatch):
    """Permitted but unreachable must also be False."""
    monkeypatch.setattr(graph_gate, "graph_is_reachable", lambda timeout=8.0: False)
    monkeypatch.setattr(graph_gate, "live_network_is_permitted", lambda: True)
    assert graph_gate.live_graph_arms_enabled() is False


def test_m8c_the_two_facts_are_not_folded_into_the_reachability_probe():
    """`graph_is_reachable` must NOT answer the permission question.

    A function named "is it reachable" that returns False because this process
    lacks permission is a lie at the call site, and the next reader would have
    to discover it the way this one was discovered. Asserted on the source, so
    a later "simplification" that folds them together fails here rather than
    silently changing what eight gates mean.
    """
    source = pathlib.Path(graph_gate.__file__).read_text(encoding="utf-8")
    body = source.split("def graph_is_reachable(", 1)[1].split("\ndef ", 1)[0]
    assert "RUN_PREMISE_GATE" not in body, (
        "`graph_is_reachable` now consults RUN_PREMISE_GATE, so it answers "
        "'am I allowed' under a name that promises 'is it up'. Keep the two "
        "facts separate and compose them in `live_graph_arms_enabled`"
    )
    # And the composition really is a conjunction, not either-or.
    composed = source.split("def live_graph_arms_enabled(", 1)[1]
    assert "live_network_is_permitted() and graph_is_reachable" in composed, (
        "live_graph_arms_enabled no longer requires BOTH facts"
    )
