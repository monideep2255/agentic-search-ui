import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { HomePage } from "./HomePage";

describe("HomePage", () => {
  it("renders EmptyState and QueryInput", () => {
    render(<HomePage onSubmitQuery={vi.fn()} />);

    expect(
      screen.getByRole("heading", {
        name: /ask the agent a biomedical question/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/ask a question/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /search/i })).toBeInTheDocument();
  });

  it("calls onSubmitQuery with the trimmed query text on submit", async () => {
    const user = userEvent.setup();
    const onSubmitQuery = vi.fn();
    render(<HomePage onSubmitQuery={onSubmitQuery} />);

    await user.type(screen.getByLabelText(/ask a question/i), "test query{Enter}");

    expect(onSubmitQuery).toHaveBeenCalledWith("test query");
  });

  it("does not call onSubmitQuery for an empty query", async () => {
    const user = userEvent.setup();
    const onSubmitQuery = vi.fn();
    render(<HomePage onSubmitQuery={onSubmitQuery} />);

    await user.click(screen.getByRole("button", { name: /search/i }));

    expect(onSubmitQuery).not.toHaveBeenCalled();
  });
});
