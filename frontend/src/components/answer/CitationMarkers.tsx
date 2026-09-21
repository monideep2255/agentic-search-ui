/**
 * Inline citation markers: small superscript numbers after a sentence.
 *
 * PRODUCT-OWNER REQUEST, 2026-09-14, and a deliberate change to the design
 * system's citation chip (`docs/build/design/design-system/identity/
 * citation-chip.html`, which records the change and its date):
 *
 *   "the inline citations overwhelm the answer to be honest. Too big
 *   citations that overwhelm the answer."
 *   "Citation is important but not when the user has to read the answer."
 *
 * The boxed chip (`1 ncbi_efetch MedGen:C0346153`) carried the index, the
 * source id, a 4px layer edge and a wash, and a summary sentence carried up
 * to thirteen of them, so the chips took more room than the words. Per-claim
 * citation stays, because `CLAUDE.md` makes it non-negotiable. What changes is
 * where the detail lives: the sentence carries a quiet number, the number
 * opens a small card with the source, its id, its layer and its record link,
 * and the full provenance stays in the Sources section below the answer.
 *
 * THE COLLAPSE RULE, `collapseCitations` below:
 *
 *   one to three sources  a comma list, one marker each: 1, 2, 3
 *   four or more          ONE marker covering all of them: 1–13 when the
 *                         indices are consecutive, otherwise "1 +5" (the
 *                         first index and how many more). Its card lists
 *                         every source.
 *
 * Three is where a comma list stops being scannable at 11px and starts
 * rebuilding the wall the product owner complained about; a range keeps the
 * whole set one keyboard stop, and nothing is dropped because the card lists
 * every member.
 *
 * ACCESSIBILITY. Each marker is a real `<button>`, so it is reachable by
 * keyboard and announced as a control. Its accessible name comes from
 * visually hidden text inside it, "Source 1, layer 2", or for a range
 * "Sources 1 to 13: Source 1, layer 2; ...", so a screen reader hears which
 * source and which layer without colour (WCAG 1.4.1). The visible digits are
 * `aria-hidden` so they are not read twice. The card opens on hover, on
 * keyboard focus and on tap, and closes on Escape, on blur, on an outside
 * press, on scroll and on pointer leave.
 *
 * EVERY VISUAL VALUE NAMES ITS TOKEN (`design-consistency`):
 *
 *   marker type     mono 11px, weight 700, .06em tracking: the layer badge's
 *                   `.n` rule in `identity/layer-badges.html`, which is also
 *                   the theme's `overline` size
 *   marker colour   `layerColour(n).main`, the same colour `.n` uses; a range
 *                   spanning several layers reads in `designTokens.inkMuted`
 *   comma           `designTokens.inkFaint`
 *   focus ring      3px `designTokens.link`, offset 2px, radius 4px: the
 *                   prototype's global `:focus-visible` rule (app.html:25)
 *   card            `PersonaInfo`'s card in `shell/PersonaChip.tsx`, the
 *                   nearest designed neighbour for a small anchored card:
 *                   `surface` ground, `line` border, 8px radius (`--r`), the
 *                   same shadow, padding 12px 14px, width 280
 *   card rows       layer dot 12px with 3px radius (`.dot`, layer-badges),
 *                   `L2 · live` in mono 11px bold layer colour (`.n`), name
 *                   13.5px weight 600 (`.pcap` and the card heading), tool in
 *                   mono 12.5px `inkMuted` (the source card's token rows),
 *                   link `designTokens.link` 12.5px (the card's Wikipedia
 *                   link), off-host note 11.5px `designTokens.risk` (the
 *                   source card's own "Not linked" line)
 *
 * One value has no design token, named rather than hidden: the card's
 * `maxHeight` of `min(60vh, 320px)` for a thirteen-source range. It is a
 * layout bound, not a colour, radius or type size.
 */

import type React from "react";
import { useEffect, useId, useRef, useState } from "react";
import { Box } from "@mui/material";
import { visuallyHidden } from "@mui/utils";

import { designTokens, layerColour } from "../../theme";

export type CitationLayer = 1 | 2 | 3;

/** The fields of a source this card reads. A subset of `AnswerScreen`'s `Source`. */
export interface CitationSource {
  n: number;
  layer: CitationLayer;
  name: string;
  tool: string;
  url: string;
}

/** The prototype's `s.tag`, naming the layer rather than numbering it. */
export const LAYER_WORD: Record<number, string> = { 1: "graph", 2: "live", 3: "literature" };

/** More than this many sources on one sentence collapse into a single marker. */
export const COMMA_LIST_MAX = 3;

