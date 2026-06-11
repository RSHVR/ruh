/**
 * Aritzia site adapter (config-only, JSON-LD backbone — LORE.md ADR-003/ADR-004).
 *
 * Aritzia has no usable client-session reviews endpoint, so `fetchReviews` is
 * omitted (interface segregation — CLAUDE.md SOLID/I). Reviews, where present,
 * arrive via JSON-LD aggregateRating in the scraped product HTML.
 */

import type { SiteAdapter } from './types';

const ARITZIA_HOST = /(^|\.)aritzia\.com$/i;

function aritziaHostname(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return ARITZIA_HOST.test(host) ? host : null;
  } catch {
    return null;
  }
}

export const aritziaAdapter: SiteAdapter = {
  name: 'aritzia',

  matches(url: string): boolean {
    return aritziaHostname(url) !== null;
  },

  isProductPage(url: string): boolean {
    if (!aritziaHostname(url)) return false;
    try {
      const path = new URL(url).pathname;
      return path.includes('/product/');
    } catch {
      return false;
    }
  },
};
