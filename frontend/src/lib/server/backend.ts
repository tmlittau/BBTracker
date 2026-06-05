import { env } from '$env/dynamic/private';

// Server-to-server origin for Django. In Docker this is http://backend:8000.
const BACKEND_ORIGIN = env.BACKEND_ORIGIN ?? 'http://localhost:8000';

/** Fetch from the Django backend, forwarding the browser's cookies for session auth. */
export async function backendFetch(
	path: string,
	init: RequestInit & { cookie?: string | null } = {}
): Promise<Response> {
	const { cookie, headers, ...rest } = init;
	const h = new Headers(headers);
	if (cookie) h.set('cookie', cookie);
	return fetch(`${BACKEND_ORIGIN}${path}`, { ...rest, headers: h });
}

/** Resolve the current user from allauth's session endpoint, or null if anonymous. */
export async function getSession(cookie: string | null): Promise<App.Locals['user']> {
	const res = await backendFetch('/_allauth/browser/v1/auth/session', { cookie });
	if (!res.ok) return null;
	const body = await res.json().catch(() => null);
	if (body?.meta?.is_authenticated && body?.data?.user) {
		const u = body.data.user;
		return { id: u.id, email: u.email, display: u.display };
	}
	return null;
}
