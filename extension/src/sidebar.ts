import './app.css';
import { mount } from 'svelte';
import Sidebar from './Sidebar.svelte';

// Wait for DOM to be ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}

function initApp() {
  const target = document.getElementById('app');
  if (!target) {
    console.error('[Eject] App target not found');
    return;
  }

  // Use Svelte 5 mount API
  mount(Sidebar, { target });
}
