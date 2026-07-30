import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

// Static SPA: no SSR, single index.html fallback so the client router handles all routes.
// Auth uses allauth's browser session and CSRF cookies; no SSR is required.
/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		adapter: adapter({ fallback: 'index.html' })
	}
};

export default config;
