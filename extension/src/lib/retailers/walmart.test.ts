import { describe, it, expect } from "vitest";

import { walmartAdapter } from "./walmart";

describe("walmartAdapter", () => {
  it('has the stable retailer key "walmart"', () => {
    expect(walmartAdapter.name).toBe("walmart");
  });

  it("matches walmart.com URLs", () => {
    expect(
      walmartAdapter.matches("https://www.walmart.com/ip/Product/1971741696"),
    ).toBe(true);
    expect(walmartAdapter.matches("https://walmart.com/cp/grocery/123")).toBe(
      true,
    );
  });

  it("matches walmart.ca URLs", () => {
    expect(
      walmartAdapter.matches(
        "https://www.walmart.ca/en/ip/Britax-One4Life/38WYZF7I4FZ6",
      ),
    ).toBe(true);
    expect(walmartAdapter.matches("https://www.walmart.ca/fr/browse/123")).toBe(
      true,
    );
  });

  it("does not match other retailers", () => {
    expect(walmartAdapter.matches("https://www.amazon.com/dp/B000123456")).toBe(
      false,
    );
    expect(walmartAdapter.matches("not a url")).toBe(false);
  });

  it("treats /ip/ paths as product pages", () => {
    expect(
      walmartAdapter.isProductPage(
        "https://www.walmart.com/ip/Great-Value-Honey/1971741696",
      ),
    ).toBe(true);
  });

  it("treats locale-prefixed walmart.ca /ip/ paths with alphanumeric ids as product pages", () => {
    expect(
      walmartAdapter.isProductPage(
        "https://www.walmart.ca/en/ip/Britax-One4Life-All-in-One-Car-Seat-Glacier-Graphite/38WYZF7I4FZ6",
      ),
    ).toBe(true);
    expect(
      walmartAdapter.isProductPage(
        "https://www.walmart.ca/fr/ip/Britax-One4Life/38WYZF7I4FZ6",
      ),
    ).toBe(true);
  });

  it("rejects non-product Walmart pages and non-Walmart product-like URLs", () => {
    expect(
      walmartAdapter.isProductPage("https://www.walmart.com/cp/grocery/123"),
    ).toBe(false);
    expect(
      walmartAdapter.isProductPage("https://www.walmart.ca/en/browse/grocery"),
    ).toBe(false);
    expect(walmartAdapter.isProductPage("https://www.amazon.com/ip/123")).toBe(
      false,
    );
  });

  it("omits fetchReviews (no usable client-session reviews endpoint)", () => {
    expect(walmartAdapter.fetchReviews).toBeUndefined();
  });
});
