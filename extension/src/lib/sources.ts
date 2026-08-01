/**
 * Source extraction for finding cards.
 *
 * Research-derived findings embed their receipts inline in the description
 * text ("… Source: pmc.ncbi.nlm.nih.gov/articles/PMC2896013, cdc.gov/…").
 * Non-technical users shouldn't have to read raw URLs, so we split each
 * description into:
 *   - `reason`: the plain-language explanation with source clutter removed
 *   - `sources`: structured {url, domain} entries for the favicon stack
 */

export interface SourceRef {
  /** Fully-qualified URL (https:// added when the text omitted the scheme). */
  url: string;
  /** Registrable-ish host, used for favicons + display ("cdc.gov"). */
  domain: string;
}

// Matches http(s) URLs and bare domain paths like "cdc.gov/niosh/x.pdf" or
// "reddit.com/r/GelX_Nails". Requires a dot-separated host with a 2+ letter
// TLD so ordinary prose ("e.g.", "approx.") doesn't match.
const URL_PATTERN =
  /\bhttps?:\/\/[^\s,;)]+|\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:\/[^\s,;)]*)?/gi;

// Bare "Source:" / "Sources:" label — removed AFTER the URLs themselves are
// stripped (the label's payload is the URL list, which URL_PATTERN handles;
// trying to match "up to the sentence end" fails because URLs contain dots).
const SOURCE_LABEL = /\bsources?\s*:\s*/gi;

function toDomain(raw: string): string | null {
  try {
    const url = new URL(raw.startsWith("http") ? raw : `https://${raw}`);
    const host = url.hostname.replace(/^www\./, "");
    // Guard against prose false-positives that survived the pattern
    if (!host.includes(".")) return null;
    return host;
  } catch {
    return null;
  }
}

export function extractSources(text: string): {
  reason: string;
  sources: SourceRef[];
} {
  if (!text) return { reason: "", sources: [] };

  const sources: SourceRef[] = [];
  const seen = new Set<string>();

  for (const match of text.match(URL_PATTERN) ?? []) {
    // Trim trailing punctuation the pattern may have swallowed
    const cleanedMatch = match.replace(/[.,;)\]]+$/, "");
    const domain = toDomain(cleanedMatch);
    if (!domain) continue;
    const url = cleanedMatch.startsWith("http")
      ? cleanedMatch
      : `https://${cleanedMatch}`;
    if (!seen.has(url)) {
      seen.add(url);
      sources.push({ url, domain });
    }
  }

  let reason = text
    .replace(URL_PATTERN, " ") // URLs out first (they contain dots/commas)
    .replace(SOURCE_LABEL, " ") // then the now-empty "Source:" label
    .replace(/\(\s*\)/g, " ") // empty parens left behind
    .replace(/(?:\s*,\s*)+(?=[.,]|$)/g, "") // dangling comma runs
    .replace(/\s+([.,;])/g, "$1")
    .replace(/\.{2,}/g, ".")
    .replace(/\s{2,}/g, " ")
    .trim();
  // Drop a dangling connector if the sentence ended in the removed segment
  reason = reason.replace(/[,;:\s]+$/, "").trim();
  if (reason && !/[.!?]$/.test(reason)) reason += ".";

  return { reason, sources };
}

/** Favicon URL for a source domain (Google's public favicon service). */
export function faviconUrl(domain: string, size = 32): string {
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=${size}`;
}
