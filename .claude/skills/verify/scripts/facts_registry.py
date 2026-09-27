"""The registry of facts System 3's web app states about itself.

Read by `check_facts.py` in this directory, which holds the engine: the
readers, the comparisons, the call graph, the verdicts and the self-test.
This file holds the fact declarations and, beside them, the small functions
that compute a particular fact's truth or parse what a particular place
says. An edit here can therefore change how a fact is decided: it gets the
same review as an edit to the engine, and `--self-test` must pass after it.
One `Fact` per claim:

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
    NUMBER,
    SET,
    STEPS,
    SUBSET,
    TALLY,
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
    call_graph,
    checked_by_code_alone,
    g,
    line_of,
    loop_steps,
    merge_dicts,
    offsets,
    parse_python,
    present,
    quoted,
    set_allowing_omitted,
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
S3_CLI = f"{PKG}/adapters/cli/main.py"
KGX_CLI = f"{PKG}/export/cli.py"
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

# How the Integrations page names the fields every citation carries: for
# each field, the whole phrases that name it. An item of the sentence maps to
# a field only when it IS one of these phrases, normalised for case and
# spacing, never when it merely contains a key word, so "the reviewer who
# approved its confidence" names no field (PR118-V02). "tool" is not a
# `CitationPayload` field; its phrase is here so that sentence reads as the
# FAIL it is, not as an unknown item. An item in no tuple is an ERROR.
CITATION_FIELD_PHRASES: dict[str, tuple[str, ...]] = {
    "layer": ("the layer that produced it",),
    "tool": ("the tool that fetched it",),
    "evidence_kind": ("its evidence type",),
    "assertion_confidence": ("its confidence",),
    "license": ("its licence", "its license"),
}

# The answer mode labels a sentence may name. The labels themselves come
# from DepthControl.tsx; one missing here reads as "not named" and fails.
MODE_NAMES = ("Plain language", "Researcher")

# Event types the web client leaves out of KNOWN_EVENT_TYPES on purpose, each
# named in that file's own docstring: `cost` never reaches a non-operator
# client (frontend/src/lib/events.ts). Any other type missing from the list
# is a client that does not know the event. An omission counts only while
# the backend still declares the type (`set_allowing_omitted`).
CLIENT_OMITS_ON_PURPOSE = ("cost",)

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


def citation_fields_named(match: re.Match[str]) -> frozenset[str]:
    """Every item the sentence lists must be, whole, one of the phrases in
    `CITATION_FIELD_PHRASES`. An item the registry has never seen cannot be
    judged, so it raises, which reports an ERROR rather than letting the rest
    of the list pass (PR118-03). Matching is by the whole phrase, never by a
    key word inside the item (PR118-V02)."""
    by_phrase = {
        " ".join(phrase.lower().split()): field
        for field, phrases in CITATION_FIELD_PHRASES.items()
        for phrase in phrases
    }
    items = words_list(re.sub(r"^with\s+", "", match.group(1)))
    named = set()
    for item in items:
        field = by_phrase.get(" ".join(item.lower().split()))
        if field is None:
            raise ValueError(f"the item {item!r} is no phrase CITATION_FIELD_PHRASES names")
        named.add(field)
    return frozenset(named)


def modes_named(match: re.Match[str]) -> frozenset[str]:
    return frozenset(m for m in MODE_NAMES if m in match.group(0))


# ---- places matched by the shape of their claim, not the wording they had
#
# A correction of a page must read as PASS or FAIL on its claim, never as a
# pattern that finds nothing (PR118-12, and builder R's corrected pages in
# phase 8.10). So a count is captured as `N`, any number, and a yes-or-no
# claim is anchored on words a correction keeps, such as the card it sits
# in, and read for which way it points. A reading the registry cannot place
# either way raises, which is an honest ERROR, not a silent PASS.

N = f"({NUMBER})"
# How many of a group a sentence says: a number, or all or none of them.
QUANTITY = f"((?i:every one|each one|all|none)|{NUMBER})"
MCP_CARD = r'title="[^"]*MCP[^"]*"\s+body="'
MCP_TOOL_COUNT = MCP_CARD + r'[^"]*?\b' + N + r" (?:advertised )?tools?\b"
MCP_TOOL_NAMES = MCP_CARD + r'([^"]*)"'
PLAN_TIER_CARD = r'name: "Plan tier",[^}]*?body: "([^"]*)"'
STEPS_ASKING = (
    r"\b" + QUANTITY + r" of the " + N + r" steps (?:can |may )?ask a (?:language )?model"
)
AGENT_READS = r"The agent reads ([^.:;]+)"
WRITE_PASSAGE = r"Write composes the answer from those records alone\.(.*?)</StopText>"
SEED_SENTENCE = (
    r"(?:\b"
    + QUANTITY
    + r" of )?\b[Tt]hese "
    + N
    + r" (?:are|come)\b[^.;]*?\bfrom the evaluation set"
)


def _quantity(said: str | None, total: int) -> int:
    said = (said or "").lower()
    if said in ("", "every one", "each one", "all"):
        return total
    return 0 if said == "none" else to_int(said)


def steps_asking(match: re.Match[str]) -> int:
    """ "Four of the five steps ask a model" is 4; "every one of the five
    steps can ask a model" is 5."""
    return _quantity(match.group(1), to_int(match.group(2)))


