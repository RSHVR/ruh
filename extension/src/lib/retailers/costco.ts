/**
 * Costco site adapter (config-only, JSON-LD backbone — LORE.md ADR-003/ADR-004).
 *
 * Costco has no usable client-session reviews endpoint, so `fetchReviews` is omitted
 * (interface segregation — CLAUDE.md SOLID/I). Reviews, where present, arrive via
 * JSON-LD aggregateRating in the scraped product HTML. Product detail pages carry a
 * `.product.` segment in the pathname (e.g. `/some-item.product.100334757.html`).
 */

import type { SiteAdapter } from './types';

const COSTCO_HOST = /(^|\.)costco\.com$/i;

function costcoHostname(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return COSTCO_HOST.test(host) ? host : null;
  } catch {
    return null;
  }
}

export const costcoAdapter: SiteAdapter = {
  name: 'costco',

  matches(url: string): boolean {
    return costcoHostname(url) !== null;
  },

  isProductPage(url: string): boolean {
    if (!costcoHostname(url)) return false;
    try {
      const path = new URL(url).pathname;
      return path.includes('.product.');
    } catch {
      return false;
    }
  },
};
