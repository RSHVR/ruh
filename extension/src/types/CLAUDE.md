# TypeScript Type Definitions

## Overview

Central TypeScript type definitions for the extension. Ensures type safety and consistency across all modules.

---

## Type Definitions

### Core Analysis Types

```typescript
// Product analysis result from backend
export interface ProductAnalysis {
  product_name: string;
  brand: string;
  retailer: string;
  ingredients: string[];
  materials: string[];
  overall_score: number;              // 0-100 (higher = safer)
  allergens_detected: Allergen[];
  pfas_detected: PFASCompound[];
  other_concerns: ToxicSubstance[];
  confidence: number;                 // 0.0-1.0
  analyzed_at: string;                // ISO 8601 timestamp
}

// Allergen with severity
export interface Allergen {
  name: string;
  severity: 'low' | 'moderate' | 'high';
  health_effects: string;
}

// PFAS compound
export interface PFASCompound {
  name: string;
  chemical_formula?: string;
  health_effects: string;
  regulatory_status?: string;
}

// Toxic substance
export interface ToxicSubstance {
  name: string;
  toxicity_level: 'low' | 'medium' | 'high';
  description: string;
  health_effects?: string;
}
```

### API Response Types

```typescript
// Complete analysis response from backend
export interface AnalysisResponse {
  analysis: {
    product_analysis: ProductAnalysis;
  };
  alternatives: AlternativeRecommendation[];  // Empty array for now
  cached: boolean;
  url_hash: string;
}

// Alternative product recommendation (future feature)
export interface AlternativeRecommendation {
  product_name: string;
  brand: string;
  retailer: string;
  url: string;
  overall_score: number;
  price?: number;
  rationale: string;
}
```

### Cache Types

```typescript
// Cached analysis entry
export interface CachedAnalysis {
  key: string;               // Product URL or URL hash
  value: AnalysisResponse;   // Complete analysis
  timestamp: number;         // Unix timestamp (ms)
}
```

### UI Types

```typescript
// Risk level for UI rendering
export type RiskLevel = 'low' | 'medium' | 'high';

// Risk class names for CSS
export type RiskClass = 'risk-low' | 'risk-medium' | 'risk-high';
```

### Message Types (Chrome Extension)

```typescript
// Message types for chrome.runtime.sendMessage
export type MessageType =
  | 'OPEN_SIDEBAR'
  | 'CLOSE_SIDEBAR'
  | 'ANALYSIS_DATA';

// Message structure
export interface ExtensionMessage {
  type: MessageType;
  data?: any;
}
```

---

## File-Level Import Relationships

```
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
/extension/src/types/
└── index.ts       # All type definitions
```

---

## File Description

### index.ts
**Purpose**: Central type definitions for the entire extension

**Exports**:
- `ProductAnalysis` - Main product analysis result
- `Allergen` - Allergen with severity
- `PFASCompound` - PFAS chemical
- `ToxicSubstance` - Other harmful substances
- `AnalysisResponse` - Complete API response
- `AlternativeRecommendation` - Product alternative (future)
- `CachedAnalysis` - IndexedDB cache entry
- `RiskLevel` - UI risk level enum
- `RiskClass` - CSS class names
- `MessageType` - Extension message types
- `ExtensionMessage` - Message structure

**No Runtime Code**: Pure type definitions only

**Dependencies**: None (no imports)

**Relationships**:
- Imported by all other modules
- Defines the "contract" between backend and frontend
- Ensures type safety across the extension

---

## Type Alignment with Backend

### Backend Types (Python Pydantic)

```python
# backend/src/domain/models.py
class ProductAnalysis(BaseModel):
    product_name: str
    brand: str
    retailer: str
    ingredients: List[str]
    materials: List[str]
    overall_score: int
    allergens_detected: List[Allergen]
    pfas_detected: List[PFASCompound]
    other_concerns: List[ToxicSubstance]
    confidence: float
    analyzed_at: str
```

### Frontend Types (TypeScript)

```typescript
// extension/src/types/index.ts
export interface ProductAnalysis {
  product_name: string;
  brand: string;
  retailer: string;
  ingredients: string[];
  materials: string[];
  overall_score: number;
  allergens_detected: Allergen[];
  pfas_detected: PFASCompound[];
  other_concerns: ToxicSubstance[];
  confidence: number;
  analyzed_at: string;
}
```

**Alignment**: Field names and types match exactly (snake_case preserved for API consistency).

---

## Type Guards

### Example Type Guard

```typescript
export function isAnalysisResponse(data: any): data is AnalysisResponse {
  return (
    data &&
    typeof data === 'object' &&
    'analysis' in data &&
    'cached' in data &&
    'url_hash' in data
  );
}
```

**Use Case**: Runtime validation of API responses

---

## Future Type Additions

### Planned Types (Not Yet Implemented)

```typescript
// User preferences
export interface UserPreferences {
  theme: 'light' | 'dark';
  notifications: boolean;
  allergen_alerts: string[];  // Allergens user wants to be alerted about
}

// Analytics event
export interface AnalyticsEvent {
  event_type: 'view' | 'click' | 'purchase';
  product_url: string;
  timestamp: number;
}

// Error types
export interface APIError {
  code: string;
  message: string;
  details?: any;
}
```

---

## Type Utilities

### Utility Types

```typescript
// Extract keys of a type
export type KeysOf<T> = keyof T;

// Make all properties optional
export type PartialAnalysis = Partial<ProductAnalysis>;

// Pick specific fields
export type AnalysisSummary = Pick<ProductAnalysis, 'product_name' | 'overall_score'>;

// Omit specific fields
export type PublicAnalysis = Omit<ProductAnalysis, 'confidence'>;
```

---

## Testing with Types

### Type Testing

```typescript
// Compile-time type checking
const analysis: ProductAnalysis = {
  product_name: 'Test',
  brand: 'Test Brand',
  // TypeScript error if any required field is missing
};

// Runtime type checking
if (isAnalysisResponse(data)) {
  // TypeScript knows data is AnalysisResponse here
  console.log(data.analysis.product_analysis.overall_score);
}
```

---

## Related Documentation

- [Extension Source](../CLAUDE.md) - Parent directory
- [Sidebar](../../CLAUDE.md) - Uses types
- [Components](../components/CLAUDE.md) - Uses types
- [Libraries](../lib/CLAUDE.md) - Uses types
- [Backend Models](../../../backend/src/domain/CLAUDE.md) - Backend type definitions

---

Last Updated: 2025-11-18
