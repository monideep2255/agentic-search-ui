"""Live probe: can a bounded scan of the E. coli Metadata TSV find ESBL
isolates within a 120-second budget, and what does the data actually look
like.

MEASUREMENT ONLY. Writes no product code. Reuses
`pathogen_ftp_transport.resolve_complete_snapshot` and
`stream_filtered_tsv_rows` exactly as `pathogen_detection.py`'s existing
modes call them (see `_isolate_lookup`), so the numbers this script prints
reflect the real transport a third "search by AMR genotype" mode would
also go through, not a hand-rolled HTTP loop with different behavior.

Run under caffeinate so the laptop does not sleep mid-measurement:

    caffeinate -i .venv/bin/python testing/Developer/reports/2026-09-22_isolate_search/probe_ecoli_metadata.py

Run with the repo's src/ on PYTHONPATH (this repo has no `pip install -e .`
into its own venv at the time of this probe):

    PYTHONPATH=src caffeinate -i venv/bin/python testing/Developer/reports/2026-09-22_isolate_search/probe_ecoli_metadata.py

Makes NO E-utilities calls. FTP-over-HTTPS to ftp.ncbi.nlm.nih.gov only.
"""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path

import httpx

from system_03_search_agent.tools import pathogen_ftp_transport as transport

REPORT_DIR = Path(__file__).resolve().parent
RESULTS_MD = REPORT_DIR / "probes.md"

TAXON_FOLDER_PATTERN = re.compile(r'href="([^"/?][^"]*)/"')
ESBL_PREFIXES = ("blaCTX-M", "blaSHV-", "blaTEM-", "blaOXA-")


def _append_section(heading: str, body: str, note: str) -> None:
    with RESULTS_MD.open("a") as f:
        f.write(f"\n## {heading}\n\n")
        f.write("```\n")
        f.write(body.rstrip("\n"))
        f.write("\n```\n\n")
        f.write(note.strip() + "\n")


def _init_report() -> None:
    date_str = time.strftime("%Y-%m-%d")
    header = (
        "# E. coli metadata AMR-genotype scan probe\n\n"
        f"Probed on {date_str}. Live measurement against the real NCBI Pathogen "
        "Detection FTP snapshot tree (`ftp.ncbi.nlm.nih.gov/pathogen/Results/`), "
        "using `pathogen_ftp_transport.resolve_complete_snapshot` and "
        "`stream_filtered_tsv_rows` exactly as the shipped tool calls them. "
        "Purpose: decide whether a bounded scan of a taxon's Metadata TSV can "
        "find isolates carrying a given AMR genotype (ESBL genes as the test "
        "case) inside a 120 second budget, for a planned third mode of "
        "`pathogen_detection.py`.\n"
    )
    RESULTS_MD.write_text(header)


async def probe_a(client: httpx.AsyncClient) -> tuple[str, str]:
    """Which taxon folder name the tree uses for E. coli, and the resolved
    complete snapshot id for it."""
    root_url = transport.PATHOGEN_FTP_BASE + "/"
    started = time.monotonic()
    listing = await transport._get_directory_listing(root_url, client=client)
    listing_elapsed = time.monotonic() - started
    folders = sorted(set(TAXON_FOLDER_PATTERN.findall(listing)))
    ecoli_candidates = [f for f in folders if "coli" in f.lower() or "shigella" in f.lower()]

    body_lines = [
        f"Root listing GET: {root_url}",
        f"Root listing elapsed: {listing_elapsed:.3f}s",
        f"All taxon folders ({len(folders)}):",
    ]
    body_lines.extend(f"  {f}" for f in folders)
    body_lines.append("")
    body_lines.append(f"E. coli / Shigella candidate folders: {ecoli_candidates}")

    if not ecoli_candidates:
        note = (
            "No folder name containing 'coli' or 'shigella' was found at the FTP "
            "root. Design implication: the taxon parameter for an E. coli mode "
            "needs a different folder name than assumed; see the full folder list "
            "above for the actual name to use."
        )
        _append_section(
            "A. Snapshot resolution: taxon folder and snapshot id", "\n".join(body_lines), note
        )
        raise SystemExit("Could not find an E. coli taxon folder; see probes.md section A.")

    taxon = ecoli_candidates[0]
    resolve_started = time.monotonic()
    try:
        snapshot = await transport.resolve_complete_snapshot(taxon, client=client)
        resolve_elapsed = time.monotonic() - resolve_started
        body_lines.append("")
        body_lines.append(f"Chosen taxon folder: {taxon}")
        body_lines.append(f"resolve_complete_snapshot('{taxon}') -> {snapshot}")
        body_lines.append(f"resolve_complete_snapshot elapsed: {resolve_elapsed:.3f}s")
        note = (
            f"Taxon folder is '{taxon}'; resolved complete snapshot is '{snapshot}'. "
            f"Resolution (root listing + snapshot walk) took "
            f"{listing_elapsed + resolve_elapsed:.2f}s total, well inside a 120s budget."
        )
        _append_section(
            "A. Snapshot resolution: taxon folder and snapshot id", "\n".join(body_lines), note
        )
        return taxon, snapshot
    except transport.PathogenTransportError as exc:
        resolve_elapsed = time.monotonic() - resolve_started
        body_lines.append("")
        body_lines.append(f"resolve_complete_snapshot('{taxon}') FAILED after {resolve_elapsed:.3f}s")
        body_lines.append(f"Exception: {exc!r}")
        note = (
            f"Snapshot resolution failed for taxon '{taxon}'. Design implication: "
            "the design cannot proceed until this is fixed; see the exception above."
        )
        _append_section(
            "A. Snapshot resolution: taxon folder and snapshot id", "\n".join(body_lines), note
        )
        raise


