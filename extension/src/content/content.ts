// Inline utility function to avoid imports
function isAmazonProductPage(url: string): boolean {
  try {
    const urlObj = new URL(url);
    const isAmazon =
      urlObj.hostname.includes('amazon.com') || urlObj.hostname.includes('amazon.ca');
    const hasDP = urlObj.pathname.includes('/dp/') || urlObj.pathname.includes('/gp/product/');
    return isAmazon && hasDP;
  } catch {
    return false;
  }
}

// Get score color based on harm level
function getScoreColor(score: number): string {
  if (score <= 30) return '#9BB88F'; // Safe Green
  if (score <= 60) return '#D4A574'; // Caution Amber
  return '#C18A72'; // Alert Rust
}

console.log('[ruh] Content script loaded');

// State
let triggerButton: HTMLDivElement | null = null;
let currentProductUrl: string | null = null;
let buttonDismissed: boolean = false;

// ============================================
// BUTTON VISIBILITY MANAGEMENT
// ============================================

/**
 * Query background to check if side panel is open for this tab
 * and update button visibility accordingly.
 */
async function updateButtonVisibility() {
  if (!triggerButton || buttonDismissed) return;

  try {
    const response = await chrome.runtime.sendMessage({
      type: 'IS_SIDE_PANEL_OPEN'
    });

    if (response?.isOpen) {
      triggerButton.style.display = 'none';
    } else if (currentProductUrl) {
      triggerButton.style.display = 'block';
    }
  } catch (err) {
    // If query fails, default to showing button (if we have data)
    if (currentProductUrl) {
      triggerButton.style.display = 'block';
    }
  }
}

/**
 * Listen for side panel state changes from background (polling notifications)
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'SIDE_PANEL_STATE_CHANGED') {
    console.log('[Ruh Content] Side panel state changed:', message.isOpen);

    if (triggerButton && !buttonDismissed) {
      triggerButton.style.display = message.isOpen ? 'none' : 'block';
    }
  }
});

/**
 * Check state when tab becomes visible (user switches back to this tab)
 */
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    console.log('[Ruh Content] Tab became visible, checking side panel state');
    updateButtonVisibility();
  }
});

/**
 * Check state when window regains focus
 */
window.addEventListener('focus', () => {
  console.log('[Ruh Content] Window focused, checking side panel state');
  updateButtonVisibility();
});

/**
 * Initialize the extension on Amazon product pages
 */
function init() {
  if (!isAmazonProductPage(window.location.href)) {
    console.log('[Ruh Content] Not a product page, skipping analysis');
    return;
  }

  currentProductUrl = window.location.href;
  console.log('[Ruh Content] Product page detected:', currentProductUrl);

  // Start analysis in background
  startAnalysis();
}

/**
 * Start product analysis in background
 */
