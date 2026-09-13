/**
 * `lib/routing.ts`, the path-to-screen mapping.
 *
 * WHY THIS FILE EXISTS. `e2e/routing.spec.ts` already proves routing in a
 * real browser, and it stays the arm that carries the weight, because the
 * back button is a browser behaviour no component tree can demonstrate. What
 * it cannot do cheaply is prove the TABLE is complete: adding a screen to
 * `ScreenName` without adding its path leaves `PATH_BY_SCREEN` missing an
 * entry, and TypeScript catches that, while adding the path and mistyping it
 * compiles fine and sends the browser suite looking for a page at the wrong
 * address. These arms read the table directly.
 *
 * COVERAGE STATEMENT, per `goal-contracts`:
 *
 *   Exercised:      every entry of `PATH_BY_SCREEN` round-trips through
 *                   `screenForPath`, the `/architecture` path specifically,
 *                   trailing-slash tolerance, the `/docs` legacy alias, and
 *                   the unknown-path fallback.
 *
 *   NOT exercised:  `useScreenRoute`, which pushes history and listens for
 *                   `popstate`. Both are browser behaviours and both are
 *                   covered by `e2e/routing.spec.ts`, whose back-button arm
 *                   is the one a push-only implementation fails.
 */

import { describe, expect, it } from "vitest";

import { DEFAULT_SCREEN, LEGACY_PATHS, PATH_BY_SCREEN, screenForPath } from "./routing";

describe("screenForPath", () => {
  it("round-trips every screen in the table", () => {
    // Derived from the table rather than restated, so a screen added without
    // a path cannot pass by being left out of a hand-written list here.
    for (const [screen, path] of Object.entries(PATH_BY_SCREEN)) {
      expect(screenForPath(path), `${path} did not resolve to ${screen}`).toBe(screen);
    }
  });

  it("owns the four paths the app actually has", () => {
    // The membership assertion the loop above cannot make: it proves each
    // entry is consistent, not that the right entries exist. A missing
    // Architecture route would leave the loop green and this arm red.
    expect(PATH_BY_SCREEN).toEqual({
      search: "/",
      integrations: "/integrations",
      about: "/about",
      architecture: "/architecture",
    });
  });

  it("resolves the architecture path, with or without a trailing slash", () => {
    expect(screenForPath("/architecture")).toBe("architecture");
    expect(screenForPath("/architecture/")).toBe("architecture");
  });

  it("still lands a retired path on the screen that holds its content", () => {
    for (const [path, screen] of Object.entries(LEGACY_PATHS)) {
      expect(screenForPath(path)).toBe(screen);
    }
    expect(screenForPath("/docs")).toBe("integrations");
  });

  it("falls back to the landing screen for a path the app does not own", () => {
    expect(screenForPath("/not-a-real-page")).toBe(DEFAULT_SCREEN);
    // Near misses, which are the ones a typo produces. `/architecture` is a
    // new route and `/architectures` must not quietly resolve to it.
    expect(screenForPath("/architectures")).toBe(DEFAULT_SCREEN);
    expect(screenForPath("/arch")).toBe(DEFAULT_SCREEN);
  });
});
