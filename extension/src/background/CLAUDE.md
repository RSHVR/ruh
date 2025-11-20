# Background Service Worker

## Overview

Background service worker for the Chrome extension. Handles message routing between content scripts, sidebar, and other extension components.

---

## Function-Level Flow Diagram

```
📄 background.ts::chrome.runtime.onMessage listener
  ├─ Listens: Messages from content scripts or sidebar
  │
  ├─ Receives: (message, sender, sendResponse)
  │   ├─ message: {type: string, ...data}
  │   ├─ sender: Chrome tab/frame info
  │   └─ sendResponse: Callback function
  │
  ├─ Logs: console.log('Background received message:', message)
  │
  ├─ Message routing (currently minimal):
  │   ├─ IF message.type == 'OPEN_SIDEBAR':
  │   │   └─ Forward to active tab's content script
  │   │
  │   └─ IF message.type == 'CLOSE_SIDEBAR':
  │       └─ Forward to active tab's content script
  │
  └─ Returns: void
```

---

## File-Level Import Relationships

```
background.ts
  IMPORTS:
    - chrome (global API from Chrome extension runtime)
  IMPORTED BY:
    - None (loaded by manifest.json)
  LOADED BY:
    - manifest.json (service_worker configuration)
```

---

## Directory Structure

```
/extension/src/background/
└── background.ts      # Background service worker
```

---

## File Description

### background.ts
**Purpose**: Chrome extension background service worker (Manifest V3)

**Current Functionality**:
- Message listener setup
- Basic message routing (minimal implementation)
- Logging for debugging

**Potential Functionality** (not implemented):
- Badge management (extension icon badge)
- Persistent state management
- Alarms and scheduled tasks
- Cross-tab communication
- Network request interception

**Dependencies**:
- Chrome Extension APIs (chrome.runtime, chrome.tabs, chrome.storage)

**Relationships**:
- Receives messages from content scripts
- Receives messages from sidebar
- Can send messages to content scripts
- Currently acts as simple message relay

---

## Chrome Manifest V3 Service Worker

### Lifecycle

**Activation**:
- Starts when extension is installed
- Starts on browser launch
- Starts on incoming message
- **Dies after 30 seconds of inactivity** (Manifest V3 behavior)

**Implications**:
- Cannot maintain long-lived connections
- Must use chrome.storage for persistence
- Must use alarms for scheduled tasks

### Current Implementation

**Minimal Functionality**:
```typescript
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('Background received message:', message);

  // Message routing happens here (if needed)

  return true; // Keep message channel open
});
```

**Why minimal?**:
- Current architecture doesn't require complex background logic
- Content script handles API calls directly
- Sidebar handles UI rendering directly
- No need for cross-tab coordination

---

## Potential Future Enhancements

### Badge Management

**Use Case**: Show analysis status on extension icon

```typescript
// Set badge text
chrome.action.setBadgeText({
  text: harmScore.toString()
});

// Set badge background color
chrome.action.setBadgeBackgroundColor({
  color: harmScore < 30 ? '#10b981' : '#ef4444'
});
```

### Storage Management

**Use Case**: Sync settings across devices

```typescript
// Store user preferences
chrome.storage.sync.set({
  theme: 'dark',
  notifications: true
});

// Retrieve preferences
const data = await chrome.storage.sync.get(['theme', 'notifications']);
```

### Alarms

**Use Case**: Periodic cache cleanup

```typescript
// Create alarm for daily cleanup
chrome.alarms.create('cache-cleanup', {
  periodInMinutes: 1440  // 24 hours
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'cache-cleanup') {
    // Clean up expired cache entries
  }
});
```

---

## Message Flow Architecture

### Current Message Flow

```
Content Script
  ↓ (direct API call)
Backend API
  ↓ (response)
Content Script
  ↓ (postMessage)
Sidebar
```

**Background Worker Not Used** for main flow.

### Potential Message Flow (Future)

```
Content Script
  ↓ (chrome.runtime.sendMessage)
Background Worker
  ↓ (API call with retry logic)
Backend API
  ↓ (response)
Background Worker
  ↓ (chrome.tabs.sendMessage)
Content Script
  ↓ (postMessage)
Sidebar
```

**Benefits**:
- Centralized API call logic
- Retry logic in background
- Request deduplication
- Rate limiting

---

## Debugging Background Worker

### Chrome DevTools

**Access**:
1. Navigate to `chrome://extensions/`
2. Enable "Developer mode"
3. Find "Eject" extension
4. Click "service worker" link (or "Inspect views: service worker")

**Console Output**:
- `console.log()` statements appear in worker console
- View message flow and errors
- Inspect state and variables

### Common Issues

**Issue**: Service worker goes inactive

**Solution**: Message listener keeps it active for 30s after each message

**Issue**: Cannot access DOM

**Solution**: Use content scripts for DOM manipulation, not background worker

---

## Related Documentation

- [Extension Source](../CLAUDE.md) - Parent directory
- [Content Script](../content/CLAUDE.md) - Primary communication partner
- [Manifest](../../public/CLAUDE.md) - Service worker configuration

---

Last Updated: 2025-11-18
