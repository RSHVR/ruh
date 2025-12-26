# Background Service Worker (`/extension/src/background/`)

## Overview

The background service worker is the persistent process for the Ruh Chrome extension. It manages communication between content scripts and the side panel, tracks side panel state per tab, and handles analysis data storage.

## Files

| File | Purpose | Lines | Key Functions |
|------|---------|-------|---------------|
| `background.ts` | Main service worker with message routing | 219 | Installation handler, message router, tab cleanup |

## Service Worker Lifecycle

| Aspect | Details |
|--------|---------|
| **Activation** | On extension install or Chrome start |
| **Persistence** | Non-persistent; state persisted via `chrome.storage.local` |
| **Cleanup** | `chrome.tabs.onRemoved` listener cleans up tab data |

## State Management

### In-Memory State
| Variable | Type | Purpose |
|----------|------|---------|
| `sidePanelOpenState` | `Map<number, boolean>` | Tracks panel state per tab |

### Chrome Storage Keys
| Key Pattern | Data |
|-------------|------|
| `userId` | UUID for user tracking |
| `sidePanelOpen_${tabId}` | Boolean panel state |
| `analysis_${tabId}` | Full analysis state object |

## Message Types Handled

| Message Type | Source | Purpose |
|--------------|--------|---------|
| `SIDE_PANEL_OPENED` | SidePanelContainer | Track panel opened |
| `SIDE_PANEL_CLOSED` | SidePanelContainer | Track panel closed |
| `GET_SIDE_PANEL_STATE` | content.ts | Query panel state |
| `ANALYSIS_STARTED` | content.ts | Store loading state |
| `ANALYSIS_COMPLETE` | content.ts | Store analysis result |
| `ANALYSIS_ERROR` | content.ts | Store error state |
| `OPEN_SIDE_PANEL` | content.ts | Open side panel |

## Production Readiness Issues

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| **Critical** | No message type validation | background.ts:29 | Add TypeScript discriminated unions |
| **Critical** | No sender origin validation | background.ts:29 | Verify `sender.id === chrome.runtime.id` |
| **High** | Storage operations no error handling | multiple | Add `.catch()` handlers |
| **High** | OPEN_SIDE_PANEL returns success on failure | background.ts:184 | Return error response |
| **High** | In-memory state lost on termination | background.ts:4 | Always use chrome.storage |
| **Medium** | Dead code: GET_USER_ID, TRACK_* | background.ts:86-103 | Remove or implement |
| **Medium** | No message TTL/expiry | background.ts | Add stale data cleanup |

## Chrome APIs Used

| API | Purpose | Permission |
|-----|---------|------------|
| `chrome.runtime.onInstalled` | First-time setup | N/A |
| `chrome.runtime.onMessage` | Message routing | N/A |
| `chrome.storage.local` | Persistent storage | `storage` |
| `chrome.tabs.sendMessage` | Send to content scripts | `tabs` |
| `chrome.tabs.onRemoved` | Tab close detection | `tabs` |
| `chrome.sidePanel.open` | Open side panel | `sidePanel` |

## Test Coverage: 0%
