// Web auth against Django + allauth headless (the *browser* client): session cookie
// carries auth, and the CSRF cookie is echoed as X-CSRFToken on unsafe requests.
// (The iOS app uses the app-token flow instead; the web app is the session/CSRF flow —
// see the accounts CSRFView docstring.) Dev requests go through the Vite proxy so
// cookies are same-origin; PUBLIC_API_BASE stays empty.
import { browser } from '$app/environment';
import { writable } from 'svelte/store';

const BASE = (browser ? (import.meta.env.PUBLIC_API_BASE ?? '') : '') as string;

export interface Me {
	id: number;
	email: string;
	first_name: string;
	last_name: string;
	is_coach: boolean;
}

// undefined = not yet checked; null = signed out; Me = signed in. Drives the shell.
export const currentUser = writable<Me | null | undefined>(undefined);

/** Thrown by `login` when the account needs a TOTP code to finish signing in. */
export class MfaRequired extends Error {
	constructor() {
		super('A verification code is required.');
	}
}

function csrfToken(): string {
	if (!browser) return '';
	const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
	return m ? decodeURIComponent(m[1]) : '';
}

function allauthError(data: unknown): string | null {
	const errs = (data as { errors?: { message?: string }[] })?.errors;
	return errs?.[0]?.message ?? null;
}

function pendingMfa(status: number, data: unknown): boolean {
	if (status !== 401) return false;
	const flows = (data as { data?: { flows?: { id?: string }[] } })?.data?.flows ?? [];
	return flows.some((f) => f.id === 'mfa_authenticate');
}

/** Ensure the csrftoken cookie is set (call before any unsafe request pre-login). */
export async function ensureCsrf(): Promise<void> {
	await fetch(`${BASE}/api/v1/auth/csrf/`, { credentials: 'include' });
}

async function post(path: string, body: unknown): Promise<Response> {
	return fetch(`${BASE}${path}`, {
		method: 'POST',
		credentials: 'include',
		headers: {
			'Content-Type': 'application/json',
			Accept: 'application/json',
			'X-CSRFToken': csrfToken()
		},
		body: JSON.stringify(body)
	});
}

/** Sign in. Resolves on success (session cookie set); throws MfaRequired if a TOTP
 * code is needed next, or Error with a readable message on bad credentials. */
export async function login(email: string, password: string): Promise<void> {
	await ensureCsrf();
	const res = await post('/_allauth/browser/v1/auth/login', { email, password });
	if (res.ok) return;
	const data = await res.json().catch(() => ({}));
	if (pendingMfa(res.status, data)) throw new MfaRequired();
	throw new Error(allauthError(data) ?? 'Sign-in failed.');
}

/** Complete a pending MFA login with a TOTP (or recovery) code. */
export async function completeMfa(code: string): Promise<void> {
	const res = await post('/_allauth/browser/v1/auth/2fa/authenticate', { code: code.trim() });
	if (res.ok) return;
	const data = await res.json().catch(() => ({}));
	throw new Error(allauthError(data) ?? 'That code was not accepted.');
}

export async function fetchMe(): Promise<Me> {
	const res = await fetch(`${BASE}/api/v1/auth/me/`, {
		credentials: 'include',
		headers: { Accept: 'application/json' }
	});
	if (!res.ok) throw new Error('Not authenticated');
	return res.json();
}

export async function logout(): Promise<void> {
	try {
		await fetch(`${BASE}/_allauth/browser/v1/auth/session`, {
			method: 'DELETE',
			credentials: 'include',
			headers: { 'X-CSRFToken': csrfToken(), Accept: 'application/json' }
		});
	} catch {
		// best-effort; clear local state regardless
	}
	currentUser.set(null);
}
