import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { SvelteKitPWA } from '@vite-pwa/sveltekit';
import { defineConfig } from 'vitest/config';

// Server-side SvelteKit talks to Django directly; the browser uses the dev proxy below.
const backend = process.env.BACKEND_ORIGIN ?? 'http://localhost:8000';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit(),
		SvelteKitPWA({
			registerType: 'autoUpdate',
			devOptions: { enabled: true },
			manifest: {
				name: 'BBTracker',
				short_name: 'BBTracker',
				description: 'Self-coaching bodybuilding tracker — training, nutrition, protocols, diary.',
				start_url: '/dashboard',
				scope: '/',
				display: 'standalone',
				orientation: 'portrait',
				background_color: '#0a0a0a',
				theme_color: '#4f46e5',
				icons: [
					{ src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
					{ src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
					{ src: '/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' }
				]
			},
			workbox: {
				globPatterns: ['**/*.{js,css,html,svg,png,ico,webp,woff,woff2}'],
				// SSR-safe offline shell: navigations + API use NetworkFirst, so online
				// always hits the server (fresh SSR / data) and offline falls back to the
				// last-seen response. Auth endpoints are never cached.
				runtimeCaching: [
					{
						urlPattern: ({ request }) => request.mode === 'navigate',
						handler: 'NetworkFirst',
						options: { cacheName: 'pages', networkTimeoutSeconds: 3, expiration: { maxEntries: 50 } }
					},
					{
						urlPattern: ({ url }) => url.pathname.startsWith('/api'),
						handler: 'NetworkFirst',
						options: {
							cacheName: 'api',
							networkTimeoutSeconds: 5,
							expiration: { maxEntries: 200, maxAgeSeconds: 86400 }
						}
					}
				]
			}
		})
	],
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
