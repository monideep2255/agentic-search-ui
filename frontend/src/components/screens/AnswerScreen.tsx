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
import { Box, Typography } from "@mui/material";

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
}

/** What the trust line's info card says (item 9.9). */
export const TRUST_LINE_EXPLAINER =
  "Sources are counted by the database each record comes from, so twenty records from one " +
  "database are one source. Confirmed means two independent databases agree on the same " +
  "high-stakes fact. Not yet confirmed means a high-stakes fact rests on a single source.";

/** Bold the backend's chosen terms, matched exactly as it spelled them. */
function withEmphasis(text: string, emphasis?: string[]): React.ReactNode {
  const terms = (emphasis ?? []).filter((term) => term.length > 0);
  if (terms.length === 0) return text;
  const escaped = [...terms]
    .sort((a, b) => b.length - a.length)
    .map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`(${escaped.join("|")})`, "g");
  return text.split(pattern).map((part, i) =>
    terms.includes(part) ? (
      <Box key={i} component="strong" sx={{ fontWeight: 700 }}>
        {part}
      </Box>
    ) : (
      <Fragment key={i}>{part}</Fragment>
    ),
  );
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

  const sourceByIndex = new Map(sources.map((source) => [source.n, source]));

  /** One claim's spine segment. `grow` shares a paragraph's height evenly. */
  const spineSegment = (claim: Claim, index: number, grow = false) => (
    <Box
      key={index}
      aria-hidden="true"
      data-testid={`${testIdPrefix}spine-segment-${index}`}
      data-layer={claim.layer ?? (claim.pendingCitations ? "pending" : "none")}
      sx={{
        width: 6,
        mx: "auto",
        borderRadius: 1,
        alignSelf: "stretch",
        ...(grow ? { flex: 1 } : {}),
        // A sentence whose sources are still arriving is not uncited: it
        // takes the lighter `line` token, never the uncited `lineStrong`.
        bgcolor:
          claim.layer === null && claim.pendingCitations
            ? designTokens.line
            : layerColour(claim.layer).main,
      }}
    />
  );

  /*
   * One claim's citation markers, 2026-09-14.
   *
   * These were boxed chips reading `1 ncbi_efetch MedGen:C0346153`, and the
   * product owner's verdict was that they overwhelmed the answer. They are
   * now superscript numbers whose card carries the source, its id, its layer
   * and its record link; see `answer/CitationMarkers.tsx` for the design and
   * the token behind every value.
   *
   * WHAT DID NOT MOVE: each source still names its own layer for assistive
   * technology (F-4.9-A-04), now as the marker button's own accessible name,
   * and an uncited sentence still says so in words (F-4.8-A-16, WCAG 1.4.1).
   * The spine stays decorative, so the meaning is carried here.
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
   * UI FIX SET 9: THE STRUCTURED ANSWER (items 9.3 to 9.5, 9.8, 9.10).
   *
   * A claim that carries `paragraph` came from a typed token stream, so the
   * answer renders as the backend structured it: consecutive sentences of one
   * paragraph flow as prose in one grid row, a heading or an inline note is a
   * row of its own, and a code-built listing is a list or a table. Every claim
   * keeps its own spine segment (stacked within its block) and its own
   * `claim-text-N` hook, so the spine still has exactly one segment per claim.
   *
   * DESIGN SOURCES, per `design-consistency`. The prose, bold and heading
   * values are the prototype's `.answer p`, `.answer p strong` and `.answer
   * .ah` rules; the table is its `.rtab`. DESIGN GAP, named: no card or
   * prototype rule styles a bulleted list inside an answer. The list uses the
   * body text of `.answer p` with the browser's own marker and the 6px gap
   * the refusal block already uses, introducing no new value.
   */
  const structured = claims.some((claim) => claim.paragraph !== undefined);
  type AnswerBlock =
    | { type: "heading"; text: string; key: string }
    | { type: "note"; text: string; key: string }
    | {
        type: "claim" | "list_item" | "table_row";
        paragraph: number;
        key: string;
        items: { claim: Claim; index: number }[];
      };
  const blocks: AnswerBlock[] = [];
  if (structured) {
    claims.forEach((claim, index) => {
      if (claim.noteBefore) blocks.push({ type: "note", text: claim.noteBefore, key: `note-${index}` });
      if (claim.heading) blocks.push({ type: "heading", text: claim.heading, key: `heading-${index}` });
      const type = claim.kind ?? "claim";
      const paragraphNo = claim.paragraph ?? 0;
      const last = blocks[blocks.length - 1];
      if (last && last.type === type && "items" in last && last.paragraph === paragraphNo) {
        last.items.push({ claim, index });
      } else {
        blocks.push({ type, paragraph: paragraphNo, key: `block-${index}`, items: [{ claim, index }] });
      }
    });
  }
  const tableCell = {
    textAlign: "left",
    p: "8px 11px",
    borderBottom: `1px solid ${designTokens.line}`,
    verticalAlign: "top",
  } as const;
  let headingNumber = 0;
  let noteNumber = 0;
  const renderBlock = (block: AnswerBlock) => {
    if (block.type === "heading") {
      return (
        <Fragment key={block.key}>
          <Box aria-hidden="true" />
          <Typography
            component="h2"
            data-testid={`${testIdPrefix}answer-heading-${headingNumber++}`}
            sx={{
              fontSize: 11.5,
              letterSpacing: "0.13em",
              textTransform: "uppercase",
              fontWeight: 700,
              color: designTokens.inkFaint,
              mt: headingNumber === 1 ? 0 : 1.5,
              mb: 0,
              pb: "7px",
              borderBottom: `1px solid ${designTokens.line}`,
            }}
          >
            {block.text}
          </Typography>
        </Fragment>
      );
    }
    if (block.type === "note") {
      return (
        <Fragment key={block.key}>
          <Box aria-hidden="true" />
          <Typography
            data-testid={`${testIdPrefix}answer-inline-note-${noteNumber++}`}
            sx={{ fontSize: 13.5, color: designTokens.inkMuted, maxWidth: "66ch" }}
          >
            {block.text}
          </Typography>
        </Fragment>
      );
    }
    const spine = (
      <Box sx={{ display: "flex", flexDirection: "column", gap: "3px", alignSelf: "stretch" }}>
        {block.items.map(({ claim, index }) => spineSegment(claim, index, true))}
      </Box>
    );
    if (block.type === "list_item") {
      return (
        <Fragment key={block.key}>
          {spine}
          <Box
            component="ul"
            sx={{ m: 0, pl: 2.5, display: "flex", flexDirection: "column", gap: 0.75 }}
          >
            {block.items.map(({ claim, index }) => (
              <Box
                component="li"
                key={index}
                data-testid={`${testIdPrefix}claim-text-${index}`}
                sx={{ maxWidth: "66ch" }}
              >
                {claim.cells?.[0] ?? claim.text}
                {citationChips(claim, index)}
              </Box>
            ))}
          </Box>
        </Fragment>
      );
    }
    if (block.type === "table_row") {
      const header = block.items[0]?.claim.tableHeader;
      return (
        <Fragment key={block.key}>
          {spine}
          <Box sx={{ overflowX: "auto" }}>
            <Box
              component="table"
              data-testid={`${testIdPrefix}answer-table`}
              sx={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: 13.5,
                border: `1px solid ${designTokens.line}`,
                bgcolor: designTokens.surface,
              }}
            >
              {header ? (
                <thead>
                  <tr>
                    {header.map((label) => (
                      <Box
                        component="th"
                        key={label}
                        scope="col"
                        sx={{
                          ...tableCell,
                          fontSize: 10.5,
                          letterSpacing: "0.1em",
                          textTransform: "uppercase",
                          color: designTokens.inkFaint,
                          bgcolor: designTokens.surfaceSunk,
                        }}
                      >
                        {label}
                      </Box>
                    ))}
                  </tr>
                </thead>
              ) : null}
              <tbody>
                {block.items.map(({ claim, index }) => (
                  <Box
                    component="tr"
                    key={index}
                    data-testid={`${testIdPrefix}claim-text-${index}`}
                  >
                    <Box component="td" sx={{ ...tableCell, ...mono, fontSize: 12.5 }}>
                      {claim.cells?.[0] ?? claim.text}
                    </Box>
                    <Box component="td" sx={tableCell}>
                      {claim.cells?.[1] ?? ""}
                      {citationChips(claim, index)}
                    </Box>
                  </Box>
                ))}
              </tbody>
            </Box>
          </Box>
        </Fragment>
      );
    }
    return (
      <Fragment key={block.key}>
        {spine}
        <Typography component="p" sx={{ maxWidth: "66ch", m: 0 }}>
          {block.items.map(({ claim, index }) => (
            <Box component="span" key={index} data-testid={`${testIdPrefix}claim-text-${index}`}>
              {/* No space before the markers: a superscript sits against the
                  sentence it cites, and a space would let it wrap onto a line
                  of its own. */}
              {withEmphasis(claim.text, claim.emphasis)}
              {citationChips(claim, index)}{" "}
            </Box>
          ))}
        </Typography>
      </Fragment>
    );
  };

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
      {/*
        RENDERED UNCONDITIONALLY, even with no claims, exactly as it was
        before the extraction. An empty grid has no height, and it is what
        the onboarding tour's `citations` anchor hangs on: guarding it on
        `claims.length` would take the anchor off the page on a refusal,
        which is a behaviour change this ticket has no business making.
      */}
      <Box
        {...(tour ? { "data-tour": "citations" } : {})}
        data-testid={`${testIdPrefix}claims`}
        aria-live={streaming ? "polite" : undefined}
        sx={{
          display: "grid",
          gridTemplateColumns: "14px 1fr",
          columnGap: 2.25,
          rowGap: 1.9,
          alignItems: "stretch",
        }}
      >
          {structured ? blocks.map(renderBlock) : null}
          {structured ? null : claims.map((claim, index) => (
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
                data-testid={`${testIdPrefix}spine-segment-${index}`}
                data-layer={claim.layer ?? (claim.pendingCitations ? "pending" : "none")}
                sx={{
                  width: 6,
                  mx: "auto",
                  borderRadius: 1,
                  alignSelf: "stretch",
                  // A sentence whose sources are still arriving is not uncited: it
        // takes the lighter `line` token, never the uncited `lineStrong`.
        bgcolor:
          claim.layer === null && claim.pendingCitations
            ? designTokens.line
            : layerColour(claim.layer).main,
                }}
              />

              <Typography
                data-testid={`${testIdPrefix}claim-text-${index}`}
                sx={{ maxWidth: "64ch" }}
              >
                {claim.text}
                {/*
                  F-4.9-A-04 still holds: each marker names its OWN source's
                  layer, not the claim's first one. The same renderer as the
                  structured path, so the two cannot drift.
                */}
                {citationChips(claim, index)}
              </Typography>
            </Fragment>
          ))}
      </Box>

      {/*
        2026-09-14, product-owner request: show that the answer is still being
        written. A quiet line at the end of the streamed text, gone the moment
        the run lands (this body re-renders without `writing`) or stops.

        NEAREST DESIGNED NEIGHBOUR: the inline system note above it in this
        same grid (`answer-inline-note`, 13.5px `inkMuted`, 66ch), set in the
        spine's second column so it lines up with the prose, followed by the
        caption's `WritingEllipsis`. `aria-hidden`, because the claims region
        is already a polite live region and `RunProgress` announces "Write
        step running"; a third announcement would only repeat them.
      */}
      {streaming && writing ? (
        <Box
          data-testid={`${testIdPrefix}streaming-writing-indicator`}
          aria-hidden="true"
          sx={{ display: "grid", gridTemplateColumns: "14px 1fr", columnGap: 2.25, mt: 1 }}
        >
          <Box />
          <Typography sx={{ fontSize: 13.5, color: designTokens.inkMuted, maxWidth: "66ch" }}>
            writing
            <WritingEllipsis />
          </Typography>
        </Box>
      ) : null}

      {/*
        UI fix set 9, item 9.8: disclosures render AFTER the answer they
        qualify, as quiet grey notes, never as amber boxes above the first
        sentence. Colour and size are the refusal explanation's (`inkMuted`,
        13.5px), the nearest designed neighbour for text about an answer.
      */}
      {!streaming && systemNotes.length > 0 ? (
        <Box sx={{ mt: 2.5, display: "flex", flexDirection: "column", gap: 0.75 }}>
          {systemNotes.map((note, i) => (
            <Typography
              key={i}
              role="status"
              data-testid={`${testIdPrefix}answer-note-${i}`}
              sx={{ fontSize: 13.5, color: designTokens.inkMuted, maxWidth: "66ch" }}
            >
              {note}
            </Typography>
          ))}
        </Box>
      ) : null}

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
              data-testid={`${testIdPrefix}sources-count`}
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
                data-testid={`${testIdPrefix}source-${source.n}`}
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
            mt: 2.5,
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
                  fontWeight: signal.kind === "plain" ? 400 : 600,
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
    <Box sx={{ width: "100%", maxWidth: 900, mx: "auto", my: "auto", px: 3, py: 3.5 }}>
      <Box
        data-tour="answer"
        sx={{
          bgcolor: designTokens.surface,
          border: `1px solid ${designTokens.line}`,
          borderRadius: 1,
          p: { xs: 2.5, sm: 3.25 },
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
                  <AnswerBody streaming writing={!stopped} claims={claims} sources={sources} />
                </Box>
              ) : null}
            </>
          ) : (
            <>
              <AnswerBody
                tour
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
