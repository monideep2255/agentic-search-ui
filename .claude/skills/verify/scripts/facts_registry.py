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

A PLACE STATES ITS WHOLE SENTENCE. Write its pattern with `sent`, the
sentence word for word with the value as a group, because the engine fails
a place that touches a sentence it does not cover. When two facts read one
sentence, build the pattern once (the helpers under "sentences" below) and
give each fact its own group. A list of names is read with a strict parser
(`names_only` and its users), where every word must be a known name or an
allowed connective. A place that reads fields out of a structure, not a
sentence, is marked `block=True`, and says so. `--self-test` proves each of
these on every place, and `--mutation-test` replays `MUTATIONS`, the
reviewers' break-it edits, at the end of this file.

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
    visible,
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
KGX_MANIFEST = f"{PKG}/export/manifest.py"
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
    "rest_sse": ("REST", "REST and SSE", "the API"),
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
# client (frontend/src/lib/events.ts). `step` is left out too, but it is not
# listed here: it is read from the set `useAgentRun.ts` skips by name
# (`client_parsed_types`), so it stays allowed only while the client really
# skips it. Any other type missing from the list is a client that does not
# know the event. An omission counts only while the backend still declares
# the type (`set_allowing_omitted`).
CLIENT_OMITS_ON_PURPOSE = ("cost",)

# ------------------------------------------------------------------ parsers


# The only words a list of names may carry besides the names themselves.
# Default deny: a word outside this set, such as "not", "never", "except" or
# "excluded", is a word the registry cannot read, so the place FAILs rather
# than passing on the names it happens to contain (F-53-J03). Allowing a new
# connective word is a registry edit, reviewed like any other.
LIST_WORDS = frozenset(
    {"and", "or", "the", "NCBI", "v2", "API", "then", "record", "bulk", "snapshot", "over", "FTP"}
)


def names_only(
    text: str, names: dict[str, tuple[str, ...]], allowed: frozenset[str] = LIST_WORDS
) -> frozenset[str]:
    """The names a list states, each by its first display name, where every
    word of the list must be a known name or an allowed connective. A word
    that is neither raises, which reports the place as a FAIL."""
    aliases = sorted(
        ((alias, key) for key, forms in names.items() for alias in forms),
        key=lambda pair: -len(pair[0]),
    )
    rest = text
    found: set[str] = set()
    for alias, key in aliases:
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])")
        if pattern.search(rest):
            found.add(names[key][0])
            rest = pattern.sub(" ", rest)
    unread = [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9.\-]*", rest) if w not in allowed]
    if unread:
        raise ValueError(f"the list says {' '.join(unread)!r}, which is no name the registry reads")
    return frozenset(found)


def named_families(match: re.Match[str]) -> frozenset[str]:
    """The API families a list names, each by its first display name, so a
    report says "PubChem" rather than a transport key. A name no code calls
    is kept, marked, so the place FAILs on it."""
    names = {**FAMILY_NAMES, **{f"{n} (no code calls it)": (n,) for n in NOT_CALLED}}
    return names_only(match.group(1), names)


def named_surfaces(match: re.Match[str]) -> frozenset[str]:
    return names_only(match.group(1), SURFACE_NAMES, LIST_WORDS | {"server", "tools"})


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
    """The answer modes a sentence names, from its captured labels, each of
    which must be a label the registry knows."""
    named = frozenset(" ".join(g.split()) for g in match.groups() if g)
    unknown = named - set(MODE_NAMES)
    if unknown:
        raise ValueError(f"no answer mode is called {sorted(unknown)}")
    return named


def ws(text: str) -> str:
    """A literal sentence as a pattern that allows any run of white space,
    a line break included, between its words: page prose wraps in JSX."""
    return r"\s+".join(re.escape(word) for word in text.split())


def wording(meanings: dict[str, bool]):
    """For a sentence that makes a yes-or-no claim, captured as one of the
    wordings the registry knows: that wording's meaning. Each pattern offers
    the page's current wording AND the wording that says the opposite, so a
    page that flips its claim reads as the FAIL it is, never as a pattern
    that finds nothing. A wording the registry does not know raises, which
    reports an ERROR (card 53)."""
    table = {" ".join(k.lower().split()): v for k, v in meanings.items()}

    def parse(match: re.Match[str]) -> bool:
        said = " ".join(match.group(1).lower().split())
        if said not in table:
            raise ValueError(f"the wording {said!r} is none of {sorted(table)}")
        return table[said]

    return parse


def share_of(match: re.Match[str]) -> int:
    """How many a sentence counts: "Every one of the five" is five, and
    "Four of the five" is four. Group 1 is the head, group 2 the whole."""
    head = " ".join(match.group(1).lower().split())
    return to_int(match.group(2)) if head == "every one" else to_int(match.group(1))


def snake_names(match: re.Match[str]) -> frozenset[str]:
    """A list of snake_case names, every item of which must be one name,
    written bare or in backticks. Any other item raises."""
    items: list[str] = []
    for group in match.groups():
        if group:
            items += words_list(group)
    names = set()
    for item in items:
        bare = item.strip("`")
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+", bare):
            raise ValueError(f"the item {item!r} is not one tool name")
        names.add(bare)
    return frozenset(names)


PIPELINE_WORDS = frozenset({"to", "BioLink", "KGX"})


def pipeline_step_names(match: re.Match[str]) -> tuple[str, ...]:
    """Each pipeline step's first word, where any further word must be one
    the registry reads ("Map to BioLink", "Export KGX"); anything else in an
    item raises."""
    steps = []
    for item in quoted(match.group(1)):
        words = item.split()
        extra = [x for x in words[1:] if x not in PIPELINE_WORDS]
        if not words or extra:
            raise ValueError(f"the step {item!r} says more than the registry reads")
        steps.append(words[0])
    return tuple(steps)


def sent(template: str, **slots: str) -> str:
    """A whole sentence as a pattern: the template's words literal, any run
    of white space between them (page prose wraps), and each «name» the
    regex given for it. Every place that reads a sentence states all of
    it, so the engine's whole-sentence rule has nothing left over."""
    out = []
    for i, part in enumerate(re.split(r"«(\w+)»", template)):
        if i % 2:
            out.append(slots[part])
            continue
        for piece in re.split(r"(\s+)", part):
            out.append(r"\s+" if piece and piece.isspace() else re.escape(piece))
    return "".join(out)


def either(*phrases: str) -> str:
    """One capture group offering each phrase, any white space between its
    words, for `wording`."""
    return "(" + "|".join(ws(p) for p in phrases) + ")"


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


GRAPH_MODULE = "system_03_search_agent.core.graph"


def _graph_function(repo: Repo, name: str) -> ast.AST:
    node = call_graph(repo).funcs.get(f"{GRAPH_MODULE}:{name}")
    if node is None:
        raise RegistryError(f"{GRAPH_PY}: no function {name}")
    return node


def _step_function(repo: Repo, step: str) -> str:
    for name, fn, _ in loop_steps(repo):
        if name == step:
            return fn
    raise RegistryError(f"{GRAPH_PY}: no loop step {step!r}")


def layer_one_read_first(repo: Repo) -> Truth:
    """False when Act sends its first round of planned calls, the graph
    query among them, out together through `asyncio.gather`, so the graph
    is not read before the live layers."""
    graph = call_graph(repo)
    node = _graph_function(repo, GATHER_FN)
    act = _step_function(repo, "act")
    together = graph.reaches(f"{GRAPH_MODULE}:{act}", f"{GRAPH_MODULE}:{GATHER_FN}") and any(
        isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "gather" for n in ast.walk(node)
    )
    note = "Act's first round goes out at once through asyncio.gather" if together else ""
    return Truth(not together, GRAPH_PY, node.lineno, note)


def act_rounds(repo: Repo) -> Truth:
    """True when the Act step gathers its planned calls in more than one
    round: it calls `_gather_planned_calls` at least twice, the second time
    for the follow-ups the first round's results feed (F-53-J06)."""
    act = _graph_function(repo, _step_function(repo, "act"))
    calls = [
        n
        for n in ast.walk(act)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == GATHER_FN
    ]
    return Truth(len(calls) >= 2, GRAPH_PY, act.lineno, f"act gathers {len(calls)} rounds")


FOLLOW_UPS = "_BREADTH_FOLLOW_UPS"


def pubmed_follow_ups(repo: Repo) -> Truth:
    """What Act's second round does with a PubMed search's results, as the
    purposes `_BREADTH_FOLLOW_UPS["pubmed_search"]` names."""
    table = PyConst(GRAPH_PY, FOLLOW_UPS).read(repo)
    rows = dict(table.value).get("pubmed_search")
    if not rows:
        raise RegistryError(f"{GRAPH_PY}: {FOLLOW_UPS} has no pubmed_search row")
    return Truth(frozenset(row[3] for row in rows), GRAPH_PY, table.line)


# How a page names each follow-up purpose.
FOLLOW_UP_PHRASES = {
    "the abstracts of the papers a PubMed search found": "pubmed_abstracts",
    "PubTator3's markup of those papers": "pubtator_publications",
}


def follow_ups_named(match: re.Match[str]) -> frozenset[str]:
    items = [i.strip() for i in re.split(r"\s+or\s+", " ".join(match.group(1).split()))]
    named = set()
    for item in items:
        if item not in FOLLOW_UP_PHRASES:
            raise ValueError(f"the example {item!r} is none the registry reads")
        named.add(FOLLOW_UP_PHRASES[item])
    return frozenset(named)


LAYER3_PLANNER = "_build_layer_tool_calls"


def _layer3_call_site(repo: Repo) -> tuple[ast.AST, ast.Call, list[ast.AST]]:
    """plan_node, its one call to `_build_layer_tool_calls`, and the chain of
    statements that enclose that call inside plan_node."""
    plan = _graph_function(repo, _step_function(repo, "plan"))
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(plan):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    sites = [
        n
        for n in ast.walk(plan)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == LAYER3_PLANNER
    ]
    if len(sites) != 1:
        raise RegistryError(f"{GRAPH_PY}: plan_node calls {LAYER3_PLANNER} {len(sites)} times")
    chain = []
    node: ast.AST = sites[0]
    while node in parents:
        node = parents[node]
        chain.append(node)
    return plan, sites[0], chain


def layer3_not_every_question(repo: Repo) -> Truth:
    """True when plan_node reaches `_build_layer_tool_calls` only inside a
    branch, so some questions plan no layer 3 call at all (F-53-J02)."""
    _, site, chain = _layer3_call_site(repo)
    conditional = any(isinstance(n, (ast.If, ast.IfExp, ast.Match)) for n in chain)
    return Truth(
        conditional,
        GRAPH_PY,
        site.lineno,
        f"plan_node calls {LAYER3_PLANNER} "
        + ("inside a branch" if conditional else "on every path"),
    )


def _layer3_body(repo: Repo) -> ast.AST:
    return _graph_function(repo, LAYER3_PLANNER)


def _source(repo: Repo, node: ast.AST) -> str:
    return ast.unparse(node)


