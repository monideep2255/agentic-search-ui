/**
 * The feedback surface, build phase 4.8, ticket T-4.8-07. Wired for real by
 * build phase 4.6, ticket T-4.6-09.
 *
 * Answer-level rating, plus the thing a cite-or-refuse system actually needs:
 * a per-citation flag saying this source does not support the claim attached
 * to it. That produces a labelled pair rather than an opinion, and it is the
 * highest-value signal this product can collect.
 *
 * The reason chips are not generic. Every entry maps to a failure mode this
 * system has genuinely produced and logged: an unsupported citation, a
 * confidently wrong answer, a dropped entity in a multi-part question, and a
 * refusal that should have answered. A reason list built from real failures is
 * worth more at review time than "not helpful", and it is what makes
 * signal-based review sampling possible later.
 *
 * WHY THE PER-CITATION FLAG IS BUNDLED INTO THIS SAME SUBMISSION, rather than
 * posted the instant its button is clicked on the source card. `record_
 * feedback` (`src/system_03_search_agent/feedback/writer.py`) REPLACES the
 * whole `user_feedback` row on every write, it does not merge fields in. A
 * lone POST fired from a citation-flag click, carrying only that flag, would
 * silently erase a rating or comment already sent in an earlier call. Bundling
 * every field into the one submission this panel's Send button fires is what
 * keeps every write a correct, complete replacement rather than a partial one
 * that clobbers what came before.
 *
 * WHY A 409 IS NOT TREATED AS A FAILURE. `feedback.capture_run` runs as a
 * background task dispatched after the run's own `done` event, so a rating
 * typed the instant an answer lands can genuinely beat that row into
 * existence. The server answers that race with 409 and a `Retry-After`
 * header (`postFeedback`'s `FeedbackNotYetCapturedError`), and this
 * component retries automatically, showing the caller that it is still
 * saving rather than that it failed, bounded to a small number of attempts
 * before it gives up and offers a manual retry.
 *
 * WHY A FAILED SEND STAYS ON SCREEN WITH A RETRY, rather than silently
 * discarding the rating. A user who rated an answer and had that rating
 * vanish with no sign of it is worse off than one who sees a plain error and
 * a button to try again: the first looks like it worked and did not, the
 * second is honest about what happened and gives the user a next step.
 */

import { useEffect, useRef, useState } from "react";
import { Box, Typography } from "@mui/material";

import { designTokens } from "../../theme";
import { FeedbackNotYetCapturedError, postFeedback } from "../../lib/api";
import type { FeedbackRequestBody } from "../../lib/api";

/** Each maps to a failure mode this system has actually produced. */
const REASONS = [
  "Citation does not support the claim",
  "Wrong answer",
  "Missing a source I expected",
  "Should have refused",
  "Too slow",
] as const;

/**
 * The fixed reason attached to every per-citation flag. The source card's
 * button carries exactly one meaning ("this source does not support the
 * claim it is attached to"), so there is no separate reason control for it,
 * unlike the answer-level reason chips above.
 */
const CITATION_FLAG_REASON = "Citation does not support the claim";

/** Bounded so a genuinely stuck capture path fails visibly rather than
 *  retrying forever. Each attempt waits the server's own `Retry-After`
 *  hint, so three attempts is comfortably longer than one background DB
 *  write normally takes. */
const MAX_NOT_YET_CAPTURED_RETRIES = 3;

type SendStatus = "idle" | "sending" | "retrying" | "sent" | "error";

function Thumb({ down = false }: { down?: boolean }) {
  /*
   * T-4.16-10. The rotation is on an inner `<g>`, NOT on the `<svg>` itself,
   * and that one move is the whole of the defect the product owner reported
   * as "the feedback buttons were not working properly. The down arrow was
   * outside the box."
   *
   * WHY THE OLD PLACEMENT BROKE IT. `transform` on the OUTERMOST `<svg>` is
   * not an SVG transform, it is a CSS one, resolved in the element's own CSS
   * pixel space rather than in the viewBox coordinate system. So
   * `rotate(180 8 8)` rotated about a point 8 CSS pixels from the element's
   * origin instead of about the centre of a `0 0 16 16` viewBox, displacing
   * the whole glyph 16px down and to the right. On an inner `<g>` the same
   * string is parsed as an SVG transform, where `8 8` is exactly the viewBox
   * centre and the rotation is in place.
   *
   * MEASURED IN A REAL BROWSER, not reasoned about, because the two
   * placements are one word apart and read identically:
   *
   *     UP    (no transform)              contained
   *     DOWN  (transform on root <svg>)   OUTSIDE: right 8.5px, bottom 8.5px
   *     DOWN  (transform on inner <g>)    contained
   *
   * AND WHY IT ALSO READ AS "NOT WORKING". The `<button>` stayed a correct
   * 30x30 hit target the whole time; only the glyph moved. So the thumb a
   * person could see sat outside the control it belonged to, and clicking
   * what they saw missed the button entirely. One defect, two symptoms, and
   * the functional one is a consequence of the visual one rather than a
   * second bug.
   *
   * This is `LEARNINGS.md` rows 107 and 108 again: every frontend assertion
   * in this repository checks what is on screen and never where it is, so a
   * pure-geometry defect is invisible to all 211 of them. The guard is
   * `e2e/feedback-submission.spec.ts`'s "both feedback thumbs render inside
   * their own buttons", which measures bounding boxes in a real browser.
   * Mutation-run before commit: restoring the `transform` to the `<svg>`
   * fails it on the down thumb with an 8px right overflow and leaves the up
   * thumb green, which is the asymmetry the defect actually had.
   */
  return (
    <svg
      width={15}
      height={15}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      strokeLinejoin="round"
      aria-hidden="true"
      data-testid={down ? "thumb-down-glyph" : "thumb-up-glyph"}
    >
      <g transform={down ? "rotate(180 8 8)" : undefined}>
        <path d="M5.5 7 8.2 2.2a1.3 1.3 0 0 1 2.4.7V6h2.6a1.3 1.3 0 0 1 1.28 1.55l-.85 4.2A1.3 1.3 0 0 1 12.15 13H5.5z" />
        <rect x={1.6} y={7} width={3.9} height={6} rx={0.8} />
      </g>
    </svg>
  );
}

