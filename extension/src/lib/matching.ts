/**
 * Ingredient ↔ finding name matching for chip highlighting.
 *
 * Findings name things three ways that naive matching gets wrong:
 *   - "Ethylhexylglycerin - Contact Sensitizer"        (must NOT match "Glycerin")
 *   - "1,4-Dioxane Contamination Risk (Ceteareth-20)"  (MUST match "Ceteareth-20" —
 *     the affected label ingredient lives in the parenthetical)
 *   - "2-Hydroxyethyl Methacrylate (HEMA)"             (must match the label's
 *     "2-Hydroxyethyl Methacrylate - HEMA (3-5%)")
 *
 * Strategy: compare WHOLE-token sets (never substrings), and treat each
 * parenthetical chunk of the finding name as an additional match candidate
 * (split on "/" for forms like "(CPK/Irgacure 184)").
 */

function tokensOf(s: string): string[] {
  return s
    .toLowerCase()
    .replace(/\b\d+(?:[.,]\d+)?\s*%/g, " ") // percentage ranges: "3-5%", "40%"
    .replace(/\b\d+[,'′-]*/g, " ") // locants and counts: "1,4-", "2-", "184"
    .replace(/[^a-z\s]/g, " ")
    .split(/\s+/)
    .filter((t) => t.length > 2);
}

/** True when the smaller token set is wholly contained in the larger one. */
function tokenSubset(a: string[], b: string[]): boolean {
  if (a.length === 0 || b.length === 0) return false;
  const [small, large] = a.length <= b.length ? [a, b] : [b, a];
  const largeSet = new Set(large);
  return small.every((t) => largeSet.has(t));
}

export function namesMatch(ingredient: string, findingName: string): boolean {
  const ingredientTokens = tokensOf(ingredient);
  if (ingredientTokens.length === 0) return false;

  // Candidate names: the finding minus parentheticals, plus each
  // parenthetical's slash-separated parts as standalone candidates.
  const candidates: string[] = [findingName.replace(/\([^)]*\)/g, " ")];
  for (const paren of findingName.match(/\(([^)]*)\)/g) ?? []) {
    for (const part of paren.slice(1, -1).split("/")) {
      candidates.push(part);
    }
  }

  return candidates.some((candidate) =>
    tokenSubset(ingredientTokens, tokensOf(candidate)),
  );
}
