<script lang="ts">
  /**
   * SidePanelContainer - Chrome Side Panel Orchestrator
   *
   * Manages the Chrome Side Panel lifecycle, state synchronization,
   * and event coordination. This container component handles:
   * - Auth gating (login required before viewing — gated beta)
   * - Credit-based access to detailed analysis
   * - Tab switching and URL navigation detection
   * - Analysis data loading from chrome.storage
   * - Empty states and error handling
   *
   * Rendering flow:
   *   loading → auth check →
   *     NOT logged in → LoginView
   *     logged in → auth header +
   *       no data → empty state
   *       loading → LoadingScreen
   *       error → error state
   *       complete →
   *         unlimited tier → AnalysisView
   *         non-unlimited AND NOT unlocked → ScoreSummaryView
   *         non-unlimited AND unlocked → AnalysisView
   *       (FeatureBoard pinned at the bottom in every authenticated state)
   */
  import { onMount, onDestroy } from 'svelte';
  import AnalysisView from './components/AnalysisView.svelte';
  import LoadingScreen from './components/LoadingScreen.svelte';
  import LoginView from './components/LoginView.svelte';
  import CreditBadge from './components/CreditBadge.svelte';
  import ScoreSummaryView from './components/ScoreSummaryView.svelte';
  import ConfirmDialog from './components/ConfirmDialog.svelte';
  import type { TabAnalysisState } from './lib/storage-sync';
  import { getTabStorageKey, getActiveTab } from './lib/storage-sync';
  import { isAmazonProductPage } from '@/lib/utils';
  import { initSupabase } from './lib/supabase';
  import { authStore } from './lib/auth-store.svelte';

  // Props: initialTabId is passed from sidepanel.ts (read from URL query params)
  let { initialTabId = null }: { initialTabId: number | null } = $props();

  let currentTabState: TabAnalysisState | null = $state(null);
  let currentTabId: number | null = $state(null);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);

  // Track whether current product is unlocked (client-side state)
  let analysisUnlocked = $state(false);
  // Set when an unlock was free because the analysis was inconclusive.
  let freeUnlockNote: string | null = $state(null);

  // Sign-out confirmation (the button sits one misclick from the panel close)
  let confirmingSignOut = $state(false);

  let storageListener: ((changes: any, area: string) => void) | null = null;
  let tabActivatedListener: ((activeInfo: chrome.tabs.TabActiveInfo) => void) | null = null;
  let tabUpdatedListener: ((tabId: number, changeInfo: chrome.tabs.TabChangeInfo, tab: chrome.tabs.Tab) => void) | null = null;

  // Determine if user should see full analysis (authenticated users only —
  // login is required to reach this point in the gated beta).
  let showFullAnalysis = $derived(
    authStore.userTier === 'unlimited' || analysisUnlocked,
  );

  onMount(async () => {
    console.log('[SidePanelContainer] Initializing with initialTabId:', initialTabId);

    // Initialize Supabase + auth state
    await initSupabase();
    await authStore.initialize();

    // Use initialTabId from URL if available, otherwise query active tab
    if (initialTabId) {
      await loadTabState(initialTabId);
    } else {
      await loadActiveTabState();
    }

    // Listen for storage changes (any tab's analysis updates)
    storageListener = (changes, area) => {
      if (area !== 'local' || !currentTabId) return;

      const key = getTabStorageKey(currentTabId);
      if (changes[key]) {
        console.log('[SidePanelContainer] Storage updated for current tab:', currentTabId);
        currentTabState = changes[key].newValue;
        loading = false;
        // Check unlock status from response data
        checkUnlockFromResponse();
      }
    };
    chrome.storage.onChanged.addListener(storageListener);

    // Listen for tab activation (user switches tabs)
    tabActivatedListener = async (activeInfo) => {
      console.log('[SidePanelContainer] Tab activated:', activeInfo.tabId);
      await loadTabState(activeInfo.tabId);
    };
    chrome.tabs.onActivated.addListener(tabActivatedListener);

    // Listen to tab URL changes
    tabUpdatedListener = async (tabId, changeInfo, tab) => {
      if (tabId !== currentTabId || !changeInfo.url) return;

      console.log('[SidePanelContainer] Tab URL changed:', changeInfo.url);

      const isProductPage = isAmazonProductPage(changeInfo.url);

      if (!isProductPage) {
        console.log('[SidePanelContainer] Navigated away from product page');
        currentTabState = null;
        analysisUnlocked = false;
        loading = false;
      } else {
        console.log('[SidePanelContainer] Navigated to new product page');
        analysisUnlocked = false;
        await loadTabState(tabId);
      }
    };
    chrome.tabs.onUpdated.addListener(tabUpdatedListener);
  });

  onDestroy(() => {
    if (storageListener) {
      chrome.storage.onChanged.removeListener(storageListener);
    }
    if (tabActivatedListener) {
      chrome.tabs.onActivated.removeListener(tabActivatedListener);
    }
    if (tabUpdatedListener) {
      chrome.tabs.onUpdated.removeListener(tabUpdatedListener);
    }
  });

  /**
   * Load state for the currently active tab
   */
  async function loadActiveTabState() {
    const tab = await getActiveTab();
    if (!tab?.id) {
      console.warn('[SidePanelContainer] No active tab found');
      loading = false;
      return;
    }

    await loadTabState(tab.id);
  }

  /**
   * Load analysis state for a specific tab
   */
  async function loadTabState(tabId: number) {
    currentTabId = tabId;
    const key = getTabStorageKey(tabId);

    try {
      const result = await chrome.storage.local.get(key);
      const state = result[key];

      if (!state) {
        console.log('[SidePanelContainer] No analysis data for tab:', tabId);
        currentTabState = null;
        loading = false;
        return;
      }

      console.log('[SidePanelContainer] Loaded state for tab:', tabId, state.status);
      currentTabState = state;
      loading = false;

      // Check unlock status from response data
      checkUnlockFromResponse();
    } catch (err) {
      console.error('[SidePanelContainer] Error loading tab state:', err);
      error = 'Failed to load analysis data';
      loading = false;
    }
  }

  /**
   * Check if the analysis response indicates this product is unlocked.
   * The stored blob reflects unlock state AT ANALYSIS TIME — if the user
   * unlocked afterwards, it's stale, so fall through to an authoritative
   * server check (unlocks are permanent server-side; the report must never
   * re-present a "1 credit" button for something already paid for).
   */
  function checkUnlockFromResponse() {
    if (currentTabState?.status === 'complete' && currentTabState.data) {
      const data = currentTabState.data;
      if (data.analysis_unlocked) {
        analysisUnlocked = true;
      } else {
        void verifyUnlockWithServer();
      }
    }
  }

  /** Persist the unlocked flag into the stored analysis so panel reopens
   *  land directly on the full report. */
  function persistUnlockedFlag() {
    if (!currentTabState?.data || currentTabId == null) return;
    currentTabState.data.analysis_unlocked = true;
    const snapshot = JSON.parse(JSON.stringify(currentTabState));
    chrome.storage.local
      .set({ [getTabStorageKey(currentTabId)]: snapshot })
      .catch(() => {});
  }

  /** Ask the server whether this product was already unlocked (covers stale
   *  stored analyses and unlocks made on other devices). */
  async function verifyUnlockWithServer() {
    const data = currentTabState?.data;
    if (!data?.url_hash || analysisUnlocked) return;

    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
    const token = authStore.getAccessToken();
    if (!token || !API_BASE_URL) return;

    try {
      const resp = await fetch(
        `${API_BASE_URL}/api/credits/check/${data.url_hash}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (resp.ok) {
        const info = await resp.json();
        if (info.unlocked) {
          analysisUnlocked = true;
          persistUnlockedFlag();
        }
      }
    } catch {
      // Offline/transient — teaser stays; the unlock RPC is idempotent, so a
      // re-click can never double-charge.
    }
  }

  /**
   * Retry a failed analysis. The analysis runs in the product tab's content
   * script, so retrying means asking THAT script to re-run — merely
   * re-reading the stored error (the old behavior) retried nothing.
   * Falls back to reloading the product tab if the content script is
   * unreachable (e.g. orphaned after an extension update).
   */
  async function retryAnalysis() {
    if (currentTabId == null) return;

    // Optimistic: show the loading screen while the retry spins up.
    if (currentTabState) {
      currentTabState = { ...currentTabState, status: 'loading', error: null };
    }

    try {
      await chrome.tabs.sendMessage(currentTabId, { type: 'RETRY_ANALYSIS' });
    } catch {
      // Content script unreachable — a tab reload re-injects it and
      // re-triggers the analysis on load.
      try {
        await chrome.tabs.reload(currentTabId);
      } catch {
        error = 'Could not retry — refresh the product page.';
      }
    }
  }

  /**
   * Handle unlock button click — deduct credit via API
   */
  async function handleUnlock() {
    if (!currentTabState?.data?.url_hash) return;

    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
    const token = authStore.getAccessToken();
    if (!token || !API_BASE_URL) return;

    try {
      const resp = await fetch(`${API_BASE_URL}/api/credits/deduct`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ url_hash: currentTabState.data.url_hash }),
      });

      if (resp.ok) {
        const result = await resp.json();
        analysisUnlocked = true;
        // Inconclusive analyses unlock free — tell the user they kept their credit.
        if (result.charged === false) {
          freeUnlockNote =
            'No charge — this analysis came back inconclusive, so your credit was not used.';
        }
        persistUnlockedFlag();
        await authStore.refreshCredits();
      } else if (resp.status === 402) {
        error = 'No credits remaining. Please upgrade your plan.';
      } else {
        error = 'Failed to unlock analysis';
      }
    } catch (err) {
      console.error('[SidePanelContainer] Unlock failed:', err);
      error = 'Failed to unlock analysis';
    }
  }
</script>

<div class="side-panel-container">
  {#if loading || authStore.loading}
    <div class="empty-state">
      <div class="spinner"></div>
      <p>Loading...</p>
    </div>
  {:else if !authStore.isAuthenticated}
    <LoginView />
  {:else}
    <!-- Auth header with credit badge and sign out -->
    <div class="auth-header">
      <img src="/ruh-wordmark.svg" alt="ruh" class="header-wordmark" />
      <CreditBadge />
      <button class="signout-btn" onclick={() => (confirmingSignOut = true)}>
        Sign Out
      </button>
    </div>

    {#if error}
      <div class="empty-state">
        <p class="error-text">{error}</p>
        <button onclick={() => { error = null; loadActiveTabState(); }} class="retry-button">
          Retry
        </button>
      </div>
    {:else if !currentTabState}
      <div class="empty-state">
        <img src="/icon-128.png" alt="Ruh" class="empty-icon" />
        <h2>No Analysis Yet</h2>
        <p>Navigate to an Amazon product page to analyze its safety.</p>
      </div>
    {:else if currentTabState.status === 'loading'}
      <LoadingScreen currentStep="" />
    {:else if currentTabState.status === 'error'}
      <div class="empty-state">
        <p class="error-text">{currentTabState.error || 'Analysis failed'}</p>
        <button onclick={retryAnalysis} class="retry-button">
          Retry
        </button>
      </div>
    {:else if currentTabState.status === 'complete' && currentTabState.data}
      {#if showFullAnalysis}
        {#if freeUnlockNote}
          <p class="free-unlock-note">{freeUnlockNote}</p>
        {/if}
        <AnalysisView
          analysis={currentTabState.data}
          loading={false}
          error={null}
          visible={true}
        />
      {:else}
        <ScoreSummaryView
          analysis={currentTabState.data}
          onUnlock={handleUnlock}
        />
      {/if}
    {:else}
      <div class="empty-state">
        <p>Unknown state</p>
      </div>
    {/if}

  {/if}

  {#if confirmingSignOut}
    <ConfirmDialog
      title="Sign out of ruh?"
      body="You'll need an email code to sign back in."
      confirmLabel="Sign out"
      onConfirm={() => {
        confirmingSignOut = false;
        void authStore.signOut();
      }}
      onCancel={() => (confirmingSignOut = false)}
    />
  {/if}
</div>

<style>
  .free-unlock-note {
    margin: 10px 16px 0;
    padding: 8px 12px;
    border-radius: 10px;
    background: #e3f0e6;
    border: 1px solid rgba(47, 107, 63, 0.25);
    font-family: 'Poppins', sans-serif;
    font-size: 12px;
    line-height: 1.45;
    color: #2f6b3f;
  }

  .side-panel-container {
    width: 100%;
    height: 100vh;
    overflow-y: auto;
    overflow-x: hidden;
    background: var(--color-bg-primary, #fffbf5);
    display: flex;
    flex-direction: column;
  }

  .header-wordmark {
    height: 20px;
    width: auto;
    flex-shrink: 0;
    margin-right: 10px;
  }

  .auth-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    border-bottom: 1px solid #e8e0d4;
    background: var(--color-bg-primary, #fffbf5);
    position: sticky;
    top: 0;
    z-index: 10;
  }

  .signout-btn {
    background: none;
    border: none;
    font-family: 'Poppins', sans-serif;
    font-size: 12px;
    color: var(--color-text-secondary, #6B6560);
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 4px;
    transition: all 150ms ease;
  }

  .signout-btn:hover {
    background: #f0ebe2;
    color: var(--color-text-primary, #3A3633);
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 24px;
    text-align: center;
    min-height: 400px;
  }

  .empty-icon {
    width: 80px;
    height: 80px;
    margin-bottom: 24px;
    opacity: 0.6;
  }

  .empty-state h2 {
    font-family: 'Instrument Sans', sans-serif;
    font-size: 24px;
    font-weight: 600;
    color: var(--color-text-primary, #3A3633);
    margin: 0 0 12px 0;
  }

  .empty-state p {
    font-family: 'Poppins', sans-serif;
    font-size: 14px;
    color: var(--color-text-secondary, #6B6560);
    margin: 0 0 24px 0;
    max-width: 280px;
  }

  .error-text {
    color: var(--color-rust, #C46E5A);
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid #E8DCC8;
    border-top-color: #6B6560;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 16px;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .retry-button {
    padding: 10px 20px;
    background: var(--color-sage, #94A37C);
    color: white;
    border: none;
    border-radius: 6px;
    font-family: 'Poppins', sans-serif;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 150ms ease;
  }

  .retry-button:hover {
    background: #7d8a68;
    transform: translateY(-1px);
  }

  .retry-button:active {
    transform: translateY(0);
  }
</style>
