<script lang="ts">
  /**
   * AnalysisView - Product Analysis Results Display
   *
   * Pure presentation component that renders product safety analysis results.
   * Displays harm score, allergens, PFAS compounds, and other concerns.
   *
   * This component has no Chrome API interactions or state management -
   * it purely renders the analysis data passed via props.
   */
  import type { AnalysisResponse } from "@/types";
  import {
    getHarmScore,
    getRiskLevel,
    getRiskClass,
    formatTimeAgo,
  } from "@/lib/utils";

  interface Props {
    analysis: AnalysisResponse | null;
    loading?: boolean;
    error?: string | null;
    visible?: boolean;
  }

  let { analysis, loading = false, error = null, visible = true }: Props = $props();

  const productAnalysis = $derived(analysis?.analysis);
  const harmScore = $derived(productAnalysis
    ? getHarmScore(productAnalysis.overall_score)
    : 0);
  const riskLevel = $derived(getRiskLevel(harmScore));
  const riskClass = $derived(getRiskClass(riskLevel));

  // Donut chart calculations
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = $derived(circumference - (harmScore / 100) * circumference);

  // Get color based on risk level (ruh brand guidelines)
  function getScoreColor(score: number): string {
    if (score <= 30) return "#9BB88F"; // Safe Green
    if (score <= 50) return "#D4A574"; // Caution Amber
    if (score <= 70) return "#c45c4a"; // High Risk Red
    return "#a63d2d"; // Severe Risk - Deep Red
  }

  const scoreColor = $derived(getScoreColor(harmScore));

  function handleRetry() {
    // Reload the page to trigger a new analysis
    window.location.reload();
  }
</script>

