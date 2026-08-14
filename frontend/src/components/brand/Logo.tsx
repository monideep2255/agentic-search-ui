/**
 * The mark, build phase 4.8, ticket T-4.8-03.
 *
 * A double helix whose three rungs are the three data layers. It reads as DNA
 * at 16px and as the provenance system on inspection. Nothing is borrowed from
 * the NCBI or NLM marks: the restraint is shared, the geometry is not.
 *
 * On the blue app bar the rungs shift to light tints. Layer 1 blue is the same
 * value as the bar itself, so at full strength a third of the mark's meaning
 * would vanish into the ground.
 *
 * Source of truth: `docs/build/design/design-system/brand/logo.html`.
 */

import { designTokens } from "../../theme";

/** The two strands, mirrored, crossing at three points. */
const STRANDS = [
  "M12 2 Q19 5.35 12 8.7 Q5 12 12 15.3 Q19 18.65 12 22",
  "M12 2 Q5 5.35 12 8.7 Q19 12 12 15.3 Q5 18.65 12 22",
];

/** The three rungs sit where the strands are furthest apart. */
const RUNG_Y = [5.35, 12, 18.65];

export interface LogoProps {
  size?: number;
  /** `onNavy` uses light tints so all three rungs survive a saturated ground. */
  variant?: "onLight" | "onNavy";
}

export function Logo({ size = 21, variant = "onNavy" }: LogoProps) {
  const onNavy = variant === "onNavy";
  const strand = onNavy ? "#FFFFFF" : designTokens.navy;
  const rungs = onNavy
    ? ["#CFE1F5", "#9FD3A8", "#C3B2E6"]
    : [designTokens.layer1, designTokens.layer2, designTokens.layer3];

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      focusable="false"
      style={{ display: "block", flex: "none" }}
    >
      {STRANDS.map((d) => (
        <path
          key={d}
          d={d}
          stroke={strand}
          strokeWidth={1.9}
          strokeLinecap="round"
          fill="none"
        />
      ))}
      {RUNG_Y.map((y, i) => (
        <line
          key={y}
          x1={8.6}
          y1={y}
          x2={15.4}
          y2={y}
          stroke={rungs[i]}
          strokeWidth={1.9}
          strokeLinecap="round"
        />
      ))}
    </svg>
  );
}

export default Logo;
