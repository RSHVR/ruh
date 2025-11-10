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
interface AnalysisState {
  status: 'idle' | 'loading' | 'complete' | 'error';
  data: any | null;
  error: string | null;
}

let state: AnalysisState = { status: 'idle', data: null, error: null };
let sidebarIframe: HTMLIFrameElement | null = null;
let triggerButton: HTMLDivElement | null = null;
let currentProductUrl: string | null = null;
let buttonDismissed: boolean = false;

/**
 * Initialize the extension on Amazon product pages
 */
function init() {
  if (!isAmazonProductPage(window.location.href)) {
    console.log('[ruh] Not a product page, skipping');
    return;
  }

  currentProductUrl = window.location.href;
  console.log('[ruh] Product page detected:', currentProductUrl);

  // Listen for messages from background script (extension icon click)
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'OPEN_SIDEBAR') {
      openSidebar();
      sendResponse({ success: true });
    }
  });

  // Listen for messages from sidebar iframe
  window.addEventListener('message', handleMessage);

  // Start analysis in background
  startAnalysis();
}

/**
 * Start product analysis in background
 */
async function startAnalysis() {
  if (!currentProductUrl) return;

  state.status = 'loading';
  console.log('[ruh] Starting analysis for:', currentProductUrl);

  try {
    // Call API
    const response = await fetch('http://localhost:8001/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_url: currentProductUrl })
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    const data = await response.json();
    state.status = 'complete';
    state.data = data;
    console.log('[ruh] Analysis complete:', data);

    // Inject button now that analysis is complete
    // overall_score is safety score (0-100 where 100=safe), we need harm score
    const harmScore = 100 - data.analysis.overall_score;
    if (!buttonDismissed) {
      injectTriggerButton(harmScore);
    }
  } catch (error) {
    state.status = 'error';
    state.error = error instanceof Error ? error.message : 'Analysis failed';
    console.error('[ruh] Analysis error:', error);
    // Don't show button on error
  }
}

/**
 * Create and inject the trigger button with score badge
 */
function injectTriggerButton(harmScore: number) {
  if (triggerButton || buttonDismissed) return;

  const scoreColor = getScoreColor(harmScore);

  triggerButton = document.createElement('div');
  triggerButton.id = 'ruh-trigger-button';

  // Create donut badge SVG
  const radius = 16;
  const circumference = 2 * Math.PI * radius;
  const progress = (harmScore / 100) * circumference;
  const offset = circumference - progress;

  triggerButton.innerHTML = `
    <div class="ruh-button-container">
      <div class="ruh-button-content">
        <div class="ruh-score-badge">
          <svg viewBox="0 0 40 40" class="ruh-donut">
            <circle cx="20" cy="20" r="${radius}" fill="none" stroke="rgba(107, 101, 96, 0.2)" stroke-width="3"/>
            <circle cx="20" cy="20" r="${radius}" fill="none" stroke="${scoreColor}" stroke-width="3" stroke-linecap="round"
              stroke-dasharray="${circumference}" stroke-dashoffset="${offset}"
              transform="rotate(-90 20 20)" class="ruh-donut-progress"/>
          </svg>
          <span class="ruh-score-number">${harmScore}</span>
        </div>
        <span class="ruh-button-text">View Safety Score</span>
      </div>
      <button class="ruh-dismiss-btn">dismiss</button>
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
        top: 20px;
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

      .ruh-button-container {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 4px;
      }

      .ruh-button-content {
        display: flex;
        align-items: center;
        gap: 12px;
        background: #E8DCC8;
        border-radius: 24px;
        padding: 8px 20px 8px 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        cursor: pointer;
        transition: all 150ms ease-in-out;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      }

      .ruh-button-content:hover {
        background: #C9B5A0;
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
      }

      .ruh-button-content:active {
        transform: translateY(-1px) scale(0.98);
      }

      .ruh-score-badge {
        position: relative;
        width: 44px;
        height: 44px;
        flex-shrink: 0;
      }

      .ruh-donut {
        width: 100%;
        height: 100%;
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
        font-size: 14px;
        color: #3A3633;
        line-height: 1;
      }

      .ruh-button-text {
        font-size: 15px;
        font-weight: 500;
        color: #3A3633;
        white-space: nowrap;
      }

      .ruh-dismiss-btn {
        background: none;
        border: none;
        padding: 0;
        font-family: 'Inter', sans-serif;
        font-size: 12px;
        font-weight: 400;
        color: #6B6560;
        cursor: pointer;
        transition: color 150ms ease;
        text-transform: lowercase;
      }

      .ruh-dismiss-btn:hover {
        color: #3A3633;
      }
    `;
    document.head.appendChild(styleEl);
  }

  // Add click handlers
  const buttonContent = triggerButton.querySelector('.ruh-button-content');
  const dismissBtn = triggerButton.querySelector('.ruh-dismiss-btn');

  buttonContent?.addEventListener('click', openSidebar);
  dismissBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    dismissButton();
  });

  document.body.appendChild(triggerButton);
}

