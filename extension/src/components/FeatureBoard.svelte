<script lang="ts">
  /**
   * FeatureBoard - collapsible feature-request board.
   *
   * Pinned at the bottom of the authenticated side panel across all states
   * (empty / score / analysis). Lets beta users upvote existing requests and
   * suggest new ones. Voting is optimistic (see lib/feature-board.ts); the list
   * is fetched lazily the first time the block is expanded.
   */
  import { authStore } from '../lib/auth-store.svelte';
  import {
    fetchFeatures,
    voteFeature,
    submitFeature,
    toggleVoteInList,
    reconcileVoteInList,
    replaceFeatureInList,
    prependFeature,
    FeatureBoardError,
    type Feature,
  } from '../lib/feature-board';

  const MAX_TITLE = 120;

  let expanded = $state(false);
  let loaded = $state(false);
  let loading = $state(false);
  let loadError = $state('');

  let features = $state<Feature[]>([]);
  let votingIds = $state<string[]>([]);

  let newTitle = $state('');
  let submitting = $state(false);
  let submitError = $state('');

  const statusLabels: Record<string, string> = {
    planned: 'Planned',
    in_progress: 'In progress',
    shipped: 'Shipped',
    declined: 'Declined',
  };

  function statusLabel(status: string): string {
    return statusLabels[status] ?? status.replace(/_/g, ' ');
  }

  async function toggleExpanded() {
    expanded = !expanded;
    if (expanded && !loaded && !loading) {
      await loadFeatures();
    }
  }

  async function loadFeatures() {
    const token = authStore.getAccessToken();
    if (!token) {
      loadError = 'Sign in to see feature requests.';
      return;
    }
    loading = true;
    loadError = '';
    try {
      features = await fetchFeatures(token);
      loaded = true;
    } catch {
      loadError = 'Could not load requests — try again.';
    } finally {
      loading = false;
    }
  }

  async function handleVote(feature: Feature) {
    if (votingIds.includes(feature.id)) return;
    const token = authStore.getAccessToken();
    if (!token) return;

    const original = feature;
    // Optimistic: reflect the toggle immediately, then reconcile/revert.
    features = toggleVoteInList(features, feature.id);
    votingIds = [...votingIds, feature.id];

    try {
      const res = await voteFeature(token, feature.id);
      features = reconcileVoteInList(features, feature.id, res);
    } catch {
      features = replaceFeatureInList(features, original);
    } finally {
      votingIds = votingIds.filter((id) => id !== feature.id);
    }
  }

  async function handleSubmit() {
    const title = newTitle.trim();
    if (!title || submitting) return;
    const token = authStore.getAccessToken();
    if (!token) return;

    submitting = true;
    submitError = '';
    try {
      const created = await submitFeature(token, title, undefined);
      features = prependFeature(features, created);
      newTitle = '';
    } catch (err) {
      submitError =
        err instanceof FeatureBoardError && err.status === 429
          ? 'Limit reached for today — thanks for the enthusiasm!'
          : 'Could not submit — please try again.';
    } finally {
      submitting = false;
    }
  }
</script>

