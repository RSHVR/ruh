console.log('[Ruh] Background service worker initialized');

// Disable automatic side panel open on action click
// This allows our onClicked handler to run and set the tabId query param
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: false })
  .then(() => console.log('[Ruh] setPanelBehavior set to false'))
  .catch((err) => console.error('[Ruh] setPanelBehavior failed:', err));

// ============================================
// SIDE PANEL STATE DETECTION using getContexts()
// ============================================

// Track which tabs have open side panels (for polling)
const tabsWithOpenSidePanel = new Set<number>();
let pollingInterval: ReturnType<typeof setInterval> | null = null;

/**
 * Check if side panel is open for a specific tab using getContexts API.
 * Uses URL query param workaround since getContexts returns tabId: -1 for side panels.
 */
async function isSidePanelOpenForTab(tabId: number): Promise<boolean> {
  try {
    const contexts = await chrome.runtime.getContexts({
      contextTypes: ['SIDE_PANEL']
    });

    return contexts.some((ctx) => {
      if (!ctx.documentUrl) return false;
      try {
        const url = new URL(ctx.documentUrl);
        return url.searchParams.get('tabId') === String(tabId);
      } catch {
        return false;
      }
    });
  } catch (err) {
    console.error('[Ruh] Error checking side panel state:', err);
    return false;
  }
}

/**
 * Start polling to detect side panel close.
 * Chrome has no onSidePanelClosed event, so we poll getContexts().
 */
function startPolling() {
  if (pollingInterval) return;

  pollingInterval = setInterval(async () => {
    if (tabsWithOpenSidePanel.size === 0) {
      stopPolling();
      return;
    }

    try {
      const contexts = await chrome.runtime.getContexts({
        contextTypes: ['SIDE_PANEL']
      });

      // Build set of tabs that currently have side panels open
      const currentlyOpen = new Set<number>();
      for (const ctx of contexts) {
        if (ctx.documentUrl) {
          try {
            const url = new URL(ctx.documentUrl);
            const tabIdParam = url.searchParams.get('tabId');
            if (tabIdParam) currentlyOpen.add(Number(tabIdParam));
          } catch {}
        }
      }

      // Find tabs whose side panels have closed
      for (const tabId of tabsWithOpenSidePanel) {
        if (!currentlyOpen.has(tabId)) {
          console.log('[Ruh] Side panel closed for tab:', tabId);
          tabsWithOpenSidePanel.delete(tabId);

          // Notify content script
          chrome.tabs.sendMessage(tabId, {
            type: 'SIDE_PANEL_STATE_CHANGED',
            isOpen: false
          }).catch(() => {
            // Content script may not be available
          });
        }
      }
    } catch (err) {
      console.error('[Ruh] Polling error:', err);
    }
  }, 1000); // Poll every 1 second
}

function stopPolling() {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
}

// ============================================
// EXTENSION LIFECYCLE
// ============================================

// Listen for extension installation
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('[Ruh] Extension installed');

    // Generate and store user UUID
    const userId = crypto.randomUUID();
    chrome.storage.local.set({ userId }, () => {
      console.log('[Ruh] User ID generated:', userId);
    });

    // Set default settings
    chrome.storage.local.set({
      allergenProfile: [],
      sensitivityLevel: 'moderate',
      notificationsEnabled: true
    });
  } else if (details.reason === 'update') {
    console.log('[Ruh] Extension updated to version', chrome.runtime.getManifest().version);
  }
});

