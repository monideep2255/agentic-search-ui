"""Premise gate for build phase 4.12's code-side deliverables.

Two things this phase inherits, both filed by earlier phases with an owner,
plus one gap found while scouting them.

## 1. The Caddyfile does not overwrite `X-Forwarded-For` (from build phase 4.11)

`services/graph_query_service/app.py`'s `_client_address` reads the RIGHTMOST
element of `X-Forwarded-For`, and only when the immediate peer is the local
proxy. That rule is correct and arm P20 of build phase 4.11's own gate pins it.

What is missing is the second layer. Caddy's `reverse_proxy` APPENDS to
`X-Forwarded-For` by default, so a caller that sends its own value produces
`forged, real` and the header carries attacker-controlled text at all. The
rightmost rule is what makes that safe, and it is currently the ONLY thing
that does.

Finding F-4.11-RV-02 is the reason this arm exists and the reason it is
written this way. `_client_address`'s docstring used to CLAIM the deployed
Caddyfile "additionally OVERWRITES the header with the real remote host rather
than appending to it, so both layers are safe independently". A re-verifier
read the deployed `/etc/caddy/Caddyfile` and found no such directive. The
claim was false, it was the third false comment that phase produced, and the
docstring now ends with an explicit instruction to whoever fixes it:

    Do not restore the two-layer claim without first adding the directive to
    the Caddyfile AND an arm that reads it.

P1 and P2 are that arm. They read the Caddyfile itself rather than trusting
any comment about it, which is the whole point: a comment asserting a security
property is a claim to be tested, per `.claude/rules/self-eval-loop.md`.

## 2. The Caddyfile is invisible to the drift check (found while scouting)

`check_drift.sh` proves the deployed copies are byte-identical to this
repository's, which is what makes Section 24's server-side re-validation real
rather than nominal. It checks FIVE files. The Caddyfile is not one of them,
while the Caddyfile's own header comment says:

    Never hand-edited on the box: a hand-edit is invisible to this repository
    and survives until it causes an outage nobody can explain.

The one file that warns about invisible hand-edits is the one file the drift
check cannot see, so the warning is unenforceable exactly where it is written.
That matters more after this phase than before it, because the directive P1
adds is a SECURITY control: someone removing it on the box to debug a proxy
problem would silently return the service to one safeguard, and nothing would
report it. P3 closes that.

## 3. Eight premise gates still probe the deleted SSH tunnel

Build phase 4.11 deleted the tunnel and moved Layer 1 behind
`GRAPH_QUERY_URL`. Eight test files still decide whether to run their live
arms by opening a TCP socket to `GRAPH_PG_HOST`/`GRAPH_PG_PORT`, the tunnel's
local port. On a machine where the graph is perfectly reachable over HTTPS,
those arms skip, and they print a skip reason that is FALSE, some of them
literally telling the reader to reopen a tunnel that no longer exists.

The continuation prompt records this as seven files. Measured here, it is
EIGHT, and the figure is corrected rather than inherited, which is the same
discipline this repository applies to a carried-forward test baseline.

P4 and P5 pin it.

## 4. A skip condition that does not match what the arm needs

Found while measuring item 3, and it is the whole of this repository's
standing six-failure baseline.

`test_citation_trust_full_premise.py` carries two marks. `premise_gate`
requires the tunnel, so it always skips now. `live_only` requires ONLY a model
key. A model key says nothing about whether `tests/conftest.py` is permitting
outbound HTTP, so six arms marked `live_only` RUN in the ordinary offline
suite, hit the block, and fail with `LiveHttpCallInUnitSuiteError`.

Verified 2026-08-24: that file is `8 passed, 2 skipped` under
`RUN_PREMISE_GATE=1`. Nothing in it is broken. It FAILS where it should SKIP,
which is item 3's defect in the other direction, and it has trained every
reader of this suite to expect six red results. A permanent red baseline is
precisely where a real regression goes unnoticed.

P6 pins the rule: a mark that gates a live-network arm must require the live
network to be permitted, not merely a credential to exist.

## What this gate does NOT cover

- It does not verify the DEPLOYED Caddyfile on the Hetzner box. It reads this
  repository's copy, which is what `deploy.sh` installs. Proving the box
  matches is `check_drift.sh`'s job, and P3 is what puts the Caddyfile inside
  its reach; running it needs `ssh`, which this harness blocks (build phase
  4.11 had three non-destructive `ssh` commands refused).
- It does not test Caddy's runtime behaviour. Asserting that Caddy actually
  replaces the header would need a live proxy and a forged request against it.
  What is asserted is that the directive is present and correctly formed.
- It does not cover Railway provisioning, which is the product owner's, nor
  anything that creates a public URL, which is gated on the security scan.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CADDYFILE = REPO_ROOT / "services/graph_query_service/deploy/Caddyfile"
DRIFT_SCRIPT = REPO_ROOT / "services/graph_query_service/deploy/check_drift.sh"
DEPLOY_SCRIPT = REPO_ROOT / "services/graph_query_service/deploy/deploy.sh"
SERVICE_APP = REPO_ROOT / "services/graph_query_service/app.py"

#: The eight files that gate live arms on a TCP probe of the deleted tunnel's
#: port. Enumerated rather than globbed so a NEW file committing the same
#: mistake fails P5 loudly instead of being silently absorbed by a pattern.
STALE_TUNNEL_PROBE_FILES = (
    "tests/system_03_search_agent/tools/test_cypher_query_premise.py",
    "tests/system_03_search_agent/tools/test_cypher_query_e2e.py",
    "tests/system_03_search_agent/tools/test_ncbi_efetch_premise.py",
    "tests/system_03_search_agent/core/test_write_grounding_premise.py",
    "tests/system_03_search_agent/core/test_feedback_capture_premise.py",
    "tests/system_03_search_agent/core/test_personalization_premise.py",
    "tests/system_03_search_agent/synthesis/test_citation_trust_full_premise.py",
    "tests/system_03_search_agent/export/test_kgx_export_premise.py",
)


# ---------------------------------------------------------------------------
# P1 and P2: the Caddyfile directive.
# ---------------------------------------------------------------------------


def test_p1_caddyfile_replaces_the_forwarded_for_header():
    """The directive exists, inside the reverse_proxy block, and REPLACES.

    `header_up` with a bare value replaces; Caddy's default with no directive
    at all appends. The distinction is the entire finding, so the assertion is
    on the form of the directive rather than on the substring
    `X-Forwarded-For` appearing somewhere in the file.
    """
    text = CADDYFILE.read_text(encoding="utf-8")

    # POPULATE-CHECK: this is the Caddyfile this phase means, and it still has
    # the proxy block the directive has to live inside. Without this, an empty
    # or renamed file would make every assertion below vacuous.
    assert "reverse_proxy 127.0.0.1:8080" in text, (
        "the reverse_proxy line is gone, so this is not the file the "
        "directive belongs in and the assertions below grade nothing"
    )

    directive = re.search(
        r"^\s*header_up\s+X-Forwarded-For\s+(\S+)\s*$", text, re.MULTILINE | re.IGNORECASE
    )
    assert directive is not None, (
        "no `header_up X-Forwarded-For` directive. Caddy's default APPENDS, "
        "so a caller can put attacker-controlled text in the header and the "
        "rightmost-element rule in app.py is the single safeguard rather "
        "than one of two (F-4.11-RV-02)"
    )

    value = directive.group(1)
    assert value == "{remote_host}", (
        f"the directive sets {value!r}. It must be `{{remote_host}}`, the "
        "immediate peer address Caddy itself observed. Anything derived from "
        "the incoming header would preserve exactly what this fix removes"
    )

    # A `+X-Forwarded-For` form APPENDS rather than replaces, and reads almost
    # identically. Caught here rather than by a reader noticing a plus sign.
    assert not re.search(r"header_up\s+\+X-Forwarded-For", text, re.IGNORECASE), (
        "`header_up +X-Forwarded-For` APPENDS. Drop the leading plus"
    )


def test_p2_the_service_still_reads_the_rightmost_element():
    """The Caddyfile directive is the SECOND layer, never a replacement for
    the first.

    A future edit that added the directive and then relaxed `app.py` to trust
    the whole header, on the grounds that the proxy now sanitises it, would
    pass P1 and reintroduce the finding through the front door. Both layers
    are asserted together, in one arm, so neither can be traded for the other.
    """
    text = SERVICE_APP.read_text(encoding="utf-8")

    assert "_TRUSTED_PROXY_HOSTS" in text, (
        "the trusted-peer check is gone; the header would be honoured from "
        "any caller reaching the service directly"
    )
    assert 'rsplit(",", 1)[-1]' in text, (
        "the rightmost-element rule is gone from `_client_address`. The "
        "Caddyfile directive is defence in depth, not a licence to trust the "
        "whole header"
    )


# ---------------------------------------------------------------------------
# P3: the Caddyfile is inside the drift check's reach.
# ---------------------------------------------------------------------------


def test_p3_the_drift_check_covers_the_caddyfile():
    """The file that warns about invisible hand-edits must not be the one
    file the drift check cannot see.

    This matters more now than before this phase: the directive P1 adds is a
    security control, and someone removing it on the box while debugging a
    proxy problem would silently return the service to a single safeguard
    with nothing reporting it.
    """
    drift = DRIFT_SCRIPT.read_text(encoding="utf-8")
    deploy = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    # POPULATE-CHECK: `deploy.sh` really does install this file to that path,
    # so the pair P3 demands is a real pair and not one invented here.
    assert "/etc/caddy/Caddyfile" in deploy, (
        "deploy.sh no longer installs the Caddyfile to /etc/caddy/Caddyfile, "
        "so the drift pair this arm requires would point at nothing"
    )

    assert "PAIRS=(" in drift, (
        "check_drift.sh no longer declares a PAIRS list; this arm is reading "
        "a script it no longer understands"
    )
    assert "/etc/caddy/Caddyfile" in drift, (
        "check_drift.sh does not verify the deployed Caddyfile. A hand-edit "
        "on the box, including removing the X-Forwarded-For directive, is "
        "invisible to this repository, which is exactly what that file's own "
        "header comment says must never be true of it"
    )
    assert "services/graph_query_service/deploy/Caddyfile" in drift, (
        "the drift pair names no local counterpart, so nothing is compared"
    )


# ---------------------------------------------------------------------------
# P4 and P5: the stale tunnel probes.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "relative_path",
    STALE_TUNNEL_PROBE_FILES,
    ids=[Path(p).stem for p in STALE_TUNNEL_PROBE_FILES],
)
def test_p4_no_gate_decides_liveness_by_probing_the_deleted_tunnel(relative_path):
    """No live arm is gated on a TCP socket to the tunnel's local port.

    Build phase 4.11 deleted that tunnel. A probe of its port now reports the
    graph unreachable on a machine where it is perfectly reachable over
    HTTPS, so the arm skips and prints a reason that is false.

    The `GRAPH_PG_*` variables are NOT banned outright by this arm, and the
    distinction is deliberate: `graph_connection.py` still dispatches on
    whether `GRAPH_QUERY_URL` is set and falls back to the direct connection,
    so a test may legitimately reference those names. What it may not do is
    decide whether the graph is REACHABLE by opening a socket to them.
    """
    path = REPO_ROOT / relative_path

    # POPULATE-CHECK: the file exists and still gates something. An arm
    # asserting "no socket probe" passes trivially against a deleted file.
    assert path.exists(), f"{relative_path} no longer exists; re-pin this arm"
    text = path.read_text(encoding="utf-8")
    # Both skip mechanisms, because these eight files use both and an arm that
    # knew only `skipif` failed on `test_cypher_query_e2e.py`, which gates via
    # `pytest.skip()` inside a fixture. That was a defect in THIS arm, not in
    # the file it graded: a populate-check narrower than the thing it is
    # checking for reports a false problem, which is the same class of noise
    # as a skip reason that is false.
    assert "skipif" in text or "pytest.skip(" in text, (
        f"{relative_path} no longer skips anything, so this arm is not "
        "grading a live-arm gate"
    )

    probe = re.search(
        r"create_connection\(\s*\(\s*[^)]*GRAPH_PG|"
        r"create_connection\(\s*\(\s*host\s*,\s*int\(\s*port",
        text,
    )
    assert probe is None, (
        f"{relative_path} still decides liveness by opening a socket to the "
        "deleted SSH tunnel's port. Gate on RUN_PREMISE_GATE, or probe "
        "GRAPH_QUERY_URL's health endpoint, as the post-4.11 gates do"
    )


@pytest.mark.parametrize(
    "relative_path",
    STALE_TUNNEL_PROBE_FILES,
    ids=[Path(p).stem for p in STALE_TUNNEL_PROBE_FILES],
)
def test_p5_no_skip_reason_tells_the_reader_to_reopen_the_tunnel(relative_path):
    """A skip reason that names a deleted tunnel is worse than no reason.

    It sends the next reader to reopen something that does not exist, and it
    makes a green run read as "this class is covered" when the arms did not
    run at all. Separated from P4 because a fix could correct the CONDITION
    and leave the message, which is the half a reader actually sees.
    """
    text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    stale = re.search(r"[Rr]eopen the tunnel|ssh -L|tunnel is a manual", text)
    assert stale is None, (
        f"{relative_path} still tells the reader to reopen the SSH tunnel "
        f"build phase 4.11 deleted (matched {stale.group(0)!r} if shown)"
    )


# ---------------------------------------------------------------------------
# P6: a live-network gate must require the live network.
# ---------------------------------------------------------------------------


def test_p6_a_live_network_mark_requires_the_live_network_to_be_permitted():
    """The whole of this repository's standing six-failure baseline.

    `live_only` in `test_citation_trust_full_premise.py` requires only that a
    model key exists. A model key says nothing about whether
    `tests/conftest.py` is permitting outbound HTTP, so six arms run in the
    ordinary offline suite and FAIL rather than skip.

    Verified 2026-08-24: that file is `8 passed, 2 skipped` under
    `RUN_PREMISE_GATE=1`. Nothing in it is broken. It fails where it should
    skip, and it has trained every reader of this suite to expect six red
    results, which is precisely where a real regression would go unnoticed.
    """
    path = REPO_ROOT / (
        "tests/system_03_search_agent/synthesis/test_citation_trust_full_premise.py"
    )
    text = path.read_text(encoding="utf-8")

    # POPULATE-CHECK: the mark still exists and is still applied, so this arm
    # is grading a live gate rather than a name that no longer means anything.
    assert "live_only = pytest.mark.skipif(" in text, (
        "the `live_only` mark is gone; re-pin this arm to whatever replaced it"
    )
    assert "@live_only" in text, "`live_only` is defined but never applied"

    # Read to the MATCHING close paren, not the first one. Splitting on the
    # first `)` truncated at `_model_is_configured(` the moment the condition
    # became a compound expression, so the arm reported a false failure
    # against a correct fix. A parser narrower than the thing it parses is
    # the same class of defect as a populate-check narrower than its subject.
    tail = text.split("live_only = pytest.mark.skipif(", 1)[1]
    depth, definition = 1, ""
    for char in tail:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                break
        definition += char
    assert "RUN_PREMISE_GATE" in definition or "_live_network_is_permitted" in definition, (
        "`live_only` gates on a model key alone. A credential existing is not "
        "the same fact as outbound HTTP being permitted, and the arms it "
        "marks reach live NCBI, PubTator, LitVar2 and ClinicalTrials.gov. "
        f"Definition read: {definition.strip()!r}"
    )


# ---------------------------------------------------------------------------
# P7: the regression this phase caused, and the reason P6's rule is general.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "relative_path",
    STALE_TUNNEL_PROBE_FILES,
    ids=[Path(p).stem for p in STALE_TUNNEL_PROBE_FILES],
)
def test_p7_a_graph_gate_requires_the_network_to_be_permitted_too(relative_path):
    """Both facts, in every one of the eight, not just the one P6 names.

    THIS ARM EXISTS BECAUSE THIS PHASE CAUSED THE DEFECT IT CATCHES, and that
    is recorded rather than quietly fixed.

    Correcting the stale tunnel probe (P4) made `_graph_is_reachable` answer
    truthfully for the first time since build phase 4.11. Measured
    immediately afterwards: arms that had been silently skipping began to RUN
    in the ordinary offline suite, hit `tests/conftest.py`'s block, and
    FAILED. `test_write_grounding_premise.py` alone went from a clean skip to
    `6 failed, 4 passed, 2 skipped in 169.73s`.

    That is precisely the defect P6 was written for, reproduced in seven more
    files by the fix for a different one. P6 pinned the instance; this arm
    pins the CATEGORY, which is the difference between fixing the order and
    fixing the scheduler.

    The rule: "the dependency answers" and "this process may talk to it" are
    two separate facts. A gate needs both, and neither is a proxy for the
    other.
    """
    text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    # POPULATE-CHECK: this file really does gate on graph reachability, so the
    # assertion below is about a gate that exists rather than a name absent
    # for an unrelated reason.
    assert "_graph_is_reachable" in text or "_graph_reachable" in text, (
        f"{relative_path} no longer has a graph-reachability gate; re-pin "
        "this arm or drop the file from STALE_TUNNEL_PROBE_FILES"
    )

    assert "live_graph_arms_enabled" in text or "live_network_is_permitted" in text, (
        f"{relative_path} decides whether to run a live graph arm without "
        "requiring that outbound HTTP is permitted. With a truthful "
        "reachability probe, its arms will RUN in the offline suite and FAIL "
        "against conftest's block rather than skipping. Use "
        "`graph_gate.live_graph_arms_enabled`, which requires both facts"
    )
