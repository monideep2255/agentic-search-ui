"""Tests for shared/ftp_client.py - idempotent FTP download and directory listing.

Depends on:
    - system-01-data-pipelines/shared/ftp_client.py
    - pytest, unittest.mock
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shared.ftp_client import download_ftp_file, list_ftp_directory


class TestDownloadFtpFile:
    def test_cache_hit_skips_download(self, tmp_path):
        """download_ftp_file returns early when dest exists and force=False."""
        dest = tmp_path / "gene_info.gz"
        dest.write_text("cached content")

        with patch("urllib.request.urlretrieve") as mock_retrieve:
            result = download_ftp_file("ftp://ftp.ncbi.nlm.nih.gov/gene_info.gz", dest)

        mock_retrieve.assert_not_called()
        assert result == dest

    def test_downloads_when_file_missing(self, tmp_path):
        """download_ftp_file calls urlretrieve when dest does not exist."""
        dest = tmp_path / "gene_info.gz"
        url = "ftp://ftp.ncbi.nlm.nih.gov/gene_info.gz"

        def fake_retrieve(url, tmp_path_arg):
            Path(tmp_path_arg).write_text("downloaded content")

        with patch("urllib.request.urlretrieve", side_effect=fake_retrieve) as mock_retrieve:
            result = download_ftp_file(url, dest)

        mock_retrieve.assert_called_once()
        assert result == dest
        assert dest.read_text() == "downloaded content"

    def test_atomic_rename_via_tmp(self, tmp_path):
        """download_ftp_file writes to a .tmp file first, then renames to dest."""
        dest = tmp_path / "gene_info.gz"
        url = "ftp://ftp.ncbi.nlm.nih.gov/gene_info.gz"
        captured_tmp = []

        def fake_retrieve(url, tmp_path_arg):
            captured_tmp.append(tmp_path_arg)
            Path(tmp_path_arg).write_text("downloaded content")

        with patch("urllib.request.urlretrieve", side_effect=fake_retrieve):
            download_ftp_file(url, dest)

        assert len(captured_tmp) == 1
        # the .tmp file was used and then renamed away
        assert str(captured_tmp[0]).endswith(".tmp")
        assert not Path(str(captured_tmp[0])).exists()
        assert dest.exists()

    def test_force_true_downloads_even_if_cached(self, tmp_path):
        """download_ftp_file re-downloads when force=True even if dest exists."""
        dest = tmp_path / "gene_info.gz"
        dest.write_text("old cached content")
        url = "ftp://ftp.ncbi.nlm.nih.gov/gene_info.gz"

        def fake_retrieve(url, tmp_path_arg):
            Path(tmp_path_arg).write_text("fresh content")

        with patch("urllib.request.urlretrieve", side_effect=fake_retrieve) as mock_retrieve:
            download_ftp_file(url, dest, force=True)

        mock_retrieve.assert_called_once()
        assert dest.read_text() == "fresh content"

    def test_cleanup_tmp_on_error(self, tmp_path):
        """download_ftp_file removes the .tmp file if urlretrieve raises."""
        dest = tmp_path / "gene_info.gz"
        url = "ftp://ftp.ncbi.nlm.nih.gov/gene_info.gz"

        def fake_retrieve_with_error(url, tmp_path_arg):
            Path(tmp_path_arg).write_text("partial content")
            raise OSError("simulated network error")

        with patch("urllib.request.urlretrieve", side_effect=fake_retrieve_with_error):
            with pytest.raises(OSError):
                download_ftp_file(url, dest)

        tmp_file = dest.with_suffix(dest.suffix + ".tmp")
        assert not tmp_file.exists()
        assert not dest.exists()


class TestListFtpDirectory:
    def test_returns_sorted_filenames(self):
        """list_ftp_directory returns sorted bare filenames from FTP."""
        mock_ftp = MagicMock()
        mock_ftp.nlst.return_value = [
            "/gene/DATA/gene_info.gz",
            "/gene/DATA/README",
            "/gene/DATA/gene2go.gz",
        ]

        with patch("ftplib.FTP") as mock_ftp_class:
            mock_ftp_class.return_value.__enter__ = MagicMock(return_value=mock_ftp)
            mock_ftp_class.return_value.__exit__ = MagicMock(return_value=False)

            result = list_ftp_directory("ftp.ncbi.nlm.nih.gov", "/gene/DATA/")

        assert result == ["README", "gene2go.gz", "gene_info.gz"]

    def test_calls_login_and_cwd(self):
        """list_ftp_directory calls anonymous login and navigates to path."""
        mock_ftp = MagicMock()
        mock_ftp.nlst.return_value = ["file.gz"]

        with patch("ftplib.FTP") as mock_ftp_class:
            mock_ftp_class.return_value.__enter__ = MagicMock(return_value=mock_ftp)
            mock_ftp_class.return_value.__exit__ = MagicMock(return_value=False)

            list_ftp_directory("ftp.ncbi.nlm.nih.gov", "/gene/DATA/")

        mock_ftp.login.assert_called_once()
        mock_ftp.cwd.assert_called_once_with("/gene/DATA/")

    def test_filters_empty_entries(self):
        """list_ftp_directory skips empty strings in nlst output."""
        mock_ftp = MagicMock()
        mock_ftp.nlst.return_value = ["gene_info.gz", "", "gene2go.gz"]

        with patch("ftplib.FTP") as mock_ftp_class:
            mock_ftp_class.return_value.__enter__ = MagicMock(return_value=mock_ftp)
            mock_ftp_class.return_value.__exit__ = MagicMock(return_value=False)

            result = list_ftp_directory("ftp.ncbi.nlm.nih.gov", "/gene/DATA/")

        assert "" not in result
        assert len(result) == 2
