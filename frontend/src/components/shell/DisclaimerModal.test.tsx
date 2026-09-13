/**
 * Fix set 5, item 5.5 (R19, R42; decision U4).
 *
 * Pins the reference-sized disclaimer the product owner asked for on
 * 2026-09-12, in place of the design system's 520px card. See this
 * component's own docstring for the layout source and the amended token
 * rule.
 *
 * What this file exercises:
 *
 *   - The dialog is labelled "Important medical disclaimer".
 *   - The physician-referral sentence is present.
 *   - A titled "Prototype" notice is present.
 *   - The continue button stays disabled until the checkbox is ticked, then
 *     enables.
 *   - Escape does not call `onAccept` (F-4.8-A-08's keyboard trap).
 *   - Clicking the enabled button calls `onAccept` exactly once.
 *
 * What this file does not exercise: the focus trap's Tab cycling and the
 * `inert` background, which are `frontend/e2e/accessibility.spec.ts`'s job
 * against a real browser rather than jsdom's own focus model.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DisclaimerModal } from "./DisclaimerModal";

describe("DisclaimerModal", () => {
  it("labels the dialog with the reference-sized title", () => {
    render(<DisclaimerModal onAccept={vi.fn()} />);
    expect(
      screen.getByRole("dialog", { name: /important medical disclaimer/i }),
    ).toBeInTheDocument();
  });

  it("includes the physician-referral sentence", () => {
    render(<DisclaimerModal onAccept={vi.fn()} />);
    expect(
      screen.getByText(
        /always seek the advice of your physician or another qualified health professional/i,
      ),
    ).toBeInTheDocument();
  });

  it("includes a titled Prototype notice", () => {
    render(<DisclaimerModal onAccept={vi.fn()} />);
    expect(screen.getByText("Prototype")).toBeInTheDocument();
    expect(screen.getByText(/prototype under active development/i)).toBeInTheDocument();
  });

  it("disables the continue button until the checkbox is ticked", async () => {
    const user = userEvent.setup();
    render(<DisclaimerModal onAccept={vi.fn()} />);
    const button = screen.getByRole("button", { name: /continue/i });
    expect(button).toBeDisabled();

    await user.click(screen.getByRole("checkbox"));
    expect(button).toBeEnabled();
  });

  it("does not call onAccept on Escape", async () => {
    const user = userEvent.setup();
    const onAccept = vi.fn();
    render(<DisclaimerModal onAccept={onAccept} />);

    await user.keyboard("{Escape}");
    expect(onAccept).not.toHaveBeenCalled();
  });

  it("calls onAccept exactly once when the enabled button is clicked", async () => {
    const user = userEvent.setup();
    const onAccept = vi.fn();
    render(<DisclaimerModal onAccept={onAccept} />);

    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onAccept).toHaveBeenCalledTimes(1);
  });
});
