import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../lib/api";
import { AuthGate } from "./AuthGate";

// `lib/api.ts`'s `login`/`signup` are mocked at the module level, the same
// convention `StopButton.test.tsx` established for `stopRun`, so this
// suite controls exactly what the backend "returns" without a real
// network call. `vi.importActual` keeps `ApiError` real, since this file
// needs the real class to construct a realistic rejection.
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    login: vi.fn(),
    signup: vi.fn(),
  };
});

import { login, signup } from "../../lib/api";

const loginMock = vi.mocked(login);
const signupMock = vi.mocked(signup);

describe("AuthGate", () => {
  beforeEach(() => {
    loginMock.mockReset();
    signupMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("disables both buttons until an email and a password are entered", () => {
    render(<AuthGate onAuthenticated={vi.fn()} />);

    expect(screen.getByRole("button", { name: /^log in$/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^sign up$/i })).toBeDisabled();
  });

  it("logs in and calls onAuthenticated with the access token on success", async () => {
    loginMock.mockResolvedValue({
      access_token: "test-token",
      refresh_token: "test-refresh",
      token_type: "bearer",
    });
    const user = userEvent.setup();
    const onAuthenticated = vi.fn();

    render(<AuthGate onAuthenticated={onAuthenticated} />);
    await user.type(screen.getByLabelText(/email/i), "person@example.com");
    await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
    await user.click(screen.getByRole("button", { name: /^log in$/i }));

    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith("test-token"));
    expect(loginMock).toHaveBeenCalledWith({
      email: "person@example.com",
      password: "correct horse battery staple",
    });
    expect(signupMock).not.toHaveBeenCalled();
  });

  it("signs up, then logs in with the same credentials, and calls onAuthenticated with the access token", async () => {
    signupMock.mockResolvedValue({ id: "user-1", email: "person@example.com" });
    loginMock.mockResolvedValue({
      access_token: "test-token",
      refresh_token: "test-refresh",
      token_type: "bearer",
    });
    const user = userEvent.setup();
    const onAuthenticated = vi.fn();

    render(<AuthGate onAuthenticated={onAuthenticated} />);
    await user.type(screen.getByLabelText(/email/i), "person@example.com");
    await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
    await user.click(screen.getByRole("button", { name: /^sign up$/i }));

    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith("test-token"));
    expect(signupMock).toHaveBeenCalledWith({
      email: "person@example.com",
      password: "correct horse battery staple",
    });
    expect(loginMock).toHaveBeenCalledWith({
      email: "person@example.com",
      password: "correct horse battery staple",
    });
  });

  it("shows a fixed, generic error on a failed login, without crashing and without ever rendering the raw backend response", async () => {
    loginMock.mockRejectedValue(new ApiError(401, "login failed with 401: invalid email or password"));
    const user = userEvent.setup();
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    render(<AuthGate onAuthenticated={vi.fn()} />);
    await user.type(screen.getByLabelText(/email/i), "person@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrong-password");
    await user.click(screen.getByRole("button", { name: /^log in$/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/could not log in/i);
    // The raw ApiError message ("invalid email or password", the backend's
    // own uniform anti-enumeration string) never reaches the DOM, even
    // though it happens to be safe text today; only the fixed sentence
    // above does.
    expect(alert).not.toHaveTextContent(/invalid email or password/i);
    expect(alert).not.toHaveTextContent("wrong-password");

    // Logged for operator visibility (status only), never with the
    // password or the raw caught error's message.
    expect(warnSpy).toHaveBeenCalledTimes(1);
    const loggedArgs = warnSpy.mock.calls.flat().join(" ");
    expect(loggedArgs).not.toContain("wrong-password");
    expect(loggedArgs).not.toContain("invalid email or password");
    expect(loggedArgs).toContain("401");
  });

  it("shows a fixed, generic error on a failed signup, and never falls through to login", async () => {
    signupMock.mockRejectedValue(new ApiError(409, "signup failed with 409: email already registered"));
    const user = userEvent.setup();
    vi.spyOn(console, "warn").mockImplementation(() => {});

    render(<AuthGate onAuthenticated={vi.fn()} />);
    await user.type(screen.getByLabelText(/email/i), "person@example.com");
    await user.type(screen.getByLabelText(/password/i), "some-password");
    await user.click(screen.getByRole("button", { name: /^sign up$/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/could not create that account/i);
    expect(alert).not.toHaveTextContent(/email already registered/i);
    expect(loginMock).not.toHaveBeenCalled();
  });

  it("disables both buttons while a request is in flight, and calls onAuthenticated once it resolves", async () => {
    let resolveLogin: (() => void) | undefined;
    loginMock.mockReturnValue(
      new Promise((resolve) => {
        resolveLogin = () =>
          resolve({ access_token: "test-token", refresh_token: "test-refresh", token_type: "bearer" });
      }),
    );
    const user = userEvent.setup();
    const onAuthenticated = vi.fn();

    render(<AuthGate onAuthenticated={onAuthenticated} />);
    await user.type(screen.getByLabelText(/email/i), "person@example.com");
    await user.type(screen.getByLabelText(/password/i), "correct horse battery staple");
    await user.click(screen.getByRole("button", { name: /^log in$/i }));

    const pendingButtons = screen.getAllByRole("button", { name: /working/i });
    expect(pendingButtons).toHaveLength(2);
    pendingButtons.forEach((button) => expect(button).toBeDisabled());
    expect(onAuthenticated).not.toHaveBeenCalled();

    // On success this component intentionally never resets `pending`
    // itself (see the component's own docstring): the parent stops
    // rendering `AuthGate` once it holds a token, so there is nothing left
    // to reset. The observable contract from here is that
    // `onAuthenticated` fires with the token, not that the buttons
    // re-enable in place.
    resolveLogin?.();
    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith("test-token"));
  });
});
