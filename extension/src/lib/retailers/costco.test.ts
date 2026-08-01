/**
 * Costco adapter tests (imports the adapter directly, not via the registry).
 * Mirrors the IKEA adapter style: matches the right host, rejects others, and
 * recognizes product pages while rejecting category pages / the homepage.
 *
 * Costco serves Canadian shoppers on costco.ca and has migrated its product URL
 * scheme: the old `/<slug>.product.<id>.html` pages 301 to `/p/-/<slug>/<id>`
 * (with query params like `?langId=-24`). Both forms must be recognized because
 * category pages still link the old `.product.` URLs.
 */

import { describe, it, expect } from "vitest";
import { costcoAdapter } from "./costco";

describe("costcoAdapter", () => {
  it("matches costco.com hostnames", () => {
    expect(costcoAdapter.matches("https://www.costco.com/")).toBe(true);
    expect(
      costcoAdapter.matches(
        "https://www.costco.com/some-item.product.100334757.html",
      ),
    ).toBe(true);
  });

  it("matches costco.ca hostnames", () => {
    expect(costcoAdapter.matches("https://www.costco.ca/")).toBe(true);
    expect(
      costcoAdapter.matches(
        "https://www.costco.ca/oxiclean-max-efficiency-stain-remover-525-kg.product.4000289802.html",
      ),
    ).toBe(true);
  });

  it("rejects other retailers", () => {
    expect(costcoAdapter.matches("https://www.amazon.com/dp/B000123456")).toBe(
      false,
    );
    expect(costcoAdapter.matches("https://www.walmart.com/ip/123")).toBe(false);
  });

  it("isProductPage is true for the legacy .product. url", () => {
    expect(
      costcoAdapter.isProductPage(
        "https://www.costco.ca/oxiclean-max-efficiency-stain-remover-525-kg.product.4000289802.html",
      ),
    ).toBe(true);
  });

  it("isProductPage is true for the new /p/ scheme (post-301 redirect)", () => {
    expect(
      costcoAdapter.isProductPage(
        "https://www.costco.ca/p/-/oxiclean-max-efficiency-stain-remover-525-kg/4000289802?langId=-24",
      ),
    ).toBe(true);
  });

  it("isProductPage is false for a category page", () => {
    expect(
      costcoAdapter.isProductPage(
        "https://www.costco.ca/laundry-detergent.html",
      ),
    ).toBe(false);
  });

  it("isProductPage is false for the homepage", () => {
    expect(costcoAdapter.isProductPage("https://www.costco.com/")).toBe(false);
  });
});
