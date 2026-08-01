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
  import {
    extractSources,
    sourceRefFromUrl,
    type SourceRef,
  } from "../lib/sources";
  import { namesMatch } from "../lib/matching";
  import SourceStack from "./SourceStack.svelte";
  import SourcesSheet from "./SourcesSheet.svelte";
  import FeatureBoard from "./FeatureBoard.svelte";
  import AnalysisFeedback from "./AnalysisFeedback.svelte";

  /**
   * Merge description-parsed URLs with the agent's structured
   * research_sources whose key finding mentions this concern. The structured
   * entries carry per-source notes ({finding}) for the sources sheet.
   */
  function findingSources(name: string, parsed: SourceRef[]): SourceRef[] {
    const research = (productAnalysis?.research_sources ?? []) as {
      url?: string;
      finding?: string;
    }[];
    const merged: SourceRef[] = parsed.map((s) => ({ ...s }));
    const seen = new Set(merged.map((s) => s.url));

    for (const rs of research) {
      if (!rs.url) continue;
      if (seen.has(rs.url)) {
        // Same URL already parsed from the description — attach the note.
        const hit = merged.find((s) => s.url === rs.url);
        if (hit && !hit.note && rs.finding) hit.note = rs.finding;
        continue;
      }
      if (rs.finding && namesMatch(name, rs.finding)) {
        const ref = sourceRefFromUrl(rs.url, rs.finding);
        if (ref) {
          merged.push(ref);
          seen.add(ref.url);
        }
      }
    }
    return merged;
  }

  // Sources sheet state: which finding's receipts are being viewed.
  let sourcesSheet = $state<{
    title: string;
    reason: string;
    sources: SourceRef[];
  } | null>(null);

  interface Props {
    analysis: AnalysisResponse | null;
    loading?: boolean;
    error?: string | null;
    visible?: boolean;
  }

  let { analysis, loading = false, error = null, visible = true }: Props = $props();

  const productAnalysis = $derived(analysis?.analysis);
  const urlHash = $derived(analysis?.url_hash ?? "");


  // "Other concerns" grouped by severity, worst first, for the
  // Flagged Substances section (group headers replace per-card badges).
  const SEVERITY_ORDER = ['severe', 'high', 'moderate', 'low'] as const;
  const SEVERITY_LABELS: Record<string, string> = {
    severe: 'Severe',
    high: 'High concern',
    moderate: 'Moderate',
    low: 'Low',
    unknown: 'Noted',
  };
  const groupedConcerns = $derived.by(() => {
    const concerns = productAnalysis?.other_concerns ?? [];
    const groups: { severity: string; items: typeof concerns }[] = [];
    for (const sev of [...SEVERITY_ORDER, 'unknown']) {
      const items = concerns.filter(
        (c) =>
          (c.severity ?? 'unknown') === sev ||
          (sev === 'unknown' && !SEVERITY_ORDER.includes(c.severity as never)),
      );
      if (items.length > 0) groups.push({ severity: sev, items });
    }
    return groups;
  });
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
                      productAnalysis.allergens_detected.some((a) =>
                        namesMatch(ingredient, a.name),
                      )}
                    {@const isPFAS = productAnalysis.pfas_detected.some((p) =>
                      namesMatch(ingredient, p.name),
                    )}
                    {@const isToxic = productAnalysis.other_concerns.some((c) =>
                      namesMatch(ingredient, c.name),
                    )}
                    {@const isSafe =
                      !isAllergen &&
                      !isPFAS &&
                      !isToxic &&
                      productAnalysis.allergens_detected.length === 0 &&
                      productAnalysis.pfas_detected.length === 0 &&
                      productAnalysis.other_concerns.length === 0}
                    <span
                      class="ingredient-badge {isAllergen
                        ? 'badge-allergen'
                        : isPFAS
                          ? 'badge-pfas'
                          : isToxic
                            ? 'badge-toxic'
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
              {@const allergenParsed = extractSources(allergen.source)}
              <div class="item-card">
                <div class="flex items-start justify-between gap-3">
                  <div class="flex-1">
                    <p class="font-medium text-ink-primary">{allergen.name}</p>
                    <p class="text-sm text-ink-secondary mt-1">
                      {allergenParsed.reason || allergen.source}
                    </p>
                    <SourceStack
                      sources={allergenParsed.sources}
                      onOpen={() =>
                        (sourcesSheet = {
                          title: allergen.name,
                          reason: allergenParsed.reason,
                          sources: allergenParsed.sources,
                        })}
                    />
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
              {@const pfasParsed = extractSources(pfas.source)}
              <div class="item-card">
                <p class="font-medium text-ink-primary">{pfas.name}</p>
                {#if pfas.cas_number}
                  <p class="text-xs text-ink-muted mt-1">
                    CAS: {pfas.cas_number}
                  </p>
                {/if}
                <p class="text-sm text-ink-secondary mt-2">{pfas.body_effects}</p>
                {#if pfasParsed.sources.length > 0}
                  <SourceStack
                    sources={pfasParsed.sources}
                    onOpen={() =>
                      (sourcesSheet = {
                        title: pfas.name,
                        reason: pfas.body_effects,
                        sources: pfasParsed.sources,
                      })}
                  />
                {:else}
                  <p class="text-xs text-ink-muted mt-2">Source: {pfas.source}</p>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Flagged Substances (grouped by severity, worst first) -->
      {#if productAnalysis.other_concerns.length > 0}
        <div class="section">
          <h3 class="section-subtitle">⚠️ Flagged Substances</h3>
          {#each groupedConcerns as group (group.severity)}
            <div class="severity-group">
              <p class="severity-group-header severity-text-{group.severity}">
                {SEVERITY_LABELS[group.severity]}
              </p>
              <div class="space-y-2">
                {#each group.items as concern}
                  {@const parsed = extractSources(concern.description)}
                  {@const cardSources = findingSources(concern.name, parsed.sources)}
                  <div class="item-card">
                    <div class="flex items-start justify-between gap-3">
                      <div class="flex-1">
                        <p class="font-medium text-ink-primary">{concern.name}</p>
                        <p class="text-sm text-ink-secondary mt-1">
                          {parsed.reason || concern.description}
                        </p>
                        <SourceStack
                          sources={cardSources}
                          onOpen={() =>
                            (sourcesSheet = {
                              title: concern.name,
                              reason: parsed.reason,
                              sources: cardSources,
                            })}
                        />
                      </div>
                    </div>
                  </div>
                {/each}
              </div>
            </div>
          {/each}
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

    <!-- Rate this analysis / report a bug — sits just above the feature board -->
    {#if urlHash}
      <div class="feedback-slot">
        <AnalysisFeedback {urlHash} />
      </div>
    {/if}

    <!-- Feature request board — last section of the analysis page -->
    <div class="feature-board-slot">
      <FeatureBoard />
    </div>
  </div>

  {#if sourcesSheet}
    <SourcesSheet
      title={sourcesSheet.title}
      reason={sourcesSheet.reason}
      sources={sourcesSheet.sources}
      onClose={() => (sourcesSheet = null)}
    />
  {/if}
</div>

<style lang="postcss">
  /* Fonts loaded from app.css: Instrument Sans + Poppins */

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
    /* No own scroller: the side-panel container is the single scroll context.
       (overflow-y:auto here also force-computed overflow-x to auto, which is
       where the phantom horizontal scrollbar came from.) */
    @apply flex-1;
    padding: 20px;
  }

  .section {
    margin-bottom: 20px;
  }

  .section-title {
    font-family: 'Instrument Sans', sans-serif;
    font-weight: 700;
    font-size: 28px;
    color: var(--color-text);
    letter-spacing: -0.02em;
  }

  .section-subtitle {
    font-family: 'Instrument Sans', sans-serif;
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
    font-family: 'Instrument Sans', sans-serif;
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
    max-width: 100%;
    overflow: hidden;
  }

  /* Long unbreakable strings (source URLs, chemical names) must never widen
     the card: let the flex text column shrink below its content width and
     wrap anywhere. The severity badge keeps flex-shrink: 0 and stays put. */
  .item-card > div > div {
    min-width: 0;
  }

  .item-card p {
    overflow-wrap: anywhere;
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

  .badge-toxic {
    background: rgba(193, 138, 114, 0.5); /* Alert Rust tint */
    color: #2a120a;
    border-color: rgba(193, 138, 114, 0.75);
  }

  .severity-group {
    margin-bottom: 14px;
  }

  .severity-group-header {
    font-family: 'Poppins', sans-serif;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 0 0 6px 2px;
  }

  .severity-text-severe {
    color: #a63d2d;
  }

  .severity-text-high {
    color: #c45c4a;
  }

  .severity-text-moderate {
    color: #b07f42;
  }

  .severity-text-low {
    color: #7a9c6f;
  }

  .severity-text-unknown {
    color: #6b6560;
  }

  .feedback-slot {
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid rgba(168, 184, 159, 0.25);
  }

  .feature-board-slot {
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid rgba(168, 184, 159, 0.25);
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