def layer3_triggers(repo: Repo) -> Truth:
    """What earns the layer 3 calls, read from the code (F-53-A01):

    - symbol: plan_node passes a gene symbol only for a mention with no
      colon in it, so a gene named by an identifier has none.
    - disease_fallback: `_build_layer_tool_calls` searches on the gene
      symbol, else the disease text.
    - rsid_cap: how many rs ids earn a LitVar2 call, the slice bound of
      the loop over them."""
    plan, _, _ = _layer3_call_site(repo)
    body = _layer3_body(repo)
    plan_src = _source(repo, plan)
    body_src = _source(repo, body)
    cap = None
    for node in ast.walk(body):
        if (
            isinstance(node, ast.For)
            and isinstance(node.iter, ast.Subscript)
            and isinstance(node.iter.slice, ast.Slice)
            and isinstance(node.iter.slice.upper, ast.Constant)
        ):
            cap = node.iter.slice.upper.value
    if cap is None:
        raise RegistryError(f"{GRAPH_PY}: {LAYER3_PLANNER} has no capped loop over rs ids")
    return Truth(
        {
            "symbol": "':' not in mention" in plan_src,
            "disease_fallback": "search_text = gene_symbol or disease_text" in body_src,
            "rsid_cap": cap,
        },
        GRAPH_PY,
        body.lineno,
    )


def layer3_other_ways(repo: Repo) -> Truth:
    """The paths that plan no layer 3 call, each read from plan_node:

    - identifier: a gene mention with a colon gets no symbol.
    - isolates: an isolate question takes its own branch.
    - papers: with no gene, the plan step reaches the literature decision,
      which asks the classifier, and a question read as wanting papers
      takes the topic branch instead.
    - disease_lookup: a disease whose MedGen name lookup fails has no
      search text, so it plans the graph call alone (F-53-V01).
    - disease_identifier: only a MedGen-shaped disease identifier is read
      for a search text, so any other vocabulary plans the graph call alone."""
    plan, _, chain = _layer3_call_site(repo)
    plan_src = _source(repo, plan)
    search_text = _graph_function(repo, "_disease_search_text")
    first_curie = _graph_function(repo, "_first_disease_curie")
    graph = call_graph(repo)
    plan_key = f"{GRAPH_MODULE}:{_step_function(repo, 'plan')}"
    literature = f"{GRAPH_MODULE}:_literature_choice"
    papers = graph.reaches(plan_key, literature) and "classifier" in graph.tiers(literature)
    return Truth(
        {
            "identifier": "':' not in mention" in plan_src,
            "isolates": "elif isolate_question is not None" in plan_src
            and any(isinstance(n, ast.If) for n in chain),
            "papers": papers and "topic_term" in plan_src,
            "disease_lookup": "if not disease_curie" in _source(repo, search_text)
            and "return None" in _source(repo, search_text),
            "disease_identifier": "startswith('MedGen:')" in _source(repo, first_curie),
        },
        GRAPH_PY,
        plan.lineno,
    )


# How a page says what each in-code layer 3 call returns, by the mode the
# call is planned with.
MODE_PHRASES = {
    "pubtator_annotate": {
        "looks the name up in its index of the genes and diseases found in published papers": (
            "entity_lookup"
        ),
        "returns the papers that mention the name": "annotate_publications",
    },
    "litvar2_lookup": {
        "finds a named variant and counts the papers that mention it": "variant_search",
        "returns the papers that mention a named variant": "publications_lookup",
    },
}


def layer3_modes(repo: Repo) -> Truth:
    """The mode each in-code layer 3 call is planned with, read from the
    `"mode"` key of the input `_build_layer_tool_calls` builds (F-53-A10)."""
    body = _layer3_body(repo)
    modes: dict[str, str] = {}
    for node in ast.walk(body):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", "") == "_layer_call"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Dict):
                    for key, value in zip(inner.keys, inner.values):
                        if (
                            isinstance(key, ast.Constant)
                            and key.value == "mode"
                            and isinstance(value, ast.Constant)
                        ):
                            modes[node.args[0].value] = value.value
    wanted = set(MODE_PHRASES)
    if not wanted <= set(modes):
        raise RegistryError(
            f"{GRAPH_PY}: {LAYER3_PLANNER} plans no mode for {sorted(wanted - set(modes))}"
        )
    return Truth({k: modes[k] for k in sorted(wanted)}, GRAPH_PY, body.lineno)


def modes_stated(match: re.Match[str]) -> dict[str, str]:
    said = {"pubtator_annotate": match.group(1), "litvar2_lookup": match.group(2)}
    out = {}
    for tool, phrase in said.items():
        phrase = " ".join(phrase.split())
        if phrase not in MODE_PHRASES[tool]:
            raise ValueError(f"{tool}: the wording {phrase!r} is none the registry reads")
        out[tool] = MODE_PHRASES[tool][phrase]
    return out


# How a page names a layer 3 tool.
TOOL_DISPLAY = {
    "pubtator_annotate": "PubTator3",
    "litvar2_lookup": "LitVar2",
    "clinicaltrials_search": "ClinicalTrials.gov",
}
NCBI_HOST = "ncbi.nlm.nih.gov"


def layer3_non_ncbi_hosts(repo: Repo) -> Truth:
    """The layer 3 tools whose API constants (module-level `..._URL` or
    `..._BASE` strings) point at a host outside NCBI."""
    tools = tools_in_layer(3)(repo).value
    outside = set()
    for tool in tools:
        if tool not in TOOL_DISPLAY:
            raise RegistryError(f"{tool}: a layer 3 tool with no display name in the registry")
        path = f"{PKG}/tools/{tool}.py"
        hosts = set()
        for node in parse_python(repo, path).body:
            target = (
                node.targets[0] if isinstance(node, ast.Assign) else getattr(node, "target", None)
            )
            name = getattr(target, "id", "")
            value = getattr(node, "value", None)
            if not name.endswith(("_URL", "_BASE")) or value is None:
                continue
            try:
                url = ast.literal_eval(value)
            except (ValueError, TypeError, SyntaxError):
                continue
            m = re.match(r"https://([^/]+)", url) if isinstance(url, str) else None
            if m:
                hosts.add(m.group(1))
        if not hosts:
            raise RegistryError(f"{path}: no API host constant")
        if any(not h.endswith(NCBI_HOST) for h in hosts):
            outside.add(TOOL_DISPLAY[tool])
    return Truth(frozenset(outside), TRANSPORT, 1, "layer 3 hosts outside ncbi.nlm.nih.gov")


def planned_row_limit(repo: Repo) -> Truth:
    """The most rows any graph call Plan builds asks for: every
    `row_limit=` keyword in core/graph.py, a literal or a module constant."""
    tree = parse_python(repo, GRAPH_PY)
    values = []
    line = 1
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "row_limit":
            if isinstance(node.value, ast.Constant):
                values.append(node.value.value)
            elif isinstance(node.value, ast.Name):
                values.append(PyConst(GRAPH_PY, node.value.id).read(repo).value)
            else:
                raise RegistryError(
                    f"{GRAPH_PY}: a row_limit that is neither a literal nor a constant"
                )
            line = node.value.lineno
    if not values:
        raise RegistryError(f"{GRAPH_PY}: no planned graph call passes a row_limit")
    return Truth(max(values), GRAPH_PY, line, f"row limits planned: {sorted(set(values))}")


def longest_budget(repo: Repo) -> Truth:
    """Which source has the longest per-call limit: the graph query, a web
    API call through the transport, or Pathogen Detection."""
    budgets = {
        "a graph query": PyConst(GRAPH_CONSTS, "CYPHER_QUERY_TIMEOUT_SECONDS").read(repo).value,
        "a call to a live web API": PyConst(TRANSPORT, "DEFAULT_TIMEOUT_S").read(repo).value,
        "Pathogen Detection": PyConst(PATHOGEN, "_TOTAL_BUDGET_S").read(repo).value,
    }
    top = max(budgets, key=budgets.get)
    return Truth(top, PATHOGEN, 1, ", ".join(f"{k} {v:g} s" for k, v in budgets.items()))


def transport_retries(repo: Repo) -> Truth:
    """How many retries a web API call gets: the attempts loop in
    `_execute_with_retry`, `for attempt_index in range(N)`, less one."""
    fn = next(
        (
            n
            for n in ast.walk(parse_python(repo, TRANSPORT))
            if isinstance(n, ast.AsyncFunctionDef | ast.FunctionDef)
            and n.name == "_execute_with_retry"
        ),
        None,
    )
    if fn is None:
        raise RegistryError(f"{TRANSPORT}: no _execute_with_retry")
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.For)
            and isinstance(node.iter, ast.Call)
            and getattr(node.iter.func, "id", "") == "range"
            and len(node.iter.args) == 1
            and isinstance(node.iter.args[0], ast.Constant)
        ):
            return Truth(node.iter.args[0].value - 1, TRANSPORT, node.lineno)
    raise RegistryError(f"{TRANSPORT}: _execute_with_retry has no attempts loop")


EXPORT_DIR = f"{PKG}/export"
# The graph-side modules an export may import. Anything else under tools/
# reaches a live API.
GRAPH_SIDE_TOOLS = frozenset(
    {"agtype", "graph_connection", "graph_schema_constants", "cypher_provenance", "cypher_query"}
)


def export_layer1_only(repo: Repo) -> Truth:
    """True when no module of the KGX export imports a tool module that
    reaches a live API: every `system_03_search_agent.tools` import is one
    of the graph-side modules."""
    reached = set()
    for rel in repo.python_files(EXPORT_DIR):
        for node in ast.walk(parse_python(repo, rel)):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            for name in names:
                m = re.fullmatch(r"system_03_search_agent\.tools\.(\w+)(?:\.\w+)?", name)
                if m:
                    reached.add(m.group(1))
    live = sorted(reached - GRAPH_SIDE_TOOLS)
    return Truth(
        not live,
        EXPORT_DIR + "/kgx.py",
        1,
        "the export imports only graph-side tools" if not live else "it imports " + ", ".join(live),
    )


def redis_unused(repo: Repo) -> Truth:
    """True when no Python module under src/ imports a Redis client."""
    users = [
        rel
        for rel in repo.python_files("src")
        for node in ast.walk(parse_python(repo, rel))
        if (
            isinstance(node, ast.Import)
            and any(a.name.split(".")[0] in {"redis", "aioredis"} for a in node.names)
        )
        or (
            isinstance(node, ast.ImportFrom)
            and (node.module or "").split(".")[0] in {"redis", "aioredis"}
        )
    ]
    return Truth(
        not users,
        PKG,
        1,
        "no module imports redis" if not users else "imported by " + ", ".join(users),
    )


def about_stop_count(repo: Repo) -> Truth:
    """How many stops the About walk renders: `<JourneyStop` elements inside
    `AboutScreen`, read from what a reader sees (comments excluded)."""
    doc = visible(repo, INFO).text
    start = doc.find("export function AboutScreen(")
    if start < 0:
        raise RegistryError(f"{INFO}: no AboutScreen")
    nxt = doc.find("\nexport function ", start + 1)
    body = doc[start : nxt if nxt > 0 else len(doc)]
    count = len(re.findall(r"<JourneyStop\b", body))
    return Truth(tuple(range(count)), INFO, line_of(doc, start))


USE_AGENT_RUN = "frontend/src/hooks/useAgentRun.ts"


