/**
 * Retailer adapter registry (LORE.md ADR-003).
 *
 * Register a new retailer by importing its adapter and adding it to `adapters`.
 * `getAdapter(url)` returns the first adapter whose domain matches, or null
 * (in which case the content script does nothing — graceful, INV-3).
 *
 * NOTE: an adapter only runs if the URL is also injected by the content script,
 * which is gated by `manifest.json` `content_scripts[].matches`. Adding a retailer
 * therefore requires BOTH a registry entry here AND a manifest entry.
 */

import type { SiteAdapter } from './types';
import { amazonAdapter } from './amazon';
import { walmartAdapter } from './walmart';
import { costcoAdapter } from './costco';
import { instacartAdapter } from './instacart';
import { sephoraAdapter } from './sephora';
import { hmAdapter } from './hm';
import { uniqloAdapter } from './uniqlo';
import { sheinAdapter } from './shein';
import { aritziaAdapter } from './aritzia';
import { garageAdapter } from './garage';
import { ikeaAdapter } from './ikea';
import { temuAdapter } from './temu';

const adapters: SiteAdapter[] = [
  amazonAdapter,
  walmartAdapter,
  costcoAdapter,
  instacartAdapter,
  sephoraAdapter,
  hmAdapter,
  uniqloAdapter,
  sheinAdapter,
  aritziaAdapter,
  garageAdapter,
  ikeaAdapter,
  temuAdapter,
  // Register new retailer adapters here (keep in sync with manifest.json).
];

/** Resolve the adapter that handles `url`, or null if none matches. */
export function getAdapter(url: string): SiteAdapter | null {
  return adapters.find((adapter) => adapter.matches(url)) ?? null;
}

/** All registered adapters (exposed for tests/diagnostics). */
export function allAdapters(): readonly SiteAdapter[] {
  return adapters;
}

export type { SiteAdapter, ReviewsResult } from './types';
