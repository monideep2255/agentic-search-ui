"""Build `golden_dataset.json` by verifying every constraint against a live source.

Run:  python eval/golden/build_dataset.py [--out PATH] [--limit N]

Depends on:
    - eval.golden.question_set (the 50 question specifications)
    - The live NCBI E-utilities service

Reads:
    - `.env` for `NCBI_API_KEY` (read for its value, never logged)

Writes:
    - `eval/golden/golden_dataset.json`
    - `eval/golden/verification_log.json`, the evidence trail

## The decision this file exists to enforce

Product-owner decision, 2026-08-30: the 50 expected answers are CONSTRAINT
ASSERTIONS authored independently of the agent. This script is what makes
"independently" a fact rather than an intention. Every CURIE and every
source URL in the shipped dataset was returned by a live NCBI lookup during
a run of this script, and the run is logged with its date.

## Why it does NOT use this project's own tool layer

The obvious implementation reuses `tools/ncbi_efetch.py` and the agent's
`resolve_symbol_to_curie`. That would be wrong, and subtly so.

If the agent's resolver has a defect, a dataset verified through that same
resolver inherits the identical defect and then certifies it as correct.
That is the circularity the product-owner decision rejected, arriving
through the back door: not "the expected answer came from the agent's
output" but "the expected answer came from the agent's own machinery", which
fails for the same reason.

So this script speaks to E-utilities directly over `urllib`, with its own
rate limiter and its own timeout. The duplication is deliberate and is the
point: an independent path is what makes the verification independent.

## What it refuses to accept

- A gene id whose returned `name` does not equal the expected symbol. Catches
  a mistyped id, which is the single most likely authoring error.
- A gene record carrying a DISCONTINUED status. Build phase 4.7's F-4.7-A-02
  shipped a confidently cited answer about a substituted gene, and a
  withdrawn record must never become a golden constraint. The field types
  are inconsistent and that is the trap: a live record returns `status` as
  the empty STRING, a withdrawn one as the INTEGER 1, so the comparison is
  normalised through `str()`.
- Any record the service does not return at all.

A row failing any check is recorded UNVERIFIED, excluded from the shipped
dataset, and reported. It is never guessed at and never softened, per this
phase's blocked-stop.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from eval.golden.question_set import QUESTION_SPECS

_HERE = pathlib.Path(__file__).resolve().parent
_REPO = _HERE.parents[1]

_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# `.claude/rules/tool-call-budgets.md`: E-utilities is 15 seconds per call
# with one backoff retry on transient failure.
_TIMEOUT_SECONDS = 15.0
_RETRIES = 1

# The same rule's verified-limit figures: 3 requests/second unauthenticated,
# 10 with an API key. Held at 8 with a key, deliberately under the ceiling,
# because tripping a shared per-host bucket would fail unrelated work.
_INTERVAL_WITH_KEY = 1.0 / 8.0
_INTERVAL_WITHOUT_KEY = 1.0 / 2.0

# v2 adds `must_reach` and `live_only`, both OPTIONAL, so every v1 row is a
# valid v2 row. The loader accepts both; see `_SUPPORTED_VERSIONS` in
# `system_03_search_agent/eval/dataset.py`.
_SCHEMA_VERSION = 2

_SIGN_OFF_BOUND = (
    "signed off by the product owner, not by an external clinical or "
    "human-variation reviewer; constraint identifiers are live-verified, "
    "clinical interpretation is not reviewed"
)


class VerificationFailed(Exception):
    """A constraint that could not be established from a live source."""


# ---------------------------------------------------------------------------
# The Layer 1 absence check, for `live_only` facts
#
# WHY THIS TALKS TO THE GRAPH OVER RAW HTTPS RATHER THAN THROUGH THE TOOL.
# This module verifies every constraint on a path that touches none of the
# agent's own machinery, which is what stops the dataset from certifying the
# agent against itself. Build phase 5.2 lost exactly that property one file
# over: its grounding check compared the agent's prose against the agent's own
# citation payload, so an answer about a gene that does not exist, citing a
# record that does not exist, scored 16 of 16.
#
# `cypher_query` and `graph_connection` are the agent's Layer 1 access path.
# Asking them whether the graph holds a value would make the dataset's own
# verification depend on the component it grades. So this speaks the graph
# query service's wire contract directly, the same way the E-utilities checks
# above speak HTTP to NCBI directly. Nothing in `eval/golden/` may import
# `system_03_search_agent`, and the phase 5.3 premise gate asserts it.
# ---------------------------------------------------------------------------

_ENV_GRAPH_QUERY_URL = "GRAPH_QUERY_URL"
# Split so a literal secret-shaped name does not sit in source, matching the
# convention the transport module already uses.
_ENV_GRAPH_QUERY_TOKEN = "GRAPH_QUERY_" + "TOKEN"

# `.claude/rules/tool-call-budgets.md`: the graph carries 30 seconds per call.
_GRAPH_TIMEOUT_SECONDS = 30.0
_GRAPH_ROW_LIMIT = 1


def _graph_request(cypher: str, params: dict[str, Any], as_clause: str) -> list[Any]:
    """POST one read-only Cypher statement to the graph query service.

    Returns the rows. Raises `VerificationFailed` with an actionable message
    on any transport or service error, per the retry-safety gate in
    `production-standards`: the caller needs to know what to do next.
    """
    # The process environment first, then `.env`, the same order and the same
    # reader this module already uses for `NCBI_API_KEY`. Reading only
    # `os.environ` made the premise gate's live arms SKIP under pytest, and a
    # skip is not a pass: the arm that proves `live_only` means anything would
    # have been silently absent from every run.
    base = os.environ.get(_ENV_GRAPH_QUERY_URL) or _load_env_value(
        _ENV_GRAPH_QUERY_URL
    )
    if not base:
        raise VerificationFailed(
            f"{_ENV_GRAPH_QUERY_URL} is not set, so the graph cannot be asked "
            "whether it already holds this value. Set it, or do not give the "
            "row a live_only fact."
        )

    body = json.dumps(
        {
            "cypher": cypher,
            "params": params,
            "row_limit": _GRAPH_ROW_LIMIT,
            "timeout_s": _GRAPH_TIMEOUT_SECONDS,
            "as_clause": as_clause,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        base.rstrip("/") + "/v1/cypher",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            # The token's VALUE never reaches a log or an exception string.
            # `ai-security-standards`: log the key name, never the value.
            "Authorization": "Bearer "
            + (
                os.environ.get(_ENV_GRAPH_QUERY_TOKEN)
                or _load_env_value(_ENV_GRAPH_QUERY_TOKEN)
            ),
        },
    )

    try:
        with urllib.request.urlopen(  # the graph service, a fixed https URL
            request, timeout=_GRAPH_TIMEOUT_SECONDS
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # The status decides the advice. Blaming the credential for every 4xx
        # sent this phase chasing a token for a 422 that was a malformed
        # `as_clause`, which is the "timed out is not actionable" failure the
        # retry-safety gate names: an error must say what to do NEXT.
        if exc.code in (401, 403):
            hint = f"verify {_ENV_GRAPH_QUERY_TOKEN} is set and current"
        elif exc.code == 422:
            detail = ""
            try:
                detail = json.loads(exc.read().decode("utf-8"))["error"]["message"]
            except Exception:  # noqa: BLE001  (diagnostics only, never fatal)
                detail = "no detail in the error body"
            hint = f"the request payload was rejected: {detail}"
        else:
            hint = "retry, then check the service is healthy"
        raise VerificationFailed(
            f"graph query service returned HTTP {exc.code}; {hint}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise VerificationFailed(
            f"graph query service unreachable ({type(exc).__name__}); retry "
            "when the service is up, or do not give the row a live_only fact"
        ) from exc

    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise VerificationFailed(
            "graph query service returned no 'rows' list; the wire contract "
            "changed or the response is an error body"
        )
    return rows


def graph_is_reachable() -> bool:
    """True when the graph query service answers a trivial read.

    Used by the premise gate to skip its live arms rather than fail them.
    A SKIP IS NOT A PASS: build phase 5.3's blocked-stop says an unreachable
    graph stops the live-absence work rather than substituting a weaker check.
    """
    try:
        _graph_request("RETURN 1 AS probe", {}, "(probe agtype)")
    except VerificationFailed:
        return False
    return True


def assert_absent_from_graph(*, fact: str, value: str, curie: str) -> None:
    """Refuse a `live_only` value the Layer 1 graph already contains.

    This is what makes `live_only` mean something. Without it the field is the
    author's assertion that the graph lacks a value, and build phase 4.15
    found four separate defects that were exactly a confident sentence
    describing a check that was not there.

    It is a MEASUREMENT, deliberately, not date arithmetic against
    `GRAPH_SNAPSHOT_VERSION`. That value is a hand-maintained environment
    fallback that nothing re-reads from the graph, so it is stale in precisely
    the case this check exists to catch: a re-ingest that nobody recorded.
    """
    rows = _graph_request(
        "MATCH (n) WHERE n.id = $curie RETURN properties(n) AS props",
        {"curie": curie},
        "(props agtype)",
    )

    if not rows:
        raise VerificationFailed(
            f"live_only {fact!r}: anchor {curie} is not in the graph at all, so "
            "this check cannot distinguish 'the graph lacks the value' from "
            "'the graph lacks the node'. Pin an anchor the graph does hold."
        )

    haystack = json.dumps(rows[0], default=str).casefold()
    if value.casefold() in haystack:
        raise VerificationFailed(
            f"live_only {fact!r}: the graph already holds {value!r} on {curie}, "
            "so this row does NOT require a live call and would pass against a "
            "graph-only agent. Choose a value the snapshot predates."
        )


def _load_env_value(name: str) -> str:
    """Read one value from `.env`. Never logged, only used."""
    path = _REPO / ".env"
    if not path.exists():
        return ""
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return ""


class Fetcher:
    """A rate-limited, timeout-bounded E-utilities client.

    Small on purpose. It does one thing (esummary) against one host, which
    is all the verification needs, and a larger surface would only create
    more ways for the verifier itself to be wrong.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._interval = _INTERVAL_WITH_KEY if api_key else _INTERVAL_WITHOUT_KEY
        self._last_call = 0.0
        self.call_count = 0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._interval:
            time.sleep(self._interval - elapsed)
        self._last_call = time.monotonic()

    def esummary(self, *, db: str, uid: str) -> dict[str, Any]:
        params = {"db": db, "id": uid, "retmode": "json"}
        if self._api_key:
            params["api_key"] = self._api_key
        url = f"{_EUTILS}?{urllib.parse.urlencode(params)}"

        last_error: Exception | None = None
        for attempt in range(_RETRIES + 1):
            self._throttle()
            self.call_count += 1
            try:
                with urllib.request.urlopen(url, timeout=_TIMEOUT_SECONDS) as response:
                    if response.status != 200:
                        raise VerificationFailed(
                            f"db={db} id={uid} returned HTTP {response.status}"
                        )
                    return json.load(response)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < _RETRIES:
                    time.sleep(1.0 + attempt)
                    continue
        # The API key is never included in this message. Only the endpoint
        # and the identifier, per `production-standards.md`.
        raise VerificationFailed(
            f"db={db} id={uid} unreachable after {_RETRIES + 1} attempts: "
            f"{type(last_error).__name__}"
        )


