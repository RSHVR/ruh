# Extension - Chrome Extension Frontend

## Overview

Svelte 5 Chrome extension (Manifest V3) providing user interface for product safety analysis. Injects into Amazon product pages, displays harm scores, and shows detailed allergen/PFAS information in a sidebar.

**Stack**: Svelte 5 + TypeScript + Vite + Tailwind CSS + IndexedDB

---

## Function-Level Flow Diagram (All Extension Functions)

### Content Script (Injected into Amazon pages)

```
📄 src/content/content.ts::init()
  ├─ Listens: DOMContentLoaded event
  ├─ Checks: isAmazonProductPage(window.location.href)
  │    └─ Returns: boolean (checks for /dp/ or /gp/product/ in URL)
  │
  ├─ IF Amazon product page:
  │   ├─ Stores: currentProductUrl = window.location.href
  │   ├─ Sets up: chrome.runtime.onMessage listener
  │   └─ Calls: startAnalysis()
  │
  └─ ELSE: Does nothing

📄 src/content/content.ts::startAnalysis()
  ├─ Reads: API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  ├─ Reads: API_KEY = import.meta.env.VITE_API_KEY
  │
  ├─ Makes: fetch(API_BASE_URL + '/api/analyze', {
  │          method: 'POST',
  │          headers: {
  │            'Content-Type': 'application/json',
  │            'Authorization': `Bearer ${API_KEY}`
  │          },
  │          body: JSON.stringify({ product_url: currentProductUrl })
  │        })
  │
  ├─ Parses: data = await response.json()
  ├─ Stores: state.data = data
  ├─ Extracts: harmScore = 100 - data.analysis.product_analysis.overall_score
  └─ Calls: injectTriggerButton(harmScore)

📄 src/content/content.ts::injectTriggerButton(harmScore: number)
  ├─ Finds: titleElement = document.querySelector('#productTitle')
  │
  ├─ Creates: button = document.createElement('button')
  ├─ Sets: button.className = 'eject-trigger-button'
  ├─ Sets: button.innerHTML = `
  │         <svg>...</svg>  (donut chart with harmScore)
  │         <span>View Safety Analysis</span>
  │       `
  ├─ Attaches: button.onclick = () => openSidebar()
  │
  ├─ Injects: titleElement.parentNode.insertBefore(button, titleElement)
  └─ Returns: void

📄 src/content/content.ts::openSidebar()
  ├─ Creates: iframe = document.createElement('iframe')
  ├─ Sets: iframe.src = chrome.runtime.getURL('src/sidebar.html')
  ├─ Sets: iframe.className = 'eject-sidebar-iframe'
  ├─ Injects: document.body.appendChild(iframe)
  │
  ├─ Listens: iframe.onload
  ├─ Waits: 100ms delay
  ├─ Sends: iframe.contentWindow.postMessage({
  │          type: 'ANALYSIS_DATA',
  │          data: state.data
  │        }, '*')
  │
  └─ Hides: trigger button (display: none)

📄 src/content/content.ts::closeSidebar()
  ├─ Finds: iframe = document.querySelector('.eject-sidebar-iframe')
  ├─ Removes: iframe?.remove()
  └─ Shows: trigger button (display: block)
```

### Background Service Worker

```
📄 src/background/background.ts::chrome.runtime.onMessage listener
  ├─ Listens: Messages from content script or sidebar
  ├─ IF message.type == "OPEN_SIDEBAR":
  │   └─ Forwards to content script
  └─ IF message.type == "CLOSE_SIDEBAR":
      └─ Forwards to content script
```

### Sidebar App (Svelte 5 Application)

```
📄 src/sidebar.ts::initApp()
  ├─ Gets: app = document.getElementById('app')
  ├─ Calls: mount(Sidebar, { target: app })
  └─ Returns: Svelte component instance

📄 src/Sidebar.svelte::onMount()
  ├─ Sets up: chrome.runtime.onMessage listener
  ├─ Sets up: window.addEventListener('message', handleMessage)
  └─ Initializes: loading = true, analysis = null

📄 src/Sidebar.svelte::handleMessage(event: MessageEvent)
  ├─ IF event.data.type == 'ANALYSIS_DATA':
  │   ├─ Extracts: data = event.data.data
  │   ├─ Sets: analysis = data (reactive)
  │   ├─ Sets: loading = false
  │   │
  │   ├─ Calls: cache.set(productUrl, data)
  │   │   └─ src/lib/cache.ts::set(key, value)
  │   │       ├─ Opens: db = await openDB('eject-cache', 1)
  │   │       ├─ Stores: db.put('analyses', {
  │   │       │          key,
  │   │       │          value,
  │   │       │          timestamp: Date.now()
  │   │       │        })
  │   │       └─ Returns: void
  │   │
  │   └─ Renders: <Sidebar analysis={analysis} />
  │
  └─ Returns: void

📄 src/Sidebar.svelte::closeSidebar()
  ├─ Calls: chrome.runtime.sendMessage({ type: 'CLOSE_SIDEBAR' })
  └─ Returns: void
```

