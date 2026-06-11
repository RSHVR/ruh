/**
 * Sephora site adapter (config-only, JSON-LD backbone — LORE.md ADR-003/ADR-004).
 *
 * Sephora has no usable client-session reviews endpoint, so `fetchReviews` is omitted
 * (interface segregation — CLAUDE.md SOLID/I). Reviews, where present, arrive via
 * JSON-LD aggregateRating in the scraped product HTML. Product detail pages live under
 * `/product/` (ids look like `-P123456`).
 */

import type { SiteAdapter } from './types';

const SEPHORA_HOST = /(^|\.)sephora\.com$/i;

function sephoraHostname(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return SEPHORA_HOST.test(host) ? host : null;
  } catch {
    return null;
  }
}

export const sephoraAdapter: SiteAdapter = {
  name: 'sephora',

  matches(url: string): boolean {
    return sephoraHostname(url) !== null;
  },

  isProductPage(url: string): boolean {
    if (!sephoraHostname(url)) return false;
    try {
      const path = new URL(url).pathname;
      return path.includes('/product/');
    } catch {
      return false;
    }
  },
};
