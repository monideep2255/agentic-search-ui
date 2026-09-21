/**
 * A future live Write progress frame must not end a run, 2026-09-14.
 *
 * `parseAgentEvent` throws on an unknown type, and that throw ends the run as
 * an error. The durable backend fix will emit Write's start live, so a `step`
 * or `stage` frame is skipped by name. A `cost` frame is still rejected, which
 * is the property the skip must not weaken.
 */

import { describe, expect, it } from "vitest";

import type { AgentEvent } from "../lib/events";
import { consumeEventStream } from "./useAgentRun";

function frame(type: string, payload: unknown, seq: number): string {
  const envelope = { type, version: "v1", trace_id: "t", seq, ts: "2026-09-14T00:00:00Z", payload };
  return `event: ${type}\r\ndata: ${JSON.stringify(envelope)}\r\n\r\n`;
}

function response(body: string): Response {
  const bytes = new TextEncoder().encode(body);
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(bytes);
      controller.close();
    },
  });
  return { ok: true, status: 200, body: stream } as unknown as Response;
}

const DONE = { total_cost_usd: 0, total_tool_calls: 0, elapsed_ms: 1, trust_outcome: "answer" };

describe("forward-compatible progress frames", () => {
  it("skips a step and a stage frame and still delivers the frames around them", async () => {
    const seen: AgentEvent[] = [];
    await consumeEventStream(
      response(
        frame("guard", { passed: true, category: "ok", reason: null }, 0) +
          frame("step", { step: "write", status: "started" }, 1) +
          frame("stage", { name: "write" }, 2) +
          frame("done", DONE, 3),
      ),
      (event) => seen.push(event),
    );
    expect(seen.map((event) => event.type)).toEqual(["guard", "done"]);
  });

  it("still rejects a cost frame", async () => {
    await expect(
      consumeEventStream(response(frame("cost", { usd: 0.01 }, 0)), () => undefined),
    ).rejects.toThrow();
  });
});
