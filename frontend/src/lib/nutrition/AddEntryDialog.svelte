<script lang="ts">
	import { num } from './calc';
	import type { Food } from './api';
	import Modal from '$lib/components/ui/Modal.svelte';

	let {
		food,
		meal,
		onconfirm,
		oncancel
	}: {
		food: Food;
		meal: string;
		onconfirm: (data: { serving: number | null; quantity: string }) => void;
		oncancel: () => void;
	} = $props();

	// Mounted only while a food is pending, so it opens immediately.
	let open = $state(true);

	const defaultServing = $derived(food.servings.find((s) => s.is_default) ?? food.servings[0]);
	let servingId = $state<number | null>(defaultServing ? defaultServing.id : null);
	let quantity = $state('1');

	// Resolve grams for the live preview: quantity × serving grams, or quantity as grams.
	const grams = $derived.by(() => {
		const q = num(quantity);
		if (servingId == null) return q;
		const s = food.servings.find((x) => x.id === servingId);
		return s ? q * num(s.grams) : q;
	});

	function energyPer100() {
		const e = food.food_nutrients.find((n) => n.slug === 'energy');
		return e ? num(e.amount_per_100g) : 0;
	}
	const previewKcal = $derived(Math.round((energyPer100() * grams) / 100));

	function add() {
		open = false;
		onconfirm({ serving: servingId, quantity });
	}
</script>

<Modal bind:open title={food.name} size="sm" onclose={oncancel}>
	{#if food.brand}<p class="-mt-2 text-sm text-neutral-500">{food.brand}</p>{/if}
	<p class="mt-1 text-xs text-neutral-500">Adding to {meal}</p>

	<div class="mt-4 flex gap-2">
		<label class="flex flex-1 flex-col text-xs text-neutral-500">
			Quantity
			<input
				type="number"
				step="0.25"
				min="0"
				inputmode="decimal"
				bind:value={quantity}
				class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100"
			/>
		</label>
		<label class="flex flex-[2] flex-col text-xs text-neutral-500">
			Serving
			<select
				bind:value={servingId}
				class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100"
			>
				{#each food.servings as s (s.id)}
					<option value={s.id}>{s.label}</option>
				{/each}
				<option value={null}>{food.unit === 'ml' ? 'millilitres' : 'grams'}</option>
			</select>
		</label>
	</div>

	<p class="mt-3 text-sm text-neutral-400">
		≈ {grams.toFixed(0)} {food.unit} · {previewKcal} kcal
	</p>

	<div class="mt-5 flex justify-end gap-2">
		<button
			class="rounded-md border border-neutral-700 px-4 py-2 text-sm hover:border-neutral-500"
			onclick={() => {
				open = false;
				oncancel();
			}}
		>
			Cancel
		</button>
		<button
			class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
			onclick={add}
		>
			Add
		</button>
	</div>
</Modal>
