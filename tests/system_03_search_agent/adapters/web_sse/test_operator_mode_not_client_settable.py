"""Ordinary unit test: `operator_mode` cannot be set from a request body.

Moved out of the deleted `test_phase_4_0_premise.py` (build phase 4.14
bossman redesign, 2026-09-24,
`docs/build/Bossman_redesign_deletion_inventory.md`). T-4.0-05
(`app.py`, around the SSE resume handler) requires that operator
visibility is derived once per request purely from the authenticated
caller's `OPERATOR_USER_IDS` allowlist membership, never from the request
body or headers. `CreateRunRequest` enforces the structural half of that:
it declares no `operator_mode` field, and `model_config = ConfigDict(extra=
"forbid")` means a client that sends one gets a 422, not a silently
accepted, silently ignored value.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from system_03_search_agent.adapters.web_sse.app import CreateRunRequest


def test_create_run_request_declares_no_operator_mode_field() -> None:
    assert "operator_mode" not in CreateRunRequest.model_fields


def test_a_client_sending_operator_mode_is_rejected_outright() -> None:
    with pytest.raises(ValidationError):
        CreateRunRequest(
            text="What gene is BRCA1?",
            session_id="s-1",
            operator_mode=True,
        )
