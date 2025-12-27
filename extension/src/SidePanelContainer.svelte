<script lang="ts">
  /**
   * SidePanelContainer - Chrome Side Panel Orchestrator
   *
   * Manages the Chrome Side Panel lifecycle, state synchronization,
   * and event coordination. This container component handles:
   * - Side panel open/close state tracking
   * - Tab switching and URL navigation detection
   * - Analysis data loading from chrome.storage
   * - Empty states and error handling
   *
   * Renders AnalysisView component when data is available.
   */
  import { onMount, onDestroy } from 'svelte';
  import AnalysisView from './components/AnalysisView.svelte';
  import LoadingScreen from './components/LoadingScreen.svelte';
  import type { TabAnalysisState } from './lib/storage-sync';
  import { getTabStorageKey, getActiveTab } from './lib/storage-sync';
  import { isAmazonProductPage } from '@/lib/utils';

  let currentTabState: TabAnalysisState | null = $state(null);
  let currentTabId: number | null = $state(null);
  let loading: boolean = $state(true);
  let error: string | null = $state(null);

  let storageListener: ((changes: any, area: string) => void) | null = null;
  let tabActivatedListener: ((activeInfo: chrome.tabs.TabActiveInfo) => void) | null = null;
  let tabUpdatedListener: ((tabId: number, changeInfo: chrome.tabs.TabChangeInfo, tab: chrome.tabs.Tab) => void) | null = null;

  onMount(async () => {
    console.log('[SidePanelContainer] Initializing side panel');

    // Load initial state for active tab
    await loadActiveTabState();

    // Notify background that side panel opened
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tabs[0]?.id) {
      chrome.runtime.sendMessage({
        type: 'SIDE_PANEL_OPENED',
        tabId: tabs[0].id
      });
    }

    // Listen for storage changes (any tab's analysis updates)
    storageListener = (changes, area) => {
      if (area !== 'local' || !currentTabId) return;

      const key = getTabStorageKey(currentTabId);
      if (changes[key]) {
        console.log('[SidePanelContainer] Storage updated for current tab:', currentTabId);
        currentTabState = changes[key].newValue;
        loading = false;
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
        loading = false;
      } else {
        console.log('[SidePanelContainer] Navigated to new product page');
        await loadTabState(tabId);
      }
    };
    chrome.tabs.onUpdated.addListener(tabUpdatedListener);
  });

  onDestroy(() => {
    // Notify background that side panel closed
    if (currentTabId) {
      chrome.runtime.sendMessage({
        type: 'SIDE_PANEL_CLOSED',
        tabId: currentTabId
      });
    }

    // Clean up listeners
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
    } catch (err) {
      console.error('[SidePanelContainer] Error loading tab state:', err);
      error = 'Failed to load analysis data';
      loading = false;
    }
  }
</script>

<div class="side-panel-container">
  {#if loading}
    <div class="empty-state">
      <div class="spinner"></div>
      <p>Loading...</p>
    </div>
  {:else if error}
    <div class="empty-state">
      <p class="error-text">{error}</p>
      <button onclick={() => loadActiveTabState()} class="retry-button">
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
      <button onclick={() => loadActiveTabState()} class="retry-button">
        Retry
      </button>
    </div>
  {:else if currentTabState.status === 'complete' && currentTabState.data}
    <AnalysisView
      analysis={currentTabState.data}
      loading={false}
      error={null}
      visible={true}
    />
  {:else}
    <div class="empty-state">
      <p>Unknown state</p>
    </div>
  {/if}
</div>

<style>
  .side-panel-container {
    width: 100%;
    height: 100vh;
    overflow-y: auto;
    background: var(--color-bg-primary, #fffbf5);
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
    font-family: 'Cormorant Infant', serif;
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