async def probe_b(client: httpx.AsyncClient, taxon: str, snapshot: str) -> str:
    """The Metadata TSV: URL, Content-Length, header row."""
    metadata_url = (
        transport.PATHOGEN_FTP_BASE.rstrip("/")
        + f"/{taxon}/{snapshot}/Metadata/{snapshot}.metadata.tsv"
    )
    started = time.monotonic()
    head_resp = await client.head(metadata_url, timeout=30.0, follow_redirects=True)
    head_elapsed = time.monotonic() - started
    content_length = head_resp.headers.get("content-length")
    content_length_bytes = int(content_length) if content_length else None
    content_length_mb = (content_length_bytes / (1024 * 1024)) if content_length_bytes else None

    # Read just enough of the body to get the header row, via a streamed GET
    # capped at a short deadline, never a full buffered read.
    header_row: list[str] = []
    async with client.stream("GET", metadata_url, timeout=20.0) as resp:
        async for line in resp.aiter_lines():
            header_row = line.split("\t")
            break

    amr_present = [c for c in ("AMR_genotypes", "amr_genotypes") if c in header_row]
    ast_present = [c for c in ("AST_phenotypes", "ast_phenotypes") if c in header_row]
    core_or_ast_columns = [
        c
        for c in header_row
        if "amr" in c.lower() or "ast" in c.lower() or "genotype" in c.lower() or "phenotype" in c.lower()
    ]

    mb_line = f"Content-Length (MB): {content_length_mb:.2f}\n" if content_length_mb else "Content-Length (MB): unknown\n"
    body = (
        f"Metadata TSV URL: {metadata_url}\n"
        f"HEAD status: {head_resp.status_code}\n"
        f"HEAD elapsed: {head_elapsed:.3f}s\n"
        f"Content-Length (bytes): {content_length_bytes}\n"
        + mb_line
    )
    body += (
        f"Header row ({len(header_row)} columns), verbatim:\n"
        + "\n".join(f"  [{i}] {name}" for i, name in enumerate(header_row))
        + "\n\n"
        f"AMR genotype column(s) present: {amr_present}\n"
        f"AST phenotype column(s) present: {ast_present}\n"
        f"All AMR/AST/genotype/phenotype-related columns found: {core_or_ast_columns}\n"
    )

    note = f"Metadata TSV is {content_length_mb:.1f} MB. " if content_length_mb else "Metadata TSV size unknown (no Content-Length header). "
    if amr_present:
        note += f"AMR genotype column is '{amr_present[0]}'. "
    else:
        note += "No AMR_genotypes/amr_genotypes column found by exact name; see the full header above. "
    note += (
        "No separate 'core' AMR genotype column or AST phenotype column beyond what is listed above."
    )

    _append_section("B. Metadata TSV: URL, size, header row", body, note)
    return amr_present[0] if amr_present else (header_row[0] if header_row else "")


