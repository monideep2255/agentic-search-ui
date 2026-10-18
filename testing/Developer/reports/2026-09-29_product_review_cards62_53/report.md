# Product review, cards 62 and 53, develop at f53b238b

Stage 10 pre-screen, 2026-09-29. Cards 62 (#133) and 53 (#134). Neither changes the answer path, so there is no golden run and no rubric read of answers. This report closes nothing; the owner's verdict closes.

- Which app answered: `GET https://search-agent-api-develop-43b3.up.railway.app/health` returned `{"status":"ok","app_env":"develop"}`.
- Web app: `https://search-agent-web-develop-2aeb.up.railway.app` (`DEVELOP_WEB` in `frontend/e2e/live-target.ts`).
- Captures: `develop_<screen>_<width>.png`, `prototype_<screen>_<width>.png`, page text `develop_<screen>_text.txt`, and `measurements.json`, all in this folder, taken with Playwright driving the installed Chrome (the bundled headless shell is not installed on this machine).

## Findings, in the order they were established

### PR-cards62-53-01: the Architecture page has no design to judge it against
- Kind: missing design
- Verdict: needs your eye
- What: `docs/build/design/design-system/prototype/app.html` has no Architecture screen (its `go()` knows only landing, run, answer, wall, integrations, docs and about), and `docs/build/design/README.md`'s coverage table does not list Architecture at all. Integrations and About are listed as "NO | Only ever inside `prototype/app.html`", so for those two the prototype is the only reference.
- Evidence: `develop_architecture_1280.png`, `develop_architecture_390.png`; README coverage row "Integrations, docs and about | NO | Only ever inside `prototype/app.html`".
- Why a person would care: nobody can say whether the Architecture page looks as intended, because nothing says what intended is. It was judged here only for overflow and readability, not against a look.
- NOT CLOSED

### PR-cards62-53-02: the install command is copied blind; the page never shows it
- Kind: screen
- Verdict: needs your eye
- What: the Command line tools card shows only the agent configuration JSON in its code block. The install command that "Copy install command" puts on the clipboard is printed nowhere on the page. If the clipboard fails, the card says "Could not copy automatically. Select the example and copy it by hand." (`frontend/src/components/screens/InfoScreens.tsx`, `CardActionRow`), and there is no install example to select. The prototype's Command line card prints its command in a code block above its "Copy install command" button.
- Evidence: `develop_integrations_1280.png`, `develop_integrations_390.png` beside `prototype_integrations_1280.png`, `prototype_integrations_390.png`. `develop_integrations_text.txt` contains no `pip` and no `git+` line.
- Why a person would care: "I am asked to paste something into my terminal that I cannot see first." Query 101 says to read the card "before copying anything", and nothing on it shows what is copied.
- NOT CLOSED

### PR-cards62-53-03: the Command line tools card is one paragraph of about 300 words, with its commands set as ordinary prose
- Kind: screen
- Verdict: needs your eye
- What: the card's description is one paragraph covering requirements, the virtual environment, re-entering it, `s3`, `s3 mcp`, the agent PATH and `s3-kgx-export`. Commands in it are not monospace, so it reads "enter it again with . s3-env/bin/activate from the same folder", where the leading dot looks like stray punctuation. At 1280 the flag wraps as "python3.11 -" then "-version fails". At 390 the paragraph is about 1,100 px tall.
- Evidence: `develop_integrations_1280.png`, `develop_integrations_390.png`; `develop_integrations_text.txt`.
- Why a person would care: the steps that decide whether the install works first time are buried, and the command a person must retype in a new terminal does not look like a command.
- NOT CLOSED

### PR-cards62-53-04: README still says the Integrations page prints a KGX export command
- Kind: screen
- Verdict: fail
- What: README's "Use it from a terminal or an AI agent" says "The Integrations page prints the exact commands for each: the REST API with its event stream, GraphQL, MCP, the `s3` command line and KGX export." Since card 62 the page prints no KGX command; it says "today a KGX file comes from the operator".
- Evidence: `<repo-root>/README.md` line 107 at f53b238b; `develop_integrations_text.txt`: "s3-kgx-export is not in that install and has no download: it reads the knowledge graph directly with credentials only the operator holds, so today a KGX file comes from the operator, who runs it for the seed CURIEs you name."
- Why a person would care: someone who reads the README goes looking for a KGX command the page does not have. Query 102 asks that the pages and README say what the system actually does.
- NOT CLOSED

### PR-cards62-53-05: About places the three layer cards after the walk, where the prototype puts them first (older than these cards)
- Kind: screen
- Verdict: needs your eye
- What: in the prototype the Knowledge graph, Live NCBI APIs and Enrichment cards sit directly under the lede. On develop they sit after stop 7, below "Follow the same question live". Card 53 changed this page's wording, not its order.
- Evidence: `develop_about_1280.png` beside `prototype_about_1280.png`.
- Why a person would care: the colour key for L1, L2 and L3 arrives after the reader has met the colours in the walk.
- NOT CLOSED

### PR-cards62-53-06: `s3 mcp --help` ends mid-sentence without a full stop
- Kind: screen
- Verdict: needs your eye
- What: the help text's last sentence ends "since an agent app may not read your shell's PATH", with no full stop.
- Evidence: `cli_install_and_help.txt`, the `=== s3 mcp --help` section.
- Why a person would care: a small polish point on the text a person reads when wiring an agent.
- NOT CLOSED

## Query 101, the checks a page and a terminal can answer (card 62)

- PASS: "Before any command, the card says it needs Python 3.11 and git, and works on macOS and Linux." Read on `develop_integrations_1280.png` and in `develop_integrations_text.txt`: "The install works on macOS and Linux and needs git and Python 3.11".
- PASS, with a limit: "The install command creates its environment with `python3.11`, not `python3`". The deployed clipboard text (`deployed_install_command.txt`, captured by clicking "Copy install command" on develop, status "Copied to clipboard.") is `python3.11 -m venv s3-env` / `. s3-env/bin/activate` / `pip install "git+https://github.com/monideep2255/agentic-search-ui.git#subdirectory=clients/system3-cli"`, byte-identical to `INSTALL_EXAMPLE` in source. Run exactly as copied, under a clean default PATH (Homebrew and system paths only), it ended "Successfully installed ... system3-cli-0.1.0" (`cli_install_and_help.txt`). The limit: this machine's `python3` on that PATH is 3.14.3, not an older one, so "succeeds on a Mac whose python3 is older" is NOT CHECKED here.
- PASS: "In the second terminal, following the card's line, `s3` is found". In a fresh shell, `s3` was not found before `. s3-env/bin/activate` and was found at `<scratch>/s3-env/bin/s3` after it; `s3 login --help` printed its usage (`cli_second_terminal.txt`). Signing in itself: NOT CHECKED, no credentials.
- PASS: "`s3 mcp --help` says to point the agent app at `s3` by its full path". `cli_install_and_help.txt`: "Point the agent at s3 by the full path that command -v s3 prints, with the argument mcp, since an agent app may not read your shell's PATH". Whether an agent app then finds it: NOT CHECKED.
- PASS: "The page prints no KGX install command; it says a KGX file comes from the operator." `develop_integrations_text.txt` has three copy buttons on the card (install, command, agent config), none for KGX, and "today a KGX file comes from the operator, who runs it for the seed CURIEs you name". README still claims otherwise, finding 04.
- NOT CHECKED: the trust line under a finished answer, the stopped-search line, the `[ask]` line (each needs a signed-in `s3 ask`), and the guest-over-MCP message (needs an MCP client session). The brief forbids sign-in and questions.
- `s3 --help` result lines, verbatim: "usage: s3 <command> [options]", "Ask System 3 biomedical questions from a terminal, with every claim cited.", commands `login`, `ask`, `stop`, `mcp`, and "s3 uses https://search-agent-api-production.up.railway.app unless 's3 login --base-url' or S3_BASE_URL names another server." Exit 0. `s3 mcp --help`: "usage: s3 mcp [-h]", exit 0.

## Query 102, the checks the pages themselves can answer (card 53)

- PASS: Plan decides whether PubTator3 and ClinicalTrials.gov are searched, never "for every gene or disease question". Architecture, layer 3: "Plan decides which of them a question gets, from what Think found in it ... Not every question gets them." About, stop 3: "Plan adds them here because the question names a gene by its symbol, BRCA1, though not every question gets them." (`develop_architecture_text.txt`, `develop_about_text.txt`).
- PASS: what PubTator3 and LitVar2 return. Architecture: "PubTator3 looks the name up in its index of the genes and diseases found in published papers, LitVar2 finds a named variant and counts the papers that mention it".
- PASS: each source has its own time limit, Pathogen Detection's 120 seconds the longest. About, stop 3: "30 seconds for a graph query, 15 seconds for a call to a live web API, and 120 seconds for Pathogen Detection, the longest." Architecture lists 30, 15 and 120 seconds per tool.
- PASS: some follow-up searches run in a second round. About, stop 3 and Architecture, stop 4: "goes out in a second round once the first has returned".
- PASS: no page names LitSense (absent from all three page texts and from `<repo-root>/README.md`), and README names no Redis cache. README's Tech stack row reads "In-process caches only. A Redis service is provisioned on Railway, but no code under `src/` reads it yet". Its cost section mentions Redis as a provisioned service only.
- PRESENT AS KNOWN, card 76: the layer 3 stop names three kinds of question searched another way ("A gene named only by an identifier, a question about bacterial isolates, and a question with no gene that a classifier reads as asking for papers"), and About's L1 row says "One query returns the stored links from BRCA1 to its diseases, while the live layers are searched at the same time." Both are as the query document says; not re-filed.
- NOT CHECKED: whether BRCA1 searches PubTator3 and ClinicalTrials.gov and NCBIGene:672 does not, and "Any trials for GERD?" (each needs a question asked on develop; the brief forbids it).

## Report, ranked for the owner

Golden result: none. Neither card changes the answer path, so no golden run and no answer rubric read, per the brief.

What to look at first:

1. Fail, finding 04: README says the Integrations page prints a KGX export command, which it no longer does. `<repo-root>/README.md` line 107 and `develop_integrations_text.txt`.
2. Needs your eye, finding 02: the install command is on the clipboard but never on the page, and the clipboard-failure message says to copy an example that is not shown. `develop_integrations_1280.png`, `develop_integrations_390.png`.
3. Needs your eye, finding 03: the Command line tools card is one long paragraph, with its commands set as prose. Same screenshots.
4. Needs your eye, finding 01: the Architecture page has no design, so it cannot be judged against one. `develop_architecture_1280.png`, `develop_architecture_390.png`.
5. Needs your eye, finding 05: About's layer cards sit after the walk, not first as in the prototype; older than these cards. `develop_about_1280.png` beside `prototype_about_1280.png`.
6. Needs your eye, finding 06: `s3 mcp --help` ends without a full stop. `cli_install_and_help.txt`.

Overflow at 390 (scrollWidth minus clientWidth, `measurements.json`):

- Develop: Integrations 0, About 0, Architecture 0. None.
- The prototype's own Integrations screen overflows by 34 px at 390 (`prototype_integrations_390.png`); develop does not copy that.

Surfaces with no design:

- Architecture: absent from the prototype and from `docs/build/design/README.md`'s coverage table.
- Integrations and About: the coverage table says "NO | Only ever inside `prototype/app.html`", so they were compared against the prototype screen only.

Position against the prototype, both widths:

- Integrations: title, lede and chip row, then the cards with the main button pinned to each card's bottom, then more below. At 1280 develop has a two-column grid where the prototype has three; at 390 both are one column. The prototype's sign-in banner and "Sign in required" pills are absent on develop, which is older than these cards.
- About: title and lede match. Layer-card order differs (finding 05). At 390 both stack in one column.
- Architecture: nothing to compare against. At 390 the pipeline steps wrap to three rows and the Cypher example scrolls inside its own box.

What was not captured, and why:

- No sign-in, no question asked, no MCP client session: no credentials, and the brief forbids them. Every NOT CHECKED line above is that.
- An older system `python3`: this machine's `python3` on a clean PATH is 3.14.3.
- Only develop was captured, not production.
- The fixed app footer appears as a blue band across the middle of every full-page develop screenshot (for example `develop_integrations_1280.png` at about y 875). It is the full-page capture drawing a fixed footer at the viewport's bottom edge, not something a scrolling reader sees. The text behind it was read from `develop_<screen>_text.txt` instead.
- Screenshots were taken with Playwright driving the installed Chrome, because the bundled headless browser is not installed on this machine.

What rests on what:

- Every screen verdict rests on a screenshot I read myself (all ten PNGs in this folder).
- Every page-text verdict rests on the page text captured from develop, which I read myself.
- The terminal verdicts rest on command output I ran and read myself.
- Nothing here rests only on a summary.

## Per card, at both widths

- Card 62 (Integrations, the command line): not passed at both widths. No overflow at 1280 or 390 and the install works, but findings 02 and 03 are open for your eye, and finding 04 (README) is a fail tied to this card's change.
- Card 53 (Architecture and About wording): passed at both widths on what the pages can show. No overflow, and every page-checkable query 102 line passes. Architecture has no design to judge position against (finding 01).
