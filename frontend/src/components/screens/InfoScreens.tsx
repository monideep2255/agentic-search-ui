/**
 * Integrations and About, build phase 4.8 ticket T-4.8-11, rebuilt in the UI
 * fix loop's fix set 5 (items 5.1, 5.2, 5.4 and 5.6, requirements R15, R16,
 * R18 and R41, product-owner decision U3).
 *
 * WHERE THIS LAYOUT COMES FROM, stated rather than assumed.
 * `docs/build/design/design-system/README.md`'s coverage table says
 * "Integrations, docs and about | NO", so this surface has NO design in the
 * design system: it only ever existed inside `prototype/app.html`.
 * `.claude/rules/design-consistency.md` requires that gap to be named out
 * loud rather than filled silently, and this is the naming.
 *
 * The product owner's instruction of 2026-09-12
 * (`testing/Product/reports/2026-09-12_consistency_and_test_1.md`, sections 5,
 * 6 and 12) settles what fills it: copy the layout of the reference
 * Integration Hub, whose code is read-only at
 * `reference/agentic-search-data-engineering/reference/ncbi_ai_agents-ncbi-kg/
 * frontend/src/components/IntegrationHub.tsx`, in this product's own colours
 * and typeface. That instruction OVERRIDES this repository's design rule for
 * this one page, and section 10 question 2 settles the split: the reference
 * layout, our colours. So every visual value below reads a `designTokens`
 * entry or a theme type step, never a hex literal, and the parts that are
 * transcribed from the reference are its STRUCTURE: one title, a one-line
 * description, summary chips, equal-height cards each with a round icon,
 * title, description and a button row pinned to the bottom, then an access
 * notice.
 *
 * WHAT DECISION U3 CHANGED. The page carried five cards of uneven height.
 * It now carries exactly four, because "Command line tools" covers both
 * console commands (`s3` and `s3-kgx-export`) that the two old cards split,
 * and because a visitor cannot run either from the page, so they belong
 * together rather than beside the three HTTP surfaces. The summary chips
 * carry real figures rather than decoration: 115M nodes and 693M edges are
 * the live graph's own counts (CLAUDE.md's architecture section), 3 data
 * layers is Layer 1, 2 and 3, and 7 tools is the locked roster
 * (`cypher_query`, `ncbi_efetch`, `ncbi_dbsnp`, `pubtator_annotate`,
 * `litvar2_lookup`, `pathogen_detection`, `clinicaltrials_search`).
 *
 * WHY DOCS IS GONE (R18). The product owner could not tell what the Docs tab
 * was for. Its content was a short technical reference for these same
 * surfaces, so it is now the "API documentation" section at the bottom of
 * this page, the tab is removed from the bar, and `/docs` routes here.
 *
 * EVERY COMMAND PRINTED HERE WAS RUN, not written from memory of what the
 * surface probably looks like. That discipline is what T-4.16-04 exists for:
 * this page is prose about other modules, nothing links the two, and a
 * command here is as much a claim as a citation is. Verified against the
 * develop API on 2026-09-13:
 *
 * - `POST /v1/query` with `{"text": ..., "session_id": ...}` and a bearer
 *   token answered 202 with a `run_id` and a `persona_name`.
 * - The GraphQL document below, posted exactly as printed, answered 200 with
 *   a real BRCA1 answer and five NCBI citations, and with no validation
 *   error. R16: the old example failed three ways, being written as a query
 *   rather than a mutation, using `question` where the field is `text`, and
 *   omitting the required session id. `adapters/graphql/schema.py` declares
 *   `ask` on `Mutation`, `types.py` declares `AskInput { text, session_id,
 *   audience_depth? }`, and Strawberry's default `auto_camel_case=True`
 *   publishes those as `text`, `sessionId` and `audienceDepth`.
 *
 * The MCP server is NOT claimed to work here. Fix set 5 item 5.3 (R17) owns
 * its "Invalid Host header" defect and is not this file's work; the config
 * printed below is the one a client needs once that is fixed.
 */

import { useEffect, useRef, useState } from "react";
import { Box, Button, Chip, Typography } from "@mui/material";

import {
  EDGE_COUNT,
  NODE_COUNT,
  SNAPSHOT_DATE,
  SOURCE_DATABASE_NAMES,
} from "../../lib/architectureFacts";
import { designTokens, layerColour } from "../../theme";

export const mono = { fontFamily: "ui-monospace, monospace" } as const;

export function Page({ title, lede, children }: { title: string; lede: string; children?: React.ReactNode }) {
  return (
    // Centred between the header and footer, product-owner feedback
    // 2026-09-12, the same as the log-in screen. `width: 100%` keeps the
    // 900 frame when `my: auto` sits inside the shell's flex column.
    <Box sx={{ width: "100%", maxWidth: 900, mx: "auto", my: "auto", px: 3, py: 5 }}>
      <Typography variant="h2" component="h1" sx={{ mb: 1.5 }}>
        {title}
      </Typography>
      <Typography sx={{ color: designTokens.inkMuted, maxWidth: "66ch", mb: 3 }}>{lede}</Typography>
      {children}
    </Box>
  );
}

type CopyStatus = "idle" | "copied" | "error";

/** How long a copy button's own label, and the status line under it, hold
 *  their confirmed or failed state before resetting to idle. */
const COPY_STATUS_MS = 2500;

/** The API origin these cards quote.
 *
 * A card whose command cannot be copied and run is decoration. Read from the
 * same `VITE_API_BASE_URL` the app's own client uses, so the page can never
 * advertise one origin while the app talks to another.
 *
 * `lib/api.ts` itself resolves `VITE_API_BASE_URL` to `""` (same-origin) when
 * the variable is unset, since its own `DEFAULT_BASE_URL` is what every fetch
 * in this app actually uses. This page keeps its own local-dev fallback
 * instead, because an empty string is a correct same-origin base for a
 * `fetch()` call but a useless one to print in a code block or resolve a link
 * href from: a reader cannot paste "" into a terminal, and an empty-string
 * href resolves to the current page rather than to the API. The two constants
 * intentionally diverge for that reason.
 */
const API_ORIGIN =
  (import.meta.env?.VITE_API_BASE_URL as string | undefined) ?? "http://127.0.0.1:8000";

