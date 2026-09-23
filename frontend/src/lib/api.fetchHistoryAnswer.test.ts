/**
 * Item 10.2, overnight run 2026-09-22/23: `fetchHistoryAnswer`,
 * `GET /v1/history/{trace_id}/answer`.
 *
 * Same tool as `api.fetchHistory.test.ts` for the same reason: this module
 * calls the global `fetch` directly, so these tests stub it to control the
 * exact status and body worker B1's endpoint may return.
 *
 * The pinned wire contract makes a 403 (someone else's row), a 404 (no such
 * row) and a 404 (no saved answer on an otherwise real row) INDISTINGUISHABLE
 * on purpose, and this file's job is only to prove the client does not try
 * to tell them apart: every non-2xx status throws, and every caller of this
 * function (see `App.savedAnswer.test.tsx`) treats every throw the same way.
 *
 * Every test states, in a comment, the mutation it is proven to catch.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, fetchHistoryAnswer } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

const VALID_BODY = {
  trace_id: "t-1",
  question: "What is BRCA1?",
  asked_at: "2026-09-20T10:00:00Z",
  depth: "plain_language",
  answer_markdown: "BRCA1 is a gene.",
  citations: [
    { display_index: 1, source: "Gene", source_url: "https://www.ncbi.nlm.nih.gov/gene/672", layer: 1 },
  ],
  trust_signal: "Grounded, every claim cited",
};

describe("fetchHistoryAnswer", () => {
  it("GETs the trace-scoped answer path with a bearer token", async () => {
    // Mutation: building the URL wrong (missing trace_id, wrong segment
    // order), sending the wrong HTTP method, or omitting the Authorization
    // header turns this red.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(VALID_BODY), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchHistoryAnswer("token-1", "t-1", { baseUrl: "https://api.test" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.test/v1/history/t-1/answer");
    expect(init.method).toBe("GET");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer token-1");
    expect(result.answer_markdown).toBe("BRCA1 is a gene.");
    expect(result.citations).toHaveLength(1);
    expect(result.trust_signal).toBe("Grounded, every claim cited");
  });

  it("URL-encodes a trace_id that carries characters needing it", async () => {
    // Mutation: interpolating trace_id into the URL unencoded turns this
    // red the moment a trace_id carries a character `encodeURIComponent`
    // would change.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ...VALID_BODY, trace_id: "t/1" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchHistoryAnswer("token-1", "t/1", { baseUrl: "https://api.test" });

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.test/v1/history/t%2F1/answer");
  });

  it("throws ApiError on a 404, the same as any other non-2xx status", async () => {
    // Mutation: swallowing a 404 and returning something null-ish instead
    // of throwing turns this red. The contract makes "not yours", "does
    // not exist" and "no saved answer" indistinguishable by design, and
    // this function must not try to guess which one happened.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "not found" }), { status: 404 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchHistoryAnswer("token-1", "t-1", { baseUrl: "https://api.test" })).rejects.toBeInstanceOf(
      ApiError,
    );
  });

  it("drops a malformed citation rather than failing the whole fetch", async () => {
    // Mutation: including an unvalidated citation array in the result, or
    // dropping every citation including the well-formed one, both turn
    // this red.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          ...VALID_BODY,
          citations: [
            { display_index: 1, source: "Gene", source_url: "https://www.ncbi.nlm.nih.gov/gene/672", layer: 1 },
            { display_index: 2, source: "Bad", layer: 1 },
          ],
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchHistoryAnswer("token-1", "t-1", { baseUrl: "https://api.test" });
    expect(result.citations).toHaveLength(1);
    expect(result.citations[0].display_index).toBe(1);
  });

  it("carries trust_line through when the response body has one", async () => {
    // Mutation: dropping `trust_line` on the way through, or always
    // reading `trust_signal` in its place, turns this red. Defect two,
    // `testing/Developer/reports/2026-09-23_overnight/findings.md`'s
    // "Worker B1" entry.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ ...VALID_BODY, trust_line: "Sources disagree on at least one claim." }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchHistoryAnswer("token-1", "t-1", { baseUrl: "https://api.test" });
    expect(result.trust_line).toBe("Sources disagree on at least one claim.");
  });

  it("reads trust_line as null, never a fabricated string, when the body carries none", async () => {
    // Mutation: defaulting an absent `trust_line` to `""` or to
    // `trust_signal`'s value at this layer (rather than at the render
    // layer, where the fallback belongs) turns this red.
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(VALID_BODY), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchHistoryAnswer("token-1", "t-1", { baseUrl: "https://api.test" });
    expect(result.trust_line).toBeNull();
  });

  it("throws a plain Error when the 200 body is not the documented shape", async () => {
    // Mutation: casting the body straight to the response type without
    // checking `answer_markdown`/`citations` turns this red on a
    // malformed 200, since it would otherwise hand a component a value
    // typed as safe that is not.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ trace_id: "t-1" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      fetchHistoryAnswer("token-1", "t-1", { baseUrl: "https://api.test" }),
    ).rejects.toThrow(/documented saved-answer shape/);
  });
});