/**
 * Dismiss the trigger button
 */
function dismissButton() {
  if (triggerButton) {
    triggerButton.style.animation = 'ruhFadeOut 200ms ease-out forwards';
    setTimeout(() => {
      triggerButton?.remove();
      triggerButton = null;
      buttonDismissed = true;
    }, 200);
  }

  // Add fadeOut animation
  const styleEl = document.getElementById('ruh-button-styles');
  if (styleEl && !styleEl.textContent?.includes('ruhFadeOut')) {
    styleEl.textContent += `
      @keyframes ruhFadeOut {
        from {
          opacity: 1;
          transform: translateY(0);
        }
        to {
          opacity: 0;
          transform: translateY(-10px);
        }
      }
    `;
  }
}

/**
 * Open the sidebar with product analysis
 */
function openSidebar() {
  if (sidebarIframe) {
    // Sidebar already open
    return;
  }

  if (!currentProductUrl) return;

  // Create iframe for sidebar
  sidebarIframe = document.createElement('iframe');
  sidebarIframe.id = 'ruh-sidebar-iframe';
  sidebarIframe.src = chrome.runtime.getURL(`src/sidebar.html?url=${encodeURIComponent(currentProductUrl)}`);
  sidebarIframe.style.cssText = `
    position: fixed;
    top: 0;
    right: 0;
    width: 400px;
    height: 100%;
    border: none;
    z-index: 999999;
    box-shadow: -2px 0 8px rgba(0, 0, 0, 0.1);
  `;

  document.body.appendChild(sidebarIframe);

  // Hide trigger button when sidebar is open
  if (triggerButton) {
    triggerButton.style.display = 'none';
  }

  // If analysis is complete, send data to sidebar immediately
  if (state.status === 'complete' && state.data) {
    setTimeout(() => {
      sidebarIframe?.contentWindow?.postMessage(
        { type: 'ANALYSIS_DATA', data: state.data },
        '*'
      );
    }, 100);
  } else {
    // Send message to start analysis if not complete
    setTimeout(() => {
      sidebarIframe?.contentWindow?.postMessage(
        { type: 'ANALYZE_PRODUCT', url: currentProductUrl },
        '*'
      );
    }, 100);
  }
}

/**
 * Close the sidebar
 */
function closeSidebar() {
  if (sidebarIframe) {
    sidebarIframe.remove();
    sidebarIframe = null;
  }

  // Show trigger button again (if not dismissed)
  if (triggerButton && !buttonDismissed) {
    triggerButton.style.display = 'block';
  }
}

/**
 * Handle messages from sidebar iframe
 */
function handleMessage(event: MessageEvent) {
  if (event.data?.type === 'EJECT_CLOSE_SIDEBAR') {
    closeSidebar();
  }
}

/**
 * Clean up on page navigation
 */
function cleanup() {
  if (triggerButton) {
    triggerButton.remove();
    triggerButton = null;
  }
  closeSidebar();
  window.removeEventListener('message', handleMessage);
  state = { status: 'idle', data: null, error: null };
  buttonDismissed = false;
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
