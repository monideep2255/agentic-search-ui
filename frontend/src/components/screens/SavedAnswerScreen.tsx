/**
 * The saved-answer screen, overnight run of 2026-09-22/23, item 10.2.
 *
 * Worker B2's frontend half. `App.tsx`'s `onOpen` used to re-ask a clicked
 * history item's question every time, and the comment above that call said
 * re-asking was "the only truthful option available", because this
 * session's earlier runs were not retained. Worker B1's migration and the
 * two endpoints in the pinned wire contract
 * (`testing/Developer/reports/2026-09-23_overnight/contract.md`) make that
 * comment false: a signed-in account's answer is now stored, and
 * `GET /v1/history/{trace_id}/answer` returns it. This screen is what
 * renders it.
 *
 * FROM THE PERSON'S CHAIR (`.claude/rules/decide-from-the-users-chair.md`):
 * someone clicks a search they ran earlier and the answer they already got
 * is there at once, no wait, no second search charged to them. Run again
 * sits beside it and asks fresh, unchanged from today.
 *
 * NO DESIGN EXISTS FOR THIS SCREEN. Checked per
 * `.claude/rules/design-consistency.md`: `docs/build/design/README.md`'s
 * coverage table has no row for a saved-answer view, and the history rail's
 * own row (`prototype/app.html`'s `#rail`) covers only the rail, not what
 * opening an item shows. This is built from the nearest designed
 * neighbours instead of inventing a look: the answer screen's own card,
 * heading and button chrome (`AnswerScreen.tsx`, `screens/answer.html`),
 * its plain trust-signal line (UI fix set 9, item 9.9), and its citation
 * card's "Not linked" language (`identity/citation-chip.html`). Every
 * colour, radius and size below is a `designTokens` value already used for
 * one of those, not a new one. The one genuinely new element, the "saved
 * answer" marker banner, reuses the `layer1`/`layer1Wash` pairing the rail
 * already uses to mark an active item (`FollowUp.tsx`'s `HistoryRail`),
 * rather than choosing an unprecedented colour.
 *
 * UPDATE, worker H, overnight run, defect one in the findings file:
 * `answer_markdown` IS markdown. B1 established why: it is the only single
 * string that can carry a table, and answers here do carry tables, so
 * "never parsed as markdown" above was a false premise, not a settled
 * choice. `SavedAnswerMarkdown` (`savedAnswerMarkdown.tsx`) renders the
 * small closed set of constructs the producer can actually emit, to React
 * elements, never through `dangerouslySetInnerHTML`. See that module's own
 * docstring for why a markdown library was not added.
 *
 * UPDATE, worker H: `trust_line`, the one plain sentence the person read
 * under the original answer (UI fix set 9, item 9.9), now renders here too
 * when the stored row carries one, in the same place and the same style
 * the live answer screen renders its own (`AnswerScreen.tsx`'s "ONE PLAIN
 * LINE" block). Its absence renders nothing extra: this screen falls back
 * to the plain `trust_signal` line it always showed, unchanged.
 */

import { Fragment } from "react";
import { Box, Typography } from "@mui/material";

import { designTokens, layerColour } from "../../theme";
import { LAYER_WORD, isLinkableCitationUrl } from "../answer/CitationMarkers";
import { sourcePageKey } from "./AnswerScreen";
import { SavedAnswerMarkdown } from "./savedAnswerMarkdown";
import type { HistoryAnswerCitation, HistoryAnswerResponse } from "../../lib/api";
import { riskTagLabel } from "../../lib/riskTag";

export interface SavedAnswerScreenProps {
  /** The question as it was asked, shown while the answer is still loading. */
  question: string;
  /** True from the moment the row is opened until the fetch settles. */
  loading: boolean;
  /** Null until the fetch resolves. */
  answer: HistoryAnswerResponse | null;
  onRunAgain: () => void;
  onNewSearch?: () => void;
}

