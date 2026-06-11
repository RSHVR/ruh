/**
 * Costco adapter tests (imports the adapter directly, not via the registry).
 * Mirrors the IKEA adapter style: matches the right host, rejects others, and
 * recognizes `.product.` product pages while rejecting the homepage.
 */

import { describe, it, expect } from 'vitest';
import { costcoAdapter } from './costco';

describe('costcoAdapter', () => {
  it('matches costco.com hostnames', () => {
    expect(costcoAdapter.matches('https://www.costco.com/')).toBe(true);
    expect(
      costcoAdapter.matches(
        'https://www.costco.com/some-item.product.100334757.html'
      )
    ).toBe(true);
  });

  it('rejects other retailers', () => {
    expect(costcoAdapter.matches('https://www.amazon.com/dp/B000123456')).toBe(false);
    expect(costcoAdapter.matches('https://www.walmart.com/ip/123')).toBe(false);
  });

  it('isProductPage is true for a .product. url', () => {
    expect(
      costcoAdapter.isProductPage(
        'https://www.costco.com/some-item.product.100334757.html'
      )
    ).toBe(true);
  });

  it('isProductPage is false for the homepage', () => {
    expect(costcoAdapter.isProductPage('https://www.costco.com/')).toBe(false);
  });
});
