/**
 * The named scientist persona, build phase 4.8, ticket T-4.8-03.
 *
 * Technical specification 12.7 and 14.2. Presentation only: the persona never
 * changes which tools run, which records are retrieved, or what the trust
 * signal says. Section 14.1's personalization firewall puts personalization in
 * orchestration and synthesis style, never in grounding.
 *
 * The spec is explicit about the register, and it is a product decision rather
 * than a taste one: "a small, static label and a muted icon, never an animated
 * mascot or a cartoon avatar", on the 2026-07-21 reasoning that the persona
 * should build connection without undercutting the provenance-forward
 * positioning. So there is no animation here, and there never should be.
 *
 * T-4.5-10: no longer a stub. The name comes from `persona_name` on the
 * POST /v1/query response, resolved server-side from the curated deceased-only
 * list in `core/persona.py`. The placeholder list and its local draw are gone:
 * a client-side draw could not know which scientist an ACCOUNT is bound to, so
 * it would have shown a different name than the CLI and GraphQL surfaces do
 * for the same user.
 *
 * Renders nothing when `name` is null, which is the window before the first
 * run returns. A placeholder there would visibly change once the first answer
 * lands, which reads as a bug.
 *
 * THE INFO AFFORDANCE (2026-09-13 product-owner request): visitors do not
 * know who "Mendel" or "Franklin" is. A small circled-"i" button sits after
 * the name and opens a short dialog naming the persona's achievements, with
 * a link out to Wikipedia. This surface has NO design card of its own: the
 * design system's `persona.html` shows only the chip and the per-step
 * caption, with no affordance to expand either one. Per
 * `.claude/rules/design-consistency.md`'s "when a surface has no design, say
 * so" section, that gap is named here rather than filled silently, and the
 * dialog is built from the nearest designed neighbour instead: `AccountMenu`'s
 * popover (outside-click and Escape close it, the same surface tokens, the
 * same shadow), since a small anchored card reading account information is
 * the closest precedent this app already ships. Every colour below reads
 * from `designTokens`; nothing here is a new hex, radius, or shadow.
 *
 * The chip itself is UNCHANGED when `about` is null or absent, which is the
 * graceful-degradation path for an older backend or an existing test mock
 * that returns `{persona_name}` alone: no info button renders, so the chip
 * is byte-identical to the pre-2026-09-13 shape.
 */

import { useEffect, useId, useRef, useState } from "react";
import { Box, Typography } from "@mui/material";

import { designTokens } from "../../theme";

/** The muted icon the spec calls for: a plain figure, not a face, not a mascot. */
function PersonIcon({ size = 12 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <circle cx="8" cy="5.2" r="2.9" />
      <path d="M2.6 14a5.4 5.4 0 0 1 10.8 0z" />
    </svg>
  );
}

/** A 14px circled "i", the chip's info affordance. Inherits `currentColor`. */
function InfoIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="6.3" stroke="currentColor" strokeWidth="1.2" />
      <path
        d="M8 7.1v3.9M8 5v.01"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
    </svg>
  );
}

/**
 * Host-pinned check for the Wikipedia link, per `production-standards`'
 * source-url rule: a citation-shaped URL that only checks for `https://` can
 * be spoofed to point anywhere. Exported so it carries its own test rather
 * than being asserted only through the rendered component.
 *
 * Returns false rather than throwing on a malformed URL, since the caller's
 * job here is "render the link or don't", never to surface a parse error.
 */
export function isPinnedWikipediaUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" && parsed.hostname === "en.wikipedia.org";
  } catch {
    return false;
  }
}

export interface PersonaChipProps {
  /** The server-assigned persona, or null before the first run returns. */
  name: string | null;
  /** `onNavy` for the app bar; `onLight` for a plain surface. */
  variant?: "onLight" | "onNavy";
  /**
   * One or two sentences on the persona's achievements, at most 160
   * characters. Null omits the info button entirely, which is the
   * graceful-degradation path for an older backend.
   */
  about?: string | null;
  /** The persona's Wikipedia page. Rendered as a link only when it passes `isPinnedWikipediaUrl`. */
  wikipedia?: string | null;
}

