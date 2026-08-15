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

/**
 * Which of the wall's triggers is showing it (F-4.10-R-02).
 *
 * The wall used to render one sentence for every trigger, and that sentence
 * was true on only one of them. This type exists so a trigger cannot be
 * added without choosing what the screen then says: a new member here is a
 * compile error in `WALL_COPY` below until its copy is written.
 *
 * - `allowance_exhausted`: the server refused with 403
 *   `guest_allowance_exhausted`. Five answers delivered, five spent.
 * - `attempt_limit`: the server refused with 403
 *   `guest_attempt_limit_reached` (F-4.10-R-01). This visitor started as
 *   many runs as a guest may start, and may have received no answer at all,
 *   so any sentence about "used your free searches" is false here.
 * - `migrated`: this browser's guest session was moved into an account, at
 *   signup or at login, and the server revoked it. Reached from `ask`'s
 *   pre-flight check on a signed-out migrated browser and from a 401
 *   carrying `guest_session_revoked`. `runs_used` can be anything from 0 to
 *   5 on this path, including a visitor who created an account without ever
 *   asking a question, which is why no count and no "used" can appear.
 */
export type SignInWallReason = "allowance_exhausted" | "attempt_limit" | "migrated";

/**
 * One sentence per trigger, each true on that trigger and on no assumption
 * about the others.
 *
 * F-4.10-R-02 is the third copy fix in this phase to have replaced a false
 * statement with another false statement, so the discipline here is
 * explicit: a sentence is written against the ONE state that renders it, and
 * a state with a different truth gets its own sentence rather than a
 * broadened one. "You have used your free searches" is true only for
 * `allowance_exhausted`; the two paths below converted or exhausted
 * something else entirely.
 */
const WALL_COPY: Record<SignInWallReason, string> = {
  allowance_exhausted:
    "You have used your free searches. Sign in or create an account to keep going.",
  attempt_limit:
    "You have asked as many questions as a guest can. Sign in or create an account to keep going.",
  migrated:
    "This browser's guest session was moved into an account. Sign in to keep searching.",
};

export interface SignInWallProps {
  onSignIn?: () => void;
  /**
   * Defaults to `allowance_exhausted`, the trigger this screen was built
   * for and the only one that existed before the sign-out fix. A default
   * rather than a required prop so no caller can render the wall with no
   * sentence at all; every caller in `App.tsx` passes one explicitly.
   */
  reason?: SignInWallReason;
}

/**
 * The wall. On its original trigger it arrives having already delivered five
 * answers, which is the whole argument for the allowance: a researcher who
 * has seen the product work is being asked to sign in to keep something, not
 * to try something. It now has two further triggers, and each says its own
 * true thing rather than borrowing that one's sentence.
 */
export function SignInWall({ onSignIn, reason = "allowance_exhausted" }: SignInWallProps) {
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
            THE PROMISE IS GONE, not narrowed a second time (F-4.10-A-07).

            F-4.10-01 narrowed "Your history moves with you when you sign in"
            to "The ones from this visit move with you when you sign in." That
            is still false in the one situation this component is displayed
            in, which is the situation that matters. The wall appears on the
            SIXTH search, so by construction the visitor has already run five,
            and migration reaches only runs the in-memory `RunRegistry` still
            holds: `_evict_expired` drops any run finished more than
            `DEFAULT_RETENTION_SECONDS` (300) ago. Every search older than
            five minutes is already gone, and the sentence promised all of
            them. Measured with retention forced to zero: signup returns 201,
            `reassign_owner` moves nothing, and the new account reading that
            run gets a 404.

            There is a second reason no narrower wording would have been
            honest either. Nothing in the UI shows a migrated run: the
            browser's history list is React state that survives sign-in in
            the same tab whether migration happened or not, so the promise
            has no observable referent even when the server-side move works.

            Dropping it rather than qualifying it a third time. What is left
            is true and is the only thing this screen needs to say: the free
            searches are spent, and an account is how to keep going. Durable
            history is build phase 4.6's, tracked in `stubs/registry.ts`, and
            the copy can make a promise about it once there is one to keep.

            F-4.10-R-02: that remaining sentence was still false on two of
            the three triggers this screen now has, because the sign-out fix
            added them without revisiting what the screen says. The sentence
            is now one of three in `WALL_COPY` above, selected by `reason`,
            and none of them claims searches were used unless they were.
          */}
          {WALL_COPY[reason]}
        </Typography>
        <Button variant="contained" onClick={onSignIn} sx={{ px: 2.5, py: 1.1 }}>
          Create account or sign in
        </Button>
      </Box>
    </Box>
  );
}

export default GuestAllowance;
