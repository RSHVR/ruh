/**
 * Amazon site adapter.
 *
 * Wraps the `lib/amazon` ASIN helper so the content script needs no Amazon-specific
 * knowledge (LORE.md ADR-003). `fetchReviews` is omitted: Amazon killed anonymous
 * review pagination — `/product-reviews/<ASIN>/` now 302s to `/ap/signin` — so there
 * is no usable client-session reviews endpoint (interface segregation, CLAUDE.md
 * SOLID/I). The product page's embedded `data-hook="review"` nodes travel in the
 * captured product HTML and are parsed server-side instead.
 */

import { extractASIN } from "../amazon";
import type { SiteAdapter } from "./types";

const AMAZON_HOST =
  /(^|\.)amazon\.(com|ca|co\.uk|de|fr|it|es|com\.au|co\.jp)$/i;

function amazonHostname(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return AMAZON_HOST.test(host) ? host : null;
  } catch {
    return null;
  }
}

export const amazonAdapter: SiteAdapter = {
  name: "amazon",

  matches(url: string): boolean {
    return amazonHostname(url) !== null;
  },

  isProductPage(url: string): boolean {
    if (!amazonHostname(url)) return false;
    try {
      const path = new URL(url).pathname;
      return path.includes("/dp/") || path.includes("/gp/product/");
    } catch {
      return false;
    }
  },

  canonicalUrl(url: string): string {
    const asin = extractASIN(url);
    if (!asin) return url;
    try {
      return `${new URL(url).origin}/dp/${asin}`;
    } catch {
      return url;
    }
  },
};
