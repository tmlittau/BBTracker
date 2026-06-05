<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { trainingApi, type Program, type WorkoutSessionListItem } from '$lib/training/api';

	let programs = $state<Program[]>([]);
	let recent = $state<WorkoutSessionListItem[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	const active = $derived(programs.find((p) => p.is_active) ?? null);

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
</script>

<div class="flex items-center justify-between">
	<h1 class="text-xl font-semibold">Training</h1>
	<button
		onclick={startEmpty}
		class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
	>
		Empty workout
	</button>
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else}
	<!-- Active program: quick-start its days -->
	<section class="mt-6">
		{#if active}
			<div class="flex items-center justify-between">
				<h2 class="font-medium">
					{active.name}
					<span class="ml-1 rounded bg-green-900 px-2 py-0.5 text-xs text-green-300">Active</span>
				</h2>
				<a class="text-sm text-indigo-400 hover:text-indigo-300" href={`/training/programs/${active.id}`}>Edit →</a>
			</div>
			{#if active.days.length === 0}
				<p class="mt-2 text-sm text-neutral-500">
					No training days yet. <a class="text-indigo-400" href={`/training/programs/${active.id}`}>Add some →</a>
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
								class="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500"
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
				<a class="text-indigo-400" href="/training/programs">Pick or create one →</a> to start workouts from a plan.
			</p>
		{/if}
	</section>

	<!-- Recent workouts -->
	<section class="mt-8">
		<h2 class="font-medium">Recent workouts</h2>
		{#if recent.length === 0}
			<p class="mt-2 text-sm text-neutral-500">No workouts logged yet.</p>
		{:else}
			<div class="mt-3 space-y-2">
				{#each recent.slice(0, 5) as s (s.id)}
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
