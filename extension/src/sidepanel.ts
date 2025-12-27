import './app.css';
import SidePanelContainer from './SidePanelContainer.svelte';
import { mount } from 'svelte';

// Read tabId from URL query params (set by background when opening)
// This allows getContexts() to identify which tab this side panel belongs to
const params = new URLSearchParams(window.location.search);
const tabIdFromUrl = params.get('tabId');
const initialTabId = tabIdFromUrl ? parseInt(tabIdFromUrl, 10) : null;

console.log('[Ruh SidePanel] Initialized with tabId:', initialTabId);

const app = mount(SidePanelContainer, {
  target: document.getElementById('app')!,
  props: {
    initialTabId
  }
});

export default app;