export interface FeedbackSurfaceProps {
  /**
   * The landed run's id, `POST /v1/query/{run_id}/feedback`'s path target.
   * Optional, and `null` when omitted: `AnswerScreen` passes a real run id
   * once it has one, and until every call site of this component is
   * updated to do so, sending fails visibly rather than posting to a
   * malformed URL.
   */
  runId?: string | null;
  /**
   * The bearer token this run's own request used: a real access token once
   * signed in, a guest token before that. A guest must be able to submit
   * feedback the same as a signed-in caller, so this is deliberately not
   * scoped to an account. Optional and `null` when omitted, same reasoning
   * as `runId` above.
   */
  authToken?: string | null;
  /**
   * Source display indices (`Source.n`) the reader has flagged, via the
   * source card's own "Flag: does not support" control, as not supporting
   * their claim. Included in this same submission rather than posted the
   * moment the flag is clicked; see the module docstring for why a
   * separate, immediate POST would be unsafe against a replacing write.
   */
  flaggedSources?: number[];
}

export function FeedbackSurface({
  runId = null,
  authToken = null,
  flaggedSources = [],
}: FeedbackSurfaceProps) {
  const [rating, setRating] = useState<"up" | "down" | null>(null);
  const [reasons, setReasons] = useState<string[]>([]);
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState<SendStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  const retryAttempts = useRef(0);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Mutation proof: deleting this cleanup lets a retry fire `setState` on an
  // unmounted component (a new question remounts this component by key)
  // after the user has already moved on, which React reports as a warning
  // and which schedules a POST for a panel nobody can see any more.
  useEffect(
    () => () => {
      if (retryTimer.current !== null) {
        clearTimeout(retryTimer.current);
      }
    },
    [],
  );

  const toggleReason = (reason: string) =>
    setReasons((current) =>
      current.includes(reason) ? current.filter((r) => r !== reason) : [...current, reason],
    );

  const buildPayload = (): FeedbackRequestBody => ({
    rating,
    comment: comment.trim() === "" ? null : comment.trim(),
    flagged_reason: reasons.length > 0 ? reasons.join("; ") : null,
    citation_flags: flaggedSources.map((n) => ({
      citation_id: String(n),
      reason: CITATION_FLAG_REASON,
    })),
  });

  const attemptSend = async () => {
    if (runId === null || authToken === null) {
      // A wiring gap, not a user error: whatever renders this component has
      // not given it a real run yet. Visible rather than silent, per the
      // same rule as every other failure here, but distinguishable in the
      // message so it does not read as "your rating failed to save".
      setStatus("error");
      setErrorMessage("Feedback is not available for this answer right now.");
      return;
    }
    try {
      await postFeedback(runId, buildPayload(), authToken);
      setStatus("sent");
    } catch (error) {
      if (error instanceof FeedbackNotYetCapturedError) {
        if (retryAttempts.current >= MAX_NOT_YET_CAPTURED_RETRIES) {
          setStatus("error");
          setErrorMessage("Still saving your answer. Try again in a moment.");
          return;
        }
        retryAttempts.current += 1;
        setStatus("retrying");
        retryTimer.current = setTimeout(() => {
          void attemptSend();
        }, error.retryAfterS * 1000);
        return;
      }
      setStatus("error");
      setErrorMessage("Could not send your feedback. Check your connection and try again.");
    }
  };

  const send = () => {
    retryAttempts.current = 0;
    setStatus("sending");
    setErrorMessage(null);
    void attemptSend();
  };

  if (dismissed) {
    return null;
  }

  if (status === "sent") {
    return (
      <Box sx={{ mt: 3, pt: 2.25, borderTop: `1px solid ${designTokens.line}` }}>
        <Typography variant="body2" role="status" sx={{ color: designTokens.ok, fontWeight: 600 }}>
          Thanks. This goes to the review queue.
        </Typography>
      </Box>
    );
  }

  const busy = status === "sending" || status === "retrying";

  const button = (kind: "up" | "down") => {
    const active = rating === kind;
    const danger = kind === "down";
    return (
      <Box
        component="button"
        type="button"
        aria-label={danger ? "Not helpful" : "Helpful"}
        aria-pressed={active}
        onClick={() => setRating(kind)}
        sx={{
          width: 30,
          height: 30,
          p: 0,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 0.5,
          cursor: "pointer",
          border: "1px solid",
          borderColor: active
            ? danger
              ? designTokens.risk
              : designTokens.blue
            : designTokens.line,
          color: active
            ? danger
              ? designTokens.risk
              : designTokens.blue
            : designTokens.inkMuted,
          bgcolor: active
            ? danger
              ? designTokens.riskWash
              : designTokens.layer1Wash
            : designTokens.surface,
          "&:hover": { borderColor: designTokens.lineStrong, color: designTokens.ink },
        }}
      >
        <Thumb down={danger} />
      </Box>
    );
  };

  // A rating, or at least one flagged citation, is enough to have something
  // worth sending: a reader who only wants to flag a bad source without
  // giving an overall up/down verdict must still be able to submit that.
  const canSend = rating !== null || flaggedSources.length > 0;

  return (
    <Box
      data-testid="feedback"
      sx={{
        mt: 3,
        pt: 2.25,
        borderTop: `1px solid ${designTokens.line}`,
        display: "flex",
        flexDirection: "column",
        gap: 1.5,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
        <Typography variant="body2" sx={{ color: designTokens.inkMuted }}>
          Was this answer helpful?
        </Typography>
        {button("up")}
        {button("down")}
      </Box>

      {rating === "down" ? (
        <>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
            {REASONS.map((reason) => {
              const on = reasons.includes(reason);
              return (
                <Box
                  key={reason}
                  component="button"
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleReason(reason)}
                  sx={{
                    font: "inherit",
                    fontSize: 12.5,
                    px: 1.4,
                    py: 0.5,
                    borderRadius: 999,
                    cursor: "pointer",
                    border: "1px solid",
                    borderColor: on ? designTokens.risk : designTokens.line,
                    color: on ? designTokens.risk : designTokens.inkMuted,
                    bgcolor: on ? designTokens.riskWash : designTokens.surface,
                  }}
                >
                  {reason}
                </Box>
              );
            })}
          </Box>

          <Box
            component="input"
            type="text"
            aria-label="What went wrong"
            placeholder="What went wrong? (optional)"
            value={comment}
            onChange={(event: React.ChangeEvent<HTMLInputElement>) =>
              setComment(event.target.value)
            }
            sx={{
              maxWidth: 470,
              font: "inherit",
              fontSize: 13.5,
              px: 1.4,
              py: 1.1,
              borderRadius: 0.5,
              border: `1px solid ${designTokens.lineStrong}`,
              bgcolor: designTokens.surface,
            }}
          />
        </>
      ) : null}

      {status === "retrying" || status === "error" ? (
        <Box
          data-testid="feedback-status"
          role={status === "error" ? "alert" : "status"}
          sx={{
            fontSize: 12.5,
            color: status === "error" ? designTokens.risk : designTokens.inkMuted,
          }}
        >
          {status === "retrying"
            ? "Still finishing up your answer. Retrying in a moment."
            : errorMessage}
        </Box>
      ) : null}

      {canSend ? (
        <Box sx={{ display: "flex", gap: 1 }}>
          <Box
            component="button"
            type="button"
            disabled={busy}
            onClick={send}
            sx={{
              font: "inherit",
              fontSize: 12.5,
              fontWeight: 600,
              px: 1.75,
              py: 0.9,
              border: 0,
              borderRadius: 0.5,
              cursor: busy ? "default" : "pointer",
              color: "#FFFFFF",
              bgcolor: busy ? designTokens.inkFaint : designTokens.blue,
            }}
          >
            {status === "error"
              ? "Retry"
              : busy
                ? "Sending…"
                : "Send feedback"}
          </Box>
          <Box
            component="button"
            type="button"
            disabled={busy}
            onClick={() => setDismissed(true)}
            sx={{
              font: "inherit",
              fontSize: 12.5,
              px: 1.75,
              py: 0.9,
              borderRadius: 0.5,
              cursor: busy ? "default" : "pointer",
              color: designTokens.inkMuted,
              bgcolor: "transparent",
              border: `1px solid ${designTokens.line}`,
            }}
          >
            Skip
          </Box>
        </Box>
      ) : null}
    </Box>
  );
}

export default FeedbackSurface;
