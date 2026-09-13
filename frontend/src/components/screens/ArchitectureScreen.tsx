/**
 * The Architecture page, `/architecture`. Product-owner request of
 * 2026-09-13: "Data retrieval from data engineering repo, April 22 snapshot,
 * add this metric for the system 1, list out the names of databases as the
 * core of information being pulled from like the 115M etc, then the system 2
 * and 3, Databases in kg, pull from api layer 2 and 3."
 *
 * WHY A PAGE OF ITS OWN rather than more About. The same request offered the
 * choice and named the condition: "if it convolutes the about page too much,
 * can create another page /architecture to show the deep architecture on how
 * information is being pulled". About follows ONE question through the
 * running system, seven stops, and stays answerable by a visitor who has
 * never heard of a knowledge graph. This page answers a different question,
 * where the data itself comes from, and it names databases, node counts,
 * labels, hosts and per-call budgets. Folding it into the walk would have
 * broken the walk. About therefore keeps its seven stops and gains one short
 * strip that links here.
 *
 * THE DESIGN GAP, named rather than filled silently, as
 * `.claude/rules/design-consistency.md` requires.
 * `docs/build/design/design-system/README.md`'s coverage table ends its
 * "Designed" column with "Integrations, docs and about | NO | Only ever
 * inside `prototype/app.html`". There is no architecture card either, in
 * `components/`, `screens/`, `identity/` or `flows/`, and the prototype has
 * no such screen. So this surface has NO design.
 *
 * WHAT IT IS BUILT FROM INSTEAD, the nearest designed neighbour: the About
 * page. Every primitive on this page is imported from `InfoScreens.tsx`
 * rather than reimplemented, so the two pages cannot drift: `Page` for the
 * frame, title and lede, `JourneyStop` for the numbered spine, `StopText`
 * for body prose, `StopLabel` for the eyebrow captions, and `mono` for the
 * transcribed-string typeface. The layer cards copy the About walk's own
 * layer card, including its measured decision to read the `L1` / `L2` / `L3`
 * mark in ink on a wash ground rather than in the layer colour, which axe put
 * at 4.01:1 against WCAG 1.4.3's 4.5:1. Every colour comes from
 * `designTokens` or from `layerColour()`; there is no hex literal below.
 *
 * WHERE THE FACTS LIVE. Every figure, database name, host and budget this
 * page renders comes from `lib/architectureFacts.ts`, which the About page's
 * own strip reads too, so the two surfaces cannot disagree about the size of
 * the graph. That module carries the per-value source pointers; the summary
 * below is the same list, so a reviewer can start here.
 *
 * EVERY NUMBER AND NAME HERE WAS READ OUT OF A DOCUMENT, not recalled.
 * The sources, so a reviewer checks rather than trusts:
 *
 * System 1 and 2, from the data-engineering repository, read-only at
 * `reference/agentic-search-data-engineering/`:
 *
 *   - 115,406,761 nodes, 693,295,991 edges, 11 vertex labels, 14 edge
 *     labels, the five source databases and the 2026-04-22 date:
 *     `CLAUDE.md`'s Current focus table, and `docs/
 *     Knowledge_graph_on_server_reference.md` Section A.
 *   - The per-database node counts: the same document's Section D, "Vertex
 *     labels and counts". They are the LOADED counts, which is why Disease
 *     reads 200,845 rather than MedGen's ~233K source concepts: the page
 *     states what is in the graph, from one table, rather than mixing
 *     source-record counts with graph counts.
 *   - The five pipeline steps: the same repository's `CLAUDE.md`, "Pipeline
 *     pattern (every ETL follows this)".
 *   - PostgreSQL 15.17, Apache AGE 1.5.0, Hetzner CPX42, the `ncbi_kg`
 *     graph: `Knowledge_graph_on_server_reference.md` Section B.
 *   - The indexes and the 4m17s to 229ms edge-label figure: the same
 *     document's Sections I and H.
 *
 * System 3, from this repository:
 *
 *   - Every per-call budget and every API host: `visualizations/
 *     Architecture_diagram.md`'s tool table, each value of which is in the
 *     tool code. `CYPHER_QUERY_TIMEOUT_SECONDS = 90.0` and
 *     `MAX_ROW_LIMIT = 500` are in `tools/graph_schema_constants.py`;
 *     `DEFAULT_TIMEOUT_S = 15.0` is in `tools/ncbi_transport.py`;
 *     `_TOTAL_BUDGET_S = 120.0` is in `tools/pathogen_detection.py`.
 *   - The API hosts: `_EUTILS_BASE` in `tools/ncbi_eutils_actions.py`,
 *     `_DATASETS_BASE` in `tools/ncbi_datasets_actions.py`,
 *     `_VARIATION_BASE` in `tools/ncbi_dbsnp.py`, and the PubTator3, LitVar2
 *     and ClinicalTrials.gov constants in their own tool modules.
 *
 * ONE DIVERGENCE IS DELIBERATE AND IS STATED HERE rather than quietly
 * resolved. About's walk lists `pathogen_detection` under Layer 3. This page
 * lists it under Layer 2, following `visualizations/Architecture_diagram.md`,
 * which classifies it as Layer 2 "because it is an NCBI-native bulk source,
 * not one of the four enrichment APIs" and is the repository's source of
 * truth for the tool-to-layer mapping. About was left unchanged because this
 * work is scoped not to restructure it; the disagreement is reported rather
 * than papered over.
 *
 * THE GRAPH BUDGET IS 90 SECONDS, NOT 30. Technical specification Section 6.1
 * says 30 and the code says 90, deliberately: the plan-tier call that writes
 * the Cypher was measured at a mean of 25 seconds before the graph is touched
 * at all, so 30 could not complete. `tools/graph_schema_constants.py` carries
 * the measurement and files the spec text as a Step 6.2 reconciliation item.
 * The page states what the code enforces, since that is what a reader
 * actually experiences.
 */

