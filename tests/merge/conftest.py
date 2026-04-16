"""conftest.py for tests/merge - adds system-01-data-pipelines to sys.path.

Mirrors tests/integration/conftest.py so tests can do:

    from shared.merger import merge_kgx
    from merge.pipeline import run_five_database_merge
"""

import sys
from pathlib import Path

PIPELINES_DIR = Path(__file__).resolve().parent.parent.parent / "system-01-data-pipelines"
if str(PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINES_DIR))
