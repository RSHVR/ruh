/**
 * Reactive auth store using Svelte 5 runes.
 *
 * Manages Supabase Auth session, user profile, and credit balance.
 * Used by the side panel UI to gate access to detailed analysis.
 */

import type { Session, User } from '@supabase/supabase-js';
import { getSupabaseClient } from './supabase';

// --- Reactive state ---
let session = $state<Session | null>(null);
let user = $state<User | null>(null);
let loading = $state(true);
let creditBalance = $state<number | null>(null);
let userTier = $state<string>('free');

// --- Derived ---
const isAuthenticated = $derived(!!session);

// --- API helpers ---
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = session?.access_token;
  if (!token) throw new Error('Not authenticated');

  return fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
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
        userTier = 'free';
      }
    });

    if (session) {
      await refreshCredits();
    }
  } catch (err) {
    console.error('[Ruh] Auth init failed:', err);
  } finally {
    loading = false;
  }
}

async function signInWithGoogle(): Promise<{ success: boolean; error?: string }> {
  const client = getSupabaseClient();
  if (!client) return { success: false, error: 'Supabase not configured' };

  try {
    const { data, error } = await client.auth.signInWithOAuth({
      provider: 'google',
      options: {
        skipBrowserRedirect: true,
        redirectTo: `chrome-extension://${chrome.runtime.id}/auth-callback.html`,
      },
    });

    if (error) return { success: false, error: error.message };
    if (!data.url) return { success: false, error: 'No auth URL returned' };

    // Open OAuth popup
    chrome.windows.create({
      url: data.url,
      type: 'popup',
      width: 500,
      height: 650,
    });

    return { success: true };
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : 'OAuth failed' };
  }
}

async function signInWithEmail(
  email: string,
  password: string,
): Promise<{ success: boolean; error?: string }> {
  const client = getSupabaseClient();
  if (!client) return { success: false, error: 'Supabase not configured' };

  const { error } = await client.auth.signInWithPassword({ email, password });
  if (error) return { success: false, error: error.message };

  return { success: true };
}

async function signUp(
  email: string,
  password: string,
): Promise<{ success: boolean; error?: string }> {
  const client = getSupabaseClient();
  if (!client) return { success: false, error: 'Supabase not configured' };

  const { error } = await client.auth.signUp({ email, password });
  if (error) return { success: false, error: error.message };

  return { success: true };
}

async function signOut(): Promise<void> {
  const client = getSupabaseClient();
  if (!client) return;

  await client.auth.signOut();
  session = null;
  user = null;
  creditBalance = null;
  userTier = 'free';
}

async function refreshCredits(): Promise<void> {
  if (!session) return;

  try {
    const resp = await apiFetch('/api/credits/me');
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
  get session() { return session; },
  get user() { return user; },
  get loading() { return loading; },
  get creditBalance() { return creditBalance; },
  get userTier() { return userTier; },
  get isAuthenticated() { return isAuthenticated; },

  initialize,
  signInWithGoogle,
  signInWithEmail,
  signUp,
  signOut,
  refreshCredits,
  getAccessToken,
};
