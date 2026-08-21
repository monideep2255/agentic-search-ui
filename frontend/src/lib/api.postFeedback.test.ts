/**
 * T-4.6-09: `postFeedback`, `POST /v1/query/{run_id}/feedback`.
 *
 * `fetch` is stubbed globally (`vi.stubGlobal`, the same tool
 * `useAgentRun.test.ts` uses for the same reason: this module calls the
 * global `fetch` directly, and these tests need precise control over the
 * response status, headers and body). A separate file from
 * `api.ts`'s other functions since no `api.test.ts` exists yet for them and
 * this ticket's scope is `postFeedback` alone.
 *
 * Every test states, in a comment, the mutation it is proven to catch.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, FeedbackNotYetCapturedError, postFeedback } from "./api";
import type { FeedbackRequestBody } from "./api";

const BODY: FeedbackRequestBody = {
  rating: "down",
  comment: "cited the wrong gene",
  flagged_reason: "Wrong answer",
  citation_flags: [{ citation_id: "1", reason: "Citation does not support the claim" }],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("postFeedback", () => {
  it("POSTs to the run-scoped path with a bearer token and the JSON body, and resolves on 204", async () => {
    // Mutation: building the URL without `encodeURIComponent`, sending the
    // wrong HTTP method, omitting the Authorization header, or forwarding a
    // different body than the caller's own each turn this red.
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      postFeedback("run 42", BODY, "token-1", { baseUrl: "https://api.test" }),
    ).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.test/v1/query/run%2042/feedback");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer token-1");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual(BODY);
  });

  it("throws FeedbackNotYetCapturedError on 409, reading Retry-After", async () => {
    // Mutation: falling through to `throwIfNotOk` for a 409 (the ordinary
    // path every other status takes) turns this red, since the thrown error
    // would be a plain ApiError, not FeedbackNotYetCapturedError, and would
    // carry no `retryAfterS`.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(null, { status: 409, headers: { "Retry-After": "7" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const error = await postFeedback("run-1", BODY, "token-1").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(FeedbackNotYetCapturedError);
    expect((error as FeedbackNotYetCapturedError).retryAfterS).toBe(7);
  });

  it("falls back to a 3 second retry hint when Retry-After is absent or unparseable", async () => {
    // Mutation: dropping the `Number.isFinite(parsed) && parsed > 0` guard
    // (constructing the error from the raw parsed value) turns this red,
    // verified directly: a missing header parses to `NaN`, and without the
    // guard the thrown error carries `retryAfterS: NaN` instead of the
    // documented default of 3.
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 409 }));
    vi.stubGlobal("fetch", fetchMock);

    const error = await postFeedback("run-1", BODY, "token-1").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(FeedbackNotYetCapturedError);
    expect((error as FeedbackNotYetCapturedError).retryAfterS).toBe(3);
  });

  it("throws the ordinary ApiError, with its status, for a 403 ownership refusal", async () => {
    // Mutation: routing 403 through the 409-specific branch (an off-by-one
    // status check) turns this red, since the thrown error would be a
    // FeedbackNotYetCapturedError instead of an ApiError with status 403.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "you do not own this run" }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const error = await postFeedback("run-1", BODY, "token-1").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(403);
  });
});
