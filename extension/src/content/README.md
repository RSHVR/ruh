# Content Script (`/extension/src/content/`)

## Overview

The content script is the core injection point of the Ruh Chrome extension. It runs within the context of Amazon product pages and performs URL validation, backend API analysis, and DOM injection of the floating trigger button.

## Files

| File | Purpose | Lines | Key Functions |
|------|---------|-------|---------------|
| `content.ts` | Main content script logic | 295 | `isAmazonProductPage`, `init`, `startAnalysis`, `injectTriggerButton`, `cleanup` |
| `content.css` | Animation styles | 30 | Keyframe animations |

## Injection Configuration

- **Matches**: `https://*.amazon.com/*`, `https://*.amazon.ca/*`
- **Run at**: `document_idle`
- **Isolation**: Default (shares DOM with page, isolated JS context)

## Key Functions

### `isAmazonProductPage(url: string): boolean`
Validates whether URL is an Amazon product page (contains `/dp/` or `/gp/product/`)

### `startAnalysis(): Promise<void>`
Fetches product analysis from backend API:
- Endpoint: `POST /api/analyze`
- Sends `ANALYSIS_STARTED/COMPLETE/ERROR` messages to background worker
- No timeout or retry logic

### `injectTriggerButton(harmScore: number): void`
Creates floating donut chart button:
- Injects styles and SVG element
- Handles click to open side panel
- Uses `innerHTML` with template literal (low XSS risk - numeric input)

### `cleanup(): void`
Removes injected elements and resets state (partial - doesn't remove style element)

## SPA Navigation

Uses MutationObserver on `document.body` to detect URL changes:
- Fires on ANY DOM mutation (performance concern)
- 500ms delay before re-init (arbitrary)
- No debouncing

## Production Readiness Issues

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| **Critical** | No request timeout | content.ts:100 | Add AbortController with 30s timeout |
| **Critical** | No retry logic | content.ts:100 | Implement exponential backoff |
| **High** | MutationObserver on entire body | content.ts:284 | Use History API or narrow scope |
| **High** | Style element not cleaned up | content.ts:171 | Track and remove in cleanup() |
| **High** | Message listener never removed | content.ts:31 | Remove in cleanup() |
| **Medium** | innerHTML with template literal | content.ts:158 | Use DOM APIs |
| **Medium** | External font dependency | content.ts:175 | Bundle font or use system fonts |
| **Low** | Debug logging in production | content.ts | Add log level config |

## Dependencies

### Chrome APIs
- `chrome.runtime.sendMessage` - Background worker communication
- `chrome.runtime.onMessage` - Receive side panel state

### External Resources
- Google Fonts (Inter) - External network dependency