def seed_tally(match: re.Match[str]) -> tuple[int, int]:
    """(seeds in all, seeds from the evaluation set): "these four are real
    questions from the evaluation set" is (4, 4), and "two of these four
    come word for word from the evaluation set" is (4, 2)."""
    total = to_int(match.group(2))
    return total, _quantity(match.group(1), total)


def snake_names(match: re.Match[str]) -> frozenset[str]:
    """The snake_case names a card's text gives, which is how it names tools."""
    return frozenset(re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", match.group(1)))


def plan_tier_serves_plan(match: re.Match[str]) -> bool:
    """Whether the About screen's Plan tier card says its model serves the
    Plan step: a sentence of the card that says it "runs Plan", or that
    names Plan with "this tier" as the one answering, asking or deciding.
    The card is the anchor, so a rewritten card is read, not lost."""
    for sentence in re.split(r"(?<=\.)\s+", " ".join(match.group(1).split())):
        if re.search(r"\bruns Plan\b", sentence) or (
            re.search(r"\bPlan\b", sentence)
            and re.search(
                r"\bthis tier (?:answers|asks|decides|makes|picks|runs|writes)\b", sentence
            )
        ):
            return True
    return False


def reads_layer_one_first(match: re.Match[str]) -> bool:
    """ "The agent reads layer 1 first" is yes; "the agent reads all three
    layers at once" is no. Anything else cannot be judged."""
    said = " ".join(match.group(1).lower().split())
    if re.search(r"\b(?:layer 1|layer one|the graph) first\b", said):
        return True
    if re.search(r"\b(?:at once|together|in parallel)\b", said):
        return False
    raise ValueError(f"cannot tell whether {said[:80]!r} says layer 1 is read first")


def checked_by_code_only(match: re.Match[str]) -> bool:
    """Whether the About screen's passage on Write says code alone checks
    each sentence: no when it says a model judges any of them, yes when it
    says code checks them and names no model. Anything else cannot be
    judged."""
    said = " ".join(match.group(1).split())
    if re.search(
        r"\b(?:judged|checked|decided|read) by a (?:language )?model\b"
        r"|\ba (?:language )?model (?:judges|checks|decides)\b",
        said,
        re.IGNORECASE,
    ):
        return False
    if re.search(r"\bchecked in code\b|\bcode checks\b", said, re.IGNORECASE):
        return True
    raise ValueError(f"cannot tell who checks the sentences in {said[:80]!r}")


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


LAYER_VALUE = re.compile(r"layer_(\d)_\w+")


def _layer_keywords(tree: ast.AST, tool: str | None) -> list[ast.Constant]:
    """Every `layer="layer_N_..."` keyword argument the code passes, as its
    value node. A docstring or a comment is not a keyword argument, so text
    that only mentions a layer never counts (PR118-V07). With `tool`, only a
    call that also passes `tool=<tool>` counts."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        keywords = {k.arg: k.value for k in node.keywords if k.arg}
        value = keywords.get("layer")
        if not (
            isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            and LAYER_VALUE.fullmatch(value.value)
        ):
            continue
        named = keywords.get("tool")
        if tool is None or (isinstance(named, ast.Constant) and named.value == tool):
            found.append(value)
    return found


def declared_layer(repo: Repo, tool: str) -> tuple[int, str, ast.Constant]:
    """The layer a tool's code declares, the file it is declared in, and the
    value's node. Each tool's module passes its own `layer=` keyword; a tool
    whose module passes none, `cypher_query`, is declared where Plan builds
    its call, in core/graph.py, by a call that also passes `tool=<tool>`.
    Every such keyword in the file must agree."""
    for path, only in ((f"{PKG}/tools/{tool}.py", None), (GRAPH_PY, tool)):
        nodes = _layer_keywords(parse_python(repo, path), only)
        if nodes:
            layers = {int(LAYER_VALUE.fullmatch(n.value).group(1)) for n in nodes}
            if len(layers) > 1:
                raise RegistryError(
                    f"{path}: {tool} declares more than one layer, {sorted(layers)}"
                )
            return layers.pop(), path, nodes[0]
    raise RegistryError(f"{tool}: no layer= keyword in its module or in {GRAPH_PY}")


def tool_layers(repo: Repo) -> Truth:
    """layer number -> the tools whose code declares it (`declared_layer`)."""
    tools = PyLiteral(EVENTS_PY, "ToolName").read(repo)
    layers: dict[int, set[str]] = {}
    for tool in tools.value:
        layers.setdefault(declared_layer(repo, tool)[0], set()).add(tool)
    return Truth({k: frozenset(v) for k, v in layers.items()}, EVENTS_PY, tools.line)


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
            # Read from pathogen_detection's own declaration, not through the
            # whole tool-layer map, so an unrelated tool rename cannot turn
            # this fact into an ERROR and hide its FAIL lines (PR118-02). The
            # code's keyword, never the docstring above it (PR118-V07).
            families["pathogen_ftp"] = declared_layer(repo, "pathogen_detection")[0]
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


def cli_options(path: str):
    """Every `--option` a console command's argument parser declares."""

    def read(repo: Repo) -> Truth:
        found = sorted(
            {
                a.value
                for node in ast.walk(parse_python(repo, path))
                if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument"
                for a in node.args
                if isinstance(a, ast.Constant)
                and isinstance(a.value, str)
                and a.value.startswith("--")
            }
        )
        return Truth(tuple(found), path, 1)

    return read


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


GRAPH_PY = f"{PKG}/core/graph.py"
GATHER_FN = "_gather_planned_calls"


def layer_one_read_first(repo: Repo) -> Truth:
    """False when Act runs its planned calls together through
    `asyncio.gather`, so no layer is read before another."""
    module = "system_03_search_agent.core.graph"
    graph = call_graph(repo)
    node = graph.funcs.get(f"{module}:{GATHER_FN}")
    if node is None:
        raise RegistryError(f"{GRAPH_PY}: no function {GATHER_FN}")
    act = next(fn for name, fn, _ in loop_steps(repo) if name == "act")
    together = graph.reaches(f"{module}:{act}", f"{module}:{GATHER_FN}") and any(
        isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "gather" for n in ast.walk(node)
    )
    note = "Act runs every planned call at once with asyncio.gather" if together else ""
    return Truth(not together, GRAPH_PY, node.lineno, note)


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


def _spaced(text: str) -> str:
    """Normalised for case and spacing only: punctuation and every word stay."""
    return " ".join(text.lower().split())


def question_forms(question: str) -> frozenset[str]:
    """The whole-question forms a seed may take to count as this golden
    question, normalised for case and spacing: the question's whole text,
    and the same whole text without its one closing question mark or full
    stop, since the Home screen writes its seeds without one. Nothing
    shorter counts: a fragment such as "RCA1" or a phrase inside a longer
    question is not the question (PR118-V03)."""
    whole = _spaced(question)
    return frozenset({whole, re.sub(r"\s*[?.]$", "", whole)})


def _seeds(repo: Repo) -> tuple[list[str], re.Match[str]]:
    home = repo.text(HOME_TSX)
    block = re.search(r"const SEEDS[^=]*= \[(.*?)\];", home, S)
    if block is None:
        raise RegistryError(f"{HOME_TSX}: no SEEDS array")
    seeds = [
        m.group(1) + (m.group(2) or "")
        for m in re.finditer(r'\{ text: "([^"]*)"(?:, mono: "([^"]*)")?', block.group(1))
    ]
    return seeds, block


def seeds_in_golden_set(repo: Repo) -> Truth:
    """Every seed question on the Home screen, each paired with whether it
    IS a golden evaluation question: its whole text, normalised for case and
    spacing, equals one of `question_forms` of a golden question.

    That is the only provenance a script can check honestly. The first
    version matched identifiers alone, so "Songs about BRCA1" passed
    (PR118-04). The second matched a substring of joined words, so "RCA1"
    passed, and counted matches rather than seeds, so a fifth seed rode
    under "these four" (PR118-V03). The place states how many seeds there
    are and how many come from the set, and both must match (`TALLY`):
    "these four are" claims all four, so every seed must qualify. The note still
    names, for each seed that fails, the golden question carrying the same
    identifiers, as a lead for whoever fixes the page; it decides nothing."""
    seeds, _ = _seeds(repo)
    questions = [q["question"] for q in json.loads(repo.text(GOLDEN))["queries"]]
    forms = frozenset().union(*(question_forms(q) for q in questions))
    judged = tuple((seed, _spaced(seed) in forms) for seed in seeds)
    leads = []
    for seed, qualifies in judged:
        if qualifies:
            continue
        ids = [w for w in re.findall(r"[A-Za-z0-9]+", seed) if re.search(r"\d|[A-Z]", w[1:])]
        near = next(
            (
                q
                for q in questions
                if ids and all(re.search(rf"\b{re.escape(i)}\b", q) for i in ids)
            ),
            None,
        )
        leads.append(f"{seed!r} -> " + (repr(near) if near else "no golden question names it"))
    good = sum(1 for _, qualifies in judged if qualifies)
    note = f"{len(seeds)} seeds, {good} a golden question whole; " + "; ".join(leads)
    return Truth(judged, GOLDEN, 1, note)


def _seed_mutation(repo: Repo) -> dict[str, str]:
    """For the self-test: make the first seed a golden question, whole, so
    that seed's verdict must move."""
    _, block = _seeds(repo)
    question = json.loads(repo.text(GOLDEN))["queries"][0]["question"].replace('"', "'")
    home = repo.text(HOME_TSX)
    first = re.search(r'\{ text: "[^"]*"(?:, mono: "[^"]*")? \}', home[block.start(1) :])
    at = block.start(1) + first.start()
    return {HOME_TSX: home[:at] + f'{{ text: "{question}" }}' + home[at + len(first.group(0)) :]}


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


def move_tool_layer(tool: str, new: str):
    """Move a tool's code declaration to another layer, and put a decoy
    comment carrying the OLD declaration on the file's first line. A reader
    that took the first `layer="..."` text in the file, a comment's or a
    docstring's, would read the decoy and miss the move, so the self-test
    fails it; the AST reader sees only the code's keyword (PR118-V07)."""

    def mutate(repo: Repo) -> dict[str, str]:
        _, path, node = declared_layer(repo, tool)
        text = repo.text(path)
        start, end = offsets(text, node)
        moved = text[:start] + f'"{new}"' + text[end:]
        return {path: f"# decoy for the self-test: layer={text[start:end]}\n{moved}"}

    return mutate


PATHOGEN_LAYER = move_tool_layer("pathogen_detection", "layer_3_enrichment")
PUBTATOR_LAYER = move_tool_layer("pubtator_annotate", "layer_2_api")
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
            w(ABOUT, INFO, r"\b" + N + r" NCBI databases", COUNT, flags=re.IGNORECASE),
            w(ARCH, ARCH_TSX, r"\b" + N + r" NCBI databases are downloaded", COUNT),
            w(ARCH, ARCH_TSX, r"The " + N + r" source databases", COUNT),
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
            w(ARCH, ARCH_TSX, r"\b" + N + r" tools cover the " + NUMBER + r" layers", COUNT),
        ),
        downstream=(
            *everywhere(INSTRUCTION_FILES, r"PLANNED, (\w+) tools\.", COUNT),
            w(
                DOC,
                ARCH_DIAGRAM,
                r"## The " + NUMBER + r" data layers and the " + N + r" tools",
                COUNT,
            ),
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
        Computed(EVENTS_PY, tool_layers, PATHOGEN_LAYER),
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
            w(ARCH, ARCH_TSX, r"\b" + N + r" data layers feed one search agent", COUNT),
        ),
        downstream=(
            *everywhere(INSTRUCTION_FILES, r"\b" + N + r"-layer data access", COUNT),
            w(DOC, SCHEMA_VIS, r'string layer "one of (\w+)"', COUNT),
        ),
    ),
    Fact(
        "layers.l2_tools",
        "how many tools reach the live NCBI APIs",
        Computed(EVENTS_PY, tools_in_layer(2), PATHOGEN_LAYER),
        stated=(w(ARCH, ARCH_TSX, r"\b" + N + r" tools cover that", COUNT),),
    ),
    Fact(
        "layers.l3_tools",
        "how many tools add enrichment",
        Computed(EVENTS_PY, tools_in_layer(3), PUBTATOR_LAYER),
        stated=(w(ARCH, ARCH_TSX, r"\b" + N + r" further tools add evidence", COUNT),),
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
        Computed(TRANSPORT, api_families(3), PATHOGEN_LAYER),
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
            w(
                CODE,
                EVENTS_TS,
                r"export const KNOWN_EVENT_TYPES[^=]*= \[(.*?)\];",
                set_allowing_omitted(CLIENT_OMITS_ON_PURPOSE),
                lambda m: frozenset(quoted(m.group(1))),
                flags=S,
            ),
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
    Fact(
        "citations.fields",
        "what every citation carries",
        PyFields(EVENTS_PY, "CitationPayload"),
        stated=(
            w(
                INTEGRATIONS,
                INFO,
                r"Every claim is tied to a specific record, (with [^.]+)\.",
                SUBSET,
                citation_fields_named,
            ),
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
            w(INTEGRATIONS, INFO, MCP_TOOL_COUNT, COUNT),
            w(INTEGRATIONS, INFO, MCP_TOOL_NAMES, SET, snake_names),
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
            w(INTEGRATIONS, INFO, r"\b" + N + r" console commands", COUNT),
            w(INTEGRATIONS, INFO, r"\b(s3(?:-[a-z]+)*) (?:asks|writes)", SET, g(), union),
        ),
    ),
    Fact(
        "surfaces.s3_options",
        "the options the s3 command accepts",
        Computed(S3_CLI, cli_options(S3_CLI), swap(S3_CLI, r'"--depth",', '"--json",')),
        stated=(w(INTEGRATIONS, INFO, r"JSON with (--[a-z-]+)", MEMBER, g()),),
    ),
    Fact(
        "surfaces.kgx_options",
        "the options the s3-kgx-export command accepts",
        Computed(KGX_CLI, cli_options(KGX_CLI), swap(KGX_CLI, r'"--hops",', '"--depth",')),
        stated=(
            w(
                INTEGRATIONS,
                INFO,
                r"export const KGX_EXAMPLE = `([^`]*)`",
                SUBSET,
                lambda m: frozenset(re.findall(r"--[a-z-]+", m.group(1))),
            ),
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
                r"the " + NUMBER + r" steps the system takes: ([^.]+)\.",
                STEPS,
                lambda m: tuple(words_list(m.group(1))),
            ),
            w(TOUR, TOUR_TSX, r"shows the " + N + r" steps", COUNT),
            w(ABOUT, INFO, r"\bof the " + N + r" steps\b", COUNT),
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
        stated=(w(ABOUT, INFO, STEPS_ASKING, COUNT, steps_asking),),
        downstream=(
            w(DOC, ARCH_DIAGRAM, r"\b" + N + r" of them make exactly one model call each", COUNT),
        ),
    ),
    Fact(
        "loop.tier_count",
        "how many model tiers the harness has",
        PyLiteral(TIERS_PY, "Tier"),
        stated=(w(ABOUT, INFO, r"There are " + N + r" tiers", COUNT),),
        downstream=(*everywhere(INSTRUCTION_FILES, r"harness with " + N + r" tiers", COUNT),),
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
        stated=(w(ABOUT, INFO, PLAN_TIER_CARD, BOOL, plan_tier_serves_plan, flags=S),),
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
        "loop.layer_one_read_first",
        "the agent reads the graph before it calls the live layers",
        Computed(
            GRAPH_PY,
            layer_one_read_first,
            swap(
                GRAPH_PY,
                r"await asyncio\.gather\(\*coroutines\)",
                "for c in coroutines:\n        await c",
            ),
        ),
        stated=(w(ARCH, ARCH_TSX, AGENT_READS, BOOL, reads_layer_one_first),),
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
        stated=(w(ABOUT, INFO, WRITE_PASSAGE, BOOL, checked_by_code_only, flags=S),),
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
        "the Home screen shows as many seeds as the tour says, and each is a golden question, whole",
        Computed(GOLDEN, seeds_in_golden_set, _seed_mutation),
        stated=(w(TOUR, TOUR_TSX, SEED_SENTENCE, TALLY, seed_tally),),
    ),
)


