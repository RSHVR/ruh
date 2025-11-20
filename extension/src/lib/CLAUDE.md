# Shared Libraries

## Overview

Shared utility libraries for the extension: API client, IndexedDB cache manager, and UI utility functions.

---

## Function-Level Flow Diagram

### API Client

```
📄 api.ts::EjectAPI.analyzeProduct(productUrl: string) → Promise<AnalysisResponse>
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
  ├─ IF response.ok:
  │   ├─ Parses: data = await response.json()
  │   └─ Returns: data as AnalysisResponse
  │
  └─ IF !response.ok:
      ├─ Throws: Error(`API error: ${response.status}`)
      └─ Returns: never
```

### Cache Manager

```
📄 cache.ts::CacheManager.init() → Promise<void>
  ├─ Calls: openDB('eject-cache', 1, {
  │          upgrade(db) {
  │            if (!db.objectStoreNames.contains('analyses')) {
  │              db.createObjectStore('analyses');
  │            }
  │          }
  │        })
  ├─ Stores: this.db = db
  └─ Returns: void

📄 cache.ts::CacheManager.get(key: string) → Promise<AnalysisResponse | null>
  ├─ Opens: db = await this.ensureDb()
  ├─ Reads: item = await db.get('analyses', key)
  │
  ├─ IF item exists:
  │   ├─ Calculates: age = Date.now() - item.timestamp
  │   ├─ Checks: if (age < 30 * 24 * 60 * 60 * 1000)  // 30 days
  │   │   └─ Returns: item.value
  │   └─ ELSE (expired):
  │       ├─ Calls: this.delete(key)
  │       └─ Returns: null
  │
  └─ ELSE (not found):
      └─ Returns: null

📄 cache.ts::CacheManager.set(key: string, value: AnalysisResponse) → Promise<void>
  ├─ Opens: db = await this.ensureDb()
  ├─ Stores: db.put('analyses', {
  │           key,
  │           value,
  │           timestamp: Date.now()
  │         }, key)
  └─ Returns: void

📄 cache.ts::CacheManager.delete(key: string) → Promise<void>
  ├─ Opens: db = await this.ensureDb()
  ├─ Deletes: db.delete('analyses', key)
  └─ Returns: void

📄 cache.ts::CacheManager.clear() → Promise<void>
  ├─ Opens: db = await this.ensureDb()
  ├─ Clears: db.clear('analyses')
  └─ Returns: void
```

### Utility Functions

```
📄 utils.ts::getHarmScore(analysis: ProductAnalysis) → number
  └─ Returns: 100 - analysis.overall_score

📄 utils.ts::getRiskLevel(score: number) → RiskLevel
  ├─ IF score < 30: Returns 'low'
  ├─ IF score < 60: Returns 'medium'
  └─ IF score >= 60: Returns 'high'

📄 utils.ts::getRiskClass(level: RiskLevel) → string
  ├─ IF level == 'low': Returns 'risk-low'
  ├─ IF level == 'medium': Returns 'risk-medium'
  └─ IF level == 'high': Returns 'risk-high'

📄 utils.ts::formatTimeAgo(timestamp: string) → string
  ├─ Parses: date = new Date(timestamp)
  ├─ Calculates: diff = now - date (in milliseconds)
  │
  ├─ Converts: seconds, minutes, hours, days
  │
  ├─ IF < 1 minute: Returns 'just now'
  ├─ IF < 1 hour: Returns '{n} minutes ago'
  ├─ IF < 1 day: Returns '{n} hours ago'
  ├─ IF < 7 days: Returns '{n} days ago'
  └─ ELSE: Returns date.toLocaleDateString()
```

---

## File-Level Import Relationships

```
api.ts
  IMPORTS:
    - @/types.{AnalysisResponse}
  IMPORTED BY:
    - ../Sidebar.svelte

cache.ts
  IMPORTS:
    - idb.{openDB, IDBPDatabase}
    - @/types.{AnalysisResponse, CachedAnalysis}
  IMPORTED BY:
    - ../Sidebar.svelte

utils.ts
  IMPORTS:
    - @/types.{ProductAnalysis, RiskLevel}
  IMPORTED BY:
    - ../components/Sidebar.svelte
```

---

## Directory Structure

```
/extension/src/lib/
├── api.ts          # Backend API client
├── cache.ts        # IndexedDB cache manager
└── utils.ts        # UI utility functions
```

---

## Files Description

### api.ts
**Purpose**: Backend API client for product analysis

