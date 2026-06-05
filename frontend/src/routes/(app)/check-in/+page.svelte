<script lang="ts">
	import { onMount } from 'svelte';
	import { coachingApi, SUBJECTIVE_LABELS, type WeeklyCheckIn } from '$lib/coaching/api';

	let report = $state<WeeklyCheckIn | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let end = $state(new Date().toISOString().slice(0, 10));

	async function load() {
		loading = true;
		error = null;
		try {
			report = await coachingApi.weeklyCheckIn(end);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	onMount(load);

	function fmt(n: number | null | undefined, suffix = ''): string {
		return n == null ? '—' : `${n}${suffix}`;
	}
</script>

<div class="flex items-center justify-between">
	<h1 class="text-xl font-semibold">Weekly check-in</h1>
	<label class="text-xs text-neutral-500">
		Week ending
		<input type="date" bind:value={end} onchange={load} class="ml-2 rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm text-neutral-100" />
	</label>
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if report}
	<p class="mt-1 text-sm text-neutral-400">
		{report.start_date} → {report.end_date}
		{#if report.phase}· phase: <span class="text-neutral-200">{report.phase.name}</span>{/if}
	</p>

	<div class="mt-6 grid gap-4 sm:grid-cols-2">
		<!-- Bodyweight -->
		<section class="rounded-lg border border-neutral-800 p-4">
			<h2 class="text-sm font-medium text-neutral-300">Bodyweight</h2>
			{#if report.bodyweight}
				<p class="mt-1 text-2xl font-bold">
					{report.bodyweight.last} kg
					<span class="text-sm font-normal {report.bodyweight.delta < 0 ? 'text-green-400' : report.bodyweight.delta > 0 ? 'text-amber-400' : 'text-neutral-500'}">
						({report.bodyweight.delta > 0 ? '+' : ''}{report.bodyweight.delta})
					</span>
				</p>
				<p class="text-xs text-neutral-500">from {report.bodyweight.first} kg at week start</p>
			{:else}
				<p class="mt-1 text-sm text-neutral-500">No bodyweight logged this week</p>
			{/if}
		</section>

		<!-- Training -->
		<section class="rounded-lg border border-neutral-800 p-4">
			<h2 class="text-sm font-medium text-neutral-300">Training</h2>
			<p class="mt-1 text-2xl font-bold">{report.training.sessions} session(s)</p>
			<p class="text-xs text-neutral-500">
				{report.training.working_sets} working sets
				{#if report.training.prs > 0}· <span class="text-yellow-400">{report.training.prs} PR</span>{/if}
			</p>
			{#if report.training.top_muscles.length}
				<p class="mt-1 text-xs text-neutral-500">
					Top: {report.training.top_muscles.map((m) => `${m.muscle} (${m.sets})`).join(', ')}
				</p>
			{/if}
		</section>

		<!-- Nutrition -->
		<section class="rounded-lg border border-neutral-800 p-4">
			<h2 class="text-sm font-medium text-neutral-300">Nutrition</h2>
			<p class="mt-1 text-2xl font-bold">{fmt(report.nutrition.avg_calories)} kcal</p>
			<p class="text-xs text-neutral-500">
				avg over {report.nutrition.days_logged} logged day(s)
				· {fmt(report.nutrition.avg_protein_g, ' g')} protein
			</p>
		</section>

		<!-- Adherence / misc -->
		<section class="rounded-lg border border-neutral-800 p-4">
			<h2 class="text-sm font-medium text-neutral-300">This week</h2>
			<p class="mt-1 text-sm text-neutral-300">
				{report.doses} dose(s) · {report.photos} photo(s) · {report.check_ins} check-in(s)
			</p>
			<p class="text-xs text-neutral-500">
				Last bloodwork: {report.last_bloodwork ?? 'none recorded'}
			</p>
		</section>
	</div>

	<!-- Subjective wellbeing -->
	<section class="mt-6 rounded-lg border border-neutral-800 p-4">
		<h2 class="text-sm font-medium text-neutral-300">Subjective wellbeing (avg 1–5)</h2>
		<div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
			{#each Object.entries(SUBJECTIVE_LABELS) as [key, label] (key)}
				<div class="text-center">
					<p class="text-2xl font-bold">{fmt(report.subjective[key])}</p>
					<p class="text-xs text-neutral-500">{label}</p>
				</div>
			{/each}
		</div>
	</section>

	<p class="mt-6 text-xs text-neutral-600">
		This report aggregates the trailing 7 days across every module — the data you'd hand a coach.
	</p>
{/if}
