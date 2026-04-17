"""download.py - Download PubMed baseline and update XML files from NCBI FTP.

Downloads all .xml.gz files from:
    ftp://ftp.ncbi.nlm.nih.gov/pubmed/baseline/
    ftp://ftp.ncbi.nlm.nih.gov/pubmed/updatefiles/  (if include_updates=True)

Baseline alone is ~1334 files; updatefiles adds more as the year progresses.
Downloads are idempotent via the shared ftp_client cache-hit check.

Parallelism: per DECISIONS.md (2026-04-16) and bossman_execution_plan.md
decision 19, downloads run in parallel via ThreadPoolExecutor with 8 workers
to cut serial-rate ~12 hr to ~1-2 hr. NCBI FTP allows ~10 connections per IP;
8 leaves headroom. On any per-file error, the worker logs and continues; the
function re-raises a RuntimeError after all futures complete if any failed,
so the caller can re-run (cached files skip on retry).

Depends on:
    - system-01-data-pipelines/shared/ftp_client.download_ftp_file
    - system-01-data-pipelines/shared/ftp_client.list_ftp_directory
    - system-01-data-pipelines/shared/config.PipelineConfig
    - stdlib: concurrent.futures.ThreadPoolExecutor

Reads:
    - ftp://ftp.ncbi.nlm.nih.gov/pubmed/baseline/ (remote)
    - ftp://ftp.ncbi.nlm.nih.gov/pubmed/updatefiles/ (remote, optional)

Writes:
    - config.ftp_cache_dir/pubmed/*.xml.gz
"""

import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import PipelineConfig
from shared.ftp_client import download_ftp_file, list_ftp_directory

logger = logging.getLogger(__name__)

FTP_HOST = "ftp.ncbi.nlm.nih.gov"
FTP_BASELINE_PATH = "/pubmed/baseline/"
FTP_UPDATES_PATH = "/pubmed/updatefiles/"
FTP_BASE_URL = "ftp://ftp.ncbi.nlm.nih.gov"

DEFAULT_DOWNLOAD_WORKERS = 8


def download_pubmed_files(
    config: PipelineConfig,
    force: bool = False,
    include_updates: bool = True,
    max_workers: int = DEFAULT_DOWNLOAD_WORKERS,
) -> list[Path]:
    """Download all PubMed XML files from NCBI FTP to the local cache.

    Lists the baseline/ directory (and optionally updatefiles/) on the NCBI FTP
    server, filters to .xml.gz files only, then downloads each file idempotently
    using the shared ftp_client. Cache hits are skipped unless force=True.

    Downloads run in parallel via a ThreadPoolExecutor (default 8 workers).
    Per-file errors are collected and a RuntimeError is raised at the end so
    the call site sees a single failure rather than one exception per worker.
    Re-running picks up cached files automatically and only retries the
    missing or failed files.

    Logs progress every 100 completed files plus a final summary.

    Args:
        config: Pipeline configuration with ftp_cache_dir set.
        force: If True, re-download all files even when cached.
        include_updates: If True, also list and download updatefiles/. Defaults
                         to True so the pipeline captures in-year article adds.
        max_workers: Number of parallel download threads. Defaults to 8.
                     Lower this if NCBI starts throttling (HTTP 429 / connection
                     resets); raise it carefully (NCBI allows ~10 concurrent
                     connections per IP).

    Returns:
        Sorted list of local Path objects for all downloaded .xml.gz files.

    Raises:
        ftplib.all_errors: If the FTP listing fails.
        RuntimeError: If one or more individual file downloads failed.
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

    def _download_one(item: tuple[str, str]) -> Path:
        ftp_dir, filename = item
        url = f"{FTP_BASE_URL}{ftp_dir}{filename}"
        dest = cache_dir / filename
        return download_ftp_file(url=url, dest=dest, force=force)

    local_paths: list[Path] = []
    errors: list[tuple[tuple[str, str], BaseException]] = []

    logger.info(
        "Starting parallel download of %d files with max_workers=%d",
        total,
        max_workers,
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_download_one, item): item for item in all_xml_files}
        for i, future in enumerate(as_completed(futures), start=1):
            item = futures[future]
            try:
                local_paths.append(future.result())
            except Exception as exc:
                logger.error(
                    "Failed to download %s%s: %s", item[0], item[1], exc
                )
                errors.append((item, exc))

            if i % 100 == 0 or i == total:
                logger.info(
                    "Completed %d of %d (%d ok, %d errors)",
                    i,
                    total,
                    len(local_paths),
                    len(errors),
                )

    if errors:
        first_item, first_exc = errors[0]
        raise RuntimeError(
            f"PubMed download failed for {len(errors)} of {total} files. "
            f"First failure: {first_item[0]}{first_item[1]} -> {first_exc!r}. "
            "Re-run pubmed-etl to retry only the failed files (cached files skip)."
        )

    logger.info(
        "PubMed FTP downloads complete: %d files in %s",
        len(local_paths),
        cache_dir,
    )
    return sorted(local_paths)