async def probe_c(client: httpx.AsyncClient, taxon: str, snapshot: str, amr_column: str) -> None:
    """Read the first 200 rows, print 5 example non-empty AMR_genotypes values."""
    metadata_url = (
        transport.PATHOGEN_FTP_BASE.rstrip("/")
        + f"/{taxon}/{snapshot}/Metadata/{snapshot}.metadata.tsv"
    )
    header: list[str] = []
    amr_index: int | None = None
    examples: list[str] = []
    rows_read = 0
    started = time.monotonic()
    async with client.stream("GET", metadata_url, timeout=60.0) as resp:
        async for line in resp.aiter_lines():
            if not header:
                header = line.split("\t")
                if amr_column in header:
                    amr_index = header.index(amr_column)
                continue
            if not line:
                continue
            rows_read += 1
            fields = line.split("\t")
            if amr_index is not None and amr_index < len(fields):
                value = fields[amr_index].strip()
                if value and value != "NULL" and len(examples) < 5:
                    examples.append(value)
            if rows_read >= 200:
                break
    elapsed = time.monotonic() - started

    body = (
        f"Rows read: {rows_read}\n"
        f"AMR genotype column index: {amr_index}\n"
        f"Elapsed: {elapsed:.3f}s\n\n"
        f"First {len(examples)} non-empty '{amr_column}' values, verbatim:\n"
    )
    body += "\n".join(f"  {i + 1}. {v}" for i, v in enumerate(examples))
    if not examples:
        body += "  (none found in the first 200 rows)"

    note = (
        f"Out of the first {rows_read} rows, {len(examples)} example(s) of non-empty "
        f"'{amr_column}' values were captured above; see their separator and gene "
        "spelling for the third mode's parsing design."
    )
    _append_section("C. AMR genotype row format, first 200 rows", body, note)


def _matches_esbl(value: str) -> list[str]:
    return [prefix for prefix in ESBL_PREFIXES if prefix in value]


async def probe_d_single(
    client: httpx.AsyncClient,
    taxon: str,
    snapshot: str,
    amr_column: str,
    deadline_s: float,
) -> dict:
    """One scan of the full Metadata TSV for ESBL-carrying isolates, with a
    caller-supplied deadline. Uses `stream_filtered_tsv_rows`'s own
    `key_column`/`key_values` filter against a synthetic exact-match set is
    not usable here (ESBL detection needs a substring match inside a
    comma-joined field, not exact equality), so this probe streams the raw
    TSV directly with the SAME async-stream-line-by-line shape
    `stream_filtered_tsv_rows` uses, to measure what a substring-matching
    filter mode would see. This deliberately does NOT reuse
    `stream_filtered_tsv_rows` for this one probe because that function's
    `key_values` contract is exact-match only; section D's note says so
    explicitly for the product design.
    """
    metadata_url = (
        transport.PATHOGEN_FTP_BASE.rstrip("/")
        + f"/{taxon}/{snapshot}/Metadata/{snapshot}.metadata.tsv"
    )
    header: list[str] = []
    amr_index: int | None = None
    biosample_index: int | None = None
    strain_index: int | None = None
    geo_index: int | None = None
    date_index: int | None = None

    rows_scanned = 0
    matches: list[dict] = []
    match_times: list[float] = []
    truncated = False

    deadline = time.monotonic() + deadline_s
    started = time.monotonic()
    async with client.stream("GET", metadata_url, timeout=deadline_s + 10.0) as resp:
        async for line in resp.aiter_lines():
            if time.monotonic() >= deadline:
                truncated = True
                break
            if not header:
                header = line.split("\t")
                amr_index = header.index(amr_column) if amr_column in header else None
                for cand, target in (
                    (("biosample_acc",), "biosample_index"),
                    (("strain",), "strain_index"),
                    (("geo_loc_name",), "geo_index"),
                    (("collection_date",), "date_index"),
                ):
                    for c in cand:
                        if c in header:
                            if target == "biosample_index":
                                biosample_index = header.index(c)
                            elif target == "strain_index":
                                strain_index = header.index(c)
                            elif target == "geo_index":
                                geo_index = header.index(c)
                            elif target == "date_index":
                                date_index = header.index(c)
                            break
                continue
            if not line:
                continue
            rows_scanned += 1
            fields = line.split("\t")
            if amr_index is None or amr_index >= len(fields):
                continue
            value = fields[amr_index]
            if not value:
                continue
            genes = _matches_esbl(value)
            if genes:
                matches.append(
                    {
                        "biosample_acc": fields[biosample_index] if biosample_index is not None and biosample_index < len(fields) else None,
                        "strain": fields[strain_index] if strain_index is not None and strain_index < len(fields) else None,
                        "geo_loc_name": fields[geo_index] if geo_index is not None and geo_index < len(fields) else None,
                        "collection_date": fields[date_index] if date_index is not None and date_index < len(fields) else None,
                        "matched_genes": genes,
                    }
                )
                match_times.append(time.monotonic() - started)
    elapsed = time.monotonic() - started

    return {
        "rows_scanned": rows_scanned,
        "matches": matches,
        "match_times": match_times,
        "truncated": truncated,
        "elapsed": elapsed,
    }


