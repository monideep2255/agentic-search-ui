import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { QueryInput } from "./QueryInput";

describe("QueryInput", () => {
  it("has an explicit <label>, not just a placeholder-only affordance", () => {
    render(<QueryInput onSubmit={vi.fn()} />);

    // getByLabelText only finds the input via a real <label>/htmlFor
    // association; a placeholder-only affordance would fail this query.
    const input = screen.getByLabelText(/ask a question/i);
    expect(input.tagName).toBe("INPUT");
    expect(input).toHaveAttribute("placeholder");

    const label = screen.getByText("Ask a question");
    expect(label.tagName).toBe("LABEL");
  });

  it("is keyboard-operable: Tab focuses it, typing then Enter submits", async () => {
    const user = userEvent.setup();
    const handleSubmit = vi.fn();
    render(<QueryInput onSubmit={handleSubmit} />);

    await user.tab();
    const input = screen.getByLabelText(/ask a question/i);
    expect(input).toHaveFocus();

    await user.keyboard("What is the clinical significance of rs334?{Enter}");

    expect(handleSubmit).toHaveBeenCalledTimes(1);
    expect(handleSubmit).toHaveBeenCalledWith(
      "What is the clinical significance of rs334?",
    );
  });

  it("trims surrounding whitespace before submitting", async () => {
    const user = userEvent.setup();
    const handleSubmit = vi.fn();
    render(<QueryInput onSubmit={handleSubmit} />);

    const input = screen.getByLabelText(/ask a question/i);
    await user.type(input, "  spaced query  {Enter}");

    expect(handleSubmit).toHaveBeenCalledWith("spaced query");
  });

  it("does not submit on Enter when the input is empty", async () => {
    const user = userEvent.setup();
    const handleSubmit = vi.fn();
    render(<QueryInput onSubmit={handleSubmit} />);

    screen.getByLabelText(/ask a question/i).focus();
    await user.keyboard("{Enter}");

    expect(handleSubmit).not.toHaveBeenCalled();
  });

  it("submits on button click", async () => {
    const user = userEvent.setup();
    const handleSubmit = vi.fn();
    render(<QueryInput onSubmit={handleSubmit} />);

    await user.type(screen.getByLabelText(/ask a question/i), "test query");
    await user.click(screen.getByRole("button", { name: /search/i }));

    expect(handleSubmit).toHaveBeenCalledWith("test query");
  });
});
