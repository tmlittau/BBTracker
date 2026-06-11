// Typed client for the progress diary (session cookies + CSRF).
// Photo binaries are uploaded as multipart and streamed back through the API
// (never public URLs), so they stay private.

import { ensureCsrf } from '$lib/api/auth';

const BASE = '/api/v1/diary';

export interface Pose {
	id: number;
	name: string;
	slug: string;
	view: string;
	order: number;
}

export interface CheckIn {
	id: number;
	date: string;
	bodyweight: string | null;
	systolic: number | null;
	diastolic: number | null;
	pulse: number | null;
	energy: number | null;
	sleep: number | null;
	mood: number | null;
	motivation: number | null;
	soreness: number | null;
	notes: string;
	created_at: string;
}

export interface ProgressPhoto {
	id: number;
	pose: number | null;
	pose_name: string;
	taken_on: string;
	notes: string;
	width: number;
	height: number;
	bytes: number;
	content_type: string;
	image_url: string;
	thumb_url: string;
	created_at: string;
}

interface Paginated<T> {
	count: number;
	results: T[];
}

const list = <T>(p: Paginated<T> | T[]): T[] => (Array.isArray(p) ? p : p.results);

async function jsonReq<T>(method: string, path: string, body?: unknown): Promise<T> {
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

export interface CheckInInput {
	date: string;
	bodyweight?: string | null;
	systolic?: number | null;
	diastolic?: number | null;
	pulse?: number | null;
	energy?: number | null;
	sleep?: number | null;
	mood?: number | null;
	motivation?: number | null;
	soreness?: number | null;
	notes?: string;
}

export interface PhotoUploadInput {
	image: File;
	taken_on: string;
	pose?: number | null;
	notes?: string;
}

export const diaryApi = {
	poses: () => jsonReq<Pose[]>('GET', '/poses/'),

	checkIns: (params: { from?: string; to?: string } = {}) => {
		const qs = new URLSearchParams(params as Record<string, string>).toString();
		return jsonReq<Paginated<CheckIn>>('GET', `/check-ins/${qs ? `?${qs}` : ''}`).then(list);
	},
	createCheckIn: (data: CheckInInput) => jsonReq<CheckIn>('POST', '/check-ins/', data),
	updateCheckIn: (id: number, data: Partial<CheckInInput>) =>
		jsonReq<CheckIn>('PATCH', `/check-ins/${id}/`, data),
	deleteCheckIn: (id: number) => jsonReq<void>('DELETE', `/check-ins/${id}/`),

	photos: (params: { pose?: number; taken_on?: string } = {}) => {
		const qs = new URLSearchParams(params as Record<string, string>).toString();
		return jsonReq<Paginated<ProgressPhoto>>('GET', `/photos/${qs ? `?${qs}` : ''}`).then(list);
	},
	latestForPose: (pose: number) =>
		jsonReq<ProgressPhoto | Record<string, never>>('GET', `/photos/latest/?pose=${pose}`),
	deletePhoto: (id: number) => jsonReq<void>('DELETE', `/photos/${id}/`),

	async uploadPhoto(data: PhotoUploadInput): Promise<ProgressPhoto> {
		const csrf = await ensureCsrf();
		const form = new FormData();
		form.append('image', data.image);
		form.append('taken_on', data.taken_on);
		if (data.pose != null) form.append('pose', String(data.pose));
		if (data.notes) form.append('notes', data.notes);
		const res = await fetch(`${BASE}/photos/`, {
			method: 'POST',
			credentials: 'include',
			headers: { 'X-CSRFToken': csrf }, // no Content-Type: browser sets the multipart boundary
			body: form
		});
		if (!res.ok) {
			const detail = await res.text().catch(() => '');
			throw new Error(`upload → ${res.status} ${detail}`);
		}
		return res.json();
	}
};

/** A non-empty latest-photo response (the API returns {} when none exists). */
export function isPhoto(x: ProgressPhoto | Record<string, never>): x is ProgressPhoto {
	return typeof (x as ProgressPhoto).id === 'number';
}

export const SCORE_FIELDS: { key: keyof CheckIn; label: string }[] = [
	{ key: 'energy', label: 'Energy' },
	{ key: 'sleep', label: 'Sleep' },
	{ key: 'mood', label: 'Mood' },
	{ key: 'motivation', label: 'Motivation' },
	{ key: 'soreness', label: 'Soreness' }
];
