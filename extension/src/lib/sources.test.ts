import { describe, it, expect } from "vitest";
import { extractSources, faviconUrl } from "./sources";

describe("extractSources", () => {
  it("pulls a bare-domain source and cleans the reason", () => {
    const { reason, sources } = extractSources(
      "Photoinitiator that can be highly cytotoxic. Source: pmc.ncbi.nlm.nih.gov/articles/PMC2896013",
    );
    expect(sources).toEqual([
      {
        url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC2896013",
        domain: "pmc.ncbi.nlm.nih.gov",
      },
    ]);
    expect(reason).toBe("Photoinitiator that can be highly cytotoxic.");
  });

  it("handles comma-separated source lists", () => {
    const { reason, sources } = extractSources(
      "Multiple users reported reactions. Source: reddit.com/r/GelX_Nails, reddit.com/r/lacqueristas",
    );
    expect(sources.map((s) => s.domain)).toEqual(["reddit.com", "reddit.com"]);
    expect(sources[0].url).toBe("https://reddit.com/r/GelX_Nails");
    expect(reason).toBe("Multiple users reported reactions.");
  });

  it("handles full https URLs mid-sentence", () => {
    const { reason, sources } = extractSources(
      "Banned in some states per https://cdc.gov/niosh/hhe/reports/pdfs/2015-0139-3338.pdf and industry data.",
    );
    expect(sources[0].url).toBe(
      "https://cdc.gov/niosh/hhe/reports/pdfs/2015-0139-3338.pdf",
    );
    expect(reason).toContain("Banned in some states");
    expect(reason).not.toContain("cdc.gov");
  });

  it("dedupes identical urls", () => {
    const { sources } = extractSources("See cdc.gov/a. Source: cdc.gov/a");
    expect(sources).toHaveLength(1);
  });

  it("does not treat abbreviations as domains", () => {
    const { reason, sources } = extractSources(
      "Approx. 3% of users react, e.g. with dermatitis.",
    );
    expect(sources).toEqual([]);
    expect(reason).toContain("dermatitis");
  });

  it("returns empty results for empty input", () => {
    expect(extractSources("")).toEqual({ reason: "", sources: [] });
  });
});

describe("faviconUrl", () => {
  it("builds the favicon service url", () => {
    expect(faviconUrl("cdc.gov")).toBe(
      "https://www.google.com/s2/favicons?domain=cdc.gov&sz=32",
    );
  });
});
