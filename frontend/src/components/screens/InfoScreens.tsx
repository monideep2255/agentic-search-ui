/**
 * Integrations, Docs and About, build phase 4.8, ticket T-4.8-11.
 *
 * These are largely static prose, which is why they can ship complete in this
 * phase. The one thing that needs care is accuracy: a docs page that drifts
 * from the API is worse than no docs page, because a reader trusts it.
 *
 * So every endpoint named here is one that exists on `develop` today, and the
 * access note deliberately does not name a credential mechanism, because that
 * decision is open. The product-owner decision of 2026-08-13 removed the
 * bespoke API key surface: when programmatic access returns it will reuse the
 * NCBI API key already part of this system rather than minting a second one.
 *
 * Source of truth: the approved prototype's integrations and docs screens.
 *
 * T-6.2-09, "the integrations page offers only what a visitor can actually
 * use": F-6.2-09 found the page's own dead-button premise did not hold on
 * develop, five cards, zero controls, so there was nothing to click and
 * nothing broken. The real gap was the opposite of the complaint: a page of
 * prose about five reachable surfaces, and nothing on it a visitor could
 * actually operate. Every code block below now carries a copy control, and
 * the REST and SSE card links out to the two live, unauthenticated surfaces
 * verified against `develop` (`/docs`, `/openapi.json`). KGX export and the
 * command line stay copy-only, on purpose: both are batch console scripts
 * (`s3`, `s3-kgx-export`), never HTTP routes, and a download or "try it"
 * control here would advertise a route that does not exist, the exact
 * failure T-4.16-04 already found and removed once.
 */

import { useEffect, useRef, useState } from "react";
import { Box, Typography } from "@mui/material";

import { designTokens } from "../../theme";

const mono = { fontFamily: "ui-monospace, monospace" } as const;

function Page({ title, lede, children }: { title: string; lede: string; children?: React.ReactNode }) {
  return (
    <Box sx={{ maxWidth: 900, mx: "auto", px: 3, py: 5 }}>
      <Typography variant="h2" component="h1" sx={{ mb: 1.5 }}>
        {title}
      </Typography>
      <Typography sx={{ color: designTokens.inkMuted, maxWidth: "66ch", mb: 3 }}>{lede}</Typography>
      {children}
    </Box>
  );
}

type CopyStatus = "idle" | "copied" | "error";

/** How long the button's own label, and the status region beside it, hold
 *  their confirmed or failed state before resetting to idle. */
const COPY_STATUS_MS = 2500;

/**
 * A copy-to-clipboard control paired with its own screen-reader-audible
 * confirmation, shared by every code block on these three screens.
 *
 * The button's own visible label swaps to "Copied" for a moment, which a
 * sighted reader sees without looking away from the block they just copied.
 * The `role="status"` region beside it carries the same information to a
 * screen reader, matching `FeedbackSurface.tsx`'s own transient status
 * region rather than inventing a second pattern for the same job. Styling
 * (border, colour, radius, size) is transcribed from that component's
 * "Skip" button, the documented secondary-button shape in
 * `docs/build/design/design-system/components/feedback.html`'s `.fb-skip`.
 *
 * The failure path is real, not decorative: `navigator.clipboard` is absent
 * on an insecure origin, and `writeText` can reject on a denied permission.
 * Either way the reader is told to copy the text by hand, never left
 * thinking the click did nothing.
 */
function CopyButton({ text, label, testId }: { text: string; label: string; testId: string }) {
  const [status, setStatus] = useState<CopyStatus>("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Mutation proof, same shape as FeedbackSurface's own cleanup: without
  // this, a reset scheduled just before the surface unmounts fires
  // `setState` on a component nobody can see any more.
  useEffect(
    () => () => {
      if (timer.current !== null) {
        clearTimeout(timer.current);
      }
    },
    [],
  );

  const scheduleReset = () => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
    }
    timer.current = setTimeout(() => setStatus("idle"), COPY_STATUS_MS);
  };

  const handleCopy = async () => {
    try {
      if (!navigator.clipboard) {
        throw new Error("clipboard API unavailable");
      }
      await navigator.clipboard.writeText(text);
      setStatus("copied");
    } catch {
      setStatus("error");
    }
    scheduleReset();
  };

  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, flexWrap: "wrap" }}>
      <Box
        component="button"
        type="button"
        onClick={() => void handleCopy()}
        aria-label={`Copy ${label}`}
        data-testid={testId}
        sx={{
          font: "inherit",
          fontSize: 12.5,
          fontWeight: 600,
          px: 1.75,
          py: 0.9,
          borderRadius: 0.5,
          cursor: "pointer",
          border: `1px solid ${designTokens.line}`,
          color: designTokens.inkMuted,
          bgcolor: "transparent",
          "&:hover": { borderColor: designTokens.lineStrong, color: designTokens.ink },
        }}
      >
        {status === "copied" ? "Copied" : "Copy"}
      </Box>
      {status !== "idle" ? (
        <Box
          role="status"
          data-testid={`${testId}-status`}
          sx={{
            fontSize: 11.5,
            color: status === "error" ? designTokens.risk : designTokens.ok,
          }}
        >
          {status === "copied"
            ? "Copied to clipboard."
            : "Could not copy automatically. Select the text above and copy it by hand."}
        </Box>
      ) : null}
    </Box>
  );
}

