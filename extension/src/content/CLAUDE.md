# Content Scripts

## Overview

Content scripts injected into Amazon product pages to detect products, trigger analysis, and inject UI elements (trigger button and sidebar iframe).

---

## Function-Level Flow Diagram

```
📄 content.ts::init() [DOMContentLoaded event handler]
  ├─ Calls: isAmazonProductPage(window.location.href)
  │   └─ Checks: URL contains '/dp/' or '/gp/product/'
  │   └─ Returns: boolean
  │
  ├─ IF Amazon product page:
  │   ├─ Stores: currentProductUrl = window.location.href
  │   ├─ Sets up: chrome.runtime.onMessage listener
  │   └─ Calls: startAnalysis()
  │
  └─ ELSE: Returns (does nothing)

📄 content.ts::startAnalysis()
  ├─ Shows: Loading state
  ├─ Reads: API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  ├─ Reads: API_KEY = import.meta.env.VITE_API_KEY
  │
  ├─ Makes: fetch(API_BASE_URL + '/api/analyze', {
  │          method: 'POST',
  │          headers: {
  │            'Content-Type': 'application/json',
  │            'Authorization': `Bearer ${API_KEY}`
  │          },
  │          body: JSON.stringify({
  │            product_url: currentProductUrl
  │          })
  │        })
  │
  ├─ IF successful:
  │   ├─ Parses: data = await response.json()
  │   ├─ Stores: state.data = data
  │   ├─ Extracts: harmScore = 100 - data.analysis.product_analysis.overall_score
  │   └─ Calls: injectTriggerButton(harmScore)
  │
  └─ IF error:
      └─ Logs: console.error('Analysis failed:', error)

📄 content.ts::injectTriggerButton(harmScore: number)
  ├─ Finds: titleElement = document.querySelector('#productTitle')
  ├─ IF titleElement not found: Returns
  │
  ├─ Creates: button = document.createElement('button')
  ├─ Sets: button.className = 'eject-trigger-button'
  ├─ Sets: button.style = 'margin-bottom: 10px; cursor: pointer; ...'
  │
  ├─ Builds: Donut chart SVG
  │   ├─ Calculates: circumference = 2 * Math.PI * 18
  │   ├─ Calculates: offset = circumference - (harmScore / 100) * circumference
  │   ├─ Determines: strokeColor based on harmScore
  │   │   ├─ harmScore < 30: green (#10b981)
  │   │   ├─ harmScore < 60: yellow (#f59e0b)
  │   │   └─ harmScore >= 60: red (#ef4444)
  │   └─ Creates: SVG with circle elements and text
  │
  ├─ Sets: button.innerHTML = `
  │         <div style="display: flex; align-items: center; gap: 12px;">
  │           ${svg}
  │           <span>View Safety Analysis</span>
  │         </div>
  │       `
  │
  ├─ Attaches: button.addEventListener('click', () => openSidebar())
  │
  ├─ Injects: titleElement.parentNode.insertBefore(button, titleElement)
  └─ Returns: void

📄 content.ts::openSidebar()
  ├─ Creates: iframe = document.createElement('iframe')
  ├─ Sets: iframe.src = chrome.runtime.getURL('src/sidebar.html')
  ├─ Sets: iframe.className = 'eject-sidebar-iframe'
  ├─ Sets: iframe.style = `
  │         position: fixed;
  │         top: 0;
  │         right: 0;
  │         width: 400px;
  │         height: 100%;
  │         border: none;
  │         z-index: 999999;
  │         box-shadow: -2px 0 10px rgba(0,0,0,0.1);
  │       `
  │
  ├─ Injects: document.body.appendChild(iframe)
  │
  ├─ Waits: iframe.onload event
  ├─ Delays: setTimeout(() => {...}, 100)
  │
  ├─ Sends: iframe.contentWindow.postMessage({
  │          type: 'ANALYSIS_DATA',
  │          data: state.data
  │        }, '*')
  │
  ├─ Hides: trigger button
  │   └─ document.querySelector('.eject-trigger-button').style.display = 'none'
  │
  └─ Returns: void

📄 content.ts::closeSidebar()
  ├─ Finds: iframe = document.querySelector('.eject-sidebar-iframe')
  ├─ Removes: iframe?.remove()
  │
  ├─ Shows: trigger button
  │   └─ document.querySelector('.eject-trigger-button').style.display = 'block'
  │
  └─ Returns: void

📄 content.ts::chrome.runtime.onMessage listener
  ├─ Listens: Messages from background worker or sidebar
  │
  ├─ IF message.type == 'OPEN_SIDEBAR':
  │   └─ Calls: openSidebar()
  │
  ├─ IF message.type == 'CLOSE_SIDEBAR':
  │   └─ Calls: closeSidebar()
  │
  └─ Returns: void
```

---

## File-Level Import Relationships

```
content.ts
  IMPORTS:
    - chrome (global API from Chrome extension runtime)
    - import.meta.env (Vite environment variables)
  IMPORTED BY:
    - None (loaded by manifest.json)
  LOADED BY:
    - manifest.json (content_scripts configuration)
```

---

## Directory Structure

