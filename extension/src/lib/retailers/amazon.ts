/**
 * Amazon site adapter (reference implementation).
 *
 * Wraps the existing `lib/amazon` helpers (ASIN extraction + session reviews fetch)
 * so the content script needs no Amazon-specific knowledge. Reproduces the exact
 * behavior the content script had before the SiteAdapter refactor (LORE.md ADR-003).
 */

import { extractASIN, fetchReviews } from '../amazon';
import type { SiteAdapter, ReviewsResult } from './types';

const AMAZON_HOST = /(^|\.)amazon\.(com|ca|co\.uk|de|fr|it|es|com\.au|co\.jp)$/i;

function amazonHostname(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return AMAZON_HOST.test(host) ? host : null;
  } catch {
    return null;
  }
}

export const amazonAdapter: SiteAdapter = {
  name: 'amazon',

  matches(url: string): boolean {
    return amazonHostname(url) !== null;
  },

  isProductPage(url: string): boolean {
    if (!amazonHostname(url)) return false;
    try {
      const path = new URL(url).pathname;
      return path.includes('/dp/') || path.includes('/gp/product/');
    } catch {
      return false;
    }
  },

  async fetchReviews(url: string): Promise<ReviewsResult | null> {
    const asin = extractASIN(url);
    if (!asin) return null;

    const result = await fetchReviews(asin, {
      pages: 5,
      filter: 'all',
      sortBy: 'helpful',
      delayMs: 300,
    });

    if (!result.success) return null;
    const count = (result.html.match(/data-hook="review"/g) || []).length;
    return { html: result.html, count };
  },
};
