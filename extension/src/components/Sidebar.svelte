<script lang="ts">
  import type { AnalysisResponse } from '@/types';
  import { getHarmScore, getRiskLevel, getRiskClass, formatTimeAgo } from '@/lib/utils';

  export let analysis: AnalysisResponse | null = null;
  export let loading: boolean = false;
  export let error: string | null = null;
  export let onClose: () => void;

  $: productAnalysis = analysis?.analysis;
  $: harmScore = productAnalysis ? getHarmScore(productAnalysis.overall_score) : 0;
  $: riskLevel = getRiskLevel(harmScore);
  $: riskClass = getRiskClass(riskLevel);

  // Donut chart calculations
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  $: strokeDashoffset = circumference - (harmScore / 100) * circumference;

  // Get color based on risk level (ruh brand guidelines)
  function getScoreColor(score: number): string {
    if (score <= 30) return '#9BB88F'; // Safe Green
    if (score <= 60) return '#D4A574'; // Caution Amber
    if (score <= 80) return '#C18A72'; // Alert Rust (moderate)
    return '#C18A72'; // Alert Rust (high)
  }

  $: scoreColor = getScoreColor(harmScore);
</script>

<div class="sidebar slide-in">
  <!-- Header -->
  <div class="header">
    <div class="flex items-center justify-between">
      <h1 class="brand-title">ruh</h1>
      <button onclick={onClose} class="close-btn" aria-label="Close sidebar">
        ✕
      </button>
    </div>
  </div>

  <!-- Content -->
  <div class="content">
    {#if loading}
      <div class="loading">
        <div class="spinner"></div>
        <p class="text-gray-600 mt-4">Analyzing product safety...</p>
        <p class="text-sm text-gray-500 mt-2">This may take 10-30 seconds</p>
      </div>
    {:else if error}
      <div class="error">
        <span class="text-4xl">⚠️</span>
        <h3 class="text-lg font-semibold text-red-600 mt-3">Analysis Failed</h3>
        <p class="text-sm text-gray-600 mt-2">{error}</p>
        <button class="retry-btn" onclick={() => window.location.reload()}>
          Try Again
        </button>
      </div>
    {:else if productAnalysis}
      <!-- Product Info -->
      <div class="section">
        <h2 class="section-title">{productAnalysis.product_name}</h2>
        <p class="text-sm text-gray-600">{productAnalysis.brand}</p>
        {#if productAnalysis.analyzed_at}
          <p class="text-xs text-gray-400 mt-1">
            Analyzed {formatTimeAgo(productAnalysis.analyzed_at)}
          </p>
        {/if}
      </div>

      <!-- Harm Score -->
      <div class="section">
        <div class="harm-score">
          <div class="donut-container">
            <svg class="donut-chart" viewBox="0 0 120 120">
              <!-- Background circle -->
              <circle
                class="donut-bg"
                cx="60"
                cy="60"
                r={radius}
                fill="none"
                stroke="rgba(157, 157, 156, 0.2)"
                stroke-width="8"
              />
              <!-- Animated progress circle -->
              <circle
                class="donut-progress"
                cx="60"
                cy="60"
                r={radius}
                fill="none"
                stroke={scoreColor}
                stroke-width="8"
                stroke-linecap="round"
                stroke-dasharray={circumference}
                stroke-dashoffset={strokeDashoffset}
                transform="rotate(-90 60 60)"
              />
            </svg>
            <div class="donut-text">
              <span class="score-number">{harmScore}</span>
              <span class="score-label">/ 100</span>
            </div>
          </div>
          <div class="ml-6">
            <h3 class="text-lg font-semibold text-gray-800">{riskLevel}</h3>
            <p class="text-sm text-gray-600">Harm Level</p>
            <p class="text-xs text-gray-500 mt-1">
              Confidence: {Math.round(productAnalysis.confidence * 100)}%
            </p>
          </div>
        </div>
      </div>

      <!-- Allergens -->
      {#if productAnalysis.allergens_detected.length > 0}
        <div class="section">
          <h3 class="section-subtitle">⚠️ Allergens Detected</h3>
          <div class="space-y-2">
            {#each productAnalysis.allergens_detected as allergen}
              <div class="item-card">
                <div class="flex items-start justify-between">
                  <div class="flex-1">
                    <p class="font-medium text-gray-800">{allergen.name}</p>
                    <p class="text-sm text-gray-600 mt-1">{allergen.source}</p>
                  </div>
                  <span class="severity-badge severity-{allergen.severity}">
                    {allergen.severity}
                  </span>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- PFAS -->
      {#if productAnalysis.pfas_detected.length > 0}
        <div class="section">
          <h3 class="section-subtitle">🧪 PFAS Detected (Forever Chemicals)</h3>
          <div class="space-y-3">
            {#each productAnalysis.pfas_detected as pfas}
              <div class="item-card">
                <p class="font-medium text-gray-800">{pfas.name}</p>
                {#if pfas.cas_number}
                  <p class="text-xs text-gray-500 mt-1">CAS: {pfas.cas_number}</p>
                {/if}
                <p class="text-sm text-gray-600 mt-2">{pfas.body_effects}</p>
                <p class="text-xs text-gray-500 mt-2">Source: {pfas.source}</p>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Other Concerns -->
      {#if productAnalysis.other_concerns.length > 0}
        <div class="section">
          <h3 class="section-subtitle">ℹ️ Other Concerns</h3>
          <div class="space-y-2">
            {#each productAnalysis.other_concerns as concern}
              <div class="item-card">
                <div class="flex items-start justify-between">
                  <div class="flex-1">
                    <p class="font-medium text-gray-800">{concern.name}</p>
                    <p class="text-sm text-gray-600 mt-1">{concern.description}</p>
                    <p class="text-xs text-gray-500 mt-1">Category: {concern.category}</p>
                  </div>
                  <span class="severity-badge severity-{concern.severity}">
                    {concern.severity}
                  </span>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- No Issues Found -->
      {#if productAnalysis.allergens_detected.length === 0 && productAnalysis.pfas_detected.length === 0 && productAnalysis.other_concerns.length === 0}
        <div class="section">
          <div class="text-center py-8">
            <span class="text-6xl">✅</span>
            <h3 class="text-lg font-semibold text-green-600 mt-4">No Major Concerns Found</h3>
            <p class="text-sm text-gray-600 mt-2">
              This product appears to be safe based on available information.
            </p>
          </div>
        </div>
      {/if}

      <!-- Alternatives (Phase 4) -->
      {#if analysis.alternatives && analysis.alternatives.length > 0}
        <div class="section">
          <h3 class="section-subtitle">🔄 Safer Alternatives</h3>
          <p class="text-sm text-gray-600 mb-3">Based on your analysis, here are safer options:</p>
          <!-- Will implement in Phase 4 -->
        </div>
      {/if}
    {:else}
      <div class="empty">
        <span class="text-6xl">🛡️</span>
        <h3 class="text-lg font-semibold text-gray-700 mt-4">Product Safety Analysis</h3>
        <p class="text-sm text-gray-600 mt-2">
          Navigate to an Amazon product page to analyze it for harmful substances.
        </p>
      </div>
    {/if}
  </div>
</div>

<style lang="postcss">
  @import url('https://fonts.googleapis.com/css2?family=Cormorant:wght@500;600&family=Inter:wght@400;500;600&display=swap');

  /* CSS Custom Properties - ruh Brand Variables */
  :root {
    --color-primary: #E8DCC8;        /* Soft Sand */
    --color-secondary: #A8B89F;      /* Sage Green */
    --color-accent: #C9B5A0;         /* Warm Taupe */
    --color-bg-primary: #FFFBF5;     /* Cream */
    --color-bg-secondary: #F5F0E8;   /* Pale Linen */
    --color-safe: #9BB88F;           /* Safe Green */
    --color-caution: #D4A574;        /* Caution Amber */
    --color-alert: #C18A72;          /* Alert Rust */
    --color-text: #3A3633;           /* Deep Charcoal */
    --color-text-secondary: #6B6560; /* Medium Gray */
  }

  .sidebar {
    @apply fixed top-0 right-0 h-full w-[400px] shadow-2xl z-[999999] flex flex-col;
    background: var(--color-bg-primary); /* Cream */
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  }

  .header {
    padding: 24px 20px;
    background: var(--color-bg-primary); /* Same as body - blends in */
    border-bottom: 1px solid var(--color-bg-secondary); /* Subtle separator */
  }

  .brand-title {
    font-family: 'Cormorant', serif;
    font-weight: 600;
    font-size: 44px;
    color: var(--color-accent); /* Warm Taupe */
    letter-spacing: 0.075em; /* +75 tracking */
    text-transform: lowercase;
  }

  .close-btn {
    @apply hover:bg-gray-200/60 rounded-full w-9 h-9 flex items-center justify-center transition-all text-xl font-bold;
    color: var(--color-text-secondary);
  }

  .content {
    @apply flex-1 overflow-y-auto;
    padding: 20px;
  }

  .section {
    margin-bottom: 20px;
  }

  .section-title {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 18px;
    color: var(--color-text);
  }

  .section-subtitle {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 16px;
    color: var(--color-text);
    margin-bottom: 12px;
  }

  .harm-score {
    @apply flex items-center;
    padding: 20px;
    border-radius: 12px;
    background: var(--color-bg-secondary); /* Powder Peach */
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  }

  /* Donut Chart */
  .donut-container {
    position: relative;
    width: 120px;
    height: 120px;
    flex-shrink: 0;
  }

  .donut-chart {
    width: 100%;
    height: 100%;
  }

  .donut-progress {
    transition: stroke-dashoffset 1.5s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .donut-text {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }

  .score-number {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 32px;
    color: var(--color-text);
    line-height: 1;
  }

  .score-label {
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    color: var(--color-text-secondary);
    margin-top: 4px;
  }

  .item-card {
    padding: 16px;
    border-radius: 12px;
    background: var(--color-bg-secondary); /* Pale Linen */
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
    border: 1px solid rgba(168, 184, 159, 0.15); /* Light Sage tint */
    margin-bottom: 8px;
  }

  .severity-badge {
    padding: 4px 12px;
    border-radius: 9999px;
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    font-weight: 500;
    text-transform: uppercase;
    flex-shrink: 0;
  }

  .severity-low {
    background: var(--color-safe);
    color: #2D4A2A;
  }

  .severity-moderate {
    background: var(--color-caution);
    color: #6B4E2A;
  }

  .severity-high {
    background: var(--color-alert);
    color: #5C3A2D;
  }

  .severity-severe {
    background: var(--color-alert);
    color: #5C3A2D;
  }

  .loading,
  .error,
  .empty {
    @apply flex flex-col items-center justify-center text-center;
    padding: 48px 20px;
  }

  .spinner {
    width: 48px;
    height: 48px;
    border: 4px solid;
    border-radius: 50%;
    border-color: var(--color-bg-secondary);
    border-top-color: var(--color-text-secondary);
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .retry-btn {
    margin-top: 16px;
    padding: 12px 24px;
    border-radius: 8px;
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    font-size: 15px;
    background: var(--color-primary); /* Soft Sand */
    color: var(--color-text);
    transition: all 150ms ease-in-out;
    border: none;
    cursor: pointer;
  }

  .retry-btn:hover {
    background: var(--color-accent); /* Warm Taupe */
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  .retry-btn:active {
    transform: scale(0.98);
  }
</style>
