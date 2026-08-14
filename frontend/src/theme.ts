/**
 * The MUI theme, build phase 4.8, ticket T-4.8-02.
 *
 * Every colour here is transcribed from the design system's own token block,
 * `docs/build/design/design-system/foundations/colors.html`, which is itself
 * generated from the approved prototype. The premise gate asserts each value
 * against that source, so a nudged blue fails the build rather than shipping.
 *
 * Two decisions are load-bearing and are enforced here rather than left to
 * convention:
 *
 *   1. One committed light theme. No dark palette, product-owner decision of
 *      2026-08-12. MUI defaults to light, but the mode is set explicitly so a
 *      future `useMediaQuery`-driven palette cannot be introduced by accident
 *      without failing the gate.
 *
 *   2. The three data layers are first-class palette entries, not ad-hoc
 *      colours passed at call sites. Layer colour is the product's identity:
 *      it tells a reader where a fact came from, and therefore how fresh it is
 *      and how it was established. A component that needs a layer colour reads
 *      it from here.
 *
 * Red is reserved. It appears on the risk tier and on refusals and nowhere
 * else, so a high-risk clinical claim never competes with a layer colour for
 * the same meaning.
 */

import { createTheme } from "@mui/material/styles";
import type { Theme } from "@mui/material/styles";

/**
 * The raw design tokens, exactly as the design system states them.
 *
 * Exposed on the theme as `designTokens` so components can reach a token that
 * has no natural MUI palette slot (the three layer colours, the two ink
 * shades) without hardcoding a hex anywhere in the component tree.
 */
export const designTokens = {
  // grounds
  canvas: "#F0F0F0",
  canvasDeep: "#E4E6E8",
  surface: "#FFFFFF",
  surfaceSunk: "#F7F8F9",

  // lines
  line: "#D6D7D9",
  lineStrong: "#A9AEB1",

  // ink
  ink: "#1B1B1B",
  inkMuted: "#565C65",
  inkFaint: "#71767A",
  inkOnNavy: "#F3F6F9",
  inkOnNavyMute: "#A9C3DC",

  // brand
  navy: "#112F4E",
  navyDeep: "#0B2138",
  blue: "#205493",
  link: "#0071BC",

  // the layer system: this is the identity, not decoration
  layer1: "#205493", // knowledge graph, the System 1 and 2 ingest
  layer2: "#2E8540", // live NCBI APIs
  layer3: "#4C2C92", // enrichment: literature and trials
  layer1Wash: "#E7EEF6",
  layer2Wash: "#E6F2E8",
  layer3Wash: "#EEEAF6",

  // semantic, never used as an accent
  risk: "#981B1E",
  riskWash: "#F8E9E9",
  warn: "#7A5900",
  warnWash: "#FDF3D9",
  ok: "#2E8540",
} as const;

export type DesignTokens = typeof designTokens;

/** Layer number to its colour and wash, so no component maps this by hand. */
export const layerColour = (layer: 1 | 2 | 3 | null) => {
  switch (layer) {
    case 1:
      return { main: designTokens.layer1, wash: designTokens.layer1Wash };
    case 2:
      return { main: designTokens.layer2, wash: designTokens.layer2Wash };
    case 3:
      return { main: designTokens.layer3, wash: designTokens.layer3Wash };
    default:
      // An uncited claim. Deliberately the strong line colour rather than a
      // layer colour: the point of the provenance spine is that a gap is
      // visible, so it must not read as one of the three.
      return { main: designTokens.lineStrong, wash: designTokens.surfaceSunk };
  }
};

const SANS = [
  '"Public Sans"',
  "-apple-system",
  "BlinkMacSystemFont",
  '"Segoe UI"',
  "Roboto",
  '"Helvetica Neue"',
  "Arial",
  "sans-serif",
].join(",");

/**
 * Monospace marks a string transcribed exactly: accessions, rsIDs, concept
 * ids, predicate names, tool names, dates, record URLs.
 *
 * Gene symbols are deliberately NOT in that set. Product-owner decision of
 * 2026-08-12: BRCA1 inside a sentence is read as a word, and three typeface
 * switches in three sentences breaks the line rhythm for no informational
 * gain. The test is not "is this biomedical" but "would someone compare this
 * character by character".
 */
const MONO = [
  "ui-monospace",
  '"SF Mono"',
  "SFMono-Regular",
  "Menlo",
  "Consolas",
  '"Liberation Mono"',
  "monospace",
].join(",");

const base = createTheme({
  palette: {
    mode: "light",
    primary: { main: designTokens.blue, dark: designTokens.navy, contrastText: "#FFFFFF" },
    secondary: { main: designTokens.link },
    error: { main: designTokens.risk },
    warning: { main: designTokens.warn },
    success: { main: designTokens.ok },
    info: { main: designTokens.link },
    background: { default: designTokens.canvas, paper: designTokens.surface },
    text: {
      primary: designTokens.ink,
      secondary: designTokens.inkMuted,
      disabled: designTokens.inkFaint,
    },
    divider: designTokens.line,
  },

  typography: {
    fontFamily: SANS,
    fontSize: 16,
    // The landing headline is the primary voice of the app and has to hold its
    // own against the navy hero behind it, so it is set larger and tighter
    // than a section heading rather than smaller.
    h1: { fontSize: "clamp(32px, 4.8vw, 52px)", fontWeight: 800, letterSpacing: "-0.034em", lineHeight: 1.1 },
    h2: { fontSize: "clamp(24px, 3.1vw, 33px)", fontWeight: 800, letterSpacing: "-0.022em", lineHeight: 1.15 },
    h3: { fontSize: "19px", fontWeight: 700, letterSpacing: "-0.015em" },
    h4: { fontSize: "15px", fontWeight: 700 },
    body1: { fontSize: "16px", lineHeight: 1.65 },
    body2: { fontSize: "13.5px", lineHeight: 1.6 },
    caption: { fontSize: "12.5px" },
    // The uppercase micro-label used for section eyebrows and field names.
    overline: {
      fontSize: "11px",
      fontWeight: 700,
      letterSpacing: "0.14em",
      textTransform: "uppercase",
      lineHeight: 1.6,
    },
    button: { textTransform: "none", fontWeight: 600 },
  },

  shape: { borderRadius: 8 },

  components: {
    // No shadows on data surfaces. Depth comes from the tinted canvas and the
    // one saturated navy, so a card reads as a document rather than as app
    // furniture. The disclaimer modal is the single lifted surface, and it
    // opts back in explicitly.
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: { backgroundImage: "none", border: `1px solid ${designTokens.line}` },
      },
    },
    MuiAppBar: {
      defaultProps: { elevation: 0 },
      styleOverrides: { root: { backgroundColor: designTokens.blue, border: 0 } },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: { root: { borderRadius: 4 } },
    },
    MuiChip: { styleOverrides: { root: { borderRadius: 999 } } },
    MuiTooltip: {
      styleOverrides: {
        tooltip: { backgroundColor: designTokens.navy, fontSize: "12.5px" },
      },
    },
  },
});

/**
 * The theme, with the raw tokens and the monospace stack attached.
 *
 * `designTokens` is on the theme rather than imported separately so a
 * component reaches every colour through one object, and so the premise gate
 * can assert the theme and the design system agree without reaching into two
 * places.
 */
export const theme: Theme & { designTokens: DesignTokens; monoFontFamily: string } =
  Object.assign(base, { designTokens, monoFontFamily: MONO });

export default theme;
