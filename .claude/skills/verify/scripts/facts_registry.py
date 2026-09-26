"""The registry of facts System 3's web app states about itself.

Read by `check_facts.py` in this directory, which holds every computation;
this file only declares. One `Fact` per claim:

  - `truth`: how the true value is computed from its ONE source.
  - `stated`: every place a screen states it (a file and a pattern).
  - `downstream`: every document, or code copy, that restates it.

A change to a fact's source should name every place to update, so
`check_facts.py --map --from <source file>` walks this list the way the
owner's maintenance skill walks `depended_by`.

ADDING A FACT. Find the one source first (a constant, a `Literal`, a table
in the graph owner's reference). If the only place the value lives is a
second copy, say so in the fact's `what` and pick the copy the product
actually runs on. Then add every place that states it, and run
`check_facts.py --self-test`: it fails unless every new place can both
pass and fail.

THE PLACES are named the way a person reaching them would: the screen's
title, or "document" and "code copy" for restatements outside the app.
"""

from __future__ import annotations

import ast
import datetime
import json
import re
import tomllib

from check_facts import (
    BOOL,
    COUNT,
    EXACT,
    MAPPING,
    MEMBER,
    MILLIONS,
    MONTH,
    SET,
    STEPS,
    SUBSET,
    THOUSANDS,
    Computed,
    Fact,
    PyConst,
    PyFieldKw,
    PyFields,
    PyLiteral,
    RegistryError,
    Repo,
    TextMatch,
    Truth,
    Where,
    checked_by_code_alone,
    g,
    line_of,
    merge_dicts,
    offsets,
    parse_python,
    present,
    quoted,
    step_calls_no_model,
    step_names,
    step_uses_tier,
    steps_reaching_model,
    swap,
    to_date,
    to_int,
    union,
    words_list,
)

S = re.DOTALL

# ------------------------------------------------------------------ places

ABOUT = "About"
ARCH = "Architecture"
ARCH_ABOUT = "Architecture and About"
INTEGRATIONS = "Integrations"
HOME = "Home"
TOUR = "Onboarding tour"
RUN = "Run screen"
BANNER = "Refusal banner"
DOC = "document"
CODE = "code copy"

# ------------------------------------------------------------------ files

INFO = "frontend/src/components/screens/InfoScreens.tsx"
ARCH_TSX = "frontend/src/components/screens/ArchitectureScreen.tsx"
FACTS_TS = "frontend/src/lib/architectureFacts.ts"
HOME_TSX = "frontend/src/components/screens/HomeScreen.tsx"
TOUR_TSX = "frontend/src/components/tour/OnboardingTour.tsx"
RUN_TSX = "frontend/src/components/screens/RunProgress.tsx"
DEPTH_TSX = "frontend/src/components/controls/DepthControl.tsx"
EVENTS_TS = "frontend/src/lib/events.ts"
BANNER_TSX = "frontend/src/components/chat/GuardrailBanner.tsx"

CLAUDE_MD = "CLAUDE.md"
AGENTS_MD = "AGENTS.md"
README = "README.md"
MODEL_ARCH = "docs/architecture/Model_architecture.md"
DEEP_DIVE = "visualizations/System_3_deep_dive.md"
ARCH_DIAGRAM = "visualizations/Architecture_diagram.md"
SCHEMA_VIS = "visualizations/Schema_visualization.md"

PKG = "src/system_03_search_agent"
EVENTS_PY = f"{PKG}/contracts/events.py"
QUERY_PY = f"{PKG}/contracts/query.py"
TRANSPORT = f"{PKG}/tools/ncbi_transport.py"
PATHOGEN_FTP = f"{PKG}/tools/pathogen_ftp_transport.py"
GRAPH_CONSTS = f"{PKG}/tools/graph_schema_constants.py"
CYPHER_QUERY = f"{PKG}/tools/cypher_query.py"
PATHOGEN = f"{PKG}/tools/pathogen_detection.py"
CATALOGUE = f"{PKG}/tools/catalogue.py"
CALL_BUDGET = f"{PKG}/harness/call_budget.py"
TIERS_PY = f"{PKG}/harness/tiers.py"
MCP_SERVER = f"{PKG}/adapters/mcp/server.py"
GRAPHQL_CONTEXT = f"{PKG}/adapters/graphql/context.py"
WEB_APP = f"{PKG}/adapters/web_sse/app.py"
AUTH_ROUTER = f"{PKG}/auth/router.py"
PERSONAS = f"{PKG}/data/personas_v1.json"
GOLDEN = "eval/golden/golden_dataset.json"
PYPROJECT = "pyproject.toml"

KG_REF = "ref:docs/Knowledge_graph_on_server_reference.md"
REF_CLAUDE = "ref:CLAUDE.md"

# The two canonical instruction files carry the same text; AGENTS.md is
# generated from CLAUDE.md, and both are checked so a stale regeneration shows.
INSTRUCTION_FILES = (CLAUDE_MD, AGENTS_MD)

# ------------------------------------------------------------------ vocabularies

# How a page names each live API family. The families themselves come from
# `ncbi_transport._LAYER_BY_FAMILY` plus the Pathogen Detection FTP transport;
# a family with no entry here is a registry ERROR, so a new API cannot slip
# past unnamed.
FAMILY_NAMES: dict[str, tuple[str, ...]] = {
    "eutils": ("E-utilities", "EFetch", "ELink", "ESearch", "ESummary"),
    "datasets": ("Datasets",),
    "pubchem": ("PubChem",),
    "variation": ("dbSNP", "Variation Services"),
    "pathogen_ftp": ("Pathogen Detection",),
    "pubtator": ("PubTator3", "PubTator"),
    "litvar2": ("LitVar2", "LitVar"),
    "clinicaltrials": ("ClinicalTrials.gov",),
}
# Names a document uses for an API no code calls. Finding one is stale.
NOT_CALLED = ("LitSense",)

# How a page names each programmatic surface in `RequestContext.surface`.
SURFACE_NAMES: dict[str, tuple[str, ...]] = {
    "rest_sse": ("REST", "the API"),
    "graphql": ("GraphQL",),
    "mcp": ("MCP",),
    "cli": ("command line", "Command line", "the export"),
}

# The answer mode labels a sentence may name. The labels themselves come
# from DepthControl.tsx; one missing here reads as "not named" and fails.
MODE_NAMES = ("Plain language", "Researcher")

# ------------------------------------------------------------------ parsers


def named_families(match: re.Match[str]) -> frozenset[str]:
    """The API families a sentence names, each by its first display name, so
    a report says "PubChem" rather than a transport key."""
    text = match.group(1)
    found = {names[0] for names in FAMILY_NAMES.values() if any(n in text for n in names)}
    found |= {f"{n} (no code calls it)" for n in NOT_CALLED if n in text}
    return frozenset(found)


def named_surfaces(match: re.Match[str]) -> frozenset[str]:
    text = match.group(1)
    return frozenset(names[0] for names in SURFACE_NAMES.values() if any(n in text for n in names))


