// The single HTTP client for the Coach Console.
//
// Auth: Django session cookie (allauth *browser* client) + CSRF. The session cookie is
// sent automatically (credentials:include); unsafe methods echo the csrftoken cookie as
// X-CSRFToken. Per-client scope: `actingApi(clientId)` sends X-Acting-Client on every call
// so the coach reads/writes that client's data — the backend authorizes it (reads for any
// active link; writes only on prescription endpoints with can_edit_prescriptions). Passing
// the id per call (rather than a global store) keeps it race-free across concurrent loads.
const BASE = (import.meta.env.PUBLIC_API_BASE ?? '') as string;

function csrfToken(): string {
	if (typeof document === 'undefined') return '';
	const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
	return m ? decodeURIComponent(m[1]) : '';
}

export class APIError extends Error {
	constructor(
		public status: number,
		message: string,
		public fields?: Record<string, string[]>
	) {
		super(message);
	}
}

async function req<T>(
	method: string,
	path: string,
	body?: unknown,
	extraHeaders?: Record<string, string>
): Promise<T> {
	const headers: Record<string, string> = { Accept: 'application/json', ...(extraHeaders ?? {}) };
	if (body !== undefined) headers['Content-Type'] = 'application/json';
	if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) headers['X-CSRFToken'] = csrfToken();

	const res = await fetch(`${BASE}/api/v1${path}`, {
		method,
		credentials: 'include',
		headers,
		body: body === undefined ? undefined : JSON.stringify(body)
	});
	if (res.status === 204) return undefined as T;
	const text = await res.text();
	const data = text ? JSON.parse(text) : undefined;
	if (!res.ok) {
		const msg =
			(data && (data.detail || data.message)) ||
			(data && typeof data === 'object' ? Object.values(data).flat().join(' ') : '') ||
			`${method} ${path} → ${res.status}`;
		throw new APIError(res.status, msg, typeof data === 'object' ? data : undefined);
	}
	return data as T;
}

/** Unwrap DRF pagination (or pass through a bare array). */
export function list<T>(p: { results: T[] } | T[]): T[] {
	return Array.isArray(p) ? p : p.results;
}

/** Coach-as-themselves (coaching endpoints, no acting header). */
export const api = {
	get: <T>(path: string) => req<T>('GET', path),
	post: <T>(path: string, body?: unknown) => req<T>('POST', path, body ?? {}),
	patch: <T>(path: string, body: unknown) => req<T>('PATCH', path, body),
	del: (path: string) => req<void>('DELETE', path)
};

/** Coach acting on a specific client (sends X-Acting-Client). */
export function actingApi(clientId: number) {
	const h = { 'X-Acting-Client': String(clientId) };
	return {
		get: <T>(path: string) => req<T>('GET', path, undefined, h),
		post: <T>(path: string, body?: unknown) => req<T>('POST', path, body ?? {}, h),
		patch: <T>(path: string, body: unknown) => req<T>('PATCH', path, body, h),
		del: (path: string) => req<void>('DELETE', path, undefined, h)
	};
}
