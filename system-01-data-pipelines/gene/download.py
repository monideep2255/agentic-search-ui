"""download.py - Download all Gene FTP files to the local cache.

Downloads 6 files from ftp.ncbi.nlm.nih.gov/gene/DATA/ using the shared
idempotent FTP client. Skips files already present unless force=True.

Depends on:
    - system-01-data-pipelines/shared/ftp_client.download_ftp_file
    - system-01-data-pipelines/shared/config.PipelineConfig

Reads:
    - ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/ (remote)

Writes:
    - config.ftp_cache_dir/gene_info.gz
    - config.ftp_cache_dir/gene2go.gz
    - config.ftp_cache_dir/gene2pubmed.gz
    - config.ftp_cache_dir/gene_refseq_uniprotkb_collab.gz
    - config.ftp_cache_dir/mim2gene_medgen
    - config.ftp_cache_dir/gene_orthologs.gz
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import PipelineConfig
from shared.ftp_client import download_ftp_file

logger = logging.getLogger(__name__)

FTP_BASE = "ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/"

# Mapping from logical key to remote filename
GENE_FILES: dict[str, str] = {
    "gene_info": "gene_info.gz",
    "gene2go": "gene2go.gz",
    "gene2pubmed": "gene2pubmed.gz",
    "gene_refseq_uniprotkb_collab": "gene_refseq_uniprotkb_collab.gz",
    "mim2gene_medgen": "mim2gene_medgen",
    "gene_orthologs": "gene_orthologs.gz",
}


def download_gene_files(
    config: PipelineConfig,
    force: bool = False,
) -> dict[str, Path]:
    """Download all Gene FTP files to config.ftp_cache_dir.

    Skips any file that already exists in the cache unless force=True.
    Downloads are atomic: the shared ftp_client writes to a .tmp file
    then renames on success to prevent reading partial downloads.

    Args:
        config: Pipeline configuration with ftp_cache_dir set.
        force: If True, re-download all files even when cached.

    Returns:
        Dict mapping file key (e.g. "gene_info") to its local Path.

    Raises:
        urllib.error.URLError: If any remote file is unreachable.
        OSError: If the cache directory is not writable.
    """
    logger.info("Starting Gene FTP downloads (force=%s)", force)
    result: dict[str, Path] = {}

    for key, filename in GENE_FILES.items():
        url = FTP_BASE + filename
        dest = config.ftp_cache_dir / filename
        local_path = download_ftp_file(url=url, dest=dest, force=force)
        result[key] = local_path
        logger.debug("gene file ready: %s -> %s", key, local_path)

    logger.info(
        "Gene FTP downloads complete: %d files in %s",
        len(result),
        config.ftp_cache_dir,
    )
    return result
