"""NCBI Entrez API client with retry and exponential backoff.

Depends on:
    - biopython (Bio.Entrez)

Provides:
    - configure_entrez: set credentials once before any queries
    - entrez_esearch: run eSearch, return list of ID strings
    - entrez_esummary_batch: fetch eSummary records in batches
    - entrez_efetch: fetch raw records in batches

Called by:
    - system-01-data-pipelines/gene/pipeline.py
    - system-01-data-pipelines/clinvar/pipeline.py
    - system-01-data-pipelines/medgen/pipeline.py
"""

import logging
import time

from Bio import Entrez

logger = logging.getLogger(__name__)


def configure_entrez(email: str, api_key: str = "") -> None:
    """Set Entrez credentials. Call once before any Entrez queries.

    Args:
        email: Email address required by NCBI for Entrez access.
        api_key: Optional NCBI API key. Raises rate limit from 3 to 10 req/s.
    """
    if not email:
        raise ValueError("email is required for Entrez access")
    Entrez.email = email
    if api_key:
        Entrez.api_key = api_key
    logger.debug("Entrez configured for %s", email)


def entrez_esearch(
    db: str,
    term: str,
    retmax: int = 10_000,
    retries: int = 3,
    sleep: float = 0.35,
) -> list[str]:
    """Run an Entrez eSearch and return a list of ID strings.

    Retries on transient errors with exponential backoff. Returns an empty
    list if all attempts fail (logged at ERROR level).

    Args:
        db: NCBI database name (e.g. "gene", "clinvar", "medgen").
        term: Entrez search term.
        retmax: Maximum number of IDs to return. Defaults to 10,000.
        retries: Number of attempts before giving up. Defaults to 3.
        sleep: Base sleep time in seconds between requests. Defaults to 0.35.

    Returns:
        List of ID strings from the eSearch IdList.
    """
    for attempt in range(retries):
        try:
            handle = Entrez.esearch(db=db, term=term, retmax=retmax)
            record = Entrez.read(handle)
            handle.close()
            time.sleep(sleep)
            ids: list[str] = list(record.get("IdList", []))
            logger.debug("esearch returned %d IDs from %s for term: %s", len(ids), db, term)
            return ids
        except Exception as exc:
            wait = sleep * (2 ** attempt)
            logger.warning(
                "esearch attempt %d/%d failed (%s); retrying in %.1fs",
                attempt + 1,
                retries,
                exc,
                wait,
            )
            time.sleep(wait)
    logger.error("esearch failed after %d attempts for db=%s term=%s", retries, db, term)
    return []


def entrez_esummary_batch(
    db: str,
    ids: list[str],
    batch_size: int = 50,
    sleep: float = 0.35,
) -> list[dict]:
    """Fetch Entrez eSummary records for a list of IDs in batches.

    Processes IDs in chunks of batch_size to stay within NCBI limits.
    Each batch is retried up to 3 times with exponential backoff on failure.
    Failed batches are skipped and logged; partial results are returned.

    Args:
        db: NCBI database name.
        ids: List of ID strings to summarize.
        batch_size: Number of IDs per batch request. Defaults to 50.
        sleep: Base sleep time in seconds between requests. Defaults to 0.35.

    Returns:
        Flat list of DocumentSummary dicts.
    """
    results: list[dict] = []
    total_batches = (len(ids) + batch_size - 1) // batch_size

    for batch_index, i in enumerate(range(0, len(ids), batch_size)):
        batch = ids[i : i + batch_size]
        logger.debug(
            "esummary batch %d/%d: %d IDs",
            batch_index + 1,
            total_batches,
            len(batch),
        )
        for attempt in range(3):
            try:
                handle = Entrez.esummary(db=db, id=",".join(batch))
                summaries = Entrez.read(handle)
                handle.close()
                time.sleep(sleep)
                docs = (
                    summaries.get("DocumentSummarySet", {}).get("DocumentSummary", [])
                )
                results.extend(docs)
                break
            except Exception as exc:
                wait = sleep * (2 ** attempt)
                logger.warning(
                    "esummary batch %d attempt %d/3 failed (%s); retrying in %.1fs",
                    batch_index + 1,
                    attempt + 1,
                    exc,
                    wait,
                )
                time.sleep(wait)
        else:
            logger.error(
                "esummary batch %d/%d failed after 3 attempts; skipping %d IDs",
                batch_index + 1,
                total_batches,
                len(batch),
            )

    logger.debug("esummary returned %d records total from %s", len(results), db)
    return results


def entrez_efetch(
    db: str,
    ids: list[str],
    rettype: str = "xml",
    batch_size: int = 50,
    sleep: float = 0.35,
) -> list[str]:
    """Fetch raw Entrez records in batches and return text responses.

    Intended for XML or other bulk formats that will be parsed downstream.
    Each batch is retried up to 3 times with exponential backoff on failure.
    Failed batches are skipped and logged; partial results are returned.

    Args:
        db: NCBI database name.
        ids: List of ID strings to fetch.
        rettype: Return type string (e.g. "xml", "gb", "fasta"). Defaults to "xml".
        batch_size: Number of IDs per batch request. Defaults to 50.
        sleep: Base sleep time in seconds between requests. Defaults to 0.35.

    Returns:
        List of raw text response strings, one per successful batch.
    """
    responses: list[str] = []
    total_batches = (len(ids) + batch_size - 1) // batch_size

    for batch_index, i in enumerate(range(0, len(ids), batch_size)):
        batch = ids[i : i + batch_size]
        logger.debug(
            "efetch batch %d/%d: %d IDs (rettype=%s)",
            batch_index + 1,
            total_batches,
            len(batch),
            rettype,
        )
        for attempt in range(3):
            try:
                handle = Entrez.efetch(db=db, id=",".join(batch), rettype=rettype, retmode="text")
                text: str = handle.read()
                handle.close()
                time.sleep(sleep)
                responses.append(text)
                break
            except Exception as exc:
                wait = sleep * (2 ** attempt)
                logger.warning(
                    "efetch batch %d attempt %d/3 failed (%s); retrying in %.1fs",
                    batch_index + 1,
                    attempt + 1,
                    exc,
                    wait,
                )
                time.sleep(wait)
        else:
            logger.error(
                "efetch batch %d/%d failed after 3 attempts; skipping %d IDs",
                batch_index + 1,
                total_batches,
                len(batch),
            )

    logger.debug("efetch returned %d batch responses from %s", len(responses), db)
    return responses
