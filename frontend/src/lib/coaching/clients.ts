// Coach-side client: the /api/v1/coaching/ endpoints (client list, per-client
// overview, invite lifecycle) plus a client-scoped check-in report download.
// Session cookies + CSRF, same pattern as the other domain clients.

import type { BodyAnalysis } from '$lib/analysis/api';
import { ensureCsrf } from '$lib/api/auth';

import type { DashboardToday, WeeklyCheckIn } from './api';

const BASE = '/api/v1/coaching';

export interface ClientBrief {
	link_id: number;
	client_id: number;
	email: string;
	name: string;
	status: string;
	phase: string | null;
	last_check_in: string | null;
	bodyweight: number | null;
}

export interface CoachLink {
	id: number;
	coach: number;
	client: number;
	coach_email: string;
	client_email: string;
	coach_name: string;
	client_name: string;
	status: string;
	created_at: string;
	responded_at: string | null;
}

export interface ClientOverview {
	client: { id: number; email: string; name: string };
	dashboard: DashboardToday;
	weekly_check_in: WeeklyCheckIn;
	body: BodyAnalysis;
}

export interface InvitesPayload {
	sent: CoachLink[];
	received: CoachLink[];
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

export const coachApi = {
	clients: () => req<ClientBrief[]>('GET', '/clients/'),
	overview: (id: number) => req<ClientOverview>('GET', `/clients/${id}/overview/`),
	invites: () => req<InvitesPayload>('GET', '/invites/'),
	invite: (email: string) => req<CoachLink>('POST', '/invites/', { email }),
	respond: (id: number, accept: boolean) =>
		req<CoachLink>('POST', `/invites/${id}/respond/`, { accept }),
	revoke: (id: number) => req<CoachLink>('POST', `/links/${id}/revoke/`)
};

/** Download a client's check-in report PDF (coach view) via the X-Acting-Client header. */
export async function downloadClientReport(
	clientId: number,
	opts: { start?: string; end?: string; include?: string } = {}
): Promise<void> {
	const qs = new URLSearchParams();
	if (opts.start) qs.set('start', opts.start);
	if (opts.end) qs.set('end', opts.end);
	if (opts.include) qs.set('include', opts.include);
	const res = await fetch(`/api/v1/report/checkin/?${qs}`, {
		credentials: 'include',
		headers: { 'X-Acting-Client': String(clientId) }
	});
	if (!res.ok) throw new Error(`Report failed (${res.status})`);
	const blob = await res.blob();
	const cd = res.headers.get('Content-Disposition') ?? '';
	const m = cd.match(/filename="?([^"]+)"?/);
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = m ? m[1] : 'client-checkin.pdf';
	a.click();
	URL.revokeObjectURL(url);
}
