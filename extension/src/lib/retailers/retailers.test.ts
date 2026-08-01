/**
 * Adapter registry tests (LORE.md ADR-003).
 *
 * Locks the contract: each adapter matches its own domains and rejects others,
 * identifies product pages correctly, and getAdapter resolves by URL.
 * New retailers should add their cases here (TDD: write the case, then the adapter).
 */

import { describe, it, expect } from "vitest";
import { getAdapter, allAdapters } from "./index";
import { amazonAdapter } from "./amazon";

describe("amazonAdapter", () => {
  it("matches amazon.com and amazon.ca domains", () => {
    expect(amazonAdapter.matches("https://www.amazon.com/dp/B000123456")).toBe(
      true,
    );
    expect(amazonAdapter.matches("https://www.amazon.ca/dp/B000123456")).toBe(
      true,
    );
    expect(
      amazonAdapter.matches("https://smile.amazon.com/dp/B000123456"),
    ).toBe(true);
  });

  it("rejects non-amazon domains", () => {
    expect(amazonAdapter.matches("https://www.walmart.com/ip/123")).toBe(false);
    expect(
      amazonAdapter.matches("https://www.notamazon.com/dp/B000123456"),
    ).toBe(false);
    expect(amazonAdapter.matches("not a url")).toBe(false);
  });

  it("identifies product pages by /dp/ or /gp/product/", () => {
    expect(
      amazonAdapter.isProductPage(
        "https://www.amazon.ca/Some-Title/dp/B000123456/ref=x",
      ),
    ).toBe(true);
    expect(
      amazonAdapter.isProductPage(
        "https://www.amazon.com/gp/product/B000123456",
      ),
    ).toBe(true);
  });

  it("rejects non-product amazon pages", () => {
    expect(amazonAdapter.isProductPage("https://www.amazon.com/")).toBe(false);
    expect(
      amazonAdapter.isProductPage("https://www.amazon.com/s?k=sunscreen"),
    ).toBe(false);
  });

  it("omits fetchReviews (Amazon killed anonymous review pagination)", () => {
    // /product-reviews/<ASIN>/ now 302s to /ap/signin, so the adapter has no
    // usable client-session reviews endpoint and omits fetchReviews entirely
    // (interface segregation — CLAUDE.md SOLID/I). The product page's embedded
    // review nodes travel in the captured product HTML instead.
    expect(amazonAdapter.fetchReviews).toBeUndefined();
  });
});

describe("getAdapter registry", () => {
  it("resolves the amazon adapter for amazon urls", () => {
    expect(getAdapter("https://www.amazon.ca/dp/B000123456")?.name).toBe(
      "amazon",
    );
  });

  it("returns null for unsupported domains", () => {
    expect(
      getAdapter("https://www.some-unconfigured-shop.example/p/1"),
    ).toBeNull();
  });

  it("every registered adapter has a unique name", () => {
    const names = allAdapters().map((a) => a.name);
    expect(new Set(names).size).toBe(names.length);
  });
});
