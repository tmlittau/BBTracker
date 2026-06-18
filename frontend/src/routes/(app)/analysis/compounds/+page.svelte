<script lang="ts">
	import { onMount } from 'svelte';
	import {
		protocolsApi,
		COMPOUND_CLASSES,
		FREQUENCIES,
		type Compound,
		type CompoundPlot,
		type PlotItemInput
	} from '$lib/protocols/api';
	import SearchSelect from '$lib/components/ui/SearchSelect.svelte';
	import CompoundPlotChart from '$lib/protocols/CompoundPlotChart.svelte';

	interface Row {
		id: number;
		compound: number | null;
		dose: string;
		unit: string;
		frequency: string;
		startWeek: string;
		weeks: string;
	}
	let nextId = 1;
	const newRow = (): Row => ({
		id: nextId++,
		compound: null,
		dose: '',
		unit: 'mg',
		frequency: 'weekly',
		startWeek: '0',
		weeks: '12'
	});

	let compounds = $state<Compound[]>([]);
	let rows = $state<Row[]>([newRow()]);
	let horizonWeeks = $state('16');
	let plot = $state<CompoundPlot | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	const exOptions = $derived(
		compounds.map((c) => ({
			id: c.id,
			label: c.name,
			group: c.compound_class,
			badge: c.ester || undefined
		}))
	);
	const compoundById = $derived(new Map(compounds.map((c) => [c.id, c])));

	onMount(async () => {
		try {
			compounds = await protocolsApi.compounds();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	function addRow() {
		rows = [...rows, newRow()];
	}
	function removeRow(id: number) {
		rows = rows.filter((r) => r.id !== id);
	}
	function onPick(row: Row, id: number) {
		row.compound = id;
		const c = compoundById.get(id);
		if (c) row.unit = c.default_unit; // prefill the compound's usual unit
	}

	const UNITS = ['mg', 'mcg', 'iu'];

	const items = $derived(
		rows
			.filter((r) => r.compound != null && r.dose !== '' && Number(r.dose) > 0)
			.map(
				(r): PlotItemInput => ({
					compound: r.compound as number,
					dose_amount: Number(r.dose),
					dose_unit: r.unit,
					frequency: r.frequency,
					start_day: Math.max(0, Math.round(Number(r.startWeek) || 0)) * 7,
					duration_days: Math.max(1, Math.round(Number(r.weeks) || 1)) * 7
				})
			)
	);
	const horizonDays = $derived(Math.max(1, Math.round(Number(horizonWeeks) || 16)) * 7);

	// Auto-plot (debounced) whenever the inputs change.
	let timer: ReturnType<typeof setTimeout>;
	$effect(() => {
		const payload = JSON.stringify({ horizon_days: horizonDays, items });
		clearTimeout(timer);
		if (items.length === 0) {
			plot = null;
			return;
		}
		timer = setTimeout(async () => {
			try {
				plot = await protocolsApi.plot(JSON.parse(payload));
				error = null;
			} catch (e) {
				error = (e as Error).message;
			}
		}, 250);
	});

	const fieldClass =
		'rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100';
</script>

<p class="rounded-md border border-amber-900/60 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
	A planning estimate of relative active serum levels — informational, not medical advice. Curves use
	a one-compartment (Bateman) model with literature half-life / Tmax / bioavailability; individuals
	vary widely.
</p>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else}
	{#if error}<p class="mt-4 text-sm text-red-400">{error}</p>{/if}

	<!-- Plan rows -->
	<div class="mt-4 space-y-3">
		{#each rows as row, i (row.id)}
			<div class="rounded-lg border border-neutral-800 p-3">
				<div class="flex items-center justify-between gap-2">
					<span class="text-xs text-neutral-500">Compound {i + 1}</span>
					<button class="text-xs text-red-400 hover:text-red-300" onclick={() => removeRow(row.id)}>
						Remove
					</button>
				</div>
				<div class="mt-2">
					<SearchSelect
						options={exOptions}
						groups={COMPOUND_CLASSES}
						placeholder="Choose compound…"
						value={row.compound}
						onchange={(id) => onPick(row, id)}
					/>
				</div>
				<div class="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-5">
					<label class="flex flex-col text-xs text-neutral-500"
						>Dose
						<input type="number" step="0.5" min="0" bind:value={row.dose} class="mt-1 {fieldClass}" />
					</label>
					<label class="flex flex-col text-xs text-neutral-500"
						>Unit
						<select bind:value={row.unit} class="mt-1 {fieldClass}">
							{#each UNITS as u (u)}<option value={u}>{u}</option>{/each}
						</select>
					</label>
					<label class="flex flex-col text-xs text-neutral-500"
						>Frequency
						<select bind:value={row.frequency} class="mt-1 {fieldClass}">
							{#each FREQUENCIES.filter((f) => f.key !== 'specific_days' && f.key !== 'prn') as f (f.key)}
								<option value={f.key}>{f.label}</option>
							{/each}
						</select>
					</label>
					<label class="flex flex-col text-xs text-neutral-500"
						>Start (week)
						<input type="number" min="0" bind:value={row.startWeek} class="mt-1 {fieldClass}" />
					</label>
					<label class="flex flex-col text-xs text-neutral-500"
						>Length (weeks)
						<input type="number" min="1" bind:value={row.weeks} class="mt-1 {fieldClass}" />
					</label>
				</div>
			</div>
		{/each}
	</div>

	<div class="mt-3 flex flex-wrap items-center gap-3">
		<button
			class="rounded-md border border-neutral-700 px-3 py-1.5 text-sm text-violet-300 hover:border-neutral-500"
			onclick={addRow}>+ Add compound</button
		>
		<label class="flex items-center gap-2 text-xs text-neutral-500">
			Horizon (weeks)
			<input type="number" min="1" bind:value={horizonWeeks} class="w-20 {fieldClass}" />
		</label>
	</div>

	<!-- Chart -->
	<section class="mt-6 rounded-lg border border-neutral-800 p-4">
		<h2 class="font-medium">Concentration plot</h2>
		<div class="mt-3">
			{#if plot}
				<CompoundPlotChart data={plot} />
			{:else}
				<p class="text-sm text-neutral-500">Choose a compound and dose to see the curve.</p>
			{/if}
		</div>
	</section>
{/if}
