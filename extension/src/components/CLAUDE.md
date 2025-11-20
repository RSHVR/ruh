# Svelte UI Components

## Overview

Presentation layer components for the Eject extension sidebar. Pure UI rendering with no business logic or API calls.

---

## Function-Level Flow Diagram

### Sidebar UI Component

```
📄 Sidebar.svelte (receives analysis prop from parent)
  │
  ├─ Reactive Computations:
  │   ├─ productAnalysis = analysis.analysis.product_analysis
  │   ├─ harmScore = getHarmScore(productAnalysis)
  │   ├─ riskLevel = getRiskLevel(harmScore)
  │   └─ riskClass = getRiskClass(riskLevel)
  │
  ├─ Renders: Header Section
  │   ├─ Product name
  │   ├─ Brand name
  │   └─ Close button
  │
  ├─ Renders: Harm Score Section
  │   ├─ Donut chart SVG
  │   │   ├─ Circle (background)
  │   │   ├─ Circle (foreground with stroke-dasharray based on harmScore)
  │   │   └─ Text (harmScore value)
  │   ├─ Risk level badge (risk-low/medium/high class)
  │   └─ Overall score (100 - harmScore)
  │
  ├─ Renders: Allergens Section (if any detected)
  │   └─ For each allergen:
  │       ├─ Name
  │       ├─ Severity badge
  │       └─ Health effects
  │
  ├─ Renders: PFAS Section (if any detected)
  │   └─ For each PFAS compound:
  │       ├─ Name
  │       ├─ Chemical formula (if available)
  │       └─ Health effects
  │
  ├─ Renders: Other Concerns Section (if any)
  │   └─ For each concern:
  │       ├─ Substance name
  │       ├─ Toxicity level badge
  │       └─ Description
  │
  └─ Renders: Footer
      ├─ Confidence score
      └─ Analyzed timestamp (formatted with formatTimeAgo)
```

---

## File-Level Import Relationships

```
Sidebar.svelte
  IMPORTS:
    - @/types.{AnalysisResponse}
    - @/lib/utils.{getHarmScore, getRiskLevel, getRiskClass, formatTimeAgo}
  IMPORTED BY:
    - ../Sidebar.svelte (root component)
```

---

## Directory Structure

```
/extension/src/components/
└── Sidebar.svelte     # Main sidebar UI component
```

---

## File Description

### Sidebar.svelte
**Purpose**: Presentation component for product analysis results

**Props**:
- `analysis: AnalysisResponse` - Complete analysis data from backend

**Computed Values**:
- `productAnalysis` - Extracted from analysis.analysis.product_analysis
- `harmScore` - Calculated from overall_score (100 - overall_score)
- `riskLevel` - Derived from harmScore ('low' | 'medium' | 'high')
- `riskClass` - CSS class name for risk level styling

**Dependencies**:
- `lib/utils.ts` - Utility functions for calculations
- `types/index.ts` - TypeScript type definitions

**Relationships**:
- Receives props from `../Sidebar.svelte`
- Uses utilities from `lib/utils.ts`
- Pure presentation - no API calls or state management

---

## UI Components Breakdown

### Donut Chart Visualization

**SVG Structure**:
```svelte
<svg viewBox="0 0 100 100">
  <!-- Background circle -->
  <circle cx="50" cy="50" r="40" fill="none" stroke="#e5e7eb" stroke-width="12" />

  <!-- Foreground circle (progress) -->
  <circle
    cx="50" cy="50" r="40"
    fill="none"
    stroke={strokeColor}
    stroke-width="12"
    stroke-dasharray={circumference}
    stroke-dashoffset={offset}
    transform="rotate(-90 50 50)"
  />

  <!-- Score text -->
  <text x="50" y="50" text-anchor="middle" dy=".3em">
    {harmScore}
  </text>
</svg>
```

**Calculation**:
- `circumference = 2 * Math.PI * 40` (circle radius)
- `offset = circumference - (harmScore / 100) * circumference`
- `strokeColor` - Based on risk level (green/yellow/red)

### Risk Level Badge

**Classes**:
- `risk-low` - Green background (#10b981)
- `risk-medium` - Yellow background (#f59e0b)
- `risk-high` - Red background (#ef4444)

**Display Text**:
- Low Risk (0-30)
- Medium Risk (31-60)
- High Risk (61-100)

### Allergen List

**Structure**:
```svelte
{#each productAnalysis.allergens_detected as allergen}
  <div class="allergen-item">
    <div class="allergen-name">{allergen.name}</div>
    <span class="severity-badge severity-{allergen.severity}">
      {allergen.severity}
    </span>
    <div class="allergen-effects">{allergen.health_effects}</div>
  </div>
{/each}
```

### PFAS List

**Structure**:
```svelte
{#each productAnalysis.pfas_detected as pfas}
  <div class="pfas-item">
    <div class="pfas-name">{pfas.name}</div>
    {#if pfas.chemical_formula}
      <div class="pfas-formula">{pfas.chemical_formula}</div>
    {/if}
    <div class="pfas-effects">{pfas.health_effects}</div>
  </div>
{/each}
```

---

## Styling

**Tailwind CSS Classes Used**:
- Layout: `flex`, `flex-col`, `grid`, `space-y-*`
- Typography: `text-*`, `font-*`, `leading-*`
- Colors: `bg-*`, `text-*`, `border-*`
- Spacing: `p-*`, `m-*`, `gap-*`
- Borders: `rounded-*`, `border-*`

**Custom Styles** (in app.css):
- `.eject-sidebar-iframe` - Sidebar positioning
- `.risk-low`, `.risk-medium`, `.risk-high` - Risk level colors
- `.severity-low`, `.severity-moderate`, `.severity-high` - Severity colors

---

## Component Design Principles

### Pure Presentation

**No business logic**:
- All calculations delegated to `lib/utils.ts`
- No API calls
- No state management
- Receives all data via props

**Why?**:
- Testable in isolation
- Reusable across different contexts
- Clear separation of concerns

### Reactive Updates

**Svelte reactivity**:
- Prop changes automatically trigger re-renders
- Computed values update reactively
- No manual DOM manipulation

### Accessibility

**Features**:
- Semantic HTML (headings, lists, sections)
- ARIA labels on interactive elements
- Keyboard navigation support
- High contrast color schemes

---

## Related Documentation

- [Extension Source](../CLAUDE.md) - Parent directory
- [Utilities](../lib/CLAUDE.md) - Helper functions used by component
- [Types](../types/CLAUDE.md) - TypeScript definitions

---

Last Updated: 2025-11-18
