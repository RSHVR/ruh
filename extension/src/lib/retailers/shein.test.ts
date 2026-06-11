/**
 * SHEIN adapter tests (imports the adapter directly, not via the registry).
 * Mirrors the Amazon/IKEA adapter style: matches the right host (incl.
 * us.shein.com), rejects others, and recognizes `-p-…​.html` product pages
 * while rejecting the homepage.
 */

import { describe, it, expect } from 'vitest';
import { sheinAdapter } from './shein';

describe('sheinAdapter', () => {
  it('matches shein.com hostnames (incl. us.shein.com)', () => {
    expect(sheinAdapter.matches('https://www.shein.com/')).toBe(true);
    expect(sheinAdapter.matches('https://us.shein.com/')).toBe(true);
    expect(
      sheinAdapter.matches('https://us.shein.com/some-name-p-12345678.html')
    ).toBe(true);
  });

  it('rejects other retailers', () => {
    expect(sheinAdapter.matches('https://www.amazon.com/dp/B000123456')).toBe(false);
    expect(sheinAdapter.matches('https://www.walmart.com/ip/123')).toBe(false);
  });

  it('isProductPage is true for a -p-….html url', () => {
    expect(
      sheinAdapter.isProductPage('https://us.shein.com/some-name-p-12345678.html')
    ).toBe(true);
  });

  it('isProductPage is false for the homepage', () => {
    expect(sheinAdapter.isProductPage('https://us.shein.com/')).toBe(false);
  });

  it('isProductPage is false on a matching host without the -p-….html pattern', () => {
    expect(
      sheinAdapter.isProductPage('https://us.shein.com/category/dresses.html')
    ).toBe(false);
  });

  it('does not expose fetchReviews (no client-session reviews endpoint)', () => {
    expect(sheinAdapter.fetchReviews).toBeUndefined();
  });
});