export function PersonaChip({ name, variant = "onNavy", about = null, wikipedia = null }: PersonaChipProps) {
  const onNavy = variant === "onNavy";
  const [open, setOpen] = useState(false);
  const dialogId = useId();
  const wrapRef = useRef<HTMLDivElement | null>(null);

  // Outside click and Escape close the dialog, the same mechanics
  // `AccountMenu`'s popover already uses, so the two anchored cards in this
  // app bar behave identically rather than each inventing their own rules.
  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (name === null) return null;

  const infoIconColor = onNavy ? "rgba(255,255,255,.7)" : designTokens.inkFaint;
  const showLink = wikipedia !== null && isPinnedWikipediaUrl(wikipedia);

  return (
    <Box
      ref={wrapRef}
      data-testid="persona-chip"
      sx={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        gap: 1,
        borderRadius: 999,
        px: 1.6,
        py: 0.6,
        pl: 0.9,
        border: "1px solid",
        borderColor: onNavy ? "rgba(255,255,255,.28)" : designTokens.line,
        bgcolor: onNavy ? "rgba(255,255,255,.10)" : designTokens.surface,
        // inkOnNavyMute (#A9C3DC) fails WCAG AA here: the chip's own
        // translucent background composites to ~#36659E over the app bar, and
        // that pair measures about 2.7:1 against a 4.5:1 requirement. The
        // bright ink token measures 5.4:1 on the same ground. Caught by the
        // e2e contrast check, not by eye.
        color: onNavy ? designTokens.inkOnNavy : designTokens.inkMuted,
        whiteSpace: "nowrap",
      }}
    >
      <Box
        component="span"
        sx={{
          width: 22,
          height: 22,
          borderRadius: "50%",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          flex: "none",
          border: "1px solid",
          borderColor: onNavy ? "rgba(255,255,255,.28)" : designTokens.line,
          bgcolor: onNavy ? "rgba(255,255,255,.14)" : designTokens.surfaceSunk,
          color: onNavy ? "#FFFFFF" : designTokens.inkFaint,
        }}
      >
        <PersonIcon />
      </Box>
      <Typography variant="body2" component="span" sx={{ fontSize: 13 }}>
        Working as{" "}
        <Box component="b" sx={{ fontWeight: 700, color: onNavy ? "#FFFFFF" : designTokens.ink }}>
          {name}
        </Box>
      </Typography>

      {about !== null ? (
        <Box
          component="button"
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-label={`About ${name}`}
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-controls={open ? dialogId : undefined}
          sx={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            flex: "none",
            width: 18,
            height: 18,
            p: 0,
            border: 0,
            background: "none",
            cursor: "pointer",
            color: infoIconColor,
            borderRadius: "50%",
            "&:hover": {
              color: onNavy ? "#FFFFFF" : designTokens.ink,
            },
          }}
        >
          <InfoIcon />
        </Box>
      ) : null}

      {open && about !== null ? (
        <Box
          id={dialogId}
          role="dialog"
          aria-labelledby={`${dialogId}-heading`}
          sx={{
            position: "absolute",
            top: "calc(100% + 9px)",
            right: 0,
            width: 280,
            maxWidth: "calc(100vw - 32px)",
            "@media (max-width: 720px)": {
              width: "calc(100vw - 32px)",
            },
            bgcolor: designTokens.surface,
            border: `1px solid ${designTokens.line}`,
            borderRadius: 1,
            boxShadow: "0 14px 34px rgba(0,0,0,.2)",
            zIndex: 60,
            p: "12px 14px",
            color: designTokens.ink,
            textAlign: "left",
            // The chip sets `whiteSpace: "nowrap"` so the label never
            // breaks, and this card sits inside it, so it inherited that
            // and the about line ran off the right edge of the page
            // (measured live at 1280px: 1555px of scroll width). Reset
            // here so the card wraps like ordinary text.
            whiteSpace: "normal",
          }}
        >
          <Typography
            id={`${dialogId}-heading`}
            component="p"
            sx={{ fontSize: 13.5, fontWeight: 700, color: designTokens.ink, m: 0, mb: "4px" }}
          >
            {name}
          </Typography>
          <Typography
            component="p"
            sx={{ fontSize: 13.5, color: designTokens.inkMuted, m: 0, lineHeight: 1.45 }}
          >
            {about}
          </Typography>
          {showLink ? (
            <Typography
              component="a"
              href={wikipedia as string}
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                display: "inline-block",
                mt: "8px",
                fontSize: 12.5,
                color: designTokens.link,
                textDecoration: "none",
                "&:hover": { textDecoration: "underline" },
              }}
            >
              Learn more on Wikipedia
            </Typography>
          ) : null}
        </Box>
      ) : null}
    </Box>
  );
}

/**
 * What each loop step is called while it is the live one.
 *
 * Section 12.7: the caption updates from the active step's own `narrative`
 * field. It is a caption on work that is genuinely happening, not a mascot
 * with a script, which is why the wording describes the step rather than
 * performing enthusiasm.
 */
export const STEP_NARRATIVE: Record<string, string> = {
  Guard: "is checking the question is answerable and in scope",
  Think: "is working out what the question is asking for",
  Plan: "is choosing which sources to read",
  Act: "is reading the records",
  Write: "is writing the answer, citing as it goes",
};

export interface PersonaCaptionProps {
  /** Server-assigned persona (T-4.5-10); null before the first run returns. */
  name: string | null;
  /** The live step, or null when no run is in flight. */
  step: string | null;
}

/** The per-step caption on the run screen. Renders nothing when idle. */
export function PersonaCaption({ name, step }: PersonaCaptionProps) {
  if (!step || name === null) return null;
  return (
    <Box
      data-testid="persona-caption"
      sx={{ display: "flex", alignItems: "center", gap: 1.2, mt: 2, minHeight: 22 }}
    >
      <Box
        component="span"
        sx={{
          width: 20,
          height: 20,
          borderRadius: "50%",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          flex: "none",
          border: `1px solid ${designTokens.line}`,
          bgcolor: designTokens.surfaceSunk,
          color: designTokens.inkFaint,
        }}
      >
        <PersonIcon />
      </Box>
      <Typography variant="body2" sx={{ color: designTokens.inkMuted }}>
        <Box component="b" sx={{ fontWeight: 700, color: designTokens.ink }}>
          {name}
        </Box>{" "}
        {STEP_NARRATIVE[step] ?? "is working"}
      </Typography>
    </Box>
  );
}

export default PersonaChip;
