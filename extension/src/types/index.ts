export interface ProductAnalysis {
  id: string | null;
  product_url: string;
  product_name: string;
  brand: string;
  retailer: string;
  ingredients: string[];
  /**
   * Optional provenance segmentation of `ingredients` (backend task #15).
   * When present, the UI groups the chips by how each ingredient was known;
   * when absent (all existing analyses), the flat `ingredients` list is shown.
   */
  ingredients_by_provenance?: {
    declared: string[];
    found: string[];
    /** Each inferred ingredient carries the production stage it likely enters at. */
    inferred: { name: string; stage: string }[];
  };
  /**
   * Optional region-aware sourcing summary (backend task #16). `region` echoes
   * the region the research was run for; `alert` is a prominent caution (e.g. an
   * active recall/outbreak) and already includes its own source + timeframe.
   */
  origin?: {
    summary: string;
    region: string | null;
    alert: string | null;
  };
  overall_score: number;
  allergens_detected: AllergenDetection[];
  pfas_detected: PFASDetection[];
  other_concerns: ToxinConcern[];
  research_sources?: { type?: string; url?: string; finding?: string }[];
  confidence: number;
  analyzed_at: string;
  analysis_version: string;
  claude_model: string;
}

export interface AllergenDetection {
  name: string;
  severity: "low" | "moderate" | "high" | "severe";
  source: string;
  confidence: number;
}

export interface PFASDetection {
  name: string;
  cas_number?: string;
  body_effects: string;
  source: string;
  confidence: number;
}

export interface ToxinConcern {
  name: string;
  category: string;
  severity: "low" | "moderate" | "high" | "severe";
  description: string;
  confidence: number;
}

export interface AlternativeProduct {
  id: string | null;
  product_url: string;
  product_name: string;
  brand: string;
  safety_score: number;
  safety_improvement: number;
  price?: number;
  price_difference?: number;
  rank: number;
  affiliate_link?: string;
  affiliate_network?: string;
  recommended_at?: string;
}

export interface AnalysisResponse {
  analysis: ProductAnalysis;
  alternatives: AlternativeProduct[];
  cached: boolean;
  cache_age_seconds?: number;
  url_hash?: string;
  reviews_stored?: number | null;

  // Auth/credit context (present when user is JWT-authenticated)
  user_tier?: string; // 'free' | 'basic' | 'middle' | 'unlimited'
  credits_remaining?: number; // -1 = unlimited
  analysis_unlocked?: boolean;
}

export interface UserContext {
  isAuthenticated: boolean;
  userId?: string;
  email?: string;
  displayName?: string;
  avatarUrl?: string;
  tier: string;
  creditsRemaining: number;
}

export interface CachedAnalysis {
  data: AnalysisResponse;
  timestamp: number;
  url: string;
}

export type RiskLevel =
  | "Low Risk"
  | "Minor Risk"
  | "Moderate Risk"
  | "High Risk"
  | "Severe Risk";

export interface ProductInfo {
  url: string;
  name?: string;
  asin?: string;
}

/**
 * Request payload for product analysis API
 */
export interface AnalysisRequest {
  product_url: string;
  /** Client-provided product page HTML (captured from DOM) */
  product_html?: string;
  /** Client-provided reviews HTML (fetched via user's Amazon session) */
  reviews_html?: string;
  /**
   * Shopper's region (e.g. "CA-ON"), for region-aware origin research. Injected
   * by the background worker from the signed-in user's metadata; null if unset.
   */
  user_region?: string | null;
}

/**
 * Result from client-side reviews fetching
 */
export interface ReviewsFetchStatus {
  success: boolean;
  pagesLoaded: number;
  error?: string;
}
