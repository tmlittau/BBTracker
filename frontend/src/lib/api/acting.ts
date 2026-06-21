// A browser-only "acting client" context for coach editing. When a coach opens a
// client's builder, the coach page sets this id; the domain API clients (training,
// protocols) then send `X-Acting-Client` so their reads/writes target the client.
// The backend authorises it (active link, and `can_edit_prescriptions` for writes
// on prescription endpoints). It is module-level and only ever set in the browser,
// so it never affects SSR rendering or leaks across users.
import { browser } from '$app/environment';

let actingClientId: number | null = null;

/** Scope subsequent API calls to a client (or clear with null). No-op on the server. */
export function setActingClient(id: number | null): void {
	actingClientId = browser ? id : null;
}

/** Header to merge into a request: the acting-client id when set, else nothing. */
export function actingHeaders(): Record<string, string> {
	return actingClientId != null ? { 'X-Acting-Client': String(actingClientId) } : {};
}
