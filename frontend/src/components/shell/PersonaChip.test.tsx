/**
 * The persona chip's info affordance (2026-09-13 product-owner request):
 * visitors do not know who "Mendel" or "Franklin" is, so an info button
 * after the name opens a short dialog naming the persona's achievements
 * with a link out to Wikipedia.
 *
 * Pins:
 *   - No info button when `about` is null, the graceful-degradation path
 *     for an older backend or an existing test mock returning
 *     `{persona_name}` alone.
 *   - The info button opens a dialog containing the about text.
 *   - The Wikipedia link's href, rel and target.
 *   - A non-Wikipedia URL renders no link at all (the host-pinned check).
 *   - Escape closes the dialog.
 *   - The chip still renders nothing when `name` is null.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PersonaCaption, isPinnedWikipediaUrl, PersonaChip } from "./PersonaChip";

describe("isPinnedWikipediaUrl", () => {
  it("accepts an https en.wikipedia.org URL", () => {
    expect(isPinnedWikipediaUrl("https://en.wikipedia.org/wiki/Gregor_Mendel")).toBe(true);
  });

  it("rejects a non-wikipedia host", () => {
    expect(isPinnedWikipediaUrl("https://evil.example/wiki/Gregor_Mendel")).toBe(false);
  });

  it("rejects a host that merely contains en.wikipedia.org", () => {
    expect(isPinnedWikipediaUrl("https://en.wikipedia.org.evil.example/wiki/X")).toBe(false);
  });

  it("rejects http (not https)", () => {
    expect(isPinnedWikipediaUrl("http://en.wikipedia.org/wiki/Gregor_Mendel")).toBe(false);
  });

  it("rejects a malformed URL without throwing", () => {
    expect(isPinnedWikipediaUrl("not a url")).toBe(false);
  });
});

describe("PersonaChip", () => {
  it("renders nothing when name is null", () => {
    render(<PersonaChip name={null} about="Some achievement." wikipedia={null} />);
    expect(screen.queryByTestId("persona-chip")).toBeNull();
  });

  it("renders the chip with no info button when about is null", () => {
    render(<PersonaChip name="Mendel" about={null} wikipedia={null} />);
    expect(screen.getByTestId("persona-chip")).toHaveTextContent("Mendel");
    expect(screen.queryByRole("button", { name: /about mendel/i })).toBeNull();
  });

  it("opens a dialog containing the about text when the info button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <PersonaChip
        name="Mendel"
        about="Pea plant experiments in a monastery garden established the laws of inheritance."
        wikipedia={null}
      />,
    );

    const infoButton = screen.getByRole("button", { name: /about mendel/i });
    expect(infoButton).toHaveAttribute("aria-haspopup", "dialog");
    expect(infoButton).toHaveAttribute("aria-expanded", "false");

    await user.click(infoButton);

    expect(infoButton).toHaveAttribute("aria-expanded", "true");
    const dialog = screen.getByRole("dialog");
    expect(
      within(dialog).getByText(/pea plant experiments in a monastery garden/i),
    ).toBeInTheDocument();
  });

  it("opens the dialog with the keyboard (Enter on the info button)", async () => {
    const user = userEvent.setup();
    render(<PersonaChip name="Mendel" about="Founded the laws of inheritance." wikipedia={null} />);

    const infoButton = screen.getByRole("button", { name: /about mendel/i });
    infoButton.focus();
    await user.keyboard("{Enter}");

    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("renders a Wikipedia link with the right href, rel and target", async () => {
    const user = userEvent.setup();
    render(
      <PersonaChip
        name="Mendel"
        about="Founded the laws of inheritance."
        wikipedia="https://en.wikipedia.org/wiki/Gregor_Mendel"
      />,
    );

    await user.click(screen.getByRole("button", { name: /about mendel/i }));

    const link = screen.getByRole("link", { name: /learn more on wikipedia/i });
    expect(link).toHaveAttribute("href", "https://en.wikipedia.org/wiki/Gregor_Mendel");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders no link at all when the URL fails the host pin", async () => {
    const user = userEvent.setup();
    render(
      <PersonaChip
        name="Mendel"
        about="Founded the laws of inheritance."
        wikipedia="https://evil.example/wiki/Gregor_Mendel"
      />,
    );

    await user.click(screen.getByRole("button", { name: /about mendel/i }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /learn more on wikipedia/i })).toBeNull();
  });

  it("closes the dialog on Escape", async () => {
    const user = userEvent.setup();
    render(<PersonaChip name="Mendel" about="Founded the laws of inheritance." wikipedia={null} />);

    await user.click(screen.getByRole("button", { name: /about mendel/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("PersonaCaption on the run screen", () => {
  // Product-owner request 2026-09-13: the "i" must also be there where the
  // scientist's name appears during the answer, not only in the app bar.
  it("offers the same info card beside the name in the per-step caption", async () => {
    const user = userEvent.setup();
    render(
      <PersonaCaption
        name="Mendel"
        step="Guard"
        about="Pea plant experiments established the laws of inheritance."
        wikipedia="https://en.wikipedia.org/wiki/Gregor_Mendel"
      />,
    );
    await user.click(screen.getByRole("button", { name: "About Mendel" }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Pea plant experiments established the laws of inheritance.");
    expect(screen.getByRole("link", { name: /wikipedia/i })).toHaveAttribute(
      "href",
      "https://en.wikipedia.org/wiki/Gregor_Mendel",
    );
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders no info button in the caption when there is no about line", () => {
    render(<PersonaCaption name="Mendel" step="Guard" />);
    expect(screen.queryByRole("button", { name: "About Mendel" })).toBeNull();
    expect(screen.getByTestId("persona-caption")).toHaveTextContent("Mendel");
  });
});