def ts_union(match: re.Match[str]) -> frozenset[str]:
    return frozenset(quoted(match.group(1)))


def ts_keys(match: re.Match[str]) -> frozenset[str]:
    return frozenset(re.findall(r"^\s+(\w+):", match.group(1), re.MULTILINE))


def word_set(match: re.Match[str]) -> frozenset[str]:
    return frozenset(words_list(match.group(1)))


def ts_layers(field: str):
    """Parse a TS array of `{ n: 1, ... }` layer objects into layer -> set of
    `field` values (a tools string, or tool names)."""

    def parse(match: re.Match[str]) -> dict[int, frozenset[str]]:
        chunks = re.split(r"\bn: (\d)\b", match.group(1))
        layers: dict[int, frozenset[str]] = {}
        for number, chunk in zip(chunks[1::2], chunks[2::2]):
            if field == "tools":
                values = re.findall(r'tools: "([^"]+)"', chunk)
                names = {t.strip() for v in values for t in v.split(",")}
            else:
                # A tool name has an underscore; a layer's own title does not.
                names = set(re.findall(rf'{field}: "([a-z][a-z0-9]*_[a-z0-9_]+)"', chunk))
            layers[int(number)] = frozenset(names)
        return layers

    return parse


def layer_calls(layer: int):
    """The family names in a TS layers array's `calls:` strings for one layer."""

    def parse(match: re.Match[str]) -> frozenset[str]:
        chunks = re.split(r"\bn: (\d)\b", match.group(1))
        for number, chunk in zip(chunks[1::2], chunks[2::2]):
            if int(number) == layer:
                calls = " ".join(re.findall(r'calls: "([^"]+)"', chunk))
                return named_families(re.match(r"(.*)", calls, S))
        raise ValueError(f"no layer {layer}")

    return parse


def modes_named(match: re.Match[str]) -> frozenset[str]:
    return frozenset(m for m in MODE_NAMES if m in match.group(0))


# ------------------------------------------------------------------ computed truths


def _kg_table(repo: Repo) -> tuple[dict[str, int], dict[str, str], int]:
    """Section D of the graph reference: label -> rows, label -> source, for
    the labels with an exact count."""
    text = repo.text(KG_REF)
    section = re.search(r"## D\. Vertex labels and counts(.*?)\n## E\.", text, S)
    if section is None:
        raise RegistryError(f"{KG_REF}: no Section D table")
    rows: dict[str, int] = {}
    sources: dict[str, str] = {}
    for m in re.finditer(r"^\| (\w+) \| ([\d,]+) \| ([^|]+) \|", section.group(1), re.MULTILINE):
        rows[m.group(1)] = int(m.group(2).replace(",", ""))
        sources[m.group(1)] = m.group(3).strip()
    return rows, sources, line_of(text, section.start())


def _kg_total(repo: Repo) -> int:
    text = repo.text(KG_REF)
    m = re.search(r"It contains ([\d,]+) nodes", text)
    if m is None:
        raise RegistryError(f"{KG_REF}: no node total")
    return int(m.group(1).replace(",", ""))


def _kg_vertex_labels(repo: Repo) -> int:
    m = re.search(r"across (\d+) vertex labels", repo.text(KG_REF))
    if m is None:
        raise RegistryError(f"{KG_REF}: no vertex label count")
    return int(m.group(1))


def per_database_nodes(repo: Repo) -> Truth:
    rows, _, line = _kg_table(repo)
    return Truth(rows, KG_REF, line)


def minor_label_nodes(repo: Repo) -> Truth:
    rows, _, line = _kg_table(repo)
    return Truth(
        _kg_total(repo) - sum(rows.values()),
        KG_REF,
        line,
        "the total less the five labels with exact counts",
    )


def minor_label_count(repo: Repo) -> Truth:
    rows, _, line = _kg_table(repo)
    return Truth(_kg_vertex_labels(repo) - len(rows), KG_REF, line)


def gene_rows(repo: Repo) -> Truth:
    rows, _, line = _kg_table(repo)
    return Truth(rows["Gene"], KG_REF, line)


def pipeline_steps(repo: Repo) -> Truth:
    text = repo.text(REF_CLAUDE)
    block = re.search(r"## Pipeline pattern.*?```(.*?)```", text, S)
    if block is None:
        raise RegistryError(f"{REF_CLAUDE}: no pipeline pattern block")
    return Truth(
        tuple(re.findall(r"Step \d: (\w+)", block.group(1))),
        REF_CLAUDE,
        line_of(text, block.start()),
    )


def tool_layers(repo: Repo) -> Truth:
    """layer number -> the tools that declare it. Each tool's module declares
    its own `layer="..."`; `cypher_query` is declared where Plan builds its
    call, in core/graph.py."""
    tools = PyLiteral(EVENTS_PY, "ToolName").read(repo).value
    layers: dict[int, set[str]] = {}
    for tool in tools:
        text = repo.text(f"{PKG}/tools/{tool}.py")
        m = re.search(r'\blayer="layer_(\d)_\w+"', text)
        if m is None:
            m = re.search(
                rf'tool="{tool}".{{0,200}}?layer="layer_(\d)_\w+"',
                repo.text(f"{PKG}/core/graph.py"),
                S,
            )
        if m is None:
            raise RegistryError(f"{tool}: no layer declaration found")
        layers.setdefault(int(m.group(1)), set()).add(tool)
    return Truth(
        {k: frozenset(v) for k, v in layers.items()},
        EVENTS_PY,
        PyLiteral(EVENTS_PY, "ToolName").read(repo).line,
    )


def tools_in_layer(layer: int):
    def read(repo: Repo) -> Truth:
        truth = tool_layers(repo)
        return Truth(tuple(sorted(truth.value.get(layer, ()))), truth.path, truth.line)

    return read


def api_families(layer: int):
    """The live API families a layer calls: the transport's family table,
    plus the Pathogen Detection FTP transport, which is Layer 2 because
    `pathogen_detection` declares it so."""

    def read(repo: Repo) -> Truth:
        table = PyConst(TRANSPORT, "_LAYER_BY_FAMILY").read(repo)
        families = dict(table.value)
        if "PATHOGEN_FTP_BASE" in repo.text(PATHOGEN_FTP):
            pathogen_layer = next(
                n for n, tools in tool_layers(repo).value.items() if "pathogen_detection" in tools
            )
            families["pathogen_ftp"] = pathogen_layer
        unnamed = set(families) - set(FAMILY_NAMES)
        if unnamed:
            raise RegistryError(
                f"{TRANSPORT}: API families with no display name in the registry: {sorted(unnamed)}"
            )
        chosen = frozenset(FAMILY_NAMES[k][0] for k, n in families.items() if n == layer)
        return Truth(chosen, TRANSPORT, table.line)

    return read


