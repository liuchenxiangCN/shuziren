import { createApp } from 'vue';
import App from './App.vue';
import ControlPlaneApp from './ControlPlaneApp.vue';
import './style.css';

const rootComponent = window.location.pathname.startsWith('/manage') ? ControlPlaneApp : App;

createApp(rootComponent).mount('#app');
