console.log('[Ruh] Background service worker initialized');

// Track side panel open state per tab
const sidePanelOpenState = new Map<number, boolean>();

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

  if (message.type === 'SIDE_PANEL_OPENED') {
    const tabId = message.tabId || sender.tab?.id;
    if (!tabId) return;

    console.log('[Ruh Background] Side panel opened for tab:', tabId);
    sidePanelOpenState.set(tabId, true);

    // Store in chrome.storage for persistence
    chrome.storage.local.set({ [`sidePanelOpen_${tabId}`]: true });

    // Notify content script
    chrome.tabs.sendMessage(tabId, {
      type: 'SIDE_PANEL_STATE_CHANGED',
      isOpen: true
    }).catch(() => {
      // Content script may not be injected yet
    });

    return;
  }

  if (message.type === 'SIDE_PANEL_CLOSED') {
    const tabId = message.tabId || sender.tab?.id;
    if (!tabId) return;

    console.log('[Ruh Background] Side panel closed for tab:', tabId);
    sidePanelOpenState.set(tabId, false);

    // Store in chrome.storage
    chrome.storage.local.set({ [`sidePanelOpen_${tabId}`]: false });

    // Notify content script
    chrome.tabs.sendMessage(tabId, {
      type: 'SIDE_PANEL_STATE_CHANGED',
      isOpen: false
    }).catch(() => {
      // Content script may not be injected
    });

    return;
  }

  if (message.type === 'GET_SIDE_PANEL_STATE') {
    const tabId = sender.tab?.id;
    if (!tabId) {
      sendResponse({ isOpen: false });
      return;
    }

    const isOpen = sidePanelOpenState.get(tabId) ?? false;
    sendResponse({ isOpen });
    return true; // Keep message channel open
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
      return;
    }

    console.log('[Ruh] Opening side panel for tab:', tabId);
    chrome.sidePanel.open({ tabId }).catch((err) => {
      console.error('[Ruh] Failed to open side panel:', err);
    });

    sendResponse({ success: true });
  }
});

// Handle browser action click (toolbar icon) - Open side panel
chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.id) {
    console.warn('[Ruh] No tab ID in action click');
    return;
  }

  console.log('[Ruh] Toolbar icon clicked for tab:', tab.id);

  try {
    await chrome.sidePanel.open({ tabId: tab.id });
  } catch (err) {
    console.error('[Ruh] Failed to open side panel:', err);
  }
});

// Clean up storage when tabs are closed
chrome.tabs.onRemoved.addListener((tabId) => {
  console.log('[Ruh] Tab closed, cleaning up:', tabId);
  chrome.storage.local.remove(`analysis_${tabId}`);

  // Clean up side panel state
  sidePanelOpenState.delete(tabId);
  chrome.storage.local.remove(`sidePanelOpen_${tabId}`);
});

export {};
