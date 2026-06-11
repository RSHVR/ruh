/**
 * Garage Clothing site adapter (LORE.md ADR-003 / ADR-004).
 *
 * Garage (garageclothing.com) is an apparel retailer with JSON-LD Product data;
 * product detail URLs look like `/us/p/<slug>/<sku>.html`. No usable client-session
 * reviews endpoint, so `fetchReviews` is omitted (interface segregation — CLAUDE.md SOLID/I).
 */

import type { SiteAdapter } from './types';

const GARAGE_HOST = /(^|\.)garageclothing\.com$/i;

function garageHostname(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return GARAGE_HOST.test(host) ? host : null;
  } catch {
    return null;
  }
}

export const garageAdapter: SiteAdapter = {
  name: 'garage',

  matches(url: string): boolean {
    return garageHostname(url) !== null;
  },

  isProductPage(url: string): boolean {
    if (!garageHostname(url)) return false;
    try {
      const path = new URL(url).pathname;
      return path.includes('/p/') && path.endsWith('.html');
    } catch {
      return false;
    }
  },
};
