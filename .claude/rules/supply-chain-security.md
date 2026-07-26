---
description: "Before installing any npm or PyPI package, or wiring up any MCP server or MCP-shaped tool integration (cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup), run checks that catch live supply-chain compromise before a CVE exists: version and timestamp verification, install-script inspection, and an enable-versus-trust gate for anything that executes code."
scope: portable
alwaysApply: true
---

## Supply-chain security

npm audit and pip-audit only catch known CVEs. A live supply-chain attack has no CVE while the malicious version is live: the compromise gets discovered, reported, and pulled, and only then does a CVE get filed. A clean audit run during the live window still reports clean. The checks in this rule catch what the CVE databases cannot, before install for npm and PyPI packages, and before wiring up any MCP server or MCP-shaped tool integration.

This rule owns the ecosystem and execution-surface checks. The `ai-security-standards` rule owns the agent layer: prompt injection defense, sandboxing, least privilege, and human approval for high-risk actions. Apply both together whenever a new dependency or tool integration is in play.

### npm: pre-install and audit checks

1. Search for recent compromise reports: `[package-name] npm malware` or `[package-name] npm compromised`. Even the most downloaded library can be hijacked briefly. Brief is enough.
2. Verify the exact version and its publish timestamp before installing:

```bash
npm view <package> time --json         # published timestamp for each version
npm view <package>@<version> dist-tags # dist-tag assignments
```

Suspicious signal: a version published at an unusual hour, an unexpected version jump, or a new transitive dependency that was not in the prior version.

3. Inspect postinstall scripts before install:

```bash
npm pack <package>@<version> --dry-run  # see what ships in the tarball
cat node_modules/<package>/package.json | jq '.scripts'
```

Red flag: a postinstall or install script in a package with no legitimate reason to run code at install time, for example a utility library or an HTTP client. Check transitive dependencies added in the same version bump too.

4. Run audit after install:

```bash
npm audit
npm audit --audit-level=high
```

This catches known CVEs. It does not catch zero-day supply-chain attacks. A clean audit is necessary, not sufficient.

### PyPI: pre-install and audit checks

Apply the same discipline to Python dependencies for the FastAPI and LangGraph backend.

1. Search for recent compromise reports: `[package-name] pypi malware` or `[package-name] pypi compromised`.
2. Inspect before installing unfamiliar packages:

```bash
pip download --no-deps <package>   # download without installing
pip show <package>                 # check installed package metadata
```

Red flag: a setup.py with network calls, subprocess execution, or obfuscated code. Legitimate packages do not need to phone home at install time.

3. Run pip-audit before and after install:

```bash
pip-audit                          # scan current environment
pip-audit -r requirements.txt      # scan requirements file
pip-audit --desc                   # include vulnerability descriptions
```

### Read before execute

Prefer reading metadata over executing a package manager when you only need to inspect:

- npm: `npm pack --dry-run` (reads) over `npm ls` (can execute postinstall)
- PyPI: `pip download --no-deps` (downloads) over `pip install` (executes setup.py)
- MCP or tool config: read the config JSON or tool source directly before running `npx -y` or `uvx`, or before wiring a new tool into the agent loop

### Reference cases: no CVE while live

- axios, March 2026: malicious versions 1.14.1 and 0.30.4 shipped a postinstall script that dropped a remote access trojan, live for roughly two hours before discovery and pull. No CVE existed for the entire live window.
- Shai-Hulud, May 2026: 324+ packages and 643+ versions compromised simultaneously across five ecosystems, npm, PyPI, Composer, RubyGems, and Go, including Mistral AI and TanStack. Supply-chain security is not an npm problem or a Python problem. It is a cross-ecosystem problem.

If a compromised version was installed during either attack window, rotate all secrets and credentials immediately.

### MCP servers: the unmonitored attack surface

MCP servers run with your credentials and file access. They are package-equivalent execution surfaces but are rarely audited. This repo's roadmap tool integrations (cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup) are execution surfaces in the same sense: each one reaches a live credential-bearing connection, the Hetzner AGE graph or an NCBI API key, or a live external API. Apply these checks to any of them before it goes live, whether it is invoked as a native tool call or through an MCP server.

Before adding a new MCP server or wiring up a new tool integration:

