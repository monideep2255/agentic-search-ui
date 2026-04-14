"""conftest.py for tests/shared - adds system-01-data-pipelines to sys.path.

The shared modules live in system-01-data-pipelines/shared/. The hyphenated
directory name cannot be imported as a Python package directly. This conftest
inserts the directory so tests can do:

    from shared.config import PipelineConfig
"""

import sys
from pathlib import Path

PIPELINES_DIR = Path(__file__).resolve().parent.parent.parent / "system-01-data-pipelines"
if str(PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINES_DIR))
