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

  // Get color based on risk level
  function getScoreColor(score: number): string {
    if (score <= 20) return '#10B981'; // Green
    if (score <= 50) return '#F59E0B'; // Orange
    return '#EF4444'; // Red
  }

  $: scoreColor = getScoreColor(harmScore);
</script>

<div class="sidebar slide-in">
  <!-- Header -->
  <div class="header">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="text-2xl">🛡️</span>
        <h1 class="brand-title">Eject</h1>
      </div>
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
                stroke="#E5E7EB"
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
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@700;800;900&display=swap');

  .sidebar {
    @apply fixed top-0 right-0 h-full w-[400px] shadow-2xl z-[999999] flex flex-col;
    background: #F5F1ED; /* Warm neutral beige */
    border-radius: 0 0 0 24px;
  }

  .header {
    @apply p-5 shadow-sm;
    background: linear-gradient(135deg, #FAF8F6 0%, #F5F1ED 100%);
    border-radius: 0 0 0 24px;
  }

  .brand-title {
    font-family: 'Outfit', sans-serif;
    font-weight: 900;
    font-size: 26px;
    background: linear-gradient(135deg, #2D3748 0%, #4A5568 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.5px;
  }

  .close-btn {
    @apply hover:bg-gray-200/60 rounded-full w-9 h-9 flex items-center justify-center transition-all text-xl font-bold;
    color: #4A5568;
  }

  .content {
    @apply flex-1 overflow-y-auto p-5;
  }

  .section {
    @apply mb-5;
  }

  .section-title {
    @apply text-lg font-bold text-gray-800;
  }

  .section-subtitle {
    @apply text-base font-semibold text-gray-800 mb-3;
  }

  .harm-score {
    @apply flex items-center p-5 rounded-2xl;
    background: #FAF8F6; /* Lighter warm neutral for cards */
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
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
    @apply text-3xl font-bold;
    color: #2D3748;
    line-height: 1;
  }

  .score-label {
    @apply text-xs mt-1;
    color: #718096;
  }

  .item-card {
    @apply p-4 rounded-xl;
    background: #FAF8F6; /* Lighter warm neutral */
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
    border: 1px solid #F0EBE6;
  }

  .severity-badge {
    @apply px-3 py-1 rounded-full text-xs font-medium uppercase shrink-0;
  }

  .severity-low {
    background: #D1FAE5; /* Soft pastel green */
    color: #059669;
  }

  .severity-moderate {
    background: #FEF3C7; /* Soft pastel yellow */
    color: #D97706;
  }

  .severity-high {
    background: #FECACA; /* Soft pastel red/pink */
    color: #DC2626;
  }

  .severity-severe {
    background: #FECACA;
    color: #991B1B;
  }

  .loading,
  .error,
  .empty {
    @apply flex flex-col items-center justify-center text-center py-12;
  }

  .spinner {
    @apply w-12 h-12 border-4 rounded-full animate-spin;
    border-color: #E5E7EB;
    border-top-color: #6B7280;
  }

  .retry-btn {
    @apply mt-4 px-5 py-2.5 rounded-xl transition-all font-medium;
    background: #4A5568;
    color: white;
  }

  .retry-btn:hover {
    background: #2D3748;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }
</style>