def programmatic_surfaces(repo: Repo) -> Truth:
    truth = PyLiteral(QUERY_PY, "surface", cls="RequestContext", drop=("web_ui",)).read(repo)
    unnamed = set(truth.value) - set(SURFACE_NAMES)
    if unnamed:
        raise RegistryError(
            f"{QUERY_PY}: surfaces with no display name in the registry: {sorted(unnamed)}"
        )
    return Truth(tuple(SURFACE_NAMES[k][0] for k in truth.value), truth.path, truth.line)


def mcp_tools(repo: Repo) -> Truth:
    tree = parse_python(repo, MCP_SERVER)
    names = tuple(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(
            isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "tool"
            for d in node.decorator_list
        )
    )
    return Truth(names, MCP_SERVER, 1)


def console_scripts(repo: Repo) -> Truth:
    text = repo.text(PYPROJECT)
    scripts = tomllib.loads(text).get("project", {}).get("scripts", {})
    return Truth(tuple(sorted(scripts)), PYPROJECT, line_of(text, text.find("[project.scripts]")))


def _routes(repo: Repo, path: str, owner: str) -> tuple[str, ...]:
    tree = parse_python(repo, path)
    prefix = ""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", "") == "APIRouter"
        ):
            for kw in node.value.keywords:
                if kw.arg == "prefix":
                    prefix = ast.literal_eval(kw.value)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in node.decorator_list:
                if (
                    isinstance(d, ast.Call)
                    and isinstance(d.func, ast.Attribute)
                    and isinstance(d.func.value, ast.Name)
                    and d.func.value.id == owner
                    and d.args
                    and isinstance(d.args[0], ast.Constant)
                ):
                    found.append(prefix + d.args[0].value)
    return tuple(found)


def auth_routes(repo: Repo) -> Truth:
    return Truth(_routes(repo, AUTH_ROUTER, "router"), AUTH_ROUTER, 1)


def has_route(route: str):
    def read(repo: Repo) -> Truth:
        routes = _routes(repo, WEB_APP, "app")
        text = repo.text(WEB_APP)
        return Truth(route in routes, WEB_APP, line_of(text, max(text.find(f'"{route}"'), 0)))

    return read


def marker(path: str, pattern: str, meaning: str):
    """A yes-or-no truth: does the source still contain the construct that
    makes the claim true. Weaker than a computed value, so each names what
    the construct means."""

    def read(repo: Repo) -> Truth:
        text = repo.text(path)
        m = re.search(pattern, text)
        return Truth(m is not None, path, line_of(text, m.start()) if m else 1, meaning)

    return read