/**
 * A link to a live surface this app does not itself render, always opened in
 * a new tab. The anchor, `target` and `rel` are transcribed from
 * `AnswerScreen.tsx`'s own citation link, the existing precedent for an
 * external link in this codebase, so this page gains no second pattern for
 * the same job. `rel="noopener noreferrer"` is the same host-safety
 * discipline `production-standards.md` requires for any redirect target: the
 * new tab must never gain a reference back to this page's `window`.
 */
function ExternalLink({ href, label, testId }: { href: string; label: string; testId: string }) {
  return (
    <Box
      component="a"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      data-testid={testId}
      sx={{
        fontSize: 12.5,
        fontWeight: 600,
        color: designTokens.link,
        textDecoration: "none",
        "&:hover": { textDecoration: "underline" },
      }}
    >
      {label}
    </Box>
  );
}

interface CardLink {
  label: string;
  href: string;
  testId: string;
}

function Card({
  title,
  body,
  code,
  copyLabel,
  copyTestId,
  links,
}: {
  title: string;
  body: string;
  code?: string;
  /** The noun phrase that completes "Copy {copyLabel}" in the button's
   *  accessible name. Required whenever `code` is given, so every copy
   *  control on a page carries a distinct name rather than five buttons all
   *  named plain "Copy". */
  copyLabel?: string;
  copyTestId?: string;
  links?: CardLink[];
}) {
  const hasActions = (code && copyLabel && copyTestId) || (links && links.length > 0);
  return (
    <Box
      sx={{
        bgcolor: designTokens.surface,
        border: `1px solid ${designTokens.line}`,
        borderRadius: 1,
        p: 2.5,
        display: "flex",
        flexDirection: "column",
        gap: 1.25,
      }}
    >
      <Typography variant="h4" component="h2">
        {title}
      </Typography>
      <Typography variant="body2" sx={{ color: designTokens.inkMuted }}>
        {body}
      </Typography>
      {code ? (
        <Box
          component="pre"
          // A pre with overflow-x: auto is a scrollable region, and a keyboard
          // user cannot scroll it without being able to focus it. axe flags
          // this as scrollable-region-focusable; the fix is a tab stop plus a
          // name, so the region is both reachable and announced.
          tabIndex={0}
          role="region"
          aria-label={`${title} example`}
          sx={{
            ...mono,
            fontSize: 11.5,
            m: 0,
            p: 1.25,
            // Wrapped rather than scrolled. Measured 2026-09-05 at 1440px:
            // every one of the five snippets was clipped at the card edge,
            // so a reader could copy a command they could not read. These
            // are short commands and small JSON objects in a narrow card,
            // which wrap well; a wide table would not, and would keep the
            // scroll instead.
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            // Kept as a safety net for a single unbreakable token, and the
            // focusable region above is kept with it for the same reason.
            overflowX: "auto",
            bgcolor: designTokens.surfaceSunk,
            border: `1px solid ${designTokens.line}`,
            borderRadius: 0.5,
          }}
        >
          {code}
        </Box>
      ) : null}
      {hasActions ? (
        <Box sx={{ display: "flex", alignItems: "center", gap: 2, flexWrap: "wrap" }}>
          {code && copyLabel && copyTestId ? (
            <CopyButton text={code} label={copyLabel} testId={copyTestId} />
          ) : null}
          {links?.map((link) => (
            <ExternalLink key={link.testId} href={link.href} label={link.label} testId={link.testId} />
          ))}
        </Box>
      ) : null}
    </Box>
  );
}

