<script lang="ts">
	import { onMount } from 'svelte';
	import { nutritionApi, type Food, type Nutrient } from '$lib/nutrition/api';
	import { kcalFromMacros, num } from '$lib/nutrition/calc';
	import Modal from '$lib/components/ui/Modal.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Button from '$lib/components/ui/Button.svelte';

	// Create a custom food without leaving the page (mirrors the in-context exercise/
	// compound modals). Supports g or ml as the base unit (SI). `oncreated` hands the
	// new food back so the caller can immediately log it.
	let {
		open = $bindable(false),
		oncreated,
		onclose
	}: {
		open?: boolean;
		oncreated: (food: Food) => void;
		onclose?: () => void;
	} = $props();

	let nutrients = $state<Nutrient[]>([]);
	let name = $state('');
	let brand = $state('');
	let unit = $state<'g' | 'ml'>('g');
	let macros = $state<Record<string, string>>({
		energy: '', protein: '', carbohydrate: '', fat: '', fiber: ''
	});
	let saving = $state(false);
	let error = $state<string | null>(null);

	const MACRO_FIELDS: [string, string][] = [
		['energy', 'Calories'],
		['protein', 'Protein'],
		['carbohydrate', 'Carbs'],
		['fat', 'Fat'],
		['fiber', 'Fiber']
	];
	const previewKcal = $derived(
		kcalFromMacros(num(macros.protein), num(macros.carbohydrate), num(macros.fat))
	);

	onMount(async () => {
		nutrients = await nutritionApi.nutrients().catch(() => []);
	});

	const nid = (slug: string) => nutrients.find((n) => n.slug === slug)?.id ?? null;

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (!name.trim()) return;
		saving = true;
		error = null;
		try {
			const food_nutrients = MACRO_FIELDS.map(([s]) => s)
				.filter((s) => macros[s] !== '' && nid(s) != null)
				.map((s) => ({ nutrient: nid(s)!, amount_per_100g: String(num(macros[s])) }));
			const food = await nutritionApi.createFood({
				name: name.trim(),
				brand: brand.trim(),
				unit,
				servings: [{ label: `100 ${unit}`, grams: '100', is_default: true }],
				food_nutrients
			});
			oncreated(food);
			name = brand = '';
			unit = 'g';
			macros = { energy: '', protein: '', carbohydrate: '', fat: '', fiber: '' };
			open = false;
		} catch (err) {
			error = (err as Error).message;
		} finally {
			saving = false;
		}
	}
</script>

<Modal bind:open title="New food" {onclose}>
	<form class="space-y-3" onsubmit={submit}>
		<div class="flex gap-2">
			<Input placeholder="Food name" required bind:value={name} />
			<Input placeholder="Brand (optional)" bind:value={brand} />
		</div>
		<label class="flex items-center gap-2 text-xs text-neutral-500">
			Measured in
			<select bind:value={unit} class="rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100">
				<option value="g">grams (g)</option>
				<option value="ml">millilitres (ml)</option>
			</select>
			<span class="text-neutral-600">— use ml for drinks/liquids</span>
		</label>
		<p class="text-xs text-neutral-500">Nutrition per 100 {unit}:</p>
		<div class="grid grid-cols-2 gap-2 sm:grid-cols-5">
			{#each MACRO_FIELDS as [slug, label] (slug)}
				<label class="flex flex-col text-xs text-neutral-500">
					{label}
					<input type="number" step="0.1" bind:value={macros[slug]} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100" />
				</label>
			{/each}
		</div>
		<p class="text-xs text-neutral-500">Calories from macros: ~{previewKcal} kcal/100{unit}</p>
		{#if error}<p class="text-sm text-red-400">{error}</p>{/if}
		<Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Create custom food'}</Button>
	</form>
</Modal>