/**
 * Hosts a citation may link to.
 *
 * F-4.8-A-24. Moved here from `AnswerScreen.tsx` unchanged, so the marker card
 * and the source card share one list rather than two that could drift.
 * `production-standards` requires a host-pinned check rather than a scheme
 * check, on whichever side of the stack builds the link.
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
 * Group one sentence's citations into markers.
 *
 * Duplicates are dropped, first occurrence kept, so a repeated index cannot
 * render two markers pointing at the same card.
 */
export function collapseCitations(citations: number[]): number[][] {
  const unique = citations.filter((n, i) => citations.indexOf(n) === i);
  if (unique.length === 0) return [];
  if (unique.length <= COMMA_LIST_MAX) return unique.map((n) => [n]);
  return [unique];
}

function isConsecutive(sorted: number[]): boolean {
  return sorted.every((n, i) => i === 0 || n === sorted[i - 1] + 1);
}

/** What the marker SHOWS: "2", "1–13", or "1 +5" for a non-consecutive set. */
export function markerLabel(members: number[]): string {
  if (members.length === 1) return String(members[0]);
  const sorted = [...members].sort((a, b) => a - b);
  if (isConsecutive(sorted)) return `${sorted[0]}–${sorted[sorted.length - 1]}`;
  return `${sorted[0]} +${sorted.length - 1}`;
}

/**
 * What the marker SAYS to assistive technology.
 *
 * Never the visible glyphs: "1–13" is read inconsistently across screen
 * readers, so a range is spoken "Sources 1 to 13", then every source with its
 * own layer, the F-4.9-A-04 rule that each source names its OWN layer.
 */
export function markerSpokenName(
  members: number[],
  layerOf: (n: number) => CitationLayer | null,
): string {
  const each = (n: number) => `Source ${n}, layer ${layerOf(n) ?? "unknown"}`;
  if (members.length === 1) return each(members[0]);
  const sorted = [...members].sort((a, b) => a - b);
  const head = isConsecutive(sorted)
    ? `Sources ${sorted[0]} to ${sorted[sorted.length - 1]}`
    : `Sources ${sorted.slice(0, -1).join(", ")} and ${sorted[sorted.length - 1]}`;
  return `${head}: ${sorted.map(each).join("; ")}`;
}

const MONO =
  'ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace';

/**
 * Screen-reader text that is kept OUT of a copy.
 *
 * The two statements that must stay words for assistive technology ("This
 * sentence has no source.", "2 sources pending.") have no control to hang an
 * `aria-label` on, so they stay text nodes; `user-select: none` keeps a
 * reader's selection from picking them up when the answer is copied.
 */
const SCREEN_READER_ONLY = { ...visuallyHidden, userSelect: "none" } as const;

/** The card's width, `PersonaInfo`'s. */
const CARD_WIDTH = 280;
/** The page gutter the card keeps from either screen edge, `PersonaInfo`'s 32px total. */
const CARD_GUTTER = 16;

interface MarkerProps {
  members: number[];
  sourceByIndex: Map<number, CitationSource>;
  fallbackLayer: CitationLayer | null;
  testIdPrefix: string;
  claimIndex: number;
}

