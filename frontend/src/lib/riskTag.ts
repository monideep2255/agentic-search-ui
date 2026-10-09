/**
 * The words of an answer's trust line that the live answer and the reopened
 * answer must share (card 71).
 *
 * One source for each: the live answer (`hooks/useRunView.ts`) builds its
 * risk tag with `riskTagLabel`, and the saved screen
 * (`components/screens/SavedAnswerScreen.tsx`) builds both its risk tag and
 * its no-trust-line fallback here. `riskTag.parity.test.tsx` feeds the same
 * runs to the live view and to the saved screen and compares the words, so
 * the two cannot drift apart unseen.
 */

/** A span on the trust line, in the live answer's own shape. */
export interface TrustLineSpan {
  kind: "good" | "risk" | "plain";
  label: string;
}

/**
 * The live answer's words for a run with no grounding verdict at all
 * (`useRunView.ts`, F-4.9-A-02). On the saved screen they also cover any row
 * whose stored facts cannot show a grounding check ran.
 */
export const NO_GROUNDING_CHECK_LABEL = "Not verified · no grounding check was recorded";

/** The live answer's words for a grounded run with no trust line. */
export const GROUNDED_LABEL = "Grounded · every claim cited";

/**
 * The risk tag's words, or `null` for "show no tag".
 *
 * `null` for a missing or empty tier (a row saved before the tier was
 * stored, or a run whose worst tier was empty), for "low", and for
 * "unknown" (a refusal path where no risk assessment ran). "high" reads
 * "High-risk claim"; any other tier, known or new, reads "<tier> risk
 * claim", so a tier the backend adds over-reports rather than vanishes.
 */
export function riskTagLabel(tier: string | null | undefined): string | null {
  if (!tier || tier === "low" || tier === "unknown") return null;
  return tier === "high" ? "High-risk claim" : `${tier} risk claim`;
}

/**
 * The first span of a saved answer's trust line when the row has no
 * `trust_line` (card 71 fix round, A-71T-10).
 *
 * The live answer, with no trust line, shows `GROUNDED_LABEL` for a grounded
 * run that recorded trust signals and `NO_GROUNDING_CHECK_LABEL` for a run
 * that recorded none. The saved row keeps the outcome word and the risk
 * tier, and a stored tier (even an empty one) means trust signals were
 * recorded. So:
 *
 * - outcome "answer" with a stored tier: `GROUNDED_LABEL`, with the tick.
 *   An "answer" outcome is reached only when every claim was grounded.
 * - anything else ("flag", "ask", or no stored tier, which includes every
 *   row saved before the tier was stored): `NO_GROUNDING_CHECK_LABEL` in
 *   the risk colour. Never a tick and never the raw outcome word: the
 *   reopened answer must not look more confident than the live one did.
 */
export function savedTrustFallback(
  outcome: string,
  tier: string | null | undefined,
): TrustLineSpan {
  if (outcome === "answer" && typeof tier === "string") {
    return { kind: "good", label: GROUNDED_LABEL };
  }
  return { kind: "risk", label: NO_GROUNDING_CHECK_LABEL };
}
