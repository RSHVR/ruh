/**
 * Supabase client singleton for the Chrome extension.
 *
 * Uses chrome.storage.local as the auth storage backend so sessions
 * persist across service worker restarts and extension contexts.
 */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || "";
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || "";

/**
 * Custom storage adapter that uses chrome.storage.local.
 * Supabase Auth expects a synchronous localStorage-like API,
 * but chrome.storage is async. We bridge this with a sync in-memory
 * cache backed by chrome.storage.local for persistence.
 */
class ChromeStorageAdapter {
  private cache: Map<string, string> = new Map();
  private initialized = false;

  async init(): Promise<void> {
    if (this.initialized) return;
    try {
      const result = await chrome.storage.local.get("supabase_auth");
      if (result.supabase_auth && typeof result.supabase_auth === "object") {
        for (const [key, value] of Object.entries(result.supabase_auth)) {
          if (typeof value === "string") {
            this.cache.set(key, value);
          }
        }
      }
      this.initialized = true;
    } catch {
      this.initialized = true;
    }
  }

  getItem(key: string): string | null {
    return this.cache.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.cache.set(key, value);
    this._persist();
  }

  removeItem(key: string): void {
    this.cache.delete(key);
    this._persist();
  }

  private _persist(): void {
    const obj: Record<string, string> = {};
    for (const [key, value] of this.cache) {
      obj[key] = value;
    }
    chrome.storage.local.set({ supabase_auth: obj }).catch(() => {});
  }

  /** Replace the in-memory cache from another context's persisted state
   *  WITHOUT re-persisting (avoids storage-change echo loops). */
  replaceAll(obj: Record<string, unknown>): void {
    this.cache.clear();
    for (const [key, value] of Object.entries(obj)) {
      if (typeof value === "string") {
        this.cache.set(key, value);
      }
    }
  }
}

const storageAdapter = new ChromeStorageAdapter();

let _client: SupabaseClient | null = null;

/**
 * Get the Supabase client. Must call initSupabase() first in the
 * background worker to hydrate the storage adapter.
 */
export function getSupabaseClient(): SupabaseClient | null {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) return null;

  if (!_client) {
    _client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      auth: {
        storage: storageAdapter,
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: false,
        flowType: "pkce",
      },
    });
    installCrossContextAuthSync();
  }
  return _client;
}

/**
 * Every side-panel instance (one per tab) and the background worker each hold
 * their own client + in-memory storage cache, all persisting to the SAME
 * chrome.storage.local key. Without this listener, signing out in one panel
 * leaves every other context signed in until its access token expires.
 * chrome.storage does not emit the localStorage events supabase-js normally
 * relies on for cross-tab sync, so we bridge it ourselves.
 */
let _syncInstalled = false;
function installCrossContextAuthSync(): void {
  if (
    _syncInstalled ||
    typeof chrome === "undefined" ||
    !chrome.storage?.onChanged
  ) {
    return;
  }
  _syncInstalled = true;

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local" || !changes.supabase_auth) return;

    void (async () => {
      const newVal = (changes.supabase_auth.newValue ?? {}) as Record<
        string,
        string
      >;
      storageAdapter.replaceAll(newVal);

      const client = _client;
      if (!client) return;

      const tokenKey = Object.keys(newVal).find((k) =>
        k.includes("auth-token"),
      );
      const { data } = await client.auth.getSession();
      const hasLocalSession = !!data.session;

      if (!tokenKey && hasLocalSession) {
        // Signed out in another context — mirror locally (no extra server call).
        await client.auth.signOut({ scope: "local" }).catch(() => {});
      } else if (tokenKey && !hasLocalSession) {
        // Signed in in another context — adopt that session here.
        try {
          const parsed = JSON.parse(newVal[tokenKey]) as {
            access_token?: string;
            refresh_token?: string;
          };
          if (parsed.access_token && parsed.refresh_token) {
            await client.auth.setSession({
              access_token: parsed.access_token,
              refresh_token: parsed.refresh_token,
            });
          }
        } catch {
          // Unparseable session blob — leave this context signed out.
        }
      }
    })();
  });
}

/**
 * Initialize the Supabase client by hydrating the storage adapter
 * from chrome.storage.local. Call this once in the background worker.
 */
export async function initSupabase(): Promise<SupabaseClient | null> {
  await storageAdapter.init();
  return getSupabaseClient();
}

export { storageAdapter };
