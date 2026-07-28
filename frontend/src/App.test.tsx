import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("App", () => {
  it("renders the home page (EmptyState + QueryInput) on initial render", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", {
        name: /ask the agent a biomedical question/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/ask a question/i)).toBeInTheDocument();
  });

  it("navigates to the chat page when a non-empty query is submitted", async () => {
    const user = userEvent.setup();
    render(<App />);

    const input = screen.getByLabelText(/ask a question/i);
    await user.type(input, "What genes are linked to BRCA1?");
    await user.click(screen.getByRole("button", { name: /search/i }));

    expect(
      screen.getByText("What genes are linked to BRCA1?"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", {
        name: /ask the agent a biomedical question/i,
      }),
    ).not.toBeInTheDocument();
  });

  it("does not navigate when the query is empty", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: /search/i }));

    expect(
      screen.getByRole("heading", {
        name: /ask the agent a biomedical question/i,
      }),
    ).toBeInTheDocument();
  });

  it("returns to the home page when the chat page's exit button is clicked", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.type(
      screen.getByLabelText(/ask a question/i),
      "test query{Enter}",
    );
    await user.click(screen.getByRole("button", { name: /back to search/i }));

    expect(
      screen.getByRole("heading", {
        name: /ask the agent a biomedical question/i,
      }),
    ).toBeInTheDocument();
  });
});
