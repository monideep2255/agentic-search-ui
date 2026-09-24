/**
 * The answer screen, build phase 4.8, ticket T-4.8-06.
 *
 * Three things here carry the product's trust argument, and none of them is
 * decoration:
 *
 *   The provenance spine. One segment per claim, coloured by the layer that
 *   backed it, borrowed from genome browser tracks so the form is native to
 *   the audience. A grey segment means an uncited claim, visible before a word
 *   is read. Kept always rendered rather than only on a problem, settled
 *   2026-08-12: a track that appears solely when something is wrong is one
 *   nobody has learned to read at the moment it matters most.
 *
 *   The citation chip. Layer colour on the left edge, so a reader learns where
 *   a fact came from, and therefore how fresh it is and how it was
 *   established, without reading the source list.
 *
 *   The source card. Every provenance field Section 9.1 requires, including
 *   the licence. Dropping a field because it is fiddly is the defect the
 *   premise gate asserts against.
 *
 * Source of truth: `docs/build/design/design-system/screens/answer.html`,
 * `identity/provenance-spine.html`, `identity/citation-chip.html`,
 * `components/source-card.html`.
 */

import type React from "react";
import { Fragment, useEffect, useRef, useState } from "react";
import { Box, Typography, useMediaQuery } from "@mui/material";

import { designTokens, layerColour } from "../../theme";
import type { ReasoningStep } from "./RunProgress";
import { ReasoningLog } from "./ReasoningLog";
import { FeedbackSurface } from "../feedback/FeedbackSurface";
import { PersonaInfo, WritingEllipsis } from "../shell/PersonaChip";
import {
  CitationMarkers,
  LAYER_WORD,
  isLinkableCitationUrl,
} from "../answer/CitationMarkers";

export type Layer = 1 | 2 | 3;

export interface Claim {
  text: string;
  /** null means uncited: the spine must show the gap. */
  layer: Layer | null;
  /**
   * Every citation this claim declared, by display index.
   *
   * An array rather than a single number because a sentence can legitimately
   * cite more than one source, and the previous single-value shape silently
   * dropped the rest (F-4.8-J-14, made routine by F-4.8-A-04).
   */
  citations: number[];
  /*
   * UI fix set 9. All optional, all read from the token's typed `kind` on the
   * wire, so a claim from an older producer renders exactly as before.
   *
   * `kind`: a prose sentence, or a code-built list item or table row.
   * `paragraph`: which paragraph the sentence belongs to; present means the
   *   answer is structured and renders as paragraphs rather than one row per
   *   sentence.
   * `heading`, `noteBefore`: a heading or a system note that stands directly
   *   before this claim.
   * `cells`: the display values of a list item (one) or table row (two).
   * `emphasis`: substrings of `text` to bold, chosen in code by the backend.
   * `tableHeader`: the column labels, on the first row of a table.
   */
  /**
   * 2026-09-14. Citations this sentence declared whose frames have not arrived
   * yet, set by `useRunView` only while the run is still streaming. A claim
   * carrying it is NOT uncited: its spine segment reads `pending` and it shows
   * quiet pending markers instead of "This sentence has no source."
   */
  pendingCitations?: number;
  kind?: "claim" | "list_item" | "table_row";
  paragraph?: number;
  heading?: string;
  noteBefore?: string;
  cells?: string[];
  emphasis?: string[];
  tableHeader?: string[];
  /** 2026-09-14: a record line after the findings-tail note, set by `useRunView`. */
  findingsTail?: boolean;
}

/** What the trust line's info card says (item 9.9). */
export const TRUST_LINE_EXPLAINER =
  "Sources are counted by the database each record comes from, so twenty records from one " +
  "database are one source. Confirmed means two independent databases agree on the same " +
  "high-stakes fact. Not yet confirmed means a high-stakes fact rests on a single source.";

/*
 * UI fix 11.27, product owner 2026-09-14: "There is too much bold. Only the
 * title or main point should be bold. right now everything looks bold."
 *
 * WHERE THE BOLD CAME FROM. The backend's `emphasis` field (Researcher prose,
 * `synthesis/answer_layout.py`'s `emphasis_for`) names every resolved entity
 * mention AND every record name in a sentence, up to its cap, and this file
 * rendered each one at 700, in prose, in a table's first cell and in a
 * stacked row's name. A disease list therefore read as a wall of bold.
 *
 * NOW: the question heading stays bold, and ONE term in the lead summary is
 * bold, its main point. Every other emphasised term renders at regular weight,
 * with its words unchanged. `emphasis` is still read (it is what says which
 * words the backend considers key), it just no longer paints every one.
 */

/**
 * The lead summary's main point: which claim, and which term in it, is bold.
 *
 * The lead is the first prose claim (not a table row, list item or record
 * line). Its main point is one of the backend's own `emphasis` terms, never a
 * word this screen picks: preferably a term the QUESTION names (the subject
 * asked about), otherwise the term that comes first in the sentence. Null when
 * the lead carries no emphasis, which is every Plain language answer from
 * today's backend, so such an answer bolds its title alone.
 */
export function mainPointFor(
  claims: Claim[],
  question?: string | null,
): { index: number; term: string } | null {
  const index = claims.findIndex(
    (claim) => claim.kind !== "list_item" && claim.kind !== "table_row" && parseRecordLine(claim.text) === null,
  );
  if (index < 0) return null;
  const claim = claims[index]!;
  const terms = (claim.emphasis ?? []).filter((term) => term.length > 0 && claim.text.includes(term));
  if (terms.length === 0) return null;
  const asked = (question ?? "").toLowerCase();
  const named = terms.filter((term) => asked.includes(term.toLowerCase()));
  const pool = named.length > 0 ? named : terms;
  const [term] = [...pool].sort(
    (a, b) => claim.text.indexOf(a) - claim.text.indexOf(b) || b.length - a.length,
  );
  return { index, term: term! };
}

/** Bold one term, its first occurrence only; everything else stays regular. */
function withMainPoint(text: string, term: string | undefined, testId: string): React.ReactNode {
  if (!term) return text;
  const at = text.indexOf(term);
  if (at < 0) return text;
  return (
    <>
      {text.slice(0, at)}
      <Box component="strong" data-testid={testId} sx={{ fontWeight: 700 }}>
        {term}
      </Box>
      {text.slice(at + term.length)}
    </>
  );
}

/*
 * 2026-09-14, THE APPROVED ANSWER LAYOUT (`design/Main.dc.html`,
 * `Researcher.dc.html`, `Mobile.dc.html`, `Streaming.dc.html`).
 *
 * Prose paragraphs, a small-caps section heading, record tables (stacked rows
 * on a phone), a muted Notes list, the medical-advice line, then Sources and
 * the trust line. No provenance spine beside each sentence: the citation
 * marker's layer colour carries the layer. Every value below is the
 * prototype's own rule, named where it is used:
 *   `.answer p`   16.5px, line-height 1.68, 66ch, 18px below; 16px and 1.65 on a phone
 *   `.answer .ah` 11.5px, .13em, uppercase, 700, `inkFaint`, 32px above and 14px
 *                 below (28px and 10px on a phone), 7px and a `line` rule under it
 *   `.rtab`       13.5px, `line` border, `surface` ground; cells 8px 11px;
 *                 header 10.5px .1em uppercase `inkFaint` on `surfaceSunk`;
 *                 an identifier cell `.g` mono 12.5px nowrap `inkMuted`
 *   stacked row   15px/1.45 `ink` name, 12.5px mono `inkMuted` identifier, 10px
 *                 padding and a `line` rule (the mockup's `.row`, `.rn`, `.rm`;
 *                 15px is the prototype's `.fu-bar input` size)
 *   Notes list    14.5px/1.6 `inkMuted`, 20px indent, 6px between items (14px and
 *                 18px on a phone; the prototype's `.nolist li` and `.conflict`)
 *   medical line  13.5px `inkMuted` (theme `body2`)
 */

/** The prototype's phone breakpoint (`@media (max-width:720px)`). */
export const PHONE_LAYOUT_QUERY = "(max-width:720px)";

/** A sentence, row or heading rising into place while the answer is written. */
const RISE = {
  "@keyframes s3-answer-rise": {
    from: { opacity: 0, transform: "translateY(4px)" },
    to: { opacity: 1, transform: "none" },
  },
  animation: "s3-answer-rise .45s ease-out both",
  "@media (prefers-reduced-motion: reduce)": { animation: "none" },
} as const;

const AH_BASE = {
  fontSize: 11.5,
  letterSpacing: "0.13em",
  textTransform: "uppercase",
  fontWeight: 700,
  color: designTokens.inkFaint,
  m: "32px 0 14px",
  pb: "7px",
  borderBottom: `1px solid ${designTokens.line}`,
  "@media (max-width:720px)": { m: "28px 0 10px" },
} as const;
const AH_SX = { ...AH_BASE, "&:first-child": { mt: 0 } } as const;

const PROSE_SX = {
  m: "0 0 18px",
  fontSize: 16.5,
  lineHeight: 1.68,
  maxWidth: "66ch",
  color: designTokens.ink,
  textWrap: "pretty",
  "&:last-child": { mb: 0 },
  "@media (max-width:860px)": { maxWidth: "none" },
  "@media (max-width:720px)": { fontSize: 16, lineHeight: 1.65, mb: "16px" },
} as const;

const RTAB_CELL = {
  textAlign: "left",
  p: "8px 11px",
  borderBottom: `1px solid ${designTokens.line}`,
  verticalAlign: "top",
} as const;
const RTAB_HEAD = {
  ...RTAB_CELL,
  fontSize: 10.5,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  color: designTokens.inkFaint,
  bgcolor: designTokens.surfaceSunk,
  fontWeight: 700,
} as const;
const RTAB_ID = {
  fontFamily: "ui-monospace, monospace",
  fontSize: 12.5,
  whiteSpace: "nowrap",
  color: designTokens.inkMuted,
} as const;

/**
 * The record-line labels the answer recognises, deterministically.
 *
 * `synthesis/findings.py`'s `render_finding_body` writes a code-built record
 * line as "{entity type} {field}: {value}", and the findings tail is made of
 * them. A label is recognised only as one of these entity types followed by
 * one of these fields, then ": ", compared without regard to case.
 */
export const RECORD_LINE_ENTITY_TYPES = [
  "Disease",
  "Gene",
  "Clinical trial",
  "Literature entity",
  "Sequence variant",
  "SequenceVariant",
  "Chemical entity",
  "Protein",
] as const;
export const RECORD_LINE_FIELDS = ["name", "symbol", "title", "preferred name", "preferred_name"] as const;

const RECORD_LINE_PATTERN = new RegExp(
  `^((?:${RECORD_LINE_ENTITY_TYPES.join("|")}) (?:${RECORD_LINE_FIELDS.join("|")})): (\\S[\\s\\S]*)$`,
  "i",
);

/**
 * Split a record line into its label and value, or null.
 *
 * The value is the claim text with the label prefix removed and nothing else
 * changed, so a row never words a record differently from its sentence.
 */
export function parseRecordLine(text: string): { label: string; value: string } | null {
  const match = RECORD_LINE_PATTERN.exec(text);
  if (!match) return null;
  return { label: match[1]!, value: match[2]! };
}

