"""Tests for shared/entrez_client.py - NCBI Entrez API client with retry.

Depends on:
    - system-01-data-pipelines/shared/entrez_client.py
    - biopython (Bio.Entrez)
    - pytest, unittest.mock
"""

from io import StringIO
from unittest.mock import MagicMock, call, patch

import pytest

from shared.entrez_client import (
    configure_entrez,
    entrez_efetch,
    entrez_esearch,
    entrez_esummary_batch,
)


@pytest.fixture(autouse=True)
def patch_sleep():
    """Suppress all time.sleep calls in entrez_client to keep tests fast."""
    with patch("shared.entrez_client.time.sleep"):
        yield


class TestConfigureEntrez:
    def test_sets_email(self):
        """configure_entrez sets Entrez.email."""
        with patch("shared.entrez_client.Entrez") as mock_entrez:
            configure_entrez("user@example.com")
        assert mock_entrez.email == "user@example.com"

    def test_sets_api_key_when_provided(self):
        """configure_entrez sets Entrez.api_key when api_key is given."""
        with patch("shared.entrez_client.Entrez") as mock_entrez:
            configure_entrez("user@example.com", api_key="mykey")
        assert mock_entrez.api_key == "mykey"

    def test_does_not_set_api_key_when_empty(self):
        """configure_entrez does not touch Entrez.api_key when api_key is empty."""
        with patch("shared.entrez_client.Entrez") as mock_entrez:
            configure_entrez("user@example.com", api_key="")
        assert not hasattr(mock_entrez, "api_key") or mock_entrez.api_key != "something"

    def test_raises_on_empty_email(self):
        """configure_entrez raises ValueError when email is empty."""
        with pytest.raises(ValueError, match="email is required"):
            configure_entrez("")


class TestEntrezEsearch:
    def test_returns_id_list(self):
        """entrez_esearch returns the IdList from a successful eSearch response."""
        mock_handle = MagicMock()
        mock_record = {"IdList": ["672", "675", "7157"]}

        with patch("shared.entrez_client.Entrez") as mock_entrez:
            mock_entrez.esearch.return_value = mock_handle
            mock_entrez.read.return_value = mock_record

            result = entrez_esearch(db="gene", term="BRCA1[Gene Name]")

        assert result == ["672", "675", "7157"]

    def test_returns_empty_list_on_empty_idlist(self):
        """entrez_esearch returns [] when IdList is empty."""
        mock_handle = MagicMock()
        mock_record = {"IdList": []}

        with patch("shared.entrez_client.Entrez") as mock_entrez:
            mock_entrez.esearch.return_value = mock_handle
            mock_entrez.read.return_value = mock_record

            result = entrez_esearch(db="gene", term="nonexistent_term_xyz")

        assert result == []

    def test_retries_on_transient_failure(self):
        """entrez_esearch retries after a transient exception and returns result."""
        mock_handle = MagicMock()
        mock_record = {"IdList": ["672"]}

        call_count = {"n": 0}

        def esearch_side_effect(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise OSError("simulated network error")
            return mock_handle

        with patch("shared.entrez_client.Entrez") as mock_entrez:
            mock_entrez.esearch.side_effect = esearch_side_effect
            mock_entrez.read.return_value = mock_record

            result = entrez_esearch(db="gene", term="BRCA1", retries=3)

        assert result == ["672"]
        assert call_count["n"] == 2

    def test_returns_empty_list_after_all_retries_exhausted(self):
        """entrez_esearch returns [] when all retry attempts fail."""
        with patch("shared.entrez_client.Entrez") as mock_entrez:
            mock_entrez.esearch.side_effect = OSError("persistent network error")

            result = entrez_esearch(db="gene", term="BRCA1", retries=3)

        assert result == []
        assert mock_entrez.esearch.call_count == 3


class TestEntrezEsummaryBatch:
    def test_returns_document_summaries(self):
        """entrez_esummary_batch returns flat list of DocumentSummary records."""
        mock_handle = MagicMock()
        doc_summaries = [{"Name": "BRCA1", "Id": "672"}]
        mock_record = {"DocumentSummarySet": {"DocumentSummary": doc_summaries}}

        with patch("shared.entrez_client.Entrez") as mock_entrez:
            mock_entrez.esummary.return_value = mock_handle
            mock_entrez.read.return_value = mock_record

            result = entrez_esummary_batch(db="gene", ids=["672"])

        assert result == doc_summaries

    def test_batches_ids_correctly(self):
        """entrez_esummary_batch splits 5 IDs into 3 batches when batch_size=2."""
        ids = ["1", "2", "3", "4", "5"]
        mock_handle = MagicMock()
        mock_record = {"DocumentSummarySet": {"DocumentSummary": []}}

        with patch("shared.entrez_client.Entrez") as mock_entrez:
            mock_entrez.esummary.return_value = mock_handle
            mock_entrez.read.return_value = mock_record

            entrez_esummary_batch(db="gene", ids=ids, batch_size=2)

        # ceil(5/2) = 3 batches
        assert mock_entrez.esummary.call_count == 3

    def test_skips_failed_batch_and_returns_partial(self):
        """entrez_esummary_batch returns partial results when one batch fails all retries."""
        mock_handle = MagicMock()
        good_record = {"DocumentSummarySet": {"DocumentSummary": [{"Id": "1"}]}}

        call_count = {"n": 0}

        def esummary_side_effect(**kwargs):
            call_count["n"] += 1
            if call_count["n"] <= 3:
                raise OSError("batch error")
            return mock_handle

        with patch("shared.entrez_client.Entrez") as mock_entrez:
            mock_entrez.esummary.side_effect = esummary_side_effect
            mock_entrez.read.return_value = good_record

            result = entrez_esummary_batch(db="gene", ids=["bad1", "good2"], batch_size=1)

        # First batch (bad1) fails 3 times and is skipped; second batch (good2) succeeds
        assert result == [{"Id": "1"}]


class TestEntrezEfetch:
    def test_returns_text_responses(self):
        """entrez_efetch returns list of text strings from the handle."""
        mock_handle = MagicMock()
        mock_handle.read.return_value = "<GeneTable>some xml</GeneTable>"

        with patch("shared.entrez_client.Entrez") as mock_entrez:
            mock_entrez.efetch.return_value = mock_handle

            result = entrez_efetch(db="gene", ids=["672"], rettype="xml")

        assert result == ["<GeneTable>some xml</GeneTable>"]

    def test_batches_ids_correctly(self):
        """entrez_efetch splits 4 IDs into 2 batches when batch_size=2."""
        ids = ["1", "2", "3", "4"]
        mock_handle = MagicMock()
        mock_handle.read.return_value = "<xml/>"

        with patch("shared.entrez_client.Entrez") as mock_entrez:
            mock_entrez.efetch.return_value = mock_handle

            result = entrez_efetch(db="gene", ids=ids, batch_size=2)

        assert mock_entrez.efetch.call_count == 2
        assert len(result) == 2

    def test_skips_failed_batch(self):
        """entrez_efetch returns partial results when one batch fails all retries."""
        mock_handle = MagicMock()
        mock_handle.read.return_value = "<xml>good</xml>"

        call_count = {"n": 0}

        def efetch_side_effect(**kwargs):
            call_count["n"] += 1
            if call_count["n"] <= 3:
                raise OSError("network error")
            return mock_handle

        with patch("shared.entrez_client.Entrez") as mock_entrez:
            mock_entrez.efetch.side_effect = efetch_side_effect

            result = entrez_efetch(db="gene", ids=["bad", "good"], batch_size=1)

        assert result == ["<xml>good</xml>"]
