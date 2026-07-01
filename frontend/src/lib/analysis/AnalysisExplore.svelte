<script lang="ts">
	// Cross-domain overlay: pick up to 3 tracked metrics and plot them on one timeline
	// to spot relationships (e.g. testosterone dose vs hematocrit). Metrics with
	// different units are scaled to their own range (shape comparison); phase/protocol
	// changes are drawn as vertical markers.
	import { onMount } from 'svelte';
	import { analysisApi, type Metric, type SeriesOverlay } from '$lib/analysis/api';
	import LineChart from '$lib/components/ui/LineChart.svelte';

	let { start = undefined, end = undefined }: { start?: string; end?: string } = $props();

	const COLORS = ['#10b981', '#f59e0b', '#6366f1', '#ec4899'];
	const MAX = 3;

	function groupOf(catalog: Metric[]) {
		const order: string[] = [];
		const byGroup: Record<string, Metric[]> = {};
		for (const m of catalog) {
			if (!byGroup[m.group]) {
				byGroup[m.group] = [];
				order.push(m.group);
			}
			byGroup[m.group].push(m);
		}
		return order.map((g) => ({ group: g, metrics: byGroup[g] }));
	}

	let selected = $state<string[]>(['bodyweight']);
	let data = $state<SeriesOverlay | null>(null);
	let loading = $state(false);
	let error = $state<string | null>(null);
	// Created in onMount (client-only) so the relative fetch has an origin — a
	// top-level fetch would fire during SSR where it can't resolve.
	let catalogPromise = $state<Promise<Metric[]> | null>(null);

	onMount(() => {
		catalogPromise = analysisApi.metricCatalog();
		load();
	});

	async function load() {
		if (!selected.length) {
			data = null;
			return;
		}
		loading = true;
		error = null;
		try {
			data = await analysisApi.series(selected, start, end);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	function toggle(key: string) {
		if (selected.includes(key)) selected = selected.filter((k) => k !== key);
		else if (selected.length < MAX) selected = [...selected, key];
		load();
	}

	const single = $derived((data?.metrics.length ?? 0) <= 1);

	const chartSeries = $derived.by(() =>
		(data?.metrics ?? [])
			.filter((m) => m.points.length)
			.map((m, i) => {
				const ys = m.points.map((p) => p.value);
				const lo = Math.min(...ys);
				const hi = Math.max(...ys);
				const norm = (v: number) => (hi > lo ? (v - lo) / (hi - lo) : 0.5);
				return {
					label: m.label,
					color: COLORS[i % COLORS.length],
					dots: m.points.length < 8,
					points: m.points.map((p) => ({ x: p.date, y: single ? p.value : norm(p.value) }))
				};
			})
	);

	const legend = $derived.by(() =>
		(data?.metrics ?? []).map((m, i) => {
			const ys = m.points.map((p) => p.value);
			return {
				label: m.label,
				unit: m.unit,
				color: COLORS[i % COLORS.length],
				min: ys.length ? Math.min(...ys) : null,
				max: ys.length ? Math.max(...ys) : null,
				n: ys.length
			};
		})
	);

	const markers = $derived(
		(data?.events ?? []).map((e) => ({ x: e.date, label: e.label, color: '#f59e0b' }))
	);
</script>

<p class="text-xs text-neutral-500">
	Overlay up to {MAX} metrics on one timeline to spot relationships. With more than one metric each
	is scaled to its own range (shape comparison, not absolute); protocol changes are marked.
</p>

<div class="mt-3 space-y-2">
	{#if catalogPromise}
		{#await catalogPromise}
			<p class="text-sm text-neutral-500">Loading metrics…</p>
		{:then catalog}
			{#each groupOf(catalog) as g (g.group)}
				<div>
					<span class="text-[10px] font-medium uppercase tracking-wide text-neutral-600">{g.group}</span>
					<div class="mt-1 flex flex-wrap gap-1.5">
						{#each g.metrics as m (m.key)}
							<button
								type="button"
								class="rounded-full border px-2.5 py-0.5 text-xs {selected.includes(m.key)
									? 'border-emerald-500 bg-emerald-950 text-emerald-200'
									: 'border-neutral-700 text-neutral-400 hover:border-neutral-500'}"
								disabled={!selected.includes(m.key) && selected.length >= MAX}
								onclick={() => toggle(m.key)}
							>
								{m.label}
							</button>
						{/each}
					</div>
				</div>
			{/each}
		{:catch}
			<p class="text-sm text-red-400">Couldn't load the metric list.</p>
		{/await}
	{/if}
</div>

{#if error}
	<p class="mt-2 text-sm text-red-400">{error}</p>
{:else if loading}
	<p class="mt-3 text-sm text-neutral-500">Loading…</p>
{:else if data && chartSeries.length}
	<div class="mt-3">
		<LineChart
			series={chartSeries}
			{markers}
			unit={single ? (data.metrics[0]?.unit ?? '') : ''}
			height={220}
		/>
	</div>
	<div class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
		{#each legend as l (l.label)}
			<span class="flex items-center gap-1 text-neutral-400">
				<span class="inline-block h-2 w-2 rounded-full" style="background:{l.color}"></span>
				{l.label}
				{#if l.min != null}<span class="text-neutral-600">{l.min}–{l.max} {l.unit} · {l.n}pt</span>{/if}
			</span>
		{/each}
	</div>
{:else if data}
	<p class="mt-3 text-sm text-neutral-500">No data for the selected metric(s) in this window.</p>
{/if}
