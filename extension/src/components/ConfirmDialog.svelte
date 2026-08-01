<script lang="ts">
  import { fade, scale } from 'svelte/transition';

  interface Props {
    title: string;
    body?: string;
    confirmLabel?: string;
    cancelLabel?: string;
    onConfirm: () => void;
    onCancel: () => void;
  }

  let {
    title,
    body = '',
    confirmLabel = 'Confirm',
    cancelLabel = 'Cancel',
    onConfirm,
    onCancel,
  }: Props = $props();

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') onCancel();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div
  class="confirm-backdrop"
  role="presentation"
  onclick={(e) => {
    if (e.target === e.currentTarget) onCancel();
  }}
  transition:fade={{ duration: 120 }}
>
  <div
    class="confirm-dialog"
    role="alertdialog"
    aria-modal="true"
    aria-label={title}
    tabindex="-1"
    transition:scale={{ start: 0.95, duration: 150 }}
  >
    <h4>{title}</h4>
    {#if body}
      <p class="confirm-body">{body}</p>
    {/if}
    <div class="confirm-actions">
      <button type="button" class="cancel-btn" onclick={onCancel}>
        {cancelLabel}
      </button>
      <button type="button" class="confirm-btn" onclick={onConfirm}>
        {confirmLabel}
      </button>
    </div>
  </div>
</div>

<style>
  .confirm-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(58, 54, 51, 0.45);
    backdrop-filter: blur(2px);
    z-index: 120;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }

  .confirm-dialog {
    width: 100%;
    max-width: 280px;
    background: var(--color-bg-primary, #fffbf5);
    border-radius: 14px;
    padding: 18px;
    box-sizing: border-box;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.18);
  }

  h4 {
    font-family: 'Instrument Sans', sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: var(--color-text-primary, #3a3633);
    margin: 0 0 6px;
  }

  .confirm-body {
    font-family: 'Poppins', sans-serif;
    font-size: 13px;
    line-height: 1.5;
    color: var(--color-text-secondary, #6b6560);
    margin: 0 0 16px;
  }

  .confirm-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }

  .cancel-btn {
    padding: 8px 14px;
    border-radius: 8px;
    border: 1px solid #e0d8cc;
    background: white;
    font-family: 'Poppins', sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: var(--color-text-primary, #3a3633);
    cursor: pointer;
  }

  .confirm-btn {
    padding: 8px 14px;
    border-radius: 8px;
    border: none;
    background: var(--color-sage, #94a37c);
    font-family: 'Poppins', sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: white;
    cursor: pointer;
  }

  .confirm-btn:hover {
    background: #7d8a68;
  }
</style>
