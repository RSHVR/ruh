/**
 * Uniqlo adapter tests (imports the adapter directly, not via the registry).
 * Mirrors the IKEA adapter style: matches the right host, rejects others,
 * and recognizes `/products/` product pages while rejecting the homepage.
 */

import { describe, it, expect } from 'vitest';
import { uniqloAdapter } from './uniqlo';

describe('uniqloAdapter', () => {
  it('matches uniqlo.com hostnames', () => {
    expect(uniqloAdapter.matches('https://www.uniqlo.com/us/en/')).toBe(true);
    expect(
      uniqloAdapter.matches('https://www.uniqlo.com/us/en/products/E460318-000')
    ).toBe(true);
  });

  it('rejects other retailers', () => {
    expect(uniqloAdapter.matches('https://www.amazon.com/dp/B000123456')).toBe(false);
    expect(uniqloAdapter.matches('https://www.walmart.com/ip/123')).toBe(false);
  });

  it('isProductPage is true for a /products/ url', () => {
    expect(
      uniqloAdapter.isProductPage('https://www.uniqlo.com/us/en/products/E460318-000')
    ).toBe(true);
  });

  it('isProductPage is false for the homepage', () => {
    expect(uniqloAdapter.isProductPage('https://www.uniqlo.com/us/en/')).toBe(false);
  });
});
