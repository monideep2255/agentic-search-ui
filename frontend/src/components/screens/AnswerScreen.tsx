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

import { Fragment } from "react";
import { Box, Typography } from "@mui/material";
import { visuallyHidden } from "@mui/utils";

import { designTokens, layerColour } from "../../theme";

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

export interface AnswerScreenProps {
  question: string;
  claims: Claim[];
  sources: Source[];
  meta?: string;
  trust?: TrustSignal[];
  /** The feedback surface, injected so this screen does not own its state. */
  feedback?: React.ReactNode;
  /** Rendered under the sources. The follow-up field. */
  followUp?: React.ReactNode;
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
 * A refusal, failure or cap notice.
 *
 * Copy arrives already chosen from a fixed, interpolation-free table, so no
 * cost figure can reach a user-facing refusal even by accident.
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
  trust = [],
  feedback,
  followUp,
  onNewSearch,
  refusal = null,
  failure = null,
  capMessage = null,
  systemNotes = [],
  onFlagSource,
  flaggedSources = [],
}: AnswerScreenProps) {
  return (
    <Box sx={{ maxWidth: 900, mx: "auto", px: 3, py: 3.5 }}>
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
                sx={{
                  font: "inherit",
                  fontSize: 12.5,
                  px: 1.6,
                  py: 0.6,
                  flex: "none",
                  borderRadius: 0.5,
                  cursor: "pointer",
                  color: designTokens.inkMuted,
                  bgcolor: designTokens.surface,
                  border: `1px solid ${designTokens.line}`,
                  "&:hover": { borderColor: designTokens.lineStrong, color: designTokens.ink },
                }}
              >
                New search
              </Box>
            ) : null}
          </Box>
          {meta ? (
            <Typography variant="body2" sx={{ color: designTokens.inkMuted, mt: 1 }}>
              {meta}
            </Typography>
          ) : null}
        </Box>

        {refusal ? <Notice testId="answer-refusal" tone="warn" text={refusal} /> : null}
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
                <Box component="span" sx={visuallyHidden}>
                  {claim.citations.length === 0
                    ? "This sentence has no source."
                    : `Source ${claim.citations.join(" and ")}, layer ${claim.layer}.`}
                </Box>
                {claim.citations.map((n, position) => (
                  <Box
                    key={n}
                    component="span"
                    data-testid={`citation-${n}`}
                    data-claim={index}
                    data-layer={claim.layer}
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
                      borderLeft: `4px solid ${layerColour(claim.layer).main}`,
                      bgcolor: layerColour(claim.layer).wash,
                      ml: position === 0 ? 0 : 0.5,
                    }}
                  >
                    {n}
                  </Box>
                ))}
              </Typography>
            </Fragment>
          ))}
        </Box>

        {sources.length > 0 ? (
          <Typography
            variant="overline"
            component="p"
            sx={{ mt: 3.5, mb: 1.25, color: designTokens.inkFaint }}
          >
            Sources
          </Typography>
        ) : null}

        {sources.map((source) => {
          const colour = layerColour(source.layer);
          return (
            <Box
              key={source.n}
              data-testid={`source-${source.n}`}
              data-layer={source.layer}
              sx={{
                border: `1px solid ${designTokens.line}`,
                borderLeft: `4px solid ${colour.main}`,
                borderRadius: 0.5,
                bgcolor: designTokens.surface,
                mb: 1,
                p: 1.75,
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, flexWrap: "wrap", mb: 1.25 }}>
                <Box component="span" sx={{ ...mono, fontWeight: 700, fontSize: 12 }}>
                  [{source.n}]
                </Box>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {source.name}
                </Typography>
                <Box component="span" sx={{ ...mono, ml: "auto", fontSize: 11.5, color: designTokens.inkMuted }}>
                  L{source.layer}
                </Box>
                {onFlagSource ? (
                  <Box
                    component="button"
                    type="button"
                    aria-pressed={flaggedSources.includes(source.n)}
                    onClick={() => onFlagSource(source.n)}
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
              </Box>

              {/* Every field Section 9.1 requires. The licence is not optional. */}
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

        {feedback}
        {followUp}
      </Box>
    </Box>
  );
}

export default AnswerScreen;
