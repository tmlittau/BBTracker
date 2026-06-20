<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { trainingApi, type Program, type WorkoutSessionListItem } from '$lib/training/api';

	let programs = $state<Program[]>([]);
	let recent = $state<WorkoutSessionListItem[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	const active = $derived(programs.find((p) => p.is_active) ?? null);
	// In-progress = started but not finished — surfaced so you can jump back in if
	// you navigated away mid-workout (all logged sets are retained).
	const inProgress = $derived(recent.filter((s) => !s.is_completed));
	const completed = $derived(recent.filter((s) => s.is_completed));

	onMount(async () => {
		try {
			[programs, recent] = await Promise.all([trainingApi.programs(), trainingApi.sessions()]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	function startDay(dayId: number) {
		goto(`/training/log?day=${dayId}`);
	}
	function startEmpty() {
		goto('/training/log');
	}
	function resume(id: number) {
		goto(`/training/log?session=${id}`);
	}
</script>

<div class="flex items-center justify-between">
	<h1 class="text-xl font-semibold">Training</h1>
	<button
		onclick={startEmpty}
		class="rounded-full bg-brand px-4 py-2 text-sm font-medium text-white hover:brightness-110"
	>
		Empty workout
	</button>
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else}
	<!-- Resume a workout left in progress (navigated away mid-session) -->
	{#if inProgress.length > 0}
		<section class="mt-6">
			<h2 class="font-medium text-amber-400">In progress</h2>
			<div class="mt-3 space-y-2">
				{#each inProgress as s (s.id)}
					<div class="flex items-center justify-between gap-2 rounded-lg border border-amber-800/60 bg-amber-950/20 p-4">
						<div>
							<span class="font-medium">{s.name || 'Workout'}</span>
							<p class="text-xs text-neutral-500">
								Started {new Date(s.started_at).toLocaleString()} · {s.exercise_count} exercise(s)
							</p>
						</div>
						<button
							class="shrink-0 rounded-full bg-brand px-3 py-1.5 text-sm font-medium text-white hover:brightness-110"
							onclick={() => resume(s.id)}
						>
							Resume
						</button>
					</div>
				{/each}
			</div>
		</section>
	{/if}

	<!-- Active program: quick-start its days -->
	<section class="mt-6">
		{#if active}
			<div class="flex items-center justify-between">
				<h2 class="font-medium">
					{active.name}
					<span class="ml-1 rounded bg-green-900 px-2 py-0.5 text-xs text-green-300">Active</span>
				</h2>
				<a class="arrow-link" href={`/training/programs/${active.id}`}>Edit →</a>
			</div>
			{#if active.days.length === 0}
				<p class="mt-2 text-sm text-neutral-500">
					No training days yet. <a class="text-orange-400 hover:text-orange-300" href={`/training/programs/${active.id}`}>Add some →</a>
				</p>
			{:else}
				<div class="mt-3 grid gap-3 sm:grid-cols-2">
					{#each active.days as day (day.id)}
						<div class="flex items-center justify-between rounded-lg border border-neutral-800 p-4">
							<div>
								<span class="font-medium">{day.name}</span>
								<p class="text-xs text-neutral-500">{day.slots.length} exercise(s)</p>
							</div>
							<button
								class="rounded-full bg-brand px-3 py-1.5 text-sm font-medium text-white hover:brightness-110"
								onclick={() => startDay(day.id)}
							>
								Start
							</button>
						</div>
					{/each}
				</div>
			{/if}
		{:else}
			<p class="text-sm text-neutral-500">
				No active program.
				<a class="text-orange-400 hover:text-orange-300" href="/training/programs">Pick or create one →</a> to start workouts from a plan.
			</p>
		{/if}
	</section>

	<!-- Recent workouts -->
	<section class="mt-8">
		<h2 class="font-medium">Recent workouts</h2>
		{#if completed.length === 0}
			<p class="mt-2 text-sm text-neutral-500">No workouts logged yet.</p>
		{:else}
			<div class="mt-3 space-y-2">
				{#each completed.slice(0, 5) as s (s.id)}
					<a href="/training/history" class="block rounded-lg border border-neutral-800 p-4 transition hover:border-neutral-600">
						<div class="flex items-center justify-between">
							<span>{s.name || 'Workout'}</span>
							<span class="text-xs text-neutral-500">
								{new Date(s.started_at).toLocaleDateString()} · {s.exercise_count} exercise(s)
							</span>
						</div>
					</a>
				{/each}
			</div>
		{/if}
	</section>
{/if}
