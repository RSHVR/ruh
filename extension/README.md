# Eject Chrome Extension

AI-powered product safety analysis Chrome extension built with Svelte 5.

## Features

- 🛡️ **Real-time Safety Analysis**: Analyzes Amazon products for harmful substances
- ⚠️ **Allergen Detection**: Identifies common allergens and their severity
- 🧪 **PFAS Detection**: Detects "forever chemicals" with health impact explanations
- 📊 **Harm Score**: Clear 0-100 scale showing product safety level
- 💾 **Smart Caching**: 30-day IndexedDB cache for instant results
- 🎨 **Beautiful UI**: Svelte 5 + Tailwind CSS sidebar interface

## Tech Stack

- **Svelte 5** - Reactive UI framework
- **TypeScript** - Type safety
- **Vite** - Fast build tool
- **Tailwind CSS** - Utility-first styling
- **IndexedDB** - Local caching with idb
- **Chrome Extension Manifest V3** - Latest extension format

## Development

### Prerequisites

- Node.js 18+
- npm or yarn
- Backend API running at `http://localhost:8001`

### Install Dependencies

```bash
cd extension
npm install
```

### Build Extension

```bash
# Development build with watch mode
npm run dev

# Production build
npm run build
```

### Load Extension in Chrome

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top-right)
3. Click "Load unpacked"
4. Select the `extension/dist` folder
5. Navigate to any Amazon product page
6. Click the "🛡️ Check Safety" button that appears

## Project Structure

```
extension/
├── src/
│   ├── components/
│   │   └── Sidebar.svelte       # Main sidebar UI component
│   ├── content/
│   │   ├── content.ts           # Content script (runs on Amazon pages)
│   │   └── content.css          # Content script styles
│   ├── background/
│   │   └── background.ts        # Background service worker
│   ├── lib/
│   │   ├── api.ts               # Backend API client
│   │   ├── cache.ts             # IndexedDB cache manager
│   │   └── utils.ts             # Utility functions
│   ├── types/
│   │   └── index.ts             # TypeScript type definitions
│   ├── app.css                  # Global styles with Tailwind
│   ├── Sidebar.svelte           # Sidebar app root component
│   ├── sidebar.ts               # Sidebar entry point
│   └── sidebar.html             # Sidebar HTML
├── public/
│   ├── manifest.json            # Extension manifest
│   └── *.png                    # Extension icons
├── dist/                        # Build output (git-ignored)
├── vite.config.ts              # Vite configuration
├── tailwind.config.js          # Tailwind configuration
└── tsconfig.json               # TypeScript configuration
```

## How It Works

1. **Content Script** (`content.ts`) runs on Amazon product pages
2. Detects product pages and injects a floating "Check Safety" button
3. When clicked, creates an iframe and loads the **Sidebar** (`Sidebar.svelte`)
4. Sidebar checks **IndexedDB cache** for existing analysis
5. If not cached, calls **Backend API** (`/api/analyze`)
6. Displays harm score, allergens, PFAS, and other concerns
7. Caches result for 30 days

## Allowed Domains

Extension only works on:
- `https://*.amazon.com/*`
- `https://*.amazon.ca/*`

This prevents unnecessary activation on other websites (e.g., Netflix).

## Phase 2 Status

✅ Svelte 5 + TypeScript + Vite + Tailwind setup
✅ Manifest V3 configuration
✅ Sidebar UI component with risk level display
✅ Content script for Amazon product detection
✅ Background service worker
✅ API client for backend communication
✅ IndexedDB caching (30-day TTL, per-user)
✅ Floating trigger button on product pages
⏳ E2E testing with Playwright (Phase 2 final step)

## Testing

```bash
# Type checking
npm run check

# Linting
npm run lint

# Format code
npm run format
```

## Next Steps (Phase 3)

- Connect to production backend API
- Add WebSocket for real-time analysis updates
- Implement alternative product recommendations UI
- Add user settings page
- Publish to Chrome Web Store

## License

MIT
