# Libraries (`/extension/src/lib/`)

## Overview

Shared utility modules for the Ruh Chrome extension providing API communication, caching, UI messages, utility functions, and tab state synchronization.

## Files

| File | Purpose | Lines | Exports |
|------|---------|-------|---------|
| `api.ts` | HTTP client for backend API | 96 | `EjectAPI`, `api` singleton |
| `cache.ts` | IndexedDB analysis caching | 93 | `CacheManager`, `cache` singleton |
| `messages.ts` | Loading screen messages | 39 | `wittyMessages`, `progressMessages` |
| `utils.ts` | Utility functions | 103 | 8 functions |
| `storage-sync.ts` | Chrome storage tab state | 82 | Types + 6 functions |

## api.ts - EjectAPI

### Configuration
- Base URL: `VITE_API_BASE_URL` or `http://localhost:8001`
- API Key: `VITE_API_KEY` (Bearer auth)

### Methods
- `analyzeProduct(productUrl, allergenProfile)` - POST /api/analyze
- `healthCheck()` - GET /api/health

**Note**: Singleton `api` is NOT used - content.ts duplicates this logic inline.

## cache.ts - CacheManager

### Configuration
- Storage: IndexedDB (`ruh-cache` database)
- TTL: 30 days

### Methods
- `get(url)` - Retrieve cached analysis
- `set(url, data)` - Store analysis
- `clearExpired()` - Batch delete old entries

**Note**: Singleton `cache` is NOT used anywhere in the codebase.

## utils.ts Functions

| Function | Purpose | Used |
|----------|---------|------|
| `getHarmScore(score)` | Convert to harm score (100 - score) | Yes |
| `getRiskLevel(harmScore)` | Map to risk category | Yes |
| `getRiskClass(riskLevel)` | Get CSS class | Yes |
| `getRiskColor(riskLevel)` | Get hex color | No |
| `isAmazonProductPage(url)` | Detect Amazon product URL | Yes (also duplicated in content.ts) |
| `extractASIN(url)` | Extract Amazon ASIN | No |
| `formatTimeAgo(timestamp)` | Relative time string | Yes |
| `getUserId()` | Get/create persistent UUID | No |

## storage-sync.ts

### Types
- `AnalysisStatus`: `'idle' | 'loading' | 'complete' | 'error'`
- `TabAnalysisState`: Full tab state interface

### Functions
- `getTabStorageKey(tabId)` - Generate storage key
- `setTabAnalysis(tabId, state)` - Store/update state
- `getTabAnalysis(tabId)` - Retrieve state
- `getActiveTab()` - Get current tab

## Production Readiness Issues

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| **Critical** | No request timeout | api.ts:54 | Add AbortController (30-60s) |
| **Critical** | No retry logic | api.ts:54 | Exponential backoff (3 attempts) |
| **High** | api.ts singleton unused | content.ts | Use singleton, remove duplication |
| **High** | cache.ts singleton unused | - | Integrate or remove dead code |
| **High** | No error handling in cache | cache.ts | Add try/catch blocks |
| **High** | clearExpired() never called | cache.ts | Call on startup |
| **High** | Duplicate isAmazonProductPage | content.ts vs utils.ts | Import from utils |
| **Medium** | No API response validation | api.ts:65 | Add Zod validation |
| **Medium** | formatTimeAgo can throw | utils.ts:79 | Add try/catch |

## Dependencies

### Runtime
- `idb` (^8.0.0) - IndexedDB wrapper

### Chrome APIs
- `chrome.storage.local`
- `chrome.tabs.query`
