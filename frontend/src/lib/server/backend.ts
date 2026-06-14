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

// --- Session resolution -------------------------------------------------------
//
// The `handle` hook resolves the user on every server-rendered navigation. This is
// only a routing/identity guard: Django independently validates the session cookie
// (and CSRF + ownership) on every real /api request, which is the actual security
// boundary. So it's safe to cache the lookup briefly — we key on the Django session
// id and remember the result for a few seconds, collapsing the repeated round-trips
// a single browsing burst makes. No session id (logged out, or cleared on logout)
// short-circuits to anonymous with no backend call at all.

const SESSION_TTL_MS = 10_000;
const sessionCache = new Map<string, { user: App.Locals['user']; expires: number }>();

function sessionId(cookie: string | null): string | null {
	const m = cookie?.match(/(?:^|;\s*)sessionid=([^;]+)/);
	return m ? m[1] : null;
}

async function fetchSession(cookie: string | null): Promise<App.Locals['user']> {
	const res = await backendFetch('/_allauth/browser/v1/auth/session', { cookie });
	if (!res.ok) return null;
	const body = await res.json().catch(() => null);
	if (body?.meta?.is_authenticated && body?.data?.user) {
		const u = body.data.user;
		return { id: u.id, email: u.email, display: u.display };
	}
	return null;
}

/** Resolve the current user (cached briefly by session id), or null if anonymous. */
export async function getSession(cookie: string | null): Promise<App.Locals['user']> {
	const sid = sessionId(cookie);
	if (!sid) return null; // no Django session cookie → anonymous, skip the round-trip

	const now = Date.now();
	const hit = sessionCache.get(sid);
	if (hit && hit.expires > now) return hit.user;

	const user = await fetchSession(cookie);
	sessionCache.set(sid, { user, expires: now + SESSION_TTL_MS });
	if (sessionCache.size > 100) {
		for (const [k, v] of sessionCache) if (v.expires <= now) sessionCache.delete(k);
	}
	return user;
}
