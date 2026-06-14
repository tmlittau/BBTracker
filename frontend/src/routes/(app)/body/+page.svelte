<script lang="ts">
	import { onMount } from 'svelte';
	import {
		analysisApi,
		BODY_FAT_METHODS,
		MEASUREMENT_TYPES,
		typeLabel,
		type BodyAnalysis,
		type BodyMeasurement
	} from '$lib/analysis/api';
	import { isoDate } from '$lib/date';
	import LineChart from '$lib/components/ui/LineChart.svelte';

	let analysis = $state<BodyAnalysis | null>(null);
	let measurements = $state<BodyMeasurement[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	// Entry form
	let mType = $state('waist');
	let mValue = $state('');
	let mMethod = $state('dexa');
	let mDate = $state(isoDate());
	let saving = $state(false);
	const isBodyFat = $derived(mType === 'body_fat');

	let trendType = $state('waist');

	async function load() {
		[analysis, measurements] = await Promise.all([
			analysisApi.body(),
			analysisApi.measurements()
		]);
	}
	onMount(async () => {
		try {
			await load();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	async function addMeasurement(e: SubmitEvent) {
		e.preventDefault();
		if (mValue === '') return;
		saving = true;
		error = null;
		try {
			await analysisApi.addMeasurement({
				date: mDate,
				type: mType,
				value: String(Number(mValue)),
				method: isBodyFat ? mMethod : undefined
			});
			mValue = '';
			await load();
		} catch (err) {
			error = (err as Error).message;
		} finally {
			saving = false;
		}
	}
	async function removeMeasurement(id: number) {
		await analysisApi.deleteMeasurement(id);
		await load();
	}

	const unitFor = (t: string) => MEASUREMENT_TYPES.find((m) => m.key === t)?.unit ?? '';
	const STATUS: Record<string, string> = {
		good: 'border-green-800/60 bg-green-950/20 text-green-300',
		watch: 'border-amber-800/60 bg-amber-950/20 text-amber-300',
		risk: 'border-red-800/60 bg-red-950/20 text-red-300'
	};
	const DOT: Record<string, string> = { good: 'bg-green-500', watch: 'bg-amber-500', risk: 'bg-red-500' };

	const comp = $derived(analysis?.composition);
	const energy = $derived(analysis?.energy);
	const adaptive = $derived(energy?.adaptive ?? null);

	// Trend: history for the selected measurement type (oldest→newest).
	const trendSeries = $derived([
		{
			points: measurements
				.filter((m) => m.type === trendType)
				.map((m) => ({ x: m.date, y: Number(m.value) }))
				.sort((a, b) => (a.x < b.x ? -1 : 1)),
			color: '#fb7185',
			dots: true
		}
	]);
	const recent = $derived(measurements.slice(0, 12));
	const fmtNum = (v: number | null | undefined, d = 1) =>
		v == null ? '—' : Number(v).toFixed(d);
</script>

<div class="flex items-center justify-between">
	<h1 class="text-xl font-semibold">Body analysis</h1>
</div>
<p class="mt-1 rounded-md border border-amber-900/60 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
	Estimates from anthropometric formulas — informational, not medical advice. Each figure shows its
	source; a DEXA/scan reading always overrides an estimate.
</p>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if analysis}
	<!-- Snapshot -->
	<section class="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
		<div class="rounded-lg border border-neutral-800 p-4">
			<p class="text-xs uppercase tracking-wide text-neutral-500">Body fat</p>
			<p class="mt-1 text-2xl font-bold">{fmtNum(comp?.body_fat_pct)}%</p>
			<p class="text-xs text-neutral-500">
				source: {comp?.body_fat_source ?? '—'} · fat {fmtNum(comp?.fat_mass_kg)} kg · lean {fmtNum(comp?.lean_mass_kg)} kg
			</p>
		</div>
		<div class="rounded-lg border border-neutral-800 p-4">
			<p class="text-xs uppercase tracking-wide text-neutral-500">FFMI (normalized)</p>
			<p class="mt-1 text-2xl font-bold">{fmtNum(comp?.ffmi_normalized)}</p>
			<p class="text-xs text-neutral-500">raw {fmtNum(comp?.ffmi)} · natural limit ≈ 25</p>
		</div>
		<div class="rounded-lg border border-neutral-800 p-4">
			<p class="text-xs uppercase tracking-wide text-neutral-500">Waist-to-height</p>
			<p class="mt-1 text-2xl font-bold">{fmtNum(analysis.distribution.waist_to_height, 2)}</p>
			<p class="text-xs text-neutral-500">healthy &lt; 0.5</p>
		</div>
		<div class="rounded-lg border border-neutral-800 p-4">
			<p class="text-xs uppercase tracking-wide text-neutral-500">Adaptive expenditure</p>
			{#if adaptive}
				<p class="mt-1 text-2xl font-bold">{adaptive.tdee} <span class="text-sm font-normal text-neutral-500">kcal/day</span></p>
				<p class="text-xs text-neutral-500">
					{adaptive.confidence} confidence · {adaptive.weight_slope_kg_wk > 0 ? '+' : ''}{adaptive.weight_slope_kg_wk} kg/wk over {adaptive.days} d
				</p>
			{:else}
				<p class="mt-1 text-sm text-neutral-400">Log bodyweight + food for ~2–3 weeks to estimate your real maintenance.</p>
			{/if}
		</div>
		<div class="rounded-lg border border-neutral-800 p-4">
			<p class="text-xs uppercase tracking-wide text-neutral-500">Energy balance</p>
			{#if energy?.balance != null}
				<p class="mt-1 text-2xl font-bold {energy.balance < 0 ? 'text-sky-300' : energy.balance > 0 ? 'text-amber-300' : ''}">
					{energy.balance > 0 ? '+' : ''}{energy.balance} <span class="text-sm font-normal text-neutral-500">kcal/day</span>
				</p>
				<p class="text-xs text-neutral-500">intake {energy.recent_intake} vs expenditure {adaptive?.tdee}</p>
			{:else}
				<p class="mt-1 text-sm text-neutral-400">Needs adaptive expenditure + recent intake.</p>
			{/if}
		</div>
		<div class="rounded-lg border border-neutral-800 p-4">
			<p class="text-xs uppercase tracking-wide text-neutral-500">BMR</p>
			<p class="mt-1 text-2xl font-bold">{energy?.bmr ?? '—'} <span class="text-sm font-normal text-neutral-500">kcal/day</span></p>
			<p class="text-xs text-neutral-500">
				{energy?.bmr_katch_mcardle ? 'Katch-McArdle (lean mass)' : 'Mifflin-St Jeor'}
			</p>
		</div>
	</section>

	<!-- Assessments -->
	{#if analysis.assessments.length}
		<section class="mt-8">
			<h2 class="font-medium">Assessments</h2>
			<div class="mt-3 grid gap-2 sm:grid-cols-2">
				{#each analysis.assessments as a (a.key)}
					<div class="rounded-lg border p-3 {STATUS[a.status]}">
						<div class="flex items-center justify-between">
							<span class="flex items-center gap-2 text-sm font-medium">
								<span class="h-2 w-2 rounded-full {DOT[a.status]}"></span>{a.label}
							</span>
							<span class="text-sm tabular-nums">{a.value}</span>
						</div>
						<p class="mt-1 text-xs text-neutral-400">{a.detail}</p>
						{#if a.source}<p class="mt-0.5 text-[10px] text-neutral-600">{a.source}</p>{/if}
					</div>
				{/each}
			</div>
		</section>
	{/if}

	<!-- Bloodwork ratios -->
	{#if Object.keys(analysis.bloodwork.ratios).length}
		<section class="mt-8">
			<h2 class="font-medium">Bloodwork ratios</h2>
			<div class="mt-2 flex flex-wrap gap-4 text-sm">
				{#each Object.entries(analysis.bloodwork.ratios) as [k, v] (k)}
					<span class="rounded border border-neutral-800 px-3 py-1.5">
						<span class="text-neutral-500">{k.replace('_', '/').toUpperCase()}</span>
						<span class="ml-1 font-medium tabular-nums">{v}</span>
					</span>
				{/each}
			</div>
		</section>
	{/if}

	<!-- Add measurement -->
	<section class="mt-8">
		<h2 class="font-medium">Add a measurement</h2>
		<form class="mt-3 flex flex-wrap items-end gap-2" onsubmit={addMeasurement}>
			<label class="flex flex-col text-xs text-neutral-500">Measurement
				<select bind:value={mType} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100">
					{#each MEASUREMENT_TYPES as t (t.key)}<option value={t.key}>{t.label}</option>{/each}
				</select>
			</label>
			<label class="flex flex-col text-xs text-neutral-500">Value ({unitFor(mType)})
				<input type="number" step="0.1" bind:value={mValue} class="mt-1 w-24 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100" />
			</label>
			{#if isBodyFat}
				<label class="flex flex-col text-xs text-neutral-500">Method
					<select bind:value={mMethod} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100">
						{#each BODY_FAT_METHODS as m (m.key)}<option value={m.key}>{m.label}</option>{/each}
					</select>
				</label>
			{/if}
			<label class="flex flex-col text-xs text-neutral-500">Date
				<input type="date" bind:value={mDate} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100" />
			</label>
			<button type="submit" disabled={saving} class="rounded-md bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-500 disabled:opacity-50">
				{saving ? 'Saving…' : 'Add'}
			</button>
		</form>
		{#if recent.length}
			<ul class="mt-3 divide-y divide-neutral-800 text-sm">
				{#each recent as m (m.id)}
					<li class="flex items-center justify-between py-1.5">
						<span>{typeLabel(m.type)} <span class="text-neutral-500">· {Number(m.value)} {m.unit}{#if m.method} · {m.method}{/if}</span></span>
						<span class="flex items-center gap-3 text-xs text-neutral-500">
							{m.date}
							<button class="text-neutral-600 hover:text-red-400" aria-label="Delete" onclick={() => removeMeasurement(m.id)}>✕</button>
						</span>
					</li>
				{/each}
			</ul>
		{/if}
	</section>

	<!-- Trend -->
	<section class="mt-8 rounded-lg border border-neutral-800 p-4">
		<div class="flex items-center justify-between">
			<h2 class="font-medium">Trend</h2>
			<select bind:value={trendType} class="rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100">
				{#each MEASUREMENT_TYPES as t (t.key)}<option value={t.key}>{t.label}</option>{/each}
			</select>
		</div>
		{#if trendSeries[0].points.length > 1}
			<div class="mt-3"><LineChart series={trendSeries} unit={unitFor(trendType)} /></div>
		{:else}
			<p class="mt-3 text-sm text-neutral-500">Log this measurement on at least two dates to see a trend.</p>
		{/if}
	</section>
{/if}
