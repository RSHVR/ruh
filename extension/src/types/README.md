# Types & Configuration (`/extension/src/types/`)

## Overview

Type definitions, manifest configuration, and build setup for the Ruh Chrome extension. Uses TypeScript strict mode, Svelte 5, and Chrome Manifest V3.

## TypeScript Types (types/index.ts)

### Interfaces

| Interface | Purpose |
|-----------|---------|
| `ProductAnalysis` | Core analysis result from backend |
| `AllergenDetection` | Individual allergen finding |
| `PFASDetection` | PFAS compound detection |
| `ToxinConcern` | Other harmful substance |
| `AlternativeProduct` | Safer product recommendation |
| `AnalysisResponse` | API response wrapper |
| `CachedAnalysis` | IndexedDB cache entry |
| `ProductInfo` | Basic product metadata |

### Type Safety
- **Strict mode**: Enabled
- **Any usage**: 0
- **Nullable handling**: Proper `string | null` types

## Manifest Configuration (manifest.json)

### Permissions
| Permission | Reason | Minimal? |
|------------|--------|----------|
| `storage` | Cache analysis results | Yes |
| `activeTab` | Access current tab URL | Yes |
| `sidePanel` | Display results in side panel | Yes |

### Host Permissions
| Host | Assessment |
|------|------------|
| `https://*.amazon.com/*` | Required |
| `https://*.amazon.ca/*` | Required |
| `http://localhost:8001/*` | **REMOVE FOR PRODUCTION** |
| `https://ruh-api-*.run.app/*` | Required |

## Production Readiness Issues

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| **CRITICAL** | Missing Content Security Policy | manifest.json | Add restrictive CSP |
| **CRITICAL** | Real API key in .env.example | .env.example:3 | Use placeholder value |
| **HIGH** | localhost in host_permissions | manifest.json:14 | Remove before release |
| **HIGH** | Version mismatch | package.json vs manifest.json | Sync 0.1.0 vs 0.2.0 |
| **MEDIUM** | No chunk splitting | vite.config.ts | Consider vendor splitting |

## Chrome Web Store Compliance

| Requirement | Status |
|-------------|--------|
| Manifest V3 | PASS |
| Description < 132 chars | PASS (77 chars) |
| Required icons (16, 48, 128) | PASS |
| Single purpose | PASS |
| Minimal permissions | PASS |
| No remote code execution | PASS |
| Service worker (no background pages) | PASS |
| **Content Security Policy** | **FAIL - not defined** |

## Build Configuration

### vite.config.ts
- Build target: ES2020
- Source maps: Disabled (production-ready)
- Multiple entry points: content, background, sidepanel

### tsconfig.json
- Strict mode: Enabled
- Module: ESNext
- Path alias: `@/*` -> `./src/*`

## Environment Variables

| Variable | Purpose | Sensitive |
|----------|---------|-----------|
| `VITE_API_BASE_URL` | Backend endpoint | No |
| `VITE_API_KEY` | API auth key | **YES** |
| `VITE_DEBUG` | Debug mode | No |

## Recommended CSP

```json
"content_security_policy": {
  "extension_pages": "script-src 'self'; object-src 'self'; connect-src https://ruh-api-*.run.app"
}
```