/** An accession or concept id, set in mono: "C0346153", "NCT00590109", "rs80357906", "MedGen:C1". */
export function isIdentifierCell(cell: string): boolean {
  return /^(?:[A-Za-z][\w.-]*:\S+|[A-Z]{1,4}\d{6,}|NCT\d{8}|rs\d+)$/.test(cell.trim());
}

/*
 * Item 12.9 (2026-09-23): the Researcher table's identifier column, labelled
 * by the backend (`synthesis/answer_layout.py`'s `IDENTIFIER_COLUMN_LABEL`).
 * Every cell under it is the design system's identifier cell, the
 * prototype's `.rtab td.g` (`RTAB_ID` above), whatever the value's shape, so
 * a PubTator id ("@GENE_BRCA1") or a live record's "omim 138079" sits in the
 * same mono as a CURIE beside it rather than in body type. `isIdentifierCell`
 * still decides every other column, unchanged.
 */
export const IDENTIFIER_COLUMN_LABEL = "Identifier";

/** Where a record table's identifier column is, or -1 when it has none. */
export function identifierColumn(header: string[] | null): number {
  return header ? header.indexOf(IDENTIFIER_COLUMN_LABEL) : -1;
}

/** The Plain language closing line, shown on its own rather than as a note. */
export const MEDICAL_NOTE_PREFIX = "This is a research summary, not medical advice";

export interface RecordRow {
  claim: Claim;
  index: number;
  cells: string[];
}

export type AnswerBlock =
  | { type: "heading"; text: string; key: string }
  | { type: "note"; text: string; key: string }
  | { type: "prose"; key: string; paragraph: number | undefined; items: { claim: Claim; index: number }[] }
  | {
      type: "records";
      key: string;
      source: "table_row" | "list_item" | "record_line";
      label: string | null;
      header: string[] | null;
      rows: RecordRow[];
    };

/**
 * Group an answer's claims into blocks. Pure, exported for its tests.
 *
 * RECORDS NEVER RENDER INLINE (product-owner defect, 2026-09-14: "Disease
 * name: X.1 Disease name: Y.2 gene symbol: ..."). Three shapes become a
 * record block rather than prose:
 *   - consecutive `table_row` claims, one table, with their header;
 *   - consecutive `list_item` claims, one table;
 *   - record lines ("Disease name: X") that follow the findings-tail note, or
 *     that stand next to another record line in the same paragraph, grouped
 *     by label, with the label as the block's heading.
 * Everything else is prose, one paragraph per `paragraph` number, or one
 * paragraph per sentence for a producer that sends none.
 */
export function buildAnswerBlocks(claims: Claim[]): AnswerBlock[] {
  const blocks: AnswerBlock[] = [];
  const labels = claims.map((claim) =>
    claim.kind === "list_item" || claim.kind === "table_row" ? null : parseRecordLine(claim.text),
  );
  const adjacentRecordLine = (index: number, other: number) => {
    if (other < 0 || other >= claims.length || labels[other] === null) return false;
    const later = Math.max(index, other);
    if (claims[later]!.heading || claims[later]!.noteBefore) return false;
    return claims[other]!.paragraph === claims[index]!.paragraph;
  };
  claims.forEach((claim, index) => {
    if (claim.noteBefore) blocks.push({ type: "note", text: claim.noteBefore, key: `note-${index}` });
    if (claim.heading) blocks.push({ type: "heading", text: claim.heading, key: `heading-${index}` });
    const last = blocks[blocks.length - 1];
    if (claim.kind === "table_row" || claim.kind === "list_item") {
      const cells =
        claim.kind === "table_row"
          ? claim.cells && claim.cells.length > 0
            ? claim.cells
            : [claim.text]
          : [claim.cells?.[0] ?? claim.text];
      const row = { claim, index, cells };
      if (last && last.type === "records" && last.source === claim.kind && !claim.tableHeader) {
        last.rows.push(row);
      } else {
        blocks.push({
          type: "records",
          key: `records-${index}`,
          source: claim.kind,
          label: null,
          header: claim.kind === "table_row" ? (claim.tableHeader ?? null) : null,
          rows: [row],
        });
      }
      return;
    }
    const parsed = labels[index];
    if (
      parsed &&
      (claim.findingsTail || adjacentRecordLine(index, index - 1) || adjacentRecordLine(index, index + 1))
    ) {
      const row = { claim, index, cells: [parsed.value] };
      if (last && last.type === "records" && last.source === "record_line" && last.label === parsed.label) {
        last.rows.push(row);
      } else {
        blocks.push({
          type: "records",
          key: `records-${index}`,
          source: "record_line",
          label: parsed.label,
          header: null,
          rows: [row],
        });
      }
      return;
    }
    if (
      last &&
      last.type === "prose" &&
      claim.paragraph !== undefined &&
      last.paragraph === claim.paragraph
    ) {
      last.items.push({ claim, index });
    } else {
      blocks.push({ type: "prose", key: `prose-${index}`, paragraph: claim.paragraph, items: [{ claim, index }] });
    }
  });
  return blocks;
}

export interface Source {
  n: number;
  layer: Layer;
  name: string;
  tool: string;
  evidence: string;
  confidence: string;
  license: string;
  url: string;
}

/**
 * The layer's plain-language group heading for the source list, transcribed
 * verbatim from the three `<h3>` labels in
 * `docs/build/design/design-system/identity/layer-badges.html`: "Knowledge
 * graph", "Live NCBI APIs", "Enrichment". `LAYER_WORD` in
 * `answer/CitationMarkers.tsx` names a layer inside one citation's own tag
 * ("L1 · graph"), a short internal-facing word; this names the GROUP a
 * reader sees once the source list is broken out by layer, a heading meant
 * to stand alone with no "L1" beside it, so it is a second constant rather
 * than a reuse of the first.
 */
export const LAYER_GROUP_LABEL: Record<Layer, string> = {
  1: "Knowledge graph",
  2: "Live NCBI APIs",
  3: "Enrichment",
};

/**
 * Notes the answer still CARRIES but the web UI does not SHOW.
 *
 * Product-owner decision, 2026-09-21: "the Notes section is super confusing.
 * remove it", naming these two exactly. They asked for them deleted
 * outright and that is what this does on screen.
 *
 * HIDDEN HERE RATHER THAN REMOVED IN THE BACKEND, and the reason is worth
 * keeping. Both notes are produced by `core/graph.py`, which floors
 * `trust_outcome` at `ask` in the same branch that builds them. Suppressing
 * them at the source meant rewriting five tests that guard a real property:
 * F-4.5-06 breach 2, an answer that silently reports a subset of its
 * findings while looking complete. Those tests and that floor are untouched,
 * so an incomplete answer still reaches this screen saying "not yet
 * confirmed" on its trust line, and the API, CLI and MCP surfaces still
 * carry the sentences for a programmatic caller.
 *
 * What the reader loses is the two sentences they called confusing. What
 * nobody loses is the disclosure that the answer is unconfirmed.
 *
 * Matched by pattern rather than in full because both carry a count or a
 * record type in the middle ("5 further pubmed records", "one further
 * disease record").
 */
export const HIDDEN_NOTE_PATTERNS: RegExp[] = [
  /^Note: the written summary of these records could not be verified/,
  // "Note: 5 further pubmed records were found ...", and its singular
  // "Note: one further disease record was found ...". Written as one
  // pattern because the count and the record type both vary, and a prefix
  // list got this wrong on the first attempt by matching only the singular.
  /^Note: (?:one|\d+) further /,
];

/** Whether the web UI hides this note (see `HIDDEN_NOTE_PATTERNS`). */
export const isHiddenNote = (text: string): boolean =>
  HIDDEN_NOTE_PATTERNS.some((pattern) => pattern.test(text.trimStart()));

/** One row in the grouped, deduplicated source list: `Source` plus every
 * citation marker that pointed at the same record. */
export interface MergedSource {
  /** Every citation marker this record answers for, ascending, e.g. [2, 5]. */
  ns: number[];
  layer: Layer;
  name: string;
  tool: string;
  evidence: string;
  confidence: string;
  license: string;
  url: string;
}

/**
 * Groups `sources` by layer, Knowledge graph then Live NCBI APIs then
 * Enrichment, and within each group collapses every citation that names the
 * SAME record (`source.url`) into one row carrying every marker that
 * pointed at it.
 *
 * This dedupes the SOURCE LIST only, never a table row. `AnswerScreen`'s
 * result table (`RTAB`, rendered from `claims`) is untouched by this
 * function: two table rows can legitimately cite the same record while
 * stating different facts, for instance many variants linked to one gene
 * record, and collapsing those rows would destroy information the reader
 * came for. The source list answers a different question, "where did this
 * evidence come from", so the same record answering that question twice is
 * the duplication the product owner asked removed (2026-09-20), and this
 * function only ever runs on the list that answers that question.
 *
 * A merged record's group is the layer of its FIRST citation. The same URL
 * cited from two different layers is not a modelled case in this system
 * (Section 6 gives each tool exactly one layer, so a record's layer is fixed
 * by which tool fetched it); this is a defensive default, not a real path.
 */
export function groupSourcesByLayer(
  sources: Source[],
): { layer: Layer; label: string; items: MergedSource[] }[] {
  const byUrl = new Map<string, MergedSource>();
  const order: string[] = [];
  sources.forEach((source) => {
    const existing = byUrl.get(source.url);
    if (existing) {
      existing.ns.push(source.n);
      return;
    }
    byUrl.set(source.url, {
      ns: [source.n],
      layer: source.layer,
      name: source.name,
      tool: source.tool,
      evidence: source.evidence,
      confidence: source.confidence,
      license: source.license,
      url: source.url,
    });
    order.push(source.url);
  });
  const merged = order.map((url) => byUrl.get(url) as MergedSource);
  return ([1, 2, 3] as Layer[])
    .map((layer) => ({
      layer,
      label: LAYER_GROUP_LABEL[layer],
      items: merged.filter((item) => item.layer === layer),
    }))
    .filter((group) => group.items.length > 0);
}

export interface TrustSignal {
  kind: "good" | "risk" | "plain";
  label: string;
}

/**
 * Everything an answer's BODY renders, independent of whose turn it is.
 *
 * UI fix set 7 item 7.4, the product owner on 2026-09-13: "in the folded
 * answer the sources and everything else run previously must still be
 * visible. Basically, the previous answer with all sources must be
 * retained."
 *
 * This type is what makes that statable rather than approximated. The live
 * turn and every folded turn render `AnswerBody` with a value of this
 * shape, so the two cannot drift: a field added to the live answer is
 * either carried on an archived turn as well or does not compile.
 */
