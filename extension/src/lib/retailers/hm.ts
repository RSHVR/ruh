/**
 * H&M site adapter (config-only, JSON-LD backbone — LORE.md ADR-003/ADR-004).
 *
 * H&M has no usable client-session reviews endpoint, so `fetchReviews` is omitted
 * (interface segregation — CLAUDE.md SOLID/I). Reviews, where present, arrive via
 * JSON-LD aggregateRating in the scraped product HTML. Product detail pages have a
 * pathname containing `productpage.` (e.g. /en_us/productpage.1234567001.html).
 */

import type { SiteAdapter } from './types';

const HM_HOST = /(^|\.)hm\.com$/i;

function hmHostname(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return HM_HOST.test(host) ? host : null;
  } catch {
    return null;
  }
}

export const hmAdapter: SiteAdapter = {
  name: 'hm',

  matches(url: string): boolean {
    return hmHostname(url) !== null;
  },

  isProductPage(url: string): boolean {
    if (!hmHostname(url)) return false;
    try {
      const path = new URL(url).pathname;
      return path.includes('productpage.');
    } catch {
      return false;
    }
  },
};
