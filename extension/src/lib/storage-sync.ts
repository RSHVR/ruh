import type { AnalysisResponse } from '@/types';

export type AnalysisStatus = 'idle' | 'loading' | 'complete' | 'error';

export interface TabAnalysisState {
  tabId: number;
  productUrl: string;
  status: AnalysisStatus;
  data: AnalysisResponse | null;
  error: string | null;
  timestamp: number;
  harmScore: number | null;
}

/**
 * Generate storage key for a specific tab's analysis state
 */
export function getTabStorageKey(tabId: number): string {
  return `analysis_${tabId}`;
}

/**
 * Store analysis state for a specific tab
 */
export async function setTabAnalysis(
  tabId: number,
  state: Partial<TabAnalysisState>
): Promise<void> {
  const key = getTabStorageKey(tabId);

  // Get existing state if any
  const existing = await getTabAnalysis(tabId);

  const newState: TabAnalysisState = {
    tabId,
    productUrl: state.productUrl ?? existing?.productUrl ?? '',
    status: state.status ?? existing?.status ?? 'idle',
    data: state.data ?? existing?.data ?? null,
    error: state.error ?? existing?.error ?? null,
    timestamp: state.timestamp ?? existing?.timestamp ?? Date.now(),
    harmScore: state.harmScore ?? existing?.harmScore ?? null
  };

  await chrome.storage.local.set({ [key]: newState });
}

/**
 * Get analysis state for a specific tab
 */
export async function getTabAnalysis(
  tabId: number
): Promise<TabAnalysisState | null> {
  const key = getTabStorageKey(tabId);
  const result = await chrome.storage.local.get(key);
  return result[key] ?? null;
}

/**
 * Remove analysis state for a specific tab
 */
export async function removeTabAnalysis(tabId: number): Promise<void> {
  const key = getTabStorageKey(tabId);
  await chrome.storage.local.remove(key);
}

/**
 * Get currently active tab
 */
export async function getActiveTab(): Promise<chrome.tabs.Tab | null> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab ?? null;
}

/**
 * Check if analysis data is stale (older than 30 days)
 */
export function isStaleAnalysis(timestamp: number): boolean {
  const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000; // 30 days
  const age = Date.now() - timestamp;
  return age > MAX_AGE_MS;
}
