<script lang="ts">
  /**
   * ReferralPanel - the interactive "Refer a friend" flow.
   *
   * Rendered inside EarnCreditsDialog when the user taps the referral offer
   * row; it replaces the offer list and offers a "← Back" affordance to return.
   * Mirrors FeatureBoard's shape: a thin component over the pure logic +
   * dependency-injected fetch wrappers in lib/referrals.ts. Only reachable while
   * signed in (the dialog itself is), so there is no "Sign in…" state.
   */
  import { onMount } from 'svelte';
  import { authStore } from '../lib/auth-store.svelte';
  import {
    getReferrals,
    sendReferrals,
    partitionEmails,
    summarizeSend,
    ReferralError,
    MAX_EMAILS_PER_SEND,
    type Referral,
    type ReferralSummary,
  } from '../lib/referrals';

  interface Props {
    onBack: () => void;
  }

  let { onBack }: Props = $props();

  let loading = $state(true);
  let loadError = $state('');
  let referrals = $state<Referral[]>([]);
  let summary = $state<ReferralSummary | null>(null);

  let input = $state('');
  let sending = $state(false);
  let sendError = $state('');
  let feedback = $state('');
  let invalidEmails = $state<string[]>([]);

  const statusMeta: Record<string, { label: string; cls: string }> = {
    invited: { label: 'Invited', cls: 'invited' },
    signed_up: { label: 'Joined', cls: 'joined' },
    credited: { label: 'Credited +10', cls: 'credited' },
  };

  function metaFor(status: string): { label: string; cls: string } {
    return statusMeta[status] ?? { label: status, cls: 'invited' };
  }

  let creditsEarned = $derived(
    summary ? Math.min(summary.credited, summary.credited_cap) : 0,
  );

  onMount(loadReferrals);

  async function loadReferrals() {
    const token = authStore.getAccessToken();
    if (!token) {
      loadError = 'Could not load your referrals — try again.';
      loading = false;
      return;
    }
    loading = true;
    loadError = '';
    try {
      const data = await getReferrals(token);
      referrals = data.referrals;
      summary = data.summary;
    } catch {
      loadError = 'Could not load your referrals — try again.';
    } finally {
      loading = false;
    }
  }

  // Quiet refresh after a send: keep the list/feedback visible (no full-panel
  // loading flip), just swap in the latest server state.
  async function refreshList() {
    const token = authStore.getAccessToken();
    if (!token) return;
    try {
      const data = await getReferrals(token);
      referrals = data.referrals;
      summary = data.summary;
    } catch {
      // Non-fatal — the send already succeeded; keep the current list.
    }
  }

  async function handleSend() {
    if (sending) return;
    sendError = '';
    feedback = '';

    const { valid, invalid } = partitionEmails(input);
    invalidEmails = invalid;

    if (valid.length === 0) {
      if (invalid.length > 0) {
        sendError = "Those don't look like valid emails.";
      }
      return;
    }

    // Backend accepts at most 20 per call; send the first batch and keep the
    // rest in the box so nothing is silently dropped.
    const batch = valid.slice(0, MAX_EMAILS_PER_SEND);
    const overflow = valid.length - batch.length;

    const token = authStore.getAccessToken();
    if (!token) {
      sendError = 'Could not send invites — please try again.';
      return;
    }

    sending = true;
    try {
      const res = await sendReferrals(token, batch);
      feedback = summarizeSend(res.added, res.skipped);
      summary = res.summary;
      input = overflow > 0 ? valid.slice(MAX_EMAILS_PER_SEND).join(', ') : '';
      invalidEmails = [];
      if (overflow > 0) {
        feedback += ` — sent the first ${MAX_EMAILS_PER_SEND}, add the rest below.`;
      }
      await refreshList();
    } catch (err) {
      if (err instanceof ReferralError && err.status === 429) {
        sendError = 'Slow down a moment — try again shortly.';
      } else if (err instanceof ReferralError && err.status === 422) {
        sendError = 'Some emails were rejected — double-check and try again.';
      } else {
        sendError = 'Could not send invites — please try again.';
      }
    } finally {
      sending = false;
    }
  }
</script>