import { Box, Typography } from "@mui/material";

import {
  EXAMPLE_CYPHER,
  LAYERS,
  PIPELINE_STEPS,
  SNAPSHOT_DATE,
  SNAPSHOT_FIGURES,
  SOURCE_DATABASES,
} from "../../lib/architectureFacts";
import { designTokens, layerColour } from "../../theme";
import { JourneyStop, Page, StopLabel, StopText, mono } from "./InfoScreens";

// ---------------------------------------------------------------------------

/** A small figure with its caption under it, used for the snapshot headline
 *  and nowhere else. */
function Figure({ value, label }: { value: string; label: string }) {
  return (
    <Box
      sx={{
        bgcolor: designTokens.surface,
        border: `1px solid ${designTokens.line}`,
        borderRadius: 0.5,
        px: 1.75,
        py: 1.25,
        minWidth: 0,
      }}
    >
      <Box component="p" sx={{ ...mono, fontSize: 17, fontWeight: 700, m: 0, wordBreak: "break-word" }}>
        {value}
      </Box>
      <Typography variant="body2" sx={{ color: designTokens.inkMuted }}>
        {label}
      </Typography>
    </Box>
  );
}

export interface ArchitectureScreenProps {
  /**
   * Takes the reader to About, wired by `App`, so the closing line is a real
   * link through the same screen switch the nav uses rather than a sentence
   * naming a tab. Optional, so the screen still renders standalone.
   */
  onNavigateToAbout?: () => void;
}