### Sidebar UI Component

```
📄 src/components/Sidebar.svelte (receives analysis prop)
  │
  ├─ Computes: productAnalysis = analysis.analysis.product_analysis
  │
  ├─ Calls: harmScore = getHarmScore(productAnalysis)
  │   └─ src/lib/utils.ts::getHarmScore(analysis)
  │       └─ Returns: 100 - analysis.overall_score
  │
  ├─ Calls: riskLevel = getRiskLevel(harmScore)
  │   └─ src/lib/utils.ts::getRiskLevel(score)
  │       ├─ IF score < 30: Returns 'low'
  │       ├─ IF score < 60: Returns 'medium'
  │       └─ IF score >= 60: Returns 'high'
  │
  ├─ Calls: riskClass = getRiskClass(riskLevel)
  │   └─ src/lib/utils.ts::getRiskClass(level)
  │       └─ Returns: 'risk-low' | 'risk-medium' | 'risk-high'
  │
  ├─ Calls: formattedTime = formatTimeAgo(analysis.analyzed_at)
  │   └─ src/lib/utils.ts::formatTimeAgo(timestamp)
  │       ├─ Calculates: diff = now - timestamp
  │       └─ Returns: "2 hours ago" | "3 days ago" | etc.
  │
  └─ Renders:
      ├─ Donut chart SVG (harmScore visualization)
      ├─ Product name and brand
      ├─ Risk level badge
      ├─ Allergens list (if detected)
      ├─ PFAS list (if detected)
      ├─ Other concerns list (if any)
      └─ Confidence score and timestamp
```

### API Client

```
📄 src/lib/api.ts::EjectAPI.analyzeProduct(productUrl: string)
  ├─ Reads: API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  ├─ Reads: API_KEY = import.meta.env.VITE_API_KEY
  │
  ├─ Makes: fetch(API_BASE_URL + '/api/analyze', {
  │          method: 'POST',
  │          headers: {
  │            'Content-Type': 'application/json',
  │            'Authorization': `Bearer ${API_KEY}`
  │          },
  │          body: JSON.stringify({ product_url: productUrl })
  │        })
  │
  ├─ Parses: data = await response.json()
  └─ Returns: data as AnalysisResponse
```

### Cache Manager

```
📄 src/lib/cache.ts::CacheManager.init()
  └─ Creates: db = await openDB('eject-cache', 1, {
               upgrade(db) {
                 db.createObjectStore('analyses')
               }
             })

📄 src/lib/cache.ts::CacheManager.get(key: string)
  ├─ Opens: db = await this.db
  ├─ Reads: item = await db.get('analyses', key)
  ├─ Checks: if (item && Date.now() - item.timestamp < 30 * 24 * 60 * 60 * 1000)
  │   └─ Returns: item.value (if within 30-day TTL)
  └─ Returns: null (if expired or not found)

📄 src/lib/cache.ts::CacheManager.set(key: string, value: AnalysisResponse)
  ├─ Opens: db = await this.db
  ├─ Stores: db.put('analyses', { key, value, timestamp: Date.now() })
  └─ Returns: void

📄 src/lib/cache.ts::CacheManager.clear()
  ├─ Opens: db = await this.db
  ├─ Clears: db.clear('analyses')
  └─ Returns: void
```

---

## File-Level Import Relationships

```
sidebar.ts
  IMPORTS:
    - svelte.mount
    - ./app.css
    - ./Sidebar.svelte
  LOADED BY:
    - src/sidebar.html

Sidebar.svelte
  IMPORTS:
    - svelte.onMount
    - ./components/Sidebar.svelte
    - ./lib/api.{api}
    - ./lib/cache.{cache}
    - ./types.{AnalysisResponse}
  MOUNTED BY:
    - sidebar.ts

components/Sidebar.svelte
  IMPORTS:
    - @/types.{AnalysisResponse}
    - @/lib/utils.{getHarmScore, getRiskLevel, getRiskClass, formatTimeAgo}
  IMPORTED BY:
    - ../Sidebar.svelte

content/content.ts
  IMPORTS:
    - chrome (global API)
    - import.meta.env (Vite environment)
  LOADED BY:
    - manifest.json (content_scripts)

background/background.ts
  IMPORTS:
    - chrome (global API)
  LOADED BY:
    - manifest.json (service_worker)

lib/api.ts
  IMPORTS:
    - @/types.{AnalysisResponse}
  IMPORTED BY:
    - ../Sidebar.svelte

lib/cache.ts
  IMPORTS:
    - idb.{openDB, IDBPDatabase}
    - @/types.{AnalysisResponse, CachedAnalysis}
  IMPORTED BY:
    - ../Sidebar.svelte

lib/utils.ts
  IMPORTS:
    - @/types.{ProductAnalysis, RiskLevel}
  IMPORTED BY:
    - ../components/Sidebar.svelte

types/index.ts
  IMPORTS:
    - (none - pure type definitions)
  IMPORTED BY:
    - ../Sidebar.svelte
    - ../components/Sidebar.svelte
    - ../lib/api.ts
    - ../lib/cache.ts
    - ../lib/utils.ts
```

