/**
 * Unit tests for the analysis-feedback logic layer.
 *
 * Covers the pure validators (the behaviour the widget gates on) and the
 * fetch wrapper via an injected mock fetch — no DOM, no network.
 */

import { describe, it, expect, vi } from "vitest";
import {
  countValidChars,
  canSubmit,
  sendFeedback,
  FeedbackError,
  MIN_BUG_CHARS,
  UP_REASONS,
  DOWN_REASONS,
  type FeedbackPayload,
} from "./feedback";

/** Build a `Response`-ish stub good enough for the wrapper. */
function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: async () => body,
  } as unknown as Response;
}

describe("countValidChars", () => {
  it("counts zero for empty or whitespace-only input", () => {
    expect(countValidChars("")).toBe(0);
    expect(countValidChars("   \n\t  ")).toBe(0);
  });

  it("counts non-whitespace characters, ignoring interior whitespace", () => {
    expect(countValidChars("a".repeat(24))).toBe(24);
    expect(countValidChars("a".repeat(25))).toBe(25);
    expect(countValidChars("  " + "a".repeat(25) + "  \n")).toBe(25);
  });

  it("counts multi-word input by its non-whitespace characters", () => {
    // "the product listing is wrong" → 24 non-space chars.
    expect(countValidChars("the product listing is wrong")).toBe(24);
  });

  it("counts emoji and astral characters once each (code points, not UTF-16 units)", () => {
    expect(countValidChars("🎉🎉🎉")).toBe(3);
    expect(countValidChars("café ☕ résumé")).toBe(11);
  });
});

describe("canSubmit", () => {
  it("is false with no rating chosen", () => {
    expect(canSubmit(null, "anything at all goes here!!")).toBe(false);
  });

  it("is true for up/down regardless of comment (badges/comment optional)", () => {
    expect(canSubmit("up", "")).toBe(true);
    expect(canSubmit("down", "")).toBe(true);
    expect(canSubmit("up", "   ")).toBe(true);
  });

  it("requires MIN_BUG_CHARS non-whitespace characters for a bug", () => {
    expect(canSubmit("bug", "a".repeat(MIN_BUG_CHARS - 1))).toBe(false);
    expect(canSubmit("bug", "a".repeat(MIN_BUG_CHARS))).toBe(true);
  });

  it("does not let whitespace pad a bug description to the minimum", () => {
    expect(canSubmit("bug", " ".repeat(40))).toBe(false);
    expect(canSubmit("bug", "short " + " ".repeat(40))).toBe(false);
  });

  it("accepts an emoji-containing bug description once it is long enough", () => {
    expect(canSubmit("bug", "🐛".repeat(MIN_BUG_CHARS))).toBe(true);
  });
});

describe("reason lists", () => {
  it("expose the exact canonical strings the backend validates against", () => {
    expect(UP_REASONS).toEqual([
      "Accurate",
      "Clear & simple",
      "Caught something",
      "Good sources",
      "Saved me time",
    ]);
    expect(DOWN_REASONS).toEqual([
      "Looks wrong",
      "Confusing",
      "Missed something",
      "Wrong product",
      "Not enough detail",
    ]);
  });
});

describe("sendFeedback", () => {
  const payload: FeedbackPayload = {
    url_hash: "abc123",
    rating: "up",
    reasons: ["Accurate", "Good sources"],
    comment: null,
  };

  it("POSTs the payload with the bearer token and returns the body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    const result = await sendFeedback("jwt-token", payload, fetchMock);
    expect(result).toEqual({ ok: true });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/feedback");
    expect(init.method).toBe("POST");
    expect(init.headers.Authorization).toBe("Bearer jwt-token");
    expect(JSON.parse(init.body)).toEqual(payload);
  });

  it("surfaces a 422 validation error as FeedbackError with status 422", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(null, false, 422));
    await expect(
      sendFeedback("jwt-token", payload, fetchMock),
    ).rejects.toMatchObject({ status: 422 });
  });

  it("surfaces a 429 rate limit as FeedbackError", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(null, false, 429));
    await expect(
      sendFeedback("jwt-token", payload, fetchMock),
    ).rejects.toBeInstanceOf(FeedbackError);
  });
});