export interface AnswerBodyContent {
  claims: Claim[];
  sources: Source[];
  /** The counts line the run reported, e.g. "3 tools · 5 sources". */
  meta?: string;
  /** The run's outcome word, e.g. "Answered" (F-4.8-D-05). */
  outcome?: string | null;
  /** How the outcome word should read (F-4.9-A-03). */
  outcomeTone?: "good" | "warn" | "risk" | null;
  /** Wall-clock the run reported, in ms (F-4.8-D-05). */
  elapsedMs?: number | null;
  /** The run's own account of what it did, behind `Show work` (F-4.8-D-05). */
  steps?: ReasoningStep[];
  trust?: TrustSignal[];
  /**
   * Guardrail or no-data refusal copy, when the question was turned away.
   *
   * F-4.8-J-02: a refusal arrives with a `done` event, which lands the user
   * on the answer screen immediately, so passing it only to RunScreen
   * rendered a refused question as a blank page. A refusal is a first-class
   * outcome of this product, not an error state, and it must be legible.
   */
  refusal?: string | null;
  /**
   * The refusal's short neutral label (R13, R44).
   *
   * Chosen in `useRunView` from a fixed, interpolation-free table, so no
   * cost figure can reach it. Rendered as the refusal block's first line.
   */
  refusalLabel?: string | null;
  /**
   * The refusal's NCBI fallback address (R14).
   *
   * Arrives as its own field rather than inside `refusal`, so the block can
   * render a real link instead of showing a reader an address they cannot
   * follow. Host-pinned at the point the anchor is built.
   */
  refusalLink?: string | null;
  /** Cap copy, when the run stopped early on its processing budget. */
  capMessage?: string | null;
  /** Disclosures the answer carried: truncation, unaddressed entities. */
  systemNotes?: string[];
}

/**
 * One finished turn of a conversation, kept on screen after the next
 * question replaces it (T-4.16-02).
 *
 * Carries the question asked plus the WHOLE body that turn had when it
 * landed. Nothing is recomputed when a turn is rendered from here, so a
 * previous turn always reads as what it was when it landed rather than as
 * what the current run would say.
 *
 * WHAT IS DELIBERATELY NOT CARRIED, and why:
 *
 *   `nextStep`, the offer of somewhere to go next. An offer is an ACTION,
 *   and an action archived beside a finished turn would ask this run's
 *   question from last turn's context. The offer belongs to the live turn
 *   and goes when the turn does.
 *
 *   `failure`, a fatal run error. `App.tsx` archives only a run that
 *   LANDED with an answer, so a turn reaching this type never had one.
 *
 *   The feedback surface and the follow-up field, for the same reason as
 *   the offer: both act on the answer a reader is looking at now.
 */
export interface PreviousTurn extends AnswerBodyContent {
  question: string;
  meta: string;
}

export interface AnswerScreenProps extends AnswerBodyContent {
  question: string;
  /**
   * Superseded by `runId`/`authToken` below (T-4.6-09). This screen now
   * builds `FeedbackSurface` itself, so it can give the real POST target and
   * bearer token it needs; a caller that still passes a pre-built node here
   * is not rendered. Kept in the prop type, rather than removed, only so
   * `App.tsx`'s existing call site (owned by a concurrent build-phase-4.6
   * ticket, not this one) keeps type-checking until that ticket updates it
   * to pass `runId`/`authToken` instead.
   */
  feedback?: React.ReactNode;
  /**
   * The landed run's id (`App.tsx`'s `runId`), threaded to `FeedbackSurface`
   * as its `POST /v1/query/{run_id}/feedback` target. `null` or omitted
   * before that wiring lands; `FeedbackSurface` degrades visibly rather than
   * posting to a malformed URL when this is absent.
   */
  runId?: string | null;
  /**
   * The bearer token this run's own request used (`App.tsx`'s `authToken`):
   * a real access token once signed in, a guest token before that. Threaded
   * to `FeedbackSurface` unchanged, so a guest can submit feedback the same
   * as a signed-in caller.
   */
  authToken?: string | null;
  /** Rendered under the sources. The follow-up field. */
  followUp?: React.ReactNode;
  /**
   * Earlier turns of THIS conversation, oldest first, each collapsed.
   *
   * T-4.16-02. The product owner reported "then chat does not continue" and
   * settled on 2026-08-25 that "follow up is part of the current search".
   * The prototype says the same thing in code: `askFollowUp` calls
   * `archiveCurrent()`, which moves the whole finished turn, its question,
   * meta line, spine, answer, sources and verdict, into a collapsed
   * `<details class="prev">` inside `<div class="thread">`, and only then
   * renders the new answer above it.
   *
   * Nothing built that. Every follow-up REPLACED the answer, so a reader
   * watched their previous turn disappear and the screen stopped reading as
   * a conversation at all. The dispatch always worked, which is why the
   * defect survived two rounds of looking for a failed second turn.
   *
   * No component card covers this: the follow-up appears ONLY in the
   * prototype, never in `design-system/screens/answer.html`. That gap is
   * recorded in `tracker/phase_4.16.md`; the styling below is taken from
   * the prototype's own `.prev` and `.thread` rules rather than invented.
   */
  previousTurns?: PreviousTurn[];
  /**
   * The in-flight run's progress, rendered in place of the answer body.
   *
   * UI FIX SET 7 (R22), the product owner's words: "it goes to a new page,
   * which it should not. The first answer should minimise and the chat
   * should continue on the same screen. That is one of the most important
   * things."
   *
   * Before this, a follow-up swapped the whole screen for `RunScreen`, so
   * the conversation vanished for the length of the second run and came
   * back afterwards. Now the answer screen stays mounted: the finished turn
   * collapses into `previousTurns` above, this node renders the same
   * stepper, elapsed counter and Stop control underneath the new question,
   * and the answer replaces it in place when it lands.
   *
   * A NODE rather than a set of run props, because the run's state belongs
   * to `App` and this screen has no business deriving it. `App` builds a
   * `RunProgress` with exactly the values it would have given `RunScreen`.
   *
   * While it is present, the follow-up field and the feedback surface are
   * not rendered: both act on an answer, and there is not one yet. That is
   * the same thing the full-screen run does, for the same reason.
   */
  progress?: React.ReactNode;
  /**
   * Start a fresh search.
   *
   * The run screen has always offered this; the answer screen did not, so the
   * only way back from an answer was the navigation bar. That is an
   * inconsistency a user notices at exactly the moment they are done reading.
   */
  onNewSearch?: () => void;
  /**
   * UI fix set 7 item 7.5: this run asked the reader for one more detail.
   *
   * The question itself arrives through `refusal` and `refusalLabel`, which
   * is what makes it render: a clarification IS a refusal to answer yet, and
   * dressing it as anything else would give the product a second shape for
   * "no answer this time". What this flag adds is the one behaviour a
   * refusal does not have, moving the cursor into the follow-up field, so
   * the reader answers where they are rather than hunting for the box.
   *
   * A BOOLEAN rather than the question text, because this screen must not
   * decide what a clarification looks like by matching a display string.
   * `useRunView` owns that judgement and states it here.
   */
  clarifying?: boolean;
  /**
   * 2026-09-14. The in-flight run was stopped. Only read while `progress` is
   * present: it hides the "writing" mark under a stopped follow-up's partial
   * sentences. Absent reads as not stopped, so every existing caller is
   * unchanged.
   */
  stopped?: boolean;
  /** A fatal run error, or a dispatch failure. Never rendered as silence. */
  failure?: string | null;
  /**
   * Flag a source as not supporting the claim it is attached to.
   *
   * This is the single most valuable signal a cite-or-refuse system can
   * collect: it produces a labelled pair rather than an opinion, which is what
   * the golden dataset needs. Stubbed; wired by build phase 4.6.
   */
  onFlagSource?: (n: number) => void;
  flaggedSources?: number[];
}

/** Monospace marks a string transcribed exactly. Gene symbols are excluded. */
const mono = { fontFamily: "ui-monospace, monospace" } as const;

/**
 * Hosts a citation may link to.
 *
 * F-4.8-A-24. `isCitationPayload` validates `source_url` as `typeof === "string"`
 * and nothing more, so the adversary got `https://evil.example.com/fake-ncbi-record`
 * and a `javascript:` URL rendered as the Record for a source labelled "NCBI
 * Gene". That was survivable only because nothing was clickable (A-17), and
 * making citations clickable is exactly what removes that accident of safety.
 *
 * `production-standards` requires a host-pinned check rather than a scheme
 * check, and requires it on whichever side of the stack builds the link. This
 * is that side.
 */
/*
 * The list itself moved to `answer/CitationMarkers.tsx` on 2026-09-14, so the
 * citation marker's card and the source card below read ONE allowlist rather
 * than two copies that could drift. Re-exported here so every existing import
 * of `isLinkableCitationUrl` from this module keeps working.
 */
export { isLinkableCitationUrl };

/**
 * Is this refusal's fallback address safe to turn into a link? (R14)
 *
 * SEPARATE FROM `isLinkableCitationUrl` above, and the difference is the
 * host rule rather than an oversight. A citation points at one specific
 * record on one of six known hosts, so an exact-membership list is the
 * tighter check and stays the right one there. A refusal's fallback is a
 * SEARCH address the backend composes (`synthesis/refuse.py`'s
 * `FALLBACK_BASE`), and the subdomain it is composed against is a backend
 * choice this screen does not control, so the rule pinned here is the
 * `production-standards` host regex in its own words: https, and the NCBI
 * domain or any subdomain of it.
 *
 * Anything else, a `javascript:` scheme, a lookalike domain, plain http,
 * or a string that is not a URL at all, is NOT linked. The address is
 * still shown, as text, because hiding it would lose the one thing the
 * refusal was trying to hand the reader.
 */
export function isLinkableRefusalLink(raw: string): boolean {
  try {
    const parsed = new URL(raw);
    if (parsed.protocol !== "https:") return false;
    return (
      parsed.hostname === "ncbi.nlm.nih.gov" || parsed.hostname.endsWith(".ncbi.nlm.nih.gov")
    );
  } catch {
    return false;
  }
}

/**
 * A refusal: a calm grey block, never an error (R13, R44).
 *
 * Source of truth: `design-system/components/trust-pills.html`'s
 * `.refusal` rule, transcribed rather than improvised. Every value below
 * names the token it came from:
 *
 *   border            1px solid var(--line)         `line`
 *   border-left       4px solid var(--line-strong)  `lineStrong`
 *   background        var(--surface-sunk)           `surfaceSunk`
 *   border-radius     var(--r-sm), 4px              `borderRadius: 0.5`
 *   padding           14px 16px                     `py: 1.75, px: 2`
 *   gap               6px                           `gap: 0.75`
 *   first line        <strong>, 14px                `ink`, weight 700
 *   explanation       var(--ink-muted), 13.5px      `inkMuted`
 *   explanation width max-width 62ch                `maxWidth: "62ch"`
 *
 * WHY NOT THE `Notice` COMPONENT. `Notice` has two tones and both are
 * alarms: amber `warn` and red `risk`. That card's own note says why a
 * refusal takes neither: "Refusal is a first-class state, not an error."
 * The amber box it used to render, with red trust pills under it and a red
 * "⚠ Refused" above, read as a malfunction on the one path where the
 * system is working exactly as designed. `Notice` is unchanged and still
 * carries the cap note, the system notes and the genuine failure.
 */