// ---------------------------------------------------------------------------
// The commands, each verified live. Exported so a test can pin the text
// without reaching through the clipboard, and so a reader of this module
// finds every printed claim in one place.
// ---------------------------------------------------------------------------

export const REST_EXAMPLE = `curl -X POST ${API_ORIGIN}/v1/query \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"text": "Which diseases are associated with BRCA1?", "session_id": "demo-1"}'`;

/** R16. Posted exactly as printed against develop on 2026-09-13: 200, a real
 *  answer, five citations, no validation error. `ask` is a MUTATION, the
 *  question field is `text`, and `sessionId` is required. */
export const GRAPHQL_EXAMPLE = `curl -X POST ${API_ORIGIN}/graphql \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"query": "mutation { ask(input: { text: \\"Which diseases are associated with BRCA1?\\", sessionId: \\"demo-1\\" }) { answer citations { source sourceUrl } } }"}'`;

// The trailing slash is load-bearing, not cosmetic. `app.py` mounts the MCP
// SDK's Starlette sub-app at `/mcp` (see the comment above `app.mount("/mcp",
// ...)` there), so a bare `POST /mcp` 307-redirects to `/mcp/`. Every
// spec-compliant HTTP client follows that redirect transparently over a
// same-scheme hop, which is why the route itself was never wrong. But behind
// Railway's TLS-terminating proxy, this app's `Location` header comes back as
// a plaintext `http://` URL (uvicorn's `forwarded_allow_ips` does not trust
// Railway's proxy IP by default, so the redirect is built from the
// unencrypted scheme of the connection the container actually sees), and a
// client that honors that literally sends its next request, bearer token
// included, over plaintext before the following redirect brings it back to
// https. Printing the URL with the slash already on it means a pasted config
// never triggers that redirect at all. Verified live against
// `https://search-agent-api-develop-43b3.up.railway.app` on 2026-09-20:
// `POST /mcp` 307s to a plaintext Location, `POST /mcp/` returns 200 with a
// valid initialize response. Full account:
// `testing/Developer/reports/2026-09-20_integrations/findings.md`.
export const MCP_CONFIG = `{
  "mcpServers": {
    "ncbi-search": {
      "url": "${API_ORIGIN}/mcp/"
    }
  }
}`;

export const CLI_EXAMPLE = `s3 login
s3 ask "diseases linked to BRCA1"`;

export const KGX_EXAMPLE = `s3-kgx-export NCBIGene:672 \\
  --hops 1 --output-dir ./kgx-out`;

/** The event stream frame, transcribed from `adapters/web_sse/app.py`'s own
 *  emitter (`{"id": seq, "event": type, "data": envelope_json}`) and
 *  `lib/events.ts`'s `AgentEvent` envelope, not from the old page's
 *  invented shape. */
export const EVENT_STREAM_EXAMPLE = `id: 1
event: guard
data: {"type":"guard","version":"v1","trace_id":"7c1e2a","seq":1,"ts":"2026-09-13T09:00:00Z","payload":{"passed":true,"category":"ok","reason":null}}`;

// ---------------------------------------------------------------------------
// The card icons. Inline SVG rather than an icon package: this app has no
// icon dependency today, and `production-standards.md` puts a new one in the
// ASK bucket. Each is a 20px stroked mark on `currentColor`, so the circle
// below sets the colour once from a token.
// ---------------------------------------------------------------------------

function IconFrame({ children }: { children: React.ReactNode }) {
  return (
    <Box
      aria-hidden="true"
      sx={{
        width: 44,
        height: 44,
        borderRadius: "50%",
        flex: "none",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        bgcolor: designTokens.layer1Wash,
        color: designTokens.layer1,
        mb: 1.5,
      }}
    >
      {children}
    </Box>
  );
}

const svgProps = {
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  // `as const` on the whole object rather than per key: without it TypeScript
  // widens each value to `string`, and `focusable` accepts only `"auto"` or a
  // booleanish literal, so the build fails on all four icons at once.
  focusable: "false",
} as const;

/** A stream: a request arrow and the events that come back after it. */
function StreamIcon() {
  return (
    <svg {...svgProps}>
      <path d="M3 7h13l-3-3M3 7l3 3" />
      <path d="M21 14h-6M21 18h-10" />
    </svg>
  );
}

/** A graph: one node joined to three others, which is what a typed graph
 *  query returns in a single round trip. */
function GraphIcon() {
  return (
    <svg {...svgProps}>
      <circle cx="12" cy="12" r="2.4" />
      <circle cx="4.5" cy="6" r="1.8" />
      <circle cx="19.5" cy="6" r="1.8" />
      <circle cx="12" cy="20.5" r="1.8" />
      <path d="M10.3 10.4 6 7.3M13.7 10.4 18 7.3M12 14.4v4.3" />
    </svg>
  );
}

/** A plug: the shape of a tool being connected to something else. */
function PlugIcon() {
  return (
    <svg {...svgProps}>
      <path d="M9 2v5M15 2v5" />
      <path d="M6 7h12v3a6 6 0 0 1-6 6 6 6 0 0 1-6-6V7Z" />
      <path d="M12 16v6" />
    </svg>
  );
}

