<script lang="ts">
	import { onMount } from 'svelte';
	import { nutritionApi, type BarcodeLookup, type Food } from '$lib/nutrition/api';
	import { num } from '$lib/nutrition/calc';
	import Button from '$lib/components/ui/Button.svelte';
	import FoodCreateModal from '$lib/nutrition/FoodCreateModal.svelte';
	import BarcodeScannerModal from '$lib/nutrition/BarcodeScannerModal.svelte';

	let foods = $state<Food[]>([]);
	let query = $state('');
	let loading = $state(true);
	let error = $state<string | null>(null);

	// Barcode import ("Scan / add by barcode").
	let showBarcode = $state(false);
	let barcode = $state('');
	let importing = $state(false);
	let importMsg = $state<string | null>(null);
	let importErr = $state<string | null>(null);
	let scanSupported = $state(false); // browser camera (getUserMedia) available
	let showScanner = $state(false);

	let showFoodModal = $state(false);
	let barcodePrefill = $state<BarcodeLookup | null>(null);
	let editingFood = $state<Food | null>(null);

	async function load() {
		loading = true;
		try {
			foods = await nutritionApi.foods(query.trim());
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	function friendly(err: unknown): string {
		const msg = (err as Error)?.message ?? String(err);
		const i = msg.indexOf('{');
		if (i >= 0) {
			try {
				const body = JSON.parse(msg.slice(i));
				if (body?.detail) return body.detail as string;
			} catch {
				/* not JSON — fall through */
			}
		}
		return msg;
	}

	// Look the barcode up (without saving) and open the New Food form prefilled, so
	// the pulled values can be confirmed/edited before the food is created.
	async function lookup(code: string) {
		if (!code) return;
		importing = true;
		importMsg = null;
		importErr = null;
		try {
			editingFood = null;
			barcodePrefill = await nutritionApi.lookupBarcode(code);
			showFoodModal = true;
			showBarcode = false;
			barcode = '';
		} catch (err) {
			importErr = friendly(err);
		} finally {
			importing = false;
		}
	}

	async function importByBarcode(e: SubmitEvent) {
		e.preventDefault();
		await lookup(barcode.trim());
	}

	// Camera scan result → look it up and prefill the New Food form.
	function onScanResult(code: string) {
		lookup(code);
	}

	onMount(() => {
		load();
		scanSupported = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;
	});

	let timer: ReturnType<typeof setTimeout>;
	function onSearch() {
		clearTimeout(timer);
		timer = setTimeout(load, 200);
	}

	function onCreated(food: Food) {
		foods = [food, ...foods];
		barcodePrefill = null;
		importMsg = `Saved “${food.name}”${food.brand ? ` · ${food.brand}` : ''}.`;
	}
	function onUpdated(food: Food) {
		foods = foods.map((f) => (f.id === food.id ? food : f));
		editingFood = null;
	}
	function startEdit(food: Food) {
		barcodePrefill = null;
		editingFood = food;
		showFoodModal = true;
	}

	async function remove(id: number) {
		if (!confirm('Delete this custom food?')) return;
		await nutritionApi.deleteFood(id);
		await load();
	}

	function kcalOf(food: Food): string {
		const e = food.food_nutrients.find((n) => n.slug === 'energy');
		return e ? `${num(e.amount_per_100g).toFixed(0)} kcal/100${food.unit}` : '';
	}
</script>

<FoodCreateModal
	bind:open={showFoodModal}
	oncreated={onCreated}
	onupdated={onUpdated}
	prefill={barcodePrefill}
	edit={editingFood}
	onclose={() => { barcodePrefill = null; editingFood = null; }}
/>
<BarcodeScannerModal bind:open={showScanner} onresult={onScanResult} />

<div class="flex items-center justify-between">
	<h1 class="text-xl font-semibold">Food library</h1>
	<div class="flex gap-2">
		<button
			class="rounded-md border border-neutral-700 px-4 py-2 text-sm hover:border-neutral-500"
			onclick={() => (showBarcode = !showBarcode)}
		>
			{showBarcode ? 'Cancel' : 'Scan / add by barcode'}
		</button>
		<button
			class="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
			onclick={() => { barcodePrefill = null; editingFood = null; showFoodModal = true; }}
		>
			New food
		</button>
	</div>
</div>

{#if showBarcode}
	<form class="mt-4 space-y-3 rounded-lg border border-neutral-800 p-4" onsubmit={importByBarcode}>
		<p class="text-sm text-neutral-300">Add a branded food by its barcode</p>
		<p class="text-xs text-neutral-500">
			Enter the UPC/EAN (the digits under the barcode), or scan it. We’ll look it up on Open Food
			Facts and prefill the New Food form so you can review it before saving.
		</p>
		<div class="flex gap-2">
			{#if scanSupported}
				<button
					type="button"
					onclick={() => (showScanner = true)}
					disabled={importing}
					class="shrink-0 rounded border border-emerald-700 px-3 py-2 text-sm text-emerald-300 hover:border-emerald-500 disabled:opacity-50"
				>
					📷 Scan
				</button>
			{/if}
			<input
				name="barcode"
				inputmode="numeric"
				autocomplete="off"
				placeholder="e.g. 3017620422003"
				bind:value={barcode}
				class="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-emerald-500"
			/>
			<Button type="submit" disabled={importing || !barcode.trim()}>
				{importing ? 'Looking up…' : 'Look up'}
			</Button>
		</div>
		{#if importErr}<p class="text-sm text-red-400">{importErr}</p>{/if}
		{#if importMsg}<p class="text-sm text-green-400">{importMsg}</p>{/if}
	</form>
{/if}

<div class="mt-4">
	<input
		placeholder="Search foods…"
		bind:value={query}
		oninput={onSearch}
		class="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100 outline-none focus:border-emerald-500"
	/>
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else}
	<p class="mt-4 text-xs text-neutral-500">{foods.length} food(s)</p>
	<ul class="mt-2 divide-y divide-neutral-800">
		{#each foods as food (food.id)}
			<li class="flex items-center justify-between py-3">
				<div>
					<span class="font-medium">{food.name}</span>
					{#if food.brand}<span class="text-neutral-500"> · {food.brand}</span>{/if}
					{#if food.unit === 'ml'}<span class="ml-2 rounded bg-sky-900 px-1.5 py-0.5 text-xs text-sky-300">liquid</span>{/if}
					{#if !food.is_global}
						<span class="ml-2 rounded bg-emerald-900 px-1.5 py-0.5 text-xs text-emerald-300">Custom</span>
					{/if}
					<div class="text-xs text-neutral-500">{kcalOf(food)}</div>
				</div>
				{#if !food.is_global}
					<div class="flex shrink-0 items-center gap-3 text-xs">
						<button class="text-indigo-400 hover:text-indigo-300" onclick={() => startEdit(food)}>Edit</button>
						<button class="text-red-400 hover:text-red-300" onclick={() => remove(food.id)}>Delete</button>
					</div>
				{/if}
			</li>
		{/each}
	</ul>
{/if}