<div class="sidebar">
  <!-- Content -->
  <div class="content">
    {#if loading}
      <div class="loading">
        <div class="spinner"></div>
        <p class="text-ink-secondary mt-4">Analyzing product safety...</p>
        <p class="text-sm text-ink-muted mt-2">This may take 10-30 seconds</p>
      </div>
    {:else if error}
      <div class="error">
        <span class="text-4xl">⚠️</span>
        <h3 class="text-lg font-semibold text-alert mt-3">Analysis Failed</h3>
        <p class="text-sm text-ink-secondary mt-2">{error}</p>
        <button class="retry-btn" onclick={handleRetry}>
          Try Again
        </button>
      </div>
    {:else if productAnalysis}
      <!-- Product Info -->
      <div class="section">
        <h2 class="section-title">
          {productAnalysis.product_name || "Product Analysis"}
        </h2>
        {#if productAnalysis.brand}
          <p class="text-sm text-ink-secondary">{productAnalysis.brand}</p>
        {/if}
        {#if productAnalysis.analyzed_at}
          <p class="text-xs text-ink-muted mt-1">
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
            <h3 class="text-lg font-semibold text-ink-primary">{riskLevel}</h3>
            <p class="text-sm text-ink-secondary">Harm Level</p>
            <div class="mt-2 flex items-center">
              <span class="text-base font-semibold text-ink-primary"
                >{Math.round(productAnalysis.confidence * 100)}%</span
              >
              <span class="text-xs text-ink-muted ml-1">confidence</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Analysis Details / Proof of Checks -->
      <div class="section">
        <h3 class="section-subtitle">
          {productAnalysis.ingredients.length > 0
            ? "🔍 Analysis Complete"
            : "⚠️ Analysis Inconclusive"}
        </h3>
        <div class="space-y-3">
          <!-- Ingredients Display -->
          {#if productAnalysis.ingredients.length > 0}
            <div class="analysis-detail-item">
              <div>
                <p class="font-medium text-ink-primary mb-3">
                  Ingredients Analyzed ({productAnalysis.ingredients.length})
                </p>
                <div class="ingredient-grid">
                  {#each productAnalysis.ingredients as ingredient}
                    {@const isAllergen =
                      productAnalysis.allergens_detected.some(
                        (a) =>
                          ingredient
                            .toLowerCase()
                            .includes(a.name.toLowerCase()) ||
                          a.name
                            .toLowerCase()
                            .includes(ingredient.toLowerCase()),
                      )}
                    {@const isPFAS = productAnalysis.pfas_detected.some(
                      (p) =>
                        ingredient
                          .toLowerCase()
                          .includes(p.name.toLowerCase()) ||
                        p.name.toLowerCase().includes(ingredient.toLowerCase()),
                    )}
                    {@const isToxic = productAnalysis.other_concerns.some(
                      (c) =>
                        ingredient
                          .toLowerCase()
                          .includes(c.name.toLowerCase()) ||
                        c.name.toLowerCase().includes(ingredient.toLowerCase()),
                    )}
                    {@const isSafe =
                      !isAllergen &&
                      !isPFAS &&
                      !isToxic &&
                      productAnalysis.allergens_detected.length === 0 &&
                      productAnalysis.pfas_detected.length === 0 &&
                      productAnalysis.other_concerns.length === 0}
                    <span
                      class="ingredient-badge {isAllergen || isPFAS || isToxic
                        ? isAllergen
                          ? 'badge-allergen'
                          : 'badge-pfas'
                        : isSafe
                          ? 'badge-safe'
                          : 'badge-unknown'}"
                    >
                      {ingredient}
                    </span>
                  {/each}
                </div>
              </div>
            </div>
          {:else}
            <div class="analysis-detail-item">
              <div class="flex items-center">
                <span class="text-2xl mr-3">📋</span>
                <div>
                  <p class="font-medium text-ink-primary">Ingredients Analyzed</p>
                  <p class="text-sm text-ink-secondary">No Ingredients Found</p>
                </div>
              </div>
            </div>
          {/if}

          <div class="analysis-detail-item">
            <div class="flex items-center">
              <span class="text-2xl mr-3">🧪</span>
              <div>
                <p class="font-medium text-ink-primary">Database Screening</p>
                <p class="text-sm text-ink-secondary">
                  Checked against allergen and PFAS compound databases
                </p>
              </div>
            </div>
          </div>

          <div class="analysis-detail-item">
            <div class="flex items-center">
              <span class="text-2xl mr-3"
                >{productAnalysis.confidence < 0.3 ? "🚨" : "✅"}</span
              >
              <div>
                <p class="font-medium text-ink-primary">Confidence Level</p>
                {#if productAnalysis.confidence < 0.3}
                  <p class="text-sm text-caution font-semibold">
                    {Math.round(productAnalysis.confidence * 100)}% - Low
                    Confidence
                  </p>
                  <p class="text-xs text-ink-secondary mt-1">
                    Limited ingredient data available. Analysis based on
                    database screening only. Results may be incomplete.
                  </p>
                {:else}
                  <p class="text-sm text-ink-secondary">
                    {Math.round(productAnalysis.confidence * 100)}% - Based on
                    available data and sources
                  </p>
                {/if}
              </div>
            </div>
          </div>

          {#if productAnalysis.allergens_detected.length === 0 && productAnalysis.pfas_detected.length === 0 && productAnalysis.other_concerns.length === 0}
            <div class="safe-result-box">
              <span class="text-4xl">✨</span>
              <p class="text-sm font-semibold mt-2">
                No Major Concerns Detected
              </p>
              <p class="text-xs mt-1">
                This product appears safe based on our analysis
              </p>
            </div>
          {/if}
        </div>
      </div>

      <!-- Allergens -->
      {#if productAnalysis.allergens_detected.length > 0}
        <div class="section">
          <h3 class="section-subtitle">⚠️ Allergens Detected</h3>
          <div class="space-y-2">
            {#each productAnalysis.allergens_detected as allergen}
              <div class="item-card">
                <div class="flex items-start justify-between gap-3">
                  <div class="flex-1">
                    <p class="font-medium text-ink-primary">{allergen.name}</p>
                    <p class="text-sm text-ink-secondary mt-1">{allergen.source}</p>
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
                <p class="font-medium text-ink-primary">{pfas.name}</p>
                {#if pfas.cas_number}
                  <p class="text-xs text-ink-muted mt-1">
                    CAS: {pfas.cas_number}
                  </p>
                {/if}
                <p class="text-sm text-ink-secondary mt-2">{pfas.body_effects}</p>
                <p class="text-xs text-ink-muted mt-2">Source: {pfas.source}</p>
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
                <div class="flex items-start justify-between gap-3">
                  <div class="flex-1">
                    <p class="font-medium text-ink-primary">{concern.name}</p>
                    <p class="text-sm text-ink-secondary mt-1">
                      {concern.description}
                    </p>
                    <p class="text-xs text-ink-muted mt-1">
                      Category: {concern.category}
                    </p>
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

      <!-- Alternatives (Phase 4) -->
      {#if analysis.alternatives && analysis.alternatives.length > 0}
        <div class="section">
          <h3 class="section-subtitle">🔄 Safer Alternatives</h3>
          <p class="text-sm text-ink-secondary mb-3">
            Based on your analysis, here are safer options:
          </p>
          <!-- Will implement in Phase 4 -->
        </div>
      {/if}
    {:else}
      <div class="empty">
        <span class="text-6xl">🛡️</span>
        <h3 class="text-lg font-semibold text-ink-primary mt-4">
          Product Safety Analysis
        </h3>
        <p class="text-sm text-ink-secondary mt-2">
          Navigate to an Amazon product page to analyze it for harmful
          substances.
        </p>
      </div>
    {/if}
  </div>
</div>

<style lang="postcss">
  /* Fonts loaded from app.css: Cormorant Infant + Poppins */

  /* CSS Custom Properties - ruh Brand Variables */
  :root {
    --color-primary: #e8dcc8; /* Soft Sand */
    --color-secondary: #a8b89f; /* Sage Green */
    --color-accent: #c9b5a0; /* Warm Taupe */
    --color-bg-primary: #fffbf5; /* Cream */
    --color-bg-secondary: #f5f0e8; /* Pale Linen */
    --color-safe: #9bb88f; /* Safe Green */
    --color-caution: #d4a574; /* Caution Amber */
    --color-alert: #c18a72; /* Alert Rust */
    --color-text: #3a3633; /* Deep Charcoal */
    --color-text-secondary: #5a534e; /* Medium Gray - darkened for WCAG AA */
  }

  .sidebar {
    @apply w-full h-full flex flex-col;
    background: var(--color-bg-primary); /* Cream */
    font-family: 'Poppins', -apple-system, BlinkMacSystemFont, sans-serif;
  }

  .slide-out {
    animation: slideOut 300ms ease-in forwards;
  }

  @keyframes slideOut {
    from {
      transform: translateX(0);
      opacity: 1;
    }
    to {
      transform: translateX(100%);
      opacity: 0;
    }
  }

  .close-btn {
    @apply rounded-full w-9 h-9 flex items-center justify-center transition-all text-xl font-bold;
    color: var(--color-text-secondary);
  }

  .close-btn:hover {
    background: rgba(168, 184, 159, 0.2); /* Sage green tint */
  }

  .content {
    @apply flex-1 overflow-y-auto;
    padding: 20px;
  }

  .section {
    margin-bottom: 20px;
  }

  .section-title {
    font-family: 'Cormorant Infant', Georgia, serif;
    font-weight: 700;
    font-size: 28px;
    color: var(--color-text);
    letter-spacing: -0.02em;
  }

  .section-subtitle {
    font-family: 'Work Sans', sans-serif;
    font-weight: 600;
    font-size: 15px;
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
    font-family: 'Work Sans', sans-serif;
    font-weight: 700;
    font-size: 34px;
    color: var(--color-text);
    line-height: 1;
  }

  .score-label {
    font-family: 'Poppins', sans-serif;
    font-size: 11px;
    color: var(--color-text-secondary);
    margin-top: 2px;
  }

  .item-card {
    padding: 16px;
    border-radius: 12px;
    background: var(--color-bg-secondary); /* Pale Linen */
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
    border: 1px solid rgba(168, 184, 159, 0.15); /* Light Sage tint */
    margin-bottom: 8px;
  }

  .analysis-detail-item {
    padding: 12px;
    border-radius: 8px;
    background: white;
    border: 1px solid rgba(168, 184, 159, 0.1);
  }

  .safe-result-box {
    text-align: center;
    padding: 16px;
    border-radius: 12px;
    background: rgba(155, 184, 143, 0.15); /* Safe green tint */
    border: 1px solid rgba(155, 184, 143, 0.3);
  }

  .safe-result-box p {
    color: #2d4525; /* Dark sage - 7:1 contrast */
  }

  .safe-result-box .text-xs {
    color: #3d5a35; /* Secondary - 5:1 contrast */
  }

  .severity-badge {
    padding: 4px 12px;
    border-radius: 9999px;
    font-family: 'Poppins', sans-serif;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    flex-shrink: 0;
  }

  .severity-low {
    background: #7a9c6f; /* Darker sage for white text */
    color: #fff;
  }

  .severity-moderate {
    background: #c4935f; /* Darker amber for white text */
    color: #fff;
  }

  .severity-high {
    background: #c45c4a;
    color: #fff; /* 4.5:1 contrast */
  }

  .severity-severe {
    background: #a63d2d;
    color: #fff; /* 5.5:1 contrast */
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
    to {
      transform: rotate(360deg);
    }
  }

  .retry-btn {
    margin-top: 16px;
    padding: 12px 24px;
    border-radius: 8px;
    font-family: 'Poppins', sans-serif;
    font-weight: 500;
    font-size: 14px;
    background: var(--color-primary); /* Soft Sand */
    color: var(--color-text);
    transition: all 150ms ease-in-out;
    border: none;
    cursor: pointer;
  }

  /* Ingredient Badge Styles */
  .ingredient-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 8px;
    margin-top: 8px;
  }

  .ingredient-badge {
    padding: 6px 12px;
    border-radius: 6px;
    font-family: 'Poppins', sans-serif;
    font-size: 12px;
    font-weight: 500;
    text-align: center;
    word-wrap: break-word;
    border: 1px solid transparent;
  }

  .badge-allergen {
    background: rgba(198, 118, 100, 0.6);
    color: #2a0f0b; /* Darkened for 5:1 contrast */
    border-color: rgba(198, 118, 100, 0.8);
  }

  .badge-pfas {
    background: rgba(212, 165, 116, 0.55);
    color: #1f1305; /* Darkened for 5.5:1 contrast */
    border-color: rgba(212, 165, 116, 0.75);
  }

  .badge-safe {
    background: rgba(155, 184, 143, 0.4); /* Slightly stronger tint */
    color: #1a2915; /* Darkened for 5:1 contrast */
    border-color: rgba(155, 184, 143, 0.55);
  }

  .badge-unknown {
    background: var(--color-bg-secondary);
    color: #4a4540; /* Darkened for 4.5:1 contrast */
    border-color: rgba(107, 101, 96, 0.3);
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
