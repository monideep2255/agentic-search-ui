/**
 * Build phase 8.7 fix round, F-8.7-A14: `createRun` declares that this
 * bundle reads `TokenPayload.placement`.
 *
 * The server sends the record listing ahead of the summary, and puts
 * `placement` on any token, only for a request that asks with
 * `POST /v1/query?reads=placement`. A browser still holding an older bundle
 * does not ask, so it gets the tokens in reading order and never shows the
 * answer upside down. This bundle must ask, or it would lose the early
 * listing it was built to show.
 *
 * Mutation it catches: dropping the query parameter from the URL, or
 * spelling it differently from the server's `_READS_PLACEMENT`.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { createRun, READS_PLACEMENT_QUERY } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("createRun", () => {
  it("asks for placement on POST /v1/query and sends the body unchanged", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ run_id: "run-1", persona_name: "Mendel" }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const body = { text: "What is BRCA1?", session_id: "s-1" };
    await createRun(body, "token-1", { baseUrl: "https://api.test" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(READS_PLACEMENT_QUERY).toBe("reads=placement");
    expect(url).toBe("https://api.test/v1/query?reads=placement");
    expect(init.method).toBe("POST");
    // The declaration rides on the URL, never in the body: the server's
    // request model forbids extra keys, so a body field would make this
    // bundle fail against a server that predates it.
    expect(JSON.parse(init.body as string)).toEqual(body);
  });
});
