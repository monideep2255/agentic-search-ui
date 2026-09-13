/**
 * Fix set 4, R46 (decision U9, 2026-09-13): history reachable on a phone.
 *
 * `railCollapsePremise.test.tsx` and `FollowUp.nextStep.test.tsx` run in
 * jsdom's default `matchMedia`, which always reports `matches: false`, so
 * neither file can see the narrow branch this fix adds. This file mocks
 * `window.matchMedia` to report narrow instead, the same technique
 * `e2e/rail-collapse.spec.ts` cannot use (it runs in a real browser, where
 * the viewport itself decides) and jsdom's default state cannot exercise.
 *
 * Coverage statement, per `goal-contracts`: this file exercises the
 * Drawer branch of `HistoryRail` and the null branch of `CollapsedRail` at
 * the component level, with `matchMedia` mocked rather than measured. It
 * does not exercise real layout geometry (the drawer's pixel width, the
 * slide-in animation, whether it actually overlays the page rather than
 * pushing it) or the app bar's own toggle, which live in
 * `e2e/rail-collapse.spec.ts`'s narrow-viewport describe block instead.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CollapsedRail, HistoryRail } from "./FollowUp";

const ITEMS = [{ id: "q-1", question: "Which diseases are associated with BRCA1?", meta: "2 sources" }];

/**
 * Stand in for `window.matchMedia`, reporting `matches` for every query.
 *
 * MUI's `useMediaQuery` reads `.matches` once and listens for `change`
 * events; no clause here resizes mid-test, so the listener plumbing only
 * needs to exist, not fire.
 */
function mockMatchMedia(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

describe("the history rail on a phone", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("narrow (below md)", () => {
    beforeEach(() => {
      mockMatchMedia(true);
    });

    it("renders the rail inside a dialog panel, with its items visible", () => {
      render(<HistoryRail items={ITEMS} />);

      const panel = screen.getByRole("dialog", { name: /your searches/i });
      const rail = within(panel).getByTestId("history-rail");
      expect(within(rail).getByText(/diseases are associated with BRCA1/i)).toBeInTheDocument();
    });

    it("closes through the rail's own close button, calling onCollapse once", async () => {
      const user = userEvent.setup();
      const onCollapse = vi.fn();
      render(<HistoryRail items={ITEMS} onCollapse={onCollapse} />);

      // The SAME control named "Hide your searches" that the desktop rail
      // already carries in its `.rtop` row, not a second control with the
      // same name: the task's own instruction is that exactly one control
      // may carry this accessible name in each mode.
      await user.click(screen.getByRole("button", { name: /^hide your searches$/i }));
      expect(onCollapse).toHaveBeenCalledTimes(1);
    });

    it("renders nothing for the collapsed strip", () => {
      render(<CollapsedRail count={3} />);
      expect(screen.queryByTestId("collapsed-rail")).not.toBeInTheDocument();
    });
  });

  describe("wide (md and above)", () => {
    beforeEach(() => {
      mockMatchMedia(false);
    });

    it("renders the rail inline, with no dialog role anywhere", () => {
      render(<HistoryRail items={ITEMS} />);

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      const rail = screen.getByTestId("history-rail");
      expect(within(rail).getByText(/diseases are associated with BRCA1/i)).toBeInTheDocument();
    });

    it("renders the collapsed strip", () => {
      render(<CollapsedRail count={3} />);
      expect(screen.getByTestId("collapsed-rail")).toBeInTheDocument();
    });
  });
});
