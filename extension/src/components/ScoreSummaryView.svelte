<script lang="ts">
  import type { AnalysisResponse } from '../types';
  import { authStore } from '../lib/auth-store.svelte';

  let {
    analysis,
    onUnlock,
  }: {
    analysis: AnalysisResponse;
    onUnlock: () => void;
  } = $props();

  let productAnalysis = $derived(analysis.analysis);
  let harmScore = $derived(100 - productAnalysis.overall_score);
  let riskLevel = $derived(
    harmScore <= 20
      ? 'Safe'
      : harmScore <= 40
        ? 'Low Risk'
        : harmScore <= 60
          ? 'Moderate Risk'
          : harmScore <= 80
            ? 'High Risk'
            : 'Dangerous',
  );
  let riskClass = $derived(
    harmScore <= 20
      ? 'safe'
      : harmScore <= 40
        ? 'low'
        : harmScore <= 60
          ? 'moderate'
          : 'high',
  );

  let allergenCount = $derived(productAnalysis.allergens_detected?.length ?? 0);
  let pfasCount = $derived(productAnalysis.pfas_detected?.length ?? 0);
  let concernCount = $derived(productAnalysis.other_concerns?.length ?? 0);
  let totalFindings = $derived(allergenCount + pfasCount + concernCount);

  let hasCredits = $derived(
    authStore.userTier === 'unlimited' || (authStore.creditBalance ?? 0) > 0,
  );
  let unlocking = $state(false);

  async function handleUnlock() {
    unlocking = true;
    onUnlock();
    // Parent handles the actual API call and state update
  }

  // Donut chart calculations
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  let offset = $derived(circumference - (harmScore / 100) * circumference);
  let donutColor = $derived(
    harmScore <= 20
      ? '#94A37C'
      : harmScore <= 40
        ? '#C4B078'
        : harmScore <= 60
          ? '#D4956A'
          : '#C46E5A',
  );
</script>

<div class="score-summary">
  <!-- Score donut -->
  <div class="score-section">
    <div class="donut-wrapper">
      <svg viewBox="0 0 100 100" class="donut">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#E8DCC8" stroke-width="8" />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke={donutColor}
          stroke-width="8"
          stroke-dasharray={circumference}
          stroke-dashoffset={offset}
          stroke-linecap="round"
          transform="rotate(-90 50 50)"
        />
      </svg>
      <div class="score-label">
        <span class="score-number">{harmScore}</span>
        <span class="score-unit">/ 100</span>
      </div>
    </div>

    <div class="product-info">
      <h2>{productAnalysis.product_name || 'Product'}</h2>
      {#if productAnalysis.brand}
        <p class="brand">{productAnalysis.brand}</p>
      {/if}
      <span class="risk-badge {riskClass}">{riskLevel}</span>
    </div>
  </div>

  <!-- Teaser: what's behind the gate -->
  {#if totalFindings > 0}
    <div class="findings-teaser">
      <h3>Findings detected</h3>
      <ul>
        {#if allergenCount > 0}
          <li>{allergenCount} allergen{allergenCount > 1 ? 's' : ''} found</li>
        {/if}
        {#if pfasCount > 0}
          <li>{pfasCount} PFAS compound{pfasCount > 1 ? 's' : ''} detected</li>
        {/if}
        {#if concernCount > 0}
          <li>{concernCount} other concern{concernCount > 1 ? 's' : ''}</li>
        {/if}
      </ul>
      <p class="unlock-prompt">Unlock to see full details and recommendations</p>
    </div>
  {:else}
    <div class="findings-teaser">
      <p class="no-findings">No major concerns detected. Unlock for full ingredient breakdown.</p>
    </div>
  {/if}

  <!-- Unlock button -->
  <button
    class="unlock-btn"
    onclick={handleUnlock}
    disabled={!hasCredits || unlocking}
  >
    {#if unlocking}
      Unlocking...
    {:else if hasCredits}
      Unlock Full Report (1 credit)
    {:else}
      No Credits — Upgrade to Continue
    {/if}
  </button>
</div>

<style>
  .score-summary {
    padding: 24px;
  }

  .score-section {
    display: flex;
    align-items: center;
    gap: 20px;
    margin-bottom: 24px;
  }

  .donut-wrapper {
    position: relative;
    width: 100px;
    height: 100px;
    flex-shrink: 0;
  }

  .donut {
    width: 100%;
    height: 100%;
  }

  .score-label {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }

  .score-number {
    font-family: 'Instrument Sans', sans-serif;
    font-size: 28px;
    font-weight: 700;
    color: var(--color-text-primary, #3A3633);
    line-height: 1;
  }

  .score-unit {
    font-family: 'Poppins', sans-serif;
    font-size: 10px;
    color: var(--color-text-secondary, #6B6560);
  }

  .product-info h2 {
    font-family: 'Instrument Sans', sans-serif;
    font-size: 18px;
    font-weight: 600;
    color: var(--color-text-primary, #3A3633);
    margin: 0 0 4px;
    line-height: 1.3;
  }

  .brand {
    font-family: 'Poppins', sans-serif;
    font-size: 12px;
    color: var(--color-text-secondary, #6B6560);
    margin: 0 0 8px;
  }

  .risk-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-family: 'Poppins', sans-serif;
    font-size: 11px;
    font-weight: 600;
  }

  .risk-badge.safe { background: #e8f5e9; color: #2e7d32; }
  .risk-badge.low { background: #fff8e1; color: #f57f17; }
  .risk-badge.moderate { background: #fff3e0; color: #e65100; }
  .risk-badge.high { background: #fce4ec; color: #c62828; }

  .findings-teaser {
    background: var(--color-bg-secondary, #f5f0e8);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 20px;
  }

  .findings-teaser h3 {
    font-family: 'Poppins', sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: var(--color-text-primary, #3A3633);
    margin: 0 0 8px;
  }

  .findings-teaser ul {
    list-style: none;
    padding: 0;
    margin: 0 0 8px;
  }

  .findings-teaser li {
    font-family: 'Poppins', sans-serif;
    font-size: 13px;
    color: var(--color-text-secondary, #6B6560);
    padding: 3px 0;
  }

  .findings-teaser li::before {
    content: '•';
    color: var(--color-rust, #C46E5A);
    margin-right: 8px;
    font-weight: bold;
  }

  .unlock-prompt {
    font-family: 'Poppins', sans-serif;
    font-size: 12px;
    color: var(--color-sage, #94A37C);
    font-weight: 500;
    margin: 0;
  }

  .no-findings {
    font-family: 'Poppins', sans-serif;
    font-size: 13px;
    color: var(--color-text-secondary, #6B6560);
    margin: 0;
  }

  .unlock-btn {
    width: 100%;
    padding: 14px;
    background: var(--color-sage, #94A37C);
    color: white;
    border: none;
    border-radius: 10px;
    font-family: 'Poppins', sans-serif;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 150ms ease;
  }

  .unlock-btn:hover:not(:disabled) {
    background: #7d8a68;
    transform: translateY(-1px);
  }

  .unlock-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
  }
</style>
