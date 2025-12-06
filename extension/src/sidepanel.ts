import './app.css';
import SidePanelContainer from './SidePanelContainer.svelte';
import { mount } from 'svelte';

const app = mount(SidePanelContainer, {
  target: document.getElementById('app')!
});

export default app;
