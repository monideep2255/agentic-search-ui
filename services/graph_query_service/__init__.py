"""The read-only HTTPS graph query service (build phase 4.11, T-4.11-02).

See `app.py` for the module docstring, which is the source of truth for the
wire encoding, the auth scheme, and the clamp-versus-reject boundary. See
`tracker/phase_4.11.md` for the phase's goal contract and Section 24 of
`requirements/Technical_specification.md` for the spec this implements.

Depends on:
    - Nothing.

Reads:
    - Nothing.

Writes:
    - Nothing.
"""

from __future__ import annotations
