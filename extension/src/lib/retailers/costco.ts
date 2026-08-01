/**
 * Costco site adapter (config-only, JSON-LD backbone — LORE.md ADR-003/ADR-004).
 *
 * Serves both costco.com and costco.ca (Canadian shoppers). Costco has no usable
 * client-session reviews endpoint, so `fetchReviews` is omitted (interface
 * segregation — CLAUDE.md SOLID/I). Reviews, where present, arrive via JSON-LD
 * aggregateRating in the scraped product HTML.
 *
 * Product detail pages come in two URL schemes (Costco migrated but category pages
 * still link the legacy form):
 *   - legacy: `/<slug>.product.<id>.html` (a `.product.` segment in the pathname)
 *   - current: `/p/-/<slug>/<id>` (the legacy form 301s here, e.g. `?langId=-24`)
 * Category pages like `/laundry-detergent.html` carry neither marker.
 */

import type { SiteAdapter } from "./types";

const COSTCO_HOST = /(^|\.)costco\.(com|ca)$/i;

function costcoHostname(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return COSTCO_HOST.test(host) ? host : null;
  } catch {
    return null;
  }
}

export const costcoAdapter: SiteAdapter = {
  name: "costco",

  matches(url: string): boolean {
    return costcoHostname(url) !== null;
  },

  isProductPage(url: string): boolean {
    if (!costcoHostname(url)) return false;
    try {
      const path = new URL(url).pathname;
      return path.includes(".product.") || path.startsWith("/p/");
    } catch {
      return false;
    }
  },
};
