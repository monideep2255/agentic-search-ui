---
name: python-code-standards
description: Python coding standards for the agentic-search-data-engineering project. Adapted from the ncbi_ai_agents reference repo for ETL/KG context. Strip out async/orchestrator content - this is a data pipelines repo, not a search agent.
---

# Python code standards

These standards apply to all Python code in this repo (System 1 ETL pipelines and System 2 graph loaders). System 3 lives in a separate repo and is not in scope here.

## Formatting

Black + Ruff + isort. Line length 100. Target Python 3.11.

```toml
# pyproject.toml
[tool.black]
line-length = 100
target-version = ['py311']

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "W"]

[tool.isort]
profile = "black"
line_length = 100
```

Pre-commit checks (run before every commit):

```bash
ruff check .
black --check .
mypy system-01-data-pipelines/ system-02-knowledge-graph/
```

## Type hints

Required on every function signature, public and internal. No `Any` unless genuinely opaque (e.g. `Dict[str, Any]` from a JSON response is fine).

```python
def parse_clinvar_chunk(
    chunk: pd.DataFrame,
    gene_symbols: set[str],
    config: PipelineConfig,
) -> pd.DataFrame:
    """..."""
```

Use `from __future__ import annotations` at the top of every file so forward references work without quoting.

## Docstrings (Google style)

Required on all public functions and modules. Include Args, Returns, Raises, and a short Example for non-trivial functions.

```python
def download_file(url: str, dest: Path, force: bool = False) -> Path:
    """Download a file from a URL with idempotent caching.

    Args:
        url: The full URL to download (HTTP or FTP).
        dest: Destination path. Parent directories must exist.
        force: If True, re-download even if dest already exists.

    Returns:
        The destination path (same as `dest` arg).

    Raises:
        urllib.error.URLError: On network failure after retries.

    Example:
        >>> path = download_file(
        ...     "https://ftp.ncbi.nlm.nih.gov/gene/DATA/gene_info.gz",
        ...     Path("./cache/gene_info.gz"),
        ... )
    """
```

## Architectural patterns for ETL

### 1. Idempotent steps

Every pipeline step must be safe to re-run. Cache downloads, skip work that has been done, write to temp files and atomic-rename.

```python
# CORRECT: skip if cached
if dest.exists() and not force:
    logger.info("Cache hit: %s", dest.name)
    return dest

# INCORRECT: always re-download
urllib.request.urlretrieve(url, dest)
```

### 2. Provenance on every node and edge

Never produce a node or edge without `source`, `source_url`, and (for edges) evidence fields. This is the trust moat - it is non-negotiable.

```python
# CORRECT
node = {
    "id": "NCBIGene:672",
    "category": "biolink:Gene",
    "name": "BRCA1",
    "source": "NCBI Gene",
    "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
    "xrefs": ["HGNC:1100", "Ensembl:ENSG00000012048"],
}

# INCORRECT - no provenance
node = {"id": "NCBIGene:672", "name": "BRCA1"}
```

### 3. Validate, do not silently discard

Every record that fails validation must be logged with the reason. Never drop records silently.

```python
# CORRECT
for record in records:
    try:
        validate(record)
        yield record
    except ValidationError as exc:
        logger.warning("rejected %s: %s", record.get("id"), exc)
        rejected_count += 1

# INCORRECT
yield from (r for r in records if is_valid(r))
```

### 4. Configuration via dataclass

Match the canonical reference pipeline pattern. One `PipelineConfig` dataclass with sensible defaults, `__post_init__` to create directories.

```python
@dataclass
class PipelineConfig:
    output_dir: Path = Path("./data/kgx")
    cache_dir: Path = Path("./data/ftp_cache")
    ncbi_email: str = ""
    ncbi_api_key: str = ""
    chunk_size: int = 200_000

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir)
        self.cache_dir = Path(self.cache_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
```

## Error handling

### Specific exception types

```python
class DownloadError(Exception):
    """Raised when an FTP/HTTP download fails after retries."""

class ValidationError(Exception):
    """Raised when a record fails BioLink schema validation."""

class CrossReferenceError(Exception):
    """Raised when a cross-database identifier resolution fails."""
```

### Retry with exponential backoff

For NCBI Entrez and FTP calls. Match the canonical reference pipeline pattern at `reference/ncbi_ai_agents-ncbi-kg/KG/pipeline/src/glucose_metabolism_kg/utils.py:35-86`.

```python
def entrez_with_retry(
    func: Callable[..., Any],
    *args: Any,
    retries: int = 3,
    base_sleep: float = 0.35,
    **kwargs: Any,
) -> Any:
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            wait = base_sleep * (2 ** attempt)
            logger.warning("attempt %d failed (%s); retrying in %.1fs", attempt + 1, exc, wait)
            time.sleep(wait)
    raise RuntimeError(f"all {retries} attempts failed")
```

### Structured logging

Use the `extra` keyword to attach context. Logs will be parsed downstream.

```python
logger.error(
    "Pipeline step failed",
    extra={
        "step": "clinvar_parse",
        "database": "clinvar",
        "input_file": str(path),
        "error_type": type(exc).__name__,
    },
)
```

## Performance

### Rate limiting for NCBI Entrez

Respect NCBI's policy: 3 req/sec without API key, 10 req/sec with key. Sleep between requests.

```python
class RateLimitedEntrez:
    def __init__(self, requests_per_second: float = 3.0) -> None:
        self.min_interval = 1.0 / requests_per_second
        self._last_request_time = 0.0

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_time = time.time()
```

### Chunked processing for large files

ClinVar `variant_summary.txt.gz` is hundreds of MB. PubMed baseline is 30GB. Never load these into memory at once.

```python
with gzip.open(path, "rt") as f:
    reader = pd.read_csv(f, sep="\t", chunksize=200_000, low_memory=False)
    for chunk in reader:
        filtered = chunk[chunk["GeneSymbol"].isin(gene_symbols)]
        if len(filtered):
            yield filtered
```

## Security

### Environment variables only

```python
# CORRECT
NCBI_API_KEY = os.getenv("NCBI_API_KEY")
if not NCBI_API_KEY:
    raise ValueError("NCBI_API_KEY environment variable not set")

# INCORRECT
NCBI_API_KEY = "abc123..."  # NEVER hardcode
```

### Parameterized SQL for AGE

```python
# CORRECT - parameterized
cur.execute(
    "SELECT * FROM cypher('ncbi_kg', $$ MATCH (n:Gene {id: $gene_id}) RETURN n $$, %s) AS (n agtype);",
    (json.dumps({"gene_id": gene_id}),),
)

# INCORRECT - string interpolation
cur.execute(f"SELECT * FROM cypher('ncbi_kg', $$ MATCH (n:Gene {{id: '{gene_id}'}}) RETURN n $$) AS (n agtype);")
```

### Input validation at boundaries

Trust internal code. Validate only at system boundaries: user input, NCBI API responses, FTP file contents.

```python
def validate_curie(curie: str) -> str:
    """Ensure a string is a well-formed CURIE."""
    if not curie or ":" not in curie:
        raise ValueError(f"not a CURIE: {curie!r}")
    prefix, _, local = curie.partition(":")
    if not prefix.replace("_", "").isalnum():
        raise ValueError(f"invalid CURIE prefix: {prefix!r}")
    return curie
```

## Usage

When writing or reviewing Python code in this repo, use this skill to verify formatting, type hints, docstrings, error handling, performance patterns, and security. For ETL-specific patterns (idempotency, provenance, validation discipline), this is the source of truth.
