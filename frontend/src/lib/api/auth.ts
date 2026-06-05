// Browser-side auth client for django-allauth (headless, session/browser flavour).
// Endpoints live under /_allauth/browser/v1/... and are reached via the dev proxy.

const ALLAUTH = '/_allauth/browser/v1';

export interface AuthResult {
	ok: boolean;
	requires2fa: boolean;
	/** allauth demands a fresh password confirmation before this sensitive action. */
	needsReauth?: boolean;
	error?: string;
}

function getCookie(name: string): string | null {
	const m = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]+)'));
	return m ? decodeURIComponent(m[2]) : null;
}

/** Ensure the csrftoken cookie exists (Django sets it on this GET), and return it. */
export async function ensureCsrf(): Promise<string> {
	let token = getCookie('csrftoken');
	if (!token) {
		await fetch('/api/v1/auth/csrf/', { credentials: 'include' });
		token = getCookie('csrftoken');
	}
	return token ?? '';
}

async function postJson(path: string, body: unknown): Promise<{ res: Response; data: unknown }> {
	const csrf = await ensureCsrf();
	const res = await fetch(path, {
		method: 'POST',
		credentials: 'include',
		headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
		body: JSON.stringify(body)
	});
	const data = await res.json().catch(() => ({}));
	return { res, data };
}

// --- Pure helpers (also unit-tested) ---

export function firstError(data: unknown): string {
	const errors = (data as { errors?: { message?: string }[] })?.errors;
	if (Array.isArray(errors) && errors.length && errors[0].message) {
		return errors[0].message;
	}
	return 'Request failed';
}

export function isPending2fa(data: unknown): boolean {
	const flows = (data as { data?: { flows?: { id?: string; is_pending?: boolean }[] } })?.data
		?.flows;
	return Array.isArray(flows) && flows.some((f) => f.id === 'mfa_authenticate' && f.is_pending);
}

/** A 401 carrying a `reauthenticate` flow means: confirm your password, then retry. */
export function needsReauth(data: unknown): boolean {
	const flows = (data as { data?: { flows?: { id?: string }[] } })?.data?.flows;
	return Array.isArray(flows) && flows.some((f) => f.id === 'reauthenticate');
}

// --- API calls ---

export async function login(email: string, password: string): Promise<AuthResult> {
	const { res, data } = await postJson(`${ALLAUTH}/auth/login`, { email, password });
	if (res.ok) return { ok: true, requires2fa: false };
	if (res.status === 401 && isPending2fa(data)) return { ok: false, requires2fa: true };
	return { ok: false, requires2fa: false, error: firstError(data) };
}

export async function signup(email: string, password: string): Promise<AuthResult> {
	const { res, data } = await postJson(`${ALLAUTH}/auth/signup`, { email, password });
	if (res.ok) return { ok: true, requires2fa: false };
	return { ok: false, requires2fa: false, error: firstError(data) };
}

export async function logout(): Promise<void> {
	const csrf = await ensureCsrf();
	await fetch(`${ALLAUTH}/auth/session`, {
		method: 'DELETE',
		credentials: 'include',
		headers: { 'X-CSRFToken': csrf }
	});
}

/** GET the TOTP setup secret (present only before activation), or null if already active. */
export async function getTotpSecret(): Promise<string | null> {
	const res = await fetch(`${ALLAUTH}/account/authenticators/totp`, { credentials: 'include' });
	const data = await res.json().catch(() => ({}));
	const d = data as { data?: { meta?: { secret?: string } }; meta?: { secret?: string } };
	return d?.data?.meta?.secret ?? d?.meta?.secret ?? null;
}

/** Confirm the current user's password to unlock sensitive actions (e.g. enabling 2FA). */
export async function reauthenticate(password: string): Promise<AuthResult> {
	const { res, data } = await postJson(`${ALLAUTH}/auth/reauthenticate`, { password });
	if (res.ok) return { ok: true, requires2fa: false };
	return { ok: false, requires2fa: false, error: firstError(data) };
}

export async function activateTotp(code: string): Promise<AuthResult> {
	const { res, data } = await postJson(`${ALLAUTH}/account/authenticators/totp`, { code });
	if (res.ok) return { ok: true, requires2fa: false };
	// allauth gates MFA enrollment behind a recent password confirmation.
	if (res.status === 401 && needsReauth(data)) {
		return { ok: false, requires2fa: false, needsReauth: true, error: firstError(data) };
	}
	return { ok: false, requires2fa: false, error: firstError(data) };
}

export async function authenticate2fa(code: string): Promise<AuthResult> {
	const { res, data } = await postJson(`${ALLAUTH}/auth/2fa/authenticate`, { code });
	if (res.ok) return { ok: true, requires2fa: false };
	return { ok: false, requires2fa: false, error: firstError(data) };
}
