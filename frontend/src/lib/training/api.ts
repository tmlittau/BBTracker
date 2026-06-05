// Thin typed wrappers over the training API. Uses the same credentials/CSRF
// approach as the auth client (session cookies + X-CSRFToken).

import { ensureCsrf } from '$lib/api/auth';

const BASE = '/api/v1/training';

export interface Muscle {
	id: number;
	name: string;
	slug: string;
	group: string;
}

export interface Exercise {
	id: number;
	name: string;
	category: string;
	load_type: string;
	primary_muscles: number[];
	secondary_muscles: number[];
	primary_muscle_names: string[];
	equipment: string;
	instructions: string;
	is_unilateral: boolean;
	is_global: boolean;
}

export interface PlannedSet {
	id: number;
	slot: number;
	order: number;
	set_type: string;
	target_reps_low: number | null;
	target_reps_high: number | null;
	target_weight: string | null;
	target_rpe: string | null;
	rest_seconds: number | null;
}

export interface ExerciseSlot {
	id: number;
	day: number;
	exercise: number;
	exercise_name: string;
	order: number;
	notes: string;
	superset_group: number | null;
	planned_sets: PlannedSet[];
}

export interface TrainingDay {
	id: number;
	program: number;
	name: string;
	order: number;
	notes: string;
	slots: ExerciseSlot[];
}

export interface Program {
	id: number;
	name: string;
	description: string;
	is_active: boolean;
	created_at: string;
	days: TrainingDay[];
}

export interface LoggedSet {
	id: number;
	logged_exercise: number;
	order: number;
	set_type: string;
	reps: number | null;
	weight: string | null;
	rpe: string | null;
	rir: number | null;
	duration_seconds: number | null;
	distance_m: string | null;
	rest_seconds: number | null;
	is_completed: boolean;
	e1rm: string | null;
	is_pr: boolean;
}

export interface LoggedExercise {
	id: number;
	session: number;
	exercise: number;
	exercise_name: string;
	order: number;
	superset_group: number | null;
	notes: string;
	sets: LoggedSet[];
}

export interface WorkoutSession {
	id: number;
	day: number | null;
	name: string;
	started_at: string;
	ended_at: string | null;
	bodyweight: string | null;
	notes: string;
	is_completed: boolean;
	logged_exercises: LoggedExercise[];
}

export interface WorkoutSessionListItem {
	id: number;
	day: number | null;
	name: string;
	started_at: string;
	ended_at: string | null;
	bodyweight: string | null;
	is_completed: boolean;
	exercise_count: number;
}

export interface ExerciseHistoryPoint {
	session_id: number;
	date: string;
	best_e1rm: string | null;
	top_weight: string | null;
	volume: string;
}

export interface MuscleVolume {
	muscle: string;
	sets: number;
	tonnage: string;
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

export const trainingApi = {
	muscles: () => req<Muscle[] | Paginated<Muscle>>('GET', '/muscles/').then(list),
	exercises: (q = '') =>
		req<Paginated<Exercise>>('GET', `/exercises/${q ? `?q=${encodeURIComponent(q)}` : ''}`).then(
			list
		),
	createExercise: (data: Partial<Exercise>) => req<Exercise>('POST', '/exercises/', data),
	exerciseHistory: (id: number) =>
		req<ExerciseHistoryPoint[]>('GET', `/exercises/${id}/history/`),

	programs: () => req<Paginated<Program>>('GET', '/programs/').then(list),
	program: (id: number) => req<Program>('GET', `/programs/${id}/`),
	createProgram: (data: { name: string; description?: string }) =>
		req<Program>('POST', '/programs/', data),
	deleteProgram: (id: number) => req<void>('DELETE', `/programs/${id}/`),
	activateProgram: (id: number) => req<Program>('POST', `/programs/${id}/activate/`),

	createDay: (data: { program: number; name: string; order: number }) =>
		req<TrainingDay>('POST', '/training-days/', data),
	deleteDay: (id: number) => req<void>('DELETE', `/training-days/${id}/`),

	createSlot: (data: { day: number; exercise: number; order: number }) =>
		req<ExerciseSlot>('POST', '/exercise-slots/', data),
	deleteSlot: (id: number) => req<void>('DELETE', `/exercise-slots/${id}/`),
	reorderSlots: (order: { id: number; order: number }[]) =>
		req<{ updated: number }>('POST', '/exercise-slots/reorder/', order),

	createPlannedSet: (data: Partial<PlannedSet> & { slot: number }) =>
		req<PlannedSet>('POST', '/planned-sets/', data),
	updatePlannedSet: (id: number, data: Partial<PlannedSet>) =>
		req<PlannedSet>('PATCH', `/planned-sets/${id}/`, data),
	deletePlannedSet: (id: number) => req<void>('DELETE', `/planned-sets/${id}/`),
	reorderPlannedSets: (order: { id: number; order: number }[]) =>
		req<{ updated: number }>('POST', '/planned-sets/reorder/', order),

	sessions: () => req<Paginated<WorkoutSessionListItem>>('GET', '/workout-sessions/').then(list),
	session: (id: number) => req<WorkoutSession>('GET', `/workout-sessions/${id}/`),
	createSession: (data: { name?: string; day?: number | null; started_at: string }) =>
		req<WorkoutSession>('POST', '/workout-sessions/', data),
	startFromDay: (day: number) =>
		req<WorkoutSession>('POST', '/workout-sessions/start_from_day/', { day }),
	finishSession: (id: number, dropIncomplete = false) =>
		req<WorkoutSession>('POST', `/workout-sessions/${id}/finish/`, { drop_incomplete: dropIncomplete }),

	createLoggedExercise: (data: { session: number; exercise: number; order: number }) =>
		req<LoggedExercise>('POST', '/logged-exercises/', data),
	deleteLoggedExercise: (id: number) => req<void>('DELETE', `/logged-exercises/${id}/`),
	reorderLoggedExercises: (order: { id: number; order: number }[]) =>
		req<{ updated: number }>('POST', '/logged-exercises/reorder/', order),
	createLoggedSet: (data: Partial<LoggedSet> & { logged_exercise: number }) =>
		req<LoggedSet>('POST', '/logged-sets/', data),
	updateLoggedSet: (id: number, data: Partial<LoggedSet>) =>
		req<LoggedSet>('PATCH', `/logged-sets/${id}/`, data),
	deleteLoggedSet: (id: number) => req<void>('DELETE', `/logged-sets/${id}/`),

	volume: (days = 7) => req<MuscleVolume[]>('GET', `/volume/?days=${days}`)
};
