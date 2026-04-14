"""download.py - Download MedGen FTP files to ftp_cache_dir.

Downloads all required MedGen bulk files from the NCBI FTP server. Downloads
are idempotent: a cached file is reused unless force=True.

Depends on:
    - system-01-data-pipelines/shared/config.py
    - system-01-data-pipelines/shared/ftp_client.py

Reads:
    - ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/MedGenIDMappings.txt.gz
    - ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/MGREL.RRF.gz
    - ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/NAMES.RRF.gz
    - ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/medgen_pubmed_lnk.txt.gz
    - ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/MedGen_HPO_OMIM_Mapping.txt.gz

Writes:
    - config.ftp_cache_dir/MedGenIDMappings.txt.gz
    - config.ftp_cache_dir/MGREL.RRF.gz
    - config.ftp_cache_dir/NAMES.RRF.gz
    - config.ftp_cache_dir/medgen_pubmed_lnk.txt.gz
    - config.ftp_cache_dir/MedGen_HPO_OMIM_Mapping.txt.gz
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.config import PipelineConfig
from shared.ftp_client import download_ftp_file

logger = logging.getLogger(__name__)

MEDGEN_FTP_FILES: dict[str, str] = {
    "id_mappings": (
        "ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/MedGenIDMappings.txt.gz"
    ),
    "mgrel": (
        "ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/MGREL.RRF.gz"
    ),
    "names": (
        "ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/NAMES.RRF.gz"
    ),
    "pubmed_links": (
        "ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/medgen_pubmed_lnk.txt.gz"
    ),
    "hpo_omim": (
        "ftp://ftp.ncbi.nlm.nih.gov/pub/medgen/MedGen_HPO_OMIM_Mapping.txt.gz"
    ),
}

_LOCAL_NAMES: dict[str, str] = {
    "id_mappings": "MedGenIDMappings.txt.gz",
    "mgrel": "MGREL.RRF.gz",
    "names": "NAMES.RRF.gz",
    "pubmed_links": "medgen_pubmed_lnk.txt.gz",
    "hpo_omim": "MedGen_HPO_OMIM_Mapping.txt.gz",
}


def download_medgen_files(
    config: PipelineConfig,
    force: bool = False,
) -> dict[str, Path]:
    """Download MedGen FTP files to ftp_cache_dir.

    Files downloaded:
        - id_mappings: MedGenIDMappings.txt.gz (disease/phenotype nodes and xrefs)
        - mgrel:       MGREL.RRF.gz (disease hierarchy relationships)
        - names:       NAMES.RRF.gz (concept names and synonyms)
        - pubmed_links: medgen_pubmed_lnk.txt.gz (concept-to-publication links)
        - hpo_omim:    MedGen_HPO_OMIM_Mapping.txt.gz (HPO/OMIM cross-references)

    Each download is skipped if the local file already exists and force=False.
    Uses an atomic write pattern (download to .tmp then rename) to prevent
    partial downloads from being read by parsers.

    Args:
        config: Pipeline configuration. Uses config.ftp_cache_dir as the
                destination directory.
        force:  If True, re-download even when a cached copy exists.

    Returns:
        Dict mapping file key to the local Path of the downloaded file.
        Keys: "id_mappings", "mgrel", "names", "pubmed_links", "hpo_omim".

    Raises:
        urllib.error.URLError: If a remote URL is unreachable.
        OSError: If ftp_cache_dir is not writable.
    """
    logger.info("Starting MedGen FTP downloads (force=%s)", force)
    paths: dict[str, Path] = {}

    for key, url in MEDGEN_FTP_FILES.items():
        dest = config.ftp_cache_dir / _LOCAL_NAMES[key]
        local_path = download_ftp_file(url, dest, force=force)
        paths[key] = local_path
        logger.info("Ready: %s -> %s", key, local_path)

    logger.info("MedGen downloads complete. Files: %s", list(paths.values()))
    return paths
