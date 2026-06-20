// Typed client for the self-coaching layer: phases timeline, dashboard, weekly
// check-in. Session cookies + CSRF, same pattern as the other domain clients.

import { ensureCsrf } from '$lib/api/auth';

const BASE = '/api/v1';

export interface PhaseAdjustment {
	id: number;
	phase: number;
	effective_date: string;
	reason: string;
	nutrition_target: number | null;
	program: number | null;
	protocol: number | null;
	nutrition_target_name: string | null;
	program_name: string | null;
	protocol_name: string | null;
	created_at: string;
}

export interface Phase {
	id: number;
	name: string;
	phase_type: string;
	start_date: string;
	end_date: string | null;
	notes: string;
	is_ongoing: boolean;
	adjustments: PhaseAdjustment[];
	created_at: string;
}

export interface PhaseBrief {
	id: number;
	name: string;
	phase_type: string;
	start_date: string;
	end_date: string | null;
	notes: string | null;
	nutrition_target_name?: string | null;
	program_name?: string | null;
	protocol_name?: string | null;
	adjustment_effective?: string | null;
}

export interface DashboardToday {
	date: string;
	phase: PhaseBrief | null;
	nutrition: {
		has_target: boolean;
		calories: string;
		protein_g: string;
		target_name: string | null;
	};
	workout: {
		count: number;
		completed: boolean;
		exercises: number;
		prs: number;
		name: string;
	} | null;
	doses: { item: string | null; amount: string; unit: string; site: string | null; compound_class: string | null; }[];
}

export interface WeeklyCheckIn {
	start_date: string;
	end_date: string;
	phase: PhaseBrief | null;
	bodyweight: { first: number; last: number; delta: number } | null;
	subjective: Record<string, number | null>;
	training: {
		sessions: number;
		prs: number;
		working_sets: number;
		top_muscles: { muscle: string; sets: number }[];
	};
	nutrition: {
		days_logged: number;
		avg_calories: number | null;
		avg_protein_g: number | null;
		target_name: string | null;
	};
	doses: number;
	photos: number;
	last_bloodwork: string | null;
	check_ins: number;
}

interface Paginated<T> {
	count: number;
	results: T[];
}

const list = <T>(p: Paginated<T> | T[]): T[] => (Array.isArray(p) ? p : p.results);

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

export interface PhaseInput {
	name: string;
	phase_type: string;
	start_date: string;
	end_date?: string | null;
	notes?: string;
}

export interface PhaseAdjustmentInput {
	phase: number;
	effective_date: string;
	reason?: string;
	nutrition_target?: number | null;
	program?: number | null;
	protocol?: number | null;
}

export const coachingApi = {
	phases: () => req<Paginated<Phase>>('GET', '/phases/').then(list),
	createPhase: (data: PhaseInput) => req<Phase>('POST', '/phases/', data),
	updatePhase: (id: number, data: Partial<PhaseInput>) =>
		req<Phase>('PATCH', `/phases/${id}/`, data),
	deletePhase: (id: number) => req<void>('DELETE', `/phases/${id}/`),

	createAdjustment: (data: PhaseAdjustmentInput) =>
		req<PhaseAdjustment>('POST', '/phase-adjustments/', data),
	updateAdjustment: (id: number, data: Partial<PhaseAdjustmentInput>) =>
		req<PhaseAdjustment>('PATCH', `/phase-adjustments/${id}/`, data),
	deleteAdjustment: (id: number) => req<void>('DELETE', `/phase-adjustments/${id}/`),

	dashboard: (date?: string) =>
		req<DashboardToday>('GET', `/dashboard/today/${date ? `?date=${date}` : ''}`),
	weeklyCheckIn: (end?: string) =>
		req<WeeklyCheckIn>('GET', `/checkin/weekly/${end ? `?end=${end}` : ''}`)
};

export const PHASE_TYPES = [
	{ key: 'bulk', label: 'Off-season bulk' },
	{ key: 'cut', label: 'Cut' },
	{ key: 'maintain', label: 'Maintenance' },
	{ key: 'recomp', label: 'Recomp' },
	{ key: 'prep', label: 'Contest prep' },
	{ key: 'cruise', label: 'Cruise' },
	{ key: 'blast', label: 'Blast' },
	{ key: 'trt', label: 'TRT' },
	{ key: 'mini_cut', label: 'Mini-cut' },
	{ key: 'other', label: 'Other' }
];

export const SUBJECTIVE_LABELS: Record<string, string> = {
	energy: 'Energy',
	sleep: 'Sleep',
	mood: 'Mood',
	motivation: 'Motivation',
	soreness: 'Soreness'
};
