console.log('[Eject] Background service worker initialized');

// Listen for extension installation
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('[Eject] Extension installed');

    // Generate and store user UUID
    const userId = crypto.randomUUID();
    chrome.storage.local.set({ userId }, () => {
      console.log('[Eject] User ID generated:', userId);
    });

    // Set default settings
    chrome.storage.local.set({
      allergenProfile: [],
      sensitivityLevel: 'moderate',
      notificationsEnabled: true
    });

    // Open welcome page (optional)
    // chrome.tabs.create({ url: 'https://eject.rshvr.com/welcome' });
  } else if (details.reason === 'update') {
    console.log('[Eject] Extension updated to version', chrome.runtime.getManifest().version);
  }
});

// Handle messages from content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('[Eject] Message received:', message);

  if (message.type === 'GET_USER_ID') {
    chrome.storage.local.get(['userId'], (result) => {
      sendResponse({ userId: result.userId });
    });
    return true; // Keep channel open for async response
  }

  if (message.type === 'TRACK_ANALYSIS') {
    // Track that a product was analyzed (for metrics)
    console.log('[Eject] Product analyzed:', message.productUrl);
    // Could send to analytics service here
  }

  if (message.type === 'TRACK_CLICK') {
    // Track alternative product clicks
    console.log('[Eject] Alternative clicked:', message.alternativeUrl);
    // Could send to analytics service here
  }
});

// Handle browser action click (extension icon)
chrome.action.onClicked.addListener((tab) => {
  if (tab.id) {
    // Send message to content script to open sidebar
    chrome.tabs.sendMessage(tab.id, { type: 'OPEN_SIDEBAR' });
  }
});

// Clean up expired cache periodically (every 24 hours)
setInterval(() => {
  console.log('[Eject] Running cache cleanup...');
  chrome.tabs.query({}, (tabs) => {
    tabs.forEach((tab) => {
      if (tab.id) {
        chrome.tabs.sendMessage(tab.id, { type: 'CLEANUP_CACHE' }).catch(() => {
          // Tab might not have content script, ignore error
        });
      }
    });
  });
}, 24 * 60 * 60 * 1000); // 24 hours

export {};