1. Check the package or server name against recent advisories. Search `[name] npm malware` for `npx`-installed servers, `[name] pypi malware` for `uvx`-installed servers.
2. The `npx -y <pkg>` or `uvx <pkg>` pattern executes arbitrary code at invocation time with no install-time gate. Treat every `npx -y` or `uvx` in a tool or MCP config as equivalent to a global install. When you control the invocation, pin the exact version, `pkg@1.4.8`, never `pkg@latest`, so a hijacked latest tag cannot run on your machine.
3. Check the server's or package's source repository: is it maintained? Does it have more than one contributor? When was the last commit?
4. Environment values in MCP configs and tool configs often contain API keys and credentials, including the Hetzner AGE connection string and NCBI API keys in this repo. Never log, commit, or share config files without redacting env blocks.
5. Provision least privilege. Give a new integration its own scoped credential, not your full-access one: a read-only token, a single-database scope, a separate service account. An agent with a tool inherits that tool's reach, so scope the reach down to exactly the job before connecting it. This is the same least-privilege principle `ai-security-standards` applies to Layer 1 graph access, which is read-only by design. Extend it to every new tool integration.

#### Enable versus trust: a two-phase gate for executable extensions

Separate "content loaded" from "code allowed to run." They are different risk levels and deserve different gates.

- Passive content (a skill, a prompt template, an agent definition, a rule) may auto-load when enabled. It cannot execute on its own. The worst case is a bad instruction you can read.
- Executable surfaces (an MCP server, a hook, anything invoked via `npx` or `uvx`) stay inert until an explicit, logged trust decision, even after the extension is enabled. Enabling is not trusting.

Concretely: enabling a plugin or extension should load its skills and prompts but must not activate its hooks or MCP servers until you have reviewed the source and explicitly trusted it. Repo-local executable config, a project `.mcp.json`, a project hook, requires a folder-trust step before it can run, so cloning a hostile repository cannot silently wire up a server with your credentials.

Pair the two-phase gate with exact-version or commit-SHA pinning, whichever the install method uses, so a trusted server is also a pinned one. This is the same least-privilege discipline `ai-security-standards` requires for every agent and tool integration, applied at the moment an executable extension gets wired in.

### Three-state permissions

Allow:
- Running `npm view`, `npm pack --dry-run`, `pip download --no-deps`, `pip show`, and audit commands to inspect a package or MCP server before installing, without asking
- Installing a dependency or wiring up a tool integration once it has passed every check in this rule: no compromise reports, no unexplained postinstall or setup.py script, a passing audit, and verified provenance
- Reading an MCP server's or tool's source, config, and permissions before deciding whether to trust it

Ask:
- Before installing any new npm or PyPI package with a postinstall or setup.py script, or any unfamiliar package with a low maintainer count or a recent, unusual version bump
- Before treating an enabled MCP server or executable extension as trusted. Enabling and trusting are separate steps: source review, credential scoping, and version pinning happen before the extension is allowed to run, even if it is already loaded
- Before upgrading a pinned MCP server or tool integration off an exact version or commit-SHA pin, or replacing a pin with `@latest`

Deny:
- Never install a package that has an active compromise report or an unexplained postinstall or setup.py script
- Never let an MCP server, hook, or executable extension run before it has passed the enable-versus-trust gate, regardless of whether it is enabled or loaded
- Never wire a new MCP server or tool integration to a full-access credential when a scoped, read-only, or single-purpose credential will do
- Never log, commit, or share an MCP or tool config file with its env block unredacted

### Periodic audit

Periodically inventory every configured MCP server and every tool invoked via `npx` or `uvx`. Compare against your expected list. Flag anything you do not recognize.

### Apply when

- User runs or plans to run `npm install` or `pip install`
- User asks for package recommendations, any ecosystem
- User upgrades a package to a new minor or major version
- Reviewing a `package.json`, `requirements.txt`, `pyproject.toml`, or lockfile diff that adds new dependencies
- Adding or configuring a new MCP server, or wiring up a new roadmap tool integration such as `cypher_query`, `ncbi_efetch`, `ncbi_dbsnp`, `pubtator_annotate`, or `litvar2_lookup`

### Do NOT apply when

- cargo, gem, go get: not yet covered, this repo has no Rust, Ruby, or Go dependencies
- Read-only Cypher queries against the already-deployed Hetzner AGE graph: nothing gets installed

The test: did I verify the package or execution surface, npm, PyPI, or MCP-shaped tool integration, before recommending, installing, or wiring it in?
