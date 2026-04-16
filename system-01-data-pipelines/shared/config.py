"""
config.py - Pipeline configuration loaded from environment variables.

All pipeline parameters live here. Load once at startup via PipelineConfig.from_env()
and pass the config instance through the pipeline.

Depends on:
    - python-dotenv (load_dotenv)
    - .env file at repo root (or environment variables set directly)

Reads:
    - NCBI_EMAIL, NCBI_API_KEY
    - PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DBNAME
    - DATA_DIR, FTP_CACHE_DIR, KGX_OUTPUT_DIR, RAW_DATA_DIR
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    """Return the repository root from this module location."""
    return Path(__file__).resolve().parents[2]


def _default_data_root() -> Path:
    """Return the canonical repo-local data root."""
    return _repo_root() / "data"


def _env_str(name: str, default: str = "") -> str:
    """Read an environment variable, treating blank strings as unset."""
    value = os.environ.get(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped else default


def _env_path(name: str, default: Path) -> Path:
    """Read a path env var, treating blank strings as unset."""
    return Path(_env_str(name, str(default)))


@dataclass
class PipelineConfig:
    """Configuration for all System 1 ETL pipelines.

    Load via PipelineConfig.from_env(). Direct instantiation is allowed
    for tests but requires all required fields to be supplied explicitly.

    __post_init__ converts string paths to Path objects and creates all
    data directories if they do not already exist.
    """

    # NCBI credentials
    ncbi_email: str
    """NCBI Entrez email address. Required by NCBI API policy."""

    ncbi_api_key: str = ""
    """Optional NCBI API key. Raises rate limit from 3 to 10 requests/s."""

    # Data directories. Defaults point at the repo-local data/ tree so all
    # downloaded data lands under the project's canonical storage root.
    data_dir: Path = field(default_factory=_default_data_root)
    """Root data directory. All sub-directories are created under this path."""

    ftp_cache_dir: Path = field(default_factory=lambda: _default_data_root() / "ftp_cache")
    """Local cache for downloaded FTP files. Downloads are skipped on cache hit."""

    kgx_output_dir: Path = field(default_factory=lambda: _default_data_root() / "kgx")
    """Output directory for KGX TSV files (nodes.tsv + edges.tsv per database)."""

    raw_data_dir: Path = field(default_factory=lambda: _default_data_root() / "raw")
    """Directory for raw unparsed downloads (intermediate extraction artifacts)."""

    # PostgreSQL connection params
    pg_host: str = "localhost"
    """PostgreSQL host."""

    pg_port: int = 5432
    """PostgreSQL port."""

    pg_user: str = ""
    """PostgreSQL user."""

    pg_password: str = ""
    """PostgreSQL password."""

    pg_dbname: str = ""
    """PostgreSQL database name."""

    # Pipeline tuning
    entrez_batch_size: int = 50
    """Number of IDs per Entrez eSummary/eFetch batch request."""

    chunk_size: int = 200_000
    """Row chunk size for reading large gzipped FTP files with pandas."""

    def __post_init__(self) -> None:
        """Convert string paths to Path objects and create directories."""
        self.data_dir = Path(self.data_dir)
        self.ftp_cache_dir = Path(self.ftp_cache_dir)
        self.kgx_output_dir = Path(self.kgx_output_dir)
        self.raw_data_dir = Path(self.raw_data_dir)

        for directory in (self.data_dir, self.ftp_cache_dir, self.kgx_output_dir, self.raw_data_dir):
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug("Directory ready: %s", directory)

    @classmethod
    def from_env(cls, dotenv_path: str | Path | None = None) -> "PipelineConfig":
        """Load configuration from environment variables (and optional .env file).

        Searches for a .env file in the current working directory by default.
        Pass dotenv_path to override the search location.

        Args:
            dotenv_path: Path to a .env file. If None, python-dotenv searches
                         upward from the current working directory.

        Returns:
            A fully initialised PipelineConfig with directories created.

        Raises:
            ValueError: If NCBI_EMAIL is not set in the environment.
        """
        load_dotenv(dotenv_path=dotenv_path, override=False)

        ncbi_email = os.environ.get("NCBI_EMAIL", "")
        if not ncbi_email:
            raise ValueError(
                "NCBI_EMAIL is required. Set it in your .env file or environment."
            )

        pg_port_raw = os.environ.get("PG_PORT", "5432")
        try:
            pg_port = int(pg_port_raw)
        except ValueError:
            logger.warning("PG_PORT=%r is not an integer; defaulting to 5432", pg_port_raw)
            pg_port = 5432

        default_root = _default_data_root()
        data_dir = _env_path("DATA_DIR", default_root)
        return cls(
            ncbi_email=ncbi_email,
            ncbi_api_key=_env_str("NCBI_API_KEY", ""),
            data_dir=data_dir,
            ftp_cache_dir=_env_path("FTP_CACHE_DIR", data_dir / "ftp_cache"),
            kgx_output_dir=_env_path("KGX_OUTPUT_DIR", data_dir / "kgx"),
            raw_data_dir=_env_path("RAW_DATA_DIR", data_dir / "raw"),
            pg_host=_env_str("PG_HOST", "localhost"),
            pg_port=pg_port,
            pg_user=_env_str("PG_USER", ""),
            pg_password=_env_str("PG_PASSWORD", ""),
            pg_dbname=_env_str("PG_DBNAME", ""),
        )
