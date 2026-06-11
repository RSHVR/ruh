/**
 * SHEIN site adapter (LORE.md ADR-003).
 *
 * SHEIN heavily bot-walls servers, so there is no usable client-session reviews
 * endpoint — this adapter omits `fetchReviews` (interface segregation, SOLID/I).
 * The content script ships the user's organically-loaded DOM (INV-1) and the
 * backend's SheinScraper config extracts JSON-LD + fabric composition.
 *
 * Product detail pages look like:
 *   https://us.shein.com/some-name-p-12345678.html
 * i.e. the pathname contains `-p-` and ends with `.html`.
 */

import type { SiteAdapter } from './types';

const SHEIN_HOST = /(^|\.)shein\.com$/i;

function sheinHostname(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return SHEIN_HOST.test(host) ? host : null;
  } catch {
    return null;
  }
}

export const sheinAdapter: SiteAdapter = {
  name: 'shein',

  matches(url: string): boolean {
    return sheinHostname(url) !== null;
  },

  isProductPage(url: string): boolean {
    if (!sheinHostname(url)) return false;
    try {
      const path = new URL(url).pathname;
      return path.includes('-p-') && path.endsWith('.html');
    } catch {
      return false;
    }
  },
};
