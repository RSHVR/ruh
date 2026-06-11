/**
 * IKEA adapter tests (imports the adapter directly, not via the registry).
 * Mirrors the Amazon adapter style: matches the right host, rejects others,
 * and recognizes `/p/` product pages while rejecting the homepage.
 */

import { describe, it, expect } from 'vitest';
import { ikeaAdapter } from './ikea';

describe('ikeaAdapter', () => {
  it('matches ikea.com hostnames', () => {
    expect(ikeaAdapter.matches('https://www.ikea.com/us/en/')).toBe(true);
    expect(
      ikeaAdapter.matches(
        'https://www.ikea.com/us/en/p/hemnes-8-drawer-dresser-white-stain-10576191/'
      )
    ).toBe(true);
  });

  it('rejects other retailers', () => {
    expect(ikeaAdapter.matches('https://www.amazon.com/dp/B000123456')).toBe(false);
    expect(ikeaAdapter.matches('https://www.walmart.com/ip/123')).toBe(false);
  });

  it('isProductPage is true for a /p/ url', () => {
    expect(
      ikeaAdapter.isProductPage(
        'https://www.ikea.com/us/en/p/hemnes-8-drawer-dresser-white-stain-10576191/'
      )
    ).toBe(true);
  });

  it('isProductPage is false for the homepage', () => {
    expect(ikeaAdapter.isProductPage('https://www.ikea.com/us/en/')).toBe(false);
  });
});
