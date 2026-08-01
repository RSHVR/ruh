<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  import { faviconUrl, type SourceRef } from '../lib/sources';

  interface Props {
    title: string;
    reason: string;
    sources: SourceRef[];
    onClose: () => void;
  }

  let { title, reason, sources, onClose }: Props = $props();

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
    aria-label="Sources for {title}"
    tabindex="-1"
    transition:fly={{ y: 40, duration: 250 }}
  >
    <div class="sheet-header">
      <h4>{title}</h4>
      <button type="button" class="close-btn" onclick={onClose} aria-label="Close">
        ✕
      </button>
    </div>

    {#if reason}
      <p class="sheet-reason">{reason}</p>
    {/if}

    <p class="sheet-hint">Where this finding comes from:</p>

    <div class="source-list">
      {#each sources as source (source.url)}
        <a
          class="source-row"
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          <img src={faviconUrl(source.domain)} alt="" class="row-favicon" />
          <span class="row-text">
            <span class="row-domain">{source.domain}</span>
            {#if source.note}
              <span class="row-note">{source.note}</span>
            {/if}
            <span class="row-url">{source.url}</span>
          </span>
          <span class="row-open">↗</span>
        </a>
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
    z-index: 100;
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
    font-family: 'Poppins', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: var(--color-text-primary, #3a3633);
    margin: 0;
    overflow-wrap: anywhere;
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

  .sheet-reason {
    font-family: 'Poppins', sans-serif;
    font-size: 13px;
    line-height: 1.5;
    color: var(--color-text-secondary, #6b6560);
    margin: 0 0 14px;
  }

  .sheet-hint {
    font-family: 'Poppins', sans-serif;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-secondary, #6b6560);
    margin: 0 0 8px;
  }

  .source-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .source-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--color-bg-secondary, #f5f0e8);
    border: 1px solid rgba(168, 184, 159, 0.2);
    text-decoration: none;
    transition: border-color 150ms ease;
  }

  .source-row:hover {
    border-color: var(--color-sage, #94a37c);
  }

  .row-favicon {
    width: 22px;
    height: 22px;
    border-radius: 6px;
    background: #fff;
    flex-shrink: 0;
  }

  .row-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
    flex: 1;
  }

  .row-domain {
    font-family: 'Poppins', sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--color-text-primary, #3a3633);
  }

  .row-note {
    font-family: 'Poppins', sans-serif;
    font-size: 12px;
    line-height: 1.45;
    color: var(--color-text-primary, #3a3633);
    margin: 2px 0;
    overflow-wrap: anywhere;
  }

  .row-url {
    font-family: 'Poppins', sans-serif;
    font-size: 11px;
    color: var(--color-text-secondary, #6b6560);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .row-open {
    color: var(--color-sage, #94a37c);
    font-size: 14px;
    flex-shrink: 0;
  }
</style>
