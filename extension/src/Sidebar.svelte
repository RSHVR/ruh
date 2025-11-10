<script lang="ts">
  import { onMount } from 'svelte';
  import Sidebar from './components/Sidebar.svelte';
  import { api } from './lib/api';
  import { cache } from './lib/cache';
  import type { AnalysisResponse } from './types';

  let analysis: AnalysisResponse | null = $state(null);
  let loading: boolean = $state(true); // Start with loading while waiting for content script
  let error: string | null = $state(null);
  let visible: boolean = $state(true);

  onMount(() => {
    // Listen for messages from content script via chrome.runtime
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      if (message.type === 'ANALYZE_PRODUCT') {
        handleAnalyze(message.url);
      } else if (message.type === 'CLOSE_SIDEBAR') {
        handleClose();
      }
    });

    // Listen for postMessage from content script (for pre-loaded data)
    window.addEventListener('message', (event) => {
      if (event.data?.type === 'ANALYSIS_DATA') {
        // Content script already has the analysis data, use it directly
        analysis = event.data.data;
        loading = false;
        error = null;
      } else if (event.data?.type === 'ANALYZE_PRODUCT') {
        // Content script wants us to start analysis
        handleAnalyze(event.data.url);
      }
    });

    // Do NOT automatically analyze on mount - wait for content script to send data
    // Content script will either send ANALYSIS_DATA (if ready) or ANALYZE_PRODUCT (if not)
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