/** `asked_at` as a short, local, honest date. Empty string on anything unparsable. */
function formatAskedAt(iso: string): string {
  if (iso === "") return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** One page in a saved answer's Sources list, and every citation of it. */
export interface SavedSourceRow {
  /** The first citation of the page; its name and link spelling are shown. */
  citation: HistoryAnswerCitation;
  /** Every citation number that points at this page, in answer order. */
  indices: number[];
  /**
   * Every layer the page was cited from, ascending. A citation whose stored
   * layer was not recognised (`layer: null`, card 102) adds none, so its row
   * still shows with its link and names no layer rather than a guessed one.
   */
  layers: (1 | 2 | 3)[];
}

/**
 * A saved answer's citations, one row per record page.
 *
 * Card 22 fix round (2026-10-06, J-22-04, A-22-05): this screen listed one
 * row per citation under a trust line that counts pages, so a reopened
 * BRCA1 answer read "Based on 16 sources cited" above 18 rows, the gene
 * page three times. Rows are now keyed by `sourcePageKey`, the key the live
 * Sources list and the trust line use, so the rows a person counts are the
 * sources the line names. A citation with no link is its own row, never
 * merged.
 */
export function savedSourceRows(citations: HistoryAnswerCitation[]): SavedSourceRow[] {
  const rows = new Map<string, SavedSourceRow>();
  [...citations]
    .sort((a, b) => a.display_index - b.display_index)
    .forEach((citation) => {
      const key = sourcePageKey(citation.source_url) || `#${citation.display_index}`;
      const row = rows.get(key);
      const { layer } = citation;
      if (row) {
        row.indices.push(citation.display_index);
        if (layer !== null && !row.layers.includes(layer)) {
          row.layers = [...row.layers, layer].sort((a, b) => a - b);
        }
      } else {
        rows.set(key, {
          citation,
          indices: [citation.display_index],
          layers: layer === null ? [] : [layer],
        });
      }
    });
  return Array.from(rows.values());
}

/** One source row: layer dot, source name, link or "Not linked". */
function CitationRow({ row }: { row: SavedSourceRow }) {
  const { citation } = row;
  // An unrecognised layer draws `layerColour(null)`, the neutral gap colour.
  const colour = layerColour(citation.layer ?? row.layers[0] ?? null);
  const linkable = isLinkableCitationUrl(citation.source_url);
  const label = citation.entity_name ?? citation.source;
  return (
    <Box
      component="li"
      sx={{
        display: "flex",
        gap: 1,
        alignItems: "flex-start",
        p: "8px 10px",
        borderRadius: 0.5,
        border: `1px solid ${designTokens.line}`,
        bgcolor: designTokens.surfaceSunk,
      }}
    >
      <Box
        component="span"
        aria-hidden="true"
        sx={{
          flex: "none",
          width: 8,
          height: 8,
          mt: "5px",
          borderRadius: "50%",
          bgcolor: colour.main,
        }}
      />
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography component="span" sx={{ fontSize: 13, color: designTokens.ink }}>
          {row.indices.join(", ")}. {label}
        </Typography>
        <Typography
          component="span"
          sx={{ ml: 0.75, fontSize: 11.5, color: designTokens.inkFaint, textTransform: "uppercase" }}
        >
          {row.layers.map((layer) => LAYER_WORD[layer]).join(" · ")}
        </Typography>
        {linkable ? (
          <Box sx={{ mt: "2px" }}>
            {/*
              A URL has no spaces, so without a break point a long one (a
              Pathogen Detection isolate link, a ClinVar variation) runs past
              its row and scrolls the page sideways on a phone (F-102-V-05).
              `overflowWrap: "anywhere"` is the live answer's own rule for
              long unbroken strings (`AnswerScreen.tsx`'s claim text and
              phone source names), applied at every width.
            */}
            <a
              href={citation.source_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontSize: 12.5, color: designTokens.link, overflowWrap: "anywhere" }}
            >
              {citation.source_url}
            </a>
          </Box>
        ) : (
          <Typography
            component="span"
            sx={{ display: "block", mt: "2px", fontSize: 11.5, color: designTokens.risk }}
          >
            Not linked: this URL is not on a recognised NCBI host.
          </Typography>
        )}
      </Box>
    </Box>
  );
}

/**
 * The past search a person clicked, shown instantly from what was stored
 * rather than by asking the agent again.
 */