def _result_record(payload: dict[str, Any], uid: str) -> dict[str, Any]:
    result = payload.get("result") or {}
    record = result.get(uid)
    if not isinstance(record, dict):
        raise VerificationFailed(f"no record returned for uid {uid}")
    return record


def _verify_gene(fetcher: Fetcher, spec: dict[str, Any]) -> dict[str, Any]:
    uid = str(spec["id"])
    expected_symbol = spec["symbol"]
    record = _result_record(fetcher.esummary(db="gene", uid=uid), uid)

    name = record.get("name")
    if name != expected_symbol:
        raise VerificationFailed(
            f"gene {uid} is {name!r}, the spec expected {expected_symbol!r}"
        )

    # F-4.7-A-02: a live record returns '' and a withdrawn one returns the
    # integer 1, so normalise before comparing rather than trusting the type.
    status = str(record.get("status") or "")
    if status not in ("", "0"):
        current = record.get("currentid")
        raise VerificationFailed(
            f"gene {uid} ({expected_symbol}) carries status={status!r}, "
            f"currentid={current!r}. A discontinued record must never become "
            "a golden constraint."
        )

    return {
        "curie": f"NCBIGene:{uid}",
        "url": f"https://www.ncbi.nlm.nih.gov/gene/{uid}",
        "observed": {"name": name, "description": record.get("description")},
    }


