<script lang="ts">
	import type { DashboardToday } from '$lib/coaching/api';
	import { PHASE_TYPES } from '$lib/coaching/api';

	let { data } = $props();

	// `today` is the real aggregated payload from /api/v1/dashboard/today/ (SSR load).
	const today = $derived(data.today as DashboardToday | null);
	console.log(today.doses);

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
	<a class="arrow-link" href="/phases">Manage Phases</a>
	<a class="arrow-link" href="/check-in">Check-in Overview</a>
	<a class="arrow-link" href="/analysis">Analysis</a>
</div>

{#if today}
	<!-- Current phase banner -->
	<section
	class="relative isolate mt-6 overflow-hidden rounded-[1.75rem] border border-white/10 bg-[#09090b] p-6 shadow-2xl shadow-black/40"
>
		<div
			class="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_82%_35%,rgba(255,126,31,0.30),transparent_28%),radial-gradient(circle_at_98%_55%,rgba(255,43,77,0.22),transparent_34%),linear-gradient(90deg,rgba(9,9,11,1)_0%,rgba(9,9,11,0.96)_48%,rgba(255,126,31,0.10)_78%,rgba(255,43,77,0.16)_100%)]"
		></div>

		<div class="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-white/[0.04] to-transparent"></div>

		{#if today.phase}
			<div class="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
				<div>
					<span class="text-xs font-semibold uppercase tracking-[0.22em] text-neutral-500">
						Current phase
					</span>

					<p class="mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">
						{today.phase.name}
					</p>

					<p
						class="mt-1 bg-gradient-to-r from-orange-400 via-orange-500 to-rose-500 bg-clip-text text-sm font-semibold text-transparent"
					>
						{phaseTypeLabel(today.phase.phase_type)} · since {today.phase.start_date}
						{#if today.phase.end_date}→ {today.phase.end_date}{:else}(ongoing){/if}
					</p>

					{#if today.phase.nutrition_target_name || today.phase.program_name || today.phase.protocol_name}
						<p class="mt-4 max-w-3xl text-sm leading-6 text-neutral-400">
							{#if today.phase.program_name}
								<span> · Split: {today.phase.program_name}</span>
							{/if}
						</p>
					{/if}
				</div>

				<a
					class="inline-flex items-center justify-center rounded-full bg-gradient-to-r from-orange-400 via-orange-500 to-rose-500 px-6 py-3 text-sm font-bold tracking-wide text-neutral-950 shadow-lg shadow-orange-500/20 transition hover:scale-[1.02] hover:shadow-orange-500/30 focus:outline-none focus:ring-2 focus:ring-orange-400 focus:ring-offset-2 focus:ring-offset-neutral-950"
					href="/diary/check-in"
				>
					Daily Check-in
				</a>
			</div>
		{:else}
			<div>
				<p class="text-3xl font-bold tracking-tight text-white">
					No active phase.
				</p>

				<p class="mt-3 max-w-2xl text-sm leading-6 text-neutral-400">
					Start one to tie your nutrition target, program, and protocol to a timeline.
				</p>

				<a
					class="mt-6 inline-flex items-center justify-center rounded-full bg-gradient-to-r from-orange-400 via-orange-500 to-rose-500 px-6 py-3 text-sm font-bold tracking-wide text-neutral-950 shadow-lg shadow-orange-500/20 transition hover:scale-[1.02] hover:shadow-orange-500/30 focus:outline-none focus:ring-2 focus:ring-orange-400 focus:ring-offset-2 focus:ring-offset-neutral-950"
					href="/phases"
				>
					Start one <span class="ml-2 text-lg leading-none">→</span>
				</a>
			</div>
		{/if}
	</section>

	<!-- Domain tiles -->
	<div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
		<!-- Nutrition -->
		<a href="/nutrition" class="group relative isolate overflow-hidden rounded-[1.25rem] border border-white/10 bg-[#09090b] p-5 shadow-xl shadow-black/30 transition hover:border-orange-400/60 hover:shadow-orange-500/10">
			<div
				class="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_90%_20%,rgba(255,126,31,0.24),transparent_30%),radial-gradient(circle_at_100%_70%,rgba(255,43,77,0.18),transparent_36%),linear-gradient(90deg,rgba(9,9,11,1)_0%,rgba(9,9,11,0.96)_55%,rgba(255,126,31,0.10)_82%,rgba(255,43,77,0.14)_100%)]"
			></div>

			<div class="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-white/[0.04] to-transparent"></div>

			
			
			<div class="flex items-start justify-between gap-4">
				<div>
					<h2
						class="bg-gradient-to-r from-orange-300 via-orange-400 to-rose-400 bg-clip-text text-sm font-semibold text-transparent"
					>
						Nutrition
					</h2>
					<p class="mt-2 text-2xl font-bold tracking-tight text-white">
						{num(today.nutrition.calories).toFixed(0)} kcal
					</p>

					<p class="mt-1 text-xs text-neutral-400">
						{num(today.nutrition.protein_g).toFixed(0)} g protein
					</p>
				</div>

				<span
					aria-hidden="true"
					class="pointer-events-none inline-flex shrink-0 items-center justify-center rounded-full bg-gradient-to-r from-orange-400 via-orange-500 to-rose-500 px-4 py-2 text-xs font-bold tracking-wide text-neutral-950 shadow-lg shadow-orange-500/20 transition group-hover:scale-[1.03] group-hover:shadow-orange-500/30"
				>
					Log Food
				</span>
			</div>
		</a>

		<!-- Workout -->
		<a href="/training" class="group relative isolate overflow-hidden rounded-[1.25rem] border border-white/10 bg-[#09090b] p-5 shadow-xl shadow-black/30 transition hover:border-orange-400/60 hover:shadow-orange-500/10">
			<div
				class="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_90%_20%,rgba(255,126,31,0.24),transparent_30%),radial-gradient(circle_at_100%_70%,rgba(255,43,77,0.18),transparent_36%),linear-gradient(90deg,rgba(9,9,11,1)_0%,rgba(9,9,11,0.96)_55%,rgba(255,126,31,0.10)_82%,rgba(255,43,77,0.14)_100%)]"
			></div>

			<div class="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-white/[0.04] to-transparent"></div>

			<div class="flex items-start justify-between gap-4">
				<div>
					<h2
						class="bg-gradient-to-r from-orange-300 via-orange-400 to-rose-400 bg-clip-text text-sm font-semibold text-transparent"
					>
						Workout
					</h2>
					{#if today.workout}
						<p class="mt-1 text-2xl font-bold">{today.workout.name}</p>
						<p class="text-xs text-neutral-500">
							{today.workout.exercises} exercise(s)
							{#if today.workout.prs > 0}· <span class="text-yellow-400">{today.workout.prs} PR</span>{/if}
							· {today.workout.completed ? 'completed' : 'in progress'}
						</p>
					{:else}
						<p class="mt-2 text-2xl font-bold tracking-tight text-neutral-500">Rest day</p>
						<p class="text-xs text-neutral-500">No workout logged today</p>
					{/if}
				</div>
				<span
					aria-hidden="true"
					class="pointer-events-none inline-flex shrink-0 items-center justify-center rounded-full bg-gradient-to-r from-orange-400 via-orange-500 to-rose-500 px-4 py-2 text-xs font-bold tracking-wide text-neutral-950 shadow-lg shadow-orange-500/20 transition group-hover:scale-[1.03] group-hover:shadow-orange-500/30"
				>
					Start Workout
				</span>
			</div>
		</a>
	
		<!-- Doses -->
		<a href="/protocols" class="group relative isolate overflow-hidden rounded-[1.25rem] border border-white/10 bg-[#09090b] p-5 shadow-xl shadow-black/30 transition hover:border-orange-400/60 hover:shadow-orange-500/10">
			<div
				class="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_90%_20%,rgba(255,126,31,0.24),transparent_30%),radial-gradient(circle_at_100%_70%,rgba(255,43,77,0.18),transparent_36%),linear-gradient(90deg,rgba(9,9,11,1)_0%,rgba(9,9,11,0.96)_55%,rgba(255,126,31,0.10)_82%,rgba(255,43,77,0.14)_100%)]"
			></div>

			<div class="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-white/[0.04] to-transparent"></div>

			<div class="flex items-start justify-between gap-4">
				<div>
					<h2 class="text-sm font-medium text-violet-300">Doses</h2>
					<p class="mt-1 text-2xl font-bold">{today.doses.length}</p>
					{#if today.doses.length > 0}
						<p class="truncate text-xs text-neutral-500">
							{today.doses.map((d) => `${d.item} ${d.amount}${d.unit}`).join(', ')}
						</p>
					{:else}
						<p class="text-xs text-neutral-500">Nothing logged today</p>
					{/if}
				</div>
			
				<span
					aria-hidden="true"
					class="pointer-events-none inline-flex shrink-0 items-center justify-center rounded-full bg-gradient-to-r from-orange-400 via-orange-500 to-rose-500 px-4 py-2 text-xs font-bold tracking-wide text-neutral-950 shadow-lg shadow-orange-500/20 transition group-hover:scale-[1.03] group-hover:shadow-orange-500/30"
				>
					Log Dose
				</span>
			</div>
		</a>
			
	</div>
{:else}
	<p class="mt-6 text-neutral-400">Couldn't load today's summary.</p>
{/if}
