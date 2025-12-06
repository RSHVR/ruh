import './app.css';
import SidePanel from './SidePanel.svelte';
import { mount } from 'svelte';

const app = mount(SidePanel, {
  target: document.getElementById('app')!
});

export default app;