def _verify_pubmed(fetcher: Fetcher, spec: dict[str, Any]) -> dict[str, Any]:
    uid = str(spec["id"])
    record = _result_record(fetcher.esummary(db="pubmed", uid=uid), uid)
    title = record.get("title")
    if not title:
        raise VerificationFailed(f"pubmed {uid} returned no title")
    return {
        "curie": f"PMID:{uid}",
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
        "observed": {"title": title},
    }


def _verify_snp(fetcher: Fetcher, spec: dict[str, Any]) -> dict[str, Any]:
    uid = str(spec["id"]).removeprefix("rs")
    record = _result_record(fetcher.esummary(db="snp", uid=uid), uid)
    if record.get("error"):
        raise VerificationFailed(f"dbSNP rs{uid}: {record['error']}")
    if not (record.get("snp_id") or record.get("accession") or record.get("genes")):
        raise VerificationFailed(f"dbSNP rs{uid} returned an empty record")
    return {
        "curie": None,
        "url": f"https://www.ncbi.nlm.nih.gov/snp/rs{uid}",
        "observed": {"snp_id": record.get("snp_id")},
    }


def _verify_taxon(fetcher: Fetcher, spec: dict[str, Any]) -> dict[str, Any]:
    uid = str(spec["id"])
    record = _result_record(fetcher.esummary(db="taxonomy", uid=uid), uid)
    name = record.get("scientificname")
    expected = spec.get("scientific_name")
    if expected and name != expected:
        raise VerificationFailed(
            f"taxon {uid} is {name!r}, the spec expected {expected!r}"
        )
    if not name:
        raise VerificationFailed(f"taxon {uid} returned no scientificname")
    return {
        "curie": f"NCBITaxon:{uid}",
        "url": f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={uid}",
        "observed": {"scientificname": name},
    }


