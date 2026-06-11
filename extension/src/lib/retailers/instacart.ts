/**
 * Instacart site adapter (LORE.md ADR-003/004/005).
 *
 * Instacart is login-gated and has no usable client-session reviews endpoint, so
 * `fetchReviews` is omitted (interface segregation — CLAUDE.md SOLID/I).
 *
 * Its nutrition facts (and sometimes ingredients) are lazily rendered on scroll into
 * hashed-class DOM with no state blob (archetype-D). `prepareForCapture` scrolls the
 * page so that content is present in the DOM before the content script snapshots it; the
 * backend `InstacartScraper` then extracts it by content pattern (ADR-005).
 */

import type { SiteAdapter } from './types';

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const INSTACART_HOST = /(^|\.)instacart\.com$/i;

function instacartHostname(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return INSTACART_HOST.test(host) ? host : null;
  } catch {
    return null;
  }
}

export const instacartAdapter: SiteAdapter = {
  name: 'instacart',

  matches(url: string): boolean {
    return instacartHostname(url) !== null;
  },

  isProductPage(url: string): boolean {
    if (!instacartHostname(url)) return false;
    try {
      const path = new URL(url).pathname;
      return path.includes('/products/');
    } catch {
      return false;
    }
  },

  async prepareForCapture(): Promise<void> {
    // Nutrition/ingredients render lazily on scroll. Step through the page to trigger
    // it, give it a beat to render, then restore the user's original scroll position.
    const startY = window.scrollY;
    const step = 600;
    const height = document.body.scrollHeight;
    for (let y = 0; y < height; y += step) {
      window.scrollTo(0, y);
      await sleep(120);
    }
    await sleep(1000); // let lazily-rendered detail sections settle
    window.scrollTo(0, startY);
  },
};
