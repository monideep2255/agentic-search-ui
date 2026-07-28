import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("renders a heading and at least one example question", () => {
    render(<EmptyState />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /ask the agent a biomedical question/i,
      }),
    ).toBeInTheDocument();

    const items = screen.getAllByRole("listitem");
    expect(items.length).toBeGreaterThan(0);
  });
});