const GRID = {
  display: "grid",
  gap: 2,
  gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
} as const;

/**
 * The API origin these cards quote.
 *
 * A card whose command cannot be copied and run is decoration, and the MCP
 * card's previous elided `https://.../mcp` was exactly that. Read from the
 * same `VITE_API_BASE_URL` the app's own client uses, so the page can never
 * advertise one origin while the app talks to another; the fallback matches
 * `lib/api.ts`'s own default for a local dev run.
 *
 * `lib/api.ts` itself resolves `VITE_API_BASE_URL` to `""` (same-origin) when
 * the variable is unset, since its own `DEFAULT_BASE_URL` is what every fetch
 * in this app actually uses. This page keeps its own local-dev fallback
 * (`http://127.0.0.1:8000`) instead, because an empty string is a correct
 * same-origin base for a `fetch()` call but a useless one to print in a code
 * block or resolve a link href from: a reader cannot paste "" into a
 * terminal, and an empty-string href resolves to the current page, not to the
 * API. The two constants intentionally diverge for that reason.
 */
const API_ORIGIN =
  (import.meta.env?.VITE_API_BASE_URL as string | undefined) ?? "http://127.0.0.1:8000";

/**
 * T-4.16-04, the product owner's defect 5 from the live demo: "I do not see
 * the KGX, REST API, command line or MCP setup up properly on the
 * integrations page."
 *
 * Every surface named there had SHIPPED. This was never missing capability,
 * it was a page describing surfaces that do not exist in the shape it
 * described them. Four errors, each verified against the code rather than
 * taken from the page:
 *
 * - The command line card printed `ncbi-search ask "..."`. No such command
 *   exists. `pyproject.toml` declares `s3` and `s3-kgx-export`, which is
 *   what build phase 4.2 shipped and named in its own row.
 * - The KGX card printed `POST /v1/export/kgx`. No such route exists in
 *   `adapters/`. Build phase 4.4 shipped KGX as a console script over a
 *   query-scoped subgraph, seeds and bounded hops, not a live endpoint, and
 *   the card's own body said "prepared as a batch job" while its code block
 *   contradicted it.
 * - The MCP card printed an elided `https://.../mcp`, which cannot be
 *   copied and used.
 * - GraphQL was ABSENT. It shipped in build phase 4.3 as PR #48 and is
 *   mounted at `/graphql`. The lede said "reachable four ways" and there
 *   are five.
 *
 * The general form, and the reason this sat unnoticed through two phases:
 * this page is prose about other modules, and nothing links the two. A
 * command here is as much a claim as a citation is, and neither should be
 * written from memory of what a surface probably looks like.
 */
export function IntegrationsScreen() {
  return (
    <Page
      title="Integrations"
      lede="The same agent, reachable five ways. Every surface runs the identical loop and returns the identical citations."
    >
      <Box sx={GRID}>
        <Card
          title="REST and SSE"
          body="Start a run, then subscribe to its event stream and render it as it happens, exactly as this interface does. Resumable after a dropped connection."
          code={"POST /v1/query\nGET  /v1/query/{run_id}/events\nGET  /v1/query/{run_id}/citations"}
          copyLabel="the REST and SSE example"
          copyTestId="integration-copy-rest"
          links={[
            {
              label: "Open API reference",
              href: `${API_ORIGIN}/docs`,
              testId: "integration-link-api-docs",
            },
            {
              label: "View OpenAPI schema",
              href: `${API_ORIGIN}/openapi.json`,
              testId: "integration-link-openapi-schema",
            },
          ]}
        />
        <Card
          title="GraphQL"
          body="One typed request and one typed response over the same core, for a client that wants the whole answer in a single round trip. Registered accounts only, and no live stream: a run is returned complete or not at all."
          code={`POST ${API_ORIGIN}/graphql\n{ ask(input: {question: "..."}) {\n    answer citations { sourceUrl } } }`}
          copyLabel="the GraphQL example"
          copyTestId="integration-copy-graphql"
        />
        <Card
          title="MCP server"
          body="One advertised tool, ask_biomedical_question. It folds a whole run into a single cited answer; the seven internal tools are never separately reachable."
          code={`{"mcpServers": {"ncbi-search": {\n  "url": "${API_ORIGIN}/mcp"}}}`}
          copyLabel="the MCP server configuration"
          copyTestId="integration-copy-mcp"
        />
        <Card
          title="KGX export"
          body="A query-scoped subgraph as BioLink-compliant KGX: seed CURIEs, bounded hops, written as nodes.tsv, edges.tsv and a manifest. A batch command rather than a live endpoint, and not a whole-graph snapshot."
          code={'s3-kgx-export NCBIGene:672 \\\n  --hops 1 --output-dir ./kgx-out'}
          copyLabel="the KGX export command"
          copyTestId="integration-copy-kgx"
        />
        <Card
          title="Command line"
          body="The same answer, piped. Human-readable by default and JSON with --json, so answers chain into other tools."
          code={'s3 login\ns3 ask "diseases linked to BRCA1"'}
          copyLabel="the command line example"
          copyTestId="integration-copy-cli"
        />
      </Box>
    </Page>
  );
}

