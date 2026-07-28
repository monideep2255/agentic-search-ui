import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ChatPage } from "./ChatPage";

describe("ChatPage", () => {
  it("renders inside ChatShell with the initial query and a placeholder", () => {
    render(<ChatPage initialQuery="What is rs334?" onExit={vi.fn()} />);

    expect(screen.getByText("What is rs334?")).toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("calls onExit when the back-to-search button is clicked", async () => {
    const user = userEvent.setup();
    const onExit = vi.fn();
    render(<ChatPage initialQuery="test" onExit={onExit} />);

    await user.click(screen.getByRole("button", { name: /back to search/i }));

    expect(onExit).toHaveBeenCalledTimes(1);
  });
});