function RefusalBlock({
  testId,
  label,
  text,
  link,
}: {
  testId: string;
  label: string | null;
  text: string | null;
  link: string | null;
}) {
  return (
    <Box
      data-testid={testId}
      role="status"
      sx={{
        mb: 2.5,
        px: 2,
        py: 1.75,
        fontSize: 14,
        display: "flex",
        flexDirection: "column",
        gap: 0.75,
        borderRadius: 0.5,
        border: `1px solid ${designTokens.line}`,
        borderLeft: `4px solid ${designTokens.lineStrong}`,
        bgcolor: designTokens.surfaceSunk,
        color: designTokens.ink,
      }}
    >
      {label ? (
        <Box component="span" sx={{ fontWeight: 700, fontSize: 14 }}>
          {label}
        </Box>
      ) : null}
      {text ? (
        <Box
          component="span"
          sx={{ color: designTokens.inkMuted, fontSize: 13.5, maxWidth: "62ch" }}
        >
          {text}
        </Box>
      ) : null}
      {link ? (
        <Box
          component="span"
          sx={{ fontSize: 13.5, maxWidth: "62ch", wordBreak: "break-word" }}
        >
          {isLinkableRefusalLink(link) ? (
            <Box
              component="a"
              href={link}
              target="_blank"
              rel="noopener noreferrer"
              sx={{ color: designTokens.link }}
            >
              {link}
            </Box>
          ) : (
            /*
             * Shown, not linked, and not hidden either. An address that
             * fails the host pin is either a backend change nobody meant
             * or an attempt to steer a reader somewhere else; in both
             * cases the honest rendering is the characters themselves,
             * with no affordance suggesting they can be trusted.
             */
            <Box component="span" sx={{ color: designTokens.inkMuted }}>
              {link}
            </Box>
          )}
        </Box>
      ) : null}
    </Box>
  );
}

/**
 * A failure or cap notice.
 *
 * Copy arrives already chosen from a fixed, interpolation-free table, so no
 * cost figure can reach a user-facing notice even by accident.
 *
 * NO LONGER CARRIES THE REFUSAL: that is `RefusalBlock` above, per R13 and
 * R44. Both of this component's tones are alarms, and a refusal is not one.
 */
function Notice({
  testId,
  tone,
  text,
}: {
  testId: string;
  tone: "warn" | "risk";
  text: string;
}) {
  const warn = tone === "warn";
  return (
    <Box
      data-testid={testId}
      role="status"
      sx={{
        mb: 2.5,
        px: 1.75,
        py: 1.4,
        fontSize: 14,
        borderRadius: 0.5,
        border: `1px solid ${warn ? designTokens.warn : designTokens.risk}`,
        borderLeftWidth: 4,
        bgcolor: warn ? designTokens.warnWash : designTokens.riskWash,
      }}
    >
      {text}
    </Box>
  );
}

export interface AnswerBodyProps extends AnswerBodyContent {
  /** A fatal run error, or a dispatch failure. Never rendered as silence. */
  failure?: string | null;
  /**
   * Flag a source as not supporting the claim it is attached to.
   *
   * Omitted on an archived turn, deliberately: the flag posts against the
   * run a reader is looking at now, and an old turn's source is not that
   * run's source. A body with no handler renders no flag control at all.
   */
  onFlagSource?: (n: number) => void;
  flaggedSources?: number[];
  /**
   * Prefixed onto every test id this body renders. "" for the live turn.
   *
   * WHY THIS EXISTS AT ALL. `answer-meta` is how every check in this
   * repository, vitest and Playwright alike, knows a run has landed, and
   * Playwright's locators are strict: two elements carrying that id turn a
   * passing suite red for a reason that has nothing to do with the defect
   * under test. An archived turn renders the same ids under its own prefix
   * (`previous-turn-0-answer-meta`), so a folded body is addressable
   * without colliding with the live one.
   */
  testIdPrefix?: string;
  /**
   * Hang the onboarding tour's anchors on this body.
   *
   * True for the live turn only. `data-tour` is queried by exact value in
   * `OnboardingTour`, so a second copy of `citations` or `sources` inside a
   * folded turn would point the tour at an archived answer.
   */
  tour?: boolean;
  /**
   * UI fix set 9, item 9.6: the run is still writing this answer.
   *
   * Only the claims render, as they arrive. Sources, notes and the trust
   * line belong to a finished answer and wait for the run to land.
   */
  streaming?: boolean;
  /**
   * 2026-09-14: sentences are still arriving, so show the quiet "writing"
   * mark at the end of the streamed text. Separate from `streaming` because a
   * STOPPED follow-up keeps its partial sentences on screen under the
   * "Search stopped" block, and a writing mark there would claim work that
   * is no longer happening.
   */
  writing?: boolean;
  /**
   * UI fix 11.27: the question this body answers, used only to choose the
   * lead summary's main point (`mainPointFor`). Optional: without it the
   * main point is the lead's first emphasised term.
   */
  question?: string | null;
}

/**
 * The answer itself: status line, notices, claims, sources and verdict.
 *
 * UI FIX SET 7 ITEM 7.4. This was inline in `AnswerScreen` and the folded
 * turns above it rendered a hand-written summary of their own: claim TEXT
 * with no citation chips, and one line reading "5 sources · Grounded". So
 * a reader who opened an earlier turn got the words back and lost every
 * source behind them, on a product whose whole argument is that a claim is
 * worth no more than the record under it. The product owner's words on
 * 2026-09-13: "the previous answer with all sources must be retained".
 *
 * THE FIX IS THE EXTRACTION, not a second renderer that copies this one.
 * Both the live turn and every folded turn render THIS component, so a
 * field added to one appears in the other or fails to compile. A folded
 * turn that merely looked similar today is the arrangement that decays,
 * and it is the arrangement that produced the defect.
 *
 * STATE IS PER INSTANCE, which is why this is a component rather than a
 * render function: `Show work`, the sources disclosure and each open
 * source card belong to the body a reader is actually poking at, so
 * opening the sources on an archived turn must not open them on the live
 * answer.
 *
 * DESIGN GAP, named rather than filled silently (`design-consistency`).
 * The prototype's `archiveCurrent()` (`prototype/app.html`, around line
 * 1163) clones the spine, the answer, the sources block and the verdict
 * into `.prevbody`, so the design DOES cover a folded turn carrying its
 * full answer and its sources, and that half is transcribed rather than
 * invented. What the prototype's folded turn does NOT carry is the status
 * line, `Show work` and the system notes: it puts the meta text in the
 * summary as `.pm` and drops the rest. The product owner asked for the
 * complete answer, so those three are rendered in the folded body too,
 * from the same components the live answer uses. That is the one place
 * this component goes beyond the design, and no new visual value is
 * introduced by it.
 */
