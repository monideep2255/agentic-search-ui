/**
 * Which deployment a live browser check points at, and proof of which one
 * actually answered.
 *
 * Build phase 6.2, T-6.2-12.
 *
 * ## Why this exists
 *
 * Every piece of evidence in `testing/UI_feedback.md` was gathered against
 * PRODUCTION, and that was the wrong target. Production moves only on a
 * deliberate release, so it lags whatever anyone is working on, and a
 * browser run there measures an older build than the one being fixed. The
 * two live diagnostics in this directory each hardcoded the production web
 * URL, so there was no way to point them anywhere else short of editing
 * them.
 *
 * The default is now DEVELOP. Production is checked only when confirming a
 * release actually shipped what it claimed, and that is an explicit
 * override rather than the path of least resistance.
 *
 * ## The `app_env` capture is not decoration
 *
 * A screenshot of an answer screen looks identical whichever deployment
 * produced it. Committing one under `testing/evidence/` without
 * recording which app answered produces evidence that cannot be compared
 * against a later run, which is the failure `testing/UI_feedback.md` hit from the
 * other side: its own measurements are correct and were taken against the
 * wrong build, and nothing in them says so.
 *
 * So `describeTarget` asks the API's own `/health` for the `app_env` it
 * reports about ITSELF, rather than inferring the environment from the URL
 * string. A URL is what someone intended to hit; `app_env` is what
 * answered. Those differ exactly when it matters most, which is when a
 * variable is set wrong, and build phase 4.15 shipped precisely that defect:
 * a develop web app that was live, answered 200, and could reach no API at
 * all, because `VITE_API_BASE_URL` is compiled in at BUILD time.
 */

const DEVELOP_WEB = "https://search-agent-web-develop-2aeb.up.railway.app";
const DEVELOP_API = "https://search-agent-api-develop-43b3.up.railway.app";

/**
 * Loopback is allowed, and this is a carve-out rather than a hole.
 *
 * The `https://` rule exists because a live check spends a real guest
 * allowance and real model budget against whatever it is pointed at, so a
 * typo resolving to some plaintext host would burn a run and produce
 * evidence about nothing. Loopback is not that case: `playwright.config.ts`
 * boots a full local stack, Vite on 5273 and FastAPI on 8931 with the
 * outbound model call FAKED, so a capture against it spends no allowance
 * and no budget at all.
 *
 * Refusing it had a real cost, found by hitting it: the first version of
 * this file made it impossible to film a UI change before that change was
 * deployed anywhere, which is precisely when someone wants to look at it.
 *
 * Only the two loopback literals, never a bare hostname. `http://internal`
 * or `http://localhost.evil.example` are still refused.
 */
const LOOPBACK = ["http://127.0.0.1:", "http://localhost:"];

/**
 * The web app a live check drives. Override with `S3_LIVE_WEB_URL`.
 *
 * Rejects anything that is not `https://`. These specs spend a real guest
 * allowance and real model budget against whatever they are pointed at, so
 * a typo that silently resolved to a local or plaintext host would burn a
 * run and produce evidence about nothing.
 */
export const LIVE_WEB_URL = requireHttps(
  process.env.S3_LIVE_WEB_URL ?? DEVELOP_WEB,
  "S3_LIVE_WEB_URL",
);

/** The API behind it. Override with `S3_LIVE_API_URL`. */
export const LIVE_API_URL = requireHttps(
  process.env.S3_LIVE_API_URL ?? DEVELOP_API,
  "S3_LIVE_API_URL",
);


function requireHttps(url: string, variable: string): string {
  if (LOOPBACK.some((prefix) => url.startsWith(prefix))) return url;
  if (!url.startsWith("https://")) {
    throw new Error(
      `${variable} must be an https:// URL or a loopback address, got ` +
        `${JSON.stringify(url)}. A live check spends a real guest allowance ` +
        `against whatever it is pointed at, so an unreachable or plaintext ` +
        `remote target is refused rather than attempted.`,
    );
  }
  return url;
}

/**
 * A one-line description of what actually answered, for the run log and for
 * the caption on any committed screenshot.
 *
 * Never throws. A failure to reach `/health` must not fail a diagnostic
 * whose job is to capture what the page looks like: it degrades to naming
 * the environment as unknown, which is still more honest than a caption
 * that asserts an environment nothing confirmed.
 */
export async function describeTarget(): Promise<string> {
  let appEnv = "unreachable";
  try {
    const response = await fetch(`${LIVE_API_URL}/health`);
    const body = (await response.json()) as { app_env?: unknown };
    if (typeof body.app_env === "string" && body.app_env.trim()) {
      appEnv = body.app_env.trim();
    } else {
      appEnv = "unknown";
    }
  } catch {
    appEnv = "unreachable";
  }
  return `web=${LIVE_WEB_URL} api=${LIVE_API_URL} app_env=${appEnv}`;
}
