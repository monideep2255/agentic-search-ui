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
 */

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

function Card({ title, body, code }: { title: string; body: string; code?: string }) {
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
          sx={{
            ...mono,
            fontSize: 11.5,
            m: 0,
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
    </Box>
  );
}

const GRID = {
  display: "grid",
  gap: 2,
  gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
} as const;

export function IntegrationsScreen() {
  return (
    <Page
      title="Integrations"
      lede="The same agent, reachable four ways. Every surface runs the identical loop and returns the identical citations."
    >
      <Box sx={GRID}>
        <Card
          title="REST and SSE"
          body="Start a run, then subscribe to its event stream and render it as it happens, exactly as this interface does. Resumable after a dropped connection."
          code={"POST /v1/query\nGET  /v1/query/{run_id}/events\nGET  /v1/query/{run_id}/citations"}
        />
        <Card
          title="MCP server"
          body="One advertised tool, ask_biomedical_question. It folds a whole run into a single cited answer; the seven internal tools are never separately reachable."
          code={'{"mcpServers":{"ncbi-search":{\n  "url":"https://.../mcp"}}}'}
        />
        <Card
          title="KGX export"
          body="Nodes and edges in BioLink-compliant KGX, for loading into your own graph. Prepared as a batch job rather than served live."
          code={"POST /v1/export/kgx"}
        />
        <Card
          title="Command line"
          body="The same answer, piped. Reads your NCBI API key from the environment."
          code={'export NCBI_API_KEY=your-ncbi-api-key\nncbi-search ask "diseases linked to BRCA1"'}
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
