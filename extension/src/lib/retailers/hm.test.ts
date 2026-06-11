/**
 * H&M adapter tests (imports the adapter directly, not via the registry).
 * Mirrors the IKEA/Amazon adapter style: matches the right host (incl. www2),
 * rejects others, and recognizes `productpage.` detail pages while rejecting
 * the homepage.
 */

import { describe, it, expect } from 'vitest';
import { hmAdapter } from './hm';

describe('hmAdapter', () => {
  it('matches hm.com hostnames including www2', () => {
    expect(hmAdapter.matches('https://www2.hm.com/en_us/productpage.1234567001.html')).toBe(true);
    expect(hmAdapter.matches('https://hm.com/en_us/')).toBe(true);
    expect(hmAdapter.matches('https://www.hm.com/en_us/')).toBe(true);
  });

  it('rejects other retailers', () => {
    expect(hmAdapter.matches('https://www.amazon.com/dp/B000123456')).toBe(false);
    expect(hmAdapter.matches('https://www.walmart.com/ip/123')).toBe(false);
  });

  it('isProductPage is true for a productpage. url', () => {
    expect(
      hmAdapter.isProductPage('https://www2.hm.com/en_us/productpage.1234567001.html')
    ).toBe(true);
  });

  it('isProductPage is false for the homepage', () => {
    expect(hmAdapter.isProductPage('https://www2.hm.com/en_us/')).toBe(false);
  });
});
