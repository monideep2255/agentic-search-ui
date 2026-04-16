"""parse_pubmed_xml.py - Stream-parse PubMed XML files into BioLink nodes and edges.

Uses lxml.etree.iterparse with tag='PubmedArticle' so only one article element
lives in memory at a time. Each article is yielded as (article_node, mesh_edges)
and the lxml element is cleared immediately after to keep memory flat across
40M articles.

Depends on:
    - lxml (iterparse)
    - system-01-data-pipelines/shared/biolink_mapper.map_node
    - system-01-data-pipelines/shared/biolink_mapper.map_edge

Reads:
    - .xml.gz files from config.ftp_cache_dir/pubmed/

Yields:
    tuple[dict, list[dict]]: (article_node_dict, list_of_mesh_edge_dicts)
"""

import gzip
import logging
import sys
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.biolink_mapper import map_node, map_edge

try:
    from lxml import etree
except ImportError as exc:
    raise ImportError("lxml is required for PubMed XML parsing: pip install lxml") from exc

logger = logging.getLogger(__name__)

_ARTICLE_SOURCE = "PubMed"
_ARTICLE_CATEGORY = "biolink:Article"
_MESH_PREDICATE = "biolink:has_mesh_annotation"


def _source_url(pmid: str) -> str:
    """Build the canonical PubMed URL for a given PMID."""
    return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


def parse_pubmed_file(path: Path) -> Iterator[tuple[dict, list[dict]]]:
    """Stream-parse one PubMed XML .gz file, yielding one article at a time.

    For each PubmedArticle element encountered:
    - Extracts PMID (skips the article if absent or empty).
    - Extracts ArticleTitle (defaults to "[No title]" if absent).
    - Extracts AbstractText (omitted from node if absent).
    - Extracts all MeshHeading DescriptorName @UI values and builds one
      biolink:has_mesh_annotation edge per UI.
    - Calls elem.clear() after processing to free element memory.

    Uses lxml.etree.XMLSyntaxError handling to log malformed files and
    continue the pipeline rather than aborting.

    Args:
        path: Local path to a PubMed .xml.gz file.

    Yields:
        Tuple of (article_node_dict, list_of_mesh_edge_dicts). The list may
        be empty if the article has no MeshHeadingList.

    Raises:
        OSError: If path cannot be opened for reading.
    """
    logger.info("Parsing PubMed file: %s", path.name)

    try:
        fh = gzip.open(path, "rb")
    except OSError as exc:
        logger.error("Cannot open %s: %s", path, exc)
        raise

    article_count = 0
    skipped_no_pmid = 0

    try:
        context = etree.iterparse(fh, events=("end",), tag="PubmedArticle")
        root = None

        for event, elem in context:
            if root is None:
                root = elem.getroottree().getroot()

            # Extract PMID
            pmid_elem = elem.find(".//PMID")
            if pmid_elem is None or not (pmid_elem.text or "").strip():
                skipped_no_pmid += 1
                elem.clear()
                continue

            pmid = pmid_elem.text.strip()
            source_url = _source_url(pmid)

            # Extract title
            title_elem = elem.find(".//ArticleTitle")
            title = (
                (title_elem.text or "").strip()
                if title_elem is not None
                else ""
            ) or "[No title]"

            # Extract abstract (optional)
            abstract_elem = elem.find(".//AbstractText")
            abstract_text: str | None = None
            if abstract_elem is not None and abstract_elem.text:
                abstract_text = abstract_elem.text.strip() or None

            # Build article node
            extra: dict = {}
            if abstract_text:
                extra["description"] = abstract_text

            article_node = map_node(
                id=f"PMID:{pmid}",
                category=_ARTICLE_CATEGORY,
                name=title,
                source=_ARTICLE_SOURCE,
                source_url=source_url,
                **extra,
            )

            # Extract MeSH edges
            mesh_edges: list[dict] = []
            for descriptor in elem.findall(".//MeshHeadingList/MeshHeading/DescriptorName"):
                ui = descriptor.get("UI", "").strip()
                if not ui:
                    continue
                edge = map_edge(
                    subject=f"PMID:{pmid}",
                    predicate=_MESH_PREDICATE,
                    object=f"MeSH:{ui}",
                    source=_ARTICLE_SOURCE,
                    source_url=source_url,
                )
                mesh_edges.append(edge)

            article_count += 1
            yield article_node, mesh_edges

            # Free element memory; also clear ancestors periodically
            parent = elem.getparent()
            elem.clear()
            if parent is not None and article_count % 10_000 == 0:
                # Walk forward and remove processed siblings to avoid root bloat
                while len(parent) > 0 and parent[0] is not elem:
                    del parent[0]

    except etree.XMLSyntaxError as exc:
        logger.error("XML syntax error in %s: %s (parsed %d articles so far)", path.name, exc, article_count)

    finally:
        fh.close()

    logger.info(
        "Finished parsing %s: %d articles yielded, %d skipped (no PMID)",
        path.name,
        article_count,
        skipped_no_pmid,
    )