def _route_handler(repo: Repo, method: str, route: str) -> ast.AST:
    for node in ast.walk(parse_python(repo, WEB_APP)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in node.decorator_list:
                if (
                    isinstance(d, ast.Call)
                    and isinstance(d.func, ast.Attribute)
                    and d.func.attr == method
                    and d.args
                    and isinstance(d.args[0], ast.Constant)
                    and d.args[0].value == route
                ):
                    return node
    raise RegistryError(f"{WEB_APP}: no {method.upper()} {route} route")


def route_depends_on(method: str, route: str, dependency: str, meaning: str) -> Computed:
    """True when the route's handler takes a parameter `= Depends(dependency)`."""

    def uses(repo: Repo) -> tuple[ast.AST, ast.Name | None]:
        handler = _route_handler(repo, method, route)
        for default in [*handler.args.defaults, *handler.args.kw_defaults]:
            if (
                isinstance(default, ast.Call)
                and getattr(default.func, "id", "") == "Depends"
                and default.args
                and isinstance(default.args[0], ast.Name)
                and default.args[0].id == dependency
            ):
                return handler, default.args[0]
        return handler, None

    def read(repo: Repo) -> Truth:
        handler, name = uses(repo)
        return Truth(name is not None, WEB_APP, handler.lineno, meaning)

    def mutate(repo: Repo) -> dict[str, str] | None:
        text = repo.text(WEB_APP)
        _, name = uses(repo)
        if name is None:
            return None
        start, end = offsets(text, name)
        return {WEB_APP: text[:start] + "mutant" + text[end:]}

    return Computed(WEB_APP, read, mutate)


def api_reference_served(repo: Repo) -> Truth:
    """FastAPI serves /docs and /openapi.json unless the app turns them off."""
    tree = parse_python(repo, WEB_APP)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "FastAPI":
            off = [
                kw.arg
                for kw in node.keywords
                if kw.arg in {"docs_url", "openapi_url"}
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is None
            ]
            return Truth(not off, WEB_APP, node.lineno)
    raise RegistryError(f"{WEB_APP}: no FastAPI(...) call")


def personas_historical(repo: Repo) -> Truth:
    personas = json.loads(repo.text(PERSONAS))["personas"]
    this_year = datetime.datetime.now(tz=datetime.UTC).year
    living = [
        p["name"] for p in personas if not isinstance(p.get("died"), int) or p["died"] > this_year
    ]
    return Truth(
        not living,
        PERSONAS,
        1,
        f"{len(personas)} scientists, none living"
        if not living
        else "living or undated: " + ", ".join(living),
    )


def seeds_in_golden_set(repo: Repo) -> Truth:
    """The Home screen's seed questions that have a counterpart in the
    golden evaluation set: a golden question carrying every identifier the
    seed names (a word with a capital after its first letter, or a digit)."""
    home = repo.text(HOME_TSX)
    block = re.search(r"const SEEDS[^=]*= \[(.*?)\];", home, S)
    if block is None:
        raise RegistryError(f"{HOME_TSX}: no SEEDS array")
    seeds = [
        m.group(1) + (m.group(2) or "")
        for m in re.finditer(r'\{ text: "([^"]*)"(?:, mono: "([^"]*)")?', block.group(1))
    ]
    questions = [q["question"] for q in json.loads(repo.text(GOLDEN))["queries"]]
    matched, unmatched = [], []
    for seed in seeds:
        ids = [w for w in re.findall(r"[A-Za-z0-9]+", seed) if re.search(r"\d|[A-Z]", w[1:])]
        hit = ids and any(all(re.search(rf"\b{re.escape(i)}\b", q) for i in ids) for q in questions)
        (matched if hit else unmatched).append(seed)
    note = f"{len(seeds)} seeds; no golden question for: " + (", ".join(unmatched) or "none")
    return Truth(tuple(matched), GOLDEN, 1, note)


def _depth_options(repo: Repo) -> tuple[dict[str, str], str, int]:
    text = repo.text(DEPTH_TSX)
    options = dict(re.findall(r'\{ value: "(\w+)", label: "([^"]+)" \}', text))
    default = re.search(r'DEFAULT_ANSWER_MODE: AudienceDepth = "(\w+)"', text)
    if not options or default is None:
        raise RegistryError(f"{DEPTH_TSX}: no OPTIONS or DEFAULT_ANSWER_MODE")
    return options, default.group(1), line_of(text, default.start())


def default_mode_label(repo: Repo) -> Truth:
    options, default, line = _depth_options(repo)
    return Truth(options[default], DEPTH_TSX, line)


def mode_labels(repo: Repo) -> Truth:
    options, _, line = _depth_options(repo)
    return Truth(frozenset(options.values()), DEPTH_TSX, line)


def snapshot_date(raw: str):
    return to_date(raw)


# ------------------------------------------------------------------ source mutations

# Used only by `check_facts.py --self-test`, which rewrites a source in memory
# and requires the computed truth to change. A mutation that no longer finds
# its target is listed by the self-test, never silently dropped.
GENE_ROW = swap(KG_REF, r"(\| Gene \| )[\d,]+", r"\g<1>1")
DISEASE_ROW = swap(KG_REF, r"(\| Disease \| )[\d,]+", r"\g<1>small")
PUBTATOR_LAYER = swap(
    f"{PKG}/tools/pubtator_annotate.py", r'layer="layer_3_enrichment"', 'layer="layer_2_api"'
)
PUBCHEM_LAYER = swap(TRANSPORT, r'"pubchem": 2,', '"pubchem": 3,')
NO_GRAPHQL = swap(QUERY_PY, r', "graphql"\]', "]")

# ------------------------------------------------------------------ helpers for places


def num(index: int = 1):
    return g(index, to_int)


def w(place: str, path: str, pattern: str, cmp=EXACT, parse=None, collect=None, flags=0) -> Where:
    return Where(place, path, pattern, cmp, parse or num(), collect, flags)


def everywhere(
    files: tuple[str, ...], pattern: str, cmp=EXACT, parse=None, flags=0
) -> tuple[Where, ...]:
    return tuple(w(DOC, f, pattern, cmp, parse, flags=flags) for f in files)


# ------------------------------------------------------------------ the facts

FACTS: tuple[Fact, ...] = (
    # ---- the knowledge graph snapshot
    Fact(
        "graph.nodes",
        "how many nodes the knowledge graph holds",
        TextMatch(KG_REF, r"It contains ([\d,]+) nodes", g(1, to_int)),
        stated=(
            w(ARCH_ABOUT, FACTS_TS, r'NODE_COUNT = "([\d,]+)"'),
            w(INTEGRATIONS, INFO, r'"(\d+)M nodes"', MILLIONS),
            w(ABOUT, INFO, r"(\d+)M nodes and \d+M edges merged", MILLIONS),
            w(HOME, HOME_TSX, r'"(\d+)M nodes, \d+M edges"', MILLIONS),
        ),
        downstream=(
            *everywhere(INSTRUCTION_FILES, r"\((\d+)M nodes, \d+M edges", MILLIONS),
            w(DOC, README, r"across a (\d+)M-node knowledge graph", MILLIONS),
            w(DOC, SCHEMA_VIS, r"It holds ([\d,]+) nodes"),
        ),
    ),
    Fact(
        "graph.edges",
        "how many edges the knowledge graph holds",
        TextMatch(KG_REF, r"nodes and ([\d,]+) edges across", g(1, to_int)),
        stated=(
            w(ARCH_ABOUT, FACTS_TS, r'EDGE_COUNT = "([\d,]+)"'),
            w(INTEGRATIONS, INFO, r'"(\d+)M edges"', MILLIONS),
            w(ABOUT, INFO, r"\d+M nodes and (\d+)M edges merged", MILLIONS),
            w(HOME, HOME_TSX, r'"\d+M nodes, (\d+)M edges"', MILLIONS),
        ),
        downstream=(
            *everywhere(INSTRUCTION_FILES, r"\(\d+M nodes, (\d+)M edges", MILLIONS),
            w(DOC, SCHEMA_VIS, r"nodes and ([\d,]+) edges across"),
        ),
    ),
    Fact(
        "graph.vertex_labels",
        "how many vertex labels the graph has",
        TextMatch(KG_REF, r"across (\d+) vertex labels", g(1, to_int)),
        stated=(w(ARCH, FACTS_TS, r'VERTEX_LABEL_COUNT = "(\d+)"'),),
        downstream=(w(DOC, SCHEMA_VIS, r"across (\d+) vertex labels"),),
    ),
    Fact(
        "graph.edge_labels",
        "how many edge labels the graph has",
        TextMatch(KG_REF, r"vertex labels and (\d+) edge labels", g(1, to_int)),
        stated=(w(ARCH, FACTS_TS, r'EDGE_LABEL_COUNT = "(\d+)"'),),
        downstream=(w(DOC, SCHEMA_VIS, r"vertex labels and (\d+) edge labels"),),
    ),
    Fact(
        "graph.database_nodes",
        "how many nodes each of the five source databases contributes",
        Computed(KG_REF, per_database_nodes, GENE_ROW),
        stated=(
            w(
                ARCH,
                FACTS_TS,
                r'label: "(\w+)", nodes: "([\d,]+)"',
                MAPPING,
                lambda m: {m.group(1): to_int(m.group(2))},
                merge_dicts,
            ),
        ),
    ),
    Fact(
        "graph.databases",
        "which NCBI databases the graph is built from",
        TextMatch(
            KG_REF, r"which were ([^.]+)\. It contains", lambda m: frozenset(words_list(m.group(1)))
        ),
        stated=(w(ARCH_ABOUT, FACTS_TS, r'source: "(?:NCBI )?([^"]+)"', SET, g(), union),),
        downstream=(
            w(
                DOC,
                README,
                r"\| (\d+) NCBI databases \(([^)]+)\)",
                SET,
                lambda m: frozenset(words_list(m.group(2))),
            ),
        ),
    ),
    Fact(
        "graph.database_count",
        "how many NCBI databases the graph is built from",
        TextMatch(
            KG_REF, r"which were ([^.]+)\. It contains", lambda m: tuple(words_list(m.group(1)))
        ),
        stated=(
            w(ABOUT, INFO, r"\b(five|5) NCBI databases", COUNT, flags=re.IGNORECASE),
            w(ARCH, ARCH_TSX, r"\b(Five) NCBI databases are downloaded", COUNT),
            w(ARCH, ARCH_TSX, r"The (five) source databases", COUNT),
        ),
        downstream=(
            *everywhere(INSTRUCTION_FILES, r"edges from (\d+) NCBI databases", COUNT),
            w(DOC, README, r"\| (\d+) NCBI databases \(", COUNT),
        ),
    ),
    Fact(
        "graph.minor_label_nodes",
        "how many nodes sit outside the five main labels",
        Computed(KG_REF, minor_label_nodes, GENE_ROW),
        stated=(w(ARCH, ARCH_TSX, r"Roughly ([\d,]+) further nodes", THOUSANDS),),
    ),
    Fact(
        "graph.minor_label_count",
        "how many smaller labels hold those nodes",
        Computed(KG_REF, minor_label_count, DISEASE_ROW),
        stated=(w(ARCH, ARCH_TSX, r"further nodes sit under (\w+)\s+smaller labels"),),
    ),
    Fact(
        "graph.gene_rows",
        "how many Gene nodes an unindexed lookup would scan",
        Computed(KG_REF, gene_rows, GENE_ROW),
        stated=(w(ARCH, ARCH_TSX, r"a scan of (\d+) million rows", MILLIONS),),
    ),
    Fact(
        "graph.snapshot_date",
        "the date the loaded graph snapshot was finished",
        PyConst(CYPHER_QUERY, "_DEFAULT_GRAPH_SNAPSHOT_VERSION", snapshot_date),
        stated=(
            w(ARCH_ABOUT, FACTS_TS, r'SNAPSHOT_DATE = "([^"]+)"', EXACT, g(1, to_date)),
            w(ARCH, ARCH_TSX, r"A record that has changed since (\w+)", MONTH, g()),
        ),
    ),
    Fact(
        "graph.name",
        "the name of the graph the agent queries",
        PyConst(GRAPH_CONSTS, "GRAPH_NAME"),
        stated=(
            w(ARCH, ARCH_TSX, r"graph, named (\w+), running", EXACT, g()),
            w(ARCH, FACTS_TS, r'calls: "the (\w+) graph, PostgreSQL', EXACT, g()),
        ),
        downstream=(w(DOC, SCHEMA_VIS, r"graph called `(\w+)`", EXACT, g()),),
    ),
    Fact(
        "graph.postgres_version",
        "the PostgreSQL major version the graph runs on",
        TextMatch(KG_REF, r"\| PostgreSQL \| (\d+)\.\d+ \|", g(1, to_int)),
        stated=(w(ARCH, ARCH_TSX, r"PostgreSQL (\d+) with the Apache AGE"),),
    ),
    Fact(
        "graph.edge_label_speedup",
        "how long the first BRCA1 query took without and with its edge label",
        TextMatch(
            KG_REF,
            r"went from (\d+) minutes (\d+) seconds to (\d+) ms",
            lambda m: (int(m.group(1)), int(m.group(2)), int(m.group(3))),
        ),
        stated=(
            w(
                ARCH,
                ARCH_TSX,
                r"took (\d+) minutes and\s+(\d+) seconds without it, and (\d+) milliseconds",
                EXACT,
                lambda m: (int(m.group(1)), int(m.group(2)), int(m.group(3))),
            ),
        ),
    ),
    Fact(
        "graph.pipeline_steps",
        "the five steps every data pipeline runs",
        Computed(
            REF_CLAUDE, pipeline_steps, swap(REF_CLAUDE, r"Step 1: Download", "Step 1: Fetch")
        ),
        stated=(
            w(
                ARCH,
                FACTS_TS,
                r"PIPELINE_STEPS = \[(.*?)\]",
                EXACT,
                lambda m: tuple(s.split()[0] for s in quoted(m.group(1))),
                flags=S,
            ),
        ),
    ),
    Fact(
        "graph.biolink_version",
        "the BioLink model version the pipelines map to",
        TextMatch(REF_CLAUDE, r"BioLink (\d+\.x)", g()),
        stated=(w(ARCH, ARCH_TSX, r"the BioLink (\d+\.x) model", EXACT, g()),),
    ),
    # ---- tools and layers
    Fact(
        "tools.count",
        "how many tools the agent has",
        PyLiteral(EVENTS_PY, "ToolName"),
        stated=(
            w(INTEGRATIONS, INFO, r'"(\d+) tools"', COUNT),
            w(INTEGRATIONS, INFO, r"the (\w+) internal tools", COUNT),
            w(ABOUT, INFO, r"the descriptions of the (\w+) tools", COUNT),
            w(ARCH, ARCH_TSX, r"(Seven) tools cover the three layers", COUNT),
        ),
        downstream=(
            *everywhere(INSTRUCTION_FILES, r"PLANNED, (\w+) tools\.", COUNT),
            w(DOC, ARCH_DIAGRAM, r"## The three data layers and the (\w+) tools", COUNT),
            w(DOC, SCHEMA_VIS, r"each of the (\w+) tools", COUNT),
            w(DOC, SCHEMA_VIS, r'string tool "one of (\w+)"', COUNT),
            w(DOC, README, r"Locked\. 25 sections, (\w+) tools", COUNT),
        ),
    ),
    Fact(
        "tools.names",
        "the names of the agent's tools",
        PyLiteral(EVENTS_PY, "ToolName"),
        stated=(
            w(CODE, EVENTS_TS, r"export type ToolName =((?:\s*\|\s*\"\w+\")+);", SET, ts_union),
        ),
        downstream=(
            *everywhere(
                INSTRUCTION_FILES, r"PLANNED, \w+ tools\. ([a-z0-9_, ]+)\. Build", SET, word_set
            ),
        ),
    ),
    Fact(
        "tools.layers",
        "which tools read which data layer",
        Computed(EVENTS_PY, tool_layers, PUBTATOR_LAYER),
        stated=(
            w(
                ABOUT,
                INFO,
                r"const JOURNEY_LAYERS[^=]*= \[(.*?)\n\];",
                MAPPING,
                ts_layers("tools"),
                flags=S,
            ),
            w(
                ARCH,
                FACTS_TS,
                r"export const LAYERS[^=]*= \[(.*?)\n\];",
                MAPPING,
                ts_layers("name"),
                flags=S,
            ),
        ),
        downstream=(
            w(
                DOC,
                ARCH_DIAGRAM,
                r"^\| ([a-z0-9_]+) \| Layer (\d) \|",
                MAPPING,
                lambda m: {int(m.group(2)): frozenset({m.group(1)})},
                merge_dicts,
                re.MULTILINE,
            ),
        ),
    ),
    Fact(
        "layers.count",
        "how many data layers there are",
        PyLiteral(EVENTS_PY, "Layer"),
        stated=(
            w(INTEGRATIONS, INFO, r'"(\d+) data layers"', COUNT),
            w(ABOUT, INFO, r"crosses up to (\w+) data layers", COUNT),
            w(ARCH, ARCH_TSX, r"(Three) data layers feed one search agent", COUNT),
        ),
        downstream=(
            *everywhere(INSTRUCTION_FILES, r"(Three)-layer data access", COUNT),
            w(DOC, SCHEMA_VIS, r'string layer "one of (\w+)"', COUNT),
        ),
    ),
    Fact(
        "layers.l2_tools",
        "how many tools reach the live NCBI APIs",
        Computed(EVENTS_PY, tools_in_layer(2), PUBTATOR_LAYER),
        stated=(w(ARCH, ARCH_TSX, r"(Three) tools cover that", COUNT),),
    ),
    Fact(
        "layers.l3_tools",
        "how many tools add enrichment",
        Computed(EVENTS_PY, tools_in_layer(3), PUBTATOR_LAYER),
        stated=(w(ARCH, ARCH_TSX, r"(three) further tools add evidence", COUNT),),
    ),
    Fact(
        "layers.l2_apis",
        "which live NCBI APIs layer 2 calls",
        Computed(TRANSPORT, api_families(2), PUBCHEM_LAYER),
        stated=(
            w(ABOUT, INFO, r'colour: designTokens\.layer2,\s*body: "([^"]+)"', SET, named_families),
            w(
                ARCH,
                FACTS_TS,
                r"export const LAYERS[^=]*= \[(.*?)\n\];",
                SET,
                layer_calls(2),
                flags=S,
            ),
        ),
        downstream=(
            *everywhere(
                INSTRUCTION_FILES, r"Layer 2: NCBI APIs live \(([^)]+)\)", SET, named_families
            ),
            w(DOC, README, r"\| Layer 2: on-demand NCBI APIs \| ([^|]+) \|", SET, named_families),
        ),
    ),
    Fact(
        "layers.l3_apis",
        "which enrichment APIs layer 3 calls",
        Computed(TRANSPORT, api_families(3), PUBCHEM_LAYER),
        stated=(
            w(ABOUT, INFO, r'colour: designTokens\.layer3,\s*body: "([^"]+)"', SET, named_families),
            w(
                ARCH,
                FACTS_TS,
                r"export const LAYERS[^=]*= \[(.*?)\n\];",
                SET,
                layer_calls(3),
                flags=S,
            ),
        ),
        downstream=(
            *everywhere(
                INSTRUCTION_FILES, r"Layer 3: Enrichment APIs \(([^)]+)\)", SET, named_families
            ),
            w(DOC, README, r"\| Layer 3: enrichment APIs \| ([^|]+) \|", SET, named_families),
        ),
    ),
    # ---- budgets
    Fact(
        "budget.graph_query_s",
        "how long one graph query may take, in seconds",
        PyConst(GRAPH_CONSTS, "CYPHER_QUERY_TIMEOUT_SECONDS", int),
        stated=(
            w(ARCH, FACTS_TS, r'budget: "(\d+) seconds, at most \d+ rows"'),
            w(ARCH, ARCH_TSX, r"gives one graph query (\d+) seconds"),
            w(ABOUT, INFO, r"(\d+) seconds for a graph query"),
        ),
        downstream=(
            w(DOC, ARCH_DIAGRAM, r'CQ\["cypher_query, (\d+) s"\]'),
            w(DOC, ARCH_DIAGRAM, r"\| cypher_query \| Layer 1 \| (\d+) seconds"),
            w(DOC, DEEP_DIVE, r"Cypher writing included \| (\d+) s \|"),
            w(CODE, CATALOGUE, r"_CYPHER_QUERY_BUDGET = \((\d+)\.0"),
        ),
    ),
    Fact(
        "budget.row_limit",
        "the most rows one graph query may return",
        PyConst(GRAPH_CONSTS, "MAX_ROW_LIMIT"),
        stated=(
            w(ARCH, FACTS_TS, r'budget: "\d+ seconds, at most (\d+) rows"'),
            w(ARCH, ARCH_TSX, r"accepts at most (\d+) rows"),
        ),
        downstream=(w(DOC, ARCH_DIAGRAM, r"Row limit (\d+)"),),
    ),
    Fact(
        "budget.live_call_s",
        "how long one live NCBI or enrichment call may take, in seconds",
        PyConst(TRANSPORT, "DEFAULT_TIMEOUT_S", int),
        stated=(
            w(ABOUT, INFO, r"(\d+) seconds for a live NCBI call"),
            w(
                ARCH,
                FACTS_TS,
                r'name: "(?:ncbi_efetch|ncbi_dbsnp|pubtator_annotate|litvar2_lookup|clinicaltrials_search)",'
                r'\s*calls: "[^"]*",\s*budget: "(\d+) seconds',
                flags=S,
            ),
        ),
        downstream=(
            w(DOC, ARCH_DIAGRAM, r'(?:EF|DB|PT|LV|CT)\["\w+, (\d+) s'),
            w(
                DOC,
                ARCH_DIAGRAM,
                r"\| (?:ncbi_efetch|ncbi_dbsnp|pubtator_annotate|litvar2_lookup|clinicaltrials_search)"
                r" \| Layer \d \| (\d+) seconds",
            ),
            w(DOC, DEEP_DIVE, r"One Layer 2 or Layer 3 HTTP call \| (\d+) s"),
            w(
                CODE,
                CATALOGUE,
                r"_(?:NCBI_EFETCH|NCBI_DBSNP|PUBTATOR|LITVAR2|CLINICALTRIALS)_BUDGET = \(\s*(\d+)\.0",
            ),
        ),
    ),
    Fact(
        "budget.pathogen_s",
        "how long one Pathogen Detection call may take, in seconds",
        PyConst(PATHOGEN, "_TOTAL_BUDGET_S", int),
        stated=(
            w(
                ARCH,
                FACTS_TS,
                r'name: "pathogen_detection",\s*calls: "[^"]*",\s*budget: "(\d+) seconds"',
                flags=S,
            ),
        ),
        downstream=(
            w(DOC, ARCH_DIAGRAM, r'PD\["pathogen_detection, (\d+) s"\]'),
            w(DOC, ARCH_DIAGRAM, r"\| pathogen_detection \| Layer 2 \| (\d+) seconds total"),
            w(DOC, DEEP_DIVE, r"Pathogen Detection isolate search \| (\d+) s"),
            w(CODE, CATALOGUE, r"_PATHOGEN_DETECTION_BUDGET = \(\s*(\d+)\.0"),
        ),
    ),
    Fact(
        "budget.live_calls_per_question",
        "how many live layer 2 and 3 calls one question may make",
        PyConst(CALL_BUDGET, "MAX_LAYER_2_3_CALLS_PER_QUERY"),
        stated=(
            w(ABOUT, INFO, r"may make at most (\d+) live calls", flags=S),
            w(INTEGRATIONS, INFO, r"capped at (\w+) Layer 2 and Layer 3 calls"),
        ),
        downstream=(
            w(DOC, ARCH_DIAGRAM, r"at most (\d+) Layer 2 and Layer 3 calls per query"),
            w(DOC, DEEP_DIVE, r"at most (\d+) Layer 2 and Layer 3 calls per question"),
        ),
    ),
    # ---- the event stream
    Fact(
        "events.types",
        "the kinds of event a run emits",
        PyLiteral(EVENTS_PY, "type", cls="Event"),
        stated=(
            w(INTEGRATIONS, INFO, r"A run emits (\w+) kinds of event", COUNT),
            w(INTEGRATIONS, INFO, r"kinds of event: ([a-z_, ]+?)\. Each SSE", SET, word_set),
        ),
        downstream=(w(DOC, SCHEMA_VIS, r'string type "one of (\w+)"', COUNT),),
    ),
    Fact(
        "events.guard_fields",
        "the fields of a guard event's payload",
        PyFields(EVENTS_PY, "GuardPayload"),
        stated=(
            w(
                INTEGRATIONS,
                INFO,
                r'"payload":\{([^}]*)\}',
                SET,
                lambda m: frozenset(re.findall(r'"(\w+)":', m.group(1))),
            ),
        ),
    ),
    Fact(
        "events.guard_categories",
        "the reasons a question can be turned away",
        PyLiteral(EVENTS_PY, "category", cls="GuardPayload"),
        stated=(
            w(BANNER, BANNER_TSX, r"CATEGORY_COPY[^=]*= \{(.*?)\n\};", SET, ts_keys, flags=S),
            w(CODE, EVENTS_TS, r"category:((?:\s*\|\s*\"\w+\")+);", SET, ts_union),
        ),
    ),
    # ---- the question and the answer modes
    Fact(
        "query.max_chars",
        "how long a question may be, in characters",
        PyFieldKw(QUERY_PY, "Query", "text", "max_length"),
        stated=(
            w(TOUR, TOUR_TSX, r"can run to about ([\d,]+) characters"),
            w(HOME, HOME_TSX, r"QUESTION_MAX_LENGTH = (\d+)"),
        ),
    ),
    Fact(
        "modes.accepted",
        "the answer modes the web app sends are ones the server accepts",
        PyLiteral(QUERY_PY, "audience_depth", cls="Query"),
        stated=(w(CODE, DEPTH_TSX, r'\{ value: "(\w+)", label: "[^"]+" \}', SUBSET, g(), union),),
    ),
    Fact(
        "modes.default",
        "the answer mode a question uses unless changed",
        Computed(
            DEPTH_TSX,
            default_mode_label,
            swap(
                DEPTH_TSX,
                r'DEFAULT_ANSWER_MODE: AudienceDepth = "plain_language"',
                'DEFAULT_ANSWER_MODE: AudienceDepth = "researcher"',
            ),
        ),
        stated=(
            w(
                ABOUT,
                INFO,
                r"pick how the answer is written: ([A-Z][a-z]+ [a-z]+), the default",
                EXACT,
                g(),
            ),
            w(TOUR, TOUR_TSX, r'"([A-Z][a-z]+ [a-z]+), the default, gives', EXACT, g()),
        ),
    ),
    Fact(
        "modes.labels",
        "the answer modes a person can pick",
        Computed(
            DEPTH_TSX, mode_labels, swap(DEPTH_TSX, r'label: "Researcher" \}', 'label: "Scholar" }')
        ),
        stated=(
            w(ABOUT, INFO, r"pick how the answer is written: [^.]+\.", SET, modes_named, flags=S),
            w(TOUR, TOUR_TSX, r'"Plain language, the default, gives[^"]+"', SET, modes_named),
        ),
    ),
    # ---- how the agent is reached
    Fact(
        "surfaces.count",
        "how many ways a program can reach the agent",
        Computed(QUERY_PY, programmatic_surfaces, NO_GRAPHQL),
        stated=(w(INTEGRATIONS, INFO, r"reachable (\w+) ways", COUNT),),
    ),
    Fact(
        "surfaces.named",
        "which ways a program can reach the agent",
        Computed(QUERY_PY, programmatic_surfaces, NO_GRAPHQL),
        stated=(
            w(
                TOUR,
                TOUR_TSX,
                r"Integrations lists the other ways in: ([^.]+)\.",
                SET,
                named_surfaces,
            ),
            w(
                INTEGRATIONS,
                INFO,
                r'<IntegrationCard\s+icon=\{<\w+ />\}\s+title="([^"]+)"',
                SET,
                named_surfaces,
                union,
                S,
            ),
        ),
    ),
    Fact(
        "surfaces.mcp_tools",
        "the tools the MCP server advertises",
        Computed(
            MCP_SERVER,
            mcp_tools,
            swap(MCP_SERVER, r"async def ask_biomedical_question\(", "async def ask_mutant("),
        ),
        stated=(
            w(INTEGRATIONS, INFO, r"(One) advertised tool", COUNT),
            w(
                INTEGRATIONS,
                INFO,
                r"One advertised tool, (\w+)\.",
                SET,
                lambda m: frozenset({m.group(1)}),
            ),
        ),
    ),
    Fact(
        "surfaces.console_commands",
        "the console commands the package installs",
        Computed(
            PYPROJECT,
            console_scripts,
            swap(PYPROJECT, r"\[project\.scripts\]\n", '[project.scripts]\nmutant = "x:y"\n'),
        ),
        stated=(
            w(INTEGRATIONS, INFO, r"(Two) console commands", COUNT),
            w(INTEGRATIONS, INFO, r"\b(s3(?:-[a-z]+)*) (?:asks|writes)", SET, g(), union),
        ),
    ),
    Fact(
        "access.login_route",
        "the route that exchanges an email and password for a token",
        Computed(
            AUTH_ROUTER,
            auth_routes,
            swap(AUTH_ROUTER, r'@router\.post\("/login"', '@router.post("/mutant"'),
        ),
        stated=(w(INTEGRATIONS, INFO, r"POST (/auth/\w+) exchanges", MEMBER, g()),),
    ),
    Fact(
        "access.graphql_refuses_guests",
        "a guest cannot use GraphQL",
        Computed(
            GRAPHQL_CONTEXT,
            marker(
                GRAPHQL_CONTEXT,
                r"this bearer token is a guest credential",
                "GraphQL answers a guest token with its own refusal",
            ),
            swap(GRAPHQL_CONTEXT, r"this bearer token is a guest credential", "mutant"),
        ),
        stated=(
            w(
                INTEGRATIONS,
                INFO,
                r"GraphQL and the MCP server: an account is required",
                BOOL,
                present,
            ),
        ),
    ),
    Fact(
        "access.mcp_refuses_guests",
        "a guest cannot use the MCP server",
        Computed(
            MCP_SERVER,
            marker(
                MCP_SERVER,
                r"return resolve_user_from_bearer_token\(",
                "the MCP server resolves only a registered user's access token",
            ),
            swap(MCP_SERVER, r"return resolve_user_from_bearer_token\(", "return mutant("),
        ),
        stated=(
            w(
                INTEGRATIONS,
                INFO,
                r"GraphQL and the MCP server: an account is required",
                BOOL,
                present,
            ),
        ),
    ),
    Fact(
        "access.rest_admits_guests",
        "a guest can ask questions over REST",
        route_depends_on(
            "post",
            "/v1/query",
            "get_caller",
            "POST /v1/query resolves its caller with get_caller, which admits a guest token",
        ),
        stated=(
            w(INTEGRATIONS, INFO, r"a guest may run queries without an account", BOOL, present),
        ),
    ),
    Fact(
        "access.history_kept",
        "a signed-in person's questions are kept across reloads",
        Computed(
            WEB_APP,
            has_route("/v1/history"),
            swap(WEB_APP, r'@app\.get\("/v1/history"', '@app.get("/v1/mutant"'),
        ),
        stated=(
            w(TOUR, TOUR_TSX, r"Log in keeps your search history across reloads", BOOL, present),
            w(
                ABOUT,
                INFO,
                r"if you are signed in\s+the question is kept in your history",
                BOOL,
                present,
                flags=S,
            ),
        ),
    ),
    Fact(
        "access.api_reference",
        "the API serves its reference at /docs and its schema at /openapi.json",
        Computed(
            WEB_APP, api_reference_served, swap(WEB_APP, r"FastAPI\(", "FastAPI(docs_url=None, ")
        ),
        stated=(w(INTEGRATIONS, INFO, r"\$\{API_ORIGIN\}/(?:docs|openapi\.json)`", BOOL, present),),
    ),
    Fact(
        "access.stream_resumes",
        "a dropped event stream can be resumed",
        Computed(
            WEB_APP,
            marker(
                WEB_APP, r'alias="Last-Event-ID"', "the events route reads a Last-Event-ID header"
            ),
            swap(WEB_APP, r'alias="Last-Event-ID"', 'alias="X-Mutant"'),
        ),
        stated=(w(INTEGRATIONS, INFO, r"Resumable after a dropped connection", BOOL, present),),
    ),
    # ---- the loop and its models
    Fact(
        "loop.steps",
        "the steps every question goes through",
        step_names(),
        stated=(
            w(
                RUN,
                RUN_TSX,
                r"export const STEPS = \[([^\]]+)\]",
                STEPS,
                lambda m: tuple(quoted(m.group(1))),
            ),
            w(
                TOUR,
                TOUR_TSX,
                r"the five steps the system takes: ([^.]+)\.",
                STEPS,
                lambda m: tuple(words_list(m.group(1))),
            ),
            w(TOUR, TOUR_TSX, r"shows the (five) steps", COUNT),
            w(ABOUT, INFO, r"Four of the (five) steps", COUNT),
        ),
        downstream=(
            *everywhere(
                INSTRUCTION_FILES,
                r"(Guardrail -> Think -> Plan -> Act -> Write)",
                STEPS,
                lambda m: tuple(m.group(1).split(" -> ")),
            ),
        ),
    ),
    Fact(
        "loop.steps_asking_a_model",
        "how many of the steps ask a language model something",
        steps_reaching_model(),
        stated=(w(ABOUT, INFO, r"(Four) of the five steps ask a language model", COUNT),),
        downstream=(
            w(DOC, ARCH_DIAGRAM, r"(Four) of them make exactly one model call each", COUNT),
        ),
    ),
    Fact(
        "loop.tier_count",
        "how many model tiers the harness has",
        PyLiteral(TIERS_PY, "Tier"),
        stated=(w(ABOUT, INFO, r"There are (three) tiers", COUNT),),
        downstream=(*everywhere(INSTRUCTION_FILES, r"harness with (three) tiers", COUNT),),
    ),
    Fact(
        "loop.guardrail_on_guard_tier",
        "the guardrail step asks the guard-tier model",
        step_uses_tier("guardrail", "guard"),
        stated=(
            w(ABOUT, INFO, r'name: "Guard tier",[^}]*?Runs the guardrail', BOOL, present, flags=S),
        ),
    ),
    Fact(
        "loop.think_on_plan_tier",
        "the think step asks the plan-tier model",
        step_uses_tier("think", "plan"),
        stated=(w(ABOUT, INFO, r'name: "Plan tier",[^}]*?Runs Think', BOOL, present, flags=S),),
    ),
    Fact(
        "loop.plan_on_plan_tier",
        "the plan step asks the plan-tier model to pick tools and write the query",
        step_uses_tier("plan", "plan"),
        stated=(
            w(
                ABOUT,
                INFO,
                r"Then runs Plan, which picks the tools to call and writes the graph query itself",
                BOOL,
                present,
            ),
        ),
        downstream=(
            w(DOC, ARCH_DIAGRAM, r"- Plan: Plan tier, one call", BOOL, present),
            w(DOC, ARCH_DIAGRAM, r'PL\["Plan, Plan tier"\]', BOOL, present),
            *everywhere(
                INSTRUCTION_FILES,
                r"Plan tier: mid-range model for query decomposition and tool selection",
                BOOL,
                present,
            ),
        ),
    ),
    Fact(
        "loop.write_on_synth_tier",
        "the write step asks the synth-tier model",
        step_uses_tier("write", "synth"),
        stated=(w(ABOUT, INFO, r'name: "Synth tier",[^}]*?Runs Write', BOOL, present, flags=S),),
    ),
    Fact(
        "loop.act_asks_no_model",
        "the act step makes no model call",
        step_calls_no_model("act"),
        downstream=(
            w(DOC, ARCH_DIAGRAM, r"Act makes no model call at all", BOOL, present),
            w(DOC, ARCH_DIAGRAM, r'AC\["Act, no model call"\]', BOOL, present),
        ),
    ),
    Fact(
        "loop.plan_asks_no_model",
        "the plan step makes no model call",
        step_calls_no_model("plan"),
        downstream=(w(DOC, DEEP_DIVE, r"Note over L: Plan, no model call", BOOL, present),),
    ),
    Fact(
        "loop.sentences_checked_by_code_alone",
        "each answer sentence is checked against its record by code alone",
        checked_by_code_alone("write", "_ground_with_sentence_check"),
        stated=(
            w(
                ABOUT,
                INFO,
                r"Each sentence is then checked in\s+code against the record it points at",
                BOOL,
                present,
                flags=S,
            ),
        ),
    ),
    Fact(
        "models.code_defaults",
        "the model each tier uses when the deployment names none",
        PyConst(TIERS_PY, "_DEFAULT_MODELS"),
        downstream=(
            w(
                DOC,
                DEEP_DIVE,
                r"^\| (Guard|Plan|Synth) tier \| `([^`]+)` \|",
                MAPPING,
                lambda m: {m.group(1).lower(): m.group(2)},
                merge_dicts,
                re.MULTILINE,
            ),
            w(
                DOC,
                MODEL_ARCH,
                r"^\| (Guard|Plan|Synth) \| [^|]+ \| [^|]+ \| ([a-z0-9._/-]+) \|",
                MAPPING,
                lambda m: {m.group(1).lower(): m.group(2)},
                merge_dicts,
                re.MULTILINE,
            ),
        ),
    ),
    # ---- the people and the questions on screen
    Fact(
        "personas.historical",
        "each session's scientist is a historical figure",
        Computed(PERSONAS, personas_historical, swap(PERSONAS, r'"died": \d+', '"died": 9999')),
        stated=(
            w(TOUR, TOUR_TSX, r"a scientist from the history of biomedical science", BOOL, present),
        ),
    ),
    Fact(
        "seeds.from_golden_set",
        "the Home screen's seed questions come from the evaluation set",
        Computed(GOLDEN, seeds_in_golden_set, swap(GOLDEN, r"rs334", "rs999999")),
        stated=(
            w(TOUR, TOUR_TSX, r"These (\w+) are real questions from the evaluation set", COUNT),
        ),
    ),
)
