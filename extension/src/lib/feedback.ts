/**
 * Analysis-feedback logic.
 *
 * Same split as the referral / feature-board layers: the interesting behaviour
 * lives in pure functions (unit-testable without a DOM or network) and the
 * backend is reached through a thin `fetch` wrapper taking a dependency-injected
 * fetch (defaulting to the global) for testing.
 *
 * API contract (requires `Authorization: Bearer <supabase JWT>`):
 *   POST /api/feedback  → { ok: true }
 *     body: { url_hash, rating: 'up'|'down'|'bug', reasons: string[], comment: string|null }
 * Error statuses: 401 unauthenticated, 422 validation, 429 rate limit.
 */

export type FeedbackRating = "up" | "down" | "bug";

export interface FeedbackPayload {
  url_hash: string;
  rating: FeedbackRating;
  reasons: string[];
  comment: string | null;
}

export interface FeedbackResponse {
  ok: boolean;
}

/**
 * Canonical reason lists. The backend validates submitted reasons against
 * these exact strings, so the UI must mirror them verbatim.
 */
export const UP_REASONS: string[] = [
  "Accurate",
  "Clear & simple",
  "Caught something",
  "Good sources",
  "Saved me time",
];

export const DOWN_REASONS: string[] = [
  "Looks wrong",
  "Confusing",
  "Missed something",
  "Wrong product",
  "Not enough detail",
];

/** A bug report's description must have at least this many non-whitespace chars. */
export const MIN_BUG_CHARS = 25;

/** Error carrying the HTTP status so callers can special-case 401/422/429. */
export class FeedbackError extends Error {
  status: number;

  constructor(status: number, message?: string) {
    super(message ?? `Feedback request failed (${status})`);
    this.name = "FeedbackError";
    this.status = status;
  }
}

// --- Pure validation ---

/**
 * Count the non-whitespace characters in a string, by Unicode code point so a
 * multi-byte emoji or astral character counts once (matching a Python backend's
 * `len()`), not as two UTF-16 units.
 */
export function countValidChars(s: string): number {
  let count = 0;
  for (const ch of s) {
    if (!/\s/u.test(ch)) count++;
  }
  return count;
}

/**
 * Whether the current selection is submittable. A thumb rating needs only a
 * rating (badges + comment optional); a bug report needs a description of at
 * least MIN_BUG_CHARS non-whitespace characters.
 */
export function canSubmit(
  rating: FeedbackRating | null,
  comment: string,
): boolean {
  if (!rating) return false;
  if (rating === "bug") return countValidChars(comment) >= MIN_BUG_CHARS;
  return true;
}

// --- Network wrapper ---

type FetchLike = typeof fetch;

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

/** POST /api/feedback — submit a rating or bug report for one analysis. */
export async function sendFeedback(
  token: string,
  payload: FeedbackPayload,
  fetchImpl: FetchLike = fetch,
): Promise<FeedbackResponse> {
  const res = await fetchImpl(`${API_BASE}/api/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new FeedbackError(res.status);
  return res.json();
}
