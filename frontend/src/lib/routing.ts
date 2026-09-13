/**
 * Client-side routing for the three top-level screens.
 *
 * T-4.16-05, the product owner's defect 6 from the live demo: "NO
 * CLIENT-SIDE ROUTING. Every page is served at `/` and the URL never
 * changes." The routes were given verbatim and are the whole contract:
 *
 *     Home          /
 *     Integrations  /integrations
 *     About         /about
 *     Architecture  /architecture   (added 2026-09-13, see below)
 *     Docs          /docs      (removed as a screen, R18; now an alias)
 *
 * UPDATED 2026-09-13, the product owner's architecture request. `/architecture`
 * is a fourth REAL screen, so it joins `PATH_BY_SCREEN` rather than
 * `LEGACY_PATHS`: navigating to it must put `/architecture` in the address
 * bar, which is exactly the direction a one-way legacy entry cannot serve.
 * It has NO item in the app bar (product-owner decision the same evening):
 * it is reached from About's "Explore the architecture" link and by its
 * address, and this table is what makes the address work.
 *
 * UPDATED 2026-09-13, fix set 5 (R18). Docs is no longer a screen: its
 * content is the "API documentation" section inside Integrations. `/docs`
 * therefore resolves to `integrations` rather than 404-ing or falling back to
 * the landing screen, because an existing link or bookmark to `/docs` should
 * land on the page that now holds that content. It is an ALIAS rather than a
 * second name for the screen: `PATH_BY_SCREEN` still maps `integrations` to
 * `/integrations`, so navigating never puts `/docs` back in the address bar.
 *
 * WHY NO ROUTER DEPENDENCY. `frontend/package.json` has none today, and
 * this adds none. `production-standards.md` requires a security review for
 * every new dependency and `system-design-patterns` puts that in the ASK
 * bucket, which would be the right thing to pay for a routing library that
 * earned it. This does not: there are four static paths, one alias, no
 * parameters, no
 * nested layouts, no loaders, and one already-existing piece of state
 * (`App.tsx`'s `screen`) that a router would only end up mirroring. The
 * History API covers it in a few lines, adds nothing to the bundle, and
 * introduces no new execution surface. If this app later grows real route
 * parameters or nested layouts, revisit it then and pay for the review
 * properly rather than pre-paying now.
 *
 * WHY DEEP LINKS ALREADY WORK ON THE SERVER, so nothing outside this file
 * changes: the frontend is served by `serve -s dist` (`package.json`'s
 * `serve` script), and `-s` is single-page-app mode, which rewrites an
 * unknown path to `index.html`. So `/integrations` has always reached the
 * app; there was simply no code to read it. `tracker/phase_4.12.md` records
 * the same conclusion.
 */

import { useEffect, useState } from "react";

import type { ScreenName } from "../components/shell/AppShell";

/**
 * The one mapping, screen to path. Deliberately not two objects: a
 * hand-maintained inverse is how the two halves drift, and `screenForPath`
 * below derives its direction from this rather than restating it.
 */
export const PATH_BY_SCREEN: Record<ScreenName, string> = {
  search: "/",
  integrations: "/integrations",
  about: "/about",
  architecture: "/architecture",
};

/**
 * Paths this app once owned as screens of their own and now resolves
 * elsewhere.
 *
 * Deliberately separate from `PATH_BY_SCREEN` rather than an extra entry in
 * it: that map is read in BOTH directions, and an entry here would make
 * `navigate("integrations")` push whichever of the two paths the lookup
 * happened to find first. A one-way table cannot do that.
 */
export const LEGACY_PATHS: Record<string, ScreenName> = {
  // R18, 2026-09-13. Docs folded into the Integrations page.
  "/docs": "integrations",
};

/** The landing screen, and the answer for any path this app does not own. */
export const DEFAULT_SCREEN: ScreenName = "search";

/**
 * Resolve a URL path to a screen.
 *
 * An unknown path falls back to the landing screen rather than rendering
 * nothing. `serve -s` has already rewritten it to `index.html`, so by the
 * time this runs the alternative is a blank page, which is the one outcome
 * `production-standards.md`'s graceful-degradation gate rules out.
 *
 * A trailing slash is tolerated (`/about/` is `/about`) because a person
 * typing or a link generator adding one is not a different page. The root
 * is special-cased first so `"/"` does not normalise to `""`.
 *
 * `LEGACY_PATHS` is consulted after the real screens and before the
 * fallback, so `/docs` reaches Integrations while a path nobody ever owned
 * still reaches the landing screen.
 */
export function screenForPath(pathname: string): ScreenName {
  const normalized =
    pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
  const match = (Object.keys(PATH_BY_SCREEN) as ScreenName[]).find(
    (screen) => PATH_BY_SCREEN[screen] === normalized,
  );
  return match ?? LEGACY_PATHS[normalized] ?? DEFAULT_SCREEN;
}

/**
 * Keep one `ScreenName` and the address bar in step, in both directions.
 *
 * Returns the current screen and a setter that also pushes history, so a
 * caller replaces its `useState<ScreenName>` with this and changes nothing
 * else. The two directions are genuinely different and both are needed:
 *
 * - Forward: navigating in the app pushes a new entry, so the URL is
 *   shareable and the back button has somewhere to go.
 * - Back: the browser's back and forward buttons fire `popstate`, which
 *   this listens for and turns into a state change. Without that half the
 *   URL would change and the page would not, which is worse than no
 *   routing at all because the address bar would then be lying.
 *
 * `pushState` is skipped when the path is already correct. Otherwise
 * clicking the current nav item would stack duplicate history entries and
 * the back button would appear stuck.
 *
 * MUTATION-PROVEN, not argued. Removing the `popstate` effect below leaves
 * `e2e/routing.spec.ts`'s URL arm and deep-link arm GREEN and fails only
 * its back-button arm, with "the URL went back but the page did not, so
 * the address bar is lying". Run before this landed. That asymmetry is the
 * point: three of the four arms cannot see the difference between routing
 * and half-routing.
 */
export function useScreenRoute(): [ScreenName, (next: ScreenName) => void] {
  const [screen, setScreenState] = useState<ScreenName>(() =>
    screenForPath(window.location.pathname),
  );

  useEffect(() => {
    const onPopState = () => setScreenState(screenForPath(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = (next: ScreenName) => {
    setScreenState(next);
    const path = PATH_BY_SCREEN[next];
    if (window.location.pathname !== path) {
      window.history.pushState({}, "", path);
    }
  };

  return [screen, navigate];
}
