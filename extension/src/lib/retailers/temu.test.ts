/**
 * Temu adapter tests (imports the adapter directly, not via the registry).
 * Mirrors the Amazon/IKEA adapter style: matches the right host, rejects others,
 * and recognizes `-g-...​.html` product pages while rejecting the homepage.
 */

import { describe, it, expect } from 'vitest';
import { temuAdapter } from './temu';

describe('temuAdapter', () => {
  it('matches temu.com hostnames', () => {
    expect(temuAdapter.matches('https://www.temu.com/')).toBe(true);
    expect(
      temuAdapter.matches(
        'https://www.temu.com/stainless-steel-water-bottle-g-601099512345678.html'
      )
    ).toBe(true);
  });

  it('rejects other retailers', () => {
    expect(temuAdapter.matches('https://www.amazon.com/dp/B000123456')).toBe(false);
    expect(temuAdapter.matches('https://www.walmart.com/ip/123')).toBe(false);
  });

  it('isProductPage is true for a -g-...html url', () => {
    expect(
      temuAdapter.isProductPage(
        'https://www.temu.com/stainless-steel-water-bottle-g-601099512345678.html'
      )
    ).toBe(true);
  });

  it('isProductPage is false for the homepage', () => {
    expect(temuAdapter.isProductPage('https://www.temu.com/')).toBe(false);
  });

  it('isProductPage is false for a non-product .html without -g-', () => {
    expect(
      temuAdapter.isProductPage('https://www.temu.com/about-us.html')
    ).toBe(false);
  });
});
