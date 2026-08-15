/**
 * Typed `fetch()` wrappers for the streaming-run REST surface (Section
 * 13.1's minimal subset: create, events, stop; see this ticket's scope
 * note in `tracker/phase_1.2.md`) and, added in T-1.2-08, the two `/auth`
 * endpoints a minimal real login needs (`signup`, `login`).
 *
 * Every streaming-run call here carries a real `Authorization: Bearer
 * <token>` header. `src/system_03_search_agent/auth/dependencies.py`'s
 * `get_current_user` requires it on every one of those routes, including
 * the SSE events route; there is no cookie-based session for this backend
 * to fall back on (see `lib/events.ts` and `hooks/useAgentRun.ts` for why
 * the events route cannot use the native `EventSource` API as a result).
 * `signup` and `login` are the one exception: they carry no
 * `Authorization` header at all, since they are how a caller obtains a
 * token in the first place (`src/system_03_search_agent/auth/router.py`'s
 * `signup` and `login` endpoints require no bearer token).
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
 *
 * `reason` (T-4.10-08) is the machine-readable string a structured
 * `detail` object carries, e.g. `guest_allowance_exhausted` or
 * `concurrent_run_cap_exceeded` (`adapters/web_sse/app.py`'s
 * `HTTPException(..., detail={"reason": ..., "message": ...})` shape).
 * It is `undefined` when the backend returned a bare string `detail` (most
 * routes) or no parseable JSON body at all, so a caller must check for
 * `undefined` before branching on a specific reason string; a bare 403 is
 * NOT the same thing as a 403 carrying `guest_allowance_exhausted`, and the
 * two must never be treated alike (design decision 5,
 * `tracker/phase_4.10.md`: a 403 with this exact reason is the only one
 * that means "the allowance is spent, show the sign-in wall").
 */
export class ApiError extends Error {
  readonly status: number;
  readonly reason: string | undefined;

