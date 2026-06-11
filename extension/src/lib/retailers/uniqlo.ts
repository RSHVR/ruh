/**
 * Uniqlo site adapter (config-only, JSON-LD backbone — LORE.md ADR-003/ADR-004).
 *
 * Uniqlo has no usable client-session reviews endpoint, so `fetchReviews` is omitted
 * (interface segregation — CLAUDE.md SOLID/I). Reviews, where present, arrive via
 * JSON-LD aggregateRating in the scraped product HTML.
 */

import type { SiteAdapter } from './types';

const UNIQLO_HOST = /(^|\.)uniqlo\.com$/i;

function uniqloHostname(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return UNIQLO_HOST.test(host) ? host : null;
  } catch {
    return null;
  }
}

export const uniqloAdapter: SiteAdapter = {
  name: 'uniqlo',

  matches(url: string): boolean {
    return uniqloHostname(url) !== null;
  },

  isProductPage(url: string): boolean {
    if (!uniqloHostname(url)) return false;
    try {
      const path = new URL(url).pathname;
      return path.includes('/products/');
    } catch {
      return false;
    }
  },
};
