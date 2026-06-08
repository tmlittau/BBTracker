// Typed client for reminder settings + rest-timer notifications (session cookies
// + CSRF). Rest schedule/cancel are best-effort — they must never block the
// workout flow if Home Assistant / the backend hiccups.

import { ensureCsrf } from '$lib/api/auth';

const BASE = '/api/v1/notifications';

export interface ReminderSettings {
	enabled: boolean;
	rest_enabled: boolean;
	waking: string; // "HH:MM:SS"
	am: string;
	noon: string;
	pm: string;
	night: string;
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
	const opts: RequestInit = { method, credentials: 'include', headers: {} };
	if (body !== undefined) {
		const csrf = await ensureCsrf();
		opts.headers = { 'Content-Type': 'application/json', 'X-CSRFToken': csrf };
		opts.body = JSON.stringify(body);
	} else if (method !== 'GET') {
		const csrf = await ensureCsrf();
		opts.headers = { 'X-CSRFToken': csrf };
	}
	const res = await fetch(`${BASE}${path}`, opts);
	if (!res.ok) {
		const detail = await res.text().catch(() => '');
		throw new Error(`${method} ${path} → ${res.status} ${detail}`);
	}
	if (res.status === 204) return undefined as T;
	return res.json() as Promise<T>;
}

export const notificationsApi = {
	settings: () => req<ReminderSettings>('GET', '/reminder-settings/'),
	updateSettings: (data: Partial<ReminderSettings>) =>
		req<ReminderSettings>('PATCH', '/reminder-settings/', data),
	test: () => req<{ ok: boolean }>('POST', '/test/'),
	// Best-effort: schedule/cancel the "rest over" notification (never throws).
	scheduleRest: (seconds: number) =>
		req<{ ok: boolean }>('POST', '/rest/schedule/', { seconds }).catch(() => ({ ok: false })),
	cancelRest: () => req<{ ok: boolean }>('POST', '/rest/cancel/').catch(() => ({ ok: false }))
};
