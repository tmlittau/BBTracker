// Typed client for the current user's profile (GET + PATCH /api/v1/auth/me/).

import { ensureCsrf } from './auth';

export interface Profile {
	sex: string;
	date_of_birth: string | null;
	height_cm: string | null;
	unit_system: string;
	timezone: string;
}

export interface Me {
	id: number;
	email: string;
	first_name: string;
	last_name: string;
	profile: Profile;
}

export interface ProfileUpdate {
	first_name?: string;
	last_name?: string;
	profile?: Partial<Profile>;
}

export async function getMe(): Promise<Me> {
	const res = await fetch('/api/v1/auth/me/', { credentials: 'include' });
	if (!res.ok) throw new Error(`GET me → ${res.status}`);
	return res.json();
}

export async function updateMe(data: ProfileUpdate): Promise<Me> {
	const csrf = await ensureCsrf();
	const res = await fetch('/api/v1/auth/me/', {
		method: 'PATCH',
		credentials: 'include',
		headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
		body: JSON.stringify(data)
	});
	if (!res.ok) {
		const detail = await res.text().catch(() => '');
		throw new Error(`PATCH me → ${res.status} ${detail}`);
	}
	return res.json();
}

export const SEX_OPTIONS = [
	{ value: 'unspecified', label: 'Prefer not to say' },
	{ value: 'male', label: 'Male' },
	{ value: 'female', label: 'Female' },
	{ value: 'other', label: 'Other' }
];

export const UNIT_OPTIONS = [
	{ value: 'metric', label: 'Metric (kg, cm)' },
	{ value: 'imperial', label: 'Imperial (lb, in)' }
];
