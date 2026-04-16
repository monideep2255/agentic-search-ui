"""Tests for shared/config.py - PipelineConfig dataclass.

Depends on:
    - system-01-data-pipelines/shared/config.py
    - pytest, unittest.mock
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from shared.config import PipelineConfig


class TestPipelineConfigDefaults:
    def test_creates_with_required_field_only(self, tmp_path):
        """Direct instantiation with only ncbi_email sets all other fields to defaults."""
        cfg = PipelineConfig(
            ncbi_email="test@example.com",
            data_dir=tmp_path / "data",
            ftp_cache_dir=tmp_path / "ftp_cache",
            kgx_output_dir=tmp_path / "kgx",
            raw_data_dir=tmp_path / "raw",
        )
        assert cfg.ncbi_email == "test@example.com"
        assert cfg.ncbi_api_key == ""
        assert cfg.pg_host == "localhost"
        assert cfg.pg_port == 5432
        assert cfg.entrez_batch_size == 50
        assert cfg.chunk_size == 200_000

    def test_post_init_converts_string_paths(self, tmp_path):
        """__post_init__ converts string paths to Path objects."""
        cfg = PipelineConfig(
            ncbi_email="test@example.com",
            data_dir=str(tmp_path / "data"),
            ftp_cache_dir=str(tmp_path / "ftp_cache"),
            kgx_output_dir=str(tmp_path / "kgx"),
            raw_data_dir=str(tmp_path / "raw"),
        )
        assert isinstance(cfg.data_dir, Path)
        assert isinstance(cfg.ftp_cache_dir, Path)
        assert isinstance(cfg.kgx_output_dir, Path)
        assert isinstance(cfg.raw_data_dir, Path)

    def test_post_init_creates_directories(self, tmp_path):
        """__post_init__ creates all four data directories."""
        data_dir = tmp_path / "data"
        ftp_cache_dir = tmp_path / "ftp_cache"
        kgx_output_dir = tmp_path / "kgx"
        raw_data_dir = tmp_path / "raw"

        cfg = PipelineConfig(
            ncbi_email="test@example.com",
            data_dir=data_dir,
            ftp_cache_dir=ftp_cache_dir,
            kgx_output_dir=kgx_output_dir,
            raw_data_dir=raw_data_dir,
        )

        assert data_dir.is_dir()
        assert ftp_cache_dir.is_dir()
        assert kgx_output_dir.is_dir()
        assert raw_data_dir.is_dir()


class TestPipelineConfigFromEnv:
    def test_from_env_reads_ncbi_email(self, tmp_path):
        """from_env() reads NCBI_EMAIL from the environment."""
        env = {
            "NCBI_EMAIL": "user@example.com",
            "DATA_DIR": str(tmp_path / "data"),
            "FTP_CACHE_DIR": str(tmp_path / "ftp_cache"),
            "KGX_OUTPUT_DIR": str(tmp_path / "kgx"),
            "RAW_DATA_DIR": str(tmp_path / "raw"),
        }
        with patch.dict("os.environ", env, clear=False):
            cfg = PipelineConfig.from_env()
        assert cfg.ncbi_email == "user@example.com"

    def test_from_env_reads_api_key(self, tmp_path):
        """from_env() reads NCBI_API_KEY from the environment."""
        env = {
            "NCBI_EMAIL": "user@example.com",
            "NCBI_API_KEY": "abc123",
            "DATA_DIR": str(tmp_path / "data"),
            "FTP_CACHE_DIR": str(tmp_path / "ftp_cache"),
            "KGX_OUTPUT_DIR": str(tmp_path / "kgx"),
            "RAW_DATA_DIR": str(tmp_path / "raw"),
        }
        with patch.dict("os.environ", env, clear=False):
            cfg = PipelineConfig.from_env()
        assert cfg.ncbi_api_key == "abc123"

    def test_from_env_defaults_to_repo_data_dir(self, tmp_path):
        """from_env() defaults DATA_DIR and subdirs to the configured data root."""
        with patch.dict("os.environ", {"NCBI_EMAIL": "user@example.com"}, clear=True):
            with patch("shared.config._default_data_root", return_value=tmp_path / "data"):
                cfg = PipelineConfig.from_env(dotenv_path=tmp_path / "no.env")

        assert cfg.data_dir == tmp_path / "data"
        assert cfg.ftp_cache_dir == tmp_path / "data" / "ftp_cache"
        assert cfg.kgx_output_dir == tmp_path / "data" / "kgx"
        assert cfg.raw_data_dir == tmp_path / "data" / "raw"

    def test_from_env_treats_blank_path_vars_as_unset(self, tmp_path):
        """Blank path vars in .env should fall back to DATA_DIR-derived defaults."""
        env = {
            "NCBI_EMAIL": "user@example.com",
            "DATA_DIR": str(tmp_path / "data"),
            "FTP_CACHE_DIR": "",
            "KGX_OUTPUT_DIR": "   ",
            "RAW_DATA_DIR": "",
        }
        with patch.dict("os.environ", env, clear=True):
            cfg = PipelineConfig.from_env(dotenv_path=tmp_path / "no.env")

        assert cfg.data_dir == tmp_path / "data"
        assert cfg.ftp_cache_dir == tmp_path / "data" / "ftp_cache"
        assert cfg.kgx_output_dir == tmp_path / "data" / "kgx"
        assert cfg.raw_data_dir == tmp_path / "data" / "raw"

    def test_from_env_raises_when_ncbi_email_missing(self, tmp_path):
        """from_env() raises ValueError when NCBI_EMAIL is absent."""
        # Use a non-existent dotenv path so load_dotenv cannot load a .env file,
        # and clear NCBI_EMAIL from the environment.
        with patch.dict("os.environ", {}, clear=True):
            with patch("shared.config.load_dotenv"):
                with pytest.raises(ValueError, match="NCBI_EMAIL is required"):
                    PipelineConfig.from_env(dotenv_path=str(tmp_path / "no.env"))

    def test_from_env_reads_pg_port(self, tmp_path):
        """from_env() reads PG_PORT as an integer."""
        env = {
            "NCBI_EMAIL": "user@example.com",
            "PG_PORT": "5433",
            "DATA_DIR": str(tmp_path / "data"),
            "FTP_CACHE_DIR": str(tmp_path / "ftp_cache"),
            "KGX_OUTPUT_DIR": str(tmp_path / "kgx"),
            "RAW_DATA_DIR": str(tmp_path / "raw"),
        }
        with patch.dict("os.environ", env, clear=False):
            cfg = PipelineConfig.from_env()
        assert cfg.pg_port == 5433

    def test_from_env_defaults_pg_port_on_invalid_value(self, tmp_path):
        """from_env() falls back to port 5432 when PG_PORT is not an integer."""
        env = {
            "NCBI_EMAIL": "user@example.com",
            "PG_PORT": "not-a-number",
            "DATA_DIR": str(tmp_path / "data"),
            "FTP_CACHE_DIR": str(tmp_path / "ftp_cache"),
            "KGX_OUTPUT_DIR": str(tmp_path / "kgx"),
            "RAW_DATA_DIR": str(tmp_path / "raw"),
        }
        with patch.dict("os.environ", env, clear=False):
            cfg = PipelineConfig.from_env()
        assert cfg.pg_port == 5432
