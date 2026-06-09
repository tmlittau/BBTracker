<script lang="ts">
	import { onMount } from 'svelte';
	import { nutritionApi, type BarcodeLookup, type Food, type Nutrient } from '$lib/nutrition/api';
	import { kcalFromMacros, num } from '$lib/nutrition/calc';
	import Modal from '$lib/components/ui/Modal.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Button from '$lib/components/ui/Button.svelte';

	// Create OR edit a custom food. `prefill` (from a barcode lookup) and `edit`
	// (an existing food) both populate the form so the user confirms before saving.
	let {
		open = $bindable(false),
		oncreated,
		onupdated,
		onclose,
		prefill = null,
		edit = null
	}: {
		open?: boolean;
		oncreated?: (food: Food) => void;
		onupdated?: (food: Food) => void;
		onclose?: () => void;
		prefill?: BarcodeLookup | null;
		edit?: Food | null;
	} = $props();

	let nutrients = $state<Nutrient[]>([]);
	let name = $state('');
	let brand = $state('');
	let unit = $state<'g' | 'ml'>('g');
	let barcode = $state('');
	let macros = $state<Record<string, string>>({
		energy: '', protein: '', carbohydrate: '', fat: '', fiber: ''
	});
	let micros = $state<Record<string, string>>({});
	let showMicros = $state(false);
	let saving = $state(false);
	let error = $state<string | null>(null);

	const MACRO_FIELDS: [string, string][] = [
		['energy', 'Calories'],
		['protein', 'Protein'],
		['carbohydrate', 'Carbs'],
		['fat', 'Fat'],
		['fiber', 'Fiber']
	];
	const MACRO_SLUGS = new Set(MACRO_FIELDS.map(([s]) => s));
	const microNutrients = $derived(
		[...nutrients]
			.filter((n) => !MACRO_SLUGS.has(n.slug))
			.sort((a, b) => a.display_order - b.display_order)
	);

	const previewKcal = $derived(
		kcalFromMacros(num(macros.protein), num(macros.carbohydrate), num(macros.fat))
	);

	onMount(async () => {
		nutrients = await nutritionApi.nutrients().catch(() => []);
	});

	const nid = (slug: string) => nutrients.find((n) => n.slug === slug)?.id ?? null;

	function reset() {
		name = brand = barcode = '';
		unit = 'g';
		macros = { energy: '', protein: '', carbohydrate: '', fat: '', fiber: '' };
		micros = {};
		showMicros = false;
	}

	function loadNutrients(bySlug: Record<string, string>) {
		macros = {
			energy: bySlug.energy ?? '',
			protein: bySlug.protein ?? '',
			carbohydrate: bySlug.carbohydrate ?? '',
			fat: bySlug.fat ?? '',
			fiber: bySlug.fiber ?? ''
		};
		const m: Record<string, string> = {};
		for (const [slug, amt] of Object.entries(bySlug)) {
			if (!MACRO_SLUGS.has(slug)) m[slug] = amt;
		}
		micros = m;
		if (Object.keys(m).length) showMicros = true;
	}

	// Populate from a barcode draft or an existing food when the modal opens.
	let lastSource: BarcodeLookup | Food | null = null;
	$effect(() => {
		const source = edit ?? prefill;
		if (open && source && source !== lastSource) {
			lastSource = source;
			if (edit) {
				name = edit.name;
				brand = edit.brand;
				unit = (edit.unit as 'g' | 'ml') ?? 'g';
				barcode = edit.barcode ?? '';
				loadNutrients(Object.fromEntries(edit.food_nutrients.map((fn) => [fn.slug, fn.amount_per_100g])));
			} else if (prefill) {
				name = prefill.name ?? '';
				brand = prefill.brand ?? '';
				unit = prefill.unit ?? 'g';
				barcode = prefill.barcode ?? '';
				loadNutrients(prefill.nutrients ?? {});
			}
		}
		if (!open) lastSource = null;
	});

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		if (!name.trim()) return;
		saving = true;
		error = null;
		try {
			const entries: [string, string][] = [
				...MACRO_FIELDS.map(([s]) => [s, macros[s]] as [string, string]),
				...Object.entries(micros)
			];
			const food_nutrients = entries
				.filter(([slug, v]) => v !== '' && v != null && nid(slug) != null)
				.map(([slug, v]) => ({ nutrient: nid(slug)!, amount_per_100g: String(num(v)) }));
			const payload = {
				name: name.trim(),
				brand: brand.trim(),
				unit,
				barcode: barcode.trim() || undefined,
				servings: [{ label: `100 ${unit}`, grams: '100', is_default: true }],
				food_nutrients
			};
			if (edit) {
				onupdated?.(await nutritionApi.updateFood(edit.id, payload));
			} else {
				oncreated?.(await nutritionApi.createFood(payload));
			}
			reset();
			open = false;
		} catch (err) {
			error = (err as Error).message;
		} finally {
			saving = false;
		}
	}
</script>

<Modal bind:open title={edit ? 'Edit food' : 'New food'} {onclose}>
	<form class="space-y-3" onsubmit={submit}>
		<div class="flex gap-2">
			<Input placeholder="Food name" required bind:value={name} />
			<Input placeholder="Brand (optional)" bind:value={brand} />
		</div>
		{#if barcode}
			<p class="text-xs text-neutral-500">Barcode: <span class="font-mono text-neutral-300">{barcode}</span></p>
		{/if}
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

		<details class="rounded border border-neutral-800" bind:open={showMicros}>
			<summary class="cursor-pointer select-none px-3 py-2 text-sm text-neutral-300">
				Micronutrients (optional)
			</summary>
			<div class="border-t border-neutral-800 p-3">
				{#if microNutrients.length === 0}
					<p class="text-xs text-neutral-500">Loading…</p>
				{:else}
					<div class="grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-3">
						{#each microNutrients as n (n.id)}
							<label class="flex flex-col text-xs text-neutral-500">
								<span class="truncate">{n.name} <span class="text-neutral-600">({n.unit})</span></span>
								<input type="number" step="0.001" bind:value={micros[n.slug]} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100" />
							</label>
						{/each}
					</div>
					<p class="mt-2 text-xs text-neutral-600">Per 100 {unit}. Leave blank if unknown.</p>
				{/if}
			</div>
		</details>

		{#if error}<p class="text-sm text-red-400">{error}</p>{/if}
		<Button type="submit" disabled={saving}>
			{saving ? 'Saving…' : edit ? 'Save changes' : 'Create custom food'}
		</Button>
	</form>
</Modal>