export function ArchitectureScreen({ onNavigateToAbout }: ArchitectureScreenProps = {}) {
  return (
    <Page
      title="Architecture"
      lede="Three systems stand behind every answer: the pipelines that build the knowledge graph, the graph itself, and the search agent that reads it alongside live NCBI APIs. This page names what each one holds and where it is pulled from."
    >
      <Box
        component="ol"
        role="list"
        data-testid="architecture-systems"
        sx={{ listStyle: "none", m: 0, mb: 5, p: 0 }}
      >
        <JourneyStop index={1} title="System 1, the data pipelines">
          <StopText>
            Five NCBI databases are downloaded in full from NCBI's FTP servers, parsed, mapped to
            the BioLink 4.x model, validated against that schema, and written out as KGX files.
            Every row keeps the source it came from and a link back to its NCBI record, which is
            what lets a finished answer cite one.
          </StopText>

          <StopLabel>The pipeline, the same five steps for every database</StopLabel>
          <Box
            data-testid="architecture-pipeline"
            sx={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              gap: 1,
              mt: 0.75,
              mb: 2.5,
              maxWidth: 620,
            }}
          >
            {PIPELINE_STEPS.map((step, index) => (
              <Box key={step} sx={{ display: "flex", alignItems: "center", gap: 1, minWidth: 0 }}>
                <Box
                  sx={{
                    bgcolor: designTokens.surface,
                    border: `1px solid ${designTokens.line}`,
                    borderLeft: `4px solid ${designTokens.blue}`,
                    borderRadius: 0.5,
                    px: 1.25,
                    py: 0.75,
                    fontSize: 13.5,
                    fontWeight: 600,
                  }}
                >
                  {step}
                </Box>
                {index === PIPELINE_STEPS.length - 1 ? null : (
                  <Box
                    aria-hidden="true"
                    sx={{ color: designTokens.inkFaint, fontSize: 13.5, flex: "none" }}
                  >
                    &rarr;
                  </Box>
                )}
              </Box>
            ))}
          </Box>

          <StopText>
            What this app queries is not a live feed of those databases. It is the snapshot that run
            finished on {SNAPSHOT_DATE}, and every graph fact in an answer is as current as that
            date. Anything that has to be newer comes from layer 2 instead.
          </StopText>

          <StopLabel>The {SNAPSHOT_DATE} snapshot</StopLabel>
          <Box
            data-testid="architecture-snapshot"
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "repeat(2, minmax(0, 1fr))", sm: "repeat(4, minmax(0, 1fr))" },
              gap: 1.25,
              mt: 0.75,
              mb: 2.5,
              maxWidth: 620,
            }}
          >
            {SNAPSHOT_FIGURES.map((figure) => (
              <Figure key={figure.label} value={figure.value} label={figure.label} />
            ))}
          </Box>

          <StopLabel>The five source databases, and what each contributes</StopLabel>
          <Box
            data-testid="architecture-sources"
            sx={{
              display: "grid",
              gap: 1.25,
              mt: 0.75,
              mb: 1.5,
              maxWidth: 620,
            }}
          >
            {SOURCE_DATABASES.map((db) => (
              <Box
                key={db.source}
                data-testid={`architecture-source-${db.label}`}
                sx={{
                  bgcolor: designTokens.surface,
                  border: `1px solid ${designTokens.line}`,
                  borderLeft: `4px solid ${designTokens.layer1}`,
                  borderRadius: 0.5,
                  px: 1.75,
                  py: 1.25,
                }}
              >
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "baseline",
                    gap: 1.25,
                    flexWrap: "wrap",
                    mb: 0.25,
                  }}
                >
                  <Typography variant="h4" component="p">
                    {db.source}
                  </Typography>
                  <Box
                    component="span"
                    sx={{ ...mono, ml: "auto", fontSize: 12.5, fontWeight: 700 }}
                  >
                    {db.nodes} nodes
                  </Box>
                </Box>
                <Box
                  component="p"
                  sx={{ ...mono, fontSize: 11.5, color: designTokens.inkFaint, m: 0 }}
                >
                  {db.label} · {db.curie}
                </Box>
              </Box>
            ))}
          </Box>
          <StopText>
            The counts above are what is loaded in the graph, which is why they do not always match
            a database's own published record count. Roughly 78,000 further nodes sit under six
            smaller labels: Gene Ontology terms, MeSH headings and phenotypes that arrive with the
            five databases above, plus a small number of stub records the merge left behind where
            an edge pointed at something no pipeline had produced.
          </StopText>
        </JourneyStop>

        <JourneyStop index={2} title="System 2, the knowledge graph">
          <StopText>
            Those KGX files are merged and loaded into one graph, named ncbi_kg, running on
            PostgreSQL 15 with the Apache AGE extension on a single Hetzner server. This app reads
            it through a read-only credential, so nothing a question does can change it, and
            nothing else writes to it either.
          </StopText>

          <StopText>
            A query names a starting node by its identifier and the labelled edge to follow, then
            returns whatever sits on the other end. That is the whole shape of it.
          </StopText>
          {/*
            `tabIndex`, `role` and `aria-label` are NOT decoration here, and
            they were not written from principle either: axe failed this page
            on `scrollable-region-focusable` (WCAG 2.1.1 and 2.1.3, serious)
            the first time `e2e/accessibility.spec.ts` visited it. A `<pre>`
            holding a line of Cypher cannot wrap, so it carries its own
            horizontal scroller, and a scroller a keyboard cannot reach hides
            the second half of the line from anyone not using a mouse. Making
            it focusable is the fix; the role and the label are what stop a
            screen reader announcing the stop as an unnamed one.
          */}
          <Box
            data-testid="architecture-cypher"
            component="pre"
            tabIndex={0}
            role="region"
            aria-label="Example graph query"
            sx={{
              ...mono,
              bgcolor: designTokens.surfaceSunk,
              border: `1px solid ${designTokens.line}`,
              borderRadius: 0.5,
              px: 1.75,
              py: 1.25,
              mt: 0,
              mb: 2,
              maxWidth: 620,
              overflowX: "auto",
              fontSize: 12.5,
              lineHeight: 1.7,
              whiteSpace: "pre",
            }}
          >
            {EXAMPLE_CYPHER}
          </Box>

          <StopText>
            Two things make that fast on a graph this size. Every node identifier is indexed, so
            finding the starting point is a lookup rather than a scan of 67 million rows, and both
            ends of every edge are indexed too, so following one is a lookup as well. Naming the
            edge label is the other half: the first version of this exact query took 4 minutes and
            17 seconds without it, and 229 milliseconds with it.
          </StopText>

          <StopText>
            The search agent gives one graph query 90 seconds and accepts at most 500 rows back. A
            query that would exceed either says so rather than leaving you waiting.
          </StopText>
        </JourneyStop>

        <JourneyStop index={3} last title="System 3, the search agent">
          <StopText>
            This is the part you use. It reads the graph above as its first layer, and reaches two
            further layers live while you wait. Seven tools cover the three, each one reaching
            exactly one layer and one access path within it, and each carrying its own time limit
            in code rather than one the model chooses.
          </StopText>

          <Box data-testid="architecture-layers" sx={{ display: "grid", gap: 1.75, maxWidth: 620 }}>
            {LAYERS.map((layer) => {
              const { main, wash } = layerColour(layer.n);
              return (
                <Box
                  key={layer.n}
                  data-testid={`architecture-layer-${layer.n}`}
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
                      The mark reads in ink rather than in the layer colour,
                      copying the About walk's own measured decision for the
                      identical card: axe put `layer2` on `layer2Wash` at
                      4.01:1 for an 11px bold mark, against WCAG 1.4.3's
                      4.5:1. The colour is carried by the left border and the
                      wash instead.
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
                  <Typography variant="body2" sx={{ color: designTokens.inkMuted, mb: 1 }}>
                    {layer.summary}
                  </Typography>
                  <Box sx={{ display: "grid", gap: 0.75 }}>
                    {layer.tools.map((tool) => (
                      <Box
                        key={tool.name}
                        sx={{
                          bgcolor: designTokens.surface,
                          border: `1px solid ${designTokens.line}`,
                          borderRadius: 0.5,
                          px: 1.25,
                          py: 0.75,
                        }}
                      >
                        <Box
                          component="p"
                          sx={{ ...mono, fontSize: 12.5, fontWeight: 700, m: 0 }}
                        >
                          {tool.name}
                        </Box>
                        <Typography variant="body2" sx={{ color: designTokens.inkMuted }}>
                          Calls {tool.calls}.
                        </Typography>
                        <Box
                          component="p"
                          sx={{ ...mono, fontSize: 11.5, color: designTokens.inkFaint, m: 0 }}
                        >
                          {tool.budget}
                        </Box>
                      </Box>
                    ))}
                  </Box>
                </Box>
              );
            })}
          </Box>

          <Box sx={{ mt: 2.5 }}>
            <StopText>
              Whichever layer a fact came from, it arrives with a link to the record behind it. A
              graph row carries the source URL that was stored on the node or edge when the
              pipeline wrote it, so it opens the NCBI record the pipeline read. A live result links
              to the record page for the identifier it just came back with, such as the NCBI Gene
              page for gene 672. A claim with no such link is not cited, and an answer with nothing
              citeable behind it is refused rather than written.
            </StopText>
          </Box>
        </JourneyStop>
      </Box>

      <Typography sx={{ color: designTokens.inkMuted, maxWidth: "66ch" }}>
        To see one question travel through all three,{" "}
        {onNavigateToAbout ? (
          <Box
            component="button"
            type="button"
            onClick={onNavigateToAbout}
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
            open About
          </Box>
        ) : (
          "open About in the bar above"
        )}
        , which follows a single BRCA1 question from the moment you press send.
      </Typography>
    </Page>
  );
}

export default ArchitectureScreen;
