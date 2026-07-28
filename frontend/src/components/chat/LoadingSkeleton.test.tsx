import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LoadingSkeleton } from "./LoadingSkeleton";

describe("LoadingSkeleton", () => {
  it("renders a non-blank connecting status for cold_start", () => {
    const { container } = render(<LoadingSkeleton state="cold_start" />);

    const status = screen.getByRole("status", { name: /connecting/i });
    expect(status).toBeInTheDocument();
    expect(container.textContent?.trim().length).toBeGreaterThan(0);
  });

  it("renders a non-blank checking status for guard_pending", () => {
    const { container } = render(<LoadingSkeleton state="guard_pending" />);

    const status = screen.getByRole("status", { name: /checking your question/i });
    expect(status).toBeInTheDocument();
    expect(container.textContent?.trim().length).toBeGreaterThan(0);
  });

  it("never renders a blank pane for either known state", () => {
    for (const state of ["cold_start", "guard_pending"] as const) {
      const { container, unmount } = render(<LoadingSkeleton state={state} />);
      expect(container.firstChild).not.toBeNull();
      expect(container.textContent?.trim().length ?? 0).toBeGreaterThan(0);
      unmount();
    }
  });
});