export function SavedAnswerScreen({
  question,
  loading,
  answer,
  onRunAgain,
  onNewSearch,
}: SavedAnswerScreenProps) {
  const askedAt = answer ? formatAskedAt(answer.asked_at) : "";
  const riskLabel = answer ? riskTagLabel(answer.risk_tier) : null;
  return (
    <Box sx={{ width: "100%", maxWidth: 900, mx: "auto", my: "auto", px: { xs: 2, sm: 3 }, py: 3.5 }}>
      <Box
        data-testid="saved-answer-screen"
        sx={{
          bgcolor: designTokens.surface,
          border: `1px solid ${designTokens.line}`,
          borderRadius: 1,
          p: { xs: "20px 18px 24px", sm: "26px 32px 32px" },
        }}
      >
        {/*
          THE MARKER. This is the one thing standing between "the reader
          trusts this as much as a fresh answer" and "the reader cannot
          tell the two apart", which item 10.2's done-when names directly.
          Always rendered, loading or landed, so a slow fetch never shows a
          bare question with no cue at all.
        */}
        <Box
          data-testid="saved-answer-marker"
          sx={{
            display: "inline-flex",
            alignItems: "center",
            gap: 0.6,
            mb: 1.25,
            px: 1,
            py: 0.4,
            borderRadius: 999,
            bgcolor: designTokens.layer1Wash,
            color: designTokens.blue,
            fontSize: 11.5,
            fontWeight: 700,
            letterSpacing: ".04em",
            textTransform: "uppercase",
          }}
        >
          Saved answer{askedAt ? ` · asked ${askedAt}` : ""}
        </Box>

        <Box
          sx={{
            display: "flex",
            gap: 1.75,
            alignItems: "flex-start",
            pb: 2,
            borderBottom: `1px solid ${designTokens.line}`,
          }}
        >
          <Typography variant="h3" component="h1" sx={{ flex: 1 }}>
            {question}
          </Typography>
          <Box
            component="button"
            type="button"
            onClick={onRunAgain}
            aria-label="Run this search again, fresh"
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
              "&:focus-visible": {
                outline: `2px solid ${designTokens.blue}`,
                outlineOffset: "2px",
              },
            }}
          >
            Run again
          </Box>
        </Box>

        {loading || answer === null ? (
          <Typography
            component="p"
            data-testid="saved-answer-loading"
            sx={{ mt: 2.5, fontSize: 13.5, color: designTokens.inkMuted }}
          >
            Loading your saved answer…
          </Typography>
        ) : (
          <Box sx={{ mt: 2.5 }}>
            <SavedAnswerMarkdown markdown={answer.answer_markdown} />

            {/*
              `trust_line` first, matching the live answer screen's own
              posture (`AnswerScreen.tsx`'s "ONE PLAIN LINE"): the sentence
              replaces the older `trust_signal` word when the row has one.
              A row saved before `trust_line` existed, or one whose run
              carried none, falls back to `trust_signal` unchanged, exactly
              as this screen behaved before tonight.
            */}
            {answer.trust_line || answer.trust_signal || riskLabel ? (
              <Box
                role="status"
                data-testid="saved-answer-trust-line"
                sx={{ mt: "14px", fontSize: 12.5, color: designTokens.inkMuted }}
              >
                {answer.trust_line ? (
                  <>
                    {answer.trust_line.startsWith("Confirmed") ? (
                      <Box component="span" aria-hidden="true" sx={{ color: designTokens.ok, mr: 0.5 }}>
                        ✓
                      </Box>
                    ) : null}
                    {answer.trust_line}
                  </>
                ) : answer.trust_signal ? (
                  <>
                    <Box component="span" aria-hidden="true" sx={{ color: designTokens.ok, mr: 0.5 }}>
                      ✓
                    </Box>
                    {answer.trust_signal}
                  </>
                ) : null}
                {/*
                  The risk tag (card 71): the live answer's own words
                  (`riskTagLabel`), the risk colour, regular weight, after a
                  middle dot, as on the live trust line. A row with no stored
                  tier shows nothing here, never a low-risk claim.
                */}
                {riskLabel ? (
                  <>
                    {answer.trust_line || answer.trust_signal ? (
                      <Box component="span" aria-hidden="true" sx={{ mx: 0.75 }}>
                        ·
                      </Box>
                    ) : null}
                    <Box
                      component="span"
                      data-testid="saved-answer-trust-risk"
                      sx={{ fontWeight: 400, color: designTokens.risk }}
                    >
                      {riskLabel}
                    </Box>
                  </>
                ) : null}
              </Box>
            ) : null}

            {answer.citations.length > 0 ? (
              <Box sx={{ mt: 2.5 }}>
                <Typography
                  variant="overline"
                  component="p"
                  sx={{ color: designTokens.inkFaint, m: 0, mb: 1 }}
                >
                  Sources
                </Typography>
                <Box
                  component="ul"
                  sx={{ listStyle: "none", m: 0, p: 0, display: "flex", flexDirection: "column", gap: 0.75 }}
                >
                  {savedSourceRows(answer.citations).map((row) => (
                    <Fragment key={row.indices.join(",")}>
                      <CitationRow row={row} />
                    </Fragment>
                  ))}
                </Box>
              </Box>
            ) : null}
          </Box>
        )}

        {onNewSearch ? (
          <Box sx={{ mt: 2.5, pt: "14px", borderTop: `1px solid ${designTokens.line}` }}>
            <Box
              component="button"
              type="button"
              onClick={onNewSearch}
              sx={{
                font: "inherit",
                fontSize: 12.5,
                fontWeight: 600,
                color: designTokens.blue,
                bgcolor: "transparent",
                border: 0,
                cursor: "pointer",
                p: 0,
              }}
            >
              + New search
            </Box>
          </Box>
        ) : null}
      </Box>
    </Box>
  );
}
