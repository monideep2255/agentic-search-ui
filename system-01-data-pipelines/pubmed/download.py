"""download.py - Download PubMed baseline and update XML files from NCBI FTP.

Downloads all .xml.gz files from:
    ftp://ftp.ncbi.nlm.nih.gov/pubmed/baseline/
    ftp://ftp.ncbi.nlm.nih.gov/pubmed/updatefiles/  (if include_updates=True)

Baseline alone is ~1334 files; updatefiles adds more as the year progresses.
Downloads are idempotent via the shared ftp_client cache-hit check.

Depends on:
    - system-01-data-pipelines/shared/ftp_client.download_ftp_file
    - system-01-data-pipelines/shared/ftp_client.list_ftp_directory
    - system-01-data-pipelines/shared/config.PipelineConfig

Reads:
    - ftp://ftp.ncbi.nlm.nih.gov/pubmed/baseline/ (remote)
    - ftp://ftp.ncbi.nlm.nih.gov/pubmed/updatefiles/ (remote, optional)

Writes:
    - config.ftp_cache_dir/pubmed/*.xml.gz
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import PipelineConfig
from shared.ftp_client import download_ftp_file, list_ftp_directory

logger = logging.getLogger(__name__)

FTP_HOST = "ftp.ncbi.nlm.nih.gov"
FTP_BASELINE_PATH = "/pubmed/baseline/"
FTP_UPDATES_PATH = "/pubmed/updatefiles/"
FTP_BASE_URL = "ftp://ftp.ncbi.nlm.nih.gov"


def download_pubmed_files(
    config: PipelineConfig,
    force: bool = False,
    include_updates: bool = True,
) -> list[Path]:
    """Download all PubMed XML files from NCBI FTP to the local cache.

    Lists the baseline/ directory (and optionally updatefiles/) on the NCBI FTP
    server, filters to .xml.gz files only, then downloads each file idempotently
    using the shared ftp_client. Cache hits are skipped unless force=True.

    Logs progress every 100 files to avoid silent long runs over 1334+ files.

    Args:
        config: Pipeline configuration with ftp_cache_dir set.
        force: If True, re-download all files even when cached.
        include_updates: If True, also list and download updatefiles/. Defaults
                         to True so the pipeline captures in-year article adds.

    Returns:
        Sorted list of local Path objects for all downloaded .xml.gz files.

    Raises:
        ftplib.all_errors: If the FTP listing fails.
        urllib.error.URLError: If any download fails.
        OSError: If the cache directory is not writable.
    """
    cache_dir = config.ftp_cache_dir / "pubmed"
    cache_dir.mkdir(parents=True, exist_ok=True)

    directories_to_fetch = [FTP_BASELINE_PATH]
    if include_updates:
        directories_to_fetch.append(FTP_UPDATES_PATH)

    all_xml_files: list[tuple[str, str]] = []  # (ftp_path, filename)

    for ftp_dir in directories_to_fetch:
        logger.info("Listing FTP directory: ftp://%s%s", FTP_HOST, ftp_dir)
        try:
            filenames = list_ftp_directory(FTP_HOST, ftp_dir)
        except Exception as exc:
            logger.error("Failed to list %s: %s", ftp_dir, exc)
            raise

        xml_files = [f for f in filenames if f.endswith(".xml.gz")]
        logger.info(
            "Found %d .xml.gz files in ftp://%s%s",
            len(xml_files),
            FTP_HOST,
            ftp_dir,
        )
        for filename in xml_files:
            all_xml_files.append((ftp_dir, filename))

    total = len(all_xml_files)
    local_paths: list[Path] = []

    for i, (ftp_dir, filename) in enumerate(all_xml_files, start=1):
        url = f"{FTP_BASE_URL}{ftp_dir}{filename}"
        dest = cache_dir / filename
        local_path = download_ftp_file(url=url, dest=dest, force=force)
        local_paths.append(local_path)

        if i % 100 == 0:
            logger.info("Downloaded %d of %d files", i, total)

    logger.info(
        "PubMed FTP downloads complete: %d files in %s",
        len(local_paths),
        cache_dir,
    )
    return sorted(local_paths)
