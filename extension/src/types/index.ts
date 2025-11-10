export interface ProductAnalysis {
  id: string | null;
  product_url: string;
  product_name: string;
  brand: string;
  retailer: string;
  ingredients: string[];
  overall_score: number;
  allergens_detected: AllergenDetection[];
  pfas_detected: PFASDetection[];
  other_concerns: ToxinConcern[];
  confidence: number;
  analyzed_at: string;
  analysis_version: string;
  claude_model: string;
}

export interface AllergenDetection {
  name: string;
  severity: 'low' | 'moderate' | 'high' | 'severe';
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
  severity: 'low' | 'moderate' | 'high' | 'severe';
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
}

export interface CachedAnalysis {
  data: AnalysisResponse;
  timestamp: number;
  url: string;
}

export type RiskLevel = 'Safe' | 'Low Risk' | 'Moderate Risk' | 'High Risk' | 'Dangerous';

export interface ProductInfo {
  url: string;
  name?: string;
  asin?: string;
}
