<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { wittyMessages, progressMessages } from '@/lib/messages';
  import { fade, fly } from 'svelte/transition';

  interface Message {
    id: number;
    text: string;
    type: 'witty' | 'progress';
  }

  interface Props {
    currentStep?: string;
  }

  let { currentStep = '' }: Props = $props();

  let messages: Message[] = $state([]);
  let messageId = 0;
  let messageInterval: number | null = null;
  let messageCount = 0;
  const MAX_MESSAGES = 20; // Cap at 20 messages (60 seconds)

  onMount(() => {
    // Start with a witty message
    addMessage(getRandomWittyMessage(), 'witty');

    // Add new witty message every 3 seconds
    messageInterval = window.setInterval(() => {
      if (messageCount < MAX_MESSAGES) {
        addMessage(getRandomWittyMessage(), 'witty');
        messageCount++;
      } else if (messageCount === MAX_MESSAGES) {
        // After 60 seconds, show static message
        addMessage("Still working... this product has a lot to analyze!", 'witty');
        messageCount++;
      }
    }, 3000);
  });

  onDestroy(() => {
    if (messageInterval !== null) {
      clearInterval(messageInterval);
    }
  });

  // Watch for progress updates from backend
  $effect(() => {
    if (currentStep) {
      addMessage(currentStep, 'progress');
    }
  });

  function addMessage(text: string, type: 'witty' | 'progress') {
    messages = [...messages, { id: messageId++, text, type }];

    // Keep only last 5 messages visible
    if (messages.length > 5) {
      messages = messages.slice(-5);
    }
  }

  function getRandomWittyMessage(): string {
    return wittyMessages[Math.floor(Math.random() * wittyMessages.length)];
  }
</script>

<div class="loading-screen">
  <div class="loading-header">
    <div class="spinner"></div>
    <h3>Analyzing Product...</h3>
    <p class="wait-text">This typically takes 10-30 seconds</p>
  </div>

  <div class="message-scroller">
    {#each messages as message (message.id)}
      <div
        class="message-item {message.type === 'progress' ? 'progress-message' : 'witty-message'}"
        in:fly={{ y: 20, duration: 300 }}
        out:fade={{ duration: 200 }}
      >
        {#if message.type === 'progress'}
          <span class="message-icon">⚙️</span>
        {:else}
          <span class="message-icon">💭</span>
        {/if}
        <span class="message-text">{message.text}</span>
      </div>
    {/each}
  </div>
</div>

<style>
  .loading-screen {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 48px 20px;
    height: 100%;
    background: var(--color-bg-primary, #FFFCF8);
  }

  .loading-header {
    text-align: center;
    margin-bottom: 32px;
  }

  .spinner {
    width: 48px;
    height: 48px;
    border: 4px solid #E8DCC8;
    border-top-color: #6B6560;
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
    color: var(--color-text-primary, #3A3633);
    margin: 0 0 8px 0;
  }

  .wait-text {
    font-family: 'Poppins', sans-serif;
    font-size: 14px;
    color: var(--color-text-secondary, #6B6560);
    margin: 0;
  }

  .message-scroller {
    flex: 1;
    width: 100%;
    max-width: 360px;
    overflow: hidden;
    display: flex;
    flex-direction: column-reverse;
    gap: 8px;
    padding: 0 8px;
  }

  .message-item {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 14px;
    line-height: 1.5;
    animation: slideUp 300ms ease-out;
  }

  @keyframes slideUp {
    from {
      transform: translateY(20px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }

  .witty-message {
    background: #F5F1EB;
    color: #6B6560;
    font-style: italic;
  }

  .progress-message {
    background: #E0F2FE;
    color: #0369A1;
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
