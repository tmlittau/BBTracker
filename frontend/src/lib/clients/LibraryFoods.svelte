<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { clientPlan, writeError, FOOD_UNITS, type Food, type Nutrient, type FoodNutrient } from './plan';
	import { CLIENT_CTX, type ClientContext } from './context';

	let { clientId }: { clientId: number } = $props();
	const plan = $derived(clientPlan(clientId));
	const ctx = getContext<ClientContext>(CLIENT_CTX);
	const canEdit = $derived(ctx?.canEdit ?? false);

	// Macros we expose in the editor, matched to seeded nutrients by slug.
	const MACROS = [
		{ slug: 'energy', label: 'Calories' },
		{ slug: 'protein', label: 'Protein (g)' },
		{ slug: 'carbohydrate', label: 'Carbs (g)' },
		{ slug: 'fat', label: 'Fat (g)' },
		{ slug: 'fiber', label: 'Fiber (g)' }
	];

	let all = $state<Food[]>([]);
	let nutrients = $state<Nutrient[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let busy = $state(false);
	let search = $state('');

	const custom = $derived(
		all.filter((f) => !f.is_global).filter((f) => f.name.toLowerCase().includes(search.trim().toLowerCase()))
	);
	const globalCount = $derived(all.filter((f) => f.is_global).length);

	type Draft = { name: string; brand: string; unit: string; amounts: Record<string, string> };
	const emptyDraft = (): Draft => ({
		name: '',
		brand: '',
		unit: 'g',
		amounts: Object.fromEntries(MACROS.map((m) => [m.slug, '']))
	});
	const fromItem = (f: Food): Draft => {
		const amounts = Object.fromEntries(MACROS.map((m) => [m.slug, '']));
		for (const fn of f.food_nutrients ?? []) {
			if (fn.slug && fn.slug in amounts) amounts[fn.slug] = fn.amount_per_100g ?? '';
		}
		return { name: f.name, brand: f.brand, unit: f.unit || 'g', amounts };
	};

	let adding = $state(false);
	let editingId = $state<number | null>(null);
	let draft = $state<Draft>(emptyDraft());

	const nutrientId = (slug: string) => nutrients.find((n) => n.slug === slug)?.id;
	const energy = $derived(Number(draft.amounts['energy']) || 0);
	const macroKcal = $derived(
		Math.round(
			(Number(draft.amounts['protein']) || 0) * 4 +
				(Number(draft.amounts['carbohydrate']) || 0) * 4 +
				(Number(draft.amounts['fat']) || 0) * 9
		)
	);
	const mismatch = $derived(draft.amounts['energy'].trim() !== '' && Math.abs(macroKcal - energy) > 15);

	async function load() {
		loading = true;
		error = null;
		try {
			const [foods, nuts] = await Promise.all([
				plan.foods(),
				nutrients.length ? Promise.resolve(nutrients) : plan.nutrients()
			]);
			all = foods;
			nutrients = nuts;
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}
	onMount(load);

	function openAdd() {
		editingId = null;
		draft = emptyDraft();
		adding = true;
	}
	function openEdit(f: Food) {
		adding = false;
		editingId = f.id;
		draft = fromItem(f);
	}
	function cancel() {
		adding = false;
		editingId = null;
	}

	async function save() {
		if (!draft.name.trim()) return;
		busy = true;
		error = null;
		try {
			const food_nutrients: FoodNutrient[] = [];
			for (const m of MACROS) {
				const v = draft.amounts[m.slug].trim();
				const id = nutrientId(m.slug);
				if (v !== '' && id != null) food_nutrients.push({ nutrient: id, amount_per_100g: v });
			}
			const body = { name: draft.name.trim(), brand: draft.brand.trim(), unit: draft.unit, food_nutrients };
			if (editingId != null) await plan.updateFood(editingId, body);
			else await plan.createFood(body);
			cancel();
			await load();
		} catch (e) {
			error = writeError(e);
		} finally {
			busy = false;
		}
	}

	async function remove(f: Food) {
		if (!confirm(`Delete food “${f.name}”?`)) return;
		error = null;
		try {
			await plan.deleteFood(f.id);
			await load();
		} catch (e) {
			error = writeError(e);
		}
	}

	const kcalOf = (f: Food) => f.food_nutrients?.find((n) => n.slug === 'energy')?.amount_per_100g;
</script>

{#snippet fields()}
	<div class="mt-2 space-y-3 rounded-md border border-neutral-800 bg-neutral-950 p-3">
		<div class="flex flex-wrap gap-2">
			<label class="flex flex-[2] flex-col text-xs text-neutral-500">
				Name
				<input bind:value={draft.name} placeholder="e.g. Greek Yogurt 0%" class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100" />
			</label>
			<label class="flex flex-1 flex-col text-xs text-neutral-500">
				Brand
				<input bind:value={draft.brand} placeholder="optional" class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100" />
			</label>
			<label class="flex flex-col text-xs text-neutral-500">
				Basis
				<select bind:value={draft.unit} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100">
					{#each FOOD_UNITS as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
				</select>
			</label>
		</div>
		<div class="grid grid-cols-2 gap-2 sm:grid-cols-5">
			{#each MACROS as m (m.slug)}
				<label class="flex flex-col text-xs text-neutral-500">
					{m.label}
					<input type="number" step="0.1" bind:value={draft.amounts[m.slug]} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100" />
				</label>
			{/each}
		</div>
		<p class="text-xs {mismatch ? 'text-amber-400' : 'text-neutral-500'}">
			Per 100 {draft.unit} · macros ≈ {macroKcal} kcal{mismatch ? ` — differs from ${energy} kcal entered` : ''}
		</p>
		<div class="flex items-center gap-2">
			<button onclick={save} disabled={busy || !draft.name.trim()} class="rounded-full bg-brand px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-40">
				{editingId != null ? 'Save food' : 'Create food'}
			</button>
			<button onclick={cancel} class="text-sm text-neutral-400 hover:text-neutral-200">Cancel</button>
		</div>
	</div>
{/snippet}

{#if error}<p class="text-sm text-red-400">{error}</p>{/if}
{#if loading}
	<p class="text-sm text-neutral-400">Loading…</p>
{:else}
	<div class="flex items-center justify-between gap-3">
		<input placeholder="Filter custom foods…" bind:value={search} class="w-64 rounded border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-100" />
		<span class="text-xs text-neutral-600">{globalCount} global foods available</span>
	</div>

	<div class="mt-3 max-w-2xl space-y-2">
		{#each custom as f (f.id)}
			<div class="rounded-lg border border-neutral-800">
				<div class="flex items-center justify-between px-3 py-2">
					<div>
						<span class="font-medium">{f.brand ? `${f.brand} · ` : ''}{f.name}</span>
						<div class="mt-0.5 text-xs text-neutral-500">
							{kcalOf(f) ? `${Math.round(Number(kcalOf(f)))} kcal` : '—'} / 100 {f.unit}
						</div>
					</div>
					{#if canEdit}
						<div class="flex shrink-0 items-center gap-2 text-xs">
							<button onclick={() => openEdit(f)} class="text-orange-400 hover:text-orange-300">Edit</button>
							<button onclick={() => remove(f)} class="text-neutral-600 hover:text-red-300">✕</button>
						</div>
					{/if}
				</div>
				{#if editingId === f.id}<div class="px-3 pb-3">{@render fields()}</div>{/if}
			</div>
		{:else}
			<p class="text-sm text-neutral-500">No custom foods yet.</p>
		{/each}
	</div>

	{#if canEdit}
		{#if adding}
			<div class="mt-3 max-w-2xl">{@render fields()}</div>
		{:else}
			<button onclick={openAdd} class="mt-3 rounded-full border border-neutral-700 px-4 py-1.5 text-sm text-neutral-200 hover:bg-neutral-900">＋ New food</button>
		{/if}
	{/if}
{/if}
