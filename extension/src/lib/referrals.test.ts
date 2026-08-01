/**
 * Unit tests for the referral logic layer.
 *
 * Covers the pure email parser + send-summary formatter (the behaviour the UI
 * relies on) and the fetch wrappers via an injected mock fetch — no DOM, no
 * network.
 */

import { describe, it, expect, vi } from "vitest";
import {
  partitionEmails,
  summarizeSend,
  getReferrals,
  sendReferrals,
  ReferralError,
  type Referral,
  type ReferralSummary,
} from "./referrals";

/** Build a `Response`-ish stub good enough for the wrappers. */
function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: async () => body,
  } as unknown as Response;
}

const summary: ReferralSummary = {
  invited: 2,
  signed_up: 1,
  credited: 1,
  credited_cap: 5,
};

describe("partitionEmails", () => {
  it("splits on mixed separators (commas, spaces, newlines, semicolons)", () => {
    const { valid } = partitionEmails(
      "a@x.com, b@x.com\nc@x.com d@x.com;e@x.com",
    );
    expect(valid).toEqual([
      "a@x.com",
      "b@x.com",
      "c@x.com",
      "d@x.com",
      "e@x.com",
    ]);
  });

  it("lowercases and de-duplicates valid emails case-insensitively", () => {
    const { valid } = partitionEmails(
      "Friend@X.com, friend@x.com, FRIEND@x.com",
    );
    expect(valid).toEqual(["friend@x.com"]);
  });

  it("partitions invalid tokens away from valid ones", () => {
    const { valid, invalid } = partitionEmails(
      "good@x.com, not-an-email, also bad@, ok@y.com",
    );
    expect(valid).toEqual(["good@x.com", "ok@y.com"]);
    expect(invalid).toEqual(["not-an-email", "also", "bad@"]);
  });

  it("de-duplicates invalid tokens too (case-insensitively), preserving typed form", () => {
    const { invalid } = partitionEmails("Nope, nope, NOPE");
    expect(invalid).toEqual(["Nope"]);
  });

  it("returns empty arrays for empty or whitespace-only input", () => {
    expect(partitionEmails("")).toEqual({ valid: [], invalid: [] });
    expect(partitionEmails("   \n , ; ")).toEqual({ valid: [], invalid: [] });
  });

  it("trims surrounding whitespace on each token", () => {
    const { valid } = partitionEmails("   spaced@x.com   ");
    expect(valid).toEqual(["spaced@x.com"]);
  });
});

describe("summarizeSend", () => {
  it("reports added and skipped together", () => {
    expect(summarizeSend(3, 1)).toBe("3 added, 1 already invited");
  });

  it("reports added only when nothing was skipped", () => {
    expect(summarizeSend(2, 0)).toBe("2 added");
  });

  it("reports skipped only when nothing was added", () => {
    expect(summarizeSend(0, 2)).toBe("2 already invited");
  });

  it("has a neutral message when nothing happened", () => {
    expect(summarizeSend(0, 0)).toBe("No new invites sent.");
  });
});

describe("getReferrals", () => {
  it("returns referrals and summary on success and sends the bearer token", async () => {
    const referrals: Referral[] = [
      { invited_email: "a@x.com", status: "invited", created_at: "2026-08-01" },
      {
        invited_email: "b@x.com",
        status: "credited",
        created_at: "2026-08-01",
      },
    ];
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ referrals, summary }));

    const result = await getReferrals("jwt-token", fetchMock);
    expect(result.referrals).toEqual(referrals);
    expect(result.summary).toEqual(summary);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/referrals");
    expect(init.headers.Authorization).toBe("Bearer jwt-token");
  });

  it("defaults missing referrals/summary fields rather than throwing", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    const result = await getReferrals("jwt-token", fetchMock);
    expect(result.referrals).toEqual([]);
    expect(result.summary).toEqual({
      invited: 0,
      signed_up: 0,
      credited: 0,
      credited_cap: 5,
    });
  });

  it("throws ReferralError with the status on a 401", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(null, false, 401));
    await expect(getReferrals("jwt-token", fetchMock)).rejects.toMatchObject({
      status: 401,
    });
  });
});

describe("sendReferrals", () => {
  it("POSTs the emails array and returns the send result", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ added: 3, skipped: 1, summary }));

    const result = await sendReferrals(
      "jwt-token",
      ["a@x.com", "b@x.com", "c@x.com"],
      fetchMock,
    );
    expect(result).toEqual({ added: 3, skipped: 1, summary });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/referrals");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      emails: ["a@x.com", "b@x.com", "c@x.com"],
    });
  });

  it("surfaces a 422 validation error as ReferralError with status 422", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(null, false, 422));
    await expect(
      sendReferrals("jwt-token", ["bad"], fetchMock),
    ).rejects.toMatchObject({ status: 422 });
  });

  it("surfaces a 429 rate limit as ReferralError", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(null, false, 429));
    await expect(
      sendReferrals("jwt-token", ["a@x.com"], fetchMock),
    ).rejects.toBeInstanceOf(ReferralError);
  });
});
