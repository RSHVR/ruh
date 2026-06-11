/**
 * Sephora adapter tests (imports the adapter directly, not via the registry).
 * Mirrors the IKEA/Amazon adapter style: matches the right host, rejects others,
 * and recognizes `/product/` product pages while rejecting the homepage.
 */

import { describe, it, expect } from 'vitest';
import { sephoraAdapter } from './sephora';

describe('sephoraAdapter', () => {
  it('matches sephora.com hostnames', () => {
    expect(sephoraAdapter.matches('https://www.sephora.com/')).toBe(true);
    expect(
      sephoraAdapter.matches('https://www.sephora.com/product/some-serum-P123456')
    ).toBe(true);
  });

  it('rejects other retailers', () => {
    expect(sephoraAdapter.matches('https://www.amazon.com/dp/B000123456')).toBe(false);
    expect(sephoraAdapter.matches('https://www.ikea.com/us/en/p/foo-123/')).toBe(false);
  });

  it('isProductPage is true for a /product/ url', () => {
    expect(
      sephoraAdapter.isProductPage('https://www.sephora.com/product/some-serum-P123456')
    ).toBe(true);
  });

  it('isProductPage is false for the homepage', () => {
    expect(sephoraAdapter.isProductPage('https://www.sephora.com/')).toBe(false);
  });
});