export function DocsScreen() {
  return (
    <Page
      title="Documentation"
      lede="What each surface does, what it returns, and what it will refuse to do."
    >
      <Box sx={GRID}>
        <Card
          title="Access"
          body="The web interface is open: ask questions without an account, up to the free allowance. The programmatic surfaces need a signed-in account. How a program presents that account is not settled; it will reuse the NCBI API key already part of this system rather than a second credential."
        />
        <Card
          title="The event stream"
          body="A run emits one event per loop step, one per tool call, then the answer tokens, its citations and a trust signal. A refusal is a normal outcome with a reason attached, not an error."
          code={'event: guard  data: {"verdict":"in_scope"}\nevent: tool   data: {"name":"ncbi_dbsnp"}\nevent: done   data: {"status":"answered"}'}
          copyLabel="the event stream example"
          copyTestId="docs-copy-event-stream"
        />
        <Card
          title="Citations"
          body="Every claim is tied to a specific record, with the layer that produced it, the tool that fetched it, its evidence type, its confidence and its licence. An answer with an uncited sentence is a defect."
        />
        <Card
          title="Limits"
          body="Each tool carries its own per-call timeout and rate-limit pool. A call that would exceed either fails fast with a retry hint rather than joining an unbounded queue."
        />
      </Box>
    </Page>
  );
}

export function AboutScreen() {
  const layers: { n: 1 | 2 | 3; name: string; body: string; colour: string }[] = [
    {
      n: 1,
      name: "Knowledge graph",
      colour: designTokens.layer1,
      body: "115M nodes and 693M edges merged from 5 NCBI databases. Broad and fast, but a periodic snapshot rather than live.",
    },
    {
      n: 2,
      name: "Live NCBI APIs",
      colour: designTokens.layer2,
      body: "E-utilities, Datasets and dbSNP, called at the moment you ask. Narrower and slower, and always current.",
    },
    {
      n: 3,
      name: "Enrichment",
      colour: designTokens.layer3,
      body: "PubTator3, LitVar2 and ClinicalTrials.gov. Literature and trial evidence layered on a fact the first two layers established.",
    },
  ];

  return (
    <Page
      title="How an answer is built"
      lede="Every question crosses up to three data layers. The colour on a citation tells you which layer it came from, and therefore how fresh it is and how it was established."
    >
      <Box sx={GRID}>
        {layers.map((layer) => (
          <Box
            key={layer.n}
            sx={{
              bgcolor: designTokens.surface,
              border: `1px solid ${designTokens.line}`,
              borderRadius: 1,
              p: 2.5,
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, mb: 1.25 }}>
              <Box sx={{ width: 12, height: 12, borderRadius: 0.5, bgcolor: layer.colour, flex: "none" }} />
              <Typography variant="h4" component="h2">
                {layer.name}
              </Typography>
              <Box component="span" sx={{ ...mono, ml: "auto", fontSize: 11, fontWeight: 700, color: layer.colour }}>
                L{layer.n}
              </Box>
            </Box>
            <Typography variant="body2" sx={{ color: designTokens.inkMuted }}>
              {layer.body}
            </Typography>
          </Box>
        ))}
      </Box>

      <Typography variant="h2" component="h2" sx={{ mt: 5, mb: 1.5 }}>
        Cite or refuse
      </Typography>
      <Typography sx={{ color: designTokens.inkMuted, maxWidth: "66ch" }}>
        Every claim is tied to a specific record. When nothing supports an answer, the system says
        so and stops rather than answering from memory. The track beside each answer shows one
        segment per claim, coloured by its layer, so an uncited claim is visible before you read a
        word.
      </Typography>
    </Page>
  );
}
