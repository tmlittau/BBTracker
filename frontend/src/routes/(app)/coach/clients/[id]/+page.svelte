<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { SUBJECTIVE_LABELS } from '$lib/coaching/api';
	import { coachApi, downloadClientReport, type ClientOverview } from '$lib/coaching/clients';

	const clientId = $derived(Number($page.params.id));

	let data = $state<ClientOverview | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let downloading = $state(false);
	let downloadErr = $state<string | null>(null);

	onMount(async () => {
		try {
			data = await coachApi.overview(clientId);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	async function report() {
		downloading = true;
		downloadErr = null;
		try {
			await downloadClientReport(clientId);
		} catch (e) {
			downloadErr = (e as Error).message;
		} finally {
			downloading = false;
		}
	}

	const f = (v: number | null | undefined, d = 1) =>
		v == null ? '—' : Number(v).toFixed(d);
</script>

<a href="/coach" class="text-sm text-neutral-400 hover:text-neutral-200">← All clients</a>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if data}
	{@const comp = data.body.composition}
	{@const energy = data.body.energy}
	{@const w = data.weekly_check_in}
	<div class="mt-2 flex flex-wrap items-center justify-between gap-3">
		<div>
			<h1 class="text-xl font-semibold">{data.client.name}</h1>
			<p class="text-sm text-neutral-500">
				{data.dashboard.phase ? data.dashboard.phase.name : 'No active phase'}
			</p>
		</div>
		<div class="flex items-center gap-3">
			{#if downloadErr}<span class="text-sm text-red-400">{downloadErr}</span>{/if}
			<button
				onclick={report}
				disabled={downloading}
				class="rounded-full border border-neutral-700 px-4 py-2 text-sm font-medium text-neutral-200 hover:bg-neutral-800 disabled:opacity-50"
			>
				{downloading ? 'Generating…' : 'Download check-in report'}
			</button>
		</div>
	</div>

	<!-- Body snapshot -->
	<div class="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
		{#each [['Bodyweight', `${f(comp.weight_kg)} kg`], ['Body fat', `${f(comp.body_fat_pct)}%`], ['FFMI', f(comp.ffmi_normalized)], ['Waist : height', f(data.body.distribution.waist_to_height, 2)], ['Expenditure', energy.adaptive ? `${energy.adaptive.tdee} kcal` : '—'], ['Balance', energy.balance != null ? `${energy.balance > 0 ? '+' : ''}${energy.balance} kcal` : '—']] as [label, value] (label)}
			<div class="rounded-lg border border-neutral-800 bg-neutral-900 p-3">
				<div class="text-[10px] uppercase tracking-wide text-neutral-500">{label}</div>
				<div class="mt-0.5 text-lg font-semibold text-neutral-100">{value}</div>
			</div>
		{/each}
	</div>

	<div class="mt-6 grid gap-4 md:grid-cols-2">
		<!-- Weekly check-in -->
		<section class="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
			<h2 class="font-medium">This week</h2>
			<div class="mt-3 space-y-1.5 text-sm text-neutral-300">
				<p>
					Bodyweight:
					{#if w.bodyweight}
						{w.bodyweight.last} kg
						<span class={w.bodyweight.delta >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
							({w.bodyweight.delta >= 0 ? '+' : ''}{w.bodyweight.delta} kg)
						</span>
					{:else}—{/if}
				</p>
				<p>Training: {w.training.sessions} sessions · {w.training.prs} PRs · {w.training.working_sets} sets</p>
				<p>
					Nutrition: {w.nutrition.days_logged}/7 days ·
					{w.nutrition.avg_calories ?? '—'} kcal · {w.nutrition.avg_protein_g ?? '—'} g protein
				</p>
				<p>Doses logged: {w.doses} · check-ins: {w.check_ins}</p>
				{#if Object.values(w.subjective).some((v) => v != null)}
					<p class="text-neutral-400">
						{#each Object.entries(w.subjective).filter(([, v]) => v != null) as [k, v], i (k)}
							{i > 0 ? ' · ' : ''}{SUBJECTIVE_LABELS[k] ?? k} {v}/5
						{/each}
					</p>
				{/if}
			</div>
		</section>

		<!-- Coach insights -->
		<section class="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
			<h2 class="font-medium">Insights</h2>
			{#if data.body.insights.length === 0}
				<p class="mt-2 text-sm text-neutral-500">Not enough data yet.</p>
			{:else}
				<ul class="mt-3 space-y-2 text-sm">
					{#each data.body.insights as ins (ins.title)}
						<li>
							<span class="font-medium text-neutral-100">{ins.title}</span>
							<span class="text-neutral-400"> — {ins.detail}</span>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	</div>

	<!-- Bloodwork trends -->
	{#if data.body.bloodwork.trends.length > 0}
		<section class="mt-4 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
			<h2 class="font-medium">Bloodwork (latest)</h2>
			<div class="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
				{#each data.body.bloodwork.trends as t (t.marker)}
					<div class="flex justify-between border-b border-neutral-800/60 py-1">
						<span class="text-neutral-400">{t.marker}</span>
						<span class="font-medium text-neutral-200">{t.value} {t.unit}</span>
					</div>
				{/each}
			</div>
		</section>
	{/if}
{/if}
