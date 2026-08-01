<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { wittyMessages } from '@/lib/messages';
  import { fade, fly } from 'svelte/transition';

  interface Props {
    currentStep?: string;
  }

  let { currentStep = '' }: Props = $props();

  // One message on stage at a time, rotated from a shuffled deck so nothing
  // repeats until the whole deck has played. `tick` keys the {#key} block so
  // Svelte crossfades between consecutive messages.
  let tick = $state(0);
  let current = $state('');
  let deck: string[] = [];
  let deckIndex = 0;
  let rotations = 0;
  let rotateInterval: ReturnType<typeof setInterval> | null = null;

  const ROTATE_MS = 3000;
  const MAX_ROTATIONS = 40; // ~2 min, then settle on a static message

  function shuffled(list: string[]): string[] {
    const copy = [...list];
    for (let i = copy.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    return copy;
  }

  function nextMessage(): string {
    if (deckIndex >= deck.length) {
      deck = shuffled(wittyMessages);
      // Avoid an immediate repeat across the reshuffle boundary
      if (deck[0] === current && deck.length > 1) {
        [deck[0], deck[1]] = [deck[1], deck[0]];
      }
      deckIndex = 0;
    }
    return deck[deckIndex++];
  }

  function rotate() {
    rotations++;
    if (rotations >= MAX_ROTATIONS) {
      current = 'Still working — this product has a lot to analyze…';
      if (rotateInterval) clearInterval(rotateInterval);
      rotateInterval = null;
    } else {
      current = nextMessage();
    }
    tick++;
  }

  onMount(() => {
    deck = shuffled(wittyMessages);
    current = nextMessage();
    tick++;
    rotateInterval = setInterval(rotate, ROTATE_MS);
  });

  onDestroy(() => {
    if (rotateInterval) clearInterval(rotateInterval);
  });
</script>

<div class="loading-screen">
  <div class="loading-header">
    <div class="spinner"></div>
    <h3>Analyzing Product…</h3>
    <p class="wait-text">First look takes up to a minute or two — repeat visits are instant</p>
  </div>

  <div class="message-stage">
    {#if currentStep}
      <div class="message-item progress-message" in:fly={{ y: 12, duration: 350 }}>
        <span class="message-icon">⚙️</span>
        <span class="message-text">{currentStep}</span>
      </div>
    {:else}
      {#key tick}
        <div
          class="message-item witty-message"
          in:fly={{ y: 12, duration: 350, delay: 150 }}
          out:fade={{ duration: 150 }}
        >
          <span class="message-icon">💭</span>
          <span class="message-text">{current}</span>
        </div>
      {/key}
    {/if}
  </div>
</div>

<style>
  .loading-screen {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 48px 20px;
    height: 100vh;
    box-sizing: border-box;
    overflow: hidden;
    background: var(--color-bg-primary, #fffbf5);
  }

  .loading-header {
    text-align: center;
    margin-bottom: 32px;
  }

  .spinner {
    width: 48px;
    height: 48px;
    border: 4px solid #e8dcc8;
    border-top-color: #6b6560;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 16px;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  h3 {
    font-family: 'Cormorant Infant', serif;
    font-size: 24px;
    font-weight: 600;
    color: var(--color-text-primary, #3a3633);
    margin: 0 0 8px 0;
  }

  .wait-text {
    font-family: 'Poppins', sans-serif;
    font-size: 13px;
    color: var(--color-text-secondary, #6b6560);
    margin: 0;
  }

  /* Fixed-height single-cell stage: outgoing and incoming messages occupy the
     same grid cell during the crossfade, so the layout never jumps. */
  .message-stage {
    display: grid;
    width: 100%;
    max-width: 360px;
    min-height: 84px;
    align-items: start;
  }

  .message-stage > :global(*) {
    grid-area: 1 / 1;
  }

  .message-item {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 14px;
    line-height: 1.5;
  }

  .witty-message {
    background: #f5f1eb;
    color: #6b6560;
    font-style: italic;
  }

  .progress-message {
    background: #e0f2fe;
    color: #0369a1;
    font-weight: 500;
  }

  .message-icon {
    font-size: 18px;
    flex-shrink: 0;
    line-height: 1.5;
  }

  .message-text {
    flex: 1;
  }
</style>