**Exports**:
- `api` - Singleton instance of EjectAPI
- `EjectAPI` class

**Methods**:
- `analyzeProduct(url)` - POST /api/analyze

**Environment Variables**:
- `VITE_API_BASE_URL` - Backend API base URL
- `VITE_API_KEY` - API authentication key

**Dependencies**:
- types/index.ts

**Relationships**:
- Used by Sidebar.svelte for API calls
- Wraps fetch() with authentication
- Returns typed AnalysisResponse

### cache.ts
**Purpose**: IndexedDB cache manager for analysis results

**Exports**:
- `cache` - Singleton instance of CacheManager
- `CacheManager` class

**Database Schema**:
- Database: `eject-cache`
- Version: 1
- Object Store: `analyses`
- Structure: `{ key: string, value: AnalysisResponse, timestamp: number }`

**Cache TTL**: 30 days

**Methods**:
- `init()` - Initialize database
- `get(key)` - Retrieve cached analysis
- `set(key, value)` - Store analysis
- `delete(key)` - Delete specific entry
- `clear()` - Clear all cached analyses

**Dependencies**:
- idb (IndexedDB library)
- types/index.ts

**Relationships**:
- Used by Sidebar.svelte for caching
- Reduces API calls for repeated product views
- Automatic expiration after 30 days

### utils.ts
**Purpose**: UI utility functions for rendering

**Exports**:
- `getHarmScore()` - Convert overall_score to harm score
- `getRiskLevel()` - Determine risk level from score
- `getRiskClass()` - Get CSS class for risk level
- `formatTimeAgo()` - Human-readable timestamp

**No Side Effects**: Pure functions only

**Dependencies**:
- types/index.ts

**Relationships**:
- Used by components/Sidebar.svelte
- Provides consistent calculations across UI
- Encapsulates business logic for display

---

## API Client Details

### Authentication

**Method**: Bearer token in Authorization header

**Format**: `Authorization: Bearer ${API_KEY}`

**Error Handling**:
- Throws Error on non-200 responses
- Caller must handle try/catch

### Environment Configuration

**Development** (.env.local):
```
VITE_API_BASE_URL=http://localhost:8000
VITE_API_KEY=dev-key-12345
```

**Production** (.env):
```
VITE_API_BASE_URL=https://api.eject.app
VITE_API_KEY=prod-key-xxxxx
```

---

## Cache Manager Details

### IndexedDB Structure

**Why IndexedDB?**
- Larger storage than localStorage (100s of MB vs 10 MB)
- Async API (doesn't block UI)
- Structured data storage
- Built-in indexing

**Object Store**:
```typescript
{
  key: string,          // Product URL or URL hash
  value: AnalysisResponse,  // Complete analysis from backend
  timestamp: number     // Unix timestamp (ms)
}
```

### Cache Strategy

**Cache Hit**:
1. Check if entry exists
2. Check if timestamp < 30 days old
3. Return cached value

**Cache Miss**:
1. Fetch from backend API
2. Store in cache with current timestamp
3. Return fresh value

**Expiration**:
- Automatic: Entries older than 30 days are ignored and deleted
- Manual: `cache.clear()` clears all entries

---

## Utility Functions Details

### Risk Level Thresholds

| Harm Score | Risk Level | Color |
|------------|------------|-------|
| 0-29 | Low | Green (#10b981) |
| 30-59 | Medium | Yellow (#f59e0b) |
| 60-100 | High | Red (#ef4444) |

### Time Formatting

**Examples**:
- 30 seconds → "just now"
- 5 minutes → "5 minutes ago"
- 2 hours → "2 hours ago"
- 3 days → "3 days ago"
- 10 days → "11/08/2025" (formatted date)

---

## Testing Strategies

### API Client Testing

**Mock fetch**:
```typescript
global.fetch = vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ analysis: {...} })
});
```

### Cache Manager Testing

**Use fake-indexeddb**:
```typescript
import 'fake-indexeddb/auto';
```

### Utils Testing

**Pure functions** - Easy to test:
```typescript
expect(getHarmScore({ overall_score: 70 })).toBe(30);
expect(getRiskLevel(25)).toBe('low');
```

---

## Related Documentation

- [Extension Source](../CLAUDE.md) - Parent directory
- [Sidebar](../../CLAUDE.md) - Uses api and cache
- [Components](../components/CLAUDE.md) - Uses utils
- [Types](../types/CLAUDE.md) - Type definitions

---

Last Updated: 2025-11-18
