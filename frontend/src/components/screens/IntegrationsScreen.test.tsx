/**
 * Fix set 5, items 5.1, 5.2, 5.4 and 5.6: requirements R15, R16, R18 and R41,
 * product-owner decision U3.
 *
 * These arms pin the four facts the rebuild is judged on, each of which the
 * old page got wrong in a way that read as fine:
 *
 * - Exactly FOUR cards, with the four titles decision U3 names. Five cards of
 *   uneven height is what R15 records, and a count taken over the whole page
 *   would have passed at five, so the count is scoped to the card grid.
 * - The four summary chips, with the real figures R41 names.
 * - No Docs tab anywhere in the assembled app's navigation (R18).
 * - The GraphQL example is a MUTATION using `text` and `sessionId` (R16). The
 *   old one was a query using `question` with no session id, and failed three
 *   ways when the product owner pasted it.
 * - The MCP configuration names the `/mcp` path, rather than the elided
 *   `https://.../mcp` that T-4.16-04 already removed once.
 *
 * COVERAGE STATEMENT, per `goal-contracts`:
 *
 *   Exercised:      the card count and titles, the chips, the absence of a
 *                   Docs tab in the assembled app, the text the copy controls
 *                   actually write to the clipboard, and the code the MCP card
 *                   renders.
 *
 *   NOT exercised:  that the GraphQL document is ACCEPTED by the live API.
 *                   No unit test can know that, and pretending otherwise is
 *                   the failure R16 exists because of. It was verified by
 *                   posting the exact printed text to the develop API on
 *                   2026-09-13 (200, a real answer, five citations, no
 *                   validation error), and that verification is recorded in
 *                   `InfoScreens.tsx`'s own docstring.
 *
 *                   Equal card HEIGHT and button ALIGNMENT, which are layout
 *                   rather than DOM. LEARNINGS.md's 2026-08-14 entry is the
 *                   reason this is stated rather than claimed: `order: -1`
 *                   moves an element across the page while every DOM-order
 *                   assertion stays green. Geometry lives in `e2e/`.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { IntegrationsScreen } from "./InfoScreens";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ApiError: actual.ApiError,
    // Every export `App` calls in an effect has to exist here: an api mock
    // that omits one throws inside a `useEffect` and takes the whole render
    // down, which reads as a failure of whatever the arm was actually
    // asserting.
    fetchPersona: vi.fn(async () => ({ persona_name: "Mendel" })),
    fetchMe: vi.fn(async () => ({
      id: "u-1",
      email: "a@example.com",
      audience_depth: "researcher",
      persona_name: "Mendel",
    })),
    login: vi.fn(),
    signup: vi.fn(),
    createRun: vi.fn(),
    openEventStream: vi.fn(),
    stopRun: vi.fn(),
    mintGuest: vi.fn(),
    getAllowance: vi.fn(async () => ({ kind: "user", used: 0, total: 100, counted: false })),
    fetchHistory: vi.fn(async () => ({ items: [], count: 0 })),
    refreshSession: vi.fn(),
    logoutSession: vi.fn(async () => ({ status: "ok" })),
  };
});

const CARD_TITLES = ["REST and SSE", "GraphQL", "MCP server", "Command line tools"];
const CHIP_LABELS = ["115M nodes", "693M edges", "3 data layers", "7 tools"];

const cards = () => within(screen.getByTestId("integration-cards"));

describe("the integrations page, rebuilt from the reference layout", () => {
  it("shows exactly four cards, with the four titles decision U3 names", () => {
    render(<IntegrationsScreen />);

    const headings = cards()
      .getAllByRole("heading", { level: 2 })
      .map((node) => node.textContent?.trim());

    // COUNT and MEMBERSHIP together. Membership alone passed on the old
    // five-card page for every title it happened to keep.
    expect(headings).toEqual(CARD_TITLES);
  });

  it("shows the four summary chips with the real figures", () => {
    render(<IntegrationsScreen />);

    const summary = within(screen.getByRole("list", { name: /what the agent is built on/i }));
    const labels = summary.getAllByRole("listitem").map((node) => node.textContent?.trim());

    expect(labels).toEqual(CHIP_LABELS);
  });

  it("carries no card for KGX export or the command line on its own", () => {
    // The two old cards MERGED, they were not dropped. This arm is what
    // distinguishes "four cards" from "four cards because two surfaces
    // vanished": the merged card names both commands in its own body.
    render(<IntegrationsScreen />);

    expect(cards().queryByRole("heading", { name: /^KGX export$/ })).toBeNull();
    expect(cards().queryByRole("heading", { name: /^Command line$/ })).toBeNull();

    const merged = cards().getByRole("heading", { name: "Command line tools" }).parentElement;
    expect(merged).not.toBeNull();
    expect(merged).toHaveTextContent("s3-kgx-export");
  });

  it("renders the MCP configuration, naming the /mcp path", () => {
    render(<IntegrationsScreen />);

    const config = screen.getByRole("region", { name: /MCP server configuration/i });
    expect(config).toHaveTextContent("/mcp");
    expect(config).toHaveTextContent("mcpServers");
  });

  it("puts the API documentation section on the page, with the real event names", () => {
    render(<IntegrationsScreen />);

    expect(screen.getByRole("heading", { name: /^API documentation$/ })).toBeInTheDocument();

    const frame = screen.getByRole("region", { name: /event stream example/i });
    // The real SSE frame shape, `adapters/web_sse/app.py`'s own emitter:
    // the sequence number as `id`, the type as the event name, the whole
    // envelope as `data`. The old page invented a one-line form with no
    // envelope at all.
    expect(frame).toHaveTextContent("event: guard");
    expect(frame).toHaveTextContent('"version":"v1"');

    // R18's other half: the guest-search sentence is gone. There has been no
    // five-search guest limit since fix set 1, and the anonymous daily cap is
    // the only guest bound left.
    expect(screen.queryByText(/free allowance/i)).toBeNull();
    expect(screen.getByText(/anonymous daily cap/i)).toBeInTheDocument();
  });

  describe("the copy controls", () => {
    // Typed with its parameter so `mock.calls[0][0]` is a `string` rather than
    // an out-of-range index on an empty tuple, which is what `vi.fn(async () =>
    // undefined)` gives and what `tsc -b` rejects.
    const writeText = vi.fn(async (text: string) => {
      void text;
    });

    /**
     * ORDER IS LOAD-BEARING, and it cost a debugging round to find.
     * `userEvent.setup()` calls `attachClipboardStubToView`, which
     * unconditionally redefines `navigator.clipboard` with its own stub
     * (`node_modules/@testing-library/user-event/dist/cjs/utils/dataTransfer/
     * Clipboard.js`). A spy installed in a `beforeEach` is therefore gone by
     * the time the component runs, and every arm below would assert against a
     * function the page never called. So the spy is installed AFTER setup, by
     * this helper, which is the only way either half of the pair gets used.
     */
    /* A REST PARAMETER RATHER THAN A DEFAULT VALUE, and this is not style.
       Written first as `(clipboard = { writeText })`, an explicit
       `setupWithClipboard(undefined)` still took the default, so the
       clipboard-absent arm installed a WORKING clipboard and passed while
       asserting the failure path. It reported "Copied to clipboard." An arm
       that cannot distinguish absence from presence is not an arm. */
    const setupWithClipboard = (...args: [clipboard?: unknown]) => {
      const user = userEvent.setup();
      Object.defineProperty(navigator, "clipboard", {
        value: args.length > 0 ? args[0] : { writeText },
        configurable: true,
      });
      return user;
    };

    beforeEach(() => {
      writeText.mockClear();
    });

    it("writes a GraphQL MUTATION using text and sessionId (R16)", async () => {
      const user = setupWithClipboard();
      render(<IntegrationsScreen />);

      await user.click(cards().getByTestId("integration-copy-graphql"));

      expect(writeText).toHaveBeenCalledTimes(1);
      const copied = writeText.mock.calls[0][0];

      // The three defects the product owner hit, each pinned separately so a
      // failure says which one came back.
      expect(copied, "the example is not a mutation").toContain("mutation");
      expect(copied, "the question field is not `text`").toContain("text:");
      expect(copied, "the required session id is missing").toContain("sessionId");
      expect(copied, "`question` was the old, wrong field name").not.toContain("question:");
    });

    it("writes the REST curl, the MCP config and both console commands", async () => {
      const user = setupWithClipboard();
      render(<IntegrationsScreen />);

      for (const [testId, expected] of [
        ["integration-copy-rest", "/v1/query"],
        ["integration-copy-mcp", "/mcp"],
        ["integration-copy-cli", "s3 ask"],
        ["integration-copy-kgx", "s3-kgx-export"],
      ] as const) {
        writeText.mockClear();
        await user.click(cards().getByTestId(testId));
        expect(writeText, `${testId} copied nothing`).toHaveBeenCalledTimes(1);
        expect(writeText.mock.calls[0][0]).toContain(expected);
      }
    });

    it("says so when the clipboard is unavailable, rather than looking like nothing happened", async () => {
      const user = setupWithClipboard(undefined);
      render(<IntegrationsScreen />);

      await user.click(cards().getByTestId("integration-copy-rest"));

      expect(await screen.findByRole("status")).toHaveTextContent(/copy it by hand/i);
    });
  });
});

describe("the assembled app after Docs was folded in (R18)", () => {
  it("offers no Docs tab in the main navigation", async () => {
    const { default: App } = await import("../../App");
    render(<App />);

    const nav = within(screen.getByRole("navigation", { name: /main/i }));
    expect(nav.queryByRole("button", { name: /^docs$/i })).toBeNull();
    expect(nav.queryByRole("link", { name: /^docs$/i })).toBeNull();
    // POPULATE-CHECK. Without this, a nav that failed to render at all would
    // satisfy both assertions above and report a pass.
    expect(nav.getByRole("button", { name: /^integrations$/i })).toBeInTheDocument();
  });
});