---

## Directory Structure

```
/extension/
├── package.json                 # NPM dependencies and scripts
├── package-lock.json            # NPM lock file
├── vite.config.ts               # Vite build configuration
├── tsconfig.json                # TypeScript configuration
├── tailwind.config.js           # Tailwind CSS configuration
├── postcss.config.js            # PostCSS configuration
├── .env                         # Environment variables (git-ignored)
├── .env.example                 # Example environment config
├── README.md                    # Extension setup docs
│
├── src/                         # Source code → [src/CLAUDE.md](./src/CLAUDE.md)
│   ├── sidebar.html             # Sidebar HTML template
│   ├── sidebar.ts               # Sidebar app entry point
│   ├── Sidebar.svelte           # Root Svelte component
│   ├── app.css                  # Global styles (Tailwind directives)
│   ├── components/              # UI components → [src/components/CLAUDE.md](./src/components/CLAUDE.md)
│   ├── content/                 # Content scripts → [src/content/CLAUDE.md](./src/content/CLAUDE.md)
│   ├── background/              # Service worker → [src/background/CLAUDE.md](./src/background/CLAUDE.md)
│   ├── lib/                     # Shared libraries → [src/lib/CLAUDE.md](./src/lib/CLAUDE.md)
│   └── types/                   # TypeScript types → [src/types/CLAUDE.md](./src/types/CLAUDE.md)
│
├── public/                      # Static assets → [public/CLAUDE.md](./public/CLAUDE.md)
│   ├── manifest.json            # Chrome Extension Manifest V3
│   ├── icon-16.png              # Extension icon (16x16)
│   ├── icon-48.png              # Extension icon (48x48)
│   ├── icon-128.png             # Extension icon (128x128)
│   └── ICONS_TODO.txt           # TODO note
│
└── dist/                        # Build output (git-ignored)
    ├── manifest.json            # Copied manifest
    ├── background.js            # Compiled background worker
    ├── content.js               # Compiled content script
    ├── src/sidebar.html         # Copied sidebar HTML
    ├── assets/sidebar.css       # Compiled styles
    └── *.png                    # Copied icons
```

---

## Architecture Overview

### Chrome Extension Manifest V3 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  AMAZON PRODUCT PAGE                                             │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Content Script (content.ts)                               │ │
│  │  - Detects product page                                    │ │
│  │  - Calls backend API                                       │ │
│  │  - Injects trigger button                                  │ │
│  │  - Creates sidebar iframe                                  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Sidebar (iframe)                                          │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │  Svelte 5 App                                        │ │ │
│  │  │  - Receives analysis data                            │ │ │
│  │  │  - Displays harm score                               │ │ │
│  │  │  - Shows allergens, PFAS, concerns                   │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ↓
                    ┌──────────────────────────┐
                    │  Background Worker       │
                    │  (background.ts)         │
                    │  - Message routing       │
                    └──────────────────────────┘
                                 │
                                 ↓ HTTP POST
                    ┌──────────────────────────┐
                    │  Backend API             │
                    │  (FastAPI)               │
                    └──────────────────────────┘
```

### Data Flow

1. **User visits Amazon product page**
2. **Content script** detects page, calls backend API
3. **Backend** analyzes product, returns results
4. **Content script** injects trigger button with harm score
5. **User clicks** trigger button
6. **Content script** creates sidebar iframe
7. **Sidebar app** receives analysis data via postMessage
8. **Sidebar** displays detailed results

---

## Key Technologies

- **Framework**: Svelte 5 (with runes)
- **Language**: TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **Storage**: IndexedDB (via idb library)
- **Extension Type**: Chrome Manifest V3
- **HTTP Client**: Fetch API (native)

---

## Related Documentation

- [Root Documentation](../CLAUDE.md) - Complete system overview
- [Source Code](./src/CLAUDE.md) - Extension source details
- [Backend API](../backend/CLAUDE.md) - Backend that extension calls

---

Last Updated: 2025-11-18
