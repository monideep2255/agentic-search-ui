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
// Card 62, PR-8.10-09: a full path, since an agent app does not read the
// shell's PATH. The card says to replace it with what `command -v s3` prints.
const AGENT_CONFIG = {
  mcpServers: { system3: { command: "/path/to/s3-env/bin/s3", args: ["mcp"] } },
};
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

  it("prints the agent configuration for s3 mcp, and says it is not for a terminal", () => {
    // Build phase 8.10's fix round, F-8.10-J10 and A12: the page named `s3
    // mcp` but printed nothing to paste into an agent, and `s3 mcp` typed at
    // a terminal only waits for input. Mutation that turns this red: drop the
    // code block, or the sentence that says where it goes.
    render(<IntegrationsScreen />);

    const config = screen.getByRole("region", { name: /Agent configuration for s3 mcp/i });
    expect(JSON.parse(config.textContent ?? "")).toEqual(AGENT_CONFIG);
    const card = cards().getByRole("heading", { name: "Command line tools" }).parentElement;
    expect(card).toHaveTextContent(/not typed into a terminal/);
    expect(card).toHaveTextContent(/pasted into the agent's MCP settings/);
  });

  it("tells the reader to put the full path to s3 in the agent configuration", () => {
    // Card 62, PR-8.10-09 (F-8.10-V10): an agent app opened from the Dock
    // does not read the shell's PATH, so the bare `"command": "s3"` failed
    // to start with "No such file or directory: 's3'". Mutation that turns
    // this red: print the bare `s3` again, or drop the sentence naming
    // `command -v s3`.
    render(<IntegrationsScreen />);

    const config = screen.getByRole("region", { name: /Agent configuration for s3 mcp/i });
    const command = JSON.parse(config.textContent ?? "").mcpServers.system3.command;
    expect(command.startsWith("/"), "the configuration names a full path").toBe(true);
    const card = cards().getByRole("heading", { name: "Command line tools" }).parentElement;
    expect(card).toHaveTextContent(`replace ${command} with the full path that command -v s3 prints`);
    // Card 62's fix round (F-62-A04): `command -v s3` prints nothing outside
    // the environment, so the sentence says where to run it. Mutation that
    // turns this red: drop "inside the virtual environment".
    expect(card).toHaveTextContent(
      "command -v s3 prints inside the virtual environment, after . s3-env/bin/activate",
    );
  });

  it("says how to enter the environment again in a new terminal, before s3 login or s3 ask", () => {
    // Card 62's fix round (F-62-A04): the page's `s3 login` and `s3 ask`
    // gave "command not found: s3" in any terminal but the install's own.
    // Mutation that turns this red: drop the sentence.
    render(<IntegrationsScreen />);

    const card = cards().getByRole("heading", { name: "Command line tools" }).parentElement;
    expect(card).toHaveTextContent(
      "In a new terminal, enter it again with . s3-env/bin/activate from the same folder before s3 login or s3 ask.",
    );
  });

  it("shows its commands in code boxes, in the order a reader runs them, not as prose", () => {
    // Card 79: the install command was copied but never shown, and the
    // card was one 300-word paragraph. Mutation that turns this red: drop a
    // code box, or put the install after the sign-in example.
    render(<IntegrationsScreen />);

    const card = cards().getByRole("heading", { name: "Command line tools" }).parentElement as HTMLElement;
    const install = within(card).getByRole("region", { name: /Install command for s3/i });
    const ask = within(card).getByRole("region", { name: /Sign in and ask with s3/i });
    const config = within(card).getByRole("region", { name: /Agent configuration for s3 mcp/i });
    expect(install.textContent).toContain("python3.11 -m venv s3-env");
    expect(ask.textContent).toContain('s3 ask "diseases linked to BRCA1"');
    expect(install.compareDocumentPosition(ask) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(ask.compareDocumentPosition(config) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    for (const paragraph of card.querySelectorAll("p")) {
      expect((paragraph.textContent ?? "").split(/\s+/).length, "a paragraph runs on").toBeLessThan(90);
    }
  });

  it("says what the install needs, before the commands: git, Python 3.11, macOS or Linux", () => {
    // Card 62, PR-8.10-04: macOS's own Python 3.9 failed with "No matching
    // distribution found for setuptools==83.0.0", and Homebrew's Python
    // outside a virtual environment refused with
    // "externally-managed-environment". Its fix round (F-62-J01, J07, A03):
    // git and the platforms were never named. Mutation that turns this red:
    // drop the sentence, or move it after the commands.
    render(<IntegrationsScreen />);

    const card = cards().getByRole("heading", { name: "Command line tools" }).parentElement;
    expect(card).toHaveTextContent(/works on macOS and Linux and needs git and Python 3\.11/);
    expect(card).toHaveTextContent(/virtual environment/);
    const needs = within(card as HTMLElement).getByText(/needs git and Python 3\.11/);
    const install = within(card as HTMLElement).getByTestId("integration-copy-install");
    expect(
      needs.compareDocumentPosition(install) & Node.DOCUMENT_POSITION_FOLLOWING,
      "the requirements come before the install command",
    ).toBeTruthy();
  });

  it("says s3-kgx-export is not in the s3 install, and how a KGX file is had today", () => {
    // Card 62, PR-8.10-03: the card said both commands were "installed once
    // with pip", and after the page's own install `s3-kgx-export` was
    // "command not found". Its fix round (F-62-J02, J03, A07): the page
    // printed an install of the whole server with version floors, which
    // also deleted `s3` when removed. No KGX install is printed now; the
    // card says the operator runs it. Mutation that turns this red: put
    // back the KGX copy, or "installed once with pip".
    render(<IntegrationsScreen />);

    const card = cards().getByRole("heading", { name: "Command line tools" }).parentElement;
    expect(card).not.toHaveTextContent(/installed once with pip/);
    expect(card).toHaveTextContent(/s3-kgx-export is not in that install and has no download/);
    expect(card).toHaveTextContent(/today a KGX file comes from the operator/);
    expect(within(card as HTMLElement).queryByTestId("integration-copy-kgx")).toBeNull();
  });

  it("promises no schedule for the MCP follow-up offers, and claims no parity", () => {
    // F-8.10-J13, then card 62 (F-8.10-V06, PR-8.10-15): "coming to MCP
    // next" was a schedule promise no plan keeps. The card now says only
    // what is true today. Mutation that turns this red: put back "coming to
    // MCP next", or "the same parity the web app has".
    render(<IntegrationsScreen />);

    const card = cards().getByRole("heading", { name: "MCP server" }).parentElement;
    expect(card).not.toHaveTextContent(/same parity/i);
    expect(card).not.toHaveTextContent(/coming/i);
    expect(card).toHaveTextContent(/follow-up offers the web app shows after an answer are not/);
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

    it("writes the REST curl, the MCP config and the s3 commands", async () => {
      const user = setupWithClipboard();
      render(<IntegrationsScreen />);

      for (const [testId, expected] of [
        ["integration-copy-rest", "/v1/query"],
        ["integration-copy-mcp", "/mcp"],
        ["integration-copy-cli", "s3 ask"],
      ] as const) {
        writeText.mockClear();
        await user.click(cards().getByTestId(testId));
        expect(writeText, `${testId} copied nothing`).toHaveBeenCalledTimes(1);
        expect(writeText.mock.calls[0][0]).toContain(expected);
      }
    });

    it("points s3 login at the page's own API origin, the same one the REST example uses", async () => {
      // F-8.10-J06: `s3` defaults to production, so a tester following
      // develop's page signed in to production. Mutation that turns this
      // red: drop `--base-url` from the printed `s3 login`. And F-8.10-J10:
      // no terminal line starts `s3 mcp`, which only waits for input there.
      const user = setupWithClipboard();
      render(<IntegrationsScreen />);

      await user.click(cards().getByTestId("integration-copy-rest"));
      const origin = /curl -X POST (\S+)\/v1\/query/.exec(writeText.mock.calls[0][0])?.[1];
      expect(origin, "populate check: the REST example names an origin").toBeTruthy();

      writeText.mockClear();
      await user.click(cards().getByTestId("integration-copy-cli"));
      const cli = writeText.mock.calls[0][0];
      expect(cli).toContain(`s3 login --base-url ${origin} you@example.org`);
      expect(cli.split("\n").map((line) => line.trim())).not.toContain("s3 mcp");

      writeText.mockClear();
      await user.click(cards().getByTestId("integration-copy-mcp-stdio"));
      expect(JSON.parse(writeText.mock.calls[0][0])).toEqual(AGENT_CONFIG);
    });

    it("installs s3 with python3.11 into a new virtual environment, and installs nothing else", async () => {
      // Card 62, PR-8.10-03 and 04, and its fix round (F-62-J01, J02, A07).
      // The install copy makes the venv with `python3.11` by name, since a
      // bare `python3` is macOS's own 3.9, then activates it before pip
      // runs, so Homebrew's Python does not refuse and `s3` is on the PATH
      // for the next command. No other copy on the page installs anything.
      const user = setupWithClipboard();
      render(<IntegrationsScreen />);

      await user.click(cards().getByTestId("integration-copy-install"));
      const install = writeText.mock.calls[0][0].split("\n");
      expect(install[0]).toBe("python3.11 -m venv s3-env");
      expect(install[1]).toBe(". s3-env/bin/activate");
      expect(install[2]).toMatch(/^pip install "git\+https:\/\/\S+#subdirectory=clients\/system3-cli"$/);

      for (const testId of ["integration-copy-cli", "integration-copy-mcp-stdio"]) {
        writeText.mockClear();
        await user.click(cards().getByTestId(testId));
        expect(writeText.mock.calls[0][0], `${testId} installs something`).not.toMatch(/pip install/);
      }
    });

    it("says so when the clipboard is unavailable, rather than looking like nothing happened", async () => {
      const user = setupWithClipboard(undefined);
      render(<IntegrationsScreen />);

      await user.click(cards().getByTestId("integration-copy-install"));

      // Card 79: the message points at the command the card shows, and that
      // command is on the page. Mutation that turns this red: say "the
      // example" again, or show no install command.
      expect(await screen.findByRole("status")).toHaveTextContent(
        "Select the command shown above and copy it by hand.",
      );
      const card = cards().getByRole("heading", { name: "Command line tools" }).parentElement;
      const shown = within(card as HTMLElement).getByRole("region", { name: /Install command for s3/i });
      expect(shown.textContent).toContain("pip install");
    });

    it("does not point at a command a card does not show", async () => {
      const user = setupWithClipboard(undefined);
      render(<IntegrationsScreen />);

      await user.click(cards().getByTestId("integration-copy-rest"));

      const status = await screen.findByRole("status");
      expect(status).toHaveTextContent(/Could not copy automatically/);
      expect(status).not.toHaveTextContent(/shown above|by hand/);
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
