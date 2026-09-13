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
 * `detail` object carries: `guest_allowance_exhausted`,
 * `guest_attempt_limit_reached`, `concurrent_run_cap_exceeded`,
 * `anon_daily_cap_reached`, or
 * `guest_session_revoked` (`adapters/web_sse/app.py`'s
 * `HTTPException(..., detail={"reason": ..., "message": ...})` shape).
 * It is `undefined` when the backend returned a bare string `detail` (most
 * routes) or no parseable JSON body at all, so a caller must check for
 * `undefined` before branching on a specific reason string; a bare 403 is
 * NOT the same thing as a 403 carrying `guest_allowance_exhausted`, and the
 * two must never be treated alike (design decision 5,
 * `tracker/phase_4.10.md`: a 403 with this exact reason is the only one
 * that means "the allowance is spent, show the sign-in wall").
 *
 * The same distinction on 401 is what F-4.10-A-05 turns on: a 401 carrying
 * `guest_session_revoked` means the server revoked this guest session at
 * migration, so the client must NOT mint a fresh identity, while a bare 401
 * (a token past its 7-day TTL, tampered, or signed with the wrong key)
 * legitimately should.
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
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
   * `guest_attempt_limit_reached` (F-4.10-R-01) is the second value: this
   * guest has started as many runs as a guest may start, so the next query
   * is refused 403 even though refunded answers left `used` below `total`.
   *
   * `anon_source_daily_cap_reached` (F-4.10-V-01) is the third: this
   * network has taken its share of today's anonymous budget. Kept distinct
   * from `anon_daily_cap_reached` because the two say different true
   * things, and rendering "the whole product is busy" for "your network has
   * had its share" would be a confident wrong answer in the UI.
   *
   * NOW CONSUMED BY THE UI (F-4.10-V-03 closes F-4.10-05's client half).
   * `App.tsx` passes it to `GuestAllowance`, which stops rendering "N
   * searches left" the moment any value is present. It had to: unlike the
   * daily ceiling, which clears at UTC midnight, `guest_attempt_limit_
   * reached` never clears for that identity, so an unread field left the
   * dots promising a search for the remaining life of a 7-day token. The
   * REFUSAL itself was already handled either way: `App.tsx` walls on both
   * 403 reasons, with its own sentence for each.
   */
  blocked_reason?:
    | "anon_daily_cap_reached"
    | "anon_source_daily_cap_reached"
    | "guest_attempt_limit_reached"
    | null;
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
export interface MeResponse {
  id: string;
  email: string;
  audience_depth: string;
  persona_name: string;
}

/**
 * `GET /auth/me` (T-4.5-08, Section 14.5).
 *
 * Read once on sign-in so the depth control starts where this account left
 * it, on any device, rather than resetting to the default every session.
 * localStorage would have been cheaper and is wrong for the same reason a
 * client-side persona draw was wrong: the preference belongs to the ACCOUNT,
 * not to the browser.
 */
export async function fetchMe(
  token: string,
  options: ApiCallOptions = {},
): Promise<MeResponse> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const response = await fetch(`${baseUrl}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
    signal: options.signal,
  });
  await throwIfNotOk(response, "fetchMe");
  return (await response.json()) as MeResponse;
}

export interface PersonaResponse {
  persona_name: string;
}

/**
 * `GET /v1/persona` (T-4.5-10, Section 14.2).
 *
 * Reachable without a credential, because its whole job is to serve a
 * visitor who has no credential yet, so the persona chip in the app shell has
 * a real name on the landing screen instead of a locally invented one.
 *
 * `token`, when given, is sent as the bearer credential, and F-4.5-J-12 is
 * why it exists. The docstring here used to claim "the server keys it exactly
 * as `POST /v1/query` does, so the name shown before the first question is
 * the one the first answer will carry", and the endpoint hardcoded an
 * anonymous identity, so for a signed-in user the claim was false: the chip
 * named the session's scientist and every answer named the account's. Sending
 * the token is what makes the old sentence true. An absent, stale or invalid
 * token is not an error on this endpoint; the server falls back to the
 * session-keyed name rather than refusing.
 *
 * This is the ONE call the app uses for the pre-answer persona. `fetchMe`
 * also carries a `persona_name`, and App deliberately ignores it: two
 * unordered requests both writing one piece of state is a race, and the
 * winner was decided by network timing (F-4.5-A-12).
 */
export async function fetchPersona(
  sessionId: string,
  options: ApiCallOptions & { token?: string | null } = {},
): Promise<PersonaResponse> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const response = await fetch(
    `${baseUrl}/v1/persona?session_id=${encodeURIComponent(sessionId)}`,
    {
      signal: options.signal,
      headers:
        options.token != null ? { Authorization: `Bearer ${options.token}` } : undefined,
    },
  );
  await throwIfNotOk(response, "fetchPersona");
  return (await response.json()) as PersonaResponse;
}

// ---------------------------------------------------------------------------
// History (T-4.13-03). `GET /v1/history`'s response shape, per the contract
// pinned in `tracker/phase_4.13.md` (T-4.13-02, built by a sibling ticket in
// parallel with this one). Only `trace_id` and `question` are required here:
// every other field is read defensively, per this ticket's own instruction,
// rather than assumed present.
// ---------------------------------------------------------------------------

/**
 * One restored row of `GET /v1/history`.
 *
 * `trace_id` is `Query.trace_id`, byte-identical to the `run_id`
 * `createRun` returns (`adapters/web_sse/app.py`'s own "run_id/trace_id
 * wiring" comment). `App.tsx` uses it, not `question` text, as the key that
 * tells "this session's own run, now echoed back by the server" apart from
 * "a different past search that happens to share the same question text";
 * see `mergeServerHistory` there for why text alone is the wrong key.
 *
 * `asked_at`, `trust_signal` and `citation_count` are read only for
 * possible future display; nothing in this phase's UI renders them yet
 * (Coverage, `tracker/phase_4.13.md`: only the question list is durable,
 * not the answer), so they are optional here rather than required.
 */
export interface HistoryItem {
  trace_id: string;
  /** The question exactly as asked. This is the rail's label. */
  question: string;
  asked_at?: string;
  trust_signal?: string;
  citation_count?: number;
}

export interface HistoryResponse {
  items: HistoryItem[];
  count: number;
}

/** The minimum shape a history item must carry to be usable at all. */
function isHistoryItem(value: unknown): value is HistoryItem {
  return isRecord(value) && typeof value.trace_id === "string" && typeof value.question === "string";
}

/**
 * Keeps the three optional fields only when they carry the type this
 * interface DECLARES, and drops each one that does not.
 *
 * Round 3 of build phase 4.13. `isHistoryItem` above checks `trace_id` and
 * `question` and nothing else, so before this the declared types on the
 * other three were a claim no code enforced, and every consumer that read
 * one was reading `unknown` through a `string` or `number` annotation.
 * Measured, not reasoned: an `asked_at` of `1` or `true` reaches
 * `new Date(...)` as a millisecond offset and produces a VALID 1970 date,
 * which `App.tsx`'s `formatHistoryMeta` then renders under a real question
 * as though the server had said so. `Number.isNaN(date.getTime())` is a
 * validity check and cannot see that, because the date IS valid; only a
 * type check can. A `citation_count` of `"abc"` is worse in the same
 * direction, rendering "abc sources", and `{}` renders "[object Object]
 * sources": a fabricated source count presented as a real one.
 *
 * Dropped rather than coerced, and dropped per FIELD rather than per row.
 * Coercing would invent the value this is here to stop inventing, and
 * dropping the whole row would lose a question the caller really did ask
 * over a field nothing yet renders. An absent field is already the
 * documented "not available" state (every one is optional), and every
 * consumer omits what is absent, so this degrades to silence rather than
 * to a wrong number. Same rule as the server's own `omitted_count`
 * discipline: a value that cannot be read honestly is not reported.
 */
function withValidatedOptionalFields(item: HistoryItem): HistoryItem {
  const source = item as unknown as Record<string, unknown>;
  const validated: HistoryItem = { trace_id: item.trace_id, question: item.question };
  if (typeof source.asked_at === "string") validated.asked_at = source.asked_at;
  if (typeof source.trust_signal === "string") validated.trust_signal = source.trust_signal;
  // `Number.isFinite` rather than `typeof === "number"`: NaN and Infinity
  // are both numbers and both render as text no reader can act on.
  if (typeof source.citation_count === "number" && Number.isFinite(source.citation_count)) {
    validated.citation_count = source.citation_count;
  }
  return validated;
}

/**
 * `GET /v1/history`: the calling principal's own past questions, newest
 * first, scoped to whichever bearer token authenticates the call (a guest
 * or an account, per the endpoint's contract; `App.tsx` calls this only
 * for a signed-in account today, matching where the rail actually renders,
 * see its own seeding effect for why).
 *
 * The body is re-validated on receipt rather than cast straight to
 * `HistoryResponse`, the same discipline `lib/events.ts` applies to the
 * SSE stream: a malformed or unexpected shape is rejected here rather than
 * handed to a component that assumes well-formed data. An individual item
 * missing `trace_id` or `question` is dropped rather than failing the
 * whole fetch, so one malformed row does not blank a caller's entire rail.
 *
 * Throws `ApiError` on a non-2xx status (401 with no credential, most
 * relevantly) and a plain `Error` on a 2xx response whose body does not
 * even carry a well-formed `items` array. Both are ordinary rejections a
 * caller handles the same way: `App.tsx`'s seeding effect treats any
 * rejection as "leave whatever is already on screen", per
 * production-standards' graceful-degradation gate.
 */
export async function fetchHistory(
  token: string,
  options: ApiCallOptions & { limit?: number } = {},
): Promise<HistoryResponse> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const query = options.limit != null ? `?limit=${encodeURIComponent(String(options.limit))}` : "";
  const response = await fetch(`${baseUrl}/v1/history${query}`, {
    method: "GET",
    headers: authHeaders(token),
    signal: options.signal,
  });
  await throwIfNotOk(response, "fetchHistory");
  const body: unknown = await response.json();
  if (!isRecord(body) || !Array.isArray(body.items) || typeof body.count !== "number") {
    throw new Error("fetchHistory: response body was not the documented {items, count} shape");
  }
  return {
    items: body.items.filter(isHistoryItem).map(withValidatedOptionalFields),
    count: body.count,
  };
}

export async function mintGuest(
  options: ApiCallOptions & { sessionId?: string } = {},
): Promise<GuestTokenResponse> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  // `session_id`, when the caller knows it, so the `persona_name` on the mint
  // response is keyed the same way every later `POST /v1/query` from this
  // guest is keyed (F-4.5-A-12). Without it the server keys on the guest row
  // id and returns a name that can never match the first answer.
  const query =
    options.sessionId != null
      ? `?session_id=${encodeURIComponent(options.sessionId)}`
      : "";
  const response = await fetch(`${baseUrl}/auth/guest${query}`, {
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
 * `POST /auth/refresh`'s body. Mirrors `auth/schemas.py`'s `RefreshRequest`
 * field for field, including its `extra="forbid"`: an unknown field is a
 * 422, so nothing else may be added here without the schema moving first.
 */
export interface RefreshRequestBody {
  refresh_token: string;
}

/** `POST /auth/logout`'s body. Mirrors `auth/schemas.py`'s `LogoutRequest`. */
export interface LogoutRequestBody {
  refresh_token: string;
}

/** `POST /auth/logout`'s response. Mirrors `auth/schemas.py`'s `LogoutResponse`. */
export interface LogoutResponse {
  status: string;
}

// ---------------------------------------------------------------------------
// Feedback (T-4.6-09). Mirrors `src/system_03_search_agent/feedback/
// contracts.py`'s `FeedbackPayload` field for field, and
// `adapters/web_sse/app.py`'s `post_v1_query_feedback` route.
// ---------------------------------------------------------------------------

export interface FeedbackCitationFlag {
  citation_id: string;
  reason: string;
}

export interface FeedbackRequestBody {
  rating: "up" | "down" | null;
  comment: string | null;
  flagged_reason: string | null;
  citation_flags: FeedbackCitationFlag[];
}

/**
 * Thrown for `postFeedback`'s one special case: a 409 Conflict.
 *
 * `feedback.capture_run` is dispatched as a background task after the
 * `done` event (`app.py`'s own comment above `post_v1_query_feedback`), so
 * a rating submitted the instant an answer lands can genuinely arrive
 * before the `interactions` row does. The server answers that race with
 * 409 and a `Retry-After` header, never a 404 (which would say the run
 * does not exist at all) and never a bare 200 (which would silently drop
 * the rating). A caller of `postFeedback` must treat this as "try again
 * shortly", never as an ordinary failure.
 */
export class FeedbackNotYetCapturedError extends Error {
  /** Seconds to wait before retrying, read from the response's `Retry-After`
   *  header. Falls back to 3, the server's own documented retry hint
   *  (`app.py`'s `_FEEDBACK_NOT_YET_CAPTURED_RETRY_AFTER_S`), when the
   *  header is missing or unparseable. */
  readonly retryAfterS: number;

  constructor(retryAfterS: number) {
    super("this run's feedback target has not been captured yet");
    this.name = "FeedbackNotYetCapturedError";
    this.retryAfterS = retryAfterS;
  }
}

/**
 * `POST /v1/query/{run_id}/feedback`: submits, or replaces, this caller's
 * rating, comment and per-citation flags for one run. 204 No Content on
 * success, so there is no body to parse.
 *
 * `record_feedback` REPLACES the whole `user_feedback` row on every call
 * (`feedback/writer.py`'s own docstring), rather than merging fields in.
 * A caller must therefore always send the full current payload, rating,
 * comment, flagged_reason and citation_flags together, never just the one
 * field that changed, or an earlier field silently reverts to null.
 *
 * Throws `FeedbackNotYetCapturedError` on 409 (see above). Every other
 * non-2xx status throws the ordinary `ApiError`, including 403 (this run
 * belongs to someone else) and 404 (no such run).
 */
export async function postFeedback(
  runId: string,
  body: FeedbackRequestBody,
  token: string,
  options: ApiCallOptions = {},
): Promise<void> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const response = await fetch(`${baseUrl}/v1/query/${encodeURIComponent(runId)}/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token),
    },
    body: JSON.stringify(body),
    signal: options.signal,
  });
  if (response.status === 409) {
    const header = response.headers.get("Retry-After");
    const parsed = header !== null ? Number(header) : NaN;
    throw new FeedbackNotYetCapturedError(Number.isFinite(parsed) && parsed > 0 ? parsed : 3);
  }
  await throwIfNotOk(response, "postFeedback");
  // 204 No Content: nothing to parse.
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

/**
 * `POST /auth/refresh`: exchanges a refresh token for a fresh access token
 * and a fresh refresh token (fix set 4, requirement R46, decision U8).
 *
 * THIS CALL IS DESTRUCTIVE TO ITS OWN ARGUMENT, which is the single most
 * important thing a caller has to know. `router.py`'s `refresh` revokes the
 * presented token in the same transaction that mints its replacement, so
 * the token passed in is dead the moment this resolves and the returned
 * `refresh_token` is the only live one. Presenting a revoked token again
 * revokes every session in that family and answers 401
 * (`_revoke_family_on_reuse`, finding F-1.1-07), so a caller must never
 * send the same value twice: read it, clear it, send it, and store what
 * comes back. `lib/authSession.ts` holds that value and `App.tsx`'s restore
 * and keep-alive effects are the two callers.
 *
 * Carries no `Authorization` header, the same as `login` and `signup`: the
 * refresh token in the body IS the credential, and the access token it
 * replaces has usually already expired.
 *
 * Throws the ordinary `ApiError` on a non-2xx status. 401 is the expected,
 * ordinary outcome for a token that has expired, been revoked, or been
 * replayed, and a caller should treat it as "this visitor is signed out",
 * never as an error worth showing.
 */
export async function refreshSession(
  refreshToken: string,
  options: ApiCallOptions = {},
): Promise<LoginResponse> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const body: RefreshRequestBody = { refresh_token: refreshToken };
  const response = await fetch(`${baseUrl}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: options.signal,
  });
  await throwIfNotOk(response, "refreshSession");
  return (await response.json()) as LoginResponse;
}

/**
 * `POST /auth/logout`: revokes one refresh token server-side.
 *
 * Called on log out so the credential this browser was holding cannot be
 * used again by anyone who later reads the stored value. Best-effort at the
 * call site: `App.tsx` clears its own state and storage whether or not this
 * resolves, because a network failure must never leave a person apparently
 * still signed in after they pressed Log out. A 401 here means the token
 * was already dead, which is the desired end state anyway.
 */
export async function logoutSession(
  refreshToken: string,
  options: ApiCallOptions = {},
): Promise<LogoutResponse> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const body: LogoutRequestBody = { refresh_token: refreshToken };
  const response = await fetch(`${baseUrl}/auth/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: options.signal,
  });
  await throwIfNotOk(response, "logoutSession");
  return (await response.json()) as LogoutResponse;
}
