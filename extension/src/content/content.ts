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

console.log('[Eject] Content script loaded');

// State
let sidebarIframe: HTMLIFrameElement | null = null;
let triggerButton: HTMLButtonElement | null = null;
let currentProductUrl: string | null = null;

/**
 * Initialize the extension on Amazon product pages
 */
function init() {
  if (!isAmazonProductPage(window.location.href)) {
    console.log('[Eject] Not a product page, skipping');
    return;
  }

  currentProductUrl = window.location.href;
  console.log('[Eject] Product page detected:', currentProductUrl);

  // Create and inject the trigger button
  injectTriggerButton();

  // Listen for messages from sidebar
  window.addEventListener('message', handleMessage);
}

/**
 * Create and inject the floating trigger button
 */
function injectTriggerButton() {
  if (triggerButton) return;

  triggerButton = document.createElement('button');
  triggerButton.id = 'eject-trigger-button';
  triggerButton.innerHTML = `
    <span style="font-size: 24px;">🛡️</span>
    <span style="font-size: 12px; margin-left: 4px;">Check Safety</span>
  `;
  triggerButton.style.cssText = `
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 999998;
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
    border: none;
    border-radius: 50px;
    padding: 12px 20px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 4px;
  `;

  // Hover effect
  triggerButton.addEventListener('mouseenter', () => {
    triggerButton!.style.transform = 'scale(1.05)';
    triggerButton!.style.boxShadow = '0 6px 16px rgba(37, 99, 235, 0.5)';
  });

  triggerButton.addEventListener('mouseleave', () => {
    triggerButton!.style.transform = 'scale(1)';
    triggerButton!.style.boxShadow = '0 4px 12px rgba(37, 99, 235, 0.4)';
  });

  // Click handler
  triggerButton.addEventListener('click', openSidebar);

  document.body.appendChild(triggerButton);
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
  sidebarIframe.id = 'eject-sidebar-iframe';
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

  // Send analyze message to sidebar
  setTimeout(() => {
    sidebarIframe?.contentWindow?.postMessage(
      { type: 'ANALYZE_PRODUCT', url: currentProductUrl },
      '*'
    );
  }, 100);
}

/**
 * Close the sidebar
 */
function closeSidebar() {
  if (sidebarIframe) {
    sidebarIframe.remove();
    sidebarIframe = null;
  }

  // Show trigger button again
  if (triggerButton) {
    triggerButton.style.display = 'flex';
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
