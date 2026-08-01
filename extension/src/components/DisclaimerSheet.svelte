<script lang="ts">
  /**
   * DisclaimerSheet - bottom sheet showing the canonical product disclaimer.
   *
   * Reuses SourcesSheet's visual pattern (blurred backdrop + rounded sheet that
   * flies up). Opened from the score cards' (i) info button. Text comes from the
   * shared lib/disclaimer constant so it matches the signup expander verbatim.
   */
  import { fade, fly } from 'svelte/transition';
  import { DISCLAIMER_PARAGRAPHS } from '../lib/disclaimer';

  interface Props {
    title: string;
    onClose: () => void;
  }

  let { title, onClose }: Props = $props();

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') onClose();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div
  class="sheet-backdrop"
  role="presentation"
  onclick={(e) => {
    if (e.target === e.currentTarget) onClose();
  }}
  transition:fade={{ duration: 150 }}
>
  <div
    class="sheet"
    role="dialog"
    aria-modal="true"
    aria-label={title}
    tabindex="-1"
    transition:fly={{ y: 40, duration: 250 }}
  >
    <div class="sheet-header">
      <h4>{title}</h4>
      <button type="button" class="close-btn" onclick={onClose} aria-label="Close">
        ✕
      </button>
    </div>

    <div class="disclaimer-body">
      {#each DISCLAIMER_PARAGRAPHS as para (para)}
        <p class="disclaimer-para">{para}</p>
      {/each}
    </div>
  </div>
</div>

<style>
  .sheet-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(58, 54, 51, 0.5);
    backdrop-filter: blur(3px);
    z-index: 120;
    display: flex;
    align-items: flex-end;
  }

  .sheet {
    width: 100%;
    max-height: 75vh;
    overflow-y: auto;
    background: var(--color-bg-primary, #fffbf5);
    border-radius: 16px 16px 0 0;
    padding: 18px 18px 24px;
    box-sizing: border-box;
  }

  .sheet-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
  }

  h4 {
    font-family: 'Instrument Sans', sans-serif;
    font-size: 16px;
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

  .disclaimer-body {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .disclaimer-para {
    font-family: 'Poppins', sans-serif;
    font-size: 13px;
    line-height: 1.55;
    color: var(--color-text-secondary, #6b6560);
    margin: 0;
    overflow-wrap: anywhere;
  }
</style>
