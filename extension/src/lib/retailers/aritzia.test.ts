/**
 * Aritzia adapter tests (imports the adapter directly, not via the registry).
 * Mirrors the Amazon/IKEA adapter style: matches the right host, rejects others,
 * and recognizes `/product/` product pages while rejecting the homepage.
 */

import { describe, it, expect } from 'vitest';
import { aritziaAdapter } from './aritzia';

describe('aritziaAdapter', () => {
  it('matches aritzia.com hostnames', () => {
    expect(aritziaAdapter.matches('https://www.aritzia.com/us/en/')).toBe(true);
    expect(
      aritziaAdapter.matches(
        'https://www.aritzia.com/us/en/product/effortless-pant/12345.html'
      )
    ).toBe(true);
  });

  it('rejects other retailers', () => {
    expect(aritziaAdapter.matches('https://www.amazon.com/dp/B000123456')).toBe(false);
    expect(aritziaAdapter.matches('https://www.walmart.com/ip/123')).toBe(false);
  });

  it('isProductPage is true for a /product/ url', () => {
    expect(
      aritziaAdapter.isProductPage(
        'https://www.aritzia.com/us/en/product/effortless-pant/12345.html'
      )
    ).toBe(true);
  });

  it('isProductPage is false for the homepage', () => {
    expect(aritziaAdapter.isProductPage('https://www.aritzia.com/us/en/')).toBe(false);
  });
});
