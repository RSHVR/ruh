/**
 * Walmart site adapter (config-driven, no reviews).
 *
 * Serves both walmart.com and walmart.ca (Canadian shoppers). Walmart bot-walls
 * server-side automation, so the client-HTML path is the only real surface
 * (LORE.md INV-1). This adapter only needs `matches` + `isProductPage` — there is
 * no usable client-session reviews endpoint, so `fetchReviews` is omitted
 * (interface segregation, ADR-003).
 *
 * Product detail pages carry an `/ip/` segment anywhere in the path:
 *   - walmart.com: `/ip/<slug>/<numeric-id>`
 *   - walmart.ca:  `/en/ip/<slug>/<id>` or `/fr/ip/<slug>/<id>` (ids alphanumeric)
 * Browse/category pages (`/en/browse/...`) have no `/ip/` segment.
 */

import type { SiteAdapter } from "./types";

const WALMART_HOST = /(^|\.)walmart\.(com|ca)$/i;

function walmartHostname(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return WALMART_HOST.test(host) ? host : null;
  } catch {
    return null;
  }
}

export const walmartAdapter: SiteAdapter = {
  name: "walmart",

  matches(url: string): boolean {
    return walmartHostname(url) !== null;
  },

  isProductPage(url: string): boolean {
    if (!walmartHostname(url)) return false;
    try {
      const path = new URL(url).pathname;
      return path.includes("/ip/");
    } catch {
      return false;
    }
  },
};