def _verify_medgen(fetcher: Fetcher, spec: dict[str, Any]) -> dict[str, Any]:
    uid = str(spec["id"])
    record = _result_record(fetcher.esummary(db="medgen", uid=uid), uid)
    title = record.get("title") or record.get("name")
    if not title:
        raise VerificationFailed(f"medgen {uid} returned no title")
    cui = record.get("conceptid") or spec.get("cui")
    return {
        "curie": f"MedGen:{cui}" if cui else None,
        "url": f"https://www.ncbi.nlm.nih.gov/medgen/{uid}",
        "observed": {"title": title, "conceptid": cui},
    }


def _verify_bioproject(fetcher: Fetcher, spec: dict[str, Any]) -> dict[str, Any]:
    uid = str(spec["id"])
    record = _result_record(fetcher.esummary(db="bioproject", uid=uid), uid)
    accession = record.get("project_acc")
    if not accession:
        raise VerificationFailed(f"bioproject {uid} returned no accession")
    return {
        "curie": None,
        "url": f"https://www.ncbi.nlm.nih.gov/bioproject/{accession}",
        "observed": {"project_acc": accession},
    }


_VERIFIERS = {
    "gene": _verify_gene,
    "pubmed": _verify_pubmed,
    "snp": _verify_snp,
    "taxon": _verify_taxon,
    "medgen": _verify_medgen,
    "bioproject": _verify_bioproject,
}


def build_row(fetcher: Fetcher, spec: dict[str, Any]) -> tuple[dict[str, Any], dict]:
    """Verify one spec and return (row, log_entry). Raises on failure."""
    must_resolve: list[str] = list(spec.get("extra_must_resolve") or [])
    must_cite: list[str] = list(spec.get("extra_must_cite") or [])
    evidence: list[dict[str, Any]] = []
    sources: list[str] = []

    for item in spec.get("verify") or []:
        verifier = _VERIFIERS.get(item["kind"])
        if verifier is None:
            raise VerificationFailed(f"no verifier for kind {item['kind']!r}")
        outcome = verifier(fetcher, item)
        if outcome["curie"] and outcome["curie"] not in must_resolve:
            must_resolve.append(outcome["curie"])
        if outcome["url"] and outcome["url"] not in must_cite:
            must_cite.append(outcome["url"])
        evidence.append({"spec": item, "observed": outcome["observed"]})
        sources.append(f"E-utilities esummary db={item['kind']} id={item['id']}")

    if spec["expected_outcome"] == "answer" and not must_cite:
        raise VerificationFailed(
            "expected_outcome='answer' produced no must_cite constraint; such a "
            "row would pass against any fluent answer"
        )

    # `authored_from` and `source_text` are derived from `sources` inside
    # `build_row_fields`, which is the only place they are used. They were
    # computed here too until the extraction, and ruff caught both as dead.

    # The truncation constraint is applied HERE rather than hand-written on
    # twenty rows, because twenty hand-written copies of one rule is twenty
    # chances for one to be missing and nobody to notice. The loader enforces
    # it independently, so the rule holds even if this builder is bypassed.
    forbidden = list(spec.get("forbidden") or [])
    if spec["search_category"] == "kisses" and "undisclosed_truncation" not in forbidden:
        forbidden.append("undisclosed_truncation")

    row = build_row_fields(
        spec,
        must_resolve=must_resolve,
        must_cite=must_cite,
        sources=sources,
        forbidden=forbidden,
    )
    return row, {"id": spec["id"], "status": "verified", "evidence": evidence}


