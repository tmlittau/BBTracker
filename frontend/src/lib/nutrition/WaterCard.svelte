<script lang="ts">
	// Fast hydration logging: tap +250 / +500 ml (or a custom amount) against the
	// day's goal. Self-contained — fetches its own entries for the date and manages
	// add/undo so logging feels instant without reloading the whole page.
	import { nutritionApi, type WaterLog } from '$lib/nutrition/api';

	let { date, goalMl = null }: { date: string; goalMl?: number | null } = $props();

	let logs = $state<WaterLog[]>([]);
	let custom = $state('');
	let busy = $state(false);
	let error = $state<string | null>(null);

	const total = $derived(logs.reduce((s, l) => s + l.amount_ml, 0));
	const pct = $derived(goalMl ? Math.min(100, Math.round((total / goalMl) * 100)) : null);
	const QUICK = [250, 500];

	// Refetch whenever the viewed date changes (and on mount).
	$effect(() => {
		const d = date;
		nutritionApi
			.water(d)
			.then((rows) => {
				if (d === date) logs = rows;
			})
			.catch((e) => (error = (e as Error).message));
	});

	async function add(ml: number) {
		if (!ml || ml <= 0 || busy) return;
		busy = true;
		error = null;
		try {
			const row = await nutritionApi.logWater(date, ml);
			logs = [...logs, row];
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	async function addCustom() {
		const ml = Math.round(Number(custom));
		if (!Number.isFinite(ml) || ml <= 0) return;
		await add(ml);
		custom = '';
	}

	async function undo() {
		const last = logs[logs.length - 1];
		if (!last || busy) return;
		busy = true;
		error = null;
		try {
			await nutritionApi.deleteWater(last.id);
			logs = logs.filter((l) => l.id !== last.id);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}
</script>

<section class="mt-6 rounded-lg border border-neutral-800 p-4" data-testid="water-card">
	<div class="flex items-center justify-between">
		<h2 class="font-medium">💧 Water</h2>
		<span class="text-sm tabular-nums text-neutral-300">
			{(total / 1000).toFixed(2)} L
			{#if goalMl}<span class="text-neutral-600">/ {(goalMl / 1000).toFixed(1)} L</span>{/if}
			{#if pct != null}<span class="ml-1 text-xs text-cyan-400">{pct}%</span>{/if}
		</span>
	</div>

	{#if goalMl}
		<div class="mt-2 h-2 w-full overflow-hidden rounded-full bg-neutral-800/60">
			<div class="h-2 rounded-full bg-cyan-500/80 transition-all" style="width: {pct}%"></div>
		</div>
	{/if}

	<div class="mt-3 flex flex-wrap items-center gap-2">
		{#each QUICK as ml (ml)}
			<button
				class="rounded-full border border-cyan-800 px-3 py-1 text-sm text-cyan-300 hover:border-cyan-500 disabled:opacity-40"
				disabled={busy}
				onclick={() => add(ml)}
			>
				+{ml} ml
			</button>
		{/each}
		<div class="flex items-center gap-1">
			<input
				type="number"
				step="10"
				placeholder="ml"
				bind:value={custom}
				onkeydown={(e) => { if (e.key === 'Enter') addCustom(); }}
				class="w-20 rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm text-neutral-100"
			/>
			<button
				class="rounded-full bg-brand px-2.5 py-1 text-sm font-medium text-white hover:brightness-110 disabled:opacity-40"
				disabled={busy}
				onclick={addCustom}
			>
				Add
			</button>
		</div>
		{#if logs.length > 0}
			<button class="ml-auto text-xs text-neutral-500 hover:text-neutral-300" disabled={busy} onclick={undo}>
				Undo last
			</button>
		{/if}
	</div>

	{#if !goalMl}
		<p class="mt-2 text-xs text-neutral-600">
			Set a daily goal in <a class="underline" href="/nutrition/targets">targets</a> to track progress.
		</p>
	{/if}
	{#if error}<p class="mt-2 text-sm text-red-400">{error}</p>{/if}
</section>