function CitationMarker({
  members,
  sourceByIndex,
  fallbackLayer,
  testIdPrefix,
  claimIndex,
}: MarkerProps) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);
  const wrapRef = useRef<HTMLSpanElement | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cardId = useId();

  const layerOf = (n: number): CitationLayer | null => sourceByIndex.get(n)?.layer ?? fallbackLayer;
  const layers = new Set(members.map(layerOf));
  const sharedLayer = layers.size === 1 ? [...layers][0] : null;
  const single = members.length === 1;
  const first = [...members].sort((a, b) => a - b)[0];

  const cancelClose = () => {
    if (closeTimer.current !== null) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  };

  /*
   * FIXED rather than absolute positioning. A marker inside a table row sits
   * in an `overflow-x: auto` box, which would clip an absolutely positioned
   * card; fixed escapes it. The left edge is clamped so the card never runs
   * past either screen edge at 390px, which is the no-sideways-scroll rule.
   */
  const show = () => {
    cancelClose();
    const button = buttonRef.current;
    if (button && typeof window !== "undefined") {
      const rect = button.getBoundingClientRect();
      const width = Math.min(CARD_WIDTH, window.innerWidth - CARD_GUTTER * 2);
      const left = Math.max(
        CARD_GUTTER,
        Math.min(rect.left, window.innerWidth - width - CARD_GUTTER),
      );
      setPosition({ top: rect.bottom + 6, left });
    }
    setOpen(true);
  };

  const hideSoon = () => {
    cancelClose();
    // A short grace so a pointer crossing the gap onto the card, to reach
    // its link, does not close it on the way.
    closeTimer.current = setTimeout(() => setOpen(false), 150);
  };

  useEffect(() => cancelClose, []);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent | TouchEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    const onMove = () => setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("touchstart", onDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", onMove, true);
    window.addEventListener("resize", onMove);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("touchstart", onDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", onMove, true);
      window.removeEventListener("resize", onMove);
    };
  }, [open]);

  const colour = sharedLayer ? layerColour(sharedLayer).main : designTokens.inkMuted;

  return (
    <Box
      component="span"
      ref={wrapRef}
      onMouseEnter={show}
      onMouseLeave={hideSoon}
      onBlur={(event: React.FocusEvent<HTMLSpanElement>) => {
        const next = event.relatedTarget as Node | null;
        if (!next || !wrapRef.current?.contains(next)) setOpen(false);
      }}
      sx={{ position: "relative", display: "inline" }}
    >
      <Box
        component="button"
        type="button"
        ref={buttonRef}
        data-testid={single ? `${testIdPrefix}citation-${first}` : `${testIdPrefix}citation-group-${first}`}
        data-claim={claimIndex}
        data-layer={single ? (layerOf(first) ?? "none") : (sharedLayer ?? "mixed")}
        data-citations={members.join(",")}
        aria-expanded={open}
        aria-controls={open ? cardId : undefined}
        /*
         * 2026-09-14, product-owner defect: copying the answer yielded
         * "1–4Sources 1 to 4: Source 1, layer 2; …" because the name was a
         * visually hidden TEXT NODE inside the selectable prose. The same
         * name now travels as `aria-label`, which is not text and is not
         * copied. The visible digits stay `aria-hidden` so nothing is read
         * twice.
         */
        aria-label={markerSpokenName(members, layerOf)}
        onFocus={show}
        onClick={show}
        sx={{
          font: "inherit",
          fontFamily: MONO,
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: "0.06em",
          lineHeight: 1,
          color: colour,
          bgcolor: "transparent",
          border: 0,
          p: 0,
          cursor: "pointer",
          verticalAlign: "baseline",
          "&:hover": { textDecoration: "underline" },
          "&:focus-visible": {
            outline: `3px solid ${designTokens.link}`,
            outlineOffset: "2px",
            borderRadius: "4px",
          },
        }}
      >
        <Box component="span" aria-hidden="true">
          {markerLabel(members)}
        </Box>
      </Box>

      {open ? (
        <Box
          component="span"
          id={cardId}
          data-testid={`${testIdPrefix}cite-popover-${first}`}
          onMouseEnter={cancelClose}
          onMouseLeave={hideSoon}
          sx={{
            position: "fixed",
            top: position?.top ?? 0,
            left: position?.left ?? 0,
            display: "block",
            width: CARD_WIDTH,
            maxWidth: `calc(100vw - ${CARD_GUTTER * 2}px)`,
            maxHeight: "min(60vh, 320px)",
            overflowY: "auto",
            bgcolor: designTokens.surface,
            border: `1px solid ${designTokens.line}`,
            borderRadius: 1,
            boxShadow: "0 14px 34px rgba(0,0,0,.2)",
            zIndex: 60,
            p: "12px 14px",
            color: designTokens.ink,
            textAlign: "left",
            whiteSpace: "normal",
            fontFamily: "inherit",
            fontSize: 13.5,
            fontWeight: 400,
            letterSpacing: "normal",
            lineHeight: 1.45,
          }}
        >
          {[...members]
            .sort((a, b) => a - b)
            .map((n, row) => (
              <CardRow
                key={n}
                n={n}
                source={sourceByIndex.get(n) ?? null}
                layer={layerOf(n)}
                divided={row > 0}
                testId={`${testIdPrefix}cite-popover-row-${n}`}
              />
            ))}
        </Box>
      ) : null}
    </Box>
  );
}

