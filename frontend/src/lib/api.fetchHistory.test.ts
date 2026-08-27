/**
 * T-4.13-03: `fetchHistory`, `GET /v1/history`.
 *
 * `fetch` is stubbed globally (`vi.stubGlobal`), the same tool
 * `api.postFeedback.test.ts` uses for the same reason: this module calls
 * the global `fetch` directly, and these tests need precise control over
 * the response status and body.
 *
 * Every test states, in a comment, the mutation it is proven to catch.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, fetchHistory } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchHistory", () => {
  it("GETs the history path with a bearer token, and returns items and count", async () => {
    // Mutation: building the URL wrong, sending the wrong HTTP method, or
    // omitting the Authorization header turns this red.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [{ trace_id: "t-1", question: "What is BRCA1?" }],
          count: 1,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchHistory("token-1", { baseUrl: "https://api.test" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.test/v1/history");
    expect(init.method).toBe("GET");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer token-1");
    expect(result).toEqual({
      items: [{ trace_id: "t-1", question: "What is BRCA1?" }],
      count: 1,
    });
  });

  it("appends limit as an encoded query parameter when given", async () => {
    // Mutation: dropping the `limit` option, or building the query string
    // without it reaching the URL at all, turns this red.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [], count: 0 }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchHistory("token-1", { baseUrl: "https://api.test", limit: 10 });

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.test/v1/history?limit=10");
  });

  it("omits the query string entirely when no limit is given", async () => {
    // Mutation: always appending `?limit=...`, even `undefined`, turns
    // this red with a literal "undefined" in the URL.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [], count: 0 }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchHistory("token-1", { baseUrl: "https://api.test" });

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.test/v1/history");
  });

  it("throws ApiError with its status on 401 (no credential)", async () => {
    // Mutation: swallowing the non-2xx status instead of throwing turns
    // this red.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "not authenticated" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const error = await fetchHistory("bad-token").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(401);
  });

  it("drops an item missing trace_id or question rather than failing the whole fetch", async () => {
    // Mutation: casting the body straight to HistoryResponse without
    // filtering turns this red, since a malformed item would then reach
    // the caller instead of being dropped, per this ticket's instruction
    // to treat every field past `question` and the envelope shape
    // defensively.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [
            { trace_id: "t-1", question: "Good row" },
            { question: "Missing trace_id" },
            { trace_id: "t-3" },
            "not even an object",
          ],
          count: 4,
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchHistory("token-1");

    expect(result.items).toEqual([{ trace_id: "t-1", question: "Good row" }]);
    // `count` is passed through as the server reported it, not recomputed
    // from the filtered list: it is the server's own total, which item
    // filtering here has no authority to second-guess.
    expect(result.count).toBe(4);
  });

  it("throws a plain Error when the body is not the documented {items, count} shape", async () => {
    // Mutation: casting `body as HistoryResponse` instead of validating it
    // turns this red, since a 200 with an unexpected body would then
    // resolve successfully instead of rejecting.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ unexpected: true }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchHistory("token-1")).rejects.toThrow(/not the documented/);
  });
});
