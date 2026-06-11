/**
 * IKEA site adapter (config-only, JSON-LD backbone — LORE.md ADR-003/ADR-004).
 *
 * IKEA has no usable client-session reviews endpoint, so `fetchReviews` is omitted
 * (interface segregation — CLAUDE.md SOLID/I). Reviews, where present, arrive via
 * JSON-LD aggregateRating in the scraped product HTML.
 */

import type { SiteAdapter } from './types';

const IKEA_HOST = /(^|\.)ikea\.com$/i;

function ikeaHostname(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return IKEA_HOST.test(host) ? host : null;
  } catch {
    return null;
  }
}

export const ikeaAdapter: SiteAdapter = {
  name: 'ikea',

  matches(url: string): boolean {
    return ikeaHostname(url) !== null;
  },

  isProductPage(url: string): boolean {
    if (!ikeaHostname(url)) return false;
    try {
      const path = new URL(url).pathname;
      return path.includes('/p/');
    } catch {
      return false;
    }
  },
};
