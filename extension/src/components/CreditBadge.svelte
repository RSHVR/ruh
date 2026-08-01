<script lang="ts">
  import { authStore } from '../lib/auth-store.svelte';
  import EarnCreditsDialog from './EarnCreditsDialog.svelte';

  const tierLabels: Record<string, string> = {
    free: 'Free',
    basic: 'Basic',
    middle: 'Middle',
    unlimited: 'Unlimited',
  };

  let tierLabel = $derived(tierLabels[authStore.userTier] || 'Free');
  let isUnlimited = $derived(authStore.userTier === 'unlimited');
  let balance = $derived(authStore.creditBalance);
  let isLow = $derived(!isUnlimited && (balance ?? 0) <= 1);

  // The earn-credits "+" appears once credits run low and bounces (5 slow
  // bounces, once per threshold) when the balance lands on 10, 5, or 1.
  const BOUNCE_THRESHOLDS = [10, 5, 1];
  let showPlus = $derived(!isUnlimited && balance !== null && balance <= 10);
  let bouncing = $state(false);
  let showEarn = $state(false);
  let bounceTimer: ReturnType<typeof setTimeout> | undefined;

  $effect(() => {
    const b = balance;
    if (isUnlimited || b === null || !BOUNCE_THRESHOLDS.includes(b)) return;

    const key = `ruh_plus_bounced_${b}`;
    void (async () => {
      try {
        const stored = await chrome.storage.session.get(key);
        if (stored?.[key]) return;
        await chrome.storage.session.set({ [key]: true });
      } catch {
        // storage.session unavailable — still bounce, just maybe repeat later
      }
      bouncing = true;
      clearTimeout(bounceTimer);
      // 5 bounces × 0.9s — remove the class after the run so it can retrigger
      bounceTimer = setTimeout(() => (bouncing = false), 4600);
    })();
  });
</script>

<div class="credit-badge" class:low={isLow}>
  <span class="tier">{tierLabel}</span>
  <span class="separator">|</span>
  {#if isUnlimited}
    <span class="credits">Unlimited</span>
  {:else}
    <span class="credits">{balance ?? 0} credits</span>
  {/if}
  {#if showPlus}
    <button
      type="button"
      class="plus-btn"
      class:bouncing
      onclick={() => (showEarn = true)}
      aria-label="Earn free credits"
      title="Earn free credits"
    >
      +
    </button>
  {/if}
</div>

{#if showEarn}
  <EarnCreditsDialog onClose={() => (showEarn = false)} />
{/if}

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

  .plus-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    border: none;
    background: var(--color-sage, #94a37c);
    color: white;
    font-family: 'Instrument Sans', sans-serif;
    font-size: 13px;
    font-weight: 700;
    line-height: 1;
    cursor: pointer;
    padding: 0;
  }

  .plus-btn:hover {
    background: #7d8a68;
  }

  .plus-btn.bouncing {
    animation: plus-bounce 0.9s ease-in-out 5;
  }

  @keyframes plus-bounce {
    0%,
    100% {
      transform: translateY(0);
    }
    35% {
      transform: translateY(-5px);
    }
    65% {
      transform: translateY(1px);
    }
  }
</style>
