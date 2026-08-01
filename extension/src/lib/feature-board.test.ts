/**
 * Unit tests for the feature-board logic layer.
 *
 * Covers the optimistic-vote state machine (the behaviour the UI relies on)
 * and the fetch wrappers via an injected mock fetch — no DOM, no network.
 */

import { describe, it, expect, vi } from "vitest";
import {
  applyOptimisticVote,
  reconcileVote,
  toggleVoteInList,
  reconcileVoteInList,
  replaceFeatureInList,
  prependFeature,
  fetchFeatures,
  voteFeature,
  submitFeature,
  FeatureBoardError,
  type Feature,
} from "./feature-board";

function makeFeature(overrides: Partial<Feature> = {}): Feature {
  return {
    id: "f1",
    title: "Dark mode",
    status: "open",
    vote_count: 3,
    voted_by_me: false,
    created_at: "2026-07-31T00:00:00Z",
    ...overrides,
  };
}

/** Build a `Response`-ish stub good enough for the wrappers. */
function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: async () => body,
  } as unknown as Response;
}

describe("applyOptimisticVote", () => {
  it("adds a vote and increments the count when not yet voted", () => {
    const result = applyOptimisticVote(
      makeFeature({ voted_by_me: false, vote_count: 3 }),
    );
    expect(result.voted_by_me).toBe(true);
    expect(result.vote_count).toBe(4);
  });

  it("removes a vote and decrements the count when already voted", () => {
    const result = applyOptimisticVote(
      makeFeature({ voted_by_me: true, vote_count: 3 }),
    );
    expect(result.voted_by_me).toBe(false);
    expect(result.vote_count).toBe(2);
  });

  it("clamps the count at zero (never goes negative)", () => {
    const result = applyOptimisticVote(
      makeFeature({ voted_by_me: true, vote_count: 0 }),
    );
    expect(result.voted_by_me).toBe(false);
    expect(result.vote_count).toBe(0);
  });

  it("is a pure toggle — double application returns to the original state", () => {
    const original = makeFeature({ voted_by_me: false, vote_count: 3 });
    const roundTrip = applyOptimisticVote(applyOptimisticVote(original));
    expect(roundTrip.voted_by_me).toBe(original.voted_by_me);
    expect(roundTrip.vote_count).toBe(original.vote_count);
  });

  it("does not mutate the input feature", () => {
    const original = makeFeature({ voted_by_me: false, vote_count: 3 });
    applyOptimisticVote(original);
    expect(original.voted_by_me).toBe(false);
    expect(original.vote_count).toBe(3);
  });
});

describe("reconcileVote", () => {
  it("overwrites vote fields with server-authoritative values", () => {
    const result = reconcileVote(
      makeFeature({ voted_by_me: true, vote_count: 99 }),
      {
        voted: false,
        vote_count: 7,
      },
    );
    expect(result.voted_by_me).toBe(false);
    expect(result.vote_count).toBe(7);
  });
});

describe("list helpers", () => {
  const list = [
    makeFeature({ id: "a", vote_count: 1, voted_by_me: false }),
    makeFeature({ id: "b", vote_count: 5, voted_by_me: true }),
  ];

  it("toggleVoteInList only touches the target feature", () => {
    const next = toggleVoteInList(list, "a");
    expect(next[0]).toMatchObject({
      id: "a",
      voted_by_me: true,
      vote_count: 2,
    });
    expect(next[1]).toBe(list[1]); // untouched reference
  });

  it("reconcileVoteInList applies the server response to the target only", () => {
    const next = reconcileVoteInList(list, "b", {
      voted: false,
      vote_count: 4,
    });
    expect(next[1]).toMatchObject({
      id: "b",
      voted_by_me: false,
      vote_count: 4,
    });
    expect(next[0]).toBe(list[0]);
  });

  it("replaceFeatureInList swaps the matching feature by id", () => {
    const restored = makeFeature({ id: "b", vote_count: 5, voted_by_me: true });
    const mutated = toggleVoteInList(list, "b");
    const next = replaceFeatureInList(mutated, restored);
    expect(next[1]).toBe(restored);
  });

  it("prependFeature puts the new feature first", () => {
    const created = makeFeature({ id: "new", title: "CSV export" });
    const next = prependFeature(list, created);
    expect(next).toHaveLength(3);
    expect(next[0]).toBe(created);
  });
});

describe("fetchFeatures", () => {
  it("returns the features array on success", async () => {
    const features = [makeFeature({ id: "a" }), makeFeature({ id: "b" })];
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ features }));
    const result = await fetchFeatures("jwt-token", fetchMock);
    expect(result).toEqual(features);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/features");
    expect(init.headers.Authorization).toBe("Bearer jwt-token");
  });

  it("defaults to an empty array when the payload omits features", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    expect(await fetchFeatures("jwt-token", fetchMock)).toEqual([]);
  });

  it("throws FeatureBoardError with the status on a non-ok response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(null, false, 401));
    await expect(fetchFeatures("jwt-token", fetchMock)).rejects.toMatchObject({
      status: 401,
    });
  });
});

describe("voteFeature", () => {
  it("POSTs to the vote endpoint and returns the server vote state", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ voted: true, vote_count: 6 }));
    const result = await voteFeature("jwt-token", "f9", fetchMock);
    expect(result).toEqual({ voted: true, vote_count: 6 });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/features/f9/vote");
    expect(init.method).toBe("POST");
  });

  it("throws FeatureBoardError on failure", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(null, false, 500));
    await expect(
      voteFeature("jwt-token", "f9", fetchMock),
    ).rejects.toBeInstanceOf(FeatureBoardError);
  });
});

describe("submitFeature", () => {
  it("sends a title-only body when no description is given", async () => {
    const created = makeFeature({ id: "new", title: "CSV export" });
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(created));
    const result = await submitFeature(
      "jwt-token",
      "  CSV export  ",
      undefined,
      fetchMock,
    );
    expect(result).toEqual(created);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/features");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ title: "CSV export" }); // trimmed, no description key
  });

  it("includes a trimmed description when provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(makeFeature()));
    await submitFeature("jwt-token", "Title", "  more detail  ", fetchMock);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      title: "Title",
      description: "more detail",
    });
  });

  it("surfaces a 429 submission-limit as FeatureBoardError with status 429", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(null, false, 429));
    await expect(
      submitFeature("jwt-token", "Title", undefined, fetchMock),
    ).rejects.toMatchObject({ status: 429 });
  });
});