# ------------------------------------------------------------------ fixed readings


def _reads(pattern: str, parse, text: str, flags: int = 0):
    """For the self-test: a reading of `text` through a place's own pattern
    and parser, run only when the self-test asks for it."""
    return lambda: parse(re.search(pattern, text, flags))


_PLAN_CARD = 'name: "Plan tier",\n    kind: "a mid-range model",\n    body: "Runs Think. {}"'
_WRITE = "Write composes the answer from those records alone. {}\n          </StopText>"

# Each place whose claim a correction rewords is read here on the wording the
# page had AND on a correction of it, so a corrected page keeps reading as a
# claim, PASS or FAIL, never as a pattern that finds nothing (PR118-12,
# builder R's pages in phase 8.10). `check_facts.py --self-test` runs every
# case: (label, reading, what it must read as).
PARSER_CASES = (
    ("count by shape", _reads(r"\b" + N + r" tools cover", num(), "Eight tools cover the"), 8),
    (
        "MCP count, one",
        _reads(MCP_TOOL_COUNT, num(), 'title="MCP server"\n body="One advertised tool, a_b."'),
        1,
    ),
    (
        "MCP count, four, past the internal tools",
        _reads(
            MCP_TOOL_COUNT, num(), 'title="MCP server" body="Four tools, and the seven internal'
        ),
        4,
    ),
    (
        "MCP names",
        _reads(MCP_TOOL_NAMES, snake_names, 'title="MCP server" body="ask_one and list_two."'),
        frozenset({"ask_one", "list_two"}),
    ),
    (
        "steps asking, a number",
        _reads(STEPS_ASKING, steps_asking, "Four of the five steps ask a language model"),
        4,
    ),
    (
        "steps asking, every one",
        _reads(STEPS_ASKING, steps_asking, "Every one of the five steps can ask a language model"),
        5,
    ),
    (
        "seeds, all of them",
        _reads(SEED_SENTENCE, seed_tally, "These four are real questions from the evaluation set."),
        (4, 4),
    ),
    (
        "seeds, some of them",
        _reads(
            SEED_SENTENCE,
            seed_tally,
            "Two of these four come word for word from the evaluation set;",
        ),
        (4, 2),
    ),
    (
        "layer 1 first, as it was",
        _reads(AGENT_READS, reads_layer_one_first, "The agent reads layer 1 first, because"),
        True,
    ),
    (
        "layer 1 first, corrected",
        _reads(AGENT_READS, reads_layer_one_first, "The agent reads all three layers at once: the"),
        False,
    ),
    (
        "code alone, as it was",
        _reads(
            WRITE_PASSAGE,
            checked_by_code_only,
            _WRITE.format("Each sentence is then checked in\n code against the record."),
            S,
        ),
        True,
    ),
    (
        "code alone, corrected",
        _reads(
            WRITE_PASSAGE,
            checked_by_code_only,
            _WRITE.format("Code checks each sentence. One reworded is then judged by a model."),
            S,
        ),
        False,
    ),
    (
        "Plan tier card, as it was",
        _reads(
            PLAN_TIER_CARD,
            plan_tier_serves_plan,
            _PLAN_CARD.format("Then runs Plan, which picks the tools to call."),
            S,
        ),
        True,
    ),
    (
        "Plan tier card, this tier answers Plan's decision",
        _reads(
            PLAN_TIER_CARD,
            plan_tier_serves_plan,
            _PLAN_CARD.format("Plan then picks the tools, and this tier answers its one decision."),
            S,
        ),
        True,
    ),
    (
        "Plan tier card, another model answers Plan's decision",
        _reads(
            PLAN_TIER_CARD,
            plan_tier_serves_plan,
            _PLAN_CARD.format(
                "Plan then picks the tools and asks Jev or the guard tier its decision."
            ),
            S,
        ),
        False,
    ),
)
