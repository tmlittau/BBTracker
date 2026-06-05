import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';

// Server-side SvelteKit talks to Django directly; the browser uses the dev proxy below.
const backend = process.env.BACKEND_ORIGIN ?? 'http://localhost:8000';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		host: true,
		port: 5173,
		proxy: {
			'/api': { target: backend, changeOrigin: true },
			'/_allauth': { target: backend, changeOrigin: true }
		}
	},
	test: {
		include: ['tests/unit/**/*.{test,spec}.ts'],
		environment: 'node'
	}
});
