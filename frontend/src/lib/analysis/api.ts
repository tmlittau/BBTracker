// Typed client for the Body Analysis API (measurements + computed analysis).

import { ensureCsrf } from '$lib/api/auth';

const BASE = '/api/v1/analysis';

export interface BodyMeasurement {
	id: number;
	date: string;
	type: string;
	value: string;
	unit: string;
	method: string;
	notes: string;
}

export interface Assessment {
	key: string;
	label: string;
	status: 'good' | 'watch' | 'risk';
	value: number | string;
	detail: string;
	source: string | null;
}

export interface AdaptiveTDEE {
	tdee: number;
	weight_slope_kg_wk: number;
	days: number;
	intake_days: number;
	confidence: string;
}

export interface BodyAnalysis {
	date: string;
	sex: string;
	composition: {
		weight_kg: number | null;
		height_cm: number | null;
		body_fat_pct: number | null;
		body_fat_source: string | null;
		fat_mass_kg: number | null;
		lean_mass_kg: number | null;
		ffmi: number | null;
		ffmi_normalized: number | null;
	};
	distribution: { waist_to_height: number | null; waist_to_hip: number | null; rfm: number | null };
	energy: {
		bmr_mifflin: number | null;
		bmr_katch_mcardle: number | null;
		bmr: number | null;
		adaptive: AdaptiveTDEE | null;
		recent_intake?: number;
		balance?: number;
		activity_factor?: number;
	};
	blood_pressure: { systolic: number; diastolic: number } | null;
	bloodwork: { ratios: Record<string, number> };
	assessments: Assessment[];
	measurements: { type: string; value: number; unit: string; date: string; method: string }[];
}

// Measurement catalogue (mirrors the backend MeasurementType + units).
export const MEASUREMENT_TYPES: { key: string; label: string; unit: string }[] = [
	{ key: 'waist', label: 'Waist', unit: 'cm' },
	{ key: 'neck', label: 'Neck', unit: 'cm' },
	{ key: 'hip', label: 'Hip', unit: 'cm' },
	{ key: 'chest', label: 'Chest', unit: 'cm' },
	{ key: 'upper_arm_left', label: 'Upper arm (L)', unit: 'cm' },
	{ key: 'upper_arm_right', label: 'Upper arm (R)', unit: 'cm' },
	{ key: 'forearm_left', label: 'Forearm (L)', unit: 'cm' },
	{ key: 'forearm_right', label: 'Forearm (R)', unit: 'cm' },
	{ key: 'thigh_left', label: 'Thigh (L)', unit: 'cm' },
	{ key: 'thigh_right', label: 'Thigh (R)', unit: 'cm' },
	{ key: 'calf_left', label: 'Calf (L)', unit: 'cm' },
	{ key: 'calf_right', label: 'Calf (R)', unit: 'cm' },
	{ key: 'body_fat', label: 'Body fat %', unit: '%' },
	{ key: 'resting_hr', label: 'Resting HR', unit: 'bpm' }
];
export const BODY_FAT_METHODS = [
	{ key: 'dexa', label: 'DEXA' },
	{ key: 'bia', label: 'Bioimpedance' },
	{ key: 'calipers', label: 'Calipers' },
	{ key: 'scale', label: 'Smart scale' },
	{ key: 'estimate', label: 'Estimated' }
];
export const typeLabel = (key: string) =>
	MEASUREMENT_TYPES.find((t) => t.key === key)?.label ?? key;

interface Paginated<T> {
	count: number;
	results: T[];
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

const list = <T>(p: Paginated<T> | T[]): T[] => (Array.isArray(p) ? p : p.results);

export const analysisApi = {
	body: (date?: string) => req<BodyAnalysis>('GET', `/body/${date ? `?date=${date}` : ''}`),
	measurements: (type?: string) =>
		req<Paginated<BodyMeasurement>>(
			'GET',
			`/measurements/${type ? `?type=${type}` : ''}`
		).then(list),
	addMeasurement: (data: {
		date: string;
		type: string;
		value: string;
		method?: string;
		notes?: string;
	}) => req<BodyMeasurement>('POST', '/measurements/', data),
	deleteMeasurement: (id: number) => req<void>('DELETE', `/measurements/${id}/`)
};
