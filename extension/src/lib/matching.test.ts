import { describe, it, expect } from "vitest";
import { namesMatch } from "./matching";

// Every case below is taken from real stored analyses (CeraVe moisturizer,
// Beetles builder gel) that exposed the original matcher's failures.
describe("namesMatch", () => {
  it("does NOT match Glycerin against Ethylhexylglycerin (substring trap)", () => {
    expect(
      namesMatch("Glycerin", "Ethylhexylglycerin - Contact Sensitizer"),
    ).toBe(false);
  });

  it("matches the actual Ethylhexylglycerin ingredient", () => {
    expect(
      namesMatch("Ethylhexylglycerin", "Ethylhexylglycerin - Contact Sensitizer"),
    ).toBe(true);
  });

  it("matches contamination-risk findings via their parenthetical carrier", () => {
    expect(
      namesMatch("Ceteareth-20", "1,4-Dioxane Contamination Risk (Ceteareth-20)"),
    ).toBe(true);
    expect(
      namesMatch("Petrolatum", "PAH Contamination Risk (Petrolatum)"),
    ).toBe(true);
  });

  it("does not flag unrelated ingredients for contamination findings", () => {
    expect(
      namesMatch("Cetyl Alcohol", "1,4-Dioxane Contamination Risk (Ceteareth-20)"),
    ).toBe(false);
  });

  it("matches locant-prefixed label names with percentage suffixes", () => {
    expect(
      namesMatch(
        "2-Hydroxyethyl Methacrylate - HEMA (3-5%)",
        "2-Hydroxyethyl Methacrylate (HEMA)",
      ),
    ).toBe(true);
  });

  it("does NOT match bis-compounds to their smaller cousins (whole tokens)", () => {
    expect(
      namesMatch(
        "Isopropylidenediphenyl Bisoxyhydroxypropyl Methacrylate (5-10%)",
        "Hydroxypropyl Methacrylate (HPMA)",
      ),
    ).toBe(false);
  });

  it("matches via slash-split parenthetical aliases", () => {
    expect(
      namesMatch(
        "Hydroxycyclohexyl Phenyl Ketone - CPK (1-2%)",
        "Hydroxycyclohexyl Phenyl Ketone (CPK/Irgacure 184)",
      ),
    ).toBe(true);
  });

  it("matches simple identical names", () => {
    expect(namesMatch("Formaldehyde", "Formaldehyde")).toBe(true);
  });

  it("returns false for empty input", () => {
    expect(namesMatch("", "Formaldehyde")).toBe(false);
    expect(namesMatch("Water", "")).toBe(false);
  });
});