function CardRow({
  n,
  source,
  layer,
  divided,
  testId,
}: {
  n: number;
  source: CitationSource | null;
  layer: CitationLayer | null;
  divided: boolean;
  testId: string;
}) {
  const colour = layerColour(layer).main;
  const linkable = source !== null && isLinkableCitationUrl(source.url);
  return (
    <Box
      component="span"
      data-testid={testId}
      sx={{
        display: "flex",
        flexDirection: "column",
        gap: "4px",
        ...(divided
          ? { mt: "8px", pt: "8px", borderTop: `1px solid ${designTokens.line}` }
          : {}),
      }}
    >
      <Box component="span" sx={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <Box
          component="span"
          aria-hidden="true"
          sx={{ width: 12, height: 12, borderRadius: "3px", flex: "none", bgcolor: colour }}
        />
        <Box
          component="span"
          sx={{ fontFamily: MONO, fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", color: colour }}
        >
          [{n}] L{layer ?? "?"} · {layer ? LAYER_WORD[layer] : "source"}
        </Box>
      </Box>
      {source ? (
        <>
          <Box component="span" sx={{ fontWeight: 600, color: designTokens.ink, wordBreak: "break-word" }}>
            {source.name}
          </Box>
          <Box
            component="span"
            sx={{ fontFamily: MONO, fontSize: 12.5, color: designTokens.inkMuted, wordBreak: "break-all" }}
          >
            {source.tool}
          </Box>
          {linkable ? (
            <Box
              component="a"
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Open the record for source ${n}, opens in a new tab`}
              sx={{ fontSize: 12.5, color: designTokens.link }}
            >
              Open the record
            </Box>
          ) : (
            <Box component="span" sx={{ fontSize: 11.5, color: designTokens.risk }}>
              Not linked: this URL is not on a recognised NCBI host.
            </Box>
          )}
        </>
      ) : (
        <Box component="span" sx={{ color: designTokens.inkMuted }}>
          Source {n} is listed under Sources below.
        </Box>
      )}
    </Box>
  );
}

export interface CitationMarkersProps {
  citations: number[];
  sources: CitationSource[] | Map<number, CitationSource>;
  /** The claim's own layer, used only when a citation has no source card behind it. */
  claimLayer: CitationLayer | null;
  claimIndex: number;
  testIdPrefix?: string;
  /**
   * Citations this sentence declared whose frames have not arrived yet, while
   * the run is still streaming. Rendered as quiet pending markers: `inkFaint`,
   * not focusable, no card, spoken "sources pending". Zero or absent once
   * every citation has resolved, and always absent on a landed answer.
   */
  pending?: number;
}

/**
 * One sentence's markers, or for an uncited sentence the hidden "no source"
 * statement that keeps a cited and an uncited claim distinguishable without
 * colour (F-4.8-A-16).
 */
export function CitationMarkers({
  citations,
  sources,
  claimLayer,
  claimIndex,
  testIdPrefix = "",
  pending = 0,
}: CitationMarkersProps) {
  if (citations.length === 0 && pending > 0) {
    /*
     * The same superscript as a real marker, in `designTokens.inkFaint`, with
     * a middle dot per pending source (the dot the trust line already uses as
     * a separator), capped at three so a long list cannot rebuild the wall.
     * A `<sup>` rather than a button: nothing to open yet, so nothing to
     * focus. The words are for assistive technology only.
     */
    return (
      <Box
        component="sup"
        data-testid={`${testIdPrefix}citation-pending-${claimIndex}`}
        sx={{
          fontFamily: MONO,
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: "0.06em",
          lineHeight: 0,
          verticalAlign: "super",
          whiteSpace: "nowrap",
          color: designTokens.inkFaint,
        }}
      >
        <Box component="span" aria-hidden="true">
          {"·".repeat(Math.min(pending, COMMA_LIST_MAX))}
        </Box>
        <Box component="span" sx={SCREEN_READER_ONLY}>
          {pending === 1 ? "Source pending." : `${pending} sources pending.`}
        </Box>
      </Box>
    );
  }
  if (citations.length === 0) {
    return (
      <Box component="span" data-uncited="true" sx={SCREEN_READER_ONLY}>
        This sentence has no source.
      </Box>
    );
  }
  const sourceByIndex =
    sources instanceof Map ? sources : new Map(sources.map((source) => [source.n, source]));
  const groups = collapseCitations(citations);
  return (
    <Box
      component="sup"
      data-testid={`${testIdPrefix}citation-markers-${claimIndex}`}
      sx={{ fontSize: 11, lineHeight: 0, verticalAlign: "super", whiteSpace: "nowrap" }}
    >
      {/*
        A WORD JOINER (U+2060) ahead of the first marker. A button is an
        atomic inline, which lets a line break fall between the last word and
        its marker, so at 390px a lone "8" could wrap onto a line of its own
        (seen on the 2026-09-14 screenshot). The joiner forbids that break;
        `user-select: none` keeps it out of a copy.
      */}
      <Box component="span" aria-hidden="true" sx={{ userSelect: "none" }}>
        {"\u2060"}
      </Box>
      {groups.map((members, position) => (
        <Box component="span" key={members.join("-")}>
          {position > 0 ? (
            <Box component="span" aria-hidden="true" sx={{ color: designTokens.inkFaint }}>
              ,{" "}
            </Box>
          ) : null}
          <CitationMarker
            members={members}
            sourceByIndex={sourceByIndex}
            fallbackLayer={claimLayer}
            testIdPrefix={testIdPrefix}
            claimIndex={claimIndex}
          />
        </Box>
      ))}
    </Box>
  );
}

export default CitationMarkers;
