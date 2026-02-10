/**
 * Supabase client singleton for the Chrome extension.
 *
 * Uses chrome.storage.local as the auth storage backend so sessions
 * persist across service worker restarts and extension contexts.
 */

import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || '';
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

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
      const result = await chrome.storage.local.get('supabase_auth');
      if (result.supabase_auth && typeof result.supabase_auth === 'object') {
        for (const [key, value] of Object.entries(result.supabase_auth)) {
          if (typeof value === 'string') {
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
        flowType: 'pkce',
      },
    });
  }
  return _client;
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