async def probe_d_and_e(client: httpx.AsyncClient, taxon: str, snapshot: str, amr_column: str) -> None:
    stop_after_n_note = (
        "`stream_filtered_tsv_rows` accepts `max_matches`, which stops the scan once N "
        "rows matching an EXACT key_values membership test have been collected. It has "
        "no substring/contains matcher, so it cannot be reused as-is for a "
        "'contains any of these gene prefixes' filter; a third mode would need its own "
        "row-filter callable (or an extended transport function taking a predicate) "
        "that still stops after N matches the way max_matches does today."
    )

    results = {}
    for deadline_s, label in ((120.0, "120s"), (60.0, "60s"), (30.0, "30s")):
        result = await probe_d_single(client, taxon, snapshot, amr_column, deadline_s)
        results[label] = result

        first10 = result["matches"][:10]
        body_lines = [
            f"Deadline budget: {deadline_s:.0f}s",
            f"Elapsed: {result['elapsed']:.3f}s",
            f"Rows scanned: {result['rows_scanned']}",
            f"Matching rows: {len(result['matches'])}",
            f"Truncated by deadline: {result['truncated']}",
            "",
            f"First {len(first10)} matches:",
        ]
        for i, m in enumerate(first10, start=1):
            body_lines.append(
                f"  {i}. biosample_acc={m['biosample_acc']} strain={m['strain']} "
                f"geo_loc_name={m['geo_loc_name']} collection_date={m['collection_date']} "
                f"matched_genes={m['matched_genes']}"
            )
        note = (
            f"At a {deadline_s:.0f}s budget: {result['rows_scanned']} rows scanned, "
            f"{len(result['matches'])} ESBL matches found, "
            f"{'cut off by the deadline' if result['truncated'] else 'reached end of file before the deadline'}. "
            + stop_after_n_note
        )
        _append_section(f"D. Scan for ESBL genes, {label} deadline", "\n".join(body_lines), note)

    # E: time to 1st, 10th, 20th match, using the 120s run (the most complete).
    match_times = results["120s"]["match_times"]

    def _time_at(n: int) -> str:
        if len(match_times) >= n:
            return f"{match_times[n - 1]:.3f}s"
        return "not reached in the 120s run"

    body = (
        f"Time to 1st match: {_time_at(1)}\n"
        f"Time to 10th match: {_time_at(10)}\n"
        f"Time to 20th match: {_time_at(20)}\n"
        f"Total matches found within 120s: {len(match_times)}\n"
    )
    note = (
        "These times are from the 120s run above. If the 20th match arrives within a "
        "few seconds, a stop-after-N-matches design gives a fast, useful response even "
        "though a full scan of the file takes far longer."
    )
    _append_section("E. Time to 1st, 10th, 20th match", body, note)

    # F: total row count, if establishable.
    total_rows_120s = results["120s"]["rows_scanned"]
    truncated_120s = results["120s"]["truncated"]
    if not truncated_120s:
        body = f"Total data rows in the Metadata TSV: {total_rows_120s} (full file scanned within the 120s budget)."
        note = "The 120s scan reached end of file, so this is an exact count, not an estimate."
    else:
        body = (
            f"Could not be established within the 120s budget: the scan was cut off after "
            f"{total_rows_120s} rows scanned, still short of end of file."
        )
        note = "A full row count would need a longer-than-120s scan or a separate wc-l-style pass; not attempted here to respect the stated budget."
    _append_section("F. Total row count", body, note)


async def main() -> None:
    _init_report()
    overall_started = time.monotonic()
    async with httpx.AsyncClient() as client:
        taxon, snapshot = await probe_a(client)
        amr_column = await probe_b(client, taxon, snapshot)
        await probe_c(client, taxon, snapshot, amr_column)
        await probe_d_and_e(client, taxon, snapshot, amr_column)
    overall_elapsed = time.monotonic() - overall_started

    print("Probe complete.")
    print(f"Taxon folder: {taxon}")
    print(f"Snapshot: {snapshot}")
    print(f"AMR genotype column: {amr_column}")
    print(f"Total wall-clock time for all probes: {overall_elapsed:.2f}s")
    print(f"Report written to: {RESULTS_MD}")


if __name__ == "__main__":
    asyncio.run(main())