<section class="feature-board">
  <button
    class="board-header"
    onclick={toggleExpanded}
    aria-expanded={expanded}
  >
    <span class="board-title">Feature requests</span>
    <svg
      class="chevron"
      class:open={expanded}
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M6 9l6 6 6-6"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
  </button>

  {#if expanded}
    <div class="board-body">
      {#if loading}
        <p class="board-note">Loading requests…</p>
      {:else if loadError}
        <p class="board-note error">{loadError}</p>
        <button class="retry-link" onclick={loadFeatures}>Retry</button>
      {:else}
        {#if features.length > 0}
          <ul class="feature-list">
            {#each features as feature (feature.id)}
              <li class="feature-row">
                <button
                  class="vote-btn"
                  class:active={feature.voted_by_me}
                  onclick={() => handleVote(feature)}
                  disabled={votingIds.includes(feature.id)}
                  aria-pressed={feature.voted_by_me}
                  aria-label={`Upvote ${feature.title}`}
                >
                  <span class="vote-arrow" aria-hidden="true">▲</span>
                  <span class="vote-count">{feature.vote_count}</span>
                </button>
                <span class="feature-title">{feature.title}</span>
                {#if feature.status !== 'open'}
                  <span class="status-pill status-{feature.status}">
                    {statusLabel(feature.status)}
                  </span>
                {/if}
              </li>
            {/each}
          </ul>
        {:else}
          <p class="board-note">No requests yet — be the first to suggest one.</p>
        {/if}

        <form class="submit-row" onsubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
          <input
            class="submit-input"
            type="text"
            bind:value={newTitle}
            placeholder="Suggest a feature…"
            maxlength={MAX_TITLE}
            disabled={submitting}
            aria-label="Suggest a feature"
          />
          <button
            class="submit-btn"
            type="submit"
            disabled={submitting || !newTitle.trim()}
          >
            {submitting ? '…' : 'Send'}
          </button>
        </form>
        {#if submitError}
          <p class="board-note error">{submitError}</p>
        {/if}
      {/if}
    </div>
  {/if}
</section>

<style>
  .feature-board {
    border-top: 1px solid #e8e0d4;
    background: var(--color-bg-primary, #fffbf5);
    font-family: 'Poppins', sans-serif;
  }

  .board-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 12px 16px;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--color-text-primary, #3A3633);
    transition: background 150ms ease;
  }

  .board-header:hover {
    background: #f5f0e8;
  }

  .board-title {
    font-size: 13px;
    font-weight: 600;
  }

  .chevron {
    color: var(--color-text-secondary, #6B6560);
    transition: transform 200ms ease;
  }

  .chevron.open {
    transform: rotate(180deg);
  }

  .board-body {
    padding: 0 16px 16px;
  }

  .feature-list {
    list-style: none;
    margin: 0 0 12px;
    padding: 0;
    max-height: 300px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .feature-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px;
    border-radius: 8px;
    background: var(--color-bg-secondary, #f5f0e8);
  }

  .vote-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1px;
    min-width: 40px;
    padding: 4px 6px;
    border: 1px solid #e0d8cc;
    border-radius: 8px;
    background: white;
    color: var(--color-text-secondary, #6B6560);
    cursor: pointer;
    transition: all 150ms ease;
    flex-shrink: 0;
  }

  .vote-btn:hover:not(:disabled) {
    border-color: var(--color-sage, #94A37C);
    color: var(--color-sage, #94A37C);
  }

  .vote-btn.active {
    background: var(--color-sage, #94A37C);
    border-color: var(--color-sage, #94A37C);
    color: white;
  }

  .vote-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .vote-arrow {
    font-size: 10px;
    line-height: 1;
  }

  .vote-count {
    font-size: 12px;
    font-weight: 600;
    line-height: 1;
  }

  .feature-title {
    flex: 1;
    font-size: 13px;
    color: var(--color-text-primary, #3A3633);
    line-height: 1.35;
  }

  .status-pill {
    flex-shrink: 0;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 600;
    text-transform: capitalize;
    background: #ece4d6;
    color: var(--color-text-secondary, #6B6560);
  }

  .status-planned {
    background: #eaf0e4;
    color: #5a6b45;
  }

  .status-in_progress {
    background: #fdf1dd;
    color: #9a6b2f;
  }

  .status-shipped {
    background: #e3f0e6;
    color: #2f6b3f;
  }

  .status-declined {
    background: #f1e8e5;
    color: #8a5a4d;
  }

  .submit-row {
    display: flex;
    gap: 8px;
  }

  .submit-input {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid #e0d8cc;
    border-radius: 8px;
    font-family: 'Poppins', sans-serif;
    font-size: 13px;
    background: white;
    color: var(--color-text-primary, #3A3633);
    outline: none;
    transition: border-color 150ms ease;
  }

  .submit-input:focus {
    border-color: var(--color-sage, #94A37C);
  }

  .submit-btn {
    flex-shrink: 0;
    padding: 8px 14px;
    background: var(--color-sage, #94A37C);
    color: white;
    border: none;
    border-radius: 8px;
    font-family: 'Poppins', sans-serif;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 150ms ease;
  }

  .submit-btn:hover:not(:disabled) {
    background: #7d8a68;
  }

  .submit-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .board-note {
    font-size: 12px;
    color: var(--color-text-secondary, #6B6560);
    margin: 0 0 8px;
  }

  .board-note.error {
    color: var(--color-rust, #C46E5A);
  }

  .retry-link {
    background: none;
    border: none;
    padding: 0;
    font-family: 'Poppins', sans-serif;
    font-size: 12px;
    font-weight: 500;
    color: var(--color-sage, #94A37C);
    cursor: pointer;
  }

  .retry-link:hover {
    text-decoration: underline;
  }
</style>