/** A terminal: a prompt and a caret. */
function TerminalIcon() {
  return (
    <svg {...svgProps}>
      <rect x="2.5" y="4" width="19" height="16" rx="2" />
      <path d="M6.5 9.5 9 12l-2.5 2.5M11.5 15h6" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// The card.
// ---------------------------------------------------------------------------

interface CardCopy {
  /** The button's visible label, e.g. "Copy curl". */
  label: string;
  /** The text the click writes to the clipboard. */
  text: string;
  /** The accessible name, since "Copy curl" alone does not say which card
   *  it belongs to when a screen reader user is listing the page's buttons. */
  accessibleName: string;
  testId: string;
}

interface CardLink {
  label: string;
  href: string;
  testId: string;
}

/**
 * The button row, pinned to the bottom of its card, plus the copy
 * confirmation.
 *
 * WHY THE ROW OWNS THE COPY STATE rather than each button owning its own:
 * the row is what has to stay one line tall so the four cards' buttons line
 * up across a row, which is the whole complaint R15 records. A status message
 * rendered inline beside the buttons pushed the row's height around as it
 * appeared and disappeared, so it sits under the row instead, where it
 * changes nothing above it.
 *
 * The failure path is real, not decorative: `navigator.clipboard` is absent
 * on an insecure origin, and `writeText` can reject on a denied permission.
 * Either way the reader is told to copy the text by hand, never left thinking
 * the click did nothing. `role="status"` matches `FeedbackSurface.tsx`'s own
 * transient status region rather than inventing a second pattern for the
 * same job.
 *
 * The first copy action is the filled main action and any further one is
 * outlined, which is the reference's own "Copy curl" beside "API Docs"
 * hierarchy applied to a card whose secondary action is also a copy.
 */
function CardActionRow({ copies, links }: { copies?: CardCopy[]; links?: CardLink[] }) {
  const [state, setState] = useState<{ testId: string; status: CopyStatus } | null>(null);
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

  const handleCopy = async (copy: CardCopy) => {
    let status: CopyStatus;
    try {
      if (!navigator.clipboard) {
        throw new Error("clipboard API unavailable");
      }
      await navigator.clipboard.writeText(copy.text);
      status = "copied";
    } catch {
      status = "error";
    }
    setState({ testId: copy.testId, status });
    if (timer.current !== null) {
      clearTimeout(timer.current);
    }
    timer.current = setTimeout(() => setState(null), COPY_STATUS_MS);
  };

  const hasActions = (copies?.length ?? 0) > 0 || (links?.length ?? 0) > 0;
  if (!hasActions) return null;

  return (
    <Box sx={{ mt: "auto", pt: 2 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
        {copies?.map((copy, index) => (
          <Button
            key={copy.testId}
            variant={index === 0 ? "contained" : "outlined"}
            size="small"
            onClick={() => void handleCopy(copy)}
            aria-label={copy.accessibleName}
            data-testid={copy.testId}
          >
            {state?.testId === copy.testId && state.status === "copied" ? "Copied" : copy.label}
          </Button>
        ))}
        {links?.map((link) => (
          <Button
            key={link.testId}
            variant="outlined"
            size="small"
            href={link.href}
            target="_blank"
            rel="noopener noreferrer"
            data-testid={link.testId}
            aria-label={`${link.label}, opens in a new tab`}
          >
            {link.label}
          </Button>
        ))}
      </Box>
      {state !== null ? (
        <Box
          role="status"
          data-testid={`${state.testId}-status`}
          sx={{
            mt: 1,
            fontSize: 11.5,
            color: state.status === "error" ? designTokens.risk : designTokens.ok,
          }}
        >
          {state.status === "copied"
            ? "Copied to clipboard."
            : "Could not copy automatically. Select the example and copy it by hand."}
        </Box>
      ) : null}
    </Box>
  );
}

/**
 * One integration card: a round icon, a title, a short description, an
 * optional code box, then the button row pinned to the bottom.
 *
 * `height: "100%"` inside a grid row is what makes the four cards equal
 * height, and `mt: "auto"` on the button row is what makes their buttons line
 * up. Both are needed: equal cards with the buttons following the text would
 * still stagger.
 */
function IntegrationCard({
  icon,
  title,
  body,
  code,
  codeLabel,
  copies,
  links,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
  code?: string;
  codeLabel?: string;
  copies?: CardCopy[];
  links?: CardLink[];
}) {
  return (
    <Box
      sx={{
        bgcolor: designTokens.surface,
        border: `1px solid ${designTokens.line}`,
        borderRadius: 1,
        p: 2.5,
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <IconFrame>{icon}</IconFrame>
      <Typography variant="h3" component="h2" sx={{ mb: 1 }}>
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
          aria-label={codeLabel ?? `${title} example`}
          sx={{
            ...mono,
            fontSize: 11.5,
            m: 0,
            mt: 1.5,
            p: 1.25,
            // Scrolled rather than wrapped, which is the opposite of what this
            // page did when five cards each carried a code box. Only one card
            // shows code now, and it is a small JSON object whose lines are
            // short enough to read at 390px; a wrapped brace-per-line config
            // reads as broken, while a scroll container keeps the shape and
            // still cannot bleed the page sideways.
            overflowX: "auto",
            bgcolor: designTokens.surfaceSunk,
            border: `1px solid ${designTokens.line}`,
            borderRadius: 0.5,
          }}
        >
          {code}
        </Box>
      ) : null}
      <CardActionRow copies={copies} links={links} />
    </Box>
  );
}

/**
 * Two cards per row, one below 720px.
 *
 * 720px is the design's own breakpoint rather than a MUI one: the prototype
 * names that pixel value for the app bar, and `AppShell.tsx` already follows
 * it, so the page and its chrome change shape at the same width.
 */
const CARD_GRID = {
  display: "grid",
  gap: 2,
  alignItems: "stretch",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  "@media (max-width:720px)": { gridTemplateColumns: "minmax(0, 1fr)" },
} as const;

/** The compact grid the About screen and the API documentation section share. */
const GRID = {
  display: "grid",
  gap: 2,
  gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
} as const;

/** The real figures behind the summary chips. See the file docstring for
 *  where each one comes from. */
const SUMMARY_CHIPS = ["115M nodes", "693M edges", "3 data layers", "7 tools"] as const;

/** A compact prose card for the API documentation section. No icon and no
 *  button row: these are reference notes rather than surfaces to operate. */
function NoteCard({
  title,
  body,
  code,
  copy,
}: {
  title: string;
  body: string;
  code?: string;
  copy?: CardCopy;
}) {
  return (
    <Box
      sx={{
        bgcolor: designTokens.surface,
        border: `1px solid ${designTokens.line}`,
        borderRadius: 1,
        p: 2.5,
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Typography variant="h4" component="h3" sx={{ mb: 1 }}>
        {title}
      </Typography>
      <Typography variant="body2" sx={{ color: designTokens.inkMuted }}>
        {body}
      </Typography>
      {code ? (
        <Box
          component="pre"
          tabIndex={0}
          role="region"
          aria-label={`${title} example`}
          sx={{
            ...mono,
            fontSize: 11.5,
            m: 0,
            mt: 1.5,
            p: 1.25,
            overflowX: "auto",
            bgcolor: designTokens.surfaceSunk,
            border: `1px solid ${designTokens.line}`,
            borderRadius: 0.5,
          }}
        >
          {code}
        </Box>
      ) : null}
      <CardActionRow copies={copy ? [copy] : undefined} />
    </Box>
  );
}

export function IntegrationsScreen() {
  // The lede is ONE LINE, which is the reference's own shape and what R15
  // asks for. A longer version measured as two lines at 900px, so it was cut
  // rather than left to wrap above the chips.
  return (
    <Page
      title="Integrations"
      lede="The same agent, reachable four ways, returning the same citations."
    >
      <Box
        role="list"
        aria-label="What the agent is built on"
        sx={{ display: "flex", flexWrap: "wrap", gap: 1, mb: 3 }}
      >
        {SUMMARY_CHIPS.map((label) => (
          <Chip
            key={label}
            role="listitem"
            label={label}
            size="small"
            variant="outlined"
            sx={{
              fontWeight: 600,
              color: designTokens.inkMuted,
              borderColor: designTokens.line,
              bgcolor: designTokens.surface,
            }}
          />
        ))}
      </Box>

      {/*
        `data-testid` so a test can count the cards in THIS grid rather than
        every level-2 heading on the page. The access notice and the API
        documentation section below both carry their own, and a count over the
        whole page would pass at five cards as readily as at four, which is
        the number decision U3 actually settles.
      */}
      <Box sx={CARD_GRID} data-testid="integration-cards">
        <IntegrationCard
          icon={<StreamIcon />}
          title="REST and SSE"
          body="Start a run, then subscribe to its event stream and render it as it happens, exactly as this interface does. Resumable after a dropped connection."
          copies={[
            {
              label: "Copy curl",
              text: REST_EXAMPLE,
              accessibleName: "Copy the REST and SSE curl command",
              testId: "integration-copy-rest",
            },
          ]}
          links={[
            {
              label: "API reference",
              href: `${API_ORIGIN}/docs`,
              testId: "integration-link-api-docs",
            },
            {
              label: "OpenAPI schema",
              href: `${API_ORIGIN}/openapi.json`,
              testId: "integration-link-openapi-schema",
            },
          ]}
        />
        <IntegrationCard
          icon={<GraphIcon />}
          title="GraphQL"
          body="One typed request and one typed response over the same core, for a client that wants the whole answer in a single round trip. No live stream: a run comes back complete or not at all."
          copies={[
            {
              label: "Copy query",
              text: GRAPHQL_EXAMPLE,
              accessibleName: "Copy the GraphQL mutation",
              testId: "integration-copy-graphql",
            },
          ]}
          links={[
            {
              label: "GraphQL endpoint",
              href: `${API_ORIGIN}/graphql`,
              testId: "integration-link-graphql",
            },
          ]}
        />
        <IntegrationCard
          icon={<PlugIcon />}
          title="MCP server"
          body="One advertised tool, ask_biomedical_question. It folds a whole run into a single cited answer, and the seven internal tools are never separately reachable."
          code={MCP_CONFIG}
          codeLabel="MCP server configuration"
          copies={[
            {
              label: "Copy config",
              text: MCP_CONFIG,
              accessibleName: "Copy the MCP server configuration",
              testId: "integration-copy-mcp",
            },
          ]}
        />
        <IntegrationCard
          icon={<TerminalIcon />}
          title="Command line tools"
          body="Two console commands rather than HTTP routes. s3 asks a question and prints the answer, human-readable by default and JSON with --json. s3-kgx-export writes a query-scoped subgraph as BioLink-compliant KGX: nodes.tsv, edges.tsv and a manifest, from seed CURIEs and bounded hops."
          copies={[
            {
              label: "Copy command",
              text: CLI_EXAMPLE,
              accessibleName: "Copy the command line example",
              testId: "integration-copy-cli",
            },
            {
              label: "Copy KGX command",
              text: KGX_EXAMPLE,
              accessibleName: "Copy the KGX export command",
              testId: "integration-copy-kgx",
            },
          ]}
        />
      </Box>

      <Box
        sx={{
          mt: 3,
          p: 2.5,
          bgcolor: designTokens.layer1Wash,
          border: `1px solid ${designTokens.line}`,
          borderRadius: 1,
        }}
      >
        <Typography variant="h4" component="h2" sx={{ mb: 1 }}>
          Access
        </Typography>
        <Box
          component="ul"
          sx={{ m: 0, pl: 2.5, color: designTokens.inkMuted, fontSize: "13.5px", lineHeight: 1.6 }}
        >
          <li>Registered accounts: the Log in flow issues the bearer token every surface here accepts.</li>
          <li>GraphQL and the MCP server: an account is required, so a guest cannot reach either.</li>
          <li>REST and SSE: a guest may run queries without an account, within the anonymous daily cap.</li>
        </Box>
      </Box>

      <Typography variant="h2" component="h2" sx={{ mt: 5, mb: 1.5 }}>
        API documentation
      </Typography>
      <Typography sx={{ color: designTokens.inkMuted, maxWidth: "66ch", mb: 3 }}>
        What a programmatic caller sends, what comes back, and what the system will refuse to do.
      </Typography>
      {/*
        The SAME two-column grid as the cards above, not the auto-fit grid the
        About screen uses. Measured at 900px: auto-fit gave three columns and
        left "Limits" alone on a second row, with the two short prose cards
        stretched to the height of the one carrying a code box. Two columns
        pairs each short card with a short one.

        The ORDER is part of that: the two prose-only cards share the first
        row and the tall code-carrying card shares the second with the longest
        remaining prose, so neither row carries a card stretched far past its
        own content.
      */}
      <Box sx={CARD_GRID}>
        <NoteCard
          title="Authentication"
          body="Every programmatic call carries an Authorization header of the form Bearer followed by the token. POST /auth/login exchanges the same email and password you use here for that token and a refresh token."
        />
        <NoteCard
          title="Citations"
          body="Every claim is tied to a specific record, with the layer that produced it, the tool that fetched it, its evidence type, its confidence and its licence. An answer with an uncited sentence is a defect."
        />
        <NoteCard
          title="The event stream"
          body="A run emits eleven kinds of event: guard, think, plan, tool_start, tool_result, token, citation, trust_signal, cost, error and done. Each SSE frame carries the sequence number as its id, the event type as its name, and the whole envelope as its data. A refusal is a normal outcome with a reason attached, not an error."
          code={EVENT_STREAM_EXAMPLE}
          copy={{
            label: "Copy frame",
            text: EVENT_STREAM_EXAMPLE,
            accessibleName: "Copy the event stream frame",
            testId: "docs-copy-event-stream",
          }}
        />
        <NoteCard
          title="Limits"
          body="Each tool carries its own per-call timeout and rate-limit pool, and a query is capped at twenty Layer 2 and Layer 3 calls. A call that would exceed either fails fast with a retry hint rather than joining an unbounded queue."
        />
      </Box>
    </Page>
  );
}

// ---------------------------------------------------------------------------
// "What happens to your question": the guided walk, product-owner request of
// 2026-09-13.
//
// WHERE THIS LAYOUT COMES FROM, stated rather than assumed.
// `docs/build/design/README.md`'s coverage table says "Integrations, docs and
// about | NO", so the About page has NO design in the design system, and
// neither does a guided walk anywhere else in it.
// `.claude/rules/design-consistency.md` requires that gap to be NAMED out loud
// rather than filled silently, and this is the naming. Nothing below is
// invented: every treatment is copied from a designed neighbour.
//
//   - The spine, its numbered nodes and the line joining them, from the run
//     screen's stepper (`screens/RunScreen.tsx`) and the card it implements,
//     `design-system/components/pipeline-stepper.html`: a 2px `blue`
//     connector, a node with a 2px border filled `blue` once its step is done,
//     and the node's label in `ink`. Turned on its side here, because seven
//     stops carrying two to four sentences each cannot sit in a five-across
//     row, and because one column at every width is what this page needs.
//   - The layer badges, from the layer cards already on this screen below: a
//     square of the layer colour, the name, and the `L1`/`L2`/`L3` mark in
//     mono at the end of the row.
//   - The annotated answer mock in stop 6, from the real components'
//     treatments in `screens/AnswerScreen.tsx`: the citation chip's mono
//     numeral with a 4px left border in its layer colour over that layer's
//     wash, the trust pill's 999px radius, and the source card's 4px
//     layer-coloured left border.
//
// Every colour reads a `designTokens` entry. No hex literal appears below.
//
// EVERY CLAIM THE WALK MAKES WAS READ OUT OF THE CODE, not written from
// memory of how the system probably works, which is the same discipline
// T-4.16-04 imposed on the Integrations page's commands. Where each one was
// verified, on 2026-09-13:
//
//   - Five steps, in order: `core/graph.py`'s `add_node` calls for
//     guardrail, think, plan, act and write, with `set_entry_point("guardrail")`.
//   - Which tier runs which step: `core/graph.py`'s `_dispatch_tier_call`
//     sites pass "guard" for guardrail, "plan" for think AND for plan, and
//     "synth" for write.
//   - A tier's model is resolved from configuration and held for the query:
//     `harness/tiers.py`, `TierContext` ("fetched once at query start and
//     held for the query's duration"), reading GUARD_MODEL, PLAN_MODEL and
//     SYNTH_MODEL. No model is named here, and none should be.
//   - The stable prefix: `harness/cache.py` assembles system instructions,
//     the seven tool schemas, then the static graph and BioLink schema, in a
//     fixed order that is never reordered at runtime.
//   - The guardrail's refusal categories: `contracts/events.py`'s
//     `GuardPayload.category` and `chat/GuardrailBanner.tsx`'s `CATEGORY_COPY`
//     (off_topic, medical_advice, injection, rate_limited, cost_capped,
//     write_seeking).
//   - Entity resolution is live-confirmed: `core/graph.py`'s
//     `resolve_exact_identifiers` pre-pass, then "a span whose CURIE cannot be
//     confirmed by a live lookup" does not contribute one. NCBIGene:672 for
//     BRCA1 appears in `tools/cypher_query.py`'s own examples.
//   - Timeouts and the call budget: `CYPHER_QUERY_TIMEOUT_SECONDS` is 30
//     seconds (`tools/cypher_query.py`), `tools/ncbi_transport.py` carries the
//     15-second per-call budget with one backoff retry, and
//     `harness/call_budget.py`'s `MAX_LAYER_2_3_CALLS_PER_QUERY` is 20.
//   - Results come back typed and bounded: each tool has its own `*_schemas.py`
//     input and output models, and `harness/coordinator_worker.py` caps a
//     finding at `_MAX_FINDING_TOTAL_BYTES` and records that it cut.
//   - Findings are handed to Synth as data: `synthesis/findings.py`'s
//     `build_synth_messages` labels the question "data, not an instruction to
//     you" and puts the findings and the question in the trailing user
//     message, never in the system block.
//   - A sentence is checked against its record in code:
//     `synthesis/grounding.py`'s `ground_claim` accepts a claim only on a
//     substring match against the record's own field value.
//   - The event stream: `contracts/events.py`'s envelope `type` union carries
//     guard, think, plan, tool_start, tool_result, token, citation,
//     trust_signal, cost, error and done.
//   - The scientist is presentation only: `shell/PersonaChip.tsx`'s docstring,
//     "the persona never changes which tools run, which records are
//     retrieved, or what the trust signal says".
// ---------------------------------------------------------------------------

/** The one question the walk follows, start to finish. */
const JOURNEY_QUESTION = "Which diseases are associated with BRCA1?";

/** The three harness tiers and what each one runs. No model is named: a tier
 *  is a capability, and its model is a configuration value. */
const JOURNEY_TIERS = [
  {
    name: "Guard tier",
    kind: "a fast, inexpensive model",
    body: "Runs the guardrail. Is this a biomedical research question at all, and is it asking for medical advice rather than for evidence? A question that fails either check is turned away with a plain sentence saying which one, and nothing is looked up.",
  },
  {
    name: "Plan tier",
    kind: "a mid-range model",
    body: "Runs Think, which works out the shape of the question and which real records its words point at, so BRCA1 becomes NCBI Gene 672, confirmed by a live lookup rather than recalled. Then runs Plan, which picks the tools to call and writes the graph query itself.",
  },
  {
    name: "Synth tier",
    kind: "the strongest model",
    body: "Runs Write, which composes the answer once the records are back.",
  },
] as const;

/** The three layers Act reaches, with the tools that read each one. */
const JOURNEY_LAYERS: { n: 1 | 2 | 3; name: string; tools: string; body: string }[] = [
  {
    n: 1,
    name: "Knowledge graph",
    tools: "cypher_query",
    body: "115M nodes and 693M edges merged from five NCBI databases. One query returns a stored link, which is why a question like this one starts here.",
  },
  {
    n: 2,
    name: "Live NCBI APIs",
    // `pathogen_detection` is a Layer 2 tool by its own declaration
    // (`tools/pathogen_detection.py`, `layer="layer_2_api"`, an NCBI-native
    // bulk source rather than an enrichment API); it sat under layer 3 here
    // until 2026-09-13, when the Architecture page, built from the tool code,
    // disagreed with this walk.
    tools: "ncbi_efetch, ncbi_dbsnp, pathogen_detection",
    body: "Fetched while you wait, so they are current. Used for anything the graph cannot name, such as turning a concept id into a disease name.",
  },
  {
    n: 3,
    name: "Enrichment",
    tools: "pubtator_annotate, litvar2_lookup, clinicaltrials_search",
    body: "Literature and trial evidence, added when the question asks for it rather than by default.",
  },
];

/** One stop on the spine: a numbered node, the line down to the next stop,
 *  and the stop's own heading and prose. */
export function JourneyStop({
  index,
  last,
  title,
  children,
}: {
  index: number;
  last?: boolean;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Box component="li" sx={{ display: "flex", gap: { xs: 1.5, sm: 2 }, alignItems: "stretch" }}>
      <Box
        sx={{
          position: "relative",
          width: 26,
          flex: "none",
          display: "flex",
          justifyContent: "center",
        }}
      >
        {/* The connector, drawn from this node's centre down to the next
            one. Omitted on the last stop, so the spine ends at stop 7
            rather than trailing past it. */}
        {last ? null : (
          <Box
            aria-hidden="true"
            sx={{
              position: "absolute",
              top: 26,
              bottom: 0,
              width: 2,
              bgcolor: designTokens.blue,
            }}
          />
        )}
        <Box
          sx={{
            width: 26,
            height: 26,
            borderRadius: "50%",
            flex: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            position: "relative",
            zIndex: 1,
            border: `2px solid ${designTokens.blue}`,
            bgcolor: designTokens.blue,
            color: designTokens.surface,
            ...mono,
            fontSize: 12,
            fontWeight: 700,
          }}
        >
          {index}
        </Box>
      </Box>
      <Box sx={{ flex: 1, minWidth: 0, pb: last ? 0 : 3.5 }}>
        <Typography variant="h3" component="h3" sx={{ mb: 1 }}>
          {title}
        </Typography>
        {children}
      </Box>
    </Box>
  );
}

/** Body prose inside a stop. One place to set the measure and the colour, so
 *  seven stops cannot drift apart. */
export function StopText({ children }: { children: React.ReactNode }) {
  return (
    <Typography variant="body2" sx={{ color: designTokens.inkMuted, maxWidth: "62ch", mb: 1.5 }}>
      {children}
    </Typography>
  );
}

/** A small caption naming what the thing beside it is, in the mock and above
 *  the grouped lists. The design system's own eyebrow treatment. */
export function StopLabel({ children }: { children: React.ReactNode }) {
  return (
    <Typography variant="overline" component="p" sx={{ color: designTokens.inkFaint, m: 0 }}>
      {children}
    </Typography>
  );
}

/**
 * Stop 6's annotated mock of the finished answer.
 *
 * Built from the real components' treatments rather than from a screenshot,
 * so it cannot go stale in a way nobody can see: the citation chip, the trust
 * pill, the source card and the follow-up field each copy the shape their own
 * component renders in `AnswerScreen.tsx`.
 *
 * `aria-hidden` is deliberately NOT used. Everything here is real text a
 * reader should hear, and the small labels beside each part say what it is,
 * which is the whole point of an annotated mock.
 */
function AnswerMock() {
  return (
    <Box
      data-testid="about-answer-mock"
      sx={{
        bgcolor: designTokens.surface,
        border: `1px solid ${designTokens.line}`,
        borderRadius: 1,
        p: 2,
        maxWidth: 560,
      }}
    >
      <StopLabel>A cited sentence</StopLabel>
      <Typography variant="body2" sx={{ mt: 0.5, mb: 2 }}>
        BRCA1 is associated with hereditary breast and ovarian cancer syndrome.{" "}
        <Box
          component="span"
          sx={{
            ...mono,
            display: "inline-flex",
            alignItems: "center",
            gap: 0.6,
            fontSize: 11.5,
            fontWeight: 600,
            px: 0.75,
            borderRadius: 0.5,
            border: `1px solid ${designTokens.lineStrong}`,
            borderLeft: `4px solid ${designTokens.layer1}`,
            bgcolor: designTokens.layer1Wash,
          }}
        >
          1
          <Box component="span" sx={{ color: designTokens.inkMuted, fontWeight: 400 }}>
            MedGen C0677776
          </Box>
        </Box>
      </Typography>

      <StopLabel>The trust line</StopLabel>
      <Box sx={{ mt: 0.5, mb: 2 }}>
        <Box
          component="span"
          sx={{
            display: "inline-flex",
            alignItems: "center",
            borderRadius: 999,
            px: 1.5,
            py: 0.5,
            fontSize: 12.5,
            fontWeight: 600,
            color: designTokens.ink,
            bgcolor: designTokens.layer2Wash,
            border: `1px solid ${designTokens.ok}`,
          }}
        >
          Grounded · every claim cited
        </Box>
      </Box>

      <StopLabel>One source, opening on the record it came from</StopLabel>
      <Box
        sx={{
          mt: 0.5,
          mb: 2,
          border: `1px solid ${designTokens.line}`,
          borderLeft: `4px solid ${designTokens.layer1}`,
          borderRadius: 0.5,
          px: 1.5,
          py: 1,
          display: "flex",
          alignItems: "center",
          gap: 1.25,
          flexWrap: "wrap",
        }}
      >
        <Box component="span" sx={{ ...mono, fontWeight: 700, fontSize: 12 }}>
          [1]
        </Box>
        <Typography variant="body2" sx={{ fontWeight: 600 }}>
          Hereditary breast and ovarian cancer syndrome
        </Typography>
        <Box
          component="span"
          sx={{ ...mono, ml: "auto", fontSize: 11.5, color: designTokens.inkMuted }}
        >
          L1 · knowledge graph
        </Box>
      </Box>

      <StopLabel>The follow-up field</StopLabel>
      <Box
        sx={{
          mt: 0.5,
          border: `2px solid ${designTokens.line}`,
          borderRadius: 1,
          px: 1.5,
          py: 1,
          color: designTokens.inkFaint,
          fontSize: 13.5,
          bgcolor: designTokens.surfaceSunk,
        }}
      >
        Ask a follow-up
      </Box>
    </Box>
  );
}

export interface AboutScreenProps {
  /**
   * Takes the reader to the search home page, wired by `App` so the closing
   * "follow the same question live" line is a real link rather than a
   * sentence naming the tab. Optional so the screen still renders standalone.
   */
  onNavigateToSearch?: () => void;
  /**
   * Takes the reader to the Architecture page, wired by `App`, so the strip
   * at the foot of this page is a real link through the same screen switch
   * the nav uses. Optional, so the screen still renders standalone.
   */
  onNavigateToArchitecture?: () => void;
}

export function AboutScreen({
  onNavigateToSearch,
  onNavigateToArchitecture,
}: AboutScreenProps = {}) {
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
      <Typography variant="h2" component="h2" sx={{ mb: 1.5 }}>
        What happens to your question
      </Typography>
      <Typography sx={{ color: designTokens.inkMuted, maxWidth: "66ch", mb: 3 }}>
        One real question, followed from the moment you press send to the answer on your screen.
        Seven stops, each naming who is acting.
      </Typography>

      <Box
        component="ol"
        role="list"
        data-testid="about-journey"
        sx={{ listStyle: "none", m: 0, mb: 5, p: 0 }}
      >
        <JourneyStop index={1} title="You ask">
          <StopText>
            You type a question and pick how the answer is written: Plain language, the default,
            or Researcher. That is the whole of your part. Everything after it happens on the
            server, and your question is carried through as data rather than as an instruction the
            system obeys.
          </StopText>
          <StopLabel>The question this walk follows</StopLabel>
          <Box
            data-testid="about-journey-question"
            sx={{
              mt: 0.5,
              bgcolor: designTokens.surface,
              border: `2px solid ${designTokens.line}`,
              borderRadius: 1,
              px: 1.75,
              py: 1.25,
              maxWidth: 560,
            }}
          >
            {JOURNEY_QUESTION}
          </Box>
        </JourneyStop>

        <JourneyStop index={2} title="The model steps, tier by tier">
          <StopText>
            Four of the five steps ask a language model something, and the harness decides which
            model each one gets. There are three tiers, matched to how hard the step is. A tier's
            model is read from configuration once at the start of your question and held there, so
            it cannot change partway through a run.
          </StopText>
          <Box sx={{ display: "grid", gap: 1.5, mb: 1.5, maxWidth: 620 }}>
            {JOURNEY_TIERS.map((tier) => (
              <Box
                key={tier.name}
                sx={{
                  bgcolor: designTokens.surface,
                  border: `1px solid ${designTokens.line}`,
                  borderLeft: `4px solid ${designTokens.blue}`,
                  borderRadius: 0.5,
                  px: 1.75,
                  py: 1.25,
                }}
              >
                <Typography variant="h4" component="p" sx={{ mb: 0.5 }}>
                  {tier.name}, {tier.kind}
                </Typography>
                <Typography variant="body2" sx={{ color: designTokens.inkMuted }}>
                  {tier.body}
                </Typography>
              </Box>
            ))}
          </Box>
          <StopText>
            All of these calls open with the same unchanging block of text: the system
            instructions, the descriptions of the seven tools, and the graph's own schema. Reusing
            it exactly is what keeps the cost of a question bounded, so it is fixed in code and
            never reordered between calls.
          </StopText>
        </JourneyStop>

        <JourneyStop index={3} title="The search goes out">
          <StopText>
            Act runs the tools Plan chose, across three layers of data. Each call carries its own
            time limit, 90 seconds for a graph query and 15 seconds for a live NCBI call, and one
            question may make at most 20 live calls in total. A call that would exceed either of
            those fails fast and says which limit it hit, rather than leaving you waiting. This is
            the part you watch on the progress screen.
          </StopText>
          <Box
            data-testid="about-journey-layers"
            sx={{ display: "grid", gap: 1.5, maxWidth: 620 }}
          >
            {JOURNEY_LAYERS.map((layer) => {
              const { main, wash } = layerColour(layer.n);
              return (
                <Box
                  key={layer.n}
                  data-testid={`about-journey-layer-${layer.n}`}
                  sx={{
                    bgcolor: wash,
                    border: `1px solid ${designTokens.line}`,
                    borderLeft: `4px solid ${main}`,
                    borderRadius: 0.5,
                    px: 1.75,
                    py: 1.25,
                  }}
                >
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1.25,
                      flexWrap: "wrap",
                      mb: 0.5,
                    }}
                  >
                    <Typography variant="h4" component="p">
                      {layer.name}
                    </Typography>
                    {/*
                      The mark reads in INK, not in the layer colour, and the
                      colour is carried by the 4px left border and the wash
                      behind it instead. MEASURED, not preferred: axe put
                      `layer2` (#2E8540) on `layer2Wash` at 4.01:1 for an 11px
                      bold mark, against WCAG 1.4.3's 4.5:1. This is exactly
                      the resolution `AnswerScreen.tsx`'s trust pill already
                      documents for the same pair, "reading the LABEL in ink
                      while the border, the wash and the check mark keep
                      carrying the green", so it copies a decision rather than
                      inventing one. The layer cards further down this page
                      keep the coloured mark because their ground is `surface`,
                      where the same pair passes.
                    */}
                    <Box
                      component="span"
                      sx={{
                        ...mono,
                        ml: "auto",
                        fontSize: 11,
                        fontWeight: 700,
                        color: designTokens.ink,
                      }}
                    >
                      L{layer.n}
                    </Box>
                  </Box>
                  <Typography variant="body2" sx={{ color: designTokens.inkMuted }}>
                    {layer.body}
                  </Typography>
                  <Box
                    component="p"
                    sx={{ ...mono, fontSize: 11.5, color: designTokens.inkFaint, mt: 0.75, mb: 0 }}
                  >
                    {layer.tools}
                  </Box>
                </Box>
              );
            })}
          </Box>
        </JourneyStop>

        <JourneyStop index={4} title="The records come back">
          <StopText>
            Every tool returns typed data checked against its own schema, never loose text. A long
            result is cut to a bounded size and the cut is recorded rather than hidden. Each record
            arrives with its provenance attached: the source, the record id, the link to it, and
            the layer it came from.
          </StopText>
          <StopText>
            That bundle is handed to the Synth tier as material to read, labelled as data rather
            than as instructions. So a sentence buried inside a fetched abstract is something the
            model can quote, never something it can be told to obey, and the model may only state
            what the records in front of it support.
          </StopText>
        </JourneyStop>

        <JourneyStop index={5} title="The answer is written, then streamed to you">
          <StopText>
            Write composes the answer from those records alone. Each sentence is then checked in
            code against the record it points at, and a sentence that record does not support is
            dropped rather than reworded. If nothing citeable survives, the system says it could
            not find an answer and stops instead of answering from memory. That rule is called cite
            or refuse.
          </StopText>
          <StopText>
            What reaches your browser is a stream of small events rather than one finished page:
            each step as it completes, each tool call, the answer text as it is written, each
            citation, a trust signal, then done. The progress screen and the answer screen are both
            just that stream being drawn as it arrives.
          </StopText>
        </JourneyStop>

        <JourneyStop index={6} title="What you get">
          <StopText>
            A paragraph you can check line by line. Every sentence carries a numbered chip pointing
            at the record behind it, a trust line says whether the whole answer was grounded, and
            each source opens as a card with a link to the NCBI record it came from. Below the
            answer, a follow-up field carries the conversation forward, and if you are signed in
            the question is kept in your history.
          </StopText>
          <AnswerMock />
        </JourneyStop>

        <JourneyStop index={7} last title="What it will not do">
          <StopText>
            It will not tell you what to do about a diagnosis or a treatment. It assembles cited
            evidence, and a clinician makes that call. It will not answer from memory when the
            search comes back empty, and it will not ship a sentence with no source behind it.
          </StopText>
          <StopText>
            The scientist's name beside a run is presentation only. It never changes which tools
            run, which records are read, or what the trust line says.
          </StopText>
        </JourneyStop>
      </Box>

      {/*
        The closing line is a real link when `App` wires `onNavigateToSearch`
        (it does), through the same screen switch the nav uses, so nothing
        reloads and the in-memory access token survives. Standalone, with no
        callback, the sentence names the tab instead.
      */}
      <Typography sx={{ color: designTokens.inkMuted, maxWidth: "66ch", mb: 5 }}>
        Follow the same question live:{" "}
        {onNavigateToSearch ? (
          <Box
            component="button"
            type="button"
            onClick={onNavigateToSearch}
            sx={{
              font: "inherit",
              p: 0,
              border: 0,
              bgcolor: "transparent",
              color: designTokens.link,
              cursor: "pointer",
              textDecoration: "underline",
            }}
          >
            open Search
          </Box>
        ) : (
          "open Search in the bar above"
        )}{" "}
        and ask "{JOURNEY_QUESTION}".
      </Typography>

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

      {/*
        THE STRIP, product-owner request of 2026-09-13. The walk above says
        which layer a fact came from; it never says where the graph itself
        came from, how big it is, or how old. Four lines here, and the page
        that answers it properly is `/architecture`.

        DELIBERATELY AT THE FOOT rather than above the walk. The walk is this
        page's subject and the product owner asked for it by name; putting a
        counts-and-dates block in front of it would have been the "convolutes
        the about page" outcome the same request warned against. Every figure
        is read from `lib/architectureFacts.ts`, the module the Architecture
        page itself renders from, so the two pages cannot state different
        numbers.
      */}
      <Typography variant="h2" component="h2" sx={{ mt: 5, mb: 1.5 }}>
        Where the data comes from
      </Typography>
      <Box
        component="ul"
        data-testid="about-data-strip"
        sx={{
          listStyle: "none",
          m: 0,
          mb: 2,
          p: 0,
          display: "grid",
          gap: 0.75,
          maxWidth: "66ch",
        }}
      >
        {[
          `The knowledge graph is a snapshot, finished on ${SNAPSHOT_DATE}.`,
          `It is built from five NCBI databases: ${SOURCE_DATABASE_NAMES.slice(0, -1).join(", ")} and ${SOURCE_DATABASE_NAMES[SOURCE_DATABASE_NAMES.length - 1]}.`,
          `It holds ${NODE_COUNT} nodes and ${EDGE_COUNT} edges.`,
          "Layers 2 and 3 are stored nowhere. They are called live while you wait, so what they return is current.",
        ].map((line) => (
          <Typography
            key={line}
            component="li"
            variant="body2"
            sx={{
              color: designTokens.inkMuted,
              borderLeft: `4px solid ${designTokens.layer1}`,
              pl: 1.5,
            }}
          >
            {line}
          </Typography>
        ))}
      </Box>
      <Typography sx={{ color: designTokens.inkMuted, maxWidth: "66ch" }}>
        {onNavigateToArchitecture ? (
          <Box
            component="button"
            type="button"
            onClick={onNavigateToArchitecture}
            sx={{
              font: "inherit",
              p: 0,
              border: 0,
              bgcolor: "transparent",
              color: designTokens.link,
              cursor: "pointer",
              textDecoration: "underline",
            }}
          >
            Explore the architecture
          </Box>
        ) : (
          "The Architecture page, at /architecture, is there"
        )}{" "}
        for the pipelines behind that snapshot, what each database contributes, and every API the
        two live layers call.
      </Typography>
    </Page>
  );
}
