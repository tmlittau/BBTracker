// Typed wrappers over the nutrition API (session cookies + CSRF, like training).

import { ensureCsrf } from '$lib/api/auth';

const BASE = '/api/v1/nutrition';

export interface Nutrient {
	id: number;
	name: string;
	slug: string;
	category: string;
	unit: string;
	rda: string | null;
	display_order: number;
	is_energy: boolean;
}

export interface ServingSize {
	id: number;
	label: string;
	grams: string;
	is_default: boolean;
}

export interface FoodNutrient {
	id: number;
	nutrient: number;
	nutrient_name: string;
	slug: string;
	unit: string;
	amount_per_100g: string;
}

export interface Food {
	id: number;
	name: string;
	brand: string;
	source: string;
	barcode: string;
	unit: string; // 'g' | 'ml' — base measure for the per-100 profile
	is_verified: boolean;
	is_global: boolean;
	servings: ServingSize[];
	food_nutrients: FoodNutrient[];
}

export interface Meal {
	id: number;
	date: string;
	name: string;
	order: number;
}

export interface DiaryEntry {
	id: number;
	date: string;
	meal: number | null;
	food: number | null;
	recipe: number | null;
	serving: number | null;
	quantity: string;
	grams: string | null;
	item_name: string;
	unit: string; // the food's unit (g/ml), or 'g' for recipe entries
}

export interface NutrientTarget {
	id?: number;
	nutrient: number;
	amount: string;
}

export interface NutritionTarget {
	id: number;
	name: string;
	is_active: boolean;
	day_type: string;
	calories: string | null;
	protein_g: string | null;
	carb_g: string | null;
	fat_g: string | null;
	fiber_g: string | null;
	nutrient_targets: NutrientTarget[];
}

export interface SummaryNutrient {
	id: number;
	name: string;
	slug: string;
	unit: string;
	category: string;
	amount: string;
	target: string | null;
	percent: number | null;
}

export interface DailySummary {
	date: string;
	has_target: boolean;
	target_name: string | null;
	totals: {
		calories: string;
		protein_g: string;
		carb_g: string;
		fat_g: string;
		fiber_g: string;
	};
	nutrients: SummaryNutrient[];
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

export interface FoodInput {
	name: string;
	brand?: string;
	unit?: 'g' | 'ml';
	barcode?: string;
	servings?: { label: string; grams: string; is_default?: boolean }[];
	food_nutrients?: { nutrient: number; amount_per_100g: string }[];
}

/** Draft for the New Food modal, returned by a barcode lookup (nothing saved yet). */
export interface BarcodeLookup {
	name: string;
	brand: string;
	unit: 'g' | 'ml';
	barcode: string;
	/** canonical nutrient slug -> amount per 100 (in the nutrient's own unit) */
	nutrients: Record<string, string>;
}

export const nutritionApi = {
	nutrients: () => req<Nutrient[] | Paginated<Nutrient>>('GET', '/nutrients/').then(list),

	foods: (q = '') =>
		req<Paginated<Food>>('GET', `/foods/${q ? `?q=${encodeURIComponent(q)}` : ''}`).then(list),
	createFood: (data: FoodInput) => req<Food>('POST', '/foods/', data),
	deleteFood: (id: number) => req<void>('DELETE', `/foods/${id}/`),
	// Resolve a UPC/EAN to a Food: returns an existing match or imports it from
	// Open Food Facts (creating a global food). Throws on 404/422/502.
	importBarcode: (barcode: string) =>
		req<Food>('POST', '/foods/import_barcode/', { barcode }),
	// Look up a barcode WITHOUT saving — returns a draft to prefill the New Food
	// modal (from an existing food or Open Food Facts). Throws on 404/422/502.
	lookupBarcode: (barcode: string) =>
		req<BarcodeLookup>('POST', '/foods/lookup_barcode/', { barcode }),

	diary: (date: string) =>
		req<Paginated<DiaryEntry>>('GET', `/diary-entries/?date=${date}`).then(list),
	logEntry: (data: {
		date: string;
		meal: number;
		food?: number;
		recipe?: number;
		serving?: number | null;
		quantity: string;
	}) => req<DiaryEntry>('POST', '/diary-entries/', data),
	deleteEntry: (id: number) => req<void>('DELETE', `/diary-entries/${id}/`),

	meals: (date: string) => req<Paginated<Meal>>('GET', `/meals/?date=${date}`).then(list),
	createMeal: (data: { date: string; name: string; order?: number }) =>
		req<Meal>('POST', '/meals/', data),
	updateMeal: (id: number, data: Partial<Meal>) => req<Meal>('PATCH', `/meals/${id}/`, data),
	deleteMeal: (id: number) => req<void>('DELETE', `/meals/${id}/`),
	reorderMeals: (order: { id: number; order: number }[]) =>
		req<{ updated: number }>('POST', '/meals/reorder/', order),
	copyYesterdayMeals: (date: string) => req<Meal[]>('POST', '/meals/copy_yesterday/', { date }),

	targets: () => req<Paginated<NutritionTarget>>('GET', '/targets/').then(list),
	createTarget: (data: Partial<NutritionTarget>) =>
		req<NutritionTarget>('POST', '/targets/', data),
	updateTarget: (id: number, data: Partial<NutritionTarget>) =>
		req<NutritionTarget>('PATCH', `/targets/${id}/`, data),
	activateTarget: (id: number) => req<NutritionTarget>('POST', `/targets/${id}/activate/`),

	summary: (date: string) => req<DailySummary>('GET', `/summary/?date=${date}`)
};

// Suggested meal names for one-tap creation (meals are free-form per day now).
export const MEAL_SUGGESTIONS = [
	'Breakfast', 'Lunch', 'Dinner', 'Snack', 'Pre-workout', 'Post-workout'
];
