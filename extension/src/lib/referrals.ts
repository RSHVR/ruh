/**
 * Referral flow logic.
 *
 * Same split as the feature board (see lib/feature-board.ts): the interesting
 * behaviour lives in pure functions so it's unit-testable without a DOM or a
 * live network, and the backend is reached through thin `fetch` wrappers that
 * take a dependency-injected fetch (defaulting to the global) for testing.
 *
 * API contract (all requests require `Authorization: Bearer <supabase JWT>`):
 *   GET  /api/referrals  → { referrals: Referral[], summary: ReferralSummary }
 *   POST /api/referrals  → { added, skipped, summary }   (body: { emails: string[] }, 1..20)
 * Error statuses: 401 unauthenticated, 422 validation, 429 rate limit.
 */

export type ReferralStatus = "invited" | "signed_up" | "credited" | string;

export interface Referral {
  invited_email: string;
  status: ReferralStatus;
  created_at: string;
}

export interface ReferralSummary {
  invited: number;
  signed_up: number;
  credited: number;
  /** Number of referral credits that can be earned (backend caps at 5). */
  credited_cap: number;
}

export interface GetReferralsResponse {
  referrals: Referral[];
  summary: ReferralSummary;
}

export interface SendReferralsResponse {
  /** Emails newly added as invites this call. */
  added: number;
  /** Emails ignored because they were already invited. */
  skipped: number;
  summary: ReferralSummary;
}

/** Error carrying the HTTP status so callers can special-case 401/422/429. */
export class ReferralError extends Error {
  status: number;

  constructor(status: number, message?: string) {
    super(message ?? `Referral request failed (${status})`);
    this.name = "ReferralError";
    this.status = status;
  }
}

/** Max emails the backend accepts in one POST /api/referrals call. */
export const MAX_EMAILS_PER_SEND = 20;

// --- Pure email parsing (unit-testable) ---

export interface PartitionedEmails {
  /** Cleaned, lowercased, de-duplicated valid emails. */
  valid: string[];
  /** Distinct tokens that failed validation, preserved as typed. */
  invalid: string[];
}

// Deliberately loose: one `@`, a dot in the domain, no whitespace. Good enough
// to catch typos before hitting the network; the backend is the real authority.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Split free-form textarea input (commas, semicolons, spaces, newlines — any
 * mix) into distinct emails, partitioned into valid and invalid. Valid emails
 * are lowercased and de-duplicated case-insensitively; invalid tokens are kept
 * as the user typed them (deduped) so they can be shown back for correction.
 */
export function partitionEmails(input: string): PartitionedEmails {
  const tokens = input
    .split(/[\s,;]+/)
    .map((t) => t.trim())
    .filter(Boolean);

  const valid: string[] = [];
  const invalid: string[] = [];
  const seenValid = new Set<string>();
  const seenInvalid = new Set<string>();

  for (const token of tokens) {
    if (EMAIL_RE.test(token)) {
      const normalized = token.toLowerCase();
      if (!seenValid.has(normalized)) {
        seenValid.add(normalized);
        valid.push(normalized);
      }
    } else {
      const key = token.toLowerCase();
      if (!seenInvalid.has(key)) {
        seenInvalid.add(key);
        invalid.push(token);
      }
    }
  }

  return { valid, invalid };
}

/**
 * Human phrasing for a send result, e.g. "3 added, 1 already invited".
 * Pure so the exact copy is testable.
 */
export function summarizeSend(added: number, skipped: number): string {
  const parts: string[] = [];
  if (added > 0) parts.push(`${added} added`);
  if (skipped > 0) parts.push(`${skipped} already invited`);
  return parts.length ? parts.join(", ") : "No new invites sent.";
}

// --- Network wrappers ---

type FetchLike = typeof fetch;

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

function authHeaders(token: string): Record<string, string> {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

/** Fill in a partial/absent summary so the UI always has the four fields. */
function normalizeSummary(
  s: Partial<ReferralSummary> | undefined | null,
): ReferralSummary {
  return {
    invited: s?.invited ?? 0,
    signed_up: s?.signed_up ?? 0,
    credited: s?.credited ?? 0,
    credited_cap: s?.credited_cap ?? 5,
  };
}

/** GET /api/referrals — the caller's invite list plus a rolled-up summary. */
export async function getReferrals(
  token: string,
  fetchImpl: FetchLike = fetch,
): Promise<GetReferralsResponse> {
  const res = await fetchImpl(`${API_BASE}/api/referrals`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new ReferralError(res.status);
  const data = await res.json();
  return {
    referrals: Array.isArray(data?.referrals) ? data.referrals : [],
    summary: normalizeSummary(data?.summary),
  };
}

/** POST /api/referrals — invite one or more friends by email. */
export async function sendReferrals(
  token: string,
  emails: string[],
  fetchImpl: FetchLike = fetch,
): Promise<SendReferralsResponse> {
  const res = await fetchImpl(`${API_BASE}/api/referrals`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ emails }),
  });
  if (!res.ok) throw new ReferralError(res.status);
  const data = await res.json();
  return {
    added: data?.added ?? 0,
    skipped: data?.skipped ?? 0,
    summary: normalizeSummary(data?.summary),
  };
}
