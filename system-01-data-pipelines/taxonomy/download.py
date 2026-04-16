"""download.py - Download and extract the NCBI taxdump archive.

Downloads taxdump.tar.gz from the NCBI FTP server, then extracts nodes.dmp
and names.dmp into a local cache directory. The extraction is idempotent:
if both .dmp files already exist the tarball is not re-extracted.

Depends on:
    - system-01-data-pipelines/shared/config.py
    - system-01-data-pipelines/shared/ftp_client.py

Reads:
    - ftp://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz

Writes:
    - config.ftp_cache_dir/taxonomy/taxdump.tar.gz
    - config.ftp_cache_dir/taxonomy/nodes.dmp
    - config.ftp_cache_dir/taxonomy/names.dmp
    - (plus any other .dmp files present in the tarball)
"""

import logging
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.config import PipelineConfig
from shared.ftp_client import download_ftp_file

logger = logging.getLogger(__name__)

TAXONOMY_FTP_URL: str = (
    "ftp://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz"
)
_TARBALL_NAME: str = "taxdump.tar.gz"
_REQUIRED_DMP_FILES: tuple[str, ...] = ("nodes.dmp", "names.dmp")


def download_taxonomy_files(
    config: PipelineConfig,
    force: bool = False,
) -> Path:
    """Download taxdump.tar.gz and extract nodes.dmp and names.dmp.

    The tarball is downloaded to config.ftp_cache_dir/taxonomy/ and extracted
    in the same directory. Extraction is skipped when both nodes.dmp and
    names.dmp already exist and force=False.

    Args:
        config: Pipeline configuration. Uses config.ftp_cache_dir as the
                root cache location. A "taxonomy" subdirectory is created
                automatically.
        force:  If True, re-download and re-extract even when cached files
                already exist.

    Returns:
        Path to the directory containing the extracted .dmp files
        (config.ftp_cache_dir/taxonomy/).

    Raises:
        urllib.error.URLError: If the remote FTP server is unreachable.
        tarfile.TarError: If the downloaded archive is corrupt or cannot
                          be extracted.
        OSError: If the cache directory is not writable.
    """
    taxonomy_dir = config.ftp_cache_dir / "taxonomy"
    taxonomy_dir.mkdir(parents=True, exist_ok=True)

    tarball_path = taxonomy_dir / _TARBALL_NAME

    # Download (cache-aware)
    download_ftp_file(TAXONOMY_FTP_URL, tarball_path, force=force)

    # Check whether extraction can be skipped
    required_paths = [taxonomy_dir / name for name in _REQUIRED_DMP_FILES]
    already_extracted = all(p.exists() for p in required_paths)

    if already_extracted and not force:
        logger.info(
            "Extraction skipped: %s already present in %s",
            ", ".join(_REQUIRED_DMP_FILES),
            taxonomy_dir,
        )
        return taxonomy_dir

    logger.info("Extracting %s into %s", _TARBALL_NAME, taxonomy_dir)
    with tarfile.open(tarball_path, "r:gz") as tf:
        # Guard against path traversal: reject any member with absolute paths
        # or .. components. Python <3.12 does not support the filter= kwarg.
        safe_members = [
            m for m in tf.getmembers()
            if not (m.name.startswith("/") or ".." in m.name.split("/"))
        ]
        rejected = len(tf.getmembers()) - len(safe_members)
        if rejected:
            logger.warning("Rejected %d unsafe tarball members during extraction", rejected)
        tf.extractall(path=taxonomy_dir, members=safe_members)

    extracted = [p.name for p in taxonomy_dir.iterdir() if p.suffix == ".dmp"]
    logger.info(
        "Extracted %d .dmp files into %s: %s",
        len(extracted),
        taxonomy_dir,
        sorted(extracted),
    )

    for required_path in required_paths:
        if not required_path.exists():
            raise FileNotFoundError(
                f"Required file not found after extraction: {required_path}. "
                "The taxdump.tar.gz archive may be corrupt or its contents "
                "have changed."
            )

    return taxonomy_dir
