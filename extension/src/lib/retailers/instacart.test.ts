/**
 * Instacart adapter tests (imports the adapter directly, not via the registry).
 * Mirrors the IKEA adapter style: matches the right host, rejects others, and
 * recognizes `/products/` product pages while rejecting the homepage.
 */

import { describe, it, expect } from 'vitest';
import { instacartAdapter } from './instacart';

describe('instacartAdapter', () => {
  it('matches instacart.com hostnames', () => {
    expect(instacartAdapter.matches('https://www.instacart.com/store')).toBe(true);
    expect(
      instacartAdapter.matches('https://www.instacart.com/products/12345-organic-soy-sauce')
    ).toBe(true);
  });

  it('rejects other retailers', () => {
    expect(instacartAdapter.matches('https://www.amazon.com/dp/B000123456')).toBe(false);
    expect(instacartAdapter.matches('https://www.walmart.com/ip/123')).toBe(false);
  });

  it('isProductPage is true for a /products/ url', () => {
    expect(
      instacartAdapter.isProductPage('https://www.instacart.com/products/12345-organic-soy-sauce')
    ).toBe(true);
  });

  it('isProductPage is false for a non-product page', () => {
    expect(instacartAdapter.isProductPage('https://www.instacart.com/store')).toBe(false);
  });

  it('exposes prepareForCapture (lazy content needs a scroll before capture)', () => {
    expect(typeof instacartAdapter.prepareForCapture).toBe('function');
  });
});