<div class="referral-panel">
  <button type="button" class="back-btn" onclick={onBack}>
    <span aria-hidden="true">←</span> Back
  </button>

  <p class="ref-explainer">
    +10 credits for each friend who signs up and analyzes their first product.
    Up to 5 friends counted.
  </p>

  <form
    class="ref-form"
    onsubmit={(e) => {
      e.preventDefault();
      handleSend();
    }}
  >
    <textarea
      class="ref-input"
      bind:value={input}
      placeholder="friend@email.com, another@email.com…"
      rows="3"
      disabled={sending}
      aria-label="Friends' email addresses"
    ></textarea>
    <button
      type="submit"
      class="ref-send-btn"
      disabled={sending || input.trim().length === 0}
    >
      {sending ? 'Adding…' : 'Add friends'}
    </button>
  </form>

  {#if feedback}
    <p class="ref-note success">{feedback}</p>
  {/if}
  {#if sendError}
    <p class="ref-note error">{sendError}</p>
  {/if}
  {#if invalidEmails.length > 0}
    <p class="ref-note gentle">
      Skipped {invalidEmails.length === 1 ? 'this one' : 'these'}: {invalidEmails.join(
        ', ',
      )}
    </p>
  {/if}

  {#if loading}
    <p class="ref-note">Loading your referrals…</p>
  {:else if loadError}
    <p class="ref-note error">{loadError}</p>
    <button type="button" class="retry-link" onclick={loadReferrals}>Retry</button>
  {:else}
    {#if summary}
      <p class="ref-summary">
        <strong>{creditsEarned}</strong> of {summary.credited_cap} referral credits
        earned
      </p>
    {/if}

    {#if referrals.length > 0}
      <ul class="ref-list">
        {#each referrals as ref (ref.invited_email)}
          {@const meta = metaFor(ref.status)}
          <li class="ref-row">
            <span class="ref-email">{ref.invited_email}</span>
            <span class="ref-pill {meta.cls}">{meta.label}</span>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="ref-note">
        No invites yet — add a friend's email above to get started.
      </p>
    {/if}
  {/if}
</div>

<style>
  .referral-panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
    font-family: 'Poppins', sans-serif;
  }

  .back-btn {
    align-self: flex-start;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 0;
    background: none;
    border: none;
    font-family: 'Poppins', sans-serif;
    font-size: 12px;
    font-weight: 500;
    color: var(--color-sage, #94a37c);
    cursor: pointer;
  }

  .back-btn:hover {
    text-decoration: underline;
  }

  .ref-explainer {
    margin: 0;
    font-size: 12px;
    line-height: 1.5;
    color: var(--color-text-secondary, #6b6560);
  }

  .ref-form {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .ref-input {
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

  .ref-input:focus {
    border-color: var(--color-sage, #94a37c);
  }

  .ref-input:disabled {
    opacity: 0.6;
  }

  .ref-send-btn {
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

  .ref-send-btn:hover:not(:disabled) {
    background: #7d8a68;
  }

  .ref-send-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .ref-note {
    margin: 0;
    font-size: 12px;
    line-height: 1.45;
    color: var(--color-text-secondary, #6b6560);
    overflow-wrap: anywhere;
  }

  .ref-note.success {
    color: #2f6b3f;
  }

  .ref-note.error {
    color: var(--color-rust, #c46e5a);
  }

  .ref-note.gentle {
    color: #9a6b2f;
  }

  .retry-link {
    align-self: flex-start;
    background: none;
    border: none;
    padding: 0;
    font-family: 'Poppins', sans-serif;
    font-size: 12px;
    font-weight: 500;
    color: var(--color-sage, #94a37c);
    cursor: pointer;
  }

  .retry-link:hover {
    text-decoration: underline;
  }

  .ref-summary {
    margin: 2px 0 0;
    font-size: 12px;
    color: var(--color-text-primary, #3a3633);
  }

  .ref-summary strong {
    font-family: 'Instrument Sans', sans-serif;
    font-weight: 700;
    color: var(--color-sage, #94a37c);
  }

  .ref-list {
    list-style: none;
    margin: 0;
    padding: 0;
    max-height: 260px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .ref-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--color-bg-secondary, #f5f0e8);
    border: 1px solid rgba(168, 184, 159, 0.25);
  }

  .ref-email {
    flex: 1;
    min-width: 0;
    font-size: 13px;
    color: var(--color-text-primary, #3a3633);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .ref-pill {
    flex-shrink: 0;
    padding: 2px 10px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 600;
    /* neutral / invited */
    background: #ece4d6;
    color: var(--color-text-secondary, #6b6560);
  }

  .ref-pill.joined {
    background: #fdf1dd;
    color: #9a6b2f;
  }

  .ref-pill.credited {
    background: #e3f0e6;
    color: #2f6b3f;
  }
</style>
