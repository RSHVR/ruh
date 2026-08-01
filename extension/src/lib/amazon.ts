/**
 * Amazon URL helpers.
 *
 * Session-based review fetching used to live here, but Amazon killed anonymous
 * review pagination — `/product-reviews/<ASIN>/` now 302s to `/ap/signin` — so the
 * Amazon adapter no longer fetches reviews; the product page's embedded review nodes
 * travel in the captured product HTML and are parsed server-side. Only the ASIN /
 * domain extraction helpers remain.
 */

/**
 * Extract ASIN (Amazon Standard Identification Number) from various URL formats.
 *
 * Handles:
 * - /dp/B081PK2PFG/
 * - /gp/product/B081PK2PFG
 * - /product-reviews/B081PK2PFG/
 * - /ROCKBROS-Balaclava.../dp/B081PK2PFG/ref=...
 *
 * @param url - Amazon product URL
 * @returns ASIN string or null if not found
 */
export function extractASIN(url: string): string | null {
  const patterns = [
    /\/dp\/([A-Z0-9]{10})/i,
    /\/gp\/product\/([A-Z0-9]{10})/i,
    /\/product-reviews\/([A-Z0-9]{10})/i,
    /\/gp\/aw\/d\/([A-Z0-9]{10})/i, // Mobile URLs
  ];

  for (const pattern of patterns) {
    const match = url.match(pattern);
    if (match) return match[1].toUpperCase();
  }
  return null;
}

/**
 * Extract the Amazon domain from the current page URL.
 *
 * @param url - Current page URL
 * @returns Domain like 'amazon.ca' or 'amazon.com'
 */
export function extractAmazonDomain(url: string): string | null {
  try {
    const urlObj = new URL(url);
    const hostname = urlObj.hostname;

    // Match amazon.* domains
    const match = hostname.match(/(amazon\.[a-z.]+)$/i);
    return match ? match[1] : null;
  } catch {
    return null;
  }
}