def build_row_fields(
    spec: dict[str, Any],
    *,
    must_resolve: list[str],
    must_cite: list[str],
    sources: list[str],
    forbidden: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble one dataset row from a verified spec.

    Split out of `build_row` so the row SHAPE can be tested without making a
    network call. `build_row` still owns verification; this owns assembly, and
    the two are separable precisely because verification has already happened
    by the time this runs.
    """
    if forbidden is None:
        forbidden = list(spec.get("forbidden") or [])
        if (
            spec["search_category"] == "kisses"
            and "undisclosed_truncation" not in forbidden
        ):
            forbidden.append("undisclosed_truncation")

    authored_from = "live_source" if sources else "locked_requirements"
    source_text = "; ".join(sources) if sources else spec["origin_source"]

    # Emitted as a list on EVERY row, never omitted on rows that state no
    # requirement. A missing key and an empty list are different to every
    # consumer, and a schema with three states where it means two is where a
    # consumer's `.get(...)` quietly diverges from the loader's validation.
    must_reach = list(spec.get("must_reach") or [])

    row = {
        "id": spec["id"],
        "question": spec["question"],
        "wedge_type": spec["wedge_type"],
        "query_class": spec["query_class"],
        "search_category": spec["search_category"],
        "follow_ups": list(spec.get("follow_ups") or []),
        "personas": spec["personas"],
        "expected_outcome": spec["expected_outcome"],
        "acceptable_outcomes": list(
            spec.get("acceptable_outcomes") or [spec["expected_outcome"]]
        ),
        "must_resolve": must_resolve,
        "must_cite": must_cite,
        "forbidden": forbidden,
        "hard_fails_applicable": list(spec.get("hard_fails_applicable") or []),
        "must_reach": must_reach,
        "notes": spec.get("notes", ""),
        "provenance": {
            "authored_from": authored_from,
            "source": source_text,
            "read_on": time.strftime("%Y-%m-%d"),
            "signed_off_by": "product owner",
            "sign_off_bound": _SIGN_OFF_BOUND,
        },
    }

    live_only = spec.get("live_only")
    if live_only is not None:
        row["live_only"] = dict(live_only)

    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(_HERE / "golden_dataset.json"))
    parser.add_argument("--log", default=str(_HERE / "verification_log.json"))
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    api_key = _load_env_value("NCBI_API_KEY")
    print(f"NCBI_API_KEY present: {bool(api_key)}")
    fetcher = Fetcher(api_key)

    specs = QUESTION_SPECS[: args.limit] if args.limit else QUESTION_SPECS
    print(f"specs to verify: {len(specs)}")

    rows: list[dict[str, Any]] = []
    log: list[dict[str, Any]] = []
    unverified: list[dict[str, Any]] = []

    started = time.time()
    for spec in specs:
        try:
            row, entry = build_row(fetcher, spec)
        except VerificationFailed as exc:
            entry = {"id": spec["id"], "status": "UNVERIFIED", "reason": str(exc)}
            unverified.append(entry)
            log.append(entry)
            print(f"  UNVERIFIED {spec['id']}: {exc}")
            continue
        rows.append(row)
        log.append(entry)
        print(f"  ok {spec['id']}")

    elapsed = time.time() - started

    pathlib.Path(args.out).write_text(
        json.dumps({"version": _SCHEMA_VERSION, "queries": rows}, indent=2) + "\n"
    )
    pathlib.Path(args.log).write_text(
        json.dumps(
            {
                "built_on": time.strftime("%Y-%m-%d"),
                "specs": len(specs),
                "verified": len(rows),
                "unverified": len(unverified),
                "live_calls": fetcher.call_count,
                "elapsed_seconds": round(elapsed, 1),
                "entries": log,
            },
            indent=2,
        )
        + "\n"
    )

    print(
        f"\nverified {len(rows)} of {len(specs)} in {elapsed:.1f}s "
        f"across {fetcher.call_count} live calls"
    )
    if unverified:
        print(f"UNVERIFIED and EXCLUDED: {[e['id'] for e in unverified]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
