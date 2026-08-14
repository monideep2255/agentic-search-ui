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
    surface: "persona",
    rendersToday:
      "A name drawn from a ten-entry placeholder list, held for the session.",
    wiredBy: "4.5",
    realSource:
      "persona_name on the POST /v1/query response, drawn from the curated top-100 " +
      "biomedical-scientist list. Section 14.2. The curated list is its own Phase 6 task.",
  },
  {
    surface: "audience-depth",
    rendersToday:
      "A three-way control that holds its value locally and locks during a run.",
    wiredBy: "4.5",
    realSource: "Query.audience_depth on POST /v1/query. Sections 12.9 and 14.5.",
  },
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
    rendersToday: "An in-memory list of this session's questions, lost on reload.",
    wiredBy: "4.5",
    realSource:
      "Session memory for the live thread; the interactions table for anything " +
      "that must survive a reload, which is build phase 4.6.",
  },
  {
    surface: "feedback",
    rendersToday:
      "Rating, reason chips and the per-citation flag, all accepted and discarded.",
    wiredBy: "4.6",
    realSource:
      "The interactions table, which already names feedback as one of its fields.",
  },
  {
    surface: "guest-allowance",
    rendersToday:
      "NOTHING is rendered for an anonymous visitor beyond the sign-in wall. " +
      "The allowance counter and soft prompt are built but cannot be honoured, " +
      "because there is no anonymous path to the backend.",
    wiredBy: "6.0",
    realSource:
      "Server-side rate limiting plus an anonymous run path. The data model " +
      "already supports the flow: interactions.user_id is nullable so a session " +
      "can start anonymous and attach to an account at signup. " +
      "HISTORY, recorded because it must not be repeated: this entry previously " +
      "described only the counter, while the code rendered a complete fabricated " +
      "answer to anonymous visitors, with real NCBI source URLs and a 'Grounded' " +
      "trust pill, for any question asked. A registry entry that understates what " +
      "a stub renders is worse than none, because it is read as an inventory.",
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
