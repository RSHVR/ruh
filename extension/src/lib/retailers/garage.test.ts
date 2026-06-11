/**
 * Garage adapter tests (LORE.md ADR-003). Imports the adapter directly (not the
 * shared registry) so it can be exercised before being wired into index.ts.
 */

import { describe, it, expect } from 'vitest';
import { garageAdapter } from './garage';

const PRODUCT_URL =
  'https://www.garageclothing.com/us/p/low-rise-baggy-jeans/10010171607H.html';

describe('garageAdapter', () => {
  it('matches garageclothing.com domain', () => {
    expect(garageAdapter.matches(PRODUCT_URL)).toBe(true);
    expect(garageAdapter.matches('https://garageclothing.com/')).toBe(true);
  });

  it('rejects non-garage domains', () => {
    expect(garageAdapter.matches('https://www.amazon.com/dp/B000123456')).toBe(false);
    expect(garageAdapter.matches('https://www.walmart.com/ip/123')).toBe(false);
    expect(garageAdapter.matches('https://www.notgarageclothing.com/p/x.html')).toBe(false);
    expect(garageAdapter.matches('not a url')).toBe(false);
  });

  it('identifies product pages by /p/ path ending in .html', () => {
    expect(garageAdapter.isProductPage(PRODUCT_URL)).toBe(true);
  });

  it('rejects non-product garage pages', () => {
    expect(garageAdapter.isProductPage('https://www.garageclothing.com/')).toBe(false);
    expect(garageAdapter.isProductPage('https://www.garageclothing.com/us/c/jeans')).toBe(false);
  });

  it('omits fetchReviews (no usable client-session reviews endpoint)', () => {
    expect(garageAdapter.fetchReviews).toBeUndefined();
  });
});
