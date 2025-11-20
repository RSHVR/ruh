# Extension Source Code

## Overview

Source code for the Eject Chrome extension built with Svelte 5, TypeScript, and Vite. Follows component-based architecture with clear separation between content scripts, background workers, and sidebar UI.

---

## Function-Level Flow Diagram

See [extension/CLAUDE.md](../CLAUDE.md) for complete function flows covering:
- Content script injection and API calls
- Background service worker message routing
- Sidebar app initialization and rendering
- API client and cache manager
- Utility functions for UI rendering

---

## File-Level Import Relationships

```
sidebar.ts              (Entry point)
  └─ Sidebar.svelte    (Root component)
      ├─ components/Sidebar.svelte  (UI component)
      ├─ lib/api.ts                 (API client)
      ├─ lib/cache.ts               (Cache manager)
      └─ types/index.ts             (Type definitions)

content/content.ts      (Content script - no file imports)
background/background.ts (Background worker - no file imports)

components/Sidebar.svelte
  ├─ lib/utils.ts       (Utility functions)
  └─ types/index.ts     (Type definitions)

lib/api.ts
  └─ types/index.ts

lib/cache.ts
  └─ types/index.ts

lib/utils.ts
  └─ types/index.ts

types/index.ts          (Pure types - no imports)
```

---

## Directory Structure

```
/extension/src/
├── sidebar.html           # Sidebar HTML template
├── sidebar.ts             # Sidebar app entry point
├── Sidebar.svelte         # Root Svelte component (controller)
├── app.css                # Global styles with Tailwind directives
│
├── components/            # Svelte UI components → [components/CLAUDE.md](./components/CLAUDE.md)
│   └── Sidebar.svelte     # Sidebar UI (presentation)
│
├── content/               # Content scripts → [content/CLAUDE.md](./content/CLAUDE.md)
│   ├── content.ts         # Main content script
│   └── content.css        # Content script styles
│
├── background/            # Background service worker → [background/CLAUDE.md](./background/CLAUDE.md)
│   └── background.ts      # Service worker script
│
├── lib/                   # Shared libraries → [lib/CLAUDE.md](./lib/CLAUDE.md)
│   ├── api.ts             # Backend API client
│   ├── cache.ts           # IndexedDB cache manager
│   └── utils.ts           # Utility functions
│
└── types/                 # TypeScript types → [types/CLAUDE.md](./types/CLAUDE.md)
    └── index.ts           # Type definitions
```

---

## Architecture Pattern: Separation of Concerns

### Content Script Isolation

**Why no imports in content.ts?**
- Avoids bundling issues with Chrome extension content scripts
- Reduces bundle size injected into pages
- Prevents conflicts with page's own code
- All utilities are inlined

### Controller/Presenter Split

**Sidebar.svelte vs components/Sidebar.svelte**:
- **Sidebar.svelte** (Controller) - State management, message handling, API calls
- **components/Sidebar.svelte** (Presenter) - Pure UI rendering, no business logic

**Benefits**:
- Testable presentation layer
- Reusable UI components
- Clear separation of concerns

### Type Safety

**types/index.ts**:
- Central type definitions
- Shared across all modules
- Ensures type consistency between frontend and backend

---

## Build Configuration

### Vite Configuration (vite.config.ts)

**Key Settings**:
```typescript
{
  build: {
    rollupOptions: {
      input: {
        sidebar: 'src/sidebar.html',
        content: 'src/content/content.ts',
        background: 'src/background/background.ts'
      },
      output: {
        entryFileNames: '[name].js',
        chunkFileNames: '[name].js',
        assetFileNames: 'assets/[name].[ext]'
      }
    }
  }
}
```

**Why multiple entry points?**
- Content script: Injected into Amazon pages
- Background worker: Runs in extension context
- Sidebar: Runs in iframe with full Svelte app

### TypeScript Configuration (tsconfig.json)

**Key Settings**:
- Target: ES2020
- Module: ESNext
- Strict mode enabled
- Path aliases: `@/*` → `src/*`

---

## File Descriptions

### sidebar.html
**Purpose**: HTML template for sidebar iframe

**Content**:
- Minimal HTML shell
- Loads `sidebar.js` (compiled from sidebar.ts)
- Includes `#app` mount point for Svelte

### sidebar.ts
**Purpose**: Sidebar application entry point

**Responsibilities**:
- Initializes Svelte app
- Mounts root component to DOM

### Sidebar.svelte
**Purpose**: Root Svelte component (controller)

**Responsibilities**:
- Message passing with content script
- State management (analysis data)
- API calls and caching
- Delegates UI rendering to components/Sidebar.svelte

### app.css
**Purpose**: Global styles

**Content**:
- Tailwind CSS directives (@tailwind base, components, utilities)
- Custom CSS variables
- Global resets

---

## Data Flow Architecture

```
Content Script (content.ts)
  ↓ postMessage
Sidebar Controller (Sidebar.svelte)
  ↓ props
Sidebar UI (components/Sidebar.svelte)
  ↓ uses
Utilities (lib/utils.ts)
```

**Flow**:
1. Content script fetches analysis from backend
2. Content script sends data via postMessage to iframe
3. Root Sidebar.svelte receives message, updates state
4. State passed as props to components/Sidebar.svelte
5. UI component renders using utility functions

---

## Related Documentation

- [Extension Overview](../CLAUDE.md) - Extension architecture
- [Components](./components/CLAUDE.md) - Svelte UI components
- [Content Scripts](./content/CLAUDE.md) - Content script implementation
- [Background Worker](./background/CLAUDE.md) - Service worker
- [Libraries](./lib/CLAUDE.md) - Shared utilities
- [Types](./types/CLAUDE.md) - TypeScript definitions

---

Last Updated: 2025-11-18
