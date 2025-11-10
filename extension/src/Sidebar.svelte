<script lang="ts">
  import { onMount } from 'svelte';
  import Sidebar from './components/Sidebar.svelte';
  import { api } from './lib/api';
  import { cache } from './lib/cache';
  import type { AnalysisResponse } from './types';

  let analysis: AnalysisResponse | null = $state(null);
  let loading: boolean = $state(false);
  let error: string | null = $state(null);
  let visible: boolean = $state(true);

  onMount(() => {
    // Listen for messages from content script
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      if (message.type === 'ANALYZE_PRODUCT') {
        handleAnalyze(message.url);
      } else if (message.type === 'CLOSE_SIDEBAR') {
        handleClose();
      }
    });

    // Check if there's a product to analyze on mount
    const params = new URLSearchParams(window.location.search);
    const url = params.get('url');
    if (url) {
      handleAnalyze(url);
    }
  });

  async function handleAnalyze(productUrl: string) {
    loading = true;
    error = null;
    analysis = null;

    try {
      // Check cache first
      const cached = await cache.get(productUrl);
      if (cached) {
        analysis = cached;
        loading = false;
        return;
      }

      // Fetch from API
      const result = await api.analyzeProduct(productUrl);
      analysis = result;

      // Cache the result
      await cache.set(productUrl, result);
    } catch (err) {
      error = err instanceof Error ? err.message : 'An unknown error occurred';
      console.error('Analysis error:', err);
    } finally {
      loading = false;
    }
  }

  function handleClose() {
    visible = false;
    // Send message to content script to remove sidebar
    window.parent.postMessage({ type: 'EJECT_CLOSE_SIDEBAR' }, '*');
  }
</script>

{#if visible}
  <Sidebar {analysis} {loading} {error} onClose={handleClose} />
{/if}