def client_parsed_types(repo: Repo) -> Truth:
    """The event types the web client must parse: every type a run emits,
    less the frames `useAgentRun.ts` skips by name before parsing
    (`FORWARD_COMPATIBLE_EVENT_NAMES`). Read from that set, never from a
    copy here, so a frame the client stops skipping is a type the client
    must list. `cost`, which the server strips for a non-operator, is the
    place's own declared omission (`CLIENT_OMITS_ON_PURPOSE`)."""
    emitted = PyLiteral(EVENTS_PY, "type", cls="Event").read(repo)
    text = repo.text(USE_AGENT_RUN)
    m = re.search(r"FORWARD_COMPATIBLE_EVENT_NAMES[^=]*= new Set\(\[([^\]]*)\]\)", text)
    if m is None:
        raise RegistryError(f"{USE_AGENT_RUN}: no FORWARD_COMPATIBLE_EVENT_NAMES set")
    skipped = frozenset(quoted(m.group(1)))
    parsed = frozenset(emitted.value) - skipped
    note = "less the frames useAgentRun.ts skips by name: " + ", ".join(
        sorted(skipped & frozenset(emitted.value))
    )
    return Truth(parsed, EVENTS_PY, emitted.line, note)


def home_seeds(repo: Repo) -> Truth:
    """The example questions on the Home screen, in order."""
    seeds, block = _seeds(repo)
    return Truth(tuple(seeds), HOME_TSX, line_of(repo.text(HOME_TSX), block.start()))


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


def _add_seed(repo: Repo) -> dict[str, str]:
    """For the self-test: one more example question on the Home screen, so
    the count of seeds must move."""
    home = repo.text(HOME_TSX)
    _, block = _seeds(repo)
    at = block.start(1)
    return {HOME_TSX: home[:at] + '\n  { text: "mutant seed" },' + home[at:]}


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


def _layer3_on_every_path(repo: Repo) -> dict[str, str]:
    """For the self-test: plan_node calls `_build_layer_tool_calls` first
    thing, outside any branch, and the branch's own call is renamed."""
    text = repo.text(GRAPH_PY)
    text, one = re.subn(
        r"layer_calls = _build_layer_tool_calls\(", "layer_calls = _mutant_calls(", text, count=1
    )
    text, two = re.subn(
        r"(async def plan_node\(state: GraphState\) -> dict\[str, Any\]:\n)",
        r'\1    _build_layer_tool_calls("", None, [], None)\n',
        text,
        count=1,
    )
    return {GRAPH_PY: text} if one and two else {}


_merge_rounds = swap(
    GRAPH_PY,
    r"await _gather_planned_calls\(\[_run_one\(planned\) for planned in second_stage\]\)",
    "pass",
)
_add_stop = swap(
    INFO,
    r"<JourneyStop index=\{7\} last",
    '<JourneyStop index={8} title="mutant"><StopText>mutant</StopText></JourneyStop>\n'
    "<JourneyStop index={7} last",
)


PATHOGEN_LAYER = move_tool_layer("pathogen_detection", "layer_3_enrichment")
PUBTATOR_LAYER = move_tool_layer("pubtator_annotate", "layer_2_api")
PUBCHEM_LAYER = swap(TRANSPORT, r'"pubchem": 2,', '"pubchem": 3,')
NO_GRAPHQL = swap(QUERY_PY, r', "graphql"\]', "]")

# ------------------------------------------------------------------ helpers for places


def num(index: int = 1):
    return g(index, to_int)


def w(
    place: str,
    path: str,
    pattern: str,
    cmp=EXACT,
    parse=None,
    collect=None,
    flags=0,
    expect: int = 1,
    block: bool = False,
) -> Where:
    return Where(place, path, pattern, cmp, parse or num(), collect, flags, expect, block)


def everywhere(
    files: tuple[str, ...], pattern: str, cmp=EXACT, parse=None, flags=0
) -> tuple[Where, ...]:
    return tuple(w(DOC, f, pattern, cmp, parse, flags=flags) for f in files)


# ------------------------------------------------------------------ sentences
#
# Every place below states its WHOLE sentence (`sent`), because the engine
# fails a place whose match touches a sentence it does not cover (card 53).
# A sentence two facts read is written once here and used by both, each
# with its own group, so the two can never drift apart.

N = r"(\d+)"
W = r"(\w+)"
ANY_N = r"\d+"
ANY_W = r"\w+"


def claude_layer_one(nodes: str = ANY_N, edges: str = ANY_N, dbs: str = ANY_N) -> str:
    return sent(
        "Layer 1 provides the pre-ingested graph («n»M nodes, «e»M edges from «d» NCBI "
        "databases), hosted on Hetzner CPX42 (`<server-ip>`) and queryable via openCypher "
        "over psycopg2.",
        n=nodes,
        e=edges,
        d=dbs,
    )


def schema_holds(
    nodes: str = r"[\d,]+", edges: str = r"[\d,]+", v: str = ANY_N, e: str = ANY_N
) -> str:
    return sent(
        "It holds «n» nodes and «m» edges across «v» vertex labels and «e» edge labels.",
        n=nodes,
        m=edges,
        v=v,
        e=e,
    )


def about_merged(nodes: str = ANY_N, edges: str = ANY_N, dbs: str = r"(?:five|5)") -> str:
    return sent(
        "«n»M nodes and «e»M edges merged from «d» NCBI databases.", n=nodes, e=edges, d=dbs
    )


def arch_downloaded(dbs: str = r"\w+", biolink: str = r"\d+\.x") -> str:
    return sent(
        "«d» NCBI databases are downloaded in full from NCBI's FTP servers, parsed, mapped to "
        "the BioLink «b» model, validated against that schema, and written out as KGX files.",
        d=dbs,
        b=biolink,
    )


def arch_further(nodes: str = r"[\d,]+", labels: str = ANY_W, dbs: str = ANY_W) -> str:
    return sent(
        "Roughly «n» further nodes sit under «l» smaller labels: Gene Ontology terms, MeSH "
        "headings and phenotypes that arrive with the «d» databases above, plus a small number "
        "of stub records the merge left behind where an edge pointed at something no pipeline "
        "had produced.",
        n=nodes,
        l=labels,
        d=dbs,
    )


def arch_loaded(name: str = ANY_W, pg: str = ANY_N) -> str:
    return sent(
        "Those KGX files are merged and loaded into one graph, named «g», running on PostgreSQL "
        "«p» with the Apache AGE extension on a single Hetzner server.",
        g=name,
        p=pg,
    )


def readme_databases(count: str = ANY_N, names: str = r"[^)]+") -> str:
    return sent("| «c» NCBI databases («n») pre-ingested into PostgreSQL + AGE |", c=count, n=names)


def seven_tools(tools: str = ANY_W, layers: str = ANY_W) -> str:
    return sent(
        "«t» tools cover the «l» layers, each one reaching exactly one of them.", t=tools, l=layers
    )


def mcp_history(tools: str = ANY_W) -> str:
    return sent(
        "list_past_searches, reopen_past_answer and send_answer_feedback reach your account's own "
        "history, and the «t» internal tools are never separately reachable.",
        t=tools,
    )


def about_budgets(
    graph: str = ANY_N, live: str = ANY_N, pathogen: str = ANY_N, longest: str = r"[^,]+"
) -> str:
    return sent(
        "Each source has its own time limit in code: «g» seconds for a graph query, «l» seconds "
        "for a call to a live web API, and «p» seconds for «x», the longest.",
        g=graph,
        l=live,
        p=pathogen,
        x=longest,
    )


def arch_graph_budget(seconds: str = ANY_N, rows: str = ANY_N) -> str:
    return sent(
        "The search agent gives one graph query «s» seconds and asks it for at most «r» rows.",
        s=seconds,
        r=rows,
    )


def tool_card(tools: str, calls: str = r'[^"]*', budget: str | None = None) -> str:
    """One tool card in architectureFacts.ts's LAYERS: its name and what it
    calls, and its budget when the place reads it, each a whole string."""
    card = rf'name: "(?:{tools})",\s*calls: "{calls}"'
    return card + (rf',\s*budget: "{budget}"' if budget is not None else "")


LIVE_TOOLS = "ncbi_efetch|ncbi_dbsnp|pubtator_annotate|litvar2_lookup|clinicaltrials_search"
LIVE_BUDGET_TAILS = r"(?:, one retry| per call, two calls in sequence)?"


def l3_stop_modes(pubtator: str = r"[^,]+?", litvar: str = r"[^,]+?") -> str:
    return sent(
        "PubTator3 «p», LitVar2 «l», and ClinicalTrials.gov lists the trials registered under "
        "the name.",
        p=pubtator,
        l=litvar,
    )


def l3_stop_triggers(cap: str = ANY_W) -> str:
    return sent(
        "Plan decides which of them a question gets, from what Think found in it: PubTator3 and "
        "ClinicalTrials.gov for a gene named by its symbol or, when no gene was found, for a "
        "disease, and LitVar2 for up to «c» rs variant ids.",
        c=cap,
    )


L3_OTHER_WAYS = sent(
    "A gene named only by an identifier, a question about bacterial isolates, a question with no "
    "gene that a classifier reads as asking for papers, a disease whose MedGen name cannot be "
    "looked up, and a disease named by an identifier from another vocabulary are each searched "
    "another way, and for the last two that is the graph search alone."
)


def arch_second_round(
    examples: str = r"[\s\S]+?", when: str = ws("in a second round once the first has returned")
) -> str:
    return sent(
        "A call that needs another call's result, such as «x», goes out «w», and the answer "
        "waits for both rounds.",
        x=examples,
        w=when,
    )


def about_second_round(
    examples: str = r"[\s\S]+?", when: str = ws("in a second round once the first has returned")
) -> str:
    return sent(
        "A call that needs another call's result, such as «x», goes out «w».", x=examples, w=when
    )


SECOND_ROUND = either(
    "in a second round once the first has returned", "at the same time as the rest"
)
SECOND_ROUND_MEANS = wording(
    {"in a second round once the first has returned": True, "at the same time as the rest": False}
)


def manifest_note(
    l2: str = r"[^)]+", l3: str = r"[^)]+", present_in: str = ws("are not present")
) -> str:
    return sent(
        "Layer 2 (live NCBI APIs: «a») and Layer 3 (enrichment APIs: «b») are fetched live at "
        "query time by the search agent and «p» in this file.",
        a=l2,
        b=l3,
        p=present_in,
    )


def plan_tier_line(
    think: str = ws("Think's question analysis"),
    act: str = ws("writing a graph query in Act when no template fits"),
) -> str:
    return sent("- Plan tier: mid-range model for «t», and for «a».", t=think, a=act)


def arch_diagram_act(
    plan: str = ws("Plan tier to write a graph query when no template fits"),
    guard: str = ws("Guard tier to read article titles"),
) -> str:
    return sent("- Act: «p», and «g».", p=plan, g=guard)


def about_steps(share: str = ws("Every one"), steps: str = ANY_W) -> str:
    return sent(
        "«s» of the «n» steps can ask a language model something, and the harness decides which "
        "model each one gets.",
        s=share,
        n=steps,
    )


def tour_steps(count: str = ANY_W, names: str = r"[^.]+") -> str:
    return sent("The next screen shows the «c» steps the system takes: «n».", c=count, n=names)


def about_modes(default: str = r"[A-Z][a-z]+ [a-z]+", other: str = r"[A-Z][a-z]+") -> str:
    return sent(
        "You type a question and pick how the answer is written: «d», the default, or «o».",
        d=default,
        o=other,
    )


