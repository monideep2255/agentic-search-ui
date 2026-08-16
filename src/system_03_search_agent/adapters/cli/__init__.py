"""CLI adapter: the ``s3`` terminal client (build phase 4.2, tracker/phase_4.2.md).

A thin client over the REST plus SSE API build phase 4.0 finalized. It
constructs no ``Query``, calls no ``run()``, and holds no agent logic of
its own; every module in this package speaks HTTP and SSE to that surface
and renders the event stream for a terminal.

This file is a package marker only. It does not re-export the sibling
modules (``credentials.py``, ``sse.py``, ``client.py``, ``render.py``,
``main.py``), since those are built independently in parallel this phase
and an import here would create an import cycle and a merge conflict.

Depends on:
    - None. This module has no runtime dependencies of its own.

Reads:
    - Nothing at import time.

Writes:
    - Nothing.
"""
