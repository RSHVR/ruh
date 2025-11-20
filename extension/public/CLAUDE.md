# Public Assets

## Overview

Static assets for the Chrome extension: manifest configuration, icons, and other public files that are copied to the build output.

---

## Directory Structure

```
/extension/public/
├── manifest.json      # Chrome Extension Manifest V3 configuration
├── icon-16.png        # Extension icon (16x16px)
├── icon-48.png        # Extension icon (48x48px)
├── icon-128.png       # Extension icon (128x128px)
└── ICONS_TODO.txt     # TODO note about placeholder icons
```

---

## Files Description

### manifest.json
**Purpose**: Chrome Extension Manifest V3 configuration

**Key Configuration**:

```json
{
  "manifest_version": 3,
  "name": "Eject - Product Safety Analyzer",
  "version": "1.0.0",
  "description": "AI-powered product safety analysis for allergens, PFAS, and harmful substances",

  "permissions": [
    "storage",           // For IndexedDB cache
    "activeTab"          // For content script injection
  ],

  "host_permissions": [
    "https://*.amazon.com/*",  // Access to Amazon pages
    "https://*.amazon.co.uk/*", // International Amazon sites
    "https://*.amazon.ca/*",
    "https://*.amazon.de/*"
  ],

  "action": {
    "default_popup": "",  // No popup (extension activates on Amazon pages)
    "default_icon": {
      "16": "icon-16.png",
      "48": "icon-48.png",
      "128": "icon-128.png"
    }
  },

  "background": {
    "service_worker": "background.js",  // Compiled from src/background/background.ts
    "type": "module"
  },

  "content_scripts": [
    {
      "matches": [
        "https://*.amazon.com/*",
        "https://*.amazon.co.uk/*",
        "https://*.amazon.ca/*",
        "https://*.amazon.de/*"
      ],
      "js": ["content.js"],         // Compiled from src/content/content.ts
      "css": ["content.css"],       // Compiled from src/content/content.css
      "run_at": "document_idle"     // Inject after page load
    }
  ],

  "web_accessible_resources": [
    {
      "resources": ["src/sidebar.html", "assets/*"],  // Accessible by content scripts
      "matches": ["https://*.amazon.com/*"]
    }
  ],

  "icons": {
    "16": "icon-16.png",
    "48": "icon-48.png",
    "128": "icon-128.png"
  }
}
```

**Key Sections**:

**manifest_version: 3**
- Uses Chrome Extension Manifest V3 (required for new extensions)
- Service workers instead of background pages
- Improved security and performance

**permissions**
- `storage` - Access to chrome.storage API for caching
- `activeTab` - Access to currently active tab

**host_permissions**
- Grants access to Amazon domains (*.amazon.com, *.amazon.co.uk, etc.)
- Required for content script injection

**action**
- Extension icon configuration
- No default popup (extension is activated on Amazon pages)

**background**
- Service worker: `background.js` (from src/background/background.ts)
- Type: module (ES modules support)

**content_scripts**
- Matches: Amazon product page URLs
- JS: `content.js` (from src/content/content.ts)
- CSS: `content.css` (from src/content/content.css)
- run_at: `document_idle` (inject after page fully loads)

**web_accessible_resources**
- Makes sidebar.html and assets accessible to content scripts
- Required for iframe injection

---

### Icons

#### icon-16.png
**Purpose**: Extension toolbar icon (small size)

**Dimensions**: 16x16 pixels

**Usage**:
- Extension toolbar
- Browser extension menu
- Small displays

**Status**: ⚠️ Placeholder (see ICONS_TODO.txt)

#### icon-48.png
**Purpose**: Extension management icon (medium size)

**Dimensions**: 48x48 pixels

