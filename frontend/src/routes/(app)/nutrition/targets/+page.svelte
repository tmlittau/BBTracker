<script lang="ts">
	import { onMount } from 'svelte';
	import { nutritionApi, type NutritionTarget, type Nutrient } from '$lib/nutrition/api';
	import { kcalFromMacros, num } from '$lib/nutrition/calc';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Card from '$lib/components/ui/Card.svelte';

	let targets = $state<NutritionTarget[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	let editing = $state<NutritionTarget | null>(null);
	let name = $state('');
	// Numeric goals in a Record so the template can bind to a dynamic key.
	const GOAL_FIELDS: [string, string][] = [
		['calories', 'Calories'],
		['protein_g', 'Protein'],
		['carb_g', 'Carbs'],
		['fat_g', 'Fat'],
		['fiber_g', 'Fiber']
	];
	let goals = $state<Record<string, string>>({
		calories: '', protein_g: '', carb_g: '', fat_g: '', fiber_g: ''
	});
	let saving = $state(false);

	// Optional per-micronutrient min/max ranges, hidden behind a checkbox.
	let micros = $state<Nutrient[]>([]);
	let customizeMicros = $state(false);
	let microGoals = $state<Record<number, { min: string; max: string }>>({});

	const macroKcal = $derived(kcalFromMacros(num(goals.protein_g), num(goals.carb_g), num(goals.fat_g)));

	function blankMicroGoals(): Record<number, { min: string; max: string }> {
		return Object.fromEntries(micros.map((m) => [m.id, { min: '', max: '' }]));
	}

	async function load() {
		targets = await nutritionApi.targets();
	}

	onMount(async () => {
		try {
			const [, nutrients] = await Promise.all([load(), nutritionApi.nutrients()]);
			micros = nutrients
				.filter((n) => n.category === 'vitamin' || n.category === 'mineral')
				.sort((a, b) => a.display_order - b.display_order);
			microGoals = blankMicroGoals();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	function reset() {
		editing = null;
		name = '';
		goals = { calories: '', protein_g: '', carb_g: '', fat_g: '', fiber_g: '' };
		customizeMicros = false;
		microGoals = blankMicroGoals();
	}

	function edit(t: NutritionTarget) {
		editing = t;
		name = t.name;
		goals = {
			calories: t.calories ?? '',
			protein_g: t.protein_g ?? '',
			carb_g: t.carb_g ?? '',
			fat_g: t.fat_g ?? '',
			fiber_g: t.fiber_g ?? ''
		};
		const mg = blankMicroGoals();
		for (const nt of t.nutrient_targets) {
			if (mg[nt.nutrient]) mg[nt.nutrient] = { min: nt.min_amount ?? '', max: nt.max_amount ?? '' };
		}
		microGoals = mg;
		customizeMicros = t.nutrient_targets.length > 0;
	}

	function payload() {
		const dec = (v: string) => (v === '' ? null : String(num(v)));
		const bound = (v: string) => (v.trim() === '' ? null : String(num(v)));
		const nutrient_targets = customizeMicros
			? micros
					.filter((m) => microGoals[m.id]?.min.trim() !== '' || microGoals[m.id]?.max.trim() !== '')
					.map((m) => ({
						nutrient: m.id,
						min_amount: bound(microGoals[m.id].min),
						max_amount: bound(microGoals[m.id].max)
					}))
			: [];
		return {
			name: name.trim() || 'Daily target',
			calories: dec(goals.calories),
			protein_g: dec(goals.protein_g),
			carb_g: dec(goals.carb_g),
			fat_g: dec(goals.fat_g),
			fiber_g: dec(goals.fiber_g),
			nutrient_targets
		};
	}

	async function save(e: SubmitEvent) {
		e.preventDefault();
		saving = true;
		error = null;
		try {
			if (editing) {
				await nutritionApi.updateTarget(editing.id, payload());
			} else {
				await nutritionApi.createTarget(payload());
			}
			reset();
			await load();
		} catch (err) {
			error = (err as Error).message;
		} finally {
			saving = false;
		}
	}

	async function activate(id: number) {
		await nutritionApi.activateTarget(id);
		await load();
	}
</script>

<h1 class="text-xl font-semibold">Nutrition targets</h1>
<p class="mt-1 text-sm text-neutral-400">Your active target drives the diary's progress bars.</p>

<form class="mt-4 space-y-3 rounded-lg border border-neutral-800 p-4" onsubmit={save}>
	<h2 class="text-sm font-medium">{editing ? `Edit “${editing.name}”` : 'New target'}</h2>
	<Input placeholder="Name (e.g. Cut, Maintenance)" bind:value={name} />
	<div class="grid grid-cols-2 gap-2 sm:grid-cols-5">
		{#each GOAL_FIELDS as [key, label] (key)}
			<label class="flex flex-col text-xs text-neutral-500">
				{label}
				<input name={key} type="number" step="0.1" bind:value={goals[key]} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100" />
			</label>
		{/each}
	</div>
	<p class="text-xs text-neutral-500">
		Calories implied by macros: ~{macroKcal} kcal
		{#if goals.calories && Math.abs(macroKcal - num(goals.calories)) > 50}
			<span class="text-amber-400">(differs from your {num(goals.calories)} kcal goal)</span>
		{/if}
	</p>

	<label class="flex items-center gap-2 border-t border-neutral-800 pt-3 text-sm text-neutral-300">
		<input type="checkbox" bind:checked={customizeMicros} class="accent-orange-500" />
		Set custom micronutrient targets
	</label>
	{#if customizeMicros}
		<div class="space-y-2 rounded-md border border-neutral-800 bg-neutral-900/40 p-3">
			<p class="text-xs text-neutral-500">
				Leave a row blank to keep the RDA default. <strong>Min</strong> is the daily floor;
				<strong>Max</strong> is a ceiling — intake above it is flagged. Useful for the higher
				needs of a hard-training or enhanced lifter, and to cap nutrients that can be toxic in excess.
			</p>
			<div class="grid grid-cols-[1fr_5rem_5rem] gap-2 text-[10px] font-medium uppercase tracking-wide text-neutral-600">
				<span>Nutrient</span><span>Min</span><span>Max</span>
			</div>
			{#each micros as m (m.id)}
				<div class="grid grid-cols-[1fr_5rem_5rem] items-center gap-2">
					<span class="text-xs text-neutral-300">{m.name} <span class="text-neutral-600">({m.unit})</span></span>
					<input type="number" step="0.01" min="0" placeholder={m.rda ?? 'min'} bind:value={microGoals[m.id].min} class="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm text-neutral-100" />
					<input type="number" step="0.01" min="0" placeholder="—" bind:value={microGoals[m.id].max} class="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm text-neutral-100" />
				</div>
			{/each}
		</div>
	{/if}
	{#if error}<p class="text-sm text-red-400">{error}</p>{/if}
	<div class="flex gap-2">
		<Button type="submit" disabled={saving}>{saving ? 'Saving…' : editing ? 'Save changes' : 'Create target'}</Button>
		{#if editing}
			<button type="button" class="rounded-md border border-neutral-700 px-4 py-2 text-sm hover:border-neutral-500" onclick={reset}>
				Cancel edit
			</button>
		{/if}
	</div>
</form>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if targets.length === 0}
	<p class="mt-6 text-neutral-500">No targets yet — create your first above.</p>
{:else}
	<div class="mt-6 space-y-3">
		{#each targets as t (t.id)}
			<Card>
				<div class="flex items-center justify-between">
					<div>
						<span class="font-medium">{t.name}</span>
						{#if t.is_active}
							<span class="ml-2 rounded bg-green-900 px-2 py-0.5 text-xs text-green-300">Active</span>
						{/if}
						<div class="mt-1 text-xs text-neutral-500">
							{t.calories ?? '—'} kcal · {t.protein_g ?? '—'}P / {t.carb_g ?? '—'}C / {t.fat_g ?? '—'}F
							{#if t.nutrient_targets.length > 0}
								· <span class="text-orange-400">{t.nutrient_targets.length} custom micro{t.nutrient_targets.length > 1 ? 's' : ''}</span>
							{/if}
						</div>
					</div>
					<div class="flex items-center gap-3 text-sm">
						{#if !t.is_active}
							<button class="text-neutral-400 hover:text-white" onclick={() => activate(t.id)}>Set active</button>
						{/if}
						<button class="text-orange-400 hover:text-orange-300" onclick={() => edit(t)}>Edit</button>
					</div>
				</div>
			</Card>
		{/each}
	</div>
{/if}
