<script lang="ts">
	import { onMount } from 'svelte';
	import {
		protocolsApi,
		type BloodMarker,
		type BloodMatrix,
		type BloodPressureLog,
		type MarkerTrendPoint
	} from '$lib/protocols/api';
	import { num } from '$lib/protocols/calc';
	import Button from '$lib/components/ui/Button.svelte';
	import Modal from '$lib/components/ui/Modal.svelte';
	import LineChart from '$lib/components/ui/LineChart.svelte';

	let markers = $state<BloodMarker[]>([]);
	let matrix = $state<BloodMatrix | null>(null);
	let bpLogs = $state<BloodPressureLog[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	let view = $state<'table' | 'chart'>('table');

	// Add-results modal (full panel: every marker optional, only date required).
	let showResults = $state(false);
	let resultsDate = $state(new Date().toISOString().slice(0, 10));
	let resultValues = $state<Record<number, string>>({});
	let savingResults = $state(false);

	// Per-marker diagram.
	let chartMarker = $state<number | null>(null);
	let trend = $state<MarkerTrendPoint[]>([]);

	// Quick BP.
	let systolic = $state('');
	let diastolic = $state('');
	let pulse = $state('');

	async function loadMatrix() {
		matrix = await protocolsApi.bloodworkMatrix();
	}
	async function loadBp() {
		bpLogs = await protocolsApi.bpLogs();
	}

	onMount(async () => {
		try {
			[markers] = await Promise.all([protocolsApi.bloodMarkers(), loadMatrix(), loadBp()]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	async function saveResults(e: SubmitEvent) {
		e.preventDefault();
		savingResults = true;
		error = null;
		try {
			const results = Object.entries(resultValues)
				.filter(([, v]) => v !== '' && v != null)
				.map(([m, v]) => ({ marker: Number(m), value: String(num(v)) }));
			await protocolsApi.bulkBloodResults(resultsDate, results);
			resultValues = {};
			showResults = false;
			await loadMatrix();
			if (chartMarker != null) await loadTrend();
		} catch (err) {
			error = (err as Error).message;
		} finally {
			savingResults = false;
		}
	}

	async function loadTrend() {
		if (chartMarker == null) {
			trend = [];
			return;
		}
		trend = await protocolsApi.markerTrend(chartMarker);
	}

	async function saveBp(e: SubmitEvent) {
		e.preventDefault();
		if (systolic === '' || diastolic === '') return;
		await protocolsApi.logBp({
			systolic: Math.round(num(systolic)),
			diastolic: Math.round(num(diastolic)),
			pulse: pulse === '' ? undefined : Math.round(num(pulse)),
			measured_at: new Date().toISOString()
		});
		systolic = diastolic = pulse = '';
		await loadBp();
	}

	// Cell colouring: high = red, low = amber (distinguish direction), in-range = plain.
	function cellClass(flag: string): string {
		if (flag === 'high') return 'text-red-300 bg-red-950/40';
		if (flag === 'low') return 'text-amber-300 bg-amber-950/40';
		return 'text-neutral-200';
	}

	const chartMarkerObj = $derived(markers.find((m) => m.id === chartMarker) ?? null);
	const chartSeries = $derived([
		{ points: trend.map((p) => ({ x: p.date, y: num(p.value) })), color: '#6366f1', dots: true }
	]);
	const chartBand = $derived(
		chartMarkerObj
			? {
					low: chartMarkerObj.ref_low != null ? num(chartMarkerObj.ref_low) : null,
					high: chartMarkerObj.ref_high != null ? num(chartMarkerObj.ref_high) : null
				}
			: undefined
	);
</script>

<Modal bind:open={showResults} title="Add bloodwork results" size="lg">
	<form onsubmit={saveResults}>
		<label class="flex flex-col text-xs text-neutral-500">
			Date (required)
			<input type="date" required bind:value={resultsDate} class="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100 sm:w-44" />
		</label>
		<p class="mt-3 text-xs text-neutral-500">Enter only what you have — blank markers are skipped.</p>
		<div class="mt-2 grid gap-x-4 gap-y-2 sm:grid-cols-2">
			{#each markers as m (m.id)}
				<label class="flex items-center justify-between gap-2 text-sm">
					<span class="truncate text-neutral-300">{m.name} <span class="text-neutral-600">{m.unit}</span></span>
					<input
						type="number"
						step="0.001"
						bind:value={resultValues[m.id]}
						class="w-24 rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm text-neutral-100"
					/>
				</label>
			{/each}
		</div>
		{#if error}<p class="mt-2 text-sm text-red-400">{error}</p>{/if}
		<div class="mt-4 w-40"><Button type="submit" disabled={savingResults}>{savingResults ? 'Saving…' : 'Save results'}</Button></div>
	</form>
</Modal>

<div class="flex items-center justify-between">
	<h1 class="text-xl font-semibold">Bloodwork &amp; vitals</h1>
	<button class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500" onclick={() => (showResults = true)}>
		Add bloodwork results
	</button>
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error && !matrix}
	<p class="mt-6 text-red-400">{error}</p>
{:else}
	<!-- Exploration: table ⇄ chart -->
	<section class="mt-6 rounded-lg border border-neutral-800 p-4">
		<div class="flex items-center justify-between">
			<h2 class="font-medium">Marker trends</h2>
			<div class="flex gap-1 text-sm">
				<button class="rounded px-3 py-1 {view === 'table' ? 'bg-indigo-600 text-white' : 'border border-neutral-700 text-neutral-300'}" onclick={() => (view = 'table')}>Table</button>
				<button class="rounded px-3 py-1 {view === 'chart' ? 'bg-indigo-600 text-white' : 'border border-neutral-700 text-neutral-300'}" onclick={() => (view = 'chart')}>Diagram</button>
			</div>
		</div>

		{#if view === 'table'}
			{#if !matrix || matrix.rows.length === 0}
				<p class="mt-3 text-sm text-neutral-500">No results yet — add a panel to see trends.</p>
			{:else}
				<div class="mt-3 overflow-x-auto">
					<table class="w-full border-collapse text-sm">
						<thead class="text-xs text-neutral-500">
							<tr>
								<th class="sticky left-0 bg-neutral-950 px-2 py-1 text-left font-normal">Marker</th>
								{#each matrix.dates as d (d)}<th class="px-2 py-1 text-right font-normal">{d}</th>{/each}
							</tr>
						</thead>
						<tbody>
							{#each matrix.rows as row (row.slug)}
								<tr class="border-t border-neutral-800">
									<td class="sticky left-0 bg-neutral-950 px-2 py-1">
										{row.marker} <span class="text-neutral-600">{row.unit}</span>
									</td>
									{#each row.cells as cell, ci (ci)}
										<td class="px-2 py-1 text-right {cell ? cellClass(cell.flag) : 'text-neutral-700'}">
											{#if cell}
												{cell.value}
												{#if cell.pct_change != null}
													<span class="block text-[10px] text-neutral-500">{cell.pct_change > 0 ? '+' : ''}{cell.pct_change}%</span>
												{/if}
											{:else}—{/if}
										</td>
									{/each}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				<p class="mt-2 text-xs text-neutral-500">
					Out-of-range cells: <span class="text-red-300">high</span>, <span class="text-amber-300">low</span>.
					% is the change from the previous reading. Never-measured markers are hidden.
				</p>
			{/if}
		{:else}
			<select bind:value={chartMarker} onchange={loadTrend} class="mt-3 w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100">
				<option value={null}>Choose a marker…</option>
				{#each markers as m (m.id)}<option value={m.id}>{m.name}</option>{/each}
			</select>
			{#if chartMarker != null}
				{#if trend.length === 0}
					<p class="mt-3 text-sm text-neutral-500">No results logged for this marker yet.</p>
				{:else}
					<div class="mt-4">
						<LineChart series={chartSeries} band={chartBand} unit={chartMarkerObj?.unit ?? ''} />
						<p class="mt-1 text-xs text-neutral-500">Shaded band = reference range.</p>
					</div>
				{/if}
			{/if}
		{/if}
	</section>

	<!-- Blood pressure (quick) -->
	<section class="mt-6 rounded-lg border border-neutral-800 p-4">
		<h2 class="font-medium">Blood pressure</h2>
		<form class="mt-3 flex flex-wrap items-end gap-2" onsubmit={saveBp}>
			<label class="flex flex-col text-xs text-neutral-500">Systolic<input name="systolic" type="number" bind:value={systolic} class="mt-1 w-24 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100" /></label>
			<label class="flex flex-col text-xs text-neutral-500">Diastolic<input name="diastolic" type="number" bind:value={diastolic} class="mt-1 w-24 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100" /></label>
			<label class="flex flex-col text-xs text-neutral-500">Pulse<input name="pulse" type="number" bind:value={pulse} class="mt-1 w-20 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100" /></label>
			<Button type="submit">Log BP</Button>
		</form>
		{#if bpLogs.length > 0}
			<div class="mt-3 space-y-1">
				{#each bpLogs.slice(0, 6) as bp (bp.id)}
					<div class="flex items-center justify-between text-sm">
						<span class="font-mono">{bp.systolic}/{bp.diastolic}{#if bp.pulse} · {bp.pulse} bpm{/if}</span>
						<span class="text-xs text-neutral-500">{new Date(bp.measured_at).toLocaleString()}</span>
					</div>
				{/each}
			</div>
		{/if}
	</section>
{/if}
