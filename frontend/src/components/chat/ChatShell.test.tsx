import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChatShell } from "./ChatShell";

describe("ChatShell", () => {
  it("renders the query and its children", () => {
    render(
      <ChatShell query="What is BRCA1?">
        <p>child content</p>
      </ChatShell>,
    );

    expect(screen.getByText("What is BRCA1?")).toBeInTheDocument();
    expect(screen.getByText("child content")).toBeInTheDocument();
  });

  it("has no run_id yet, since run creation is wired in a later ticket", () => {
    const { container } = render(
      <ChatShell query="test">
        <span>body</span>
      </ChatShell>,
    );

    const shell = container.querySelector(".chat-shell");
    expect(shell).not.toHaveAttribute("data-run-id");
  });
});
