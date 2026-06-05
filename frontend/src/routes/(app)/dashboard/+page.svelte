<script lang="ts">
	import type { DashboardToday } from '$lib/coaching/api';
	import { PHASE_TYPES } from '$lib/coaching/api';

	let { data } = $props();

	// `today` is the real aggregated payload from /api/v1/dashboard/today/ (SSR load).
	const today = $derived(data.today as DashboardToday | null);

	function num(v: string | null | undefined): number {
		return v == null ? 0 : parseFloat(v) || 0;
	}
	function phaseTypeLabel(key: string | undefined): string {
		return PHASE_TYPES.find((p) => p.key === key)?.label ?? key ?? '';
	}
</script>

<div class="flex items-center justify-between">
	<div>
		<h1 class="text-xl font-semibold">Today</h1>
		<p class="mt-1 text-sm text-neutral-400">
			Signed in as {data.me?.email ?? 'unknown'}{#if today?.date} · {today.date}{/if}
		</p>
	</div>
	<a class="text-sm text-indigo-400 hover:text-indigo-300" href="/check-in">Weekly check-in →</a>
</div>

{#if today}
	<!-- Current phase banner -->
	<section class="mt-6 rounded-lg border border-neutral-800 p-4">
		{#if today.phase}
			<div class="flex items-center justify-between">
				<div>
					<span class="text-xs uppercase tracking-wide text-neutral-500">Current phase</span>
					<p class="text-lg font-semibold">{today.phase.name}</p>
					<p class="text-xs text-neutral-500">
						{phaseTypeLabel(today.phase.phase_type)} · since {today.phase.start_date}
						{#if today.phase.end_date}→ {today.phase.end_date}{:else}(ongoing){/if}
					</p>
					{#if today.phase.nutrition_target_name || today.phase.program_name || today.phase.protocol_name}
						<p class="mt-1 text-xs text-neutral-400">
							Prescribed{#if today.phase.adjustment_effective} (since {today.phase.adjustment_effective}){/if}:
							{#if today.phase.nutrition_target_name}🍽 {today.phase.nutrition_target_name}{/if}
							{#if today.phase.program_name} · 🏋 {today.phase.program_name}{/if}
							{#if today.phase.protocol_name} · 💉 {today.phase.protocol_name}{/if}
						</p>
					{/if}
				</div>
				<a class="text-sm text-indigo-400 hover:text-indigo-300" href="/phases">Manage →</a>
			</div>
		{:else}
			<p class="text-sm text-neutral-400">
				No active phase. <a class="text-indigo-400" href="/phases">Start one →</a> to tie your
				nutrition target, program, and protocol to a timeline.
			</p>
		{/if}
	</section>

	<!-- Domain tiles -->
	<div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
		<!-- Nutrition -->
		<a href="/nutrition" class="rounded-lg border border-neutral-800 border-l-4 border-l-emerald-500 p-4 hover:border-neutral-600">
			<h2 class="text-sm font-medium text-emerald-300">Nutrition</h2>
			{#if today.nutrition.has_target}
				<p class="mt-1 text-2xl font-bold">{num(today.nutrition.calories).toFixed(0)} kcal</p>
				<p class="text-xs text-neutral-500">
					{num(today.nutrition.protein_g).toFixed(0)} g protein · target {today.nutrition.target_name}
				</p>
			{:else}
				<p class="mt-1 text-2xl font-bold">{num(today.nutrition.calories).toFixed(0)} kcal</p>
				<p class="text-xs text-neutral-500">No active target set</p>
			{/if}
		</a>

		<!-- Workout -->
		<a href="/training" class="rounded-lg border border-neutral-800 border-l-4 border-l-indigo-500 p-4 hover:border-neutral-600">
			<h2 class="text-sm font-medium text-indigo-300">Workout</h2>
			{#if today.workout}
				<p class="mt-1 text-2xl font-bold">{today.workout.name}</p>
				<p class="text-xs text-neutral-500">
					{today.workout.exercises} exercise(s)
					{#if today.workout.prs > 0}· <span class="text-yellow-400">{today.workout.prs} PR</span>{/if}
					· {today.workout.completed ? 'completed' : 'in progress'}
				</p>
			{:else}
				<p class="mt-1 text-2xl font-bold text-neutral-500">Rest day</p>
				<p class="text-xs text-neutral-500">No workout logged today</p>
			{/if}
		</a>

		<!-- Doses -->
		<a href="/protocols" class="rounded-lg border border-neutral-800 border-l-4 border-l-violet-500 p-4 hover:border-neutral-600">
			<h2 class="text-sm font-medium text-violet-300">Doses</h2>
			<p class="mt-1 text-2xl font-bold">{today.doses.length}</p>
			{#if today.doses.length > 0}
				<p class="truncate text-xs text-neutral-500">
					{today.doses.map((d) => `${d.item} ${d.amount}${d.unit}`).join(', ')}
				</p>
			{:else}
				<p class="text-xs text-neutral-500">Nothing logged today</p>
			{/if}
		</a>
	</div>

	<div class="mt-6 flex flex-wrap gap-3 text-sm">
		<a class="text-emerald-400 hover:text-emerald-300" href="/nutrition">Log food →</a>
		<a class="text-indigo-400 hover:text-indigo-300" href="/training/log">Start workout →</a>
		<a class="text-violet-400 hover:text-violet-300" href="/protocols/log">Log dose →</a>
		<a class="text-sky-400 hover:text-sky-300" href="/diary/check-in">Daily check-in →</a>
	</div>
{:else}
	<p class="mt-6 text-neutral-400">Couldn't load today's summary.</p>
{/if}
