import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig, type ProxyOptions } from 'vite';

// In dev, proxy the API + allauth to the backend so the SPA is same-origin.
// The console authenticates with Django SESSION COOKIES + CSRF (allauth "browser"
// client), so the proxy must carry cookies across the localhost↔backend boundary:
//   - rewrite Set-Cookie to host-only + strip Secure, so cookies persist on http://localhost
//   - align the Origin/Referer with the backend so Django's CSRF check passes
// Override the backend with API_PROXY_TARGET (default localhost:8000; prod:
// https://bodybuilding.tmlittau.com).
const target = process.env.API_PROXY_TARGET || 'http://localhost:8000';
const targetOrigin = new URL(target).origin;

const proxy: ProxyOptions = {
	target,
	changeOrigin: true,
	secure: true,
	cookieDomainRewrite: '', // host-only cookie → stored for the dev host
	configure: (proxyServer) => {
		proxyServer.on('proxyReq', (proxyReq) => {
			// Django's CSRF check trusts the Origin; make it the backend's own origin.
			proxyReq.setHeader('origin', targetOrigin);
			if (proxyReq.getHeader('referer')) proxyReq.setHeader('referer', `${targetOrigin}/`);
		});
		proxyServer.on('proxyRes', (proxyRes) => {
			const sc = proxyRes.headers['set-cookie'];
			if (sc) {
				proxyRes.headers['set-cookie'] = sc.map((c) =>
					c.replace(/;\s*Secure/gi, '').replace(/;\s*SameSite=None/gi, '; SameSite=Lax')
				);
			}
		});
	}
};

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		proxy: {
			'/api': proxy,
			'/_allauth': proxy
		}
	}
});
