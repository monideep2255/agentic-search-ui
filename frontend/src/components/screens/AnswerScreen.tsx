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

import { Fragment, useState } from "react";
import { Box, Typography } from "@mui/material";
import { visuallyHidden } from "@mui/utils";

import { designTokens, layerColour } from "../../theme";
import type { ReasoningStep } from "./RunScreen";
import { ReasoningLog } from "./ReasoningLog";
import { FeedbackSurface } from "../feedback/FeedbackSurface";

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

export interface TrustSignal {
  kind: "good" | "risk" | "plain";
  label: string;
}

/**
 * One finished turn of a conversation, kept on screen after the next
 * question replaces it (T-4.16-02).
 *
 * Carries exactly what the prototype's `archiveCurrent()` archives: the
 * question asked, the meta line the run reported, and the answer's own
 * claims, sources and verdict. Nothing is recomputed when a turn is
 * rendered from here, so a previous turn always reads as what it was when
 * it landed rather than as what the current run would say.
 */
export interface PreviousTurn {
  question: string;
  meta: string;
  claims: Claim[];
  sources: Source[];
  trust: TrustSignal[];
}

export interface AnswerScreenProps {
  question: string;
  claims: Claim[];
  sources: Source[];
  meta?: string;
  /** The run's outcome word, e.g. "Answered" (F-4.8-D-05). */
  outcome?: string | null;
  /** Wall-clock the run reported, in ms (F-4.8-D-05). */
  elapsedMs?: number | null;
  /** How the outcome word should read (F-4.9-A-03). */
  outcomeTone?: "good" | "warn" | "risk" | null;
  /** The run's own account of what it did, behind `Show work` (F-4.8-D-05). */
  steps?: ReasoningStep[];
  trust?: TrustSignal[];
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
   * Start a fresh search.
   *
   * The run screen has always offered this; the answer screen did not, so the
   * only way back from an answer was the navigation bar. That is an
   * inconsistency a user notices at exactly the moment they are done reading.
   */
  onNewSearch?: () => void;
  /**
   * Guardrail refusal copy, when the question was turned away.
   *
   * F-4.8-J-02: a refusal arrives with a `done` event, which lands the user on
   * this screen immediately, so passing it only to RunScreen rendered a refused
   * question as a blank page. A refusal is a first-class outcome of this
   * product, not an error state, and it must be legible.
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
   * Arrives as its own field rather than inside `refusal`, so this screen
   * can render a real link instead of showing a reader an address they
   * cannot follow. Host-pinned here, at the point the anchor is built.
   */
  refusalLink?: string | null;
  /** A fatal run error, or a dispatch failure. Never rendered as silence. */
  failure?: string | null;
  /** Cap copy, when the run stopped early on its processing budget. */
  capMessage?: string | null;
  /** Disclosures the answer carried: truncation, unaddressed entities. */
  systemNotes?: string[];
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
const ALLOWED_CITATION_HOSTS = [
  "ncbi.nlm.nih.gov",
  "www.ncbi.nlm.nih.gov",
  "pubmed.ncbi.nlm.nih.gov",
  "pmc.ncbi.nlm.nih.gov",
  "clinicaltrials.gov",
  "www.clinicaltrials.gov",
];

/** A citation URL is linkable only if it is https and on an allowed host. */
export function isLinkableCitationUrl(raw: string): boolean {
  try {
    const parsed = new URL(raw);
    return parsed.protocol === "https:" && ALLOWED_CITATION_HOSTS.includes(parsed.hostname);
  } catch {
    return false;
  }
}

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
  label,
  text,
  link,
}: {
  label: string | null;
  text: string | null;
  link: string | null;
}) {
  return (
    <Box
      data-testid="answer-refusal"
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
  onNewSearch,
  refusal = null,
  refusalLabel = null,
  refusalLink = null,
  failure = null,
  capMessage = null,
  systemNotes = [],
  onFlagSource,
  flaggedSources = [],
}: AnswerScreenProps) {
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

  /** The prototype's `s.tag`, naming the layer rather than numbering it. */
  const LAYER_WORD: Record<number, string> = { 1: "graph", 2: "live", 3: "literature" };

  /*
   * The chip's short label, F-4.8-D-04.
   *
   * The prototype's chip reads `1 Gene 672`: the index AND what it points at,
   * so a reader can tell two citations apart without scrolling to the cards.
   * "NCBI " is trimmed exactly as the prototype trims it; nothing else is
   * invented, and a chip whose source is missing falls back to the bare index
   * rather than showing a placeholder.
   */
  const sourceByIndex = new Map(sources.map((source) => [source.n, source]));
  const shortLabel = (n: number): string | null => {
    const source = sourceByIndex.get(n);
    if (!source) return null;
    return source.name.replace(/^NCBI\s+/i, "");
  };

  return (
    // Set 2, R8: full width up to 900, the same as the run screen, so the box
    // keeps one size from progress to answer.
    // `my: auto` centres a short answer vertically, product-owner feedback
    // 2026-09-12. A tall one starts at the top, since auto margins collapse
    // to zero when the content is taller than the space.
    <Box sx={{ width: "100%", maxWidth: 900, mx: "auto", my: "auto", px: 3, py: 3.5 }}>
      <Box
        sx={{
          bgcolor: designTokens.surface,
          border: `1px solid ${designTokens.line}`,
          borderRadius: 1,
          p: { xs: 2.5, sm: 3.25 },
        }}
      >
        <Box sx={{ pb: 2, mb: 2.5, borderBottom: `1px solid ${designTokens.line}` }}>
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
          {/*
            The status strip, F-4.8-D-05. This was the counts alone. The
            prototype's `.summary` leads with the OUTCOME and the elapsed time,
            then the counts, then a `Show work` disclosure that reopens the
            run's own steps, which were otherwise unreachable once the run
            screen was gone.

            Still hooked as `answer-meta` so the rail's per-search counts can be
            asserted to AGREE with this line rather than matching a literal both
            could get wrong independently.
          */}
          {meta || outcome ? (
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                flexWrap: "wrap",
                gap: 1.25,
                mt: 1.25,
                pt: 1.25,
                borderTop: `1px solid ${designTokens.line}`,
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
                data-testid="answer-meta"
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
                      fontWeight: 700,
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
          ) : null}
          {workOpen && steps.length > 0 ? (
            <Box sx={{ mt: 1.75 }}>
              <ReasoningLog steps={steps} testId="work-panel" />
            </Box>
          ) : null}
        </Box>

        {/*
          Rendered on EITHER field, not on `refusal` alone. A refusal whose
          `message` arrives empty still has a label, and a refusal a reader
          can see is the whole requirement; gating on the sentence alone
          would reproduce the silent blank page F-4.8-J-02 closed.
        */}
        {refusal || refusalLabel ? (
          <RefusalBlock label={refusalLabel} text={refusal} link={refusalLink} />
        ) : null}
        {failure ? <Notice testId="answer-failure" tone="risk" text={failure} /> : null}
        {capMessage ? <Notice testId="answer-cap" tone="warn" text={capMessage} /> : null}
        {systemNotes.map((note, i) => (
          <Notice key={i} testId={`answer-note-${i}`} tone="warn" text={note} />
        ))}

        {/*
          The provenance spine runs beside the prose, one segment per claim.

          Segment and claim are two cells of the SAME grid row rather than two
          independently laid out columns, so a segment's height is driven by
          the claim it describes and the two cannot drift apart. The earlier
          form gave each segment `flex: 1` and a `minHeight` in a column of its
          own, which held only while every claim happened to be one line long:
          a two-line claim pushed the prose down while the track kept its own
          rhythm, and by the third claim the grey uncited segment sat beside
          the wrong sentence. A spine that points at the wrong claim is worse
          than no spine, because it asserts a provenance that is not there.

          Found by opening the application and looking at it, the same way the
          `#root` width defect was, and for the same reason: every test here
          asserts segment COUNT, colour and order, and none of them can see
          that two boxes are no longer level with each other.
        */}
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "14px 1fr",
            columnGap: 2.25,
            rowGap: 1.9,
            alignItems: "stretch",
          }}
        >
          {claims.map((claim, index) => (
            <Fragment key={index}>
              {/*
                F-4.8-A-16. This was `aria-hidden`, so the provenance spine,
                which this product's own documentation calls "visible before
                you read a word", did not exist for assistive technology at
                all. Axe reported zero violations the whole time, because axe
                cannot check whether the one signal a product exists to convey
                is conveyed.

                The visual track stays decorative; the MEANING is carried in
                text on each claim instead, so a cited and an uncited claim are
                distinguishable without colour. That is WCAG 1.4.1 (use of
                colour), which no automated rule was ever going to flag here.
              */}
              <Box
                aria-hidden="true"
                data-testid={`spine-segment-${index}`}
                data-layer={claim.layer ?? "none"}
                sx={{
                  width: 6,
                  mx: "auto",
                  borderRadius: 1,
                  alignSelf: "stretch",
                  bgcolor: layerColour(claim.layer).main,
                }}
              />

              <Typography data-testid={`claim-text-${index}`} sx={{ maxWidth: "64ch" }}>
                {claim.text}{" "}
                {/*
                  F-4.9-A-04. This announced one layer for the whole list,
                  taken from the claim's FIRST citation, so a sentence citing a
                  graph edge and a PubTator co-mention told a screen reader
                  that both were layer 1. Each source now names its own.
                */}
                <Box component="span" sx={visuallyHidden}>
                  {claim.citations.length === 0
                    ? "This sentence has no source."
                    : claim.citations
                        .map((n) => `Source ${n}, layer ${sourceByIndex.get(n)?.layer ?? claim.layer}`)
                        .join("; ") + "."}
                </Box>
                {claim.citations.map((n, position) => (
                  <Box
                    key={n}
                    component="span"
                    data-testid={`citation-${n}`}
                    data-claim={index}
                    // The CITATION's own layer, not the claim's (F-4.9-A-04).
                    // `claim.layer` is the first citation's, which is right for
                    // the spine segment (one per claim) and wrong for a chip
                    // (one per source): chip 2 of a graph-plus-literature claim
                    // was painted navy while its own card read "L3 · literature".
                    data-layer={sourceByIndex.get(n)?.layer ?? claim.layer}
                    aria-label={`Source ${n}`}
                    role="note"
                    sx={{
                      ...mono,
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 0.6,
                      fontSize: 11.5,
                      fontWeight: 600,
                      lineHeight: 1.7,
                      px: 0.75,
                      borderRadius: 0.5,
                      border: `1px solid ${designTokens.lineStrong}`,
                      borderLeft: `4px solid ${layerColour(sourceByIndex.get(n)?.layer ?? claim.layer).main}`,
                      bgcolor: layerColour(sourceByIndex.get(n)?.layer ?? claim.layer).wash,
                      ml: position === 0 ? 0 : 0.5,
                    }}
                  >
                    {n}
                    {shortLabel(n) ? (
                      <Box
                        component="span"
                        sx={{ color: designTokens.inkMuted, fontWeight: 400 }}
                      >
                        {shortLabel(n)}
                      </Box>
                    ) : null}
                  </Box>
                ))}
              </Typography>
            </Fragment>
          ))}
        </Box>

        {/*
          F-4.8-D-01. The sources were always expanded, every field of every
          card at once, so a six-source answer became a wall and the sources
          stopped being scannable. The prototype collapses them behind one
          disclosure carrying the count, and collapses each card inside it.
        */}
        {sources.length > 0 ? (
        <Box
          component="details"
          data-testid="sources-disclosure"
          open={sourcesOpen}
          sx={{ mt: 3.5 }}
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
              data-testid="sources-count"
              sx={{
                ...mono,
                fontSize: 11,
                fontWeight: 700,
                color: designTokens.inkMuted,
                bgcolor: designTokens.surfaceSunk,
                border: `1px solid ${designTokens.line}`,
                borderRadius: 999,
                px: 0.75,
              }}
            >
              {sources.length}
            </Box>
          </Box>

        {sources.map((source) => {
          const colour = layerColour(source.layer);
          return (
            <Box
              key={source.n}
              component="details"
              data-testid={`source-${source.n}`}
              data-layer={source.layer}
              open={openSources.includes(source.n)}
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
                  toggleSource(source.n);
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
                    transform: openSources.includes(source.n) ? "rotate(90deg)" : "none",
                    transition: "transform .12s ease",
                  }}
                >
                  ▶
                </Box>
                <Box component="span" sx={{ ...mono, fontWeight: 700, fontSize: 12 }}>
                  [{source.n}]
                </Box>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {source.name}
                </Typography>
                {/*
                  F-4.8-D-02. This read "L1", which a reader has to already
                  know how to decode. The prototype names the layer in words.
                */}
                <Box component="span" sx={{ ...mono, ml: "auto", fontSize: 11.5, color: designTokens.inkMuted }}>
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
                    aria-pressed={flaggedSources.includes(source.n)}
                    onClick={(event: React.MouseEvent) => {
                      // It lives inside the summary, as it does in the
                      // prototype, so without this a flag click also opens or
                      // closes the card under the user's cursor.
                      event.preventDefault();
                      event.stopPropagation();
                      onFlagSource(source.n);
                    }}
                    sx={{
                      font: "inherit",
                      fontSize: 11.5,
                      px: 1,
                      py: 0.3,
                      borderRadius: 0.5,
                      cursor: "pointer",
                      border: "1px solid",
                      borderColor: flaggedSources.includes(source.n)
                        ? designTokens.risk
                        : designTokens.line,
                      color: flaggedSources.includes(source.n)
                        ? designTokens.risk
                        : designTokens.inkFaint,
                      bgcolor: flaggedSources.includes(source.n)
                        ? designTokens.riskWash
                        : designTokens.surface,
                      "&:hover": { color: designTokens.risk, borderColor: designTokens.risk },
                    }}
                  >
                    {flaggedSources.includes(source.n) ? "Flagged" : "Flag: does not support"}
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
                      sx={{ fontSize: 10.5, letterSpacing: "0.1em", color: designTokens.inkFaint }}
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
        ) : null}

        {trust.length > 0 ? (
          <Box
            role="status"
            aria-label="Trust signals"
            sx={{ display: "flex", flexWrap: "wrap", gap: 1, mt: 2.5 }}
          >
            {trust.map((signal) => {
              // The "good" pill's own design-system pair fails WCAG AA: ok
              // (#2E8540) on layer2Wash (#E6F2E8) measures 4.01:1 against a
              // 4.5:1 requirement. The risk pill passes at 7.05:1, so this is
              // specific to the green, which is a lighter hue than the red.
              //
              // Fixed by reading the LABEL in ink while the border, the wash
              // and the check mark keep carrying the green. No new colour is
              // introduced and no token is changed, because the design system
              // is frozen for this phase. Recorded as a finding for the next
              // design pass, which should resolve it at the token level, since
              // this pair is stated in the design system itself.
              const palette =
                signal.kind === "good"
                  ? { fg: designTokens.ink, bg: designTokens.layer2Wash, border: designTokens.ok }
                  : signal.kind === "risk"
                    ? { fg: designTokens.risk, bg: designTokens.riskWash, border: designTokens.risk }
                    : { fg: designTokens.inkMuted, bg: designTokens.surfaceSunk, border: designTokens.line };
              return (
                <Box
                  key={signal.label}
                  data-testid={`trust-${signal.kind}`}
                  sx={{
                    display: "inline-flex",
                    alignItems: "center",
                    borderRadius: 999,
                    px: 1.5,
                    py: 0.5,
                    fontSize: 12.5,
                    fontWeight: 600,
                    color: palette.fg,
                    bgcolor: palette.bg,
                    border: `1px solid ${palette.border}`,
                  }}
                >
                  {signal.label}
                </Box>
              );
            })}
          </Box>
        ) : null}

        {/*
          F-4.8-D-11. These were the other way round. The prototype's `#tail`
          orders sources, verdict pills, the follow-up form, then the rating,
          which asks "was that useful" AFTER offering the next question rather
          than before it.
        */}
        {/*
          T-4.16-02. The conversation thread: every earlier turn of THIS
          search, collapsed, still on the page.

          POSITION IS THE PROTOTYPE'S, not a choice made here. Its answer
          section orders the tail `sources`, `verdict`, `thread`, then the
          follow-up form, so the CURRENT answer stays at the top where a
          reader lands, earlier turns sit beneath it, and the input that
          continues the conversation comes last. Rendering the thread above
          the current answer would push the thing just asked for off screen
          as the conversation grew.

          NEWEST LAST, matching `archiveCurrent()`'s `appendChild`. Each
          entry is a real `<details>`, so it is keyboard reachable and
          announced as a disclosure without any ARIA of its own, the same
          mechanism the sources list already uses.
        */}
        {previousTurns.length > 0 ? (
          <Box
            data-testid="thread"
            sx={{ display: "flex", flexDirection: "column", gap: 1.75, mt: 3.25 }}
          >
            {previousTurns.map((turn, index) => (
              <Box
                key={`${turn.question}-${index}`}
                component="details"
                data-testid={`previous-turn-${index}`}
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
                </Box>
                <Box
                  sx={{
                    px: 1.75,
                    pt: 0.5,
                    pb: 2,
                    bgcolor: designTokens.surface,
                    borderTop: `1px solid ${designTokens.line}`,
                  }}
                >
                  {turn.claims.map((claim, claimIndex) => (
                    <Typography
                      key={claimIndex}
                      sx={{ fontSize: 16, mt: claimIndex === 0 ? 2 : 1.5, maxWidth: "64ch" }}
                    >
                      {claim.text}
                    </Typography>
                  ))}
                  <Typography
                    variant="body2"
                    sx={{ mt: 1.75, color: designTokens.inkMuted }}
                  >
                    {turn.sources.length === 1
                      ? "1 source"
                      : `${turn.sources.length} sources`}
                    {turn.trust.length > 0
                      ? ` · ${turn.trust.map((signal) => signal.label).join(" · ")}`
                      : ""}
                  </Typography>
                </Box>
              </Box>
            ))}
          </Box>
        ) : null}

        {followUp}
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
      </Box>
    </Box>
  );
}

export default AnswerScreen;
