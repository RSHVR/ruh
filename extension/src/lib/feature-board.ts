/**
 * Feature-request board logic.
 *
 * Splits into two layers so the interesting behaviour is unit-testable
 * without a DOM or a live network:
 *   - Pure functions that model optimistic voting + list mutations.
 *   - Thin `fetch` wrappers that talk to the backend (dependency-injected
 *     fetch for testing; defaults to the global).
 *
 * API contract (all requests require `Authorization: Bearer <supabase JWT>`):
 *   GET  /api/features           → { features: Feature[] }
 *   POST /api/features           → Feature            (body: { title, description? })
 *   POST /api/features/{id}/vote → { voted, vote_count }
 * Error statuses: 401 unauthenticated, 429 rate/submission limit.
 */

export type FeatureStatus =
  | "open"
  | "planned"
  | "in_progress"
  | "shipped"
  | "declined"
  | string;

export interface Feature {
  id: string;
  title: string;
  description?: string;
  status: FeatureStatus;
  vote_count: number;
  voted_by_me: boolean;
  created_at: string;
}

export interface VoteResponse {
  voted: boolean;
  vote_count: number;
}

/** Error carrying the HTTP status so callers can special-case 429/401. */
export class FeatureBoardError extends Error {
  status: number;

  constructor(status: number, message?: string) {
    super(message ?? `Feature board request failed (${status})`);
    this.name = "FeatureBoardError";
    this.status = status;
  }
}

// --- Pure state helpers (optimistic voting) ---

/**
 * Flip a single feature's vote state optimistically: toggle `voted_by_me`
 * and nudge the count by ±1. Count is clamped at 0 so it can never go
 * negative if local and server state briefly disagree.
 */
export function applyOptimisticVote(feature: Feature): Feature {
  const voted = !feature.voted_by_me;
  return {
    ...feature,
    voted_by_me: voted,
    vote_count: Math.max(0, feature.vote_count + (voted ? 1 : -1)),
  };
}

/** Overwrite a feature's vote fields with the server's authoritative values. */
export function reconcileVote(feature: Feature, res: VoteResponse): Feature {
  return { ...feature, voted_by_me: res.voted, vote_count: res.vote_count };
}

/** Apply an optimistic vote toggle to the matching feature in a list. */
export function toggleVoteInList(features: Feature[], id: string): Feature[] {
  return features.map((f) => (f.id === id ? applyOptimisticVote(f) : f));
}

/** Reconcile the matching feature in a list with a server vote response. */
export function reconcileVoteInList(
  features: Feature[],
  id: string,
  res: VoteResponse,
): Feature[] {
  return features.map((f) => (f.id === id ? reconcileVote(f, res) : f));
}

/**
 * Replace the feature sharing `updated.id` with `updated`. Used to revert a
 * single feature after a failed vote without disturbing other in-flight
 * optimistic updates.
 */
export function replaceFeatureInList(
  features: Feature[],
  updated: Feature,
): Feature[] {
  return features.map((f) => (f.id === updated.id ? updated : f));
}

/** Put a newly-created feature at the top of the list. */
export function prependFeature(
  features: Feature[],
  feature: Feature,
): Feature[] {
  return [feature, ...features];
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

/** GET /api/features — returns the board, newest/most-voted as the server orders it. */
export async function fetchFeatures(
  token: string,
  fetchImpl: FetchLike = fetch,
): Promise<Feature[]> {
  const res = await fetchImpl(`${API_BASE}/api/features`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new FeatureBoardError(res.status);
  const data = await res.json();
  // Backend returns a bare array (List[FeatureResponse]); tolerate the
  // wrapped { features: [...] } shape too so neither side can silently
  // zero the board again.
  if (Array.isArray(data)) return data;
  return data.features ?? [];
}

/** POST /api/features/{id}/vote — toggle the caller's vote; returns authoritative state. */
export async function voteFeature(
  token: string,
  id: string,
  fetchImpl: FetchLike = fetch,
): Promise<VoteResponse> {
  const res = await fetchImpl(`${API_BASE}/api/features/${id}/vote`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new FeatureBoardError(res.status);
  return res.json();
}

/**
 * POST /api/features — submit a new request. `description` is omitted from the
 * body entirely when empty so the backend sees a clean `{ title }` payload.
 */
export async function submitFeature(
  token: string,
  title: string,
  description: string | undefined,
  fetchImpl: FetchLike = fetch,
): Promise<Feature> {
  const trimmedTitle = title.trim();
  const trimmedDesc = description?.trim();
  const body = trimmedDesc
    ? { title: trimmedTitle, description: trimmedDesc }
    : { title: trimmedTitle };

  const res = await fetchImpl(`${API_BASE}/api/features`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new FeatureBoardError(res.status);
  return res.json();
}