def tour_modes(default: str = r"[A-Z][a-z]+ [a-z]+", other: str = r"[A-Z][a-z]+") -> str:
    return sent(
        "«d», the default, gives the answer in simple terms, easy to understand. «o» gives it in "
        "technical terms, with the specifics and the records listed or in tables.",
        d=default,
        o=other,
    )


def mcp_card(
    count: str = ANY_W, first: str = r"\w+", rest: str = r"[a-z_, ]+?", internal: str = ANY_W
) -> str:
    return r'title="MCP server"\s+body="' + sent(
        "«c» tools. «f» folds a whole run into a single cited answer at any depth, with the "
        "session id to continue, the clarifying options and the trust line. «r» reach your "
        "account's own history, and the «i» internal tools are never separately reachable.",
        c=count,
        f=first,
        r=rest,
        i=internal,
    )


def arch_diagram_mcp(count: str = ANY_W, names: str = r".+?") -> str:
    return sent(
        "- MCP server: «c» tools, «n», mounted at `/mcp` on the same application.", c=count, n=names
    )


S3_SENTENCE = sent(
    "s3 asks a question and prints the answer, human-readable by default and JSON with «o».",
    o=r"(--[a-z-]+)",
)
KGX_SENTENCE = sent(
    "s3-kgx-export writes a query-scoped subgraph as BioLink-compliant KGX: nodes.tsv, edges.tsv "
    "and a manifest, from seed CURIEs and bounded hops."
)
GUESTS_REFUSED = sent(
    "GraphQL and the MCP server: an account is required, so a guest cannot reach either."
)

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
            w(ABOUT, INFO, about_merged(nodes=N), MILLIONS, expect=2),
            w(HOME, HOME_TSX, r'"(\d+)M nodes, \d+M edges"', MILLIONS),
        ),
        downstream=(
            *everywhere(INSTRUCTION_FILES, claude_layer_one(nodes=N), MILLIONS),
            w(
                DOC,
                README,
                sent(
                    "Agentic search agent for querying NCBI biomedical data across a «n»M-node "
                    "knowledge graph and 30+ live APIs.",
                    n=N,
                ),
                MILLIONS,
            ),
            w(DOC, SCHEMA_VIS, schema_holds(nodes=r"([\d,]+)")),
        ),
    ),
    Fact(
        "graph.edges",
        "how many edges the knowledge graph holds",
        TextMatch(KG_REF, r"nodes and ([\d,]+) edges across", g(1, to_int)),
        stated=(
            w(ARCH_ABOUT, FACTS_TS, r'EDGE_COUNT = "([\d,]+)"'),
            w(INTEGRATIONS, INFO, r'"(\d+)M edges"', MILLIONS),
            w(ABOUT, INFO, about_merged(edges=N), MILLIONS, expect=2),
            w(HOME, HOME_TSX, r'"\d+M nodes, (\d+)M edges"', MILLIONS),
        ),
        downstream=(
            *everywhere(INSTRUCTION_FILES, claude_layer_one(edges=N), MILLIONS),
            w(DOC, SCHEMA_VIS, schema_holds(edges=r"([\d,]+)")),
        ),
    ),
    Fact(
        "graph.vertex_labels",
        "how many vertex labels the graph has",
        TextMatch(KG_REF, r"across (\d+) vertex labels", g(1, to_int)),
        stated=(w(ARCH, FACTS_TS, r'VERTEX_LABEL_COUNT = "(\d+)"'),),
        downstream=(w(DOC, SCHEMA_VIS, schema_holds(v=N)),),
    ),
    Fact(
        "graph.edge_labels",
        "how many edge labels the graph has",
        TextMatch(KG_REF, r"vertex labels and (\d+) edge labels", g(1, to_int)),
        stated=(w(ARCH, FACTS_TS, r'EDGE_LABEL_COUNT = "(\d+)"'),),
        downstream=(w(DOC, SCHEMA_VIS, schema_holds(e=N)),),
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
                expect=5,
            ),
        ),
    ),
    Fact(
        "graph.databases",
        "which NCBI databases the graph is built from",
        TextMatch(
            KG_REF, r"which were ([^.]+)\. It contains", lambda m: frozenset(words_list(m.group(1)))
        ),
        stated=(
            w(ARCH_ABOUT, FACTS_TS, r'source: "(?:NCBI )?([^"]+)"', SET, g(), union, expect=5),
        ),
        downstream=(
            w(
                DOC,
                README,
                readme_databases(names=r"([^)]+)"),
                SET,
                lambda m: frozenset(words_list(m.group(1))),
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
            w(ABOUT, INFO, about_merged(dbs=r"(five|5)"), COUNT, expect=2),
            w(
                ABOUT,
                INFO,
                sent(
                    "It is built from «d» NCBI databases: ${SOURCE_DATABASE_NAMES.slice(0, -1)"
                    '.join(", ")} and ${SOURCE_DATABASE_NAMES[SOURCE_DATABASE_NAMES.length - 1]}.',
                    d=W,
                ),
                COUNT,
            ),
            w(ARCH, ARCH_TSX, arch_downloaded(dbs=r"(Five)"), COUNT),
            w(
                ARCH,
                ARCH_TSX,
                sent("The «d» source databases, and what each contributes", d=W),
                COUNT,
            ),
            w(ARCH, ARCH_TSX, arch_further(dbs=W), COUNT),
        ),
        downstream=(
            *everywhere(INSTRUCTION_FILES, claude_layer_one(dbs=N), COUNT),
            w(DOC, README, readme_databases(count=N), COUNT),
        ),
    ),
    Fact(
        "graph.minor_label_nodes",
        "how many nodes sit outside the five main labels",
        Computed(KG_REF, minor_label_nodes, GENE_ROW),
        stated=(w(ARCH, ARCH_TSX, arch_further(nodes=r"([\d,]+)"), THOUSANDS),),
    ),
    Fact(
        "graph.minor_label_count",
        "how many smaller labels hold those nodes",
        Computed(KG_REF, minor_label_count, DISEASE_ROW),
        stated=(w(ARCH, ARCH_TSX, arch_further(labels=W)),),
    ),
    Fact(
        "graph.gene_rows",
        "how many Gene nodes an unindexed lookup would scan",
        Computed(KG_REF, gene_rows, GENE_ROW),
        stated=(
            w(
                ARCH,
                ARCH_TSX,
                sent(
                    "Every node identifier is indexed, so finding the starting point is a lookup "
                    "rather than a scan of «n» million rows, and both ends of every edge are "
                    "indexed too, so following one is a lookup as well.",
                    n=N,
                ),
                MILLIONS,
            ),
        ),
    ),
    Fact(
        "graph.snapshot_date",
        "the date the loaded graph snapshot was finished",
        PyConst(CYPHER_QUERY, "_DEFAULT_GRAPH_SNAPSHOT_VERSION", snapshot_date),
        stated=(
            w(ARCH_ABOUT, FACTS_TS, r'SNAPSHOT_DATE = "([^"]+)"', EXACT, g(1, to_date)),
            w(
                ARCH,
                ARCH_TSX,
                sent(
                    "A record that has changed since «m», and every NCBI database the graph "
                    "deliberately leaves out, is fetched from NCBI at the moment you ask.",
                    m=W,
                ),
                MONTH,
                g(),
            ),
        ),
    ),
    Fact(
        "graph.name",
        "the name of the graph the agent queries",
        PyConst(GRAPH_CONSTS, "GRAPH_NAME"),
        stated=(
            w(ARCH, ARCH_TSX, arch_loaded(name=W), EXACT, g()),
            w(ARCH, FACTS_TS, r'calls: "the (\w+) graph, PostgreSQL with Apache AGE"', EXACT, g()),
        ),
        downstream=(
            w(
                DOC,
                SCHEMA_VIS,
                sent("The graph is one Apache AGE graph called `«g»`.", g=W),
                EXACT,
                g(),
            ),
        ),
    ),
    Fact(
        "graph.postgres_version",
        "the PostgreSQL major version the graph runs on",
        TextMatch(KG_REF, r"\| PostgreSQL \| (\d+)\.\d+ \|", g(1, to_int)),
        stated=(w(ARCH, ARCH_TSX, arch_loaded(pg=N)),),
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
                sent(
                    "Naming the edge label is the other half: the first version of this exact "
                    "query took «a» minutes and «b» seconds without it, and «c» milliseconds "
                    "with it.",
                    a=N,
                    b=N,
                    c=N,
                ),
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
                pipeline_step_names,
                flags=S,
            ),
        ),
    ),
    Fact(
        "graph.biolink_version",
        "the BioLink model version the pipelines map to",
        TextMatch(REF_CLAUDE, r"BioLink (\d+\.x)", g()),
        stated=(w(ARCH, ARCH_TSX, arch_downloaded(biolink=r"(\d+\.x)"), EXACT, g()),),
    ),
    # ---- tools and layers
    Fact(
        "tools.count",
        "how many tools the agent has",
        PyLiteral(EVENTS_PY, "ToolName"),
        stated=(
            w(INTEGRATIONS, INFO, r'"(\d+) tools"', COUNT),
            w(INTEGRATIONS, INFO, mcp_history(tools=W), COUNT),
            w(INTEGRATIONS, INFO, mcp_card(internal=W), COUNT),
            w(
                ABOUT,
                INFO,
                sent(
                    "All of these calls open with the same unchanging block of text: the system "
                    "instructions, the descriptions of the «t» tools, and the graph's own schema.",
                    t=W,
                ),
                COUNT,
            ),
            w(ARCH, ARCH_TSX, seven_tools(tools=r"(Seven)"), COUNT),
        ),
        downstream=(
            *everywhere(INSTRUCTION_FILES, r"PLANNED, (\w+) tools: [a-z0-9_, ]+\.(?=\s+Build)", COUNT),
            w(DOC, ARCH_DIAGRAM, r"## The \w+ data layers and the (\w+) tools", COUNT),
            w(
                DOC,
                SCHEMA_VIS,
                sent(
                    "It owns four of them: the event contract, the citation and provenance type, "
                    "the user-data schema in PostgreSQL, then the input and output schema of each "
                    "of the «t» tools.",
                    t=W,
                ),
                COUNT,
            ),
            w(DOC, SCHEMA_VIS, r'string tool "one of (\w+)"', COUNT),
            w(
                DOC,
                README,
                sent(
                    "Locked. 25 sections, «t» tools, six delivery surfaces (web UI, REST plus SSE "
                    "API, GraphQL API, MCP server, KGX export, CLI), Section 25 build order",
                    t=W,
                ),
                COUNT,
            ),
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
                INSTRUCTION_FILES,
                r"PLANNED, \w+ tools: ([a-z0-9_, ]+)\.(?=\s+Build)",
                SET,
                word_set,
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
                block=True,
            ),
            w(
                ARCH,
                FACTS_TS,
                r"export const LAYERS[^=]*= \[(.*?)\n\];",
                MAPPING,
                ts_layers("name"),
                flags=S,
                block=True,
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
                expect=7,
            ),
        ),
    ),
    Fact(
        "layers.count",
        "how many data layers there are",
        PyLiteral(EVENTS_PY, "Layer"),
        stated=(
            w(INTEGRATIONS, INFO, r'"(\d+) data layers"', COUNT),
            w(ABOUT, INFO, sent("Every question crosses up to «n» data layers.", n=W), COUNT),
            w(
                ABOUT,
                INFO,
                sent(
                    "Act sends out the calls Plan chose, across «n» layers of data, together "
                    "rather than one after another.",
                    n=W,
                ),
                COUNT,
            ),
            w(
                ARCH,
                ARCH_TSX,
                sent(
                    "«n» data layers feed one search agent: the pipelines and the knowledge graph "
                    "they build, the live NCBI APIs, and the enrichment APIs.",
                    n=r"(Three)",
                ),
                COUNT,
            ),
            w(ARCH, ARCH_TSX, seven_tools(layers=W), COUNT),
        ),
        downstream=(
            *everywhere(INSTRUCTION_FILES, r"(Three)-layer data access:", COUNT),
            w(DOC, ARCH_DIAGRAM, r"## The (\w+) data layers and the \w+ tools", COUNT),
            w(DOC, SCHEMA_VIS, r'string layer "one of (\w+)"', COUNT),
        ),
    ),
    Fact(
        "layers.l2_tools",
        "how many tools reach the live NCBI APIs",
        Computed(EVENTS_PY, tools_in_layer(2), PATHOGEN_LAYER),
        stated=(
            w(
                ABOUT,
                INFO,
                r'n: 2,\s*name: "Live NCBI APIs",\s*tools: "([^"]+)",\s*body: "'
                + sent(
                    "Fetched while you wait, so they are current. Used for anything the graph "
                    "cannot name, such as turning a concept id into a disease name."
                )
                + '"',
                COUNT,
                lambda m: len(words_list(m.group(1))),
            ),
            w(
                ARCH,
                ARCH_TSX,
                sent(
                    "«n» tools cover that, and what they return is current by definition.",
                    n=r"(Three)",
                ),
                COUNT,
            ),
        ),
    ),
    Fact(
        "layers.l3_tools",
        "how many tools add enrichment",
        Computed(EVENTS_PY, tools_in_layer(3), PUBTATOR_LAYER),
        stated=(
            w(
                ARCH,
                ARCH_TSX,
                sent(
                    "«n» further tools add evidence around the gene, disease or variant a "
                    "question names.",
                    n=r"(Three)",
                ),
                COUNT,
            ),
        ),
    ),
    Fact(
        "layers.l2_apis",
        "which live NCBI APIs layer 2 calls",
        Computed(TRANSPORT, api_families(2), PUBCHEM_LAYER),
        stated=(
            w(
                ABOUT,
                INFO,
                r'colour: designTokens\.layer2,\s*body: "'
                + sent(
                    "«l», called at the moment you ask. Narrower and slower, and always current.",
                    l=r"(.+?)",
                )
                + '"',
                SET,
                named_families,
            ),
            w(
                ARCH,
                FACTS_TS,
                tool_card("ncbi_efetch|ncbi_dbsnp|pathogen_detection", calls=r'([^"]+)'),
                SET,
                named_families,
                union,
                expect=3,
            ),
        ),
        downstream=(
            *everywhere(
                INSTRUCTION_FILES,
                sent("Layer 2: NCBI APIs live («l», called at query time)", l=r"([^)]+?)"),
                SET,
                named_families,
            ),
            w(
                DOC,
                README,
                sent(
                    "| Layer 2: on-demand NCBI APIs | 30+ databases reached at query time via «l» |",
                    l=r"([^|]+?)",
                ),
                SET,
                named_families,
            ),
            w(CODE, KGX_MANIFEST, manifest_note(l2=r"([^)]+)"), SET, named_families),
        ),
    ),
    Fact(
        "layers.l3_apis",
        "which enrichment APIs layer 3 calls",
        Computed(TRANSPORT, api_families(3), PATHOGEN_LAYER),
        stated=(
            w(
                ABOUT,
                INFO,
                r'colour: designTokens\.layer3,\s*body: "'
                + sent(
                    "«l». Literature and trial evidence about the gene, disease or variant a "
                    "question names, when Plan adds them.",
                    l=r"(.+?)",
                )
                + '"',
                SET,
                named_families,
            ),
            w(
                ARCH,
                FACTS_TS,
                tool_card(
                    "pubtator_annotate|litvar2_lookup|clinicaltrials_search", calls=r'([^"]+)'
                ),
                SET,
                named_families,
                union,
                expect=3,
            ),
        ),
        downstream=(
            *everywhere(
                INSTRUCTION_FILES,
                sent("Layer 3: Enrichment APIs («l»)", l=r"([^)]+)"),
                SET,
                named_families,
            ),
            w(
                DOC,
                README,
                sent("| Layer 3: enrichment APIs | «l» |", l=r"([^|]+?)"),
                SET,
                named_families,
            ),
            w(CODE, KGX_MANIFEST, manifest_note(l3=r"([^)]+)"), SET, named_families),
        ),
    ),
    Fact(
        "layers.l3_not_every_question",
        "Plan adds layer 3 calls on one branch only, so not every question gets them",
        Computed(
            GRAPH_PY,
            layer3_not_every_question,
            _layer3_on_every_path,
        ),
        stated=(
            w(
                ARCH,
                ARCH_TSX,
                either("Not every question gets them.", "Every question gets them."),
                BOOL,
                wording(
                    {"Not every question gets them.": True, "Every question gets them.": False}
                ),
            ),
            w(
                ARCH,
                FACTS_TS,
                sent(
                    "Literature and trial evidence about the gene, disease or variant a question "
                    "names. Plan decides whether a question gets it, and «w».",
                    w=either("not every question does", "every question does"),
                ),
                BOOL,
                wording({"not every question does": True, "every question does": False}),
            ),
            w(
                ABOUT,
                INFO,
                sent(
                    "Literature and trial evidence. Plan adds them here because the question "
                    "names a gene by its symbol, BRCA1, though «w».",
                    w=either("not every question gets them", "every question gets them"),
                ),
                BOOL,
                wording({"not every question gets them": True, "every question gets them": False}),
            ),
            w(
                ABOUT,
                INFO,
                sent(
                    "Literature and trial evidence about the gene, disease or variant a question "
                    "names, «w».",
                    w=either("when Plan adds them", "for every question"),
                ),
                BOOL,
                wording({"when Plan adds them": True, "for every question": False}),
            ),
        ),
    ),
    Fact(
        "layers.l3_triggers",
        "what earns the layer 3 calls: a gene named by its symbol, else a disease, and up to "
        "a fixed number of rs ids for LitVar2",
        Computed(
            GRAPH_PY,
            layer3_triggers,
            swap(GRAPH_PY, r"for rsid in rsids\[:2\]:", "for rsid in rsids[:3]:"),
        ),
        stated=(
            w(
                ARCH,
                ARCH_TSX,
                l3_stop_triggers(cap=W),
                MAPPING,
                lambda m: {
                    "symbol": True,
                    "disease_fallback": True,
                    "rsid_cap": to_int(m.group(1)),
                },
            ),
        ),
    ),
    Fact(
        "layers.l3_other_ways",
        "which questions plan no layer 3 call: a gene named by an identifier, an isolate "
        "question, a no-gene question the literature classifier reads as asking for papers, and "
        "a disease with no MedGen name or with another vocabulary's identifier",
        Computed(
            GRAPH_PY,
            layer3_other_ways,
            swap(GRAPH_PY, r'if mention and ":" not in mention:', "if mention:"),
        ),
        stated=(
            w(
                ARCH,
                ARCH_TSX,
                L3_OTHER_WAYS,
                MAPPING,
                lambda m: {
                    "identifier": True,
                    "isolates": True,
                    "papers": True,
                    "disease_lookup": True,
                    "disease_identifier": True,
                },
            ),
        ),
    ),
    Fact(
        "layers.l3_modes",
        "what the PubTator3 and LitVar2 calls Plan adds return, by the mode each is planned with",
        Computed(
            GRAPH_PY,
            layer3_modes,
            swap(GRAPH_PY, r'\{"mode": "entity_lookup"', '{"mode": "annotate_publications"'),
        ),
        stated=(
            w(
                ARCH,
                ARCH_TSX,
                l3_stop_modes(pubtator=r"([^,]+?)", litvar=r"([^,]+?)"),
                MAPPING,
                modes_stated,
            ),
        ),
    ),
    Fact(
        "layers.l3_non_ncbi_host",
        "which layer 3 source is not an NCBI host",
        Computed(
            TRANSPORT,
            layer3_non_ncbi_hosts,
            swap(
                f"{PKG}/tools/litvar2_lookup.py",
                r'_LITVAR2_BASE: Final\[str\] = "https://www\.ncbi\.nlm\.nih\.gov',
                '_LITVAR2_BASE: Final[str] = "https://litvar.example.org',
            ),
        ),
        stated=(
            w(
                ARCH,
                ARCH_TSX,
                sent(
                    "«t» is the one source here that is not an NCBI host.",
                    t=r"(ClinicalTrials\.gov|PubTator3|LitVar2)",
                ),
                SET,
                lambda m: frozenset({m.group(1)}),
            ),
        ),
    ),
    # ---- budgets
    Fact(
        "budget.graph_query_s",
        "how long one graph query may take, in seconds",
        PyConst(GRAPH_CONSTS, "CYPHER_QUERY_TIMEOUT_SECONDS", int),
        stated=(
            w(ARCH, FACTS_TS, r'budget: "(\d+) seconds, at most \d+ rows"'),
            w(ARCH, ARCH_TSX, arch_graph_budget(seconds=N)),
            w(ABOUT, INFO, about_budgets(graph=N)),
        ),
        downstream=(
            w(DOC, ARCH_DIAGRAM, r'CQ\["cypher_query, (\d+) s"\]'),
            w(DOC, ARCH_DIAGRAM, r"\| cypher_query \| Layer 1 \| (\d+) seconds \|"),
            w(
                DOC,
                DEEP_DIVE,
                r"\| A whole `cypher_query` call, Cypher writing included \| (\d+) s \|",
            ),
            w(CODE, CATALOGUE, r"_CYPHER_QUERY_BUDGET = \((\d+)\.0"),
        ),
    ),
    Fact(
        "budget.row_limit",
        "the most rows the cypher_query tool's schema lets one graph query return",
        PyConst(GRAPH_CONSTS, "MAX_ROW_LIMIT"),
        downstream=(
            w(DOC, ARCH_DIAGRAM, r"Row limit (\d+), plus a per-caller limit at the service"),
        ),
    ),
    Fact(
        "budget.planned_rows",
        "the most rows any graph call Plan builds asks for",
        Computed(
            GRAPH_PY,
            planned_row_limit,
            swap(GRAPH_PY, r"_PLAN_TOOL_CALL_ROW_LIMIT = 100", "_PLAN_TOOL_CALL_ROW_LIMIT = 250"),
        ),
        stated=(
            w(ARCH, FACTS_TS, r'budget: "\d+ seconds, at most (\d+) rows"'),
            w(ARCH, ARCH_TSX, arch_graph_budget(rows=N)),
        ),
    ),
    Fact(
        "budget.live_call_s",
        "how long one live NCBI or enrichment call may take, in seconds",
        PyConst(TRANSPORT, "DEFAULT_TIMEOUT_S", int),
        stated=(
            w(ABOUT, INFO, about_budgets(live=N)),
            w(
                ARCH,
                FACTS_TS,
                tool_card(LIVE_TOOLS, budget=r"(\d+) seconds" + LIVE_BUDGET_TAILS),
                flags=S,
                expect=5,
            ),
        ),
        downstream=(
            w(DOC, ARCH_DIAGRAM, r'(?:EF|DB|PT|LV|CT)\["\w+, (\d+) s(?: per call)?"\]', expect=5),
            w(
                DOC,
                ARCH_DIAGRAM,
                rf"\| (?:{LIVE_TOOLS}) \| Layer \d \| (\d+) seconds"
                r"(?:, one backoff retry| per call, two sequential calls)? \|",
                expect=5,
            ),
            w(DOC, DEEP_DIVE, r"\| One Layer 2 or Layer 3 HTTP call \| (\d+) s by default \|"),
            w(
                CODE,
                CATALOGUE,
                r"_(?:NCBI_EFETCH|NCBI_DBSNP|PUBTATOR|LITVAR2|CLINICALTRIALS)_BUDGET = \(\s*(\d+)\.0",
                expect=5,
            ),
        ),
    ),
    Fact(
        "budget.live_retries",
        "how many retries one live web API call gets",
        Computed(
            TRANSPORT,
            transport_retries,
            swap(TRANSPORT, r"for attempt_index in range\(2\):", "for attempt_index in range(3):"),
        ),
        stated=(w(ARCH, FACTS_TS, tool_card("ncbi_efetch", budget=r"\d+ seconds, (one) retry")),),
        downstream=(
            w(
                DOC,
                ARCH_DIAGRAM,
                r"\| ncbi_efetch \| Layer \d \| \d+ seconds, (one) backoff retry \|",
            ),
        ),
    ),
    Fact(
        "budget.pathogen_s",
        "how long one Pathogen Detection call may take, in seconds",
        PyConst(PATHOGEN, "_TOTAL_BUDGET_S", int),
        stated=(
            w(ARCH, FACTS_TS, tool_card("pathogen_detection", budget=r"(\d+) seconds")),
            w(ABOUT, INFO, about_budgets(pathogen=N)),
        ),
        downstream=(
            w(DOC, ARCH_DIAGRAM, r'PD\["pathogen_detection, (\d+) s"\]'),
            w(
                DOC,
                ARCH_DIAGRAM,
                r"\| pathogen_detection \| Layer 2 \| (\d+) seconds total, \d+ seconds per transfer \|",
            ),
            w(
                DOC,
                DEEP_DIVE,
                r"\| Pathogen Detection isolate search \| (\d+) s for all of one call's reads, and "
                r"Act waits up to \d+ s \|",
            ),
            w(CODE, CATALOGUE, r"_PATHOGEN_DETECTION_BUDGET = \(\s*(\d+)\.0"),
        ),
    ),
    Fact(
        "budget.pathogen_transfer_s",
        "how long one Pathogen Detection file transfer may take, in seconds",
        PyConst(PATHOGEN_FTP, "DEFAULT_TIMEOUT_S", int),
        downstream=(
            w(
                DOC,
                ARCH_DIAGRAM,
                r"\| pathogen_detection \| Layer 2 \| \d+ seconds total, (\d+) seconds per transfer \|",
            ),
        ),
    ),
    Fact(
        "budget.pathogen_act_s",
        "how long Act waits for a Pathogen Detection call, in seconds",
        Computed(
            GRAPH_PY,
            lambda repo: PyConst(
                GRAPH_PY, "_LAYER_TOOL_ACT_TIMEOUT_SECONDS", lambda d: int(d["pathogen_detection"])
            ).read(repo),
            swap(GRAPH_PY, r'"pathogen_detection": 150\.0,', '"pathogen_detection": 151.0,'),
        ),
        downstream=(
            w(
                DOC,
                DEEP_DIVE,
                r"\| Pathogen Detection isolate search \| \d+ s for all of one call's reads, and "
                r"Act waits up to (\d+) s \|",
            ),
        ),
    ),
    Fact(
        "budget.longest",
        "which source has the longest per-call time limit",
        Computed(
            PATHOGEN,
            longest_budget,
            swap(
                PATHOGEN,
                r"_TOTAL_BUDGET_S: Final\[float\] = 120\.0",
                "_TOTAL_BUDGET_S: Final[float] = 5.0",
            ),
        ),
        stated=(w(ABOUT, INFO, about_budgets(longest=r"([^,]+)"), EXACT, g()),),
    ),
    Fact(
        "budget.live_calls_per_question",
        "how many live layer 2 and 3 calls one question may make",
        PyConst(CALL_BUDGET, "MAX_LAYER_2_3_CALLS_PER_QUERY"),
        stated=(
            w(ABOUT, INFO, sent("One question may make at most «n» live calls in total.", n=N)),
            w(
                INTEGRATIONS,
                INFO,
                sent(
                    "Each tool carries its own per-call timeout and rate-limit pool, and a query is "
                    "capped at «n» Layer 2 and Layer 3 calls.",
                    n=W,
                ),
            ),
        ),
        downstream=(
            w(
                DOC,
                ARCH_DIAGRAM,
                sent(
                    "- Call budget: at most «n» Layer 2 and Layer 3 calls per query, counted at the "
                    "transport rather than at Act, plus a queue wait ceiling derived from the "
                    "calling query's own latency budget.",
                    n=N,
                ),
            ),
            w(
                DOC,
                DEEP_DIVE,
                sent(
                    "- The call ceiling: at most «n» Layer 2 and Layer 3 calls per question "
                    "(`harness/call_budget.py`, `MAX_LAYER_2_3_CALLS_PER_QUERY`).",
                    n=N,
                ),
            ),
        ),
    ),
    # ---- the event stream
    Fact(
        "events.types",
        "the kinds of event a run emits",
        PyLiteral(EVENTS_PY, "type", cls="Event"),
        stated=(
            w(
                INTEGRATIONS,
                INFO,
                r"A run emits (\w+) kinds of event: [a-z_, ]+?\.(?=\s+Each SSE)",
                COUNT,
            ),
            w(
                INTEGRATIONS,
                INFO,
                r"A run emits \w+ kinds of event: ([a-z_, ]+?)\.(?=\s+Each SSE)",
                SET,
                word_set,
            ),
        ),
        downstream=(w(DOC, SCHEMA_VIS, r'string type "one of (\w+)"', COUNT),),
    ),
    Fact(
        "events.client_types",
        "the event types the web client lists as known: every type a run emits, less the "
        "frames useAgentRun.ts skips by name and cost, which the server strips",
        Computed(
            EVENTS_PY,
            client_parsed_types,
            swap(USE_AGENT_RUN, r'new Set\(\["step", "stage"\]\)', 'new Set(["stage"])'),
        ),
        stated=(
            w(
                CODE,
                EVENTS_TS,
                r"export const KNOWN_EVENT_TYPES[^=]*= \[(.*?)\];",
                set_allowing_omitted(CLIENT_OMITS_ON_PURPOSE),
                lambda m: frozenset(quoted(m.group(1))),
                flags=S,
            ),
        ),
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
                block=True,
            ),
        ),
    ),
    Fact(
        "events.guard_categories",
        "the reasons a question can be turned away",
        PyLiteral(EVENTS_PY, "category", cls="GuardPayload"),
        stated=(
            w(
                BANNER,
                BANNER_TSX,
                r"CATEGORY_COPY[^=]*= \{(.*?)\n\};",
                SET,
                ts_keys,
                flags=S,
                block=True,
            ),
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
            w(TOUR, TOUR_TSX, sent("A question can run to about «n» characters.", n=r"([\d,]+)")),
            w(HOME, HOME_TSX, r"QUESTION_MAX_LENGTH = (\d+)"),
        ),
    ),
    Fact(
        "modes.accepted",
        "the answer modes the web app sends are ones the server accepts",
        PyLiteral(QUERY_PY, "audience_depth", cls="Query"),
        stated=(w(CODE, DEPTH_TSX, r'\{ value: "(\w+)", label:', SUBSET, g(), union, expect=2),),
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
            w(ABOUT, INFO, about_modes(default=r"([A-Z][a-z]+ [a-z]+)"), EXACT, g()),
            w(TOUR, TOUR_TSX, tour_modes(default=r"([A-Z][a-z]+ [a-z]+)"), EXACT, g()),
        ),
    ),
    Fact(
        "modes.labels",
        "the answer modes a person can pick",
        Computed(
            DEPTH_TSX, mode_labels, swap(DEPTH_TSX, r'label: "Researcher" \}', 'label: "Scholar" }')
        ),
        stated=(
            w(
                ABOUT,
                INFO,
                about_modes(default=r"([A-Z][a-z]+ [a-z]+)", other=r"([A-Z][a-z]+)"),
                SET,
                modes_named,
            ),
            w(
                TOUR,
                TOUR_TSX,
                tour_modes(default=r"([A-Z][a-z]+ [a-z]+)", other=r"([A-Z][a-z]+)"),
                SET,
                modes_named,
            ),
        ),
    ),
    # ---- how the agent is reached
    Fact(
        "surfaces.count",
        "how many ways a program can reach the agent",
        Computed(QUERY_PY, programmatic_surfaces, NO_GRAPHQL),
        stated=(
            w(
                INTEGRATIONS,
                INFO,
                sent("The same agent, reachable «n» ways, returning the same citations.", n=W),
                COUNT,
            ),
        ),
    ),
    Fact(
        "surfaces.named",
        "which ways a program can reach the agent",
        Computed(QUERY_PY, programmatic_surfaces, NO_GRAPHQL),
        stated=(
            w(
                TOUR,
                TOUR_TSX,
                sent("Integrations lists the other ways in: «l».", l=r"([^.]+)"),
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
                expect=4,
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
            w(INTEGRATIONS, INFO, mcp_card(count=W), COUNT, flags=S),
            w(
                INTEGRATIONS,
                INFO,
                mcp_card(first=r"(\w+)", rest=r"([a-z_, ]+?)"),
                SET,
                snake_names,
                flags=S,
            ),
        ),
        downstream=(
            w(DOC, ARCH_DIAGRAM, arch_diagram_mcp(count=W), COUNT),
            w(DOC, ARCH_DIAGRAM, arch_diagram_mcp(names=r"(.+?)"), SET, snake_names),
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
            w(
                INTEGRATIONS,
                INFO,
                sent(
                    "«n» console commands rather than HTTP routes.",
                    n=r"(Two)",
                ),
                COUNT,
            ),
            w(
                INTEGRATIONS,
                INFO,
                r"(?:" + S3_SENTENCE.replace("(--[a-z-]+)", "--[a-z-]+") + "|" + KGX_SENTENCE + ")",
                SET,
                lambda m: frozenset({m.group(0).split()[0]}),
                union,
                expect=2,
            ),
        ),
    ),
    Fact(
        "surfaces.s3_options",
        "the options the s3 command accepts",
        Computed(S3_CLI, cli_options(S3_CLI), swap(S3_CLI, r'"--depth",', '"--json",')),
        stated=(w(INTEGRATIONS, INFO, S3_SENTENCE, MEMBER, g()),),
    ),
    Fact(
        "access.login_route",
        "the route that exchanges an email and password for a token",
        Computed(
            AUTH_ROUTER,
            auth_routes,
            swap(AUTH_ROUTER, r'@router\.post\("/login"', '@router.post("/mutant"'),
        ),
        stated=(
            w(
                INTEGRATIONS,
                INFO,
                sent(
                    "POST «r» exchanges the same email and password you use here for that token "
                    "and a refresh token.",
                    r=r"(/auth/\w+)",
                ),
                MEMBER,
                g(),
            ),
        ),
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
        stated=(w(INTEGRATIONS, INFO, GUESTS_REFUSED, BOOL, present),),
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
        stated=(w(INTEGRATIONS, INFO, GUESTS_REFUSED, BOOL, present),),
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
            w(
                INTEGRATIONS,
                INFO,
                sent(
                    "REST and SSE: a guest may run queries without an account, within the anonymous daily cap."
                ),
                BOOL,
                present,
            ),
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
            w(
                TOUR,
                TOUR_TSX,
                sent("Log in keeps your search history across reloads."),
                BOOL,
                present,
            ),
            w(
                ABOUT,
                INFO,
                sent(
                    "Below the answer, a follow-up field carries the conversation forward, and if "
                    "you are signed in the question is kept in your history."
                ),
                BOOL,
                present,
            ),
        ),
    ),
    Fact(
        "access.api_reference",
        "the API serves its reference at /docs and its schema at /openapi.json",
        Computed(
            WEB_APP, api_reference_served, swap(WEB_APP, r"FastAPI\(", "FastAPI(docs_url=None, ")
        ),
        stated=(
            w(
                INTEGRATIONS,
                INFO,
                r"\$\{API_ORIGIN\}/(?:docs|openapi\.json)`",
                BOOL,
                present,
                expect=2,
            ),
        ),
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
        stated=(
            w(INTEGRATIONS, INFO, sent("Resumable after a dropped connection."), BOOL, present),
        ),
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
                tour_steps(names=r"([^.]+)"),
                STEPS,
                lambda m: tuple(words_list(m.group(1))),
            ),
            w(TOUR, TOUR_TSX, tour_steps(count=W), COUNT),
            w(ABOUT, INFO, about_steps(steps=W), COUNT),
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
        "how many of the steps can ask a language model something",
        steps_reaching_model(),
        stated=(w(ABOUT, INFO, about_steps(share=r"(Every one|\w+)", steps=W), COUNT, share_of),),
        downstream=(
            w(
                DOC,
                ARCH_DIAGRAM,
                sent(
                    "Every query runs the same «n» nodes in a fixed sequence, and «s» of the «m» "
                    "can ask a model something, on the tier that matches the work.",
                    n=ANY_W,
                    s=r"(every one|\w+)",
                    m=W,
                ),
                COUNT,
                share_of,
            ),
        ),
    ),
    Fact(
        "loop.tier_count",
        "how many model tiers the harness has",
        PyLiteral(TIERS_PY, "Tier"),
        stated=(
            w(
                ABOUT,
                INFO,
                sent("There are «n» tiers, matched to how hard the step is.", n=r"(three)"),
                COUNT,
            ),
        ),
        downstream=(
            *everywhere(INSTRUCTION_FILES, r"Multi-model harness with (three) tiers:", COUNT),
        ),
    ),
    Fact(
        "loop.guardrail_on_guard_tier",
        "the guardrail step asks the guard-tier model",
        step_uses_tier("guardrail", "guard"),
        stated=(
            w(
                ABOUT,
                INFO,
                r'name: "Guard tier",\s*kind: "a fast, inexpensive model",\s*body: "Runs the guardrail\.',
                BOOL,
                present,
            ),
        ),
    ),
    Fact(
        "loop.think_on_plan_tier",
        "the think step asks the plan-tier model",
        step_uses_tier("think", "plan"),
        stated=(
            w(
                ABOUT,
                INFO,
                r'name: "Plan tier",\s*kind: "a mid-range model",\s*body: "'
                + sent(
                    "Runs Think, which works out the shape of the question and which real records "
                    "its words point at, so BRCA1 becomes NCBI Gene 672, confirmed by a live lookup "
                    "rather than recalled."
                ),
                BOOL,
                present,
            ),
        ),
        downstream=(
            *everywhere(INSTRUCTION_FILES, plan_tier_line(), BOOL, present),
            w(
                DOC,
                ARCH_DIAGRAM,
                sent("- Think: Plan tier, per-step budget 45 seconds."),
                BOOL,
                present,
            ),
        ),
    ),
    Fact(
        "loop.plan_on_plan_tier",
        "the plan step asks the plan-tier model",
        step_uses_tier("plan", "plan"),
        stated=(
            w(
                ABOUT,
                INFO,
                sent(
                    "Plan itself «w» this tier: it picks the tools in code, and passes the odd "
                    "yes-or-no question, such as whether you want papers, to the guard tier or a "
                    "dedicated classifier.",
                    w=either("never calls", "also calls"),
                ),
                BOOL,
                wording({"never calls": False, "also calls": True}),
            ),
        ),
        downstream=(
            w(
                DOC,
                ARCH_DIAGRAM,
                r'PL\["Plan, ' + either("tools picked in code", "Plan tier") + r'"\]',
                BOOL,
                wording({"tools picked in code": False, "Plan tier": True}),
            ),
            w(
                DOC,
                ARCH_DIAGRAM,
                sent(
                    "- Plan: per-step budget 45 seconds, the plan tier's figure, though it «w» the "
                    "plan tier.",
                    w=either("never calls", "also calls"),
                ),
                BOOL,
                wording({"never calls": False, "also calls": True}),
            ),
            *everywhere(
                (*INSTRUCTION_FILES, README),
                r"The Plan step (?:itself )?picks its tools "
                + either("in code", "with the plan tier"),
                BOOL,
                wording({"in code": False, "with the plan tier": True}),
            ),
        ),
    ),
    Fact(
        "loop.act_on_plan_tier",
        "the act step asks the plan-tier model, to write a graph query when no template fits",
        step_uses_tier("act", "plan"),
        stated=(
            w(
                ABOUT,
                INFO,
                sent(
                    "In Act it «w» a graph query, but only when no ready-made template fits the "
                    "question.",
                    w=either("also writes", "never writes"),
                ),
                BOOL,
                wording({"also writes": True, "never writes": False}),
            ),
        ),
        downstream=(
            *everywhere(INSTRUCTION_FILES, plan_tier_line(), BOOL, present),
            w(DOC, ARCH_DIAGRAM, r'AC\["Act, Plan and Guard tiers"\]', BOOL, present),
            w(DOC, ARCH_DIAGRAM, arch_diagram_act(), BOOL, present),
            w(
                DOC,
                DEEP_DIVE,
                r"The plan tier writes Cypher only when no template fits\.",
                BOOL,
                present,
            ),
        ),
    ),
    Fact(
        "loop.act_on_guard_tier",
        "the act step asks the guard-tier model, to read article titles",
        step_uses_tier("act", "guard"),
        downstream=(
            w(DOC, ARCH_DIAGRAM, r'AC\["Act, Plan and Guard tiers"\]', BOOL, present),
            w(DOC, ARCH_DIAGRAM, arch_diagram_act(), BOOL, present),
            w(DOC, DEEP_DIVE, r"The guard tier reads article titles from the graph", BOOL, present),
        ),
    ),
    Fact(
        "loop.write_on_synth_tier",
        "the write step asks the synth-tier model",
        step_uses_tier("write", "synth"),
        stated=(
            w(
                ABOUT,
                INFO,
                r'name: "Synth tier",\s*kind: "the strongest model",\s*body: "'
                + sent("Runs Write, which composes the answer once the records are back.")
                + '"',
                BOOL,
                present,
            ),
        ),
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
        stated=(
            w(
                ARCH,
                ARCH_TSX,
                sent(
                    "The agent reads «w»: the calls Plan chose go out together, so the graph query "
                    "and the live layer 2 and 3 calls run in parallel.",
                    w=either("all three layers at once", "layer 1 first"),
                ),
                BOOL,
                wording({"all three layers at once": False, "layer 1 first": True}),
            ),
            w(
                ABOUT,
                INFO,
                sent(
                    "One query returns the stored links from BRCA1 to its diseases, while most of "
                    "the live searches run «w» and four of the thirteen calls follow in a second "
                    "round.",
                    w=either("at the same time", "afterwards"),
                ),
                BOOL,
                wording({"at the same time": False, "afterwards": True}),
            ),
            w(
                ABOUT,
                INFO,
                sent(
                    "Act sends out the calls Plan chose, across «n» layers of data, «w».",
                    n=ANY_W,
                    w=either("together rather than one after another", "one layer after another"),
                ),
                BOOL,
                wording(
                    {
                        "together rather than one after another": False,
                        "one layer after another": True,
                    }
                ),
            ),
        ),
    ),
    Fact(
        "loop.act_second_round",
        "Act sends the calls that need another call's result in a second round",
        Computed(GRAPH_PY, act_rounds, _merge_rounds),
        stated=(
            w(ARCH, ARCH_TSX, arch_second_round(when=SECOND_ROUND), BOOL, SECOND_ROUND_MEANS),
            w(ABOUT, INFO, about_second_round(when=SECOND_ROUND), BOOL, SECOND_ROUND_MEANS),
        ),
    ),
    Fact(
        "loop.pubmed_follow_ups",
        "what Act's second round does with a PubMed search's results",
        Computed(
            GRAPH_PY,
            pubmed_follow_ups,
            swap(
                GRAPH_PY,
                r'\("pubtator_annotate", "layer_3_enrichment", "pa", "pubtator_publications"\),',
                "",
            ),
        ),
        stated=(
            w(ARCH, ARCH_TSX, arch_second_round(examples=r"([\s\S]+?)"), SUBSET, follow_ups_named),
            w(ABOUT, INFO, about_second_round(examples=r"([\s\S]+?)"), SUBSET, follow_ups_named),
        ),
    ),
    Fact(
        "loop.plan_asks_no_model",
        "the plan step makes no model call",
        step_calls_no_model("plan"),
        downstream=(
            w(
                DOC,
                DEEP_DIVE,
                sent(
                    "When no gene resolved, it reads the literature decision Think started, and «w».",
                    w=either(
                        "asks it itself only when Think did not start it", "never asks it itself"
                    ),
                ),
                BOOL,
                wording(
                    {
                        "asks it itself only when Think did not start it": False,
                        "never asks it itself": True,
                    }
                ),
            ),
            w(
                DOC,
                ARCH_DIAGRAM,
                sent(
                    "When no gene resolved, it reads the literature decision Think started, «w».",
                    w=either(
                        "asking it itself only when Think did not start it",
                        "never asking it itself",
                    ),
                ),
                BOOL,
                wording(
                    {
                        "asking it itself only when Think did not start it": False,
                        "never asking it itself": True,
                    }
                ),
            ),
        ),
    ),
    Fact(
        "loop.sentences_checked_by_code_alone",
        "each answer sentence is checked against its record by code alone",
        checked_by_code_alone("write", "_ground_with_sentence_check"),
        stated=(
            w(
                ABOUT,
                INFO,
                sent(
                    "One that passes but was reworded is then judged by «w», and kept only when the "
                    "model finds it adds nothing beyond the record's own words.",
                    w=either("a model", "code alone"),
                ),
                BOOL,
                wording({"a model": False, "code alone": True}),
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
                expect=3,
            ),
            w(
                DOC,
                MODEL_ARCH,
                r"^\| (Guard|Plan|Synth) \| [^|]+ \| [^|]+ \| ([a-z0-9._/-]+) \|",
                MAPPING,
                lambda m: {m.group(1).lower(): m.group(2)},
                merge_dicts,
                re.MULTILINE,
                expect=3,
                block=True,
            ),
        ),
    ),
    # ---- the KGX export's own manifest
    Fact(
        "export.layer1_only",
        "a KGX export holds the graph alone: no export module imports a tool that reaches a live API",
        Computed(
            f"{EXPORT_DIR}/kgx.py",
            export_layer1_only,
            swap(
                f"{EXPORT_DIR}/kgx.py",
                r"(from system_03_search_agent\.tools\.graph_connection import ConnectionFactory)",
                r"\1\nfrom system_03_search_agent.tools import ncbi_transport",
            ),
        ),
        downstream=(
            w(
                CODE,
                KGX_MANIFEST,
                sent(
                    "This export covers «l», the pre-ingested knowledge graph, only.",
                    l=either("Layer 1", "Layers 1 and 2", "every layer"),
                ),
                BOOL,
                wording({"Layer 1": True, "Layers 1 and 2": False, "every layer": False}),
            ),
            w(
                CODE,
                KGX_MANIFEST,
                manifest_note(present_in=either("are not present", "are present")),
                BOOL,
                wording({"are not present": True, "are present": False}),
            ),
        ),
    ),
    # ---- the people, the questions on screen, the walk and the stack
    Fact(
        "personas.historical",
        "each session's scientist is a historical figure",
        Computed(PERSONAS, personas_historical, swap(PERSONAS, r'"died": \d+', '"died": 9999')),
        stated=(
            w(
                TOUR,
                TOUR_TSX,
                sent("Each session works as a scientist from the history of biomedical science."),
                BOOL,
                present,
            ),
        ),
    ),
    Fact(
        "seeds.count",
        "how many example questions the Home screen shows",
        Computed(HOME_TSX, home_seeds, _add_seed),
        stated=(w(TOUR, TOUR_TSX, sent("Try one of these «n» example questions.", n=W), COUNT),),
    ),
    Fact(
        "about.stop_count",
        "how many stops the About walk shows",
        Computed(INFO, about_stop_count, _add_stop),
        stated=(
            w(ABOUT, INFO, sent("«n» stops, each naming who is acting.", n=r"(Seven)"), COUNT),
        ),
    ),
    Fact(
        "stack.redis_unused",
        "no code under src/ reads Redis, so the README names no Redis cache",
        Computed(
            PKG,
            redis_unused,
            lambda repo: {f"{PKG}/harness/__mutant__.py": "import redis\n"},
        ),
        downstream=(
            w(
                DOC,
                README,
                sent(
                    "| Caching | In-process caches only. A Redis service is provisioned on Railway, "
                    "but «w» |",
                    w=either(
                        "no code under `src/` reads it yet", "the code caches responses in it"
                    ),
                ),
                BOOL,
                wording(
                    {
                        "no code under `src/` reads it yet": True,
                        "the code caches responses in it": False,
                    }
                ),
            ),
        ),
    ),
)


