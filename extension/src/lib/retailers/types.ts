/**
 * SiteAdapter — the per-retailer extension contract (LORE.md ADR-003).
 *
 * The content script is retailer-agnostic: it resolves the active adapter via
 * `getAdapter(url)` and asks it whether the page is a product page and (optionally)
 * for session-fetched reviews. Adding a retailer = adding one adapter + registry line.
 */

export interface ReviewsResult {
  /** Concatenated raw reviews HTML captured from the user's session. */
  html: string;
  /** Number of reviews detected (best-effort, for logging). */
  count: number;
}

export interface SiteAdapter {
  /** Stable retailer key, e.g. "amazon", "walmart". */
  readonly name: string;

  /** True if this adapter handles the given URL's domain. */
  matches(url: string): boolean;

  /** True if the URL is a product *detail* page for this retailer. */
  isProductPage(url: string): boolean;

  /**
   * Optionally fetch reviews using the user's logged-in session.
   * Omit entirely for retailers with no usable client-session reviews endpoint
   * (interface segregation — see CLAUDE.md SOLID/I).
   */
  fetchReviews?(url: string): Promise<ReviewsResult | null>;

  /**
   * Optionally normalize a product URL to its canonical form (e.g. Amazon
   * `/dp/<ASIN>` with tracking params stripped) so server/client cache keys
   * don't fragment across URL variants of the same product. Omit when the
   * raw URL is already stable.
   */
  canonicalUrl?(url: string): string;

  /**
   * Optionally prepare the page before the DOM is captured — e.g. scroll to trigger
   * lazily-rendered sections (Instacart nutrition facts) or expand accordions. Called
   * by the content script just before snapshotting `outerHTML`. Should restore the
   * user's scroll position. Omit for sites whose content is present at load.
   * See LORE.md ADR-005 (archetype-D: lazy-rendered, no state blob).
   */
  prepareForCapture?(): Promise<void>;
}
