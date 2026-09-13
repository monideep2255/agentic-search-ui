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

const TOKENS = { access_token: "test-token", refresh_token: "test-refresh", token_type: "bearer" };
const EMAIL_TAKEN = new ApiError(409, "signup failed with 409: email already registered");

async function fillAndSubmit(email: string, password: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/email/i), email);
  await user.type(screen.getByLabelText(/password/i), password);
  await user.click(screen.getByRole("button", { name: /^log in$/i }));
}

// Set 1, R5 and X3 (2026-09-12): one Log in button. It tries signup first,
// so a new email creates the account and a registered email logs in.
describe("AuthGate", () => {
  beforeEach(() => {
    loginMock.mockReset();
    signupMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("offers one Log in button and no Sign up button, disabled until both fields are filled", () => {
    render(<AuthGate onAuthenticated={vi.fn()} />);

    expect(screen.getByRole("button", { name: /^log in$/i })).toBeDisabled();
    expect(screen.queryByRole("button", { name: /sign up/i })).toBeNull();
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("creates the account for a new email, then logs in without resending the guest token", async () => {
    signupMock.mockResolvedValue({ id: "user-1", email: "new@example.com" });
    loginMock.mockResolvedValue(TOKENS);
    const onAuthenticated = vi.fn();

    render(<AuthGate onAuthenticated={onAuthenticated} guestToken="guest-abc" />);
    await fillAndSubmit("new@example.com", "correct horse battery staple");

    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith("test-token", "new@example.com"));
    expect(signupMock).toHaveBeenCalledWith({
      email: "new@example.com",
      password: "correct horse battery staple",
      guest_token: "guest-abc",
    });
    // Signup already migrated the guest session, so login carries none.
    expect(loginMock).toHaveBeenCalledWith({
      email: "new@example.com",
      password: "correct horse battery staple",
    });
  });

  it("logs a registered email in when signup answers 409, carrying the guest token on login", async () => {
    signupMock.mockRejectedValue(EMAIL_TAKEN);
    loginMock.mockResolvedValue(TOKENS);
    const onAuthenticated = vi.fn();

    render(<AuthGate onAuthenticated={onAuthenticated} guestToken="guest-abc" />);
    await fillAndSubmit("person@example.com", "correct horse battery staple");

    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith("test-token", "person@example.com"));
    expect(loginMock).toHaveBeenCalledWith({
      email: "person@example.com",
      password: "correct horse battery staple",
      guest_token: "guest-abc",
    });
  });

  it("omits guest_token from both calls for a visitor who never held a guest session", async () => {
    signupMock.mockRejectedValue(EMAIL_TAKEN);
    loginMock.mockResolvedValue(TOKENS);

    render(<AuthGate onAuthenticated={vi.fn()} />);
    await fillAndSubmit("person@example.com", "pw");

    await waitFor(() => expect(loginMock).toHaveBeenCalled());
    expect(signupMock).toHaveBeenCalledWith({ email: "person@example.com", password: "pw" });
    expect(loginMock).toHaveBeenCalledWith({ email: "person@example.com", password: "pw" });
  });

  it("says the password does not match on a 401, and never renders or logs the raw backend response", async () => {
    signupMock.mockRejectedValue(EMAIL_TAKEN);
    loginMock.mockRejectedValue(new ApiError(401, "login failed with 401: invalid email or password"));
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const onAuthenticated = vi.fn();

    render(<AuthGate onAuthenticated={onAuthenticated} />);
    await fillAndSubmit("person@example.com", "wrong-password");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/password does not match this email/i);
    expect(alert).not.toHaveTextContent(/invalid email or password/i);
    expect(alert).not.toHaveTextContent("wrong-password");
    expect(onAuthenticated).not.toHaveBeenCalled();

    // Logged for operator visibility (status only), never with the
    // password or the raw caught error's message.
    expect(warnSpy).toHaveBeenCalledTimes(1);
    const loggedArgs = warnSpy.mock.calls.flat().join(" ");
    expect(loggedArgs).not.toContain("wrong-password");
    expect(loggedArgs).not.toContain("invalid email or password");
    expect(loggedArgs).toContain("401");
  });

  it("asks for a valid email on a 422, and does not try to log in", async () => {
    signupMock.mockRejectedValue(new ApiError(422, "signup failed with 422"));
    vi.spyOn(console, "warn").mockImplementation(() => {});

    render(<AuthGate onAuthenticated={vi.fn()} />);
    await fillAndSubmit("not-an-email", "pw");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/enter a valid email address/i);
    expect(loginMock).not.toHaveBeenCalled();
  });

  it("shows a connection message for any other failure", async () => {
    signupMock.mockRejectedValue(new ApiError(500, "signup failed with 500"));
    vi.spyOn(console, "warn").mockImplementation(() => {});

    render(<AuthGate onAuthenticated={vi.fn()} />);
    await fillAndSubmit("person@example.com", "pw");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/could not log in right now/i);
    expect(loginMock).not.toHaveBeenCalled();
  });

  it("disables the button while a request is in flight, and calls onAuthenticated once it resolves", async () => {
    signupMock.mockRejectedValue(EMAIL_TAKEN);
    let resolveLogin: (() => void) | undefined;
    loginMock.mockReturnValue(
      new Promise((resolve) => {
        resolveLogin = () => resolve(TOKENS);
      }),
    );
    const onAuthenticated = vi.fn();

    render(<AuthGate onAuthenticated={onAuthenticated} />);
    await fillAndSubmit("person@example.com", "correct horse battery staple");

    const pending = await screen.findByRole("button", { name: /working/i });
    expect(pending).toBeDisabled();
    expect(onAuthenticated).not.toHaveBeenCalled();

    // On success this component intentionally never resets `pending`: the
    // parent stops rendering `AuthGate` once it holds a token.
    resolveLogin?.();
    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith("test-token", "person@example.com"));
  });
});
