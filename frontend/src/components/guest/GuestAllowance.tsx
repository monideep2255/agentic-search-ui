/**
 * The guest allowance, build phase 4.8, ticket T-4.8-08. Wired to a real,
 * server-counted allowance in build phase 4.10, ticket T-4.10-08.
 *
 * A visitor gets a free allowance before sign-in is required. The data model
 * already supports the flow rather than this being invented at the UI layer:
 * `interactions.user_id` is nullable precisely so a session can start
 * anonymous and attach to an account at signup.
 *
 * The counter is dots rather than a number for a reason. Five quiet dots read
 * as an allowance you were given; a number reads as a meter you are burning
 * down, and the second framing makes a research tool feel metered before the
 * user has any reason to trust it.
 *
 * `used`/`total` are read from `GET /v1/allowance` (or a fresh
 * `POST /auth/guest` response), by `App.tsx`, never counted or guessed
 * client-side: a component-local counter here would be exactly the
 * fabrication class build phase 4.8's judge round filed against demo answer
 * content, one layer up. See `stubs/registry.ts`'s `guest-allowance` entry
 * for what is real now and what still is not (durable cross-reload history).
 */

import { Box, Button, Typography } from "@mui/material";

import { designTokens } from "../../theme";

export interface GuestAllowanceProps {
  used: number;
  total: number;
}

export function GuestAllowance({ used, total }: GuestAllowanceProps) {
  const left = Math.max(0, total - used);
  return (
    <Box
      data-testid="guest-allowance"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: 1.25,
        px: 1.75,
        py: 0.7,
        borderRadius: 999,
        border: `1px solid ${designTokens.line}`,
        bgcolor: designTokens.surface,
        fontSize: 12.5,
        color: designTokens.inkMuted,
      }}
    >
      <Box sx={{ display: "flex", gap: 0.4 }} aria-hidden="true">
        {Array.from({ length: total }, (_, index) => (
          <Box
            key={index}
            sx={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              bgcolor: index < used ? designTokens.lineStrong : designTokens.blue,
            }}
          />
        ))}
      </Box>
      <Typography variant="caption">
        {left === 1 ? "1 search left" : `${left} searches left`}
      </Typography>
    </Box>
  );
}

export interface SignInWallProps {
  onSignIn?: () => void;
}

/**
 * The wall. It arrives having already delivered five answers, which is the
 * whole argument for the allowance: a researcher who has seen the product work
 * is being asked to sign in to keep something, not to try something.
 */
export function SignInWall({ onSignIn }: SignInWallProps) {
  return (
    <Box sx={{ maxWidth: 900, mx: "auto", px: 3, py: 3.5 }}>
      <Box
        data-testid="sign-in-wall"
        sx={{
          border: `1px solid ${designTokens.lineStrong}`,
          borderRadius: 1,
          bgcolor: designTokens.surface,
          p: { xs: 3, sm: 4.5 },
          textAlign: "center",
        }}
      >
        <Typography variant="h2" component="h1" sx={{ fontSize: 22, mb: 1 }}>
          Sign in to keep searching
        </Typography>
        <Typography sx={{ color: designTokens.inkMuted, mb: 2.5, fontSize: 14.5 }}>
          {/*
            F-4.10-01. This read "Your history moves with you when you sign
            in," which overstated what actually happens: nothing persists a
            run across a reload today (the run registry is in-memory and
            evicts, and the browser's history list is React state), so
            there is no cross-reload history to carry anywhere. What DOES
            move, and what design decision 4 (`tracker/phase_4.10.md`)
            actually built: the searches from THIS visit re-point to the
            new account the moment you sign in. Durable history across a
            reload is build phase 4.6's, tracked in `stubs/registry.ts`.
          */}
          You have used your free searches. The ones from this visit move with
          you when you sign in.
        </Typography>
        <Button variant="contained" onClick={onSignIn} sx={{ px: 2.5, py: 1.1 }}>
          Create account or sign in
        </Button>
      </Box>
    </Box>
  );
}

export default GuestAllowance;
