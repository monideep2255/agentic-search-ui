/**
 * Premise gate for the landing screen's alignment to the approved prototype.
 *
 * Written BEFORE the fix and watched failing, per
 * `docs/build/Build_workflow_cadence.md` stage 5.
 *
 * THE PREMISE, from the product owner's 2026-08-14 direction that the
 * prototype is the baseline:
 *
 *   The landing screen presents its controls in the prototype's own order and
 *   with the prototype's own labels: the search bar first, its submit action
 *   reading "Search", and the answer-depth control BELOW it.
 *
 * Source of truth: `prototype/app.html`'s `#s-landing`, which orders
 * `h1` then `.sub` then `form.searchbar` then `.depthwrap` then `.seeds`.
 *
 * COVERAGE STATEMENT, per `goal-contracts`:
 *
 *   Exercised:      the submit action's visible label, and the ORDER of the
 *                   search form against the depth control, compared with
 *                   `compareDocumentPosition` rather than asserted as mere
 *                   presence, since both controls were already on the screen
 *                   and only their order was wrong.
 *
 *   NOT exercised:  visual position. As with the rail's gate, DOM order is not
 *                   layout, and no jsdom assertion can tell them apart. The
 *                   landing's geometry is covered by
 *                   `e2e/rail-collapse.spec.ts`'s full-height clause and by the
 *                   accessibility suite's viewport check.
 *
 *                   That no two visible controls share an accessible name.
 *                   That is the accessibility suite's, and it is the check that
 *                   makes the aria-label below load-bearing rather than
 *                   decorative.
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

const mainArea = () => within(screen.getByRole("main"));

describe("the landing screen matches the prototype's arrangement", () => {
  it("submits with an icon-only button whose accessible name still says Search", () => {
    render(<App />);

    /*
     * The prototype's `button.go` reads "Search" plus a right arrow, and the
     * shipped button matched it until 2026-09-13, when the product owner
     * replaced the text with an up-arrow icon (testing/UI_fix_plan.md item
     * 2.12). The visible text is gone; the accessible name is what every
     * browser spec and screen reader uses, so that is what this pins.
     */
    const submit = mainArea().getByRole("button", { name: /^search\b/i });
    expect(submit).toHaveTextContent(/^$/);
    expect(submit.querySelector("svg")).not.toBeNull();
    expect(submit.getAttribute("type")).toBe("submit");
  });

  it("keeps the submit action's accessible name distinct from the nav's Search", () => {
    render(<App />);

    const navSearch = within(
      screen.getByRole("navigation", { name: /main/i }),
    ).getByRole("button", { name: "Search" });
    const submit = mainArea().getByRole("button", { name: /^search\b/i });

    // Both exist, and they are NOT the same accessible name. Asserted as an
    // inequality rather than against a literal, so renaming either one keeps
    // the guarantee.
    expect(navSearch).toBeInTheDocument();
    expect(submit.getAttribute("aria-label")).not.toBe("Search");
    // WCAG 2.5.3, Label in Name: the accessible name must CONTAIN the visible
    // text, or a speech-input user saying "Search" cannot operate it.
    expect(submit.getAttribute("aria-label")).toMatch(/search/i);
  });

  it("puts the answer-depth control below the search bar", () => {
    render(<App />);

    const submit = mainArea().getByRole("button", { name: /^search\b/i });
    const depth = mainArea().getByRole("group", { name: /depth/i });

    // The prototype orders `form.searchbar` then `.depthwrap`. The shipped
    // landing had them the other way round. Both were already present, so a
    // presence-only assertion could not have caught this.
    expect(
      depth.compareDocumentPosition(submit) & Node.DOCUMENT_POSITION_PRECEDING,
    ).toBeTruthy();
  });
});
