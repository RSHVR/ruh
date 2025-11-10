import type { ProductAnalysis, RiskLevel } from '@/types';

/**
 * Calculate harm score from overall score
 */
export function getHarmScore(overallScore: number): number {
  return 100 - overallScore;
}

/**
 * Get risk level from harm score
 */
export function getRiskLevel(harmScore: number): RiskLevel {
  if (harmScore <= 20) return 'Safe';
  if (harmScore <= 40) return 'Low Risk';
  if (harmScore <= 60) return 'Moderate Risk';
  if (harmScore <= 80) return 'High Risk';
  return 'Dangerous';
}

/**
 * Get CSS class for risk level
 */
export function getRiskClass(riskLevel: RiskLevel): string {
  const map: Record<RiskLevel, string> = {
    'Safe': 'risk-safe',
    'Low Risk': 'risk-low',
    'Moderate Risk': 'risk-moderate',
    'High Risk': 'risk-high',
    'Dangerous': 'risk-dangerous'
  };
  return map[riskLevel];
}

/**
 * Get color for risk level
 */
export function getRiskColor(riskLevel: RiskLevel): string {
  const map: Record<RiskLevel, string> = {
    'Safe': '#10b981',
    'Low Risk': '#84cc16',
    'Moderate Risk': '#f59e0b',
    'High Risk': '#ef4444',
    'Dangerous': '#dc2626'
  };
  return map[riskLevel];
}

/**
 * Check if URL is an Amazon product page
 */
export function isAmazonProductPage(url: string): boolean {
  try {
    const urlObj = new URL(url);
    const isAmazon =
      urlObj.hostname.includes('amazon.com') || urlObj.hostname.includes('amazon.ca');
    const hasDP = urlObj.pathname.includes('/dp/') || urlObj.pathname.includes('/gp/product/');
    return isAmazon && hasDP;
  } catch {
    return false;
  }
}

/**
 * Extract product ASIN from Amazon URL
 */
export function extractASIN(url: string): string | null {
  try {
    const match = url.match(/\/dp\/([A-Z0-9]{10})|\/gp\/product\/([A-Z0-9]{10})/);
    return match ? match[1] || match[2] : null;
  } catch {
    return null;
  }
}

/**
 * Format timestamp to relative time
 */
export function formatTimeAgo(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

/**
 * Generate user UUID (stored in chrome.storage)
 */
export async function getUserId(): Promise<string> {
  const result = await chrome.storage.local.get(['userId']);
  if (result.userId) {
    return result.userId;
  }

  const uuid = crypto.randomUUID();
  await chrome.storage.local.set({ userId: uuid });
  return uuid;
}
