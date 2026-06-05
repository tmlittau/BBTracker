// Typed wrappers over the protocols API (session cookies + CSRF).

import { ensureCsrf } from '$lib/api/auth';

const BASE = '/api/v1/protocols';

export interface Compound {
	id: number;
	name: string;
	slug: string;
	compound_class: string;
	default_unit: string;
	default_route: string;
	half_life_hours: string | null;
	ester: string;
	active_fraction: string;
	notes: string;
	is_global: boolean;
}

export interface SupplementNutrient {
	id?: number;
	nutrient: number;
	nutrient_name?: string;
	slug?: string;
	unit?: string;
	amount_per_serving: string;
}

export interface Supplement {
	id: number;
	name: string;
	brand: string;
	serving_label: string;
	target_benefit: string;
	notes: string;
	is_global: boolean;
	supplement_nutrients: SupplementNutrient[];
}

export interface InjectionSite {
	id: number;
	name: string;
	slug: string;
	region: string;
	side: string;
	x: string;
	y: string;
}

export interface SiteRecency extends InjectionSite {
	last_used: string | null;
	days_since: number | null;
	status: string;
}

export interface BloodMarker {
	id: number;
	name: string;
	slug: string;
	unit: string;
	category: string;
	ref_low: string | null;
	ref_high: string | null;
	ref_low_male: string | null;
	ref_high_male: string | null;
	ref_low_female: string | null;
	ref_high_female: string | null;
	display_order: number;
}

export interface ProtocolItem {
	id: number;
	protocol: number;
	compound: number | null;
	supplement: number | null;
	item_name: string;
	dose_amount: string | null;
	dose_unit: string;
	route: string;
	frequency: string;
	days_of_week: number[];
	times_of_day: string[];
	target_benefit: string;
	notes: string;
	order: number;
}

export interface BloodMatrixCell {
	value: string;
	pct_change: number | null;
	flag: string;
}
export interface BloodMatrixRow {
	marker: string;
	slug: string;
	unit: string;
	category: string;
	cells: (BloodMatrixCell | null)[];
}
export interface BloodMatrix {
	dates: string[];
	rows: BloodMatrixRow[];
}

export interface Protocol {
	id: number;
	name: string;
	is_active: boolean;
	started_on: string | null;
	ended_on: string | null;
	notes: string;
	items: ProtocolItem[];
}

export interface DoseLog {
	id: number;
	protocol_item: number | null;
	compound: number | null;
	supplement: number | null;
	item_name: string;
	taken_at: string;
	amount: string;
	unit: string;
	route: string;
	injection_site: number | null;
	site_name: string | null;
	notes: string;
	side_effects: string;
}

export interface Vial {
	id: number;
	compound: number;
	compound_name: string;
	label: string;
	concentration_mg_ml: string | null;
	total_amount: string;
	remaining_amount: string;
	unit: string;
	reorder_threshold: string;
	needs_reorder: boolean;
}

export interface BloodResult {
	id: number;
	marker: number;
	marker_name: string;
	unit: string;
	value: string;
	measured_on: string;
	notes: string;
}

export interface BloodPressureLog {
	id: number;
	systolic: number;
	diastolic: number;
	pulse: number | null;
	measured_at: string;
	notes: string;
}

export interface ConcentrationPoint {
	t: string;
	value: number;
}

export interface AdherenceRow {
	item_id: number;
	name: string;
	frequency: string;
	expected: number;
	actual: number;
	adherence: number | null;
}

export interface MarkerTrendPoint {
	date: string;
	value: string;
	flag: string;
}

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

