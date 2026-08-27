/**
 * The stub registry, build phase 4.8, ticket T-4.8-14.
 *
 * Build phase 4.8 builds every screen in the approved design, including
 * surfaces whose backend is owned by a later phase. Those surfaces render from
 * a local stub so the product looks finished, which is the whole point of the
 * phase.
 *
 * The rule that makes that safe: a stub is marked HERE, in code, and never on
 * screen. A demo audience must not be able to tell a stubbed surface from a
 * live one. The premise gate asserts both halves, that every surface below is
 * declared with an owning phase, and that no rendered text says "stub",
 * "placeholder", "coming soon" or "TODO".
 *
 * Why a registry rather than a comment per call site: a stub nobody can
 * enumerate is how a placeholder ships to production. `LEARNINGS.md` records
 * the sibling failure at the ticket level, where a well-reasoned deferral with
 * no named owner fell through twelve phases. This makes the set greppable, and
 * gives the wiring phase a list rather than a search.
 */

export interface StubEntry {
  /** Stable id. Used by the premise gate, so do not rename casually. */
  surface: string;
  /** What renders today, in one line. */
  rendersToday: string;
  /** The build phase that replaces the stub with a real call. */
  wiredBy: string;
  /** Where the real data will come from, so the wiring phase has a starting point. */
  realSource: string;
}

export const STUB_REGISTRY: StubEntry[] = [
  {
    surface: "follow-up",
    rendersToday:
      "A follow-up field with suggested hints, which starts a fresh run.",
    wiredBy: "4.5",
    realSource:
      "Bounded in-conversation session memory, RequestContext.session_memory. " +
      "Decision F and G, Section 14.3.",
  },
  {
    surface: "history",
    rendersToday:
      "REAL as of build phase 4.13 (T-4.13-03): the rail is seeded from " +
      "GET /v1/history, an owner-scoped read over the interactions rows build " +
      "phase 4.6 writes, so the list is no longer in-memory and no longer lost " +
      "on reload. A run taken this session and its server copy render as one " +
      "item, de-duplicated on trace_id. " +
      "TWO BOUNDARIES, stated because a registry entry that overstates what a " +
      "surface does is read as an inventory and is worse than none. First, only " +
      "the QUESTIONS are durable, never the answers: interactions stores no " +
      "synthesised narrative, so a restored item re-asks its question exactly " +
      "as a live item already does (decision D-4.13-01). Second, and this is " +
      "the one a reader will actually hit: after a reload a visitor must sign " +
      "in again before any of it appears, because the access token lives in " +
      "React state alone and the rail is gated on being signed in. The rows " +
      "survive; the identity does not. That is F-4.13-02, it is open, and the " +
      "product owner scoped it as its own piece of work on 2026-08-27 rather " +
      "than settling where a bearer credential may be persisted mid-phase.",
    wiredBy: "4.13",
    realSource:
      "GET /v1/history (adapters/web_sse/app.py), over " +
      "feedback/history.py's list_history, scoped by the caller's exact " +
      "owner_id and never by user_id, which is NULL for every guest. " +
      "HISTORY, recorded because it must not be repeated: this entry named " +
      "build phase 4.6 as the owner until 2026-08-21, which was a guess rather " +
      "than a decision. Section 25 never named history as a 4.6 deliverable, " +
      "and 4.6 shipped the substrate without the read path or the UI.",
  },
  {
    surface: "guest-allowance",
    rendersToday:
      "REAL as of build phase 4.10 (T-4.10-08): an anonymous visitor mints a " +
      "guest identity on the first question asked, gets a real, server-counted " +
      "five-search allowance (guest_sessions.runs_used, spent by one atomic " +
      "UPDATE), and the five dots render that server count, never a client " +
      "guess. The sign-in wall now appears only when the server refuses a run " +
      "with the reason guest_allowance_exhausted, never merely because the " +
      "visitor has no account. What is NOT real yet: durable history across a " +
      "reload. Nothing persists a run today (the run registry is in-memory and " +
      "evicts, and the browser's history list is React state); signing in " +
      "while holding a guest token re-points that guest's LIVE runs to the new " +
      "account, which is the honest subset of \"your searches move with you\" " +
      "(F-4.10-01). Durable cross-reload history is the \"history\" entry " +
      "below, owned by build phase 4.13 (corrected 2026-08-21 from 4.6).",
    wiredBy: "4.10",
    realSource:
      "POST /auth/guest, GET /v1/allowance, and the guest bearer token accepted " +
      "on all four /v1/query* endpoints (adapters/web_sse/app.py). " +
      "HISTORY, recorded because it must not be repeated: this entry previously " +
      "described only the counter, while the code rendered a complete fabricated " +
      "answer to anonymous visitors, with real NCBI source URLs and a 'Grounded' " +
      "trust pill, for any question asked. A registry entry that understates what " +
      "a stub renders is worse than none, because it is read as an inventory. It " +
      "was then wired for real in build phase 4.10, after which \"stub\" applies " +
      "only to the cross-reload history piece, not to the allowance itself; this " +
      "entry stays in the registry (not deleted) so that narrower, still-true " +
      "boundary is documented rather than lost.",
  },
  {
    surface: "kgx-export",
    rendersToday: "A request button that acknowledges and does nothing.",
    wiredBy: "4.4",
    realSource:
      "The KGX export utility, specified as a batch job over the existing " +
      "Layer 1 graph rather than a live adapter.",
  },
];

/** Look up one entry, for a component that wants to assert its own stub is declared. */
export const stubFor = (surface: string): StubEntry | undefined =>
  STUB_REGISTRY.find((entry) => entry.surface === surface);
