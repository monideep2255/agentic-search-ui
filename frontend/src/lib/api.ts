/**
 * Typed `fetch()` wrappers for the streaming-run REST surface (Section
 * 13.1's minimal subset: create, events, stop; see this ticket's scope
 * note in `tracker/phase_1.2.md`).
 *
 * Every call here carries a real `Authorization: Bearer <token>` header.
 * `src/system_03_search_agent/auth/dependencies.py`'s `get_current_user`
 * requires it on every one of these routes, including the SSE events
 * route; there is no cookie-based session for this backend to fall back
 * on (see `lib/events.ts` and `hooks/useAgentRun.ts` for why the events
 * route cannot use the native `EventSource` API as a result).
 */

export type AudienceDepth = "clinical_brief" | "researcher" | "deep_technical";

export interface CreateRunRequestBody {
  text: string;
  session_id: string;
  audience_depth?: AudienceDepth;
}

export interface CreateRunResponse {
  run_id: string;
  persona_name: string;
}

export interface StopRunResponse {
  stopped: boolean;
}

/**
 * Thrown when the backend responds with a non-2xx status. Carries the
 * HTTP status so a caller can distinguish, for example, a 401 (expired
 * token) from a 403 (run ownership) or a 404 (unknown run_id), per
 * `app.py`'s `_get_owned_run` error ordering.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Same-origin by default. Overridable via `VITE_API_BASE_URL` for a dev
 * setup where the Vite dev server and the FastAPI backend run on
 * different origins (no proxy configured), or via the `baseUrl` option
 * on any of the functions below for tests.
 */
const DEFAULT_BASE_URL: string =
  (import.meta as unknown as { env?: Record<string, string | undefined> }).env
    ?.VITE_API_BASE_URL ?? "";

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

async function throwIfNotOk(response: Response, context: string): Promise<void> {
  if (!response.ok) {
    let detail = "";
    try {
      const body = (await response.clone().json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        detail = `: ${body.detail}`;
      }
    } catch {
      // Response body was not JSON, or was already consumed. The status
      // code alone is still actionable; fall through without detail.
    }
    throw new ApiError(response.status, `${context} failed with ${response.status}${detail}`);
  }
}

export interface ApiCallOptions {
  baseUrl?: string;
  signal?: AbortSignal;
}

/**
 * `POST /v1/query`: starts a new streaming run and returns its `run_id`
 * immediately (202 Accepted), before the agent loop has necessarily
 * finished. `persona_name` is a fixed placeholder string
 * (`app.py`'s `_STUB_PERSONA_NAME`) until phase 4.5 assigns a real one.
 */
export async function createRun(
  body: CreateRunRequestBody,
  token: string,
  options: ApiCallOptions = {},
): Promise<CreateRunResponse> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const response = await fetch(`${baseUrl}/v1/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token),
    },
    body: JSON.stringify(body),
    signal: options.signal,
  });
  await throwIfNotOk(response, "createRun");
  return (await response.json()) as CreateRunResponse;
}

/**
 * `POST /v1/query/{run_id}/stop`: cancels the run's background task.
 * Idempotent on the backend (production-standards.md's retry-safety
 * gate): calling this on an already-finished or already-stopped run
 * still returns `{stopped: true}`, never an error.
 */
export async function stopRun(
  runId: string,
  token: string,
  options: ApiCallOptions = {},
): Promise<StopRunResponse> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const response = await fetch(`${baseUrl}/v1/query/${encodeURIComponent(runId)}/stop`, {
    method: "POST",
    headers: authHeaders(token),
    signal: options.signal,
  });
  await throwIfNotOk(response, "stopRun");
  return (await response.json()) as StopRunResponse;
}

/**
 * Opens the raw `fetch()` response for `GET /v1/query/{run_id}/events`,
 * carrying the real `Authorization` header the native `EventSource` API
 * cannot send (see `hooks/useAgentRun.ts`'s docstring for the full
 * rationale). Returns the raw `Response` rather than a parsed value:
 * `useAgentRun` owns reading and incrementally decoding the
 * `text/event-stream` body, since that is a stateful process (partial
 * frames spanning chunk boundaries), not a single JSON parse.
 *
 * Deliberately not named `getEvents` to avoid implying it returns
 * parsed data; it is a thin transport-layer wrapper only.
 */
export async function openEventStream(
  runId: string,
  token: string,
  options: ApiCallOptions = {},
): Promise<Response> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const response = await fetch(`${baseUrl}/v1/query/${encodeURIComponent(runId)}/events`, {
    method: "GET",
    headers: {
      Accept: "text/event-stream",
      ...authHeaders(token),
    },
    signal: options.signal,
  });
  await throwIfNotOk(response, "openEventStream");
  return response;
}
