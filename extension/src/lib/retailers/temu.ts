/**
 * Temu site adapter (config-only, JSON-LD backbone — LORE.md ADR-003/ADR-004).
 *
 * Temu has no usable client-session reviews endpoint, so `fetchReviews` is omitted
 * (interface segregation — CLAUDE.md SOLID/I). Reviews, where present, arrive via
 * JSON-LD aggregateRating in the scraped product HTML. Product detail pages have a
 * pathname containing `-g-` and ending in `.html`
 * (e.g. /some-product-name-g-601099512345678.html).
 */

import type { SiteAdapter } from './types';

const TEMU_HOST = /(^|\.)temu\.com$/i;

function temuHostname(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return TEMU_HOST.test(host) ? host : null;
  } catch {
    return null;
  }
}

export const temuAdapter: SiteAdapter = {
  name: 'temu',

  matches(url: string): boolean {
    return temuHostname(url) !== null;
  },

  isProductPage(url: string): boolean {
    if (!temuHostname(url)) return false;
    try {
      const path = new URL(url).pathname;
      return path.includes('-g-') && path.endsWith('.html');
    } catch {
      return false;
    }
  },
};