export function AnswerBody({
  claims,
  sources,
  meta,
  outcome = null,
  outcomeTone = null,
  elapsedMs = null,
  steps = [],
  trust = [],
  refusal = null,
  refusalLabel = null,
  refusalLink = null,
  failure = null,
  capMessage = null,
  systemNotes = [],
  onFlagSource,
  flaggedSources = [],
  testIdPrefix = "",
  tour = false,
  streaming = false,
  writing = false,
  question = null,
}: AnswerBodyProps) {
  /** `Show work` starts closed, as the prototype's `#workPanel` does. */
  const [workOpen, setWorkOpen] = useState(false);
  /*
   * Source disclosure state, F-4.8-D-01.
   *
   * CONTROLLED rather than relying on `<details>`' own toggling. jsdom does not
   * implement the activation behaviour reliably, so an uncontrolled version
   * would render correctly in a browser and be untestable here, which is how a
   * surface ends up with no check at all. The summary's default action is
   * prevented so the two do not fight.
   */
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [openSources, setOpenSources] = useState<number[]>([]);
  const toggleSource = (n: number) =>
    setOpenSources((current) =>
      current.includes(n) ? current.filter((x) => x !== n) : [...current, n],
    );

  /*
   * Layer-group disclosure state, 2026-09-20 (product owner, after `9d20438`
   * landed): "make those drop down so user just see the 3 layers first and
   * can have drop down". A live answer now carries up to 78 sources, so the
   * three layer headings must render alone until a reader asks for one
   * group's records.
   *
   * No design file covers a group-level disclosure: `identity/layer-badges.html`
   * gives the heading only (dot, label, colour, already transcribed in
   * `9d20438`) and `components/source-card.html` gives the per-record
   * `<details>`/arrow interaction, but neither shows a THIRD, group-level
   * layer of collapse. This reuses source-card's own arrow-and-summary
   * mechanics at the group heading, rather than inventing a second kind of
   * expander, per `design-consistency`.
   *
   * Each group's record list is rendered conditionally on `openGroups`,
   * not merely hidden by the native `<details>` `open` attribute the way
   * the outer disclosure and each record already are. A closed group's
   * records must not exist in the document at all: with up to 78 sources
   * across three groups, mounting every card whether or not its group is
   * open would put the same wall back one level down.
   */
  const [openGroups, setOpenGroups] = useState<Layer[]>([]);
  const toggleGroup = (layer: Layer) =>
    setOpenGroups((current) =>
      current.includes(layer) ? current.filter((x) => x !== layer) : [...current, layer],
    );

  const sourceByIndex = new Map(sources.map((source) => [source.n, source]));
  /*
   * The RENDERED source list, grouped by layer and deduplicated by record.
   * `sourceByIndex` above is untouched by this: every citation marker in the
   * prose resolves through it by its own `n`, one entry per `n` regardless
   * of how many markers a merged record now carries, so grouping and
   * deduplicating the list a reader scrolls through never changes what a
   * marker in the text resolves to.
   */
  const sourceGroups = groupSourcesByLayer(sources);

  /** The prototype's phone layout: record tables become stacked rows. */
  const phone = useMediaQuery(PHONE_LAYOUT_QUERY, { noSsr: true });

  /*
   * One claim's citation markers, 2026-09-14: superscript numbers in the layer
   * colour whose card carries the source; see `answer/CitationMarkers.tsx`.
   * Each marker's accessible name is its `aria-label`, so copying the answer
   * yields prose, and an uncited sentence still says so for assistive
   * technology (F-4.8-A-16, WCAG 1.4.1).
   */
  const citationChips = (claim: Claim, index: number) => (
    <CitationMarkers
      citations={claim.citations}
      sources={sourceByIndex}
      claimLayer={claim.layer}
      claimIndex={index}
      pending={claim.pendingCitations ?? 0}
      testIdPrefix={testIdPrefix}
    />
  );

  /*
   * What each claim rests on, as a data attribute on the claim itself: its
   * layer, "pending" while its citations are still arriving, or "none". This
   * is what the retired spine segment carried, moved onto the element it
   * describes. The visible, non-colour cue for an uncited claim is muted ink
   * with no marker after it.
   */
  const provenance = (claim: Claim) => claim.layer ?? (claim.pendingCitations ? "pending" : "none");
  const uncitedInk = (claim: Claim) =>
    claim.citations.length === 0 && !claim.pendingCitations ? { color: designTokens.inkMuted } : {};
  const rise = streaming ? RISE : {};

  /*
   * Pagination, product-owner request 2026-09-20: "why are we truncating,
   * if the data is relevant, all the data should show, instead if it is a
   * table, we create a pagination." Page size 10, fixed.
   *
   * Keyed per table by `block.key` (stable across a table's own streaming
   * growth, since a growing table only ever appends to `rows`, never
   * changes which claim started it). Reset on a new question rather than
   * left to a same-key coincidence between an old table and a new one,
   * since `AnswerBody` for the live turn is one long-lived component that
   * outlives any single answer.
   */
  const RECORDS_PAGE_SIZE = 10;
  const [recordsPage, setRecordsPage] = useState<Record<string, number>>({});
  useEffect(() => {
    setRecordsPage({});
  }, [question]);

  const blocks = buildAnswerBlocks(claims);
  // UI fix 11.27: the one bold term in the body, or none.
  const mainPoint = mainPointFor(claims, question);
  let headingNumber = 0;
  let noteNumber = 0;
  let recordsNumber = 0;

  /*
   * The pagination bar itself, shared between the phone (stacked-list) and
   * desktop (table) record renderings below. No pagination pattern exists
   * anywhere in `docs/build/design/design-system/` (checked
   * `prototype/app.html`, the only file carrying responsive rules, then
   * `components/`, `screens/` and the README's coverage table): the design
   * system's own result table, `.rtab`, only ever appears whole. So this is
   * built from `frontend/src/theme.ts`'s tokens plus the nearest designed
   * neighbour already shipped in this file, the "Show work" text button
   * above (a real `component="button"`, `type="button"`, transparent,
   * `designTokens.link`, `font: "inherit"`, `cursor: pointer`, `p: 0`),
   * which is this repository's own precedent for a keyboard-reachable
   * inline text control. The status line's tone (`inkMuted`) matches the
   * inline-note text a few lines below.
   */
  const renderRecordsPagination = (
    block: Extract<AnswerBlock, { type: "records" }>,
    number: number,
    currentPage: number,
    totalPages: number,
    totalRows: number,
  ) => {
    const start = currentPage * RECORDS_PAGE_SIZE + 1;
    const end = Math.min(start + RECORDS_PAGE_SIZE - 1, totalRows);
    const goTo = (next: number) =>
      setRecordsPage((current) => ({ ...current, [block.key]: next }));
    const navSx = {
      font: "inherit",
      fontSize: 13,
      fontWeight: 600,
      border: 0,
      bgcolor: "transparent",
      color: designTokens.link,
      cursor: "pointer",
      p: 0,
      "&:disabled": { color: designTokens.inkFaint, cursor: "default" },
    } as const;
    return (
      <Box
        data-testid={`${testIdPrefix}answer-records-${number}-pagination`}
        sx={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "8px 16px",
          fontSize: 13,
          color: designTokens.inkMuted,
          m: "0 0 16px",
          pt: "8px",
          borderTop: `1px solid ${designTokens.line}`,
        }}
      >
        <Box component="span" aria-live="polite" data-testid={`${testIdPrefix}answer-records-${number}-status`}>
          {`Showing ${start}–${end} of ${totalRows}`}
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <Box
            component="button"
            type="button"
            data-testid={`${testIdPrefix}answer-records-${number}-prev`}
            onClick={() => goTo(currentPage - 1)}
            disabled={currentPage === 0}
            sx={navSx}
          >
            {"‹ Previous"}
          </Box>
          <Box component="span" sx={{ color: designTokens.inkFaint, fontSize: 12.5 }}>
            {`Page ${currentPage + 1} of ${totalPages}`}
          </Box>
          <Box
            component="button"
            type="button"
            data-testid={`${testIdPrefix}answer-records-${number}-next`}
            onClick={() => goTo(currentPage + 1)}
            disabled={currentPage >= totalPages - 1}
            sx={navSx}
          >
            {"Next ›"}
          </Box>
        </Box>
      </Box>
    );
  };

  const renderRecords = (block: Extract<AnswerBlock, { type: "records" }>) => {
    const number = recordsNumber++;
    const totalRows = block.rows.length;
    const totalPages = Math.max(1, Math.ceil(totalRows / RECORDS_PAGE_SIZE));
    const isPaginated = totalRows > RECORDS_PAGE_SIZE;
    const currentPage = Math.min(recordsPage[block.key] ?? 0, totalPages - 1);
    const visibleRows = isPaginated
      ? block.rows.slice(currentPage * RECORDS_PAGE_SIZE, currentPage * RECORDS_PAGE_SIZE + RECORDS_PAGE_SIZE)
      : block.rows;
    const idColumn = identifierColumn(block.header);
    const isIdAt = (cell: string, column: number) => column === idColumn || isIdentifierCell(cell);
    const heading =
      block.label !== null ? (
        <Typography
          component="h2"
          data-testid={`${testIdPrefix}answer-heading-${headingNumber++}`}
          sx={{ ...AH_SX, ...rise }}
        >
          {block.label}
        </Typography>
      ) : null;
    if (phone) {
      return (
        <Fragment key={block.key}>
          {heading}
          <Box
            component="ul"
            data-testid={`${testIdPrefix}answer-records-${number}`}
            data-record-source={block.source}
            sx={{ listStyle: "none", m: isPaginated ? "0" : "0 0 16px", p: 0 }}
          >
            {visibleRows.map(({ claim, index, cells }) => (
              <Box
                component="li"
                key={index}
                data-testid={`${testIdPrefix}claim-text-${index}`}
                data-layer={provenance(claim)}
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "2px",
                  py: "10px",
                  borderBottom: `1px solid ${designTokens.line}`,
                  "&:last-child": { borderBottom: 0 },
                  ...rise,
                }}
              >
                <Box
                  component="span"
                  sx={{ fontSize: 15, lineHeight: 1.45, color: designTokens.ink, ...uncitedInk(claim) }}
                >
                  {cells[0] ?? claim.text}
                  {citationChips(claim, index)}
                </Box>
                {cells.slice(1).map((cell, c) =>
                  cell ? (
                    <Box
                      component="span"
                      key={c}
                      sx={
                        isIdAt(cell, c + 1)
                          ? RTAB_ID
                          : { fontSize: 13.5, lineHeight: 1.45, color: designTokens.inkMuted }
                      }
                    >
                      {cell}
                    </Box>
                  ) : null,
                )}
              </Box>
            ))}
          </Box>
          {isPaginated ? renderRecordsPagination(block, number, currentPage, totalPages, totalRows) : null}
        </Fragment>
      );
    }
    return (
      <Fragment key={block.key}>
        {heading}
        <Box
          data-testid={`${testIdPrefix}answer-records-${number}`}
          data-record-source={block.source}
          sx={{ overflowX: "auto", m: isPaginated ? "0" : "0 0 16px", "&:last-child": { mb: 0 } }}
        >
          <Box
            component="table"
            data-testid={`${testIdPrefix}answer-table`}
            sx={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 13.5,
              border: `1px solid ${designTokens.line}`,
              bgcolor: designTokens.surface,
              "& tbody tr:last-child td": { borderBottom: 0 },
            }}
          >
            {block.header ? (
              <thead>
                <tr>
                  {block.header.map((label, c) => (
                    <Box component="th" key={`${label}-${c}`} scope="col" sx={RTAB_HEAD}>
                      {label}
                    </Box>
                  ))}
                  <Box component="th" scope="col" aria-label="Sources" sx={{ ...RTAB_HEAD, width: 36 }} />
                </tr>
              </thead>
            ) : null}
            <tbody>
              {visibleRows.map(({ claim, index, cells }) => (
                <Box
                  component="tr"
                  key={index}
                  data-testid={`${testIdPrefix}claim-text-${index}`}
                  data-layer={provenance(claim)}
                  sx={{ ...uncitedInk(claim), ...rise }}
                >
                  {cells.map((cell, c) => (
                    <Box
                      component="td"
                      key={c}
                      sx={isIdAt(cell, c) ? { ...RTAB_CELL, ...RTAB_ID } : RTAB_CELL}
                    >
                      {cell}
                    </Box>
                  ))}
                  <Box component="td" sx={{ ...RTAB_CELL, width: 36, whiteSpace: "nowrap" }}>
                    {citationChips(claim, index)}
                  </Box>
                </Box>
              ))}
            </tbody>
          </Box>
        </Box>
        {isPaginated ? renderRecordsPagination(block, number, currentPage, totalPages, totalRows) : null}
      </Fragment>
    );
  };

  const renderBlock = (block: AnswerBlock) => {
    if (block.type === "heading") {
      return (
        <Typography
          key={block.key}
          component="h2"
          data-testid={`${testIdPrefix}answer-heading-${headingNumber++}`}
          sx={{ ...AH_SX, ...rise }}
        >
          {block.text}
        </Typography>
      );
    }
    if (block.type === "note") {
      return (
        <Typography
          key={block.key}
          data-testid={`${testIdPrefix}answer-inline-note-${noteNumber++}`}
          sx={{ fontSize: 13.5, color: designTokens.inkMuted, maxWidth: "66ch", m: "0 0 14px", ...rise }}
        >
          {block.text}
        </Typography>
      );
    }
    if (block.type === "records") return renderRecords(block);
    return (
      <Typography key={block.key} component="p" sx={PROSE_SX}>
        {block.items.map(({ claim, index }) => (
          <Box
            component="span"
            key={index}
            data-testid={`${testIdPrefix}claim-text-${index}`}
            data-layer={provenance(claim)}
            sx={{ ...uncitedInk(claim), ...rise }}
          >
            {/* No space before the markers: a superscript sits against the
                sentence it cites, and a space would let it wrap alone. */}
            {withMainPoint(
              claim.text,
              mainPoint?.index === index ? mainPoint.term : undefined,
              `${testIdPrefix}answer-main-point`,
            )}
            {citationChips(claim, index)}{" "}
          </Box>
        ))}
      </Typography>
    );
  };

  const medicalNotes = systemNotes.filter((note) => note.trimStart().startsWith(MEDICAL_NOTE_PREFIX));
  const otherNotes = systemNotes
    .filter((note) => !note.trimStart().startsWith(MEDICAL_NOTE_PREFIX))
    .filter((note) => !isHiddenNote(note));

  return (
    /*
     * ONE ROOT, carrying `answer-body` under this body's own prefix.
     *
     * It is not decoration and it is not layout. It is the hook that lets a
     * check compare the live body and a folded one element by element, so
     * "the two cannot drift" is a statement a test can falsify rather than
     * an intention in a comment. See
     * `AnswerScreen.previousTurnBody.test.tsx`.
     */
    <Box data-testid={`${testIdPrefix}answer-body`}>
      {/*
        The status strip, F-4.8-D-05. This was the counts alone. The
        prototype's `.summary` leads with the OUTCOME and the elapsed time,
        then the counts, then a `Show work` disclosure that reopens the
        run's own steps, which were otherwise unreachable once the run
        screen was gone.

        Still hooked as `answer-meta` so the rail's per-search counts can be
        asserted to AGREE with this line rather than matching a literal both
        could get wrong independently.

        THE RULE ABOVE IT IS NOT HERE ANY MORE. It used to be this strip's
        own `borderTop`, which worked while the strip sat inside the
        question block. Now that the body renders under a question block
        (live) or under a folded turn's summary (archived), both of which
        already end in a rule, a second one ten pixels below read as a
        double line. The one rule above the strip is the caller's;
        everything below is this component's.
      */}
      {meta || outcome ? (
        <Box sx={{ pt: 1.5, pb: 2, mb: 2.5, borderBottom: `1px solid ${designTokens.line}` }}>
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 1.25,
              /*
               * NO background of its own, which is what the prototype's
               * `.summary` has: no rule, so it sits on the panel's white.
               *
               * The first version tinted it `surfaceSunk`, an addition the
               * design does not make, and that tint is what pushed the green
               * "✓ Answered" to 4.34:1 against a 4.5:1 requirement. Matching
               * the prototype and passing the gate turned out to be the same
               * edit, which is the argument for transcribing rather than
               * improvising.
               */
            }}
          >
            <Typography
              variant="body2"
              data-testid={`${testIdPrefix}answer-meta`}
              sx={{ color: designTokens.inkMuted }}
            >
              {/*
                F-4.9-A-03. This was `✓ {outcome}` in the success green for
                every outcome, so a refusal rendered "✓ Refused" and an
                ask-back "✓ Needs a narrower question", both ticked, both
                green. The glyph and the colour now follow the outcome.

                That quoted string is the copy AS IT WAS when F-4.9-A-03
                was filed, kept verbatim so the account still reads as
                what happened. T-4.16-03 has since changed the `ask`
                wording to "Single source, not independently confirmed";
                `useRunView.ts`'s OUTCOME_BY_TRUST is the live source and
                this comment is history, not a specification.
              */}
              {outcome ? (
                <Box
                  component="span"
                  sx={{
                    color:
                      outcomeTone === "risk"
                        ? designTokens.risk
                        : outcomeTone === "warn"
                          ? designTokens.warn
                          : designTokens.ok,
                    // UI fix 11.27: regular weight; the tone colour and the
                    // glyph carry the outcome, the question is the bold line.
                    fontWeight: 400,
                    mr: 0.75,
                  }}
                >
                  {outcomeTone === "risk" ? "⚠" : outcomeTone === "warn" ? "?" : "✓"} {outcome}
                </Box>
              ) : null}
              {elapsedMs !== null ? `${(elapsedMs / 1000).toFixed(1)}s · ` : ""}
              {meta}
            </Typography>
            {steps.length > 0 ? (
              <Box
                component="button"
                type="button"
                onClick={() => setWorkOpen((open) => !open)}
                aria-expanded={workOpen}
                sx={{
                  ml: "auto",
                  font: "inherit",
                  fontSize: 13,
                  border: 0,
                  bgcolor: "transparent",
                  color: designTokens.link,
                  cursor: "pointer",
                  p: 0,
                }}
              >
                {workOpen ? "Hide work ▴" : "Show work ▾"}
              </Box>
            ) : null}
          </Box>
          {workOpen && steps.length > 0 ? (
            <Box sx={{ mt: 1.75 }}>
              <ReasoningLog steps={steps} testId={`${testIdPrefix}work-panel`} />
            </Box>
          ) : null}
        </Box>
      ) : null}

      {/*
        Rendered on EITHER field, not on `refusal` alone. A refusal whose
        `message` arrives empty still has a label, and a refusal a reader
        can see is the whole requirement; gating on the sentence alone
        would reproduce the silent blank page F-4.8-J-02 closed.
      */}
      {refusal || refusalLabel ? (
        <RefusalBlock
          testId={`${testIdPrefix}answer-refusal`}
          label={refusalLabel}
          text={refusal}
          link={refusalLink}
        />
      ) : null}
      {failure ? (
        <Notice testId={`${testIdPrefix}answer-failure`} tone="risk" text={failure} />
      ) : null}
      {capMessage ? (
        <Notice testId={`${testIdPrefix}answer-cap`} tone="warn" text={capMessage} />
      ) : null}

      {/*
        RENDERED UNCONDITIONALLY, even with no claims: the onboarding tour's
        `citations` anchor hangs on it, and an empty box has no height.
      */}
      <Box
        {...(tour ? { "data-tour": "citations" } : {})}
        data-testid={`${testIdPrefix}claims`}
        aria-live={streaming ? "polite" : undefined}
      >
        {blocks.map(renderBlock)}
      </Box>

      {/*
        The "writing" line at the end of the streamed text, from the approved
        `Streaming.dc.html`: 13.5px `inkMuted`, the dots 700 in `blue`. Gone
        the moment the run lands or stops. `aria-hidden`, because the claims
        region is already a polite live region and `RunProgress` announces
        "Write step running".
      */}
      {streaming && writing ? (
        <Box
          data-testid={`${testIdPrefix}streaming-writing-indicator`}
          aria-hidden="true"
          sx={{
            mt: 1,
            fontSize: 13.5,
            color: designTokens.inkMuted,
            display: "flex",
            alignItems: "center",
            gap: "4px",
          }}
        >
          writing
          <Box component="span" sx={{ fontWeight: 700, color: designTokens.blue }}>
            <WritingEllipsis />
          </Box>
        </Box>
      ) : null}

      {/*
        UI fix set 9, item 9.8: disclosures render AFTER the answer they
        qualify, as quiet grey notes, never as amber boxes above the first
        sentence. Colour and size are the refusal explanation's (`inkMuted`,
        13.5px), the nearest designed neighbour for text about an answer.
      */}
      {/*
        The Notes section and the medical-advice line, from the approved
        mockups: after the answer, before Sources. Notes are a muted bulleted
        list under a small-caps heading; the Plain language closing line
        stands on its own below them.
      */}
      {!streaming && otherNotes.length > 0 ? (
        <Box data-testid={`${testIdPrefix}answer-notes`} sx={{ mt: "32px", "@media (max-width:720px)": { mt: "28px" } }}>
          <Typography component="h2" sx={{ ...AH_BASE, mt: 0 }}>
            Notes
          </Typography>
          <Box
            component="ul"
            sx={{
              m: 0,
              pl: "20px",
              fontSize: 14.5,
              lineHeight: 1.6,
              color: designTokens.inkMuted,
              maxWidth: "66ch",
              "@media (max-width:720px)": { pl: "18px", fontSize: 14 },
            }}
          >
            {otherNotes.map((note, i) => (
              <Box component="li" key={i} data-testid={`${testIdPrefix}answer-note-${i}`} sx={{ m: "0 0 6px" }}>
                {note}
              </Box>
            ))}
          </Box>
        </Box>
      ) : null}
      {!streaming
        ? medicalNotes.map((note, i) => (
            <Typography
              key={i}
              data-testid={`${testIdPrefix}answer-medical-note`}
              sx={{ mt: "22px", fontSize: 13.5, color: designTokens.inkMuted, "@media (max-width:720px)": { mt: "18px", fontSize: 13 } }}
            >
              {note}
            </Typography>
          ))
        : null}

      {/*
        F-4.8-D-01. The sources were always expanded, every field of every
        card at once, so a six-source answer became a wall and the sources
        stopped being scannable. The prototype collapses them behind one
        disclosure carrying the count, and collapses each card inside it.
      */}
      {sources.length > 0 && !streaming ? (
        <Box
          component="details"
          data-testid={`${testIdPrefix}sources-disclosure`}
          {...(tour ? { "data-tour": "sources" } : {})}
          open={sourcesOpen}
          // The mockup's rule above Sources: 22px above, 14px inside, one `line`.
          sx={{ mt: "22px", pt: "14px", borderTop: `1px solid ${designTokens.line}` }}
        >
          <Box
            component="summary"
            onClick={(event: React.MouseEvent) => {
              event.preventDefault();
              setSourcesOpen((open) => !open);
            }}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
              cursor: "pointer",
              listStyle: "none",
              mb: 1.25,
              "&::-webkit-details-marker": { display: "none" },
            }}
          >
            <Box
              component="span"
              aria-hidden="true"
              sx={{
                fontSize: 10,
                color: designTokens.inkFaint,
                transform: sourcesOpen ? "rotate(90deg)" : "none",
                transition: "transform .12s ease",
              }}
            >
              ▶
            </Box>
            <Typography
              variant="overline"
              component="span"
              sx={{ color: designTokens.inkFaint }}
            >
              Sources
            </Typography>
            <Box
              component="span"
              data-testid={`${testIdPrefix}sources-count`}
              sx={{
                ...mono,
                fontSize: 11,
                fontWeight: 400,
                color: designTokens.inkMuted,
                border: `1px solid ${designTokens.line}`,
                borderRadius: 999,
                px: 0.75,
              }}
            >
              {sourceGroups.reduce((total, group) => total + group.items.length, 0)}
            </Box>
          </Box>

          {/*
            GROUPED BY LAYER (product owner, 2026-09-20): "should we bucket
            them into the layers and provide some info, will be hard to parse
            500 sources to be honest". Once the reader-facing cap rose from 16
            to 100 rows (`9cc5d63`), a flat list of that size stopped being
            scannable. Each group's dot and label are transcribed from
            `identity/layer-badges.html`'s three cards, the design system's
            own answer to "what does a reader need to tell the layers apart
            at a glance": the colour and the plain-language name, nothing
            invented for this surface.

            DEDUPLICATED WITHIN each group by record (`groupSourcesByLayer`,
            above): "ensure the content in the table is pointing to unique
            information, if it references same source, that should just be
            present once". A record cited more than once now renders as one
            card carrying every marker, e.g. "[2][5]", rather than the same
            name, tool and licence repeated. This is the SOURCE LIST only;
            the result table above is untouched, because two table rows can
            state different facts about the same record and collapsing them
            would lose one of the facts.

            COLLAPSED BEHIND ITS OWN DISCLOSURE, 2026-09-20 (product owner,
            after testing the above live): "make those drop down so user
            just see the 3 layers first and can have drop down". This reuses
            `source-card.html`'s own `<details>`/`<summary>`/arrow pattern
            one level up, rather than a second, differently styled expander:
            same arrow glyph, same rotate-on-open transition, same
            controlled-`open` approach as the outer Sources disclosure and
            each record card (`openSources` above), for the same reason
            noted there: jsdom does not implement native `<details>` toggling
            reliably, so this stays a React-controlled `open` rather than an
            uncontrolled one. Unlike those two, a closed group's records are
            left OUT of the render entirely instead of merely un-opened,
            since a group can hold most of a 78-source answer and mounting
            every card regardless of its group's state would put the wall
            back one level down.
          */}
          {sourceGroups.map((group) => {
            const groupOpen = openGroups.includes(group.layer);
            return (
            <Box
              key={group.layer}
              component="details"
              data-testid={`${testIdPrefix}sources-group-${group.layer}`}
              open={groupOpen}
              sx={{ mb: 1 }}
            >
              <Box
                component="summary"
                onClick={(event: React.MouseEvent) => {
                  event.preventDefault();
                  toggleGroup(group.layer);
                }}
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 0.75,
                  mb: 0.75,
                  mt: 0.5,
                  cursor: "pointer",
                  listStyle: "none",
                  "&::-webkit-details-marker": { display: "none" },
                }}
              >
                <Box
                  component="span"
                  aria-hidden="true"
                  sx={{
                    fontSize: 9,
                    color: designTokens.inkFaint,
                    transform: groupOpen ? "rotate(90deg)" : "none",
                    transition: "transform .12s ease",
                  }}
                >
                  ▶
                </Box>
                <Box
                  component="span"
                  aria-hidden="true"
                  sx={{
                    width: "12px",
                    height: "12px",
                    borderRadius: "3px",
                    flex: "none",
                    display: "block",
                    bgcolor: layerColour(group.layer).main,
                  }}
                />
                <Typography
                  variant="overline"
                  component="span"
                  sx={{ color: designTokens.inkFaint, fontSize: 10.5, letterSpacing: "0.1em" }}
                >
                  {group.label}
                </Typography>
                <Box
                  component="span"
                  data-testid={`${testIdPrefix}sources-group-${group.layer}-count`}
                  sx={{
                    ...mono,
                    fontSize: 11,
                    fontWeight: 400,
                    color: designTokens.inkMuted,
                    border: `1px solid ${designTokens.line}`,
                    borderRadius: 999,
                    px: 0.75,
                  }}
                >
                  {group.items.length}
                </Box>
              </Box>

              {group.items.map((source) => {
                const colour = layerColour(source.layer);
                const primaryN = source.ns[0];
                return (
                  <Box
                    key={source.ns.join(",")}
                    component="details"
                    data-testid={`${testIdPrefix}source-${primaryN}`}
                    data-layer={source.layer}
                    open={openSources.includes(primaryN)}
                    sx={{
                      border: `1px solid ${designTokens.line}`,
                      borderLeft: `4px solid ${colour.main}`,
                      borderRadius: 0.5,
                      bgcolor: designTokens.surface,
                      mb: 1,
                      px: 1.75,
                      py: 1.25,
                    }}
                  >
                    <Box
                      component="summary"
                      onClick={(event: React.MouseEvent) => {
                        event.preventDefault();
                        toggleSource(primaryN);
                      }}
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1.25,
                        flexWrap: "wrap",
                        cursor: "pointer",
                        listStyle: "none",
                        "&::-webkit-details-marker": { display: "none" },
                      }}
                    >
                      <Box
                        component="span"
                        aria-hidden="true"
                        sx={{
                          fontSize: 9,
                          color: designTokens.inkFaint,
                          transform: openSources.includes(primaryN) ? "rotate(90deg)" : "none",
                          transition: "transform .12s ease",
                        }}
                      >
                        ▶
                      </Box>
                      <Box
                        component="span"
                        data-testid={`${testIdPrefix}source-${primaryN}-markers`}
                        sx={{ ...mono, fontWeight: 700, fontSize: 12 }}
                      >
                        {source.ns.map((n) => `[${n}]`).join("")}
                      </Box>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {source.name}
                      </Typography>
                      {/*
                        F-4.8-D-02. This read "L1", which a reader has to already
                        know how to decode. The prototype names the layer in words.
                      */}
                      <Box
                        component="span"
                        sx={{ ...mono, ml: "auto", fontSize: 11.5, color: designTokens.inkMuted }}
                      >
                        L{source.layer} · {LAYER_WORD[source.layer] ?? "source"}
                      </Box>
                    </Box>

                    {/*
                      The flag control sits in the card BODY, not the summary row.
                      The prototype used to put it in the summary, and axe rightly
                      calls that `nested-interactive`: a `<summary>` with a focusable
                      descendant, WCAG 4.1.2. This shipped as a deviation
                      (F-4.9-D-13); the design-system focus-nesting pass of
                      2026-08-14 moved it in the design too, so the two agree.
                    */}
                    {onFlagSource ? (
                      <Box
                        component="button"
                        type="button"
                        aria-pressed={flaggedSources.includes(primaryN)}
                        onClick={(event: React.MouseEvent) => {
                          // It lives inside the summary, as it does in the
                          // prototype, so without this a flag click also opens or
                          // closes the card under the user's cursor.
                          event.preventDefault();
                          event.stopPropagation();
                          onFlagSource(primaryN);
                        }}
                        sx={{
                          font: "inherit",
                          fontSize: 11.5,
                          px: 1,
                          py: 0.3,
                          borderRadius: 0.5,
                          cursor: "pointer",
                          border: "1px solid",
                          borderColor: flaggedSources.includes(primaryN)
                            ? designTokens.risk
                            : designTokens.line,
                          color: flaggedSources.includes(primaryN)
                            ? designTokens.risk
                            : designTokens.inkFaint,
                          bgcolor: flaggedSources.includes(primaryN)
                            ? designTokens.riskWash
                            : designTokens.surface,
                          "&:hover": { color: designTokens.risk, borderColor: designTokens.risk },
                        }}
                      >
                        {flaggedSources.includes(primaryN) ? "Flagged" : "Flag: does not support"}
                      </Box>
                    ) : null}
                    {/* Every field Section 9.1 requires. The licence is not optional.
                        Inside the disclosure now, so a collapsed card is a header. */}
                    <Box
                      component="dl"
                      sx={{
                        m: 0,
                        display: "grid",
                        gridTemplateColumns: "auto 1fr",
                        gap: "7px 18px",
                        fontSize: 13,
                      }}
                    >
                      {[
                        ["Tool", source.tool, true],
                        ["Evidence", source.evidence, false],
                        ["Confidence", source.confidence, false],
                        ["License", source.license, false],
                        ["Record", source.url, true],
                      ].map(([label, value, isToken]) => (
                        <Box key={label as string} sx={{ display: "contents" }}>
                          <Typography
                            component="dt"
                            variant="overline"
                            sx={{
                              fontSize: 10.5,
                              letterSpacing: "0.1em",
                              color: designTokens.inkFaint,
                            }}
                          >
                            {label as string}
                          </Typography>
                          <Box
                            component="dd"
                            sx={{
                              m: 0,
                              fontSize: isToken ? 12.5 : 13,
                              ...(isToken ? mono : {}),
                              wordBreak: isToken ? "break-all" : "normal",
                            }}
                          >
                            {label === "Record" && isLinkableCitationUrl(value as string) ? (
                              // A-17: every citation must link back to its source.
                              // Previously the URL was plain text and the answer
                              // screen contained zero anchors, so verifying a claim
                              // meant selecting and copying a URL by hand.
                              <Box
                                component="a"
                                href={value as string}
                                target="_blank"
                                rel="noopener noreferrer"
                                sx={{ color: designTokens.link }}
                              >
                                {value as string}
                              </Box>
                            ) : (
                              <>
                                {value as string}
                                {label === "Record" ? (
                                  <Box
                                    component="span"
                                    sx={{ display: "block", fontSize: 11.5, color: designTokens.risk }}
                                  >
                                    Not linked: this URL is not on a recognised NCBI host.
                                  </Box>
                                ) : null}
                              </>
                            )}
                          </Box>
                        </Box>
                      ))}
                    </Box>
                  </Box>
                );
              })}
            </Box>
            );
          })}
        </Box>
      ) : null}

      {/*
        UI fix set 9, item 9.9 (decision U1): ONE PLAIN LINE, not a row of
        pills. Each signal is a span in one sentence-like line, separated by
        a middle dot, with the info card explaining how sources are counted.
        A high-risk span keeps the risk colour, the one place red appears
        (`trust-pills.html`'s note), so it stays visible. The green check
        stays on a confirmed line only; the label reads in ink, because the
        design's green on white text is the pair F-4.9 measured below AA.
        Sizes are the pills' own (12.5px) and the refusal explanation's
        colour; no new value.
      */}
      {trust.length > 0 && !streaming ? (
        <Box
          role="status"
          aria-label="Trust signals"
          data-testid={`${testIdPrefix}trust-line`}
          sx={{
            position: "relative",
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: 0.75,
            mt: "14px",
            fontSize: 12.5,
            color: designTokens.inkMuted,
          }}
        >
          {trust.map((signal, position) => (
            <Fragment key={signal.label}>
              {position > 0 ? (
                <Box component="span" aria-hidden="true">
                  ·
                </Box>
              ) : null}
              <Box
                component="span"
                data-testid={`${testIdPrefix}trust-${signal.kind}`}
                sx={{
                  // UI fix 11.27: every span regular; a high-risk span keeps
                  // the risk colour, which is what makes it stand out.
                  fontWeight: 400,
                  color:
                    signal.kind === "risk"
                      ? designTokens.risk
                      : signal.kind === "good"
                        ? designTokens.ink
                        : designTokens.inkMuted,
                }}
              >
                {signal.kind === "good" ? (
                  <Box component="span" aria-hidden="true" sx={{ color: designTokens.ok, mr: 0.5 }}>
                    ✓
                  </Box>
                ) : null}
                {signal.label}
              </Box>
            </Fragment>
          ))}
          <Box component="span" sx={{ position: "relative", display: "inline-flex" }}>
            <PersonaInfo
              name="Trust signals"
              about={TRUST_LINE_EXPLAINER}
              wikipedia={null}
              variant="onLight"
              align="left"
            />
          </Box>
        </Box>
      ) : null}
    </Box>
  );
}


