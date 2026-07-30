// Coach-scoped reads + prescription writes for one client, via X-Acting-Client.
// The backend authorizes: reads for any active link; writes only on prescription
// endpoints (phases, nutrition targets, programs+days/slots/sets, protocols+items)
// with can_edit_prescriptions.
import { actingApi, api, list } from '../api/client';
import type { BodyAnalysis } from '../coaching/api';

// ---------------------------------------------------------------------------
// Nutrition + phases (Phase 2/3 — unchanged)
// ---------------------------------------------------------------------------
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
	nutrient_targets: unknown[];
}

export interface NutritionTargetInput {
	name: string;
	calories: string | null;
	protein_g: string | null;
	carb_g: string | null;
	fat_g: string | null;
	fiber_g?: string | null;
}

export interface Phase {
	id: number;
	name: string;
	phase_type: string; // prep | maintain | bulk | recomp
	start_date: string;
	end_date: string | null;
	notes: string;
	is_ongoing: boolean;
	adjustments: unknown[];
}

export const PHASE_TYPES = [
	{ value: 'bulk', label: 'Bulk' },
	{ value: 'recomp', label: 'Recomp' },
	{ value: 'maintain', label: 'Maintain' },
	{ value: 'prep', label: 'Prep / cut' }
];

// ---------------------------------------------------------------------------
// Training tree: Program → TrainingDay → ExerciseSlot → PlannedSet
// ---------------------------------------------------------------------------
export interface PlannedSet {
	id: number;
	slot: number;
	order: number;
	set_type: string;
	target_reps_low: number | null;
	target_reps_high: number | null;
	target_weight: string | null;
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

export interface ProgramBrief {
	id: number;
	name: string;
	description: string;
	is_active: boolean;
}

export interface ExerciseRef {
	id: number;
	name: string;
	category: string;
	primary_muscle_names: string[];
	is_global: boolean;
}

export const SET_TYPES = [
	{ value: 'warmup', label: 'Warm-up' },
	{ value: 'working', label: 'Working' },
	{ value: 'top_set', label: 'Top set' },
	{ value: 'backoff', label: 'Back-off' },
	{ value: 'drop', label: 'Drop set' },
	{ value: 'rest_pause', label: 'Rest-pause' },
	{ value: 'myo_rep', label: 'Myo-rep' },
	{ value: 'cluster', label: 'Cluster' },
	{ value: 'amrap', label: 'AMRAP' },
	{ value: 'failure', label: 'To failure' }
];

// ---------------------------------------------------------------------------
// Protocol tree: Protocol → ProtocolItem (compound | supplement | custom)
// ---------------------------------------------------------------------------
export interface ProtocolItem {
	id: number;
	protocol: number;
	compound: number | null;
	supplement: number | null;
	item_name: string;
	dose_amount: string | null;
	dose_unit: string;
	route: string;
	compound_route: string;
	frequency: string;
	days_of_week: number[];
	times_of_day: string[];
	target_benefit: string;
	notes: string;
	order: number;
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

export interface ProtocolBrief {
	id: number;
	name: string;
	is_active: boolean;
	started_on: string | null;
}

export interface CompoundRef {
	id: number;
	name: string;
	compound_class: string;
	default_unit: string;
	default_route: string;
	is_global: boolean;
}

export interface SupplementRef {
	id: number;
	name: string;
	brand: string;
	serving_label: string;
	is_global: boolean;
}

export const DOSE_UNITS = [
	{ value: 'mg', label: 'mg' },
	{ value: 'mcg', label: 'µg' },
	{ value: 'iu', label: 'IU' },
	{ value: 'ml', label: 'ml' },
	{ value: 'tablet', label: 'tablet' },
	{ value: 'capsule', label: 'capsule' },
	{ value: 'serving', label: 'serving' }
];

export const ROUTES = [
	{ value: '', label: '—' },
	{ value: 'im', label: 'Intramuscular' },
	{ value: 'subq', label: 'Subcutaneous' },
	{ value: 'oral', label: 'Oral' },
	{ value: 'topical', label: 'Topical' },
	{ value: 'nasal', label: 'Nasal' },
	{ value: 'other', label: 'Other' }
];

export const FREQUENCIES = [
	{ value: 'daily', label: 'Daily' },
	{ value: 'eod', label: 'Every other day' },
	{ value: 'every_3_days', label: 'Every 3 days' },
	{ value: 'weekly', label: 'Weekly' },
	{ value: '2x_week', label: '2× / week' },
	{ value: '3x_week', label: '3× / week' },
	{ value: '2x_day', label: '2× / day' },
	{ value: 'specific_days', label: 'Specific days' },
	{ value: 'prn', label: 'As needed' }
];

export const TIMES_OF_DAY = [
	{ value: 'waking', label: 'Waking' },
	{ value: 'am', label: 'AM' },
	{ value: 'noon', label: 'Noon' },
	{ value: 'pm', label: 'PM' },
	{ value: 'night', label: 'Night' }
];

// 0 = Monday … 6 = Sunday (matches ProtocolItem.days_of_week convention).
export const WEEKDAYS = [
	{ value: 0, label: 'Mon' },
	{ value: 1, label: 'Tue' },
	{ value: 2, label: 'Wed' },
	{ value: 3, label: 'Thu' },
	{ value: 4, label: 'Fri' },
	{ value: 5, label: 'Sat' },
	{ value: 6, label: 'Sun' }
];

// ---------------------------------------------------------------------------
// Reference libraries (global seeds + the client's own custom items). A coach
// with edit access can add/edit/delete the client's customs; globals are read-only.
// ---------------------------------------------------------------------------
export interface Muscle {
	id: number;
	name: string;
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

export interface Compound {
	id: number;
	name: string;
	compound_class: string;
	default_unit: string;
	default_route: string;
	half_life_hours: string | null;
	ester: string;
	notes: string;
	is_global: boolean;
}

export interface Supplement {
	id: number;
	name: string;
	brand: string;
	serving_label: string;
	target_benefit: string;
	notes: string;
	is_global: boolean;
	supplement_nutrients: unknown[];
}

export interface FoodNutrient {
	nutrient: number;
	amount_per_100g: string;
	nutrient_name?: string;
	slug?: string;
	unit?: string;
}

export interface Food {
	id: number;
	name: string;
	brand: string;
	unit: string;
	is_global: boolean;
	food_nutrients: FoodNutrient[];
	servings: unknown[];
}

export interface Nutrient {
	id: number;
	name: string;
	slug: string;
	unit: string;
	is_energy: boolean;
}

export const EXERCISE_CATEGORIES = [
	{ value: 'barbell', label: 'Barbell' },
	{ value: 'dumbbell', label: 'Dumbbell' },
	{ value: 'machine', label: 'Machine' },
	{ value: 'cable', label: 'Cable' },
	{ value: 'bodyweight', label: 'Bodyweight' },
	{ value: 'smith', label: 'Smith machine' },
	{ value: 'kettlebell', label: 'Kettlebell' },
	{ value: 'banded', label: 'Resistance band' },
	{ value: 'other', label: 'Other' }
];

export const LOAD_TYPES = [
	{ value: 'weight_reps', label: 'Weight × reps' },
	{ value: 'bodyweight_reps', label: 'Bodyweight reps' },
	{ value: 'weighted_bodyweight', label: 'Bodyweight + added weight' },
	{ value: 'duration', label: 'Duration' },
	{ value: 'distance_duration', label: 'Distance + duration' }
];

export const COMPOUND_CLASSES = [
	{ value: 'anabolic', label: 'Anabolic steroid' },
	{ value: 'peptide', label: 'Peptide' },
	{ value: 'sarm', label: 'SARM' },
	{ value: 'ancillary', label: 'Ancillary / pharma' },
	{ value: 'other', label: 'Other' }
];

export const FOOD_UNITS = [
	{ value: 'g', label: 'per 100 g' },
	{ value: 'ml', label: 'per 100 ml' }
];

// Macro nutrients we surface in the food editor (energy is matched via is_energy).
export const MACRO_SLUGS = ['protein', 'carbohydrate', 'fat', 'fiber'];

// ---------------------------------------------------------------------------
// Meal plans: a coach-authored full day of meals the client can import/edit.
// ---------------------------------------------------------------------------
export interface PlanMacros {
	energy: string;
	protein: string;
	carbohydrate: string;
	fat: string;
	fiber: string;
}

export interface MealPlanItem {
	id: number;
	meal: number;
	food: number;
	food_name: string;
	food_brand: string;
	food_unit: string;
	serving: number | null;
	quantity: string;
	order: number;
	grams: string | null;
	macros: PlanMacros;
}

export interface MealPlanMeal {
	id: number;
	plan: number;
	name: string;
	order: number;
	items: MealPlanItem[];
	macros: PlanMacros;
}

export interface MealPlan {
	id: number;
	name: string;
	notes: string;
	meals: MealPlanMeal[];
	macros: PlanMacros;
	created_at: string;
}

// ---------------------------------------------------------------------------
// Client-scoped API surface
// ---------------------------------------------------------------------------
type ApiClient = ReturnType<typeof actingApi>;

function makePlan(c: ApiClient) {
	const q = (s: string) => (s.trim() ? `?q=${encodeURIComponent(s.trim())}` : '');

	return {
		// --- reads: body / nutrition / phases ---
		body: () => c.get<BodyAnalysis>('/analysis/body/'),
		phases: () => c.get<{ results: Phase[] } | Phase[]>('/phases/').then(list),
		targets: () =>
			c.get<{ results: NutritionTarget[] } | NutritionTarget[]>('/nutrition/targets/').then(list),

		// --- reads: training + exercise library ---
		programs: () =>
			c.get<{ results: ProgramBrief[] } | ProgramBrief[]>('/training/programs/').then(list),
		program: (id: number) => c.get<Program>(`/training/programs/${id}/`),
		exercises: (search = '') =>
			c.get<{ results: Exercise[] } | Exercise[]>(`/training/exercises/${q(search)}`).then(list),
		muscles: () => c.get<{ results: Muscle[] } | Muscle[]>('/training/muscles/').then(list),

		// --- reads: protocols + compound/supplement library ---
		protocols: () =>
			c.get<{ results: ProtocolBrief[] } | ProtocolBrief[]>('/protocols/protocols/').then(list),
		protocol: (id: number) => c.get<Protocol>(`/protocols/protocols/${id}/`),
		compounds: (search = '') =>
			c.get<{ results: Compound[] } | Compound[]>(`/protocols/compounds/${q(search)}`).then(list),
		supplements: (search = '') =>
			c.get<{ results: Supplement[] } | Supplement[]>(`/protocols/supplements/${q(search)}`).then(list),

		// --- reads: food library ---
		foods: (search = '') =>
			c.get<{ results: Food[] } | Food[]>(`/nutrition/foods/${q(search)}`).then(list),
		nutrients: () => c.get<{ results: Nutrient[] } | Nutrient[]>('/nutrition/nutrients/').then(list),

		// --- writes: nutrition targets ---
		createTarget: (data: NutritionTargetInput) => c.post<NutritionTarget>('/nutrition/targets/', data),
		updateTarget: (id: number, data: Partial<NutritionTargetInput>) =>
			c.patch<NutritionTarget>(`/nutrition/targets/${id}/`, data),
		activateTarget: (id: number) => c.post<NutritionTarget>(`/nutrition/targets/${id}/activate/`),
		deleteTarget: (id: number) => c.del(`/nutrition/targets/${id}/`),

		// --- writes: phases ---
		createPhase: (data: { name: string; phase_type: string; start_date: string; notes?: string }) =>
			c.post<Phase>('/phases/', data),
		updatePhase: (
			id: number,
			data: Partial<{
				name: string;
				phase_type: string;
				start_date: string;
				end_date: string | null;
				notes: string;
			}>
		) => c.patch<Phase>(`/phases/${id}/`, data),
		deletePhase: (id: number) => c.del(`/phases/${id}/`),

		// --- writes: exercise library ---
		createExercise: (data: Partial<Exercise>) => c.post<Exercise>('/training/exercises/', data),
		updateExercise: (id: number, data: Partial<Exercise>) =>
			c.patch<Exercise>(`/training/exercises/${id}/`, data),
		deleteExercise: (id: number) => c.del(`/training/exercises/${id}/`),

		// --- writes: compound library ---
		createCompound: (data: Partial<Compound>) => c.post<Compound>('/protocols/compounds/', data),
		updateCompound: (id: number, data: Partial<Compound>) =>
			c.patch<Compound>(`/protocols/compounds/${id}/`, data),
		deleteCompound: (id: number) => c.del(`/protocols/compounds/${id}/`),

		// --- writes: supplement library ---
		createSupplement: (data: Partial<Supplement>) =>
			c.post<Supplement>('/protocols/supplements/', data),
		updateSupplement: (id: number, data: Partial<Supplement>) =>
			c.patch<Supplement>(`/protocols/supplements/${id}/`, data),
		deleteSupplement: (id: number) => c.del(`/protocols/supplements/${id}/`),

		// --- writes: food library ---
		createFood: (data: Partial<Food>) => c.post<Food>('/nutrition/foods/', data),
		updateFood: (id: number, data: Partial<Food>) =>
			c.patch<Food>(`/nutrition/foods/${id}/`, data),
		deleteFood: (id: number) => c.del(`/nutrition/foods/${id}/`),

		// --- meal plans (read) ---
		mealPlans: () =>
			c.get<{ results: MealPlan[] } | MealPlan[]>('/nutrition/meal-plans/').then(list),
		mealPlan: (id: number) => c.get<MealPlan>(`/nutrition/meal-plans/${id}/`),

		// --- meal plans (write) ---
		createMealPlan: (data: { name: string; notes?: string }) =>
			c.post<MealPlan>('/nutrition/meal-plans/', data),
		updateMealPlan: (id: number, data: Partial<Pick<MealPlan, 'name' | 'notes'>>) =>
			c.patch<MealPlan>(`/nutrition/meal-plans/${id}/`, data),
		deleteMealPlan: (id: number) => c.del(`/nutrition/meal-plans/${id}/`),
		createPlanMeal: (data: { plan: number; name: string; order: number }) =>
			c.post<MealPlanMeal>('/nutrition/meal-plan-meals/', data),
		updatePlanMeal: (id: number, data: Partial<Pick<MealPlanMeal, 'name' | 'order'>>) =>
			c.patch<MealPlanMeal>(`/nutrition/meal-plan-meals/${id}/`, data),
		deletePlanMeal: (id: number) => c.del(`/nutrition/meal-plan-meals/${id}/`),
		createPlanItem: (data: {
			meal: number;
			food: number;
			quantity: string;
			serving?: number | null;
			order: number;
		}) => c.post<MealPlanItem>('/nutrition/meal-plan-items/', data),
		updatePlanItem: (id: number, data: Partial<Pick<MealPlanItem, 'quantity' | 'serving' | 'order'>>) =>
			c.patch<MealPlanItem>(`/nutrition/meal-plan-items/${id}/`, data),
		deletePlanItem: (id: number) => c.del(`/nutrition/meal-plan-items/${id}/`),

		// --- writes: training tree ---
		createProgram: (data: { name: string; description?: string }) =>
			c.post<Program>('/training/programs/', data),
		activateProgram: (id: number) => c.post<Program>(`/training/programs/${id}/activate/`),
		deleteProgram: (id: number) => c.del(`/training/programs/${id}/`),
		createDay: (data: { program: number; name: string; order: number }) =>
			c.post<TrainingDay>('/training/training-days/', data),
		updateDay: (id: number, data: Partial<Pick<TrainingDay, 'name' | 'notes' | 'order'>>) =>
			c.patch<TrainingDay>(`/training/training-days/${id}/`, data),
		deleteDay: (id: number) => c.del(`/training/training-days/${id}/`),
		createSlot: (data: { day: number; exercise: number; order: number }) =>
			c.post<ExerciseSlot>('/training/exercise-slots/', data),
		deleteSlot: (id: number) => c.del(`/training/exercise-slots/${id}/`),
		createSet: (data: Partial<PlannedSet> & { slot: number }) =>
			c.post<PlannedSet>('/training/planned-sets/', data),
		updateSet: (id: number, data: Partial<PlannedSet>) =>
			c.patch<PlannedSet>(`/training/planned-sets/${id}/`, data),
		deleteSet: (id: number) => c.del(`/training/planned-sets/${id}/`),

		// --- writes: protocol tree ---
		createProtocol: (data: { name: string; started_on?: string }) =>
			c.post<Protocol>('/protocols/protocols/', data),
		activateProtocol: (id: number) => c.post<Protocol>(`/protocols/protocols/${id}/activate/`),
		deleteProtocol: (id: number) => c.del(`/protocols/protocols/${id}/`),
		createItem: (data: Partial<ProtocolItem> & { protocol: number }) =>
			c.post<ProtocolItem>('/protocols/protocol-items/', data),
		updateItem: (id: number, data: Partial<ProtocolItem>) =>
			c.patch<ProtocolItem>(`/protocols/protocol-items/${id}/`, data),
		deleteItem: (id: number) => c.del(`/protocols/protocol-items/${id}/`)
	};
}

/** Coach acting on a specific client (sends X-Acting-Client). */
export function clientPlan(clientId: number) {
	return makePlan(actingApi(clientId));
}

/** Coach acting on their OWN data (no acting header) — used for the template library. */
export function coachPlan() {
	return makePlan(api);
}

export type ClientPlan = ReturnType<typeof makePlan>;

/** Friendly message for the common prescription-write failure. */
export function writeError(e: unknown): string {
	const m = (e as Error).message;
	return m.includes('403') ? "You don't have edit access to this client's plan." : m;
}
