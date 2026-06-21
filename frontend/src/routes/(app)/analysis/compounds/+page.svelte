<script lang="ts">
	import { onMount } from 'svelte';
	import {
		protocolsApi,
		COMPOUND_CLASSES,
		FREQUENCIES,
		type Compound,
		type CompoundPlot,
		type PlotItemInput,
		type ProtocolRelease
	} from '$lib/protocols/api';
	import { coachingApi, type Phase } from '$lib/coaching/api';
	import { isoDate } from '$lib/date';
	import SearchSelect from '$lib/components/ui/SearchSelect.svelte';
	import CompoundPlotChart from '$lib/protocols/CompoundPlotChart.svelte';
	import ProtocolReleaseChart from '$lib/protocols/ProtocolReleaseChart.svelte';

	let compounds = $state<Compound[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	// --- Phase view: actual logged doses → concentration curves over a phase ---
	let phases = $state<Phase[]>([]);
	let selectedPhaseId = $state<number | null>(null); // null = manual planner
	let release = $state<ProtocolRelease | null>(null);
	let levelsLoading = $state(false);
	let selectedCurveIds = $state<Set<number>>(new Set());

	const today = isoDate();
	const selectedPhase = $derived(phases.find((p) => p.id === selectedPhaseId) ?? null);
	const win = $derived.by(() => {
		const p = selectedPhase;
		if (!p) return { start: '', end: '', current: false };
		const current = today >= p.start_date && (!p.end_date || today <= p.end_date);
		return { start: p.start_date, end: current ? today : (p.end_date ?? today), current };
	});

	async function loadLevels() {
		if (selectedPhaseId == null) return;
		levelsLoading = true;
		error = null;
		try {
			release = await protocolsApi.phaseLevels(win.start, win.end);
			// Default selection: the primary (non-ancillary) compounds, else all.
			const classOf = new Map(compounds.map((c) => [c.id, c.compound_class]));
			const primary = release.compounds
				.filter((c) => !['ancillary', 'other'].includes(classOf.get(c.compound_id) ?? ''))
				.map((c) => c.compound_id);
			selectedCurveIds = new Set(
				primary.length ? primary : release.compounds.map((c) => c.compound_id)
			);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			levelsLoading = false;
		}
	}
	function onPhaseChange() {
		if (selectedPhaseId != null) loadLevels();
	}
	function toggleCurve(id: number) {
		const s = new Set(selectedCurveIds);
		s.has(id) ? s.delete(id) : s.add(id);
		selectedCurveIds = s;
	}
	const filteredRelease = $derived(
		release
			? { ...release, compounds: release.compounds.filter((c) => selectedCurveIds.has(c.compound_id)) }
			: null
	);

	// --- Manual cycle planner (stateless POST /plot/) ---
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
	let rows = $state<Row[]>([newRow()]);
	let horizonWeeks = $state('16');
	let plot = $state<CompoundPlot | null>(null);

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
			[compounds, phases] = await Promise.all([protocolsApi.compounds(), coachingApi.phases()]);
			// Default to the phase containing today; fall back to the planner.
			selectedPhaseId =
				phases.find((p) => today >= p.start_date && (!p.end_date || today <= p.end_date))?.id ??
				null;
			if (selectedPhaseId != null) await loadLevels();
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

	// Auto-plot (debounced) whenever the planner inputs change — planner mode only.
	let timer: ReturnType<typeof setTimeout>;
	$effect(() => {
		const payload = JSON.stringify({ horizon_days: horizonDays, items });
		if (selectedPhaseId != null) return; // phase mode renders its own chart
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

<div class="flex flex-wrap items-center gap-2">
	<label for="cmp-phase" class="text-sm text-neutral-400">Phase</label>
	<select id="cmp-phase" bind:value={selectedPhaseId} onchange={onPhaseChange} class={fieldClass}>
		{#each phases as p (p.id)}<option value={p.id}>{p.name}</option>{/each}
		<option value={null}>Planner (manual)</option>
	</select>
	{#if selectedPhase}
		<span class="text-xs text-neutral-500">{win.start} → {win.current ? 'now' : win.end}</span>
	{/if}
</div>

<p class="mt-3 rounded-md border border-amber-900/60 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
	A relative estimate of active serum levels — informational, not medical advice. Curves use a
	one-compartment (Bateman) model with literature half-life / Tmax / bioavailability; individuals
	vary widely.
</p>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if selectedPhaseId != null}
	<!-- Phase levels: from the owner's actual logged doses across the phase -->
	{#if error}<p class="mt-4 text-sm text-red-400">{error}</p>{/if}
	{#if levelsLoading && !release}
		<p class="mt-6 text-neutral-400">Loading levels…</p>
	{:else if release && release.compounds.length}
		<section class="mt-6 rounded-lg border border-neutral-800 p-4">
			<h2 class="font-medium">Compound levels{selectedPhase ? ` · ${selectedPhase.name}` : ''}</h2>
			<p class="mt-0.5 text-xs text-neutral-500">
				Modelled from your logged doses{win.current ? ' up to today' : ''}. Toggle compounds below.
			</p>
			<div class="mt-3 flex flex-wrap gap-2">
				{#each release.compounds as c (c.compound_id)}
					<button
						class="rounded-full border px-3 py-1 text-xs transition {selectedCurveIds.has(
							c.compound_id
						)
							? 'border-violet-500 bg-violet-950/40 text-violet-200'
							: 'border-neutral-700 text-neutral-400 hover:border-neutral-500'}"
						onclick={() => toggleCurve(c.compound_id)}>{c.name}</button
					>
				{/each}
			</div>
			{#if filteredRelease && filteredRelease.compounds.length}
				<div class="mt-3"><ProtocolReleaseChart data={filteredRelease} /></div>
			{:else}
				<p class="mt-3 text-sm text-neutral-500">Select a compound above to show its curve.</p>
			{/if}
			{#if release.excluded.length}
				<p class="mt-2 text-[10px] text-neutral-600">
					No curve for {release.excluded.join(', ')} (no half-life, or dosed in iu/ml/tablet).
				</p>
			{/if}
		</section>
	{:else}
		<p class="mt-6 text-sm text-neutral-400">
			No compound doses logged during {selectedPhase?.name}. Pick another phase or switch to the
			planner.
		</p>
	{/if}
{:else}
	<!-- Manual planner -->
	{#if error}<p class="mt-4 text-sm text-red-400">{error}</p>{/if}
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
