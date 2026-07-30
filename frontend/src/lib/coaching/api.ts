// The /api/v1/coaching/* endpoints — run as the coach (no acting header).
import { api, list } from '../api/client';

export type Relationship = 'self' | 'active' | 'pending' | 'declined' | 'revoked' | 'none';

export interface UserResult {
	id: number;
	email: string;
	name: string;
	relationship: Relationship;
}

export interface ClientBrief {
	link_id: number;
	client_id: number;
	email: string;
	name: string;
	status: string;
	can_edit_prescriptions: boolean;
	phase: string | null;
	last_check_in: string | null;
	bodyweight: number | null;
}

export interface ClientOverview {
	client: { id: number; email: string; name: string };
	dashboard: {
		phase: { name: string; phase_type: string } | null;
		nutrition: { calories: string; protein_g: string; target_name: string | null };
		workout: { name: string | null } | null;
		doses: unknown[];
	};
	weekly_check_in: Record<string, unknown>;
	body: BodyAnalysis;
}

export interface BodyAnalysis {
	composition: {
		weight_kg: number | null;
		body_fat_pct: number | null;
		fat_mass_kg: number | null;
		lean_mass_kg: number | null;
		ffmi: number | null;
	};
	energy: { bmr: number | null; tdee: number | null; [k: string]: unknown };
	bloodwork: { markers?: BloodMarkerRow[]; [k: string]: unknown };
	insights: { label: string; detail: string; severity?: string }[];
	measurements: Record<string, unknown>;
}

export interface BloodMarkerRow {
	name: string;
	value: number | string;
	unit: string;
	flag?: string; // 'low' | 'high' | 'in_range' | ...
	measured_on?: string;
}

// --- Check-in review loop ---
export interface CheckInRow {
	id: number;
	client_id: number;
	client_name: string;
	date: string;
	bodyweight: number | null;
	energy: number | null;
	sleep: number | null;
	has_notes: boolean;
	comment_count: number;
	reviewed: boolean;
}

export interface CheckInComment {
	id: number;
	check_in: number;
	author: number;
	author_name: string;
	by_coach: boolean;
	body: string;
	created_at: string;
}

export interface WeeklyCheckin {
	start_date: string;
	end_date: string;
	bodyweight: { first: number; last: number; delta: number } | null;
	subjective: Record<'energy' | 'sleep' | 'mood' | 'motivation' | 'soreness', number | null>;
	training: { sessions: number; prs: number; working_sets: number; top_muscles: { muscle: string; sets: number }[] };
	nutrition: { days_logged: number; avg_calories: number | null; avg_protein_g: number | null; target_name: string | null };
	doses: number;
	photos: number;
	last_bloodwork: string | null;
	check_ins: number;
}

export interface CheckInDetail {
	check_in: {
		id: number;
		date: string;
		bodyweight: number | null;
		systolic: number | null;
		diastolic: number | null;
		pulse: number | null;
		energy: number | null;
		sleep: number | null;
		mood: number | null;
		motivation: number | null;
		soreness: number | null;
		notes: string;
	};
	client: { id: number; name: string; email: string };
	previous_bodyweight: number | null;
	weight_series: { date: string; bodyweight: number | null }[];
	weekly: WeeklyCheckin;
	comments: CheckInComment[];
}

export const coachingApi = {
	clients: () => api.get<{ results: ClientBrief[] } | ClientBrief[]>('/coaching/clients/').then(list),
	overview: (clientId: number) => api.get<ClientOverview>(`/coaching/clients/${clientId}/overview/`),
	invite: (email: string) => api.post('/coaching/invites/', { email }),
	searchUsers: (q: string) => api.get<UserResult[]>(`/coaching/user-search/?q=${encodeURIComponent(q)}`),
	revokeLink: (linkId: number) => api.post(`/coaching/links/${linkId}/revoke/`),
	setPermission: (linkId: number, canEdit: boolean) =>
		api.post(`/coaching/links/${linkId}/permission/`, { can_edit_prescriptions: canEdit }),

	checkIns: (params: { client?: number; pending?: boolean } = {}) => {
		const q = new URLSearchParams();
		if (params.client != null) q.set('client', String(params.client));
		if (params.pending) q.set('status', 'pending');
		const qs = q.toString();
		return api.get<CheckInRow[]>(`/coaching/check-ins/${qs ? `?${qs}` : ''}`);
	},
	checkIn: (id: number) => api.get<CheckInDetail>(`/coaching/check-ins/${id}/`),
	addCheckInComment: (id: number, body: string) =>
		api.post<CheckInComment>(`/coaching/check-ins/${id}/comments/`, { body }),

	applyTemplate: (kind: 'program' | 'protocol' | 'meal_plan', id: number, client: number) =>
		api.post<{ id: number; name: string }>('/coaching/templates/apply/', { kind, id, client })
};
