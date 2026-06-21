// "Acting client" context for coaching. Two layers, both browser-only so SSR never
// sends a client header or leaks across users:
//
//  1. `viewingClient` — a persistent "view as client" mode (read drill-ins). When a
//     coach opens a client's full tabs, this is set; it survives navigation + reload
//     (sessionStorage) and an app-wide banner shows until they exit.
//  2. a scoped id set by the in-coach builders for the duration of that page.
//
// `actingHeaders()` sends `X-Acting-Client` when either is active (scoped wins). The
// backend authorises it (active link; `can_edit_prescriptions` for writes on
// prescription endpoints; reads on any owner-scoped GET).
import { browser } from '$app/environment';
import { get, writable } from 'svelte/store';

export interface ActingClient {
	id: number;
	name: string;
}

// --- scoped (component-lifecycle) id, used by the program/protocol builders ---
let scopedActingId: number | null = null;
export function setActingClient(id: number | null): void {
	scopedActingId = browser ? id : null;
}

// --- persistent "view as client" mode ---
const KEY = 'bb_view_as_client';
const initial: ActingClient | null = browser
	? JSON.parse(sessionStorage.getItem(KEY) || 'null')
	: null;
export const viewingClient = writable<ActingClient | null>(initial);
if (browser) {
	viewingClient.subscribe((v) => {
		if (v) sessionStorage.setItem(KEY, JSON.stringify(v));
		else sessionStorage.removeItem(KEY);
	});
}
export function viewAsClient(c: ActingClient): void {
	viewingClient.set(c);
}
export function exitViewAsClient(): void {
	viewingClient.set(null);
}

const SAFE = new Set(['GET', 'HEAD', 'OPTIONS']);

/** Header to merge into a request: the acting client when set (scoped wins), else nothing.
 * Throws on an unsafe request while in persistent "view as client" mode, so a coach can't
 * accidentally save to their own account while viewing a client. Scoped builder writes
 * (scopedActingId) and normal use are unaffected. */
export function actingHeaders(method = 'GET'): Record<string, string> {
	const viewing = browser ? get(viewingClient) : null;
	if (scopedActingId == null && viewing != null && !SAFE.has(method.toUpperCase())) {
		throw new Error('Read-only: exit "view as client" to make changes.');
	}
	const id = scopedActingId ?? viewing?.id ?? null;
	return id != null ? { 'X-Acting-Client': String(id) } : {};
}