```
/extension/src/content/
├── content.ts       # Main content script logic
└── content.css      # Content script styles
```

---

## Files Description

### content.ts
**Purpose**: Main content script injected into Amazon product pages

**Key Functions**:
- `init()` - Entry point, called on DOMContentLoaded
- `isAmazonProductPage()` - Detects if page is Amazon product page
- `startAnalysis()` - Calls backend API for product analysis
- `injectTriggerButton()` - Injects floating button with harm score donut chart
- `openSidebar()` - Creates and shows sidebar iframe
- `closeSidebar()` - Removes sidebar iframe

**State**:
```typescript
const state = {
  data: null,              // Analysis response from backend
  currentProductUrl: ''    // Current Amazon product URL
}
```

**Dependencies**:
- Chrome Extension APIs (chrome.runtime, chrome.storage)
- Fetch API (for backend HTTP requests)
- import.meta.env (Vite environment variables)

**Relationships**:
- Injected into every Amazon product page
- Calls backend API (POST /api/analyze)
- Creates sidebar iframe and sends data via postMessage
- Receives messages from background worker

**No File Imports**:
- All utilities are inlined to avoid bundling issues
- Content scripts run in isolated world with page's DOM
- Importing modules can cause conflicts with page's code

### content.css
**Purpose**: Styles for injected elements (trigger button, sidebar)

**Key Styles**:
- `.eject-trigger-button` - Floating button styles
- `.eject-sidebar-iframe` - Sidebar positioning and appearance
- Hover states and transitions

**Scoping**:
- Uses specific class names to avoid conflicts
- High z-index values to appear above page content

---

## Amazon Product Page Detection

### URL Patterns

**Valid Product URLs**:
- `https://www.amazon.com/dp/B004D24D0S`
- `https://www.amazon.com/gp/product/B004D24D0S`
- `https://www.amazon.com/Neutrogena-Ultra-Sheer-Sunscreen/dp/B004D24D0S`
- `https://www.amazon.co.uk/dp/...` (international domains)

**Detection Logic**:
```typescript
function isAmazonProductPage(url: string): boolean {
  return url.includes('/dp/') || url.includes('/gp/product/');
}
```

---

## Communication Patterns

### Content Script → Backend API

**Method**: HTTP POST via fetch()

**Endpoint**: `POST ${API_BASE_URL}/api/analyze`

**Headers**:
- `Content-Type: application/json`
- `Authorization: Bearer ${API_KEY}`

**Request Body**:
```json
{
  "product_url": "https://www.amazon.com/dp/B004D24D0S"
}
```

**Response**:
```json
{
  "analysis": {...},
  "alternatives": [],
  "cached": false,
  "url_hash": "..."
}
```

### Content Script → Sidebar (iframe)

**Method**: window.postMessage()

**Message Format**:
```typescript
{
  type: 'ANALYSIS_DATA',
  data: AnalysisResponse  // From backend
}
```

**Target**: `iframe.contentWindow`

**Origin**: `'*'` (any origin - iframe is from same extension)

### Background Worker → Content Script

**Method**: chrome.runtime.sendMessage()

**Message Types**:
- `{type: 'OPEN_SIDEBAR'}` - Triggers openSidebar()
- `{type: 'CLOSE_SIDEBAR'}` - Triggers closeSidebar()

---

## UI Injection Details

### Trigger Button Placement

**Selector**: `#productTitle` (Amazon's product title element)

**Injection Point**: Inserted BEFORE title element

**Reason**: High visibility, consistent placement across product pages

### Donut Chart SVG

**Dimensions**: 40x40px

**Structure**:
```svg
<svg width="40" height="40" viewBox="0 0 40 40">
  <!-- Background circle -->
  <circle cx="20" cy="20" r="18" fill="none" stroke="#e5e7eb" stroke-width="4"/>

  <!-- Foreground circle (progress) -->
  <circle
    cx="20" cy="20" r="18"
    fill="none"
    stroke="{color}"
    stroke-width="4"
    stroke-dasharray="{circumference}"
    stroke-dashoffset="{offset}"
    transform="rotate(-90 20 20)"
  />

  <!-- Score text -->
  <text x="20" y="20" text-anchor="middle" dy=".3em" font-size="10">
    {harmScore}
  </text>
</svg>
```

**Color Logic**:
- Green: harmScore < 30
- Yellow: harmScore < 60
- Red: harmScore >= 60

---

## Challenges & Solutions

### Challenge: Content Script Bundle Size

**Problem**: Importing large libraries bloats content script

**Solution**: Inline all utilities, use native APIs only

### Challenge: Page Conflicts

**Problem**: Content script can conflict with Amazon's JavaScript

**Solution**:
- Unique class names (prefixed with `eject-`)
- High z-index values
- Isolated event handlers

### Challenge: iframe Communication

**Problem**: Sidebar needs analysis data from content script

**Solution**: postMessage API for cross-origin communication

---

## Related Documentation

- [Extension Source](../CLAUDE.md) - Parent directory
- [Background Worker](../background/CLAUDE.md) - Message routing
- [Sidebar App](../../CLAUDE.md) - Receives data from content script

---

Last Updated: 2025-11-18
