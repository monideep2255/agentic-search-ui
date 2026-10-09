/**
 * The words of the risk tag on an answer's trust line (card 71).
 *
 * The live answer builds the same label in `hooks/useRunView.ts` (the
 * "High-risk claim" span). The reopened answer calls this so its tag reads
 * the same. `null` means "show no tag": a missing tier (a row saved before
 * the tier was stored), "low", and "unknown" (a refusal path where no risk
 * assessment ran) all show nothing, exactly as on the live answer.
 */
export function riskTagLabel(tier: string | null | undefined): string | null {
  if (!tier || tier === "low" || tier === "unknown") return null;
  return tier === "high" ? "High-risk claim" : `${tier} risk claim`;
}
