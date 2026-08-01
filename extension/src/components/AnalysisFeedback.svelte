<script lang="ts">
  /**
   * AnalysisFeedback - inline rating + bug-report widget.
   *
   * Sits at the foot of the analysis view (just above the feature board). A row
   * of three icon buttons (helpful / not helpful / report a bug) reveals an
   * inline form: thumbs show multi-select reason badges + an optional note; the
   * bug icon shows only a note that is mandatory (>= MIN_BUG_CHARS). Once a
   * url_hash has been submitted the widget remembers it for the session and
   * shows a thanks state on remount. Only rendered while signed in (the analysis
   * view is), so there is no sign-in state. Mirrors the referral split: thin
   * component over the pure logic + DI fetch wrapper in lib/feedback.ts.
   */
  import { onMount } from 'svelte';
  import { authStore } from '../lib/auth-store.svelte';
  import {
    UP_REASONS,
    DOWN_REASONS,
    MIN_BUG_CHARS,
    countValidChars,
    canSubmit,
    sendFeedback,
    FeedbackError,
    type FeedbackRating,
  } from '../lib/feedback';

  interface Props {
    urlHash: string;
  }

  let { urlHash }: Props = $props();

  let rating = $state<FeedbackRating | null>(null);
  let selectedReasons = $state<string[]>([]);
  let comment = $state('');
  let sending = $state(false);
  let sent = $state(false);
  let error = $state('');

  let storageKey = $derived(`ruh_feedback_sent_${urlHash}`);
  let reasons = $derived(
    rating === 'up' ? UP_REASONS : rating === 'down' ? DOWN_REASONS : [],
  );
  let showBadges = $derived(rating === 'up' || rating === 'down');
  let submitReady = $derived(canSubmit(rating, comment));
  let charsNeeded = $derived(
    rating === 'bug' ? Math.max(0, MIN_BUG_CHARS - countValidChars(comment)) : 0,
  );

  onMount(async () => {
    if (!urlHash) return;
    try {
      const stored = await chrome.storage.session.get(storageKey);
      if (stored?.[storageKey]) sent = true;
    } catch {
      // storage.session unavailable — default to interactive (not yet sent).
    }
  });

  function selectRating(next: FeedbackRating) {
    error = '';
    // Toggle the active icon off, otherwise switch to the new one. Either way
    // clear the other rating's badge/comment selections.
    rating = rating === next ? null : next;
    selectedReasons = [];
    comment = '';
  }

  function toggleReason(reason: string) {
    selectedReasons = selectedReasons.includes(reason)
      ? selectedReasons.filter((r) => r !== reason)
      : [...selectedReasons, reason];
  }

  async function submit() {
    if (!rating || !submitReady || sending) return;
    const token = authStore.getAccessToken();
    if (!token) {
      error = 'Please sign in to send feedback.';
      return;
    }

    sending = true;
    error = '';
    try {
      const trimmed = comment.trim();
      await sendFeedback(token, {
        url_hash: urlHash,
        rating,
        reasons: showBadges ? selectedReasons : [],
        comment: trimmed ? trimmed : null,
      });
      sent = true;
      try {
        await chrome.storage.session.set({ [storageKey]: true });
      } catch {
        // Non-fatal — the thanks state still holds for this session in memory.
      }
    } catch (err) {
      if (err instanceof FeedbackError && err.status === 429) {
        error = 'One moment — try again shortly.';
      } else if (err instanceof FeedbackError && err.status === 422) {
        error = 'That didn’t go through — check your note and retry.';
      } else {
        error = 'Could not send feedback — please try again.';
      }
    } finally {
      sending = false;
    }
  }
</script>