**Usage**:
- Extension management page (chrome://extensions/)
- Extension details view
- Default size for most displays

**Status**: ⚠️ Placeholder (see ICONS_TODO.txt)

#### icon-128.png
**Purpose**: Chrome Web Store icon (large size)

**Dimensions**: 128x128 pixels

**Usage**:
- Chrome Web Store listing
- Installation dialog
- High-resolution displays

**Status**: ⚠️ Placeholder (see ICONS_TODO.txt)

---

### ICONS_TODO.txt
**Purpose**: Development note about placeholder icons

**Content**: Reminder to replace placeholder icons with production-ready designs

**Status**: Development placeholder

---

## Manifest V3 Migration Notes

### Key Differences from Manifest V2

**Background Pages → Service Workers**:
- V2: Persistent background page
- V3: Service worker (event-driven, terminates when idle)

**host_permissions**:
- V2: Combined with `permissions`
- V3: Separate `host_permissions` array

**web_accessible_resources**:
- V2: Array of strings
- V3: Array of objects with `resources` and `matches`

**Content Security Policy**:
- V3: Stricter CSP by default
- No inline scripts allowed

---

## Build Process

### Vite Configuration

**Copy public/ to dist/**:
```typescript
// vite.config.ts
export default {
  publicDir: 'public',  // Copies all files from public/ to dist/
  build: {
    outDir: 'dist'
  }
}
```

**Build Output**:
```
dist/
├── manifest.json      (copied from public/)
├── icon-16.png        (copied from public/)
├── icon-48.png        (copied from public/)
├── icon-128.png       (copied from public/)
├── background.js      (compiled from src/background/background.ts)
├── content.js         (compiled from src/content/content.ts)
├── content.css        (compiled from src/content/content.css)
├── src/sidebar.html   (copied from src/)
└── assets/            (compiled Svelte app and styles)
```

---

## Chrome Web Store Requirements

### Icon Requirements

**Sizes Required**:
- 16x16 - Extension toolbar icon
- 48x48 - Extension management page
- 128x128 - Chrome Web Store and installation

**Format**: PNG (with transparency)

**Design Guidelines**:
- Clear and recognizable at small sizes
- Consistent branding across sizes
- High contrast for visibility
- No text in icons (unreadable at small sizes)

### Manifest Requirements

**Required Fields**:
- `manifest_version`: Must be 3
- `name`: Extension name (max 45 characters)
- `version`: Semantic versioning (e.g., "1.0.0")
- `description`: Short description (max 132 characters)
- `icons`: At least 128x128 icon

**Recommended Fields**:
- `homepage_url`: Extension website
- `author`: Developer name/email
- `update_url`: Auto-update URL (for self-hosting)

---

## Security Considerations

### Content Security Policy (CSP)

**Default CSP** (Manifest V3):
```
script-src 'self'; object-src 'self'
```

**Implications**:
- No inline scripts allowed
- No eval() or new Function()
- All scripts must be in separate files

### Host Permissions

**Current Permissions**:
- `https://*.amazon.com/*`
- `https://*.amazon.co.uk/*`
- `https://*.amazon.ca/*`
- `https://*.amazon.de/*`

**Why Needed**:
- Content script injection into Amazon pages
- Product page detection and analysis triggering

**Privacy**:
- Extension only activates on Amazon product pages
- No data collection from non-Amazon sites
- API calls only when user explicitly triggers analysis

---

## Testing Extension Loading

### Load Unpacked Extension

1. Build extension: `npm run build`
2. Navigate to `chrome://extensions/`
3. Enable "Developer mode"
4. Click "Load unpacked"
5. Select `extension/dist` directory

### Verify Manifest

- Check for manifest errors in chrome://extensions/
- Verify icons appear correctly
- Test content script injection on Amazon pages

---

## Related Documentation

- [Extension Overview](../CLAUDE.md) - Extension architecture
- [Content Script](../src/content/CLAUDE.md) - Content script that uses manifest configuration
- [Background Worker](../src/background/CLAUDE.md) - Service worker defined in manifest

---

Last Updated: 2025-11-18
