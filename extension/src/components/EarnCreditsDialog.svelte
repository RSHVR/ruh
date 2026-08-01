<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  import ReferralPanel from './ReferralPanel.svelte';

  interface Props {
    onClose: () => void;
  }

  let { onClose }: Props = $props();

  const SUPPORT_EMAIL = 'ruh-support@rshvr.com';

  // Which face of the dialog is showing: the static offer list, or the
  // interactive referral flow (reached by tapping the "Refer a friend" row).
  let view = $state<'offers' | 'referrals'>('offers');

  interface Offer {
    credits: number;
    title: string;
    detail: string;
    /** Present on mailto offers; absent on interactive/external offers. */
    mailtoSubject?: string;
    /** When true, the row opens the in-dialog flow instead of an email. */
    interactive?: boolean;
    /** When set, the row is an external link opened in a new tab. */
    external?: string;
  }

  const FOUNDER_BOOKING_URL =
    'https://calendar.notion.so/meet/arshveergahir/ruh-founder-chat';

  const offers: Offer[] = [
    {
      credits: 5,
      title: 'Tell us what you think',
      detail:
        'Write at least 100 words on what you like and don’t like about ruh, and email it to us.',
      mailtoSubject: 'Earning credits: my feedback (+5)',
    },
    {
      credits: 10,
      title: 'Share ruh publicly',
      detail:
        'Post about ruh anywhere public — social, blog, video — and email us the link or a screenshot.',
      mailtoSubject: 'Earning credits: I shared ruh (+10)',
    },
    {
      credits: 10,
      title: 'Refer a friend',
      detail:
        '+10 for each friend who signs up and analyzes a product — up to 5 friends. Invite them right here.',
      interactive: true,
    },
    {
      credits: 30,
      title: 'Meet the founder',
      detail:
        'Book 15 minutes on what ruh should become. Credits granted after the meeting.',
      external: FOUNDER_BOOKING_URL,
    },
  ];

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      // Escape backs out of the referral flow first, then closes the dialog.
      if (view === 'referrals') view = 'offers';
      else onClose();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div
  class="earn-backdrop"
  role="presentation"
  onclick={(e) => {
    if (e.target === e.currentTarget) onClose();
  }}
  transition:fade={{ duration: 150 }}
>
  <div
    class="earn-dialog"
    role="dialog"
    aria-modal="true"
    aria-label={view === 'referrals' ? 'Refer a friend' : 'Earn free credits'}
    tabindex="-1"
    transition:fly={{ y: 30, duration: 220 }}
  >
    <div class="earn-header">
      <h4>{view === 'referrals' ? 'Refer a friend' : 'Earn free credits'}</h4>
      <button type="button" class="close-btn" onclick={onClose} aria-label="Close">
        ✕
      </button>
    </div>

    {#if view === 'referrals'}
      <ReferralPanel onBack={() => (view = 'offers')} />
    {:else}
      <p class="earn-sub">Help make ruh better — get detail unlocks in return.</p>

      {#snippet offerBody(offer: Offer)}
        <span class="offer-credits">+{offer.credits}</span>
        <span class="offer-text">
          <span class="offer-title">{offer.title}</span>
          <span class="offer-detail">{offer.detail}</span>
        </span>
      {/snippet}

      <div class="offer-list">
        {#each offers as offer (offer.title)}
          {#if offer.interactive}
            <button
              type="button"
              class="offer-row"
              onclick={() => (view = 'referrals')}
            >
              {@render offerBody(offer)}
            </button>
          {:else if offer.external}
            <a
              class="offer-row"
              href={offer.external}
              target="_blank"
              rel="noopener noreferrer"
            >
              {@render offerBody(offer)}
            </a>
          {:else}
            <a
              class="offer-row"
              href="mailto:{SUPPORT_EMAIL}?subject={encodeURIComponent(
                offer.mailtoSubject ?? '',
              )}"
            >
              {@render offerBody(offer)}
            </a>
          {/if}
        {/each}
      </div>

      <p class="earn-footnote">
        Most options email us at {SUPPORT_EMAIL} — credits are added by a human,
        usually within a day.
      </p>
    {/if}
  </div>
</div>

<style>
  .earn-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(58, 54, 51, 0.5);
    backdrop-filter: blur(3px);
    z-index: 110;
    display: flex;
    align-items: flex-end;
  }

  .earn-dialog {
    width: 100%;
    max-height: 80vh;
    overflow-y: auto;
    background: var(--color-bg-primary, #fffbf5);
    border-radius: 16px 16px 0 0;
    padding: 18px 18px 22px;
    box-sizing: border-box;
  }

  .earn-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  h4 {
    font-family: 'Instrument Sans', sans-serif;
    font-size: 17px;
    font-weight: 700;
    color: var(--color-text-primary, #3a3633);
    margin: 0;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 14px;
    color: var(--color-text-secondary, #6b6560);
    cursor: pointer;
    padding: 2px 6px;
    flex-shrink: 0;
  }

  .earn-sub {
    font-family: 'Poppins', sans-serif;
    font-size: 12px;
    color: var(--color-text-secondary, #6b6560);
    margin: 4px 0 14px;
  }

  .offer-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .offer-row {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--color-bg-secondary, #f5f0e8);
    border: 1px solid rgba(168, 184, 159, 0.25);
    text-decoration: none;
    cursor: pointer;
    transition:
      border-color 150ms ease,
      transform 150ms ease;
  }

  /* The interactive referral row is a <button>; strip native chrome so it
     matches the <a> rows and stretches full width in the flex column. */
  button.offer-row {
    width: 100%;
    text-align: left;
    font: inherit;
    color: inherit;
  }

  .offer-row:hover {
    border-color: var(--color-sage, #94a37c);
    transform: translateY(-1px);
  }

  .offer-credits {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 44px;
    padding: 6px 8px;
    border-radius: 10px;
    background: var(--color-sage, #94a37c);
    color: white;
    font-family: 'Instrument Sans', sans-serif;
    font-size: 15px;
    font-weight: 700;
    flex-shrink: 0;
  }

  .offer-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .offer-title {
    font-family: 'Instrument Sans', sans-serif;
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text-primary, #3a3633);
  }

  .offer-detail {
    font-family: 'Poppins', sans-serif;
    font-size: 12px;
    line-height: 1.5;
    color: var(--color-text-secondary, #6b6560);
  }

  .earn-footnote {
    font-family: 'Poppins', sans-serif;
    font-size: 11px;
    color: var(--color-text-secondary, #6b6560);
    margin: 14px 0 0;
    overflow-wrap: anywhere;
  }
</style>
