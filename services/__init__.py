"""Namespace package for services deployed separately from the agent itself.

`graph_query_service` (build phase 4.11) is the first member: it runs as a
systemd unit on the Hetzner box that hosts the AGE graph, not inside the
agent's own process or distribution. It is deliberately absent from
`pyproject.toml`'s `[tool.setuptools] packages` list for that reason; the
top-level `pythonpath = ["src", "."]` pytest setting is what lets this
package's tests run from the repository root without it being installed.

Depends on:
    - Nothing.

Reads:
    - Nothing.

Writes:
    - Nothing.
"""

from __future__ import annotations
