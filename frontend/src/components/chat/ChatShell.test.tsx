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
});