async function startAnalysis() {
  if (!currentProductUrl) return;

  console.log('[ruh] Starting analysis for:', currentProductUrl);

  // Notify background worker that analysis started
  chrome.runtime.sendMessage({
    type: 'ANALYSIS_STARTED',
    productUrl: currentProductUrl
  });

  try {
    // Get API config from environment
    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';
    const API_KEY = import.meta.env.VITE_API_KEY;

    const headers: HeadersInit = { 'Content-Type': 'application/json' };
    if (API_KEY) {
      headers['Authorization'] = `Bearer ${API_KEY}`;
    }

    if (import.meta.env.VITE_DEBUG === 'true') {
      console.log('[ruh] API Config:', {
        baseUrl: API_BASE_URL,
        hasAuth: !!API_KEY,
        apiKeyPrefix: API_KEY?.substring(0, 8) + '...'
      });
    }

    console.log('[ruh] Calling API:', API_BASE_URL + '/api/analyze');

    // Call API
    const response = await fetch(API_BASE_URL + '/api/analyze', {
      method: 'POST',
      headers,
      body: JSON.stringify({ product_url: currentProductUrl })
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    const data = await response.json();
    console.log('[ruh] Analysis complete:', data);

    // Notify background worker that analysis is complete
    chrome.runtime.sendMessage({
      type: 'ANALYSIS_COMPLETE',
      productUrl: currentProductUrl,
      data
    });

    // Inject button now that analysis is complete
    // overall_score is safety score (0-100 where 100=safe), we need harm score
    const harmScore = 100 - data.analysis.overall_score;
    if (!buttonDismissed) {
      injectTriggerButton(harmScore);
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Analysis failed';
    console.error('[ruh] Analysis error:', error);

    // Notify background worker about the error
    chrome.runtime.sendMessage({
      type: 'ANALYSIS_ERROR',
      productUrl: currentProductUrl,
      error: errorMessage
    });

    // Don't show button on error
  }
}

/**
 * Create and inject the trigger button with score badge
 */
async function injectTriggerButton(harmScore: number) {
  if (triggerButton || buttonDismissed) return;

  const scoreColor = getScoreColor(harmScore);

  triggerButton = document.createElement('div');
  triggerButton.id = 'ruh-trigger-button';

  // Donut-only design: just the chart with harm score (no text, no dismiss)
  const radius = 18;
  const circumference = 2 * Math.PI * radius;
  const progress = (harmScore / 100) * circumference;
  const offset = circumference - progress;

  triggerButton.innerHTML = `
    <div class="ruh-donut-button">
      <svg viewBox="0 0 44 44" class="ruh-donut">
        <circle cx="22" cy="22" r="${radius}" fill="none" stroke="rgba(107, 101, 96, 0.2)" stroke-width="3"/>
        <circle cx="22" cy="22" r="${radius}" fill="none" stroke="${scoreColor}" stroke-width="3" stroke-linecap="round"
          stroke-dasharray="${circumference}" stroke-dashoffset="${offset}"
          transform="rotate(-90 22 22)" class="ruh-donut-progress"/>
      </svg>
      <span class="ruh-score-number">${harmScore}</span>
    </div>
  `;

  // Inject styles
  if (!document.getElementById('ruh-button-styles')) {
    const styleEl = document.createElement('style');
    styleEl.id = 'ruh-button-styles';
    styleEl.textContent = `
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

      #ruh-trigger-button {
        position: fixed;
        top: 110px;
        right: 20px;
        z-index: 999998;
        animation: ruhFadeIn 400ms ease-out 200ms both;
      }

      @keyframes ruhFadeIn {
        from {
          opacity: 0;
          transform: translateY(-10px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }

      .ruh-donut-button {
        position: relative;
        width: 52px;
        height: 52px;
        background: #E8DCC8;
        border-radius: 50%;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        cursor: pointer;
        transition: all 150ms ease-in-out;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .ruh-donut-button:hover {
        background: #DBC9B1;
        transform: translateY(-2px) scale(1.05);
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
      }

      .ruh-donut-button:active {
        transform: scale(0.95);
      }

      .ruh-donut {
        width: 44px;
        height: 44px;
      }

      .ruh-donut-progress {
        transition: stroke-dashoffset 1s ease-out 600ms;
      }

      .ruh-score-number {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 16px;
        color: #3A3633;
        line-height: 1;
      }
    `;
    document.head.appendChild(styleEl);
  }

  // Add click handler to open side panel
  triggerButton.addEventListener('click', () => {
    // Hide button immediately (optimistic update)
    if (triggerButton) {
      triggerButton.style.display = 'none';
    }
    chrome.runtime.sendMessage({ type: 'OPEN_SIDE_PANEL' });
  });

  // Check if side panel is already open before showing button
  const response = await chrome.runtime.sendMessage({
    type: 'IS_SIDE_PANEL_OPEN'
  });

  if (response?.isOpen) {
    // Hide button initially if side panel is open
    triggerButton.style.display = 'none';
  }

  document.body.appendChild(triggerButton);
}


/**
 * Clean up on page navigation
 */
function cleanup() {
  if (triggerButton) {
    triggerButton.remove();
    triggerButton = null;
  }
  buttonDismissed = false;
  currentProductUrl = null;
}

// Initialize on load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

// Re-initialize on URL changes (SPA navigation)
let lastUrl = window.location.href;
new MutationObserver(() => {
  const currentUrl = window.location.href;
  if (currentUrl !== lastUrl) {
    lastUrl = currentUrl;
    cleanup();
    setTimeout(init, 500); // Wait for page content to load
  }
}).observe(document.body, { childList: true, subtree: true });

// Cleanup on unload
window.addEventListener('beforeunload', cleanup);