  constructor(status: number, message: string, reason?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.reason = reason;
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
    let reason: string | undefined;
    try {
      const body = (await response.clone().json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        detail = `: ${body.detail}`;
      } else if (body.detail !== null && typeof body.detail === "object") {
        // The structured `{reason, message}` shape (T-4.10-08): read from
        // `app.py`'s actual `HTTPException(detail={...})` calls, not
        // assumed. `reason` is the machine-readable field a caller
        // branches on; `message` is the human-readable one this error's
        // own `message` string carries forward.
        const structured = body.detail as { reason?: unknown; message?: unknown };
        if (typeof structured.reason === "string") {
          reason = structured.reason;
        }
        if (typeof structured.message === "string") {
          detail = `: ${structured.message}`;
        }
      }
    } catch {
      // Response body was not JSON, or was already consumed. The status
      // code alone is still actionable; fall through without detail.
    }
    throw new ApiError(response.status, `${context} failed with ${response.status}${detail}`, reason);
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

// ---------------------------------------------------------------------------
// The guest allowance (T-4.10-08). Mirrors `adapters/web_sse/app.py`'s
// `AllowanceResponse` and `auth/schemas.py`'s `GuestTokenResponse`,
// field for field (design decision 6, `tracker/phase_4.10.md`).
// ---------------------------------------------------------------------------

export type AllowanceKind = "guest" | "user";

/**
 * `GET /v1/allowance`'s response shape. `counted` is the honesty field: a
 * guest's `used` is a real, server-counted value (`true`); a registered
 * caller's `used` reads a structural zero today, because nothing writes
 * `interactions` rows yet (F-2.0-04, `counted: false`). A caller of this
 * function must branch on `counted` before rendering `used` as though it
 * were a measurement, or it repeats the exact dishonesty class F-4.9-A-16
 * named ("Signed in · unlimited searches" against a real, enforced cap).
 */
export interface AllowanceResponse {
  kind: AllowanceKind;
  used: number;
  total: number;
  counted: boolean;
  /**
   * Why no search is available right now, even when `used` is below `total`.
   *
   * Build phase 4.10, design decision 8. `used` and `total` are this
   * caller's own true numbers; this is a separate question, because a
   * system-wide daily ceiling on anonymous runs sits above the personal
   * allowance. Inflating `used` to `total` was rejected on the server side:
   * the personal count is what migrates with the caller at signup, so
   * distorting it would corrupt something real.
   *
   * `null` means nothing is blocking. Optional so a payload predating the
   * field still type-checks.
   *
   * NOT YET CONSUMED BY THE UI. Carried as F-4.10-05: until the dots read
   * it, a visitor can be shown "5 searches left" while the next query is
   * refused 429, which is the same reporting-versus-enforcement mismatch
   * F-4.10-A-03 was filed for one level down. The backend is honest; the
   * client has not been taught to ask.
   */
  blocked_reason?: "anon_daily_cap_reached" | null;
}

/** `POST /auth/guest`'s response shape. */
export interface GuestTokenResponse {
  guest_token: string;
  guest_id: string;
  used: number;
  total: number;
}

/**
 * `GET /v1/allowance`: the calling principal's own search allowance,
 * for a guest or a registered caller alike. Requires whichever bearer
 * token that principal already holds (a guest token or an access token);
 * there is no unauthenticated variant.
 */
export async function getAllowance(
  token: string,
  options: ApiCallOptions = {},
): Promise<AllowanceResponse> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const response = await fetch(`${baseUrl}/v1/allowance`, {
    method: "GET",
    headers: authHeaders(token),
    signal: options.signal,
  });
  await throwIfNotOk(response, "getAllowance");
  return (await response.json()) as AllowanceResponse;
}

/**
 * `POST /auth/guest`: mints a fresh guest identity. No body and no
 * credentials (`auth/router.py`'s `create_guest`): this is the call an
 * anonymous visitor's browser makes the first time it actually needs a
 * guest identity, which `App.tsx` triggers lazily, on the first question
 * asked, rather than on every page load (T-4.10-08).
 */
export async function mintGuest(options: ApiCallOptions = {}): Promise<GuestTokenResponse> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const response = await fetch(`${baseUrl}/auth/guest`, {
    method: "POST",
    signal: options.signal,
  });
  await throwIfNotOk(response, "mintGuest");
  return (await response.json()) as GuestTokenResponse;
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

// ---------------------------------------------------------------------------
// Auth (T-1.2-08). Mirrors `src/system_03_search_agent/auth/schemas.py`'s
// `SignupRequest`/`SignupResponse`/`LoginRequest`/`TokenResponse` field for
// field. Both request bodies use `email`/`password` string fields; the
// backend normalizes and validates the email server-side (NFKC, strip,
// lowercase, then a conservative address grammar), so this client sends
// the value as typed with no client-side reformatting.
// ---------------------------------------------------------------------------

export interface SignupRequestBody {
  email: string;
  password: string;
  /**
   * A held guest session to migrate at signup (design decision 4,
   * `tracker/phase_4.10.md`): when present and valid, the server
   * re-points that guest's live runs to the new account and revokes the
   * guest session, best-effort and never fatal to the signup itself.
   * Omitted entirely (not sent as `undefined`) when the caller never held
   * a guest session, matching the backend's optional field.
   */
  guest_token?: string;
}

export interface SignupResponse {
  id: string;
  email: string;
}

export interface LoginRequestBody {
  email: string;
  password: string;
  /** Same field, same migration, on login instead of signup. */
  guest_token?: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

/**
 * `POST /auth/signup`: registers a new account. Returns only the created
 * user's `id` and `email`, never a token (`SignupResponse` in
 * `schemas.py` carries no token field); a caller that wants a token after
 * signing up must follow with `login` using the same credentials.
 */
export async function signup(
  body: SignupRequestBody,
  options: ApiCallOptions = {},
): Promise<SignupResponse> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const response = await fetch(`${baseUrl}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: options.signal,
  });
  await throwIfNotOk(response, "signup");
  return (await response.json()) as SignupResponse;
}

/**
 * `POST /auth/login`: exchanges an email and password for a bearer token
 * pair. `router.py`'s `login` returns the identical 401 status and the
 * identical "invalid email or password" detail string for an unknown
 * email and for a known email with the wrong password, by design, so a
 * caller of this function cannot and must not try to distinguish "no such
 * account" from "wrong password" from the rejection alone (see
 * `components/auth/AuthGate.tsx`'s docstring for what this means for the
 * auth UI built on top of this function).
 */
export async function login(
  body: LoginRequestBody,
  options: ApiCallOptions = {},
): Promise<LoginResponse> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const response = await fetch(`${baseUrl}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: options.signal,
  });
  await throwIfNotOk(response, "login");
  return (await response.json()) as LoginResponse;
}