# ------------------------------------------------------------------ break-it edits
#
# `check_facts.py --mutation-test` applies each edit below in memory, never
# on disk, and requires the checker to stop passing. They are the edits card
# 53's judge and adversary used to show the checker passing a false page
# (testing/Developer/reports/2026-09-29_card53/), rewritten for the pages as
# they now read, plus one per finding the fix round closed. An edit whose
# `old` text is no longer in its file is a failure of the test, not a skip:
# it means the page moved and this list must follow it.
#
# Each entry: (label, finding, ((path, old, new), ...)).

MUTATIONS: tuple[tuple[str, str, tuple[tuple[str, str, str], ...]], ...] = (
    (
        "a negation inside the manifest's layer 2 list",
        "F-53-J03",
        ((KGX_MANIFEST, 'PubChem, dbSNP and "', 'PubChem and dbSNP, not "'),),
    ),
    (
        "a negation inside CLAUDE.md's layer 3 list",
        "F-53-J03",
        (
            (
                CLAUDE_MD,
                "(PubTator3, LitVar2, ClinicalTrials.gov)",
                "(PubTator3, LitVar2, never ClinicalTrials.gov)",
            ),
        ),
    ),
    (
        "an exclusion added to the README's layer 2 list",
        "F-53-J03",
        (
            (
                README,
                "Datasets, PubChem, dbSNP and Pathogen Detection |",
                "Datasets, dbSNP and Pathogen Detection (PubChem excluded) |",
            ),
        ),
    ),
    (
        "the page says every question gets layer 3",
        "F-53-J02",
        ((ARCH_TSX, "Not every question gets them.", "Every question gets them."),),
    ),
    (
        "the page says every gene question gets PubTator3 and ClinicalTrials.gov",
        "F-53-A01",
        ((ARCH_TSX, "for a gene named by its symbol or,", "for every gene or,"),),
    ),
    (
        "the isolate path is dropped from the list of questions searched another way",
        "F-53-A02",
        ((ARCH_TSX, "a question about bacterial isolates, ", ""),),
    ),
    (
        "M03: twenty live calls in each layer rather than in total",
        "F-53-A03",
        ((INFO, "at most 20 live calls in total.", "at most 20 live calls in each layer."),),
    ),
    (
        "M04: five retries on the ncbi_efetch card",
        "F-53-A03",
        ((FACTS_TS, 'budget: "15 seconds, one retry"', 'budget: "15 seconds, five retries"'),),
    ),
    (
        "M04: the dbSNP card's two calls said to run at once",
        "F-53-A03",
        (
            (
                FACTS_TS,
                'budget: "15 seconds per call, two calls in sequence"',
                'budget: "15 seconds per call, all at once"',
            ),
        ),
    ),
    (
        "M05: a Researcher-only clause added to the layer 3 triggers",
        "F-53-A03",
        (
            (
                ARCH_TSX,
                "up to two rs variant ids.",
                "up to two rs variant ids, but only in Researcher mode.",
            ),
        ),
    ),
    (
        "M06: the live layers searched only once the graph has answered",
        "F-53-A03",
        (
            (
                INFO,
                "while the live layers are searched at the same time.",
                (
                    "while the live layers are searched at the same time as each other, once the graph "
                    "has answered."
                ),
            ),
        ),
    ),
    (
        "M08: the ncbi_efetch card's 15 seconds becomes 15 minutes",
        "F-53-A04",
        ((FACTS_TS, 'budget: "15 seconds, one retry"', 'budget: "15 minutes, one retry"'),),
    ),
    (
        "M12: a false layer 3 summary with the true one kept in an unused constant",
        "F-53-A05",
        (
            (
                FACTS_TS,
                (
                    '"Literature and trial evidence about the gene, disease or variant a question names. '
                    'Plan decides whether a question gets it, and not every question does.",'
                ),
                (
                    '"Literature and trial evidence, called for every question, after the graph has '
                    'answered.",'
                ),
            ),
            (
                FACTS_TS,
                "export const LAYERS: {",
                (
                    'const _UNUSED = "Literature and trial evidence about the gene, disease or variant a '
                    "question names. Plan decides whether a question gets it, and not every question "
                    'does.";\nexport const LAYERS: {'
                ),
            ),
        ),
    ),
    (
        "M13: a false graph budget with the true sentence kept in a JSX comment",
        "F-53-A05",
        (
            (
                ARCH_TSX,
                "The search agent gives one graph query 30 seconds and asks it for at most 100 rows.",
                (
                    "{/* The search agent gives one graph query 30 seconds and asks it for at most 100 "
                    "rows. */}\n            The search agent allows a graph query two minutes and up to "
                    "5,000 rows."
                ),
            ),
        ),
    ),
    (
        "M14: layer 3 conditions narrowed to diseases and ten rs ids",
        "F-53-A06",
        (
            (
                ARCH_TSX,
                (
                    "for a gene named by its symbol or, when no gene was found, for a\n            disease, "
                    "and LitVar2 for up to two rs variant ids."
                ),
                "only for a question that names a disease, and LitVar2 for up to ten rs variant ids.",
            ),
        ),
    ),
    (
        "M14: PubTator3 named as the source that is not an NCBI host",
        "F-53-A06",
        (
            (
                ARCH_TSX,
                "ClinicalTrials.gov is the\n            one source here that is not an NCBI host.",
                "PubTator3 is the one source here that is not an NCBI host.",
            ),
        ),
    ),
    (
        "M15: the manifest says the export covers layers 1 and 2",
        "F-53-A06",
        (
            (
                KGX_MANIFEST,
                "This export covers Layer 1, the pre-ingested knowledge graph, only. ",
                "This export covers Layers 1 and 2, the pre-ingested knowledge graph, only. ",
            ),
        ),
    ),
    (
        "M15: the manifest says the live layers are present in the file",
        "F-53-A06",
        (
            (
                KGX_MANIFEST,
                "agent and are not present in this file.",
                "agent and are present in this file.",
            ),
        ),
    ),
    (
        "M16: PubTator3 moved into the manifest's layer 2 list",
        "F-53-A06",
        ((KGX_MANIFEST, "PubChem, dbSNP and ", "PubChem, PubTator3, dbSNP and "),),
    ),
    (
        "M18: Plan said to use this tier to choose every tool",
        "F-53-A03",
        (
            (
                INFO,
                "Plan itself never calls this tier: it picks the tools in code,",
                "Plan itself never calls this tier, except to choose every tool it plans,",
            ),
        ),
    ),
    (
        "M19: nine stops",
        "F-53-A07",
        (
            (
                INFO,
                "Seven stops, each naming who is acting.",
                "Nine stops, each naming who is acting.",
            ),
        ),
    ),
    (
        "M20: five queries return the stored links",
        "F-53-A07",
        ((INFO, "One query returns the stored links", "Five queries return the stored links"),),
    ),
    (
        "M20: layer 2 fetched overnight",
        "F-53-A07",
        (
            (
                INFO,
                "Fetched while you wait, so they are current.",
                "Fetched overnight, so they are a day old.",
            ),
        ),
    ),
    (
        "Pathogen Detection's limit stated as 15 seconds",
        "F-53-A08",
        (
            (
                INFO,
                "and 120 seconds for Pathogen Detection, the",
                "and 15 seconds for Pathogen Detection, the",
            ),
        ),
    ),
    (
        "the graph budget named the longest",
        "F-53-A08",
        (
            (
                INFO,
                "for Pathogen Detection, the\n            longest.",
                "for a graph query, the\n            longest.",
            ),
        ),
    ),
    (
        "one access path per tool comes back",
        "F-53-A09",
        (
            (
                ARCH_TSX,
                "each one reaching exactly one of them.",
                "each one reaching exactly one of them and one access path within it.",
            ),
        ),
    ),
    (
        "LitVar2 said to return the papers",
        "F-53-A10",
        (
            (
                ARCH_TSX,
                "LitVar2 finds a named variant and counts the papers that mention it",
                "LitVar2 returns the papers that mention a named variant",
            ),
        ),
    ),
    (
        "500 rows back",
        "F-53-A12",
        ((ARCH_TSX, "asks it for at most 100 rows.", "asks it for at most 500 rows."),),
    ),
    (
        "the second round said to go out with the first",
        "F-53-J06",
        (
            (
                INFO,
                "goes out in a second round once the first has\n            returned.",
                "goes out at the same time as the rest.",
            ),
        ),
    ),
    (
        "the README says the code caches in Redis",
        "F-53-J04",
        ((README, "no code under `src/` reads it yet", "the code caches responses in it"),),
    ),
)
