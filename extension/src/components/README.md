# UI Components (`/extension/src/components/`)

## Overview

The Ruh Chrome extension UI is built with Svelte 5 using the runes API (`$state`, `$derived`, `$props`, `$effect`). The UI renders in a Chrome Side Panel and displays product safety analysis results.

## Component Hierarchy

```
sidepanel.html
  └── sidepanel.ts (mount point)
      └── SidePanelContainer.svelte (container)
          ├── LoadingScreen.svelte
          └── AnalysisView.svelte
```

## Files

| File | Purpose | Lines | Key Elements |
|------|---------|-------|--------------|
| `SidePanelContainer.svelte` | Container managing Chrome API lifecycle | 274 | State sync, event listeners |
| `AnalysisView.svelte` | Product analysis results display | 621 | Harm score visualization |
| `LoadingScreen.svelte` | Animated loading screen | 194 | Message rotation |
| `sidepanel.html` | HTML entry point | 13 | App mount point |
| `sidepanel.ts` | Svelte bootstrapper | 10 | `mount()` call |
| `app.css` | Global styles | 76 | Font imports, Tailwind |

## SidePanelContainer.svelte

### State ($state)
- `currentTabState: TabAnalysisState | null`
- `currentTabId: number | null`
- `loading: boolean`
- `error: string | null`

### Lifecycle
- **onMount**: Loads tab state, registers storage/tab listeners, sends SIDE_PANEL_OPENED
- **onDestroy**: Removes listeners, sends SIDE_PANEL_CLOSED

## AnalysisView.svelte

### Props
- `analysis: AnalysisResponse | null` (required)
- `loading: boolean` (optional)
- `error: string | null` (optional)

### Key Derived Values
- `harmScore` - Converted from overall_score (100 - score)
- `riskLevel` - Human-readable risk category
- `strokeDashoffset` - SVG donut chart progress

## Production Readiness Issues

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| **Critical** | Non-null assertion on mount target | sidepanel.ts:6 | Add null check |
| **High** | No error boundary | SidePanelContainer | Wrap in try-catch |
| **High** | handleRetry uses page reload | AnalysisView.svelte:51 | Use message passing |
| **Medium** | Console.log in production | multiple | Remove or wrap in DEV check |
| **Medium** | No loading timeout handling | SidePanelContainer | Add 60s timeout message |
| **Low** | Hardcoded strings not i18n | multiple | Extract to messages |

## Accessibility Issues

| Element | Issue | Fix |
|---------|-------|-----|
| Spinner | No accessible label | Add `role="status"` and `aria-label` |
| Donut chart SVG | No text alternative | Add `aria-label` |
| Error messages | No ARIA live region | Add `role="alert"` |
| Retry buttons | No focus visible style | Add `:focus-visible` outline |

## Dependencies

### Svelte 5 Runes Used
- `$state()` - Reactive state
- `$derived()` - Computed values
- `$props()` - Component props
- `$effect()` - Side effects

### Chrome APIs
- `chrome.tabs.query/onActivated/onUpdated`
- `chrome.storage.local/onChanged`
- `chrome.runtime.sendMessage`
