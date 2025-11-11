import type { AnalysisResponse } from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001';
const API_KEY = import.meta.env.VITE_API_KEY;

export class EjectAPI {
  private baseUrl: string;
  private apiKey: string;

  constructor(baseUrl: string = API_BASE_URL, apiKey: string = API_KEY) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;

    // Debug logging
    if (import.meta.env.VITE_DEBUG === 'true') {
      console.log('[Eject API] Initialized with:', {
        baseUrl: this.baseUrl,
        hasApiKey: !!this.apiKey,
        apiKeyPrefix: this.apiKey?.substring(0, 8) + '...'
      });
    }
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

      const requestUrl = `${this.baseUrl}/api/analyze`;
      const requestBody = {
        product_url: productUrl,
        allergen_profile: allergenProfile,
        force_refresh: false
      };

      if (import.meta.env.VITE_DEBUG === 'true') {
        console.log('[Eject API] Making request:', {
          url: requestUrl,
          method: 'POST',
          headers: Object.keys(headers),
          hasAuth: !!headers['Authorization']
        });
      }

      const response = await fetch(requestUrl, {
        method: 'POST',
        headers,
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
      }

      const data: AnalysisResponse = await response.json();

      if (import.meta.env.VITE_DEBUG === 'true') {
        console.log('[Eject API] Response received:', {
          status: response.status,
          hasData: !!data
        });
      }

      return data;
    } catch (error) {
      console.error('[Eject API] Request failed:', {
        error: error instanceof Error ? error.message : String(error),
        url: this.baseUrl,
        type: error instanceof TypeError ? 'Network/CORS error' : 'Other error'
      });
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
