import './app.css';
import Sidebar from './Sidebar.svelte';

const app = new Sidebar({
  target: document.getElementById('app')!
});

export default app;
