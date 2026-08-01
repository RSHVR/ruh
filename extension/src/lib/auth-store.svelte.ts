/**
 * Reactive auth store using Svelte 5 runes.
 *
 * Manages Supabase Auth session, user profile, and credit balance.
 * Used by the side panel UI to gate access to detailed analysis.
 */

import type { Session, User } from "@supabase/supabase-js";
import { getSupabaseClient } from "./supabase";

// --- Reactive state ---
let session = $state<Session | null>(null);
let user = $state<User | null>(null);
let loading = $state(true);
let creditBalance = $state<number | null>(null);
let userTier = $state<string>("free");

// --- Derived ---
const isAuthenticated = $derived(!!session);

// --- API helpers ---
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

async function apiFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const token = session?.access_token;
  if (!token) throw new Error("Not authenticated");

  return fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
}

// --- Public API ---

async function initialize(): Promise<void> {
  const client = getSupabaseClient();
  if (!client) {
    loading = false;
    return;
  }

  try {
    const { data } = await client.auth.getSession();
    session = data.session;
    user = data.session?.user ?? null;

    // Listen for auth changes (token refresh, sign out, etc.)
    client.auth.onAuthStateChange((_event, newSession) => {
      session = newSession;
      user = newSession?.user ?? null;

      if (newSession) {
        refreshCredits();
      } else {
        creditBalance = null;
        userTier = "free";
      }
    });

    // Cross-context sign-out/sign-in propagation lives at the client layer
    // (supabase.ts installCrossContextAuthSync): it mirrors foreign auth
    // changes via signOut(local)/setSession, which emit auth events that the
    // onAuthStateChange handler above already turns into UI state. A passive
    // storage listener here previously raced the sign-in flow (stale
    // getSession resolving after SIGNED_IN clobbered the fresh session) —
    // do not re-add one.

    if (session) {
      // Fire-and-forget: the panel must not block on a network round-trip —
      // getSession above is local, so gating `loading` on the credits fetch
      // made "Confirming you're signed in" hang for the API's response time.
      // CreditBadge renders a placeholder until the balance arrives.
      void refreshCredits();
    }
  } catch (err) {
    console.error("[Ruh] Auth init failed:", err);
  } finally {
    loading = false;
  }
}

async function signInWithGoogle(): Promise<{
  success: boolean;
  error?: string;
}> {
  const client = getSupabaseClient();
  if (!client) return { success: false, error: "Supabase not configured" };

  try {
    const { data, error } = await client.auth.signInWithOAuth({
      provider: "google",
      options: {
        skipBrowserRedirect: true,
        redirectTo: `chrome-extension://${chrome.runtime.id}/auth-callback.html`,
      },
    });

    if (error) return { success: false, error: error.message };
    if (!data.url) return { success: false, error: "No auth URL returned" };

    // Open OAuth popup
    chrome.windows.create({
      url: data.url,
      type: "popup",
      width: 500,
      height: 650,
    });

    return { success: true };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : "OAuth failed",
    };
  }
}

async function signInWithEmail(
  email: string,
  password: string,
): Promise<{ success: boolean; error?: string }> {
  const client = getSupabaseClient();
  if (!client) return { success: false, error: "Supabase not configured" };

  const { error } = await client.auth.signInWithPassword({ email, password });
  if (error) return { success: false, error: error.message };

  return { success: true };
}

async function signUp(
  email: string,
  password: string,
): Promise<{ success: boolean; error?: string }> {
  const client = getSupabaseClient();
  if (!client) return { success: false, error: "Supabase not configured" };

  const { error } = await client.auth.signUp({ email, password });
  if (error) return { success: false, error: error.message };

  return { success: true };
}

async function sendEmailCode(
  email: string,
): Promise<{ success: boolean; error?: string }> {
  const client = getSupabaseClient();
  if (!client) return { success: false, error: "Supabase not configured" };

  // Passwordless: emails a 6-digit code (magic-link template must include {{ .Token }}).
  const { error } = await client.auth.signInWithOtp({
    email,
    options: { shouldCreateUser: true },
  });
  if (error) return { success: false, error: error.message };

  return { success: true };
}

async function verifyEmailCode(
  email: string,
  code: string,
  region?: string,
): Promise<{ success: boolean; error?: string }> {
  const client = getSupabaseClient();
  if (!client) return { success: false, error: "Supabase not configured" };

  const { error } = await client.auth.verifyOtp({
    email,
    token: code,
    type: "email",
  });
  if (error) return { success: false, error: error.message };

  // Record one-time Terms/disclaimer acceptance (and the signup region) in the
  // user's metadata. Fire-and-forget: sign-in must not block on the write.
  void recordSignupMetadata(region);

  return { success: true };
}

/**
 * Persist signup-time metadata in Supabase user_metadata in a single
 * updateUser call: `tos_accepted_at` the first time it's seen, and `region`
 * the first time it's provided. Both writes are idempotent (existing values are
 * left untouched), so re-sign-ins are no-ops. Acceptance/region are gated in
 * the signup UI; this just records them.
 */
async function recordSignupMetadata(region?: string): Promise<void> {
  const client = getSupabaseClient();
  if (!client) return;

  try {
    const { data } = await client.auth.getUser();
    if (!data.user) return;

    const meta = data.user.user_metadata ?? {};
    const patch: Record<string, unknown> = {};
    if (!meta.tos_accepted_at) patch.tos_accepted_at = new Date().toISOString();
    if (region && !meta.region) patch.region = region;

    if (Object.keys(patch).length === 0) return;
    await client.auth.updateUser({ data: patch });
  } catch {
    // Non-fatal — the values were captured in the UI; a later sign-in retries.
  }
}

async function signOut(): Promise<void> {
  const client = getSupabaseClient();
  if (!client) return;

  try {
    // Global: revokes the refresh token server-side and clears storage,
    // which the cross-context sync propagates to every other panel.
    await client.auth.signOut();
  } catch {
    // Network revoke failed — still sign out locally so the UI never
    // stays "signed in" after the user asked to leave.
    await client.auth.signOut({ scope: "local" }).catch(() => {});
  }
  session = null;
  user = null;
  creditBalance = null;
  userTier = "free";
}

async function refreshCredits(): Promise<void> {
  if (!session) return;

  try {
    const resp = await apiFetch("/api/credits/me");
    if (resp.ok) {
      const data = await resp.json();
      creditBalance = data.credits_remaining;
      userTier = data.tier;
    }
  } catch {
    // Non-fatal — UI shows stale balance
  }
}

function getAccessToken(): string | null {
  return session?.access_token ?? null;
}

// --- Exports ---
export const authStore = {
  get session() {
    return session;
  },
  get user() {
    return user;
  },
  get loading() {
    return loading;
  },
  get creditBalance() {
    return creditBalance;
  },
  get userTier() {
    return userTier;
  },
  get isAuthenticated() {
    return isAuthenticated;
  },

  initialize,
  signInWithGoogle,
  signInWithEmail,
  signUp,
  sendEmailCode,
  verifyEmailCode,
  signOut,
  refreshCredits,
  getAccessToken,
};
