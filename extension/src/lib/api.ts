import type { AnalysisResponse } from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';
const API_KEY = import.meta.env.VITE_API_KEY;

export class EjectAPI {
  private baseUrl: string;
  private apiKey: string;

  constructor(baseUrl: string = API_BASE_URL, apiKey: string = API_KEY) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  async analyzeProduct(
    productUrl: string,
    allergenProfile: string[] = []
  ): Promise<AnalysisResponse> {
    try {
      const headers: HeadersInit = {
        'Content-Type': 'application/json'
      };

      // Add Authorization header if API key is configured
      if (this.apiKey) {
        headers['Authorization'] = `Bearer ${this.apiKey}`;
      }

      const response = await fetch(`${this.baseUrl}/api/analyze`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          product_url: productUrl,
          allergen_profile: allergenProfile,
          force_refresh: false
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
      }

      const data: AnalysisResponse = await response.json();
      return data;
    } catch (error) {
      console.error('API Error:', error);
      throw error;
    }
  }

  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/api/health`);
      return response.ok;
    } catch {
      return false;
    }
  }
}

export const api = new EjectAPI();
