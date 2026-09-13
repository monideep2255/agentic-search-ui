/**
 * `lib/authSession.ts`, fix set 4, requirement R46 (decision U8).
 *
 * Two properties matter here and both are asserted: the token survives a
 * round trip through storage, and a browser whose storage throws still
 * behaves, because that is the environment where a crash would be worst
 * (private browsing, a full quota, a sandboxed iframe).
 *
 * Every test states, in a comment, the mutation it is proven to catch, the
 * convention `api.fetchHistory.test.ts` set in this directory.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearPersistedRefreshToken,
  loadPersistedRefreshToken,
  persistRefreshToken,
} from "./authSession";

const KEY = "agentic-search-ui.refresh-token.v1";

/** Replaces `window.localStorage` with one that throws on every operation. */
function breakStorage(): void {
  const thrower = () => {
    throw new DOMException("storage is unavailable", "SecurityError");
  };
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem: thrower,
      setItem: thrower,
      removeItem: thrower,
      clear: thrower,
      key: thrower,
      length: 0,
    },
  });
}

describe("authSession", () => {
  let realStorage: Storage;

  beforeEach(() => {
    realStorage = window.localStorage;
    window.localStorage.clear();
  });

  afterEach(() => {
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: realStorage,
    });
    vi.restoreAllMocks();
  });

  it("returns null before anything has been stored", () => {
    // Mutation: seeding the loader with a default, or returning the raw
    // `undefined` a missing key would give, turns this red.
    expect(loadPersistedRefreshToken()).toBeNull();
  });

  it("round trips a refresh token through storage under the versioned key", () => {
    // Mutation: writing under a different key than the one the loader
    // reads, which is the defect that would make a reload look like it
    // persisted nothing, turns this red.
    persistRefreshToken("refresh-token-1");

    expect(window.localStorage.getItem(KEY)).toBe("refresh-token-1");
    expect(loadPersistedRefreshToken()).toBe("refresh-token-1");
  });

  it("overwrites the stored value, so a rotated token replaces the dead one", () => {
    // Mutation: an append, a no-op on a second write, or a write guarded by
    // "only if empty" turns this red. It has to be an overwrite: after
    // `POST /auth/refresh` the previous token is revoked server-side, so
    // keeping it would leave the browser holding a credential that is
    // guaranteed to fail and whose failure revokes the whole family.
    persistRefreshToken("refresh-token-1");
    persistRefreshToken("refresh-token-2");

    expect(loadPersistedRefreshToken()).toBe("refresh-token-2");
  });

  it("clears the stored value", () => {
    // Mutation: a clear that writes an empty string rather than removing
    // the key would pass a naive check; the loader's own empty-string
    // normalisation is asserted separately below.
    persistRefreshToken("refresh-token-1");
    clearPersistedRefreshToken();

    expect(window.localStorage.getItem(KEY)).toBeNull();
    expect(loadPersistedRefreshToken()).toBeNull();
  });

  it("treats an empty stored string as no session", () => {
    // Mutation: returning the raw value turns this red. An empty string is
    // not a usable credential and `RefreshRequest`'s `min_length=1` would
    // answer 422, so it must never be sent.
    window.localStorage.setItem(KEY, "");

    expect(loadPersistedRefreshToken()).toBeNull();
  });

  it("returns null instead of throwing when storage is unreachable", () => {
    // Mutation: dropping the try/catch from the loader turns this red, and
    // in the product it takes the whole render down inside the restore
    // effect rather than degrading to "this visitor is a guest".
    breakStorage();

    expect(() => loadPersistedRefreshToken()).not.toThrow();
    expect(loadPersistedRefreshToken()).toBeNull();
  });

  it("does not throw when a write or a clear is impossible", () => {
    // Mutation: dropping either try/catch turns this red. A sign-in that
    // has already succeeded must not be broken by a browser that refuses
    // to remember it; the session degrades to this tab only.
    breakStorage();

    expect(() => persistRefreshToken("refresh-token-1")).not.toThrow();
    expect(() => clearPersistedRefreshToken()).not.toThrow();
  });
});