// Handle messages from content scripts and side panel
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[Ruh] Message received:', message);

  // Query: Is side panel open for a specific tab?
  if (message.type === 'IS_SIDE_PANEL_OPEN') {
    const tabId = message.tabId || sender.tab?.id;
    if (!tabId) {
      sendResponse({ isOpen: false });
      return true;
    }

    isSidePanelOpenForTab(tabId).then((isOpen) => {
      sendResponse({ isOpen });
    });
    return true; // Keep channel open for async response
  }

  if (message.type === 'GET_USER_ID') {
    chrome.storage.local.get(['userId'], (result) => {
      sendResponse({ userId: result.userId });
    });
    return true; // Keep channel open for async response
  }

  if (message.type === 'TRACK_ANALYSIS') {
    // Track that a product was analyzed (for metrics)
    console.log('[Ruh] Product analyzed:', message.productUrl);
    sendResponse({ success: true });
  }

  if (message.type === 'TRACK_CLICK') {
    // Track alternative product clicks
    console.log('[Ruh] Alternative clicked:', message.alternativeUrl);
    sendResponse({ success: true });
  }

  if (message.type === 'ANALYSIS_COMPLETE') {
    // Content script has completed analysis - store in chrome.storage
    const tabId = sender.tab?.id;
    if (!tabId) {
      console.warn('[Ruh] No tab ID in ANALYSIS_COMPLETE message');
      return;
    }

    console.log('[Ruh] Storing analysis for tab:', tabId);
    const harmScore = message.data?.analysis?.overall_score
      ? 100 - message.data.analysis.overall_score
      : null;

    chrome.storage.local.set({
      [`analysis_${tabId}`]: {
        tabId,
        productUrl: message.productUrl,
        status: 'complete',
        data: message.data,
        error: null,
        timestamp: Date.now(),
        harmScore
      }
    });

    sendResponse({ success: true });
  }

  if (message.type === 'ANALYSIS_ERROR') {
    // Content script encountered an error
    const tabId = sender.tab?.id;
    if (!tabId) return;

    console.log('[Ruh] Storing error for tab:', tabId);
    chrome.storage.local.set({
      [`analysis_${tabId}`]: {
        tabId,
        productUrl: message.productUrl,
        status: 'error',
        data: null,
        error: message.error,
        timestamp: Date.now(),
        harmScore: null
      }
    });

    sendResponse({ success: true });
  }

  if (message.type === 'ANALYSIS_STARTED') {
    // Content script started analysis
    const tabId = sender.tab?.id;
    if (!tabId) return;

    console.log('[Ruh] Analysis started for tab:', tabId);
    chrome.storage.local.set({
      [`analysis_${tabId}`]: {
        tabId,
        productUrl: message.productUrl,
        status: 'loading',
        data: null,
        error: null,
        timestamp: Date.now(),
        harmScore: null
      }
    });

    sendResponse({ success: true });
  }

  if (message.type === 'OPEN_SIDE_PANEL') {
    // Donut button clicked - open side panel
    const tabId = message.tabId || sender.tab?.id;
    if (!tabId) {
      console.warn('[Ruh] No tab ID in OPEN_SIDE_PANEL message');
      sendResponse({ success: false });
      return;
    }

    console.log('[Ruh] Opening side panel for tab:', tabId);

    // Set options synchronously (no await) to preserve user gesture context
    chrome.sidePanel.setOptions({
      tabId: tabId,
      path: `sidepanel.html?tabId=${tabId}`,
      enabled: true
    });

    // Open must be called synchronously in response to user gesture
    chrome.sidePanel.open({ tabId }).then(() => {
      console.log('[Ruh] Side panel opened successfully');

      // Track this tab as having an open side panel
      tabsWithOpenSidePanel.add(tabId);
      startPolling();

      // Notify content script immediately
      chrome.tabs.sendMessage(tabId, {
        type: 'SIDE_PANEL_STATE_CHANGED',
        isOpen: true
      }).catch(() => {});

      sendResponse({ success: true });
    }).catch((err) => {
      console.error('[Ruh] Failed to open side panel:', err);
      sendResponse({ success: false, error: String(err) });
    });

    return true; // Async response
  }
});

// Handle browser action click (toolbar icon) - Open side panel
chrome.action.onClicked.addListener((tab) => {
  console.log('[Ruh] Toolbar icon clicked, tab:', tab);

  if (!tab.id) {
    console.warn('[Ruh] No tab ID in action click');
    return;
  }

  const tabId = tab.id;

  // Set options synchronously (no await) to preserve user gesture context
  chrome.sidePanel.setOptions({
    tabId: tabId,
    path: `sidepanel.html?tabId=${tabId}`,
    enabled: true
  });

  // Open must be called synchronously in response to user gesture
  chrome.sidePanel.open({ tabId }).then(() => {
    console.log('[Ruh] Side panel opened successfully');

    // Track and start polling
    tabsWithOpenSidePanel.add(tabId);
    startPolling();

    // Notify content script
    chrome.tabs.sendMessage(tabId, {
      type: 'SIDE_PANEL_STATE_CHANGED',
      isOpen: true
    }).catch(() => {});
  }).catch((err) => {
    console.error('[Ruh] Failed to open side panel:', err);
  });
});

// Clean up when tabs are closed
chrome.tabs.onRemoved.addListener((tabId) => {
  console.log('[Ruh] Tab closed, cleaning up:', tabId);
  chrome.storage.local.remove(`analysis_${tabId}`);

  // Clean up side panel tracking
  tabsWithOpenSidePanel.delete(tabId);
});

export {};
