<script lang="ts">
  import { authStore } from '../lib/auth-store.svelte';

  const tierLabels: Record<string, string> = {
    free: 'Free',
    basic: 'Basic',
    middle: 'Middle',
    unlimited: 'Unlimited',
  };

  let tierLabel = $derived(tierLabels[authStore.userTier] || 'Free');
  let isUnlimited = $derived(authStore.userTier === 'unlimited');
  let isLow = $derived(!isUnlimited && (authStore.creditBalance ?? 0) <= 1);
</script>

<div class="credit-badge" class:low={isLow}>
  <span class="tier">{tierLabel}</span>
  <span class="separator">|</span>
  {#if isUnlimited}
    <span class="credits">Unlimited</span>
  {:else}
    <span class="credits">{authStore.creditBalance ?? 0} credits</span>
  {/if}
</div>

<style>
  .credit-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: var(--color-bg-secondary, #f5f0e8);
    border-radius: 20px;
    font-family: 'Poppins', sans-serif;
    font-size: 12px;
    color: var(--color-text-secondary, #6B6560);
  }

  .credit-badge.low {
    background: #fef2f2;
    color: #c53030;
  }

  .tier {
    font-weight: 600;
    color: var(--color-text-primary, #3A3633);
  }

  .credit-badge.low .tier {
    color: #c53030;
  }

  .separator {
    opacity: 0.3;
  }

  .credits {
    font-weight: 500;
  }
</style>
