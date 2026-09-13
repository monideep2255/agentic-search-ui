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

import { designTokens } from "../../theme";

const mono = { fontFamily: "ui-monospace, monospace" } as const;

function Page({ title, lede, children }: { title: string; lede: string; children?: React.ReactNode }) {
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

export const MCP_CONFIG = `{
  "mcpServers": {
    "ncbi-search": {
      "url": "${API_ORIGIN}/mcp"
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
          body="A run emits ten kinds of event: guard, think, plan, tool_start, tool_result, token, citation, trust_signal, error and done. Each SSE frame carries the sequence number as its id, the event type as its name, and the whole envelope as its data. A refusal is a normal outcome with a reason attached, not an error."
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