/**
 * One folded earlier turn (item 7.4): a native disclosure whose summary row
 * carries the question, its meta line and, on the right, a "Show answer" or
 * "Hide answer" word that follows the disclosure's own open state.
 */
function FoldedTurn({ turn, index }: { turn: PreviousTurn; index: number }) {
  const [open, setOpen] = useState(false);
  return (
              <Box
                component="details"
                data-testid={`previous-turn-${index}`}
                onToggle={(event: React.SyntheticEvent<HTMLDetailsElement>) =>
                  setOpen(event.currentTarget.open)
                }
                sx={{
                  border: `1px solid ${designTokens.line}`,
                  borderRadius: 0.5,
                  bgcolor: designTokens.surfaceSunk,
                  "& > summary": {
                    cursor: "pointer",
                    listStyle: "none",
                    display: "flex",
                    alignItems: "baseline",
                    gap: 1.25,
                    px: 1.75,
                    py: 1.5,
                  },
                  "& > summary::-webkit-details-marker": { display: "none" },
                }}
              >
                <Box component="summary">
                  <Box
                    component="span"
                    aria-hidden="true"
                    sx={{ fontSize: 10, color: designTokens.inkFaint }}
                  >
                    ▶
                  </Box>
                  <Typography
                    component="span"
                    sx={{ fontWeight: 700, fontSize: 14.5, color: designTokens.ink }}
                  >
                    {turn.question}
                  </Typography>
                  <Typography
                    component="span"
                    sx={{ fontSize: 12, color: designTokens.inkFaint }}
                  >
                    {turn.meta}
                  </Typography>
                  {/*
                    Product-owner feedback, 2026-09-13, on the retest: "have a
                    show answer and hide answer on the right hand side that
                    controls the drop down. That way it is clear." The word
                    changes with the disclosure's own state, read off the
                    native `toggle` event, so the label can never disagree
                    with what the row is doing. Link colour, the same as
                    "Show work" beside the status line, which is the nearest
                    designed neighbour for a text control on the right.
                  */}
                  <Typography
                    component="span"
                    data-testid={`previous-turn-${index}-toggle`}
                    sx={{
                      marginLeft: "auto",
                      fontSize: 13,
                      fontWeight: 600,
                      color: designTokens.link,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {open ? "Hide answer" : "Show answer"}
                  </Typography>
                </Box>
                {/*
                  THE WHOLE ANSWER, not a summary of it (item 7.4). This
                  block used to render claim TEXT and a line reading "5
                  sources · Grounded", so opening an earlier turn gave a
                  reader the words back and took every record away. It is
                  the same `AnswerBody` the live turn renders, under this
                  turn's own test-id prefix, with no flag handler and no
                  tour anchors: both of those act on the run in front of
                  the reader, and this one is finished.

                  `.prevbody{padding:4px 14px 16px}` is the prototype's,
                  kept, except that the bottom padding grows to 20px because
                  the body below it is now the full answer rather than two
                  lines, and a source card ending flush against the card
                  border is the "spacing is way off" complaint in miniature.
                */}
                <Box
                  sx={{
                    px: 1.75,
                    pt: 0.5,
                    pb: 2.5,
                    bgcolor: designTokens.surface,
                    borderTop: `1px solid ${designTokens.line}`,
                  }}
                >
                  <AnswerBody
                    testIdPrefix={`previous-turn-${index}-`}
                    question={turn.question}
                    claims={turn.claims}
                    sources={turn.sources}
                    meta={turn.meta}
                    outcome={turn.outcome}
                    outcomeTone={turn.outcomeTone}
                    elapsedMs={turn.elapsedMs}
                    steps={turn.steps}
                    trust={turn.trust}
                    refusal={turn.refusal}
                    refusalLabel={turn.refusalLabel}
                    refusalLink={turn.refusalLink}
                    capMessage={turn.capMessage}
                    systemNotes={turn.systemNotes}
                  />
                </Box>
              </Box>
  );
}

export function AnswerScreen({
  question,
  claims,
  sources,
  meta,
  outcome = null,
  outcomeTone = null,
  elapsedMs = null,
  steps = [],
  trust = [],
  runId = null,
  authToken = null,
  followUp,
  previousTurns = [],
  progress = null,
  onNewSearch,
  clarifying = false,
  stopped = false,
  refusal = null,
  refusalLabel = null,
  refusalLink = null,
  failure = null,
  capMessage = null,
  systemNotes = [],
  onFlagSource,
  flaggedSources = [],
}: AnswerScreenProps) {
  /*
   * UI fix set 7 (R22). Bring the new turn's heading into view when a
   * follow-up starts.
   *
   * The thread above grows by one collapsed row per turn, so by the third
   * question the heading of the turn just asked for can sit below the fold
   * on a short laptop screen. On the old full-screen run there was nothing
   * above it and nothing to scroll to; keeping the conversation is what
   * creates this obligation.
   *
   * Keyed on the QUESTION as well as on whether a run is in flight, so a
   * re-render during the run does not keep yanking the page, and a second
   * follow-up scrolls again.
   *
   * Both guards are real rather than defensive noise: `scrollIntoView` is
   * not implemented in jsdom, and `matchMedia` is absent there too, so an
   * unguarded call would take the whole test render down. The reduced-motion
   * check is the same courtesy the screen fade in `App.tsx` already extends.
   */
  const headingRef = useRef<HTMLDivElement | null>(null);
  const running = progress !== null && progress !== undefined;
  useEffect(() => {
    if (!running) return;
    const node = headingRef.current;
    if (!node || typeof node.scrollIntoView !== "function") return;
    const reduced =
      typeof window !== "undefined" && typeof window.matchMedia === "function"
        ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
        : false;
    node.scrollIntoView({ block: "start", behavior: reduced ? "auto" : "smooth" });
  }, [running, question]);

  /*
   * UI fix set 7 item 7.5. A clarification puts the cursor in the follow-up
   * field, so the reader answers the question where it was asked.
   *
   * The product owner on 2026-09-13: "the follow up must retain context or
   * ask clarification if the question is not clear. Because if this is a
   * discussion, it must flow." A discussion does not flow if the system
   * asks something and then leaves the reader to find the box.
   *
   * THE FIELD IS NOT THIS SCREEN'S TO OWN: `followUp` arrives as an opaque
   * node built by `App`, so the input is reached through a wrapper ref
   * rather than a prop chain. That is the narrower coupling of the two on
   * offer, since the alternative is every caller passing a focus flag down
   * through a node it does not construct either.
   *
   * Keyed on the question as well, so a second clarification in the same
   * conversation focuses again rather than once per mount.
   */
  const followUpRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!clarifying || running) return;
    const field = followUpRef.current?.querySelector("input");
    if (field && typeof field.focus === "function") field.focus();
  }, [clarifying, running, question]);

  return (
    // Set 2, R8: full width up to 900, the same as the run screen, so the box
    // keeps one size from progress to answer.
    // `my: auto` centres a short answer vertically, product-owner feedback
    // 2026-09-12. A tall one starts at the top, since auto margins collapse
    // to zero when the content is taller than the space.
    <Box sx={{ width: "100%", maxWidth: 900, mx: "auto", my: "auto", px: { xs: 2, sm: 3 }, py: 3.5 }}>
      <Box
        data-tour="answer"
        sx={{
          bgcolor: designTokens.surface,
          border: `1px solid ${designTokens.line}`,
          borderRadius: 1,
          // 2026-09-14, the approved mockups' card padding.
          p: { xs: "20px 18px 24px", sm: "26px 32px 32px" },
        }}
      >
        {/*
          T-4.16-02. The conversation thread: every earlier turn of THIS
          search, collapsed, still on the page.

          POSITION CHANGED IN UI FIX SET 7 (R22), and the change is a
          deliberate departure from the prototype rather than a drift from
          it. The prototype's answer section orders the tail `sources`,
          `verdict`, `thread`, then the follow-up form, so earlier turns sit
          BELOW the current answer. The product owner asked for the opposite
          on 2026-09-13: "The first answer should minimise and the chat
          should continue on the same screen", the earlier answer shrinking
          above and the new answer growing below, which is how a conversation
          reads everywhere else. So the thread now sits at the top of the
          card, above the current question, and the current turn, whether it
          is an answer or a run still in flight, is the thing at the bottom
          where a reader's eye ends up.

          The argument the old position had, that a growing thread pushes the
          thing just asked for off screen, is real and is answered rather
          than ignored: each earlier turn is one collapsed row, and the
          effect above scrolls the new turn's heading into view when a
          follow-up starts.

          NEWEST LAST, matching `archiveCurrent()`'s `appendChild`, so the
          rows read oldest first downward into the current turn. Each entry
          is a real `<details>`, so it is keyboard reachable and announced as
          a disclosure without any ARIA of its own, the same mechanism the
          sources list already uses.

          SPACING, UI fix set 7 item 7.4. The product owner on 2026-09-13:
          "The formatting and spacing between the answers is way off."
          The rows carried the prototype's `.thread{gap:14px;margin-top:26px}`
          verbatim, which was right while the thread sat BELOW the answer and
          wrong the moment it moved above: the 26px went to the top, where the
          card's own padding already sits, and the side now facing the new
          question got nothing at all, so a folded row ended hard against the
          heading. The same 26px is simply on the other side now, which is
          what the prototype's own value means for a block that sits above
          rather than below. The 14px gap between rows is unchanged.
        */}
        {previousTurns.length > 0 ? (
          <Box
            data-testid="thread"
            sx={{ display: "flex", flexDirection: "column", gap: 1.75, mb: 3.25 }}
          >
            {previousTurns.map((turn, index) => (
              <FoldedTurn key={`${turn.question}-${index}`} turn={turn} index={index} />
            ))}
          </Box>
        ) : null}

        {/* `ref` for the scroll-into-view above: this block is the top of
            the current turn, so bringing it into view brings the question
            and everything under it with it.

            The status line moved OUT of this block and into `AnswerBody`
            (item 7.4), so an archived turn carries it too. What is left
            here is the question and the control beside it, which belong to
            the live turn alone, and the rule that separates them from the
            body below. */}
        <Box ref={headingRef} sx={{ pb: 2, borderBottom: `1px solid ${designTokens.line}` }}>
          <Box sx={{ display: "flex", gap: 1.75, alignItems: "flex-start" }}>
            <Typography variant="h3" component="h1" sx={{ flex: 1 }}>
              {question}
            </Typography>
            {onNewSearch ? (
              <Box
                component="button"
                type="button"
                onClick={onNewSearch}
                // Set 2, R12: filled blue with white text, the design system's
                // `.btn`, hovering to navy like `.go`.
                sx={{
                  font: "inherit",
                  fontSize: 12.5,
                  fontWeight: 600,
                  px: 1.6,
                  py: 0.6,
                  flex: "none",
                  borderRadius: 0.5,
                  cursor: "pointer",
                  color: designTokens.surface,
                  bgcolor: designTokens.blue,
                  border: `1px solid ${designTokens.blue}`,
                  "&:hover": { bgcolor: designTokens.navy, borderColor: designTokens.navy },
                }}
              >
                New search
              </Box>
            ) : null}
          </Box>
        </Box>

        {/*
          UI fix set 7 (R22). One of two things stands here: the answer,
          or the run that is still producing it.

          `progress` is the SAME `RunProgress` the full-screen run renders,
          passed down by `App` rather than rebuilt, so an inline follow-up
          cannot grow a second visual language for the wait. When the run
          lands, `App` stops passing it and the answer takes its place with
          the thread above unchanged, which is what "the chat continues on
          the same screen" means in DOM terms: this screen never unmounts.

          `mt` rather than the heading block's old `mb`, so the gap under
          the rule belongs to whatever stands here rather than to the
          question above it.
        */}
        <Box sx={{ mt: 2.5 }}>
          {running ? (
            <>
              {progress}
              {/* UI fix set 9, item 9.6: the answer builds under the progress. */}
              {claims.length > 0 ? (
                <Box data-testid="streaming-answer" sx={{ mt: 2.5 }}>
                  <AnswerBody streaming writing={!stopped} question={question} claims={claims} sources={sources} />
                </Box>
              ) : null}
            </>
          ) : (
            <>
              <AnswerBody
                tour
                question={question}
                claims={claims}
                sources={sources}
                meta={meta}
                outcome={outcome}
                outcomeTone={outcomeTone}
                elapsedMs={elapsedMs}
                steps={steps}
                trust={trust}
                refusal={refusal}
                refusalLabel={refusalLabel}
                refusalLink={refusalLink}
                failure={failure}
                capMessage={capMessage}
                systemNotes={systemNotes}
                onFlagSource={onFlagSource}
                flaggedSources={flaggedSources}
              />

              {/*
                F-4.8-D-11. These were the other way round. The prototype's `#tail`
                orders sources, verdict pills, the follow-up form, then the rating,
                which asks "was that useful" AFTER offering the next question rather
                than before it.
              */}

              <Box ref={followUpRef}>{followUp}</Box>
              {/*
                T-4.6-09. `FeedbackSurface` is built here, not passed in as an
                opaque node, so it can be given the real POST target (`runId`) and
                bearer token (`authToken`) it needs. `key={question}` remounts it
                per question, the same reset the old call site in `App.tsx`
                achieved with `key={searchView.question}`, so a rating typed for
                one answer can never linger onto the next.
              */}
              <FeedbackSurface
                key={question}
                runId={runId}
                authToken={authToken}
                flaggedSources={flaggedSources}
              />
            </>
          )}
        </Box>
      </Box>
    </Box>
  );
}

export default AnswerScreen;
