"""
ftp_client.py - Idempotent FTP/HTTP download with cache-hit check and directory listing.

Adapted from:
    reference/ncbi_ai_agents-ncbi-kg/KG/pipeline/src/glucose_metabolism_kg/utils.py
    lines 91-104 (download_file pattern)

Key behaviors:
- download_ftp_file: skips download if dest exists and force=False (cache-hit)
- Writes to a .tmp file first, then atomic rename to avoid corrupt partial files
- list_ftp_directory: connects via ftplib, returns bare filenames for path verification

Depends on:
    - stdlib only: urllib.request, ftplib, logging, pathlib

Reads:
    - Remote FTP/HTTP URLs (NCBI bulk file servers)

Writes:
    - dest path (caller-supplied, typically under ftp_cache_dir)
    - dest.with_suffix(dest.suffix + ".tmp") during download (cleaned up on rename)
"""

import ftplib
import logging
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)


def download_ftp_file(url: str, dest: Path, force: bool = False) -> Path:
    """Download a file from url to dest, skipping if already cached.

    Uses an atomic write pattern: downloads to dest + ".tmp" then renames to dest.
    This prevents callers from reading a partially downloaded file if the process
    is interrupted mid-download.

    Args:
        url:   Full URL to the remote file (ftp:// or https:// both work with
               urllib.request).
        dest:  Local destination path. Parent directory must exist.
        force: If True, re-download even when dest already exists.

    Returns:
        The local dest path (whether from cache or fresh download).

    Raises:
        urllib.error.URLError: If the remote URL is unreachable.
        OSError: If the destination directory is not writable.
    """
    if dest.exists() and not force:
        logger.info("Cache hit: %s", dest.name)
        return dest

    tmp = dest.with_suffix(dest.suffix + ".tmp")
    logger.info("Downloading %s -> %s", url, dest.name)

    try:
        urllib.request.urlretrieve(url, tmp)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise

    tmp.rename(dest)
    size_mb = dest.stat().st_size / 1e6
    logger.info("Downloaded %.1f MB -> %s", size_mb, dest.name)

    return dest


def list_ftp_directory(host: str, path: str) -> list[str]:
    """List filenames in an FTP directory.

    Connects anonymously (NCBI FTP servers do not require credentials),
    changes to path, and returns bare filenames. Use this to verify that
    an expected file exists on the server before calling download_ftp_file.

    Args:
        host: FTP hostname, e.g. "ftp.ncbi.nlm.nih.gov".
        path: Absolute directory path on the server, e.g.
              "/gene/DATA/".

    Returns:
        Sorted list of filenames (not full paths) in the directory.

    Raises:
        ftplib.all_errors: If the connection fails or the path does not exist.
    """
    logger.info("Listing FTP directory: ftp://%s%s", host, path)

    with ftplib.FTP(host) as ftp:
        ftp.login()  # anonymous login
        ftp.cwd(path)
        names = ftp.nlst()

    filenames = sorted(name.split("/")[-1] for name in names if name)
    logger.info("Found %d entries in ftp://%s%s", len(filenames), host, path)
    return filenames