export const protocolsApi = {
	compounds: (q = '') =>
		req<Paginated<Compound>>('GET', `/compounds/${q ? `?q=${encodeURIComponent(q)}` : ''}`).then(
			list
		),
	createCompound: (data: Partial<Compound>) => req<Compound>('POST', '/compounds/', data),

	supplements: (q = '') =>
		req<Paginated<Supplement>>(
			'GET',
			`/supplements/${q ? `?q=${encodeURIComponent(q)}` : ''}`
		).then(list),
	createSupplement: (data: Partial<Supplement>) => req<Supplement>('POST', '/supplements/', data),
	deleteSupplement: (id: number) => req<void>('DELETE', `/supplements/${id}/`),

	injectionSites: () => req<InjectionSite[]>('GET', '/injection-sites/'),
	siteRecency: (days = 30) => req<SiteRecency[]>('GET', `/injection-sites/recency/?days=${days}`),
	suggestSite: () => req<SiteRecency>('GET', '/injection-sites/suggest/'),

	bloodMarkers: () => req<BloodMarker[]>('GET', '/blood-markers/'),

	protocols: () => req<Paginated<Protocol>>('GET', '/protocols/').then(list),
	protocol: (id: number) => req<Protocol>('GET', `/protocols/${id}/`),
	createProtocol: (data: { name: string; started_on?: string }) =>
		req<Protocol>('POST', '/protocols/', data),
	deleteProtocol: (id: number) => req<void>('DELETE', `/protocols/${id}/`),
	activateProtocol: (id: number) => req<Protocol>('POST', `/protocols/${id}/activate/`),
	adherence: (id: number, windowDays = 28) =>
		req<AdherenceRow[]>('GET', `/protocols/${id}/adherence/?window_days=${windowDays}`),

	createItem: (data: Partial<ProtocolItem> & { protocol: number }) =>
		req<ProtocolItem>('POST', '/protocol-items/', data),
	deleteItem: (id: number) => req<void>('DELETE', `/protocol-items/${id}/`),

	doses: (params: { date?: string; compound?: number } = {}) => {
		const qs = new URLSearchParams(params as Record<string, string>).toString();
		return req<Paginated<DoseLog>>('GET', `/dose-logs/${qs ? `?${qs}` : ''}`).then(list);
	},
	logDose: (data: Partial<DoseLog> & { taken_at: string; amount: string }) =>
		req<DoseLog>('POST', '/dose-logs/', data),
	deleteDose: (id: number) => req<void>('DELETE', `/dose-logs/${id}/`),

	vials: () => req<Paginated<Vial>>('GET', '/vials/').then(list),
	createVial: (data: Partial<Vial> & { compound: number }) => req<Vial>('POST', '/vials/', data),

	concentration: (compound: number, days = 30) =>
		req<ConcentrationPoint[]>('GET', `/concentration/?compound=${compound}&days=${days}`),

	updateItem: (id: number, data: Partial<ProtocolItem>) =>
		req<ProtocolItem>('PATCH', `/protocol-items/${id}/`, data),

	bloodResults: (marker?: number) =>
		req<Paginated<BloodResult>>(
			'GET',
			`/blood-results/${marker ? `?marker=${marker}` : ''}`
		).then(list),
	logBloodResult: (data: { marker: number; value: string; measured_on: string }) =>
		req<BloodResult>('POST', '/blood-results/', data),
	bulkBloodResults: (measured_on: string, results: { marker: number; value: string }[]) =>
		req<BloodResult[]>('POST', '/blood-results/bulk/', { measured_on, results }),
	bloodworkMatrix: () => req<BloodMatrix>('GET', '/blood-results/matrix/'),
	markerTrend: (marker: number) =>
		req<MarkerTrendPoint[]>('GET', `/blood-results/trend/?marker=${marker}`),

	bpLogs: () => req<Paginated<BloodPressureLog>>('GET', '/bp-logs/').then(list),
	logBp: (data: { systolic: number; diastolic: number; pulse?: number; measured_at: string }) =>
		req<BloodPressureLog>('POST', '/bp-logs/', data)
};

export const FREQUENCIES = [
	{ key: 'daily', label: 'Daily' },
	{ key: 'eod', label: 'Every other day' },
	{ key: 'every_3_days', label: 'Every 3 days' },
	{ key: 'weekly', label: 'Weekly' },
	{ key: 'specific_days', label: 'Specific days of week' },
	{ key: 'prn', label: 'As needed' }
];

// Mon–Sun selector for the "specific days" frequency (0=Mon … 6=Sun).
export const WEEKDAYS = [
	{ key: 0, label: 'Mon' },
	{ key: 1, label: 'Tue' },
	{ key: 2, label: 'Wed' },
	{ key: 3, label: 'Thu' },
	{ key: 4, label: 'Fri' },
	{ key: 5, label: 'Sat' },
	{ key: 6, label: 'Sun' }
];

// Multi-select for doses within a day.
export const TIMES_OF_DAY = [
	{ key: 'waking', label: 'Waking' },
	{ key: 'am', label: 'AM' },
	{ key: 'noon', label: 'Noon' },
	{ key: 'pm', label: 'PM' },
	{ key: 'night', label: 'Night' }
];

export const ROUTES = [
	{ key: 'im', label: 'Intramuscular' },
	{ key: 'subq', label: 'Subcutaneous' },
	{ key: 'oral', label: 'Oral' },
	{ key: 'topical', label: 'Topical' },
	{ key: 'nasal', label: 'Nasal' },
	{ key: 'other', label: 'Other' }
];
