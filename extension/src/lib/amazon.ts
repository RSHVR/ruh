/**
 * Amazon utilities for client-side reviews fetching.
 *
 * Uses the user's existing Amazon session to fetch review pages,
 * which appear as normal logged-in user requests to Amazon.
 */

export interface ReviewsFetchResult {
  html: string;
  success: boolean;
  pagesLoaded: number;
  error?: 'no_reviews' | 'network_error';
}

export interface ReviewsFetchOptions {
  /** Number of review pages to fetch (default: 5, max: 10) */
  pages?: number;
  /** Filter by star rating (default: 'all') */
  filter?: 'all' | 'critical' | 'positive' | 'five_star' | 'four_star' | 'three_star' | 'two_star' | 'one_star';
  /** Delay between page fetches in ms (default: 300) */
  delayMs?: number;
  /** Sort order (default: 'helpful') */
  sortBy?: 'helpful' | 'recent';
}

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
    /\/gp\/aw\/d\/([A-Z0-9]{10})/i,  // Mobile URLs
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

/**
 * Check if HTML contains actual reviews.
 */
function hasReviews(html: string): boolean {
  return html.includes('data-hook="review"');
}

/**
 * Build the reviews page URL with optional filters.
 */
function buildReviewsUrl(
  asin: string,
  pageNumber: number,
  options: ReviewsFetchOptions
): string {
  const params = new URLSearchParams();
  params.set('pageNumber', pageNumber.toString());
  params.set('reviewerType', 'all_reviews');

  if (options.filter && options.filter !== 'all') {
    params.set('filterByStar', options.filter);
  }

  if (options.sortBy === 'recent') {
    params.set('sortBy', 'recent');
  }

  return `/product-reviews/${asin}/?${params.toString()}`;
}

/**
 * Fetch paginated reviews using the user's Amazon session.
 *
 * This function makes fetch requests from the content script context,
 * which automatically includes the user's cookies. Amazon sees these
 * as normal logged-in user requests.
 *
 * @param asin - Product ASIN
 * @param options - Fetch options
 * @returns Result with HTML content and status
 */
export async function fetchReviews(
  asin: string,
  options: ReviewsFetchOptions = {}
): Promise<ReviewsFetchResult> {
  const {
    pages = 5,
    filter = 'all',
    delayMs = 300,
    sortBy = 'helpful',
  } = options;

  // Clamp pages to reasonable range
  const maxPages = Math.min(Math.max(pages, 1), 10);

  const allHtml: string[] = [];
  let pagesLoaded = 0;

  console.log(`[ruh] Fetching ${maxPages} review pages for ASIN: ${asin}`);

  for (let page = 1; page <= maxPages; page++) {
    try {
      const url = buildReviewsUrl(asin, page, { filter, sortBy });
      console.log(`[ruh] Fetching reviews page ${page}: ${url}`);

      const response = await fetch(url, {
        credentials: 'include',  // Include cookies
        headers: {
          'Accept': 'text/html,application/xhtml+xml',
          'Accept-Language': 'en-US,en;q=0.9',
        },
      });

      if (!response.ok) {
        console.warn(`[ruh] Unable to read reviews (HTTP ${response.status})`);
        return {
          html: allHtml.join('\n'),
          success: pagesLoaded > 0,
          pagesLoaded,
          error: 'network_error',
        };
      }

      const html = await response.text();
      console.log(`[ruh] Page ${page}: ${html.length} bytes`);

      // Check if page has reviews
      if (!hasReviews(html)) {
        if (page === 1) {
          console.warn('[ruh] Unable to read reviews (no reviews found)');
          return {
            html: '',
            success: false,
            pagesLoaded: 0,
            error: 'no_reviews',
          };
        }
        // End of reviews on subsequent pages
        console.log(`[ruh] No more reviews after page ${page - 1}`);
        break;
      }

      // Add page marker and HTML
      allHtml.push(`<!-- REVIEWS_PAGE_${page} -->\n${html}`);
      pagesLoaded++;

      // Delay between requests (except for last page)
      if (page < maxPages) {
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }

    } catch (err) {
      console.error(`[ruh] Unable to read reviews:`, err);
      return {
        html: allHtml.join('\n'),
        success: pagesLoaded > 0,
        pagesLoaded,
        error: 'network_error',
      };
    }
  }

  const totalBytes = allHtml.join('\n').length;
  console.log(`[ruh] Reviews fetched: ${pagesLoaded} pages, ${(totalBytes / 1024).toFixed(1)}KB`);

  return {
    html: allHtml.join('\n'),
    success: pagesLoaded > 0,
    pagesLoaded,
  };
}

/**
 * Fetch only critical (1-3 star) reviews for health concern detection.
 * Critical reviews are more likely to contain health-related complaints.
 *
 * @param asin - Product ASIN
 * @param pages - Number of pages to fetch
 * @returns Result with HTML content and status
 */
export async function fetchCriticalReviews(
  asin: string,
  pages: number = 3
): Promise<ReviewsFetchResult> {
  return fetchReviews(asin, {
    pages,
    filter: 'critical',
    sortBy: 'helpful',
  });
}