<div class="feedback">
  {#if sent}
    <p class="thanks">Thanks — this helps make ruh better.</p>
  {:else}
    <div class="fb-head">
      <span class="fb-prompt">How was this analysis?</span>
      <div class="fb-icons">
        <button
          type="button"
          class="fb-icon"
          class:active={rating === 'up'}
          onclick={() => selectRating('up')}
          aria-pressed={rating === 'up'}
          aria-label="Helpful"
          title="Helpful"
        >
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
        <button
          type="button"
          class="fb-icon"
          class:active={rating === 'down'}
          onclick={() => selectRating('down')}
          aria-pressed={rating === 'down'}
          aria-label="Not helpful"
          title="Not helpful"
        >
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
        <button
          type="button"
          class="fb-icon"
          class:active={rating === 'bug'}
          onclick={() => selectRating('bug')}
          aria-pressed={rating === 'bug'}
          aria-label="Report a bug"
          title="Report a bug"
        >
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <g
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="m8 2 1.88 1.88" />
              <path d="M14.12 3.88 16 2" />
              <path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1" />
              <path
                d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6"
              />
              <path d="M12 20v-9" />
              <path d="M6.53 9C4.6 8.8 3 7.1 3 5" />
              <path d="M6 13H2" />
              <path d="M3 21c0-2.1 1.7-3.9 3.8-4" />
              <path d="M20.97 5c0 2.1-1.6 3.8-3.5 4" />
              <path d="M22 13h-4" />
              <path d="M17.2 17c2.1.1 3.8 1.9 3.8 4" />
            </g>
          </svg>
        </button>
      </div>
    </div>

    {#if rating}
      <div class="fb-form">
        {#if showBadges}
          <div class="fb-badges">
            {#each reasons as reason (reason)}
              <button
                type="button"
                class="fb-badge"
                class:selected={selectedReasons.includes(reason)}
                onclick={() => toggleReason(reason)}
                aria-pressed={selectedReasons.includes(reason)}
              >
                {reason}
              </button>
            {/each}
          </div>
        {/if}

        <textarea
          class="fb-comment"
          bind:value={comment}
          rows="3"
          disabled={sending}
          placeholder={rating === 'bug'
            ? 'Describe what went wrong…'
            : 'Anything else? (optional)'}
          aria-label={rating === 'bug'
            ? 'Bug description'
            : 'Additional feedback'}
        ></textarea>

        {#if rating === 'bug' && charsNeeded > 0}
          <p class="fb-hint">
            {charsNeeded} more character{charsNeeded === 1 ? '' : 's'}
          </p>
        {/if}

        {#if error}
          <p class="fb-error">{error}</p>
        {/if}

        <button
          type="button"
          class="fb-submit"
          onclick={submit}
          disabled={!submitReady || sending}
        >
          {sending ? 'Sending…' : 'Send feedback'}
        </button>
      </div>
    {/if}
  {/if}
</div>

<style>
  .feedback {
    font-family: 'Poppins', sans-serif;
  }

  .fb-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .fb-prompt {
    font-family: 'Instrument Sans', sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: var(--color-text-primary, #3a3633);
  }

  .fb-icons {
    display: flex;
    gap: 8px;
  }

  .fb-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border: 1px solid #e0d8cc;
    border-radius: 10px;
    background: white;
    color: var(--color-text-secondary, #6b6560);
    cursor: pointer;
    transition:
      border-color 150ms ease,
      background 150ms ease,
      color 150ms ease;
  }

  .fb-icon:hover {
    border-color: var(--color-sage, #94a37c);
    color: var(--color-sage, #94a37c);
  }

  .fb-icon.active {
    background: var(--color-sage, #94a37c);
    border-color: var(--color-sage, #94a37c);
    color: white;
  }

  .fb-icon svg {
    width: 18px;
    height: 18px;
  }

  .fb-form {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 12px;
  }

  .fb-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  /* Rounded, explicitly NOT pill-shaped (radius ~8px). */
  .fb-badge {
    padding: 6px 12px;
    border: 1px solid #e0d8cc;
    border-radius: 8px;
    background: white;
    font-family: 'Poppins', sans-serif;
    font-size: 12px;
    color: var(--color-text-secondary, #6b6560);
    cursor: pointer;
    transition:
      border-color 150ms ease,
      background 150ms ease,
      color 150ms ease;
  }

  .fb-badge:hover {
    border-color: var(--color-sage, #94a37c);
  }

  .fb-badge.selected {
    background: var(--color-sage, #94a37c);
    border-color: var(--color-sage, #94a37c);
    color: white;
  }

  .fb-comment {
    width: 100%;
    box-sizing: border-box;
    padding: 10px 12px;
    border: 1px solid #e0d8cc;
    border-radius: 10px;
    font-family: 'Poppins', sans-serif;
    font-size: 13px;
    line-height: 1.5;
    color: var(--color-text-primary, #3a3633);
    background: white;
    outline: none;
    resize: vertical;
    transition: border-color 150ms ease;
  }

  .fb-comment:focus {
    border-color: var(--color-sage, #94a37c);
  }

  .fb-comment:disabled {
    opacity: 0.6;
  }

  .fb-hint {
    margin: -2px 0 0;
    font-size: 11px;
    color: var(--color-text-secondary, #6b6560);
  }

  .fb-error {
    margin: -2px 0 0;
    font-size: 12px;
    color: var(--color-rust, #c46e5a);
    overflow-wrap: anywhere;
  }

  .fb-submit {
    align-self: flex-end;
    padding: 8px 16px;
    background: var(--color-sage, #94a37c);
    color: white;
    border: none;
    border-radius: 10px;
    font-family: 'Poppins', sans-serif;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: background 150ms ease;
  }

  .fb-submit:hover:not(:disabled) {
    background: #7d8a68;
  }

  .fb-submit:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .thanks {
    margin: 0;
    font-size: 13px;
    color: #2f6b3f;
  }
</style>
