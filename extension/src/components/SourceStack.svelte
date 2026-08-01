<script lang="ts">
  import { faviconUrl, type SourceRef } from '../lib/sources';

  interface Props {
    sources: SourceRef[];
    onOpen: () => void;
  }

  let { sources, onOpen }: Props = $props();

  const MAX_SHOWN = 4;
  const shown = $derived(sources.slice(0, MAX_SHOWN));
  const extra = $derived(sources.length - MAX_SHOWN);
</script>

{#if sources.length > 0}
  <button
    type="button"
    class="source-stack"
    onclick={onOpen}
    aria-label="View {sources.length} source{sources.length === 1 ? '' : 's'}"
  >
    <span class="favicons">
      {#each shown as source, i (source.url)}
        <img
          class="stack-favicon"
          style="z-index: {shown.length - i};"
          src={faviconUrl(source.domain)}
          alt=""
          loading="lazy"
        />
      {/each}
      {#if extra > 0}
        <span class="stack-more">+{extra}</span>
      {/if}
    </span>
    <span class="stack-label">
      {sources.length === 1 ? 'Source' : `${sources.length} sources`}
    </span>
  </button>
{/if}

<style>
  .source-stack {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-top: 10px;
    padding: 4px 10px 4px 4px;
    background: rgba(255, 251, 245, 0.9);
    border: 1px solid rgba(168, 184, 159, 0.35);
    border-radius: 9999px;
    cursor: pointer;
    transition: border-color 150ms ease;
  }

  .source-stack:hover {
    border-color: var(--color-sage, #94a37c);
  }

  .favicons {
    display: inline-flex;
    align-items: center;
  }

  .stack-favicon {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #fff;
    border: 2px solid #fffbf5;
    position: relative;
  }

  .stack-favicon:not(:first-child),
  .stack-more:not(:first-child) {
    margin-left: -8px;
  }

  .stack-more {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #e8dcc8;
    border: 2px solid #fffbf5;
    font-family: 'Poppins', sans-serif;
    font-size: 9px;
    font-weight: 600;
    color: #3a3633;
    position: relative;
    z-index: 0;
  }

  .stack-label {
    font-family: 'Poppins', sans-serif;
    font-size: 11px;
    font-weight: 500;
    color: var(--color-text-secondary, #6b6560);
  }
</style>
