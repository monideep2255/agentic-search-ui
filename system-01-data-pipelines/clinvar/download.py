"""download.py - Download ClinVar FTP files to ftp_cache_dir.

Downloads variant_summary.txt.gz and var_citations.txt from the NCBI ClinVar
FTP server. Downloads are idempotent: a cached file is reused unless force=True.

Depends on:
    - system-01-data-pipelines/shared/config.py
    - system-01-data-pipelines/shared/ftp_client.py

Reads:
    - ftp://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz
    - ftp://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/var_citations.txt

Writes:
    - config.ftp_cache_dir/variant_summary.txt.gz
    - config.ftp_cache_dir/var_citations.txt
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.config import PipelineConfig
from shared.ftp_client import download_ftp_file

logger = logging.getLogger(__name__)

CLINVAR_FTP_FILES: dict[str, str] = {
    "variant_summary": (
        "ftp://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"
    ),
    "var_citations": (
        "ftp://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/var_citations.txt"
    ),
}

_LOCAL_NAMES: dict[str, str] = {
    "variant_summary": "variant_summary.txt.gz",
    "var_citations": "var_citations.txt",
}


def download_clinvar_files(
    config: PipelineConfig,
    force: bool = False,
) -> dict[str, Path]:
    """Download ClinVar FTP files to ftp_cache_dir.

    Files downloaded:
        - variant_summary: variant_summary.txt.gz (~500 MB uncompressed)
        - var_citations:   var_citations.txt (plain text, smaller)

    Each download is skipped if the local file already exists and force=False.
    Uses an atomic write pattern (download to .tmp then rename) to prevent
    partial downloads from being read by the parser.

    Args:
        config: Pipeline configuration. Uses config.ftp_cache_dir as the
                destination directory.
        force:  If True, re-download even when a cached copy exists.

    Returns:
        Dict mapping file key ("variant_summary", "var_citations") to the
        local Path of the downloaded file.

    Raises:
        urllib.error.URLError: If a remote URL is unreachable.
        OSError: If ftp_cache_dir is not writable.
    """
    logger.info("Starting ClinVar FTP downloads (force=%s)", force)
    paths: dict[str, Path] = {}

    for key, url in CLINVAR_FTP_FILES.items():
        dest = config.ftp_cache_dir / _LOCAL_NAMES[key]
        local_path = download_ftp_file(url, dest, force=force)
        paths[key] = local_path
        logger.info("Ready: %s -> %s", key, local_path)

    logger.info("ClinVar downloads complete. Files: %s", list(paths.values()))
    return paths
