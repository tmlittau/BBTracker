<script lang="ts">
	import { onMount } from 'svelte';
	import {
		trainingApi,
		type ExerciseHistoryPoint,
		type Exercise,
		type MuscleVolume,
		type WorkoutSessionListItem
	} from '$lib/training/api';
	import { formatHM, durationSeconds } from '$lib/training/calc';
	import { isoDate, shiftISODate } from '$lib/date';
	import Card from '$lib/components/ui/Card.svelte';

	let sessions = $state<WorkoutSessionListItem[]>([]);
	let exercises = $state<Exercise[]>([]);
	let volume = $state<MuscleVolume[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	let selectedExercise = $state<number | null>(null);
	let history = $state<ExerciseHistoryPoint[]>([]);

	// Date-bounded workout list so we don't pull the entire history (defaults to
	// the last 30 days; widen as needed).
	let from = $state(shiftISODate(isoDate(), -30));
	let to = $state(isoDate());

	async function loadSessions() {
		sessions = await trainingApi.sessions({ from, to });
	}

	onMount(async () => {
		try {
			[, exercises, volume] = await Promise.all([
				loadSessions(),
				trainingApi.exercises(),
				trainingApi.volume(30)
			]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	async function loadHistory() {
		if (selectedExercise == null) {
			history = [];
			return;
		}
		history = await trainingApi.exerciseHistory(selectedExercise);
	}

	const maxE1rm = $derived(
		Math.max(1, ...history.map((h) => (h.best_e1rm ? Number(h.best_e1rm) : 0)))
	);
</script>

<h1 class="text-xl font-semibold">History</h1>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else}
	<section class="mt-6">
		<h2 class="font-medium">Per-exercise progression</h2>
		<select
			bind:value={selectedExercise}
			onchange={() => loadHistory()}
			class="mt-2 w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
		>
			<option value={null}>Choose an exercise…</option>
			{#each exercises as ex (ex.id)}
				<option value={ex.id}>{ex.name}</option>
			{/each}
		</select>

		{#if selectedExercise != null}
			{#if history.length === 0}
				<p class="mt-3 text-sm text-neutral-500">No logged sets for this exercise yet.</p>
			{:else}
				<div class="mt-4 space-y-1">
					{#each history as point (point.session_id)}
						<div class="flex items-center gap-3 text-sm">
							<span class="w-24 shrink-0 text-neutral-500">{point.date}</span>
							<div class="h-5 flex-1 rounded bg-neutral-900">
								<div
									class="flex h-5 items-center rounded bg-indigo-600 px-2 text-xs"
									style="width: {point.best_e1rm
										? (Number(point.best_e1rm) / maxE1rm) * 100
										: 0}%"
								>
									{point.best_e1rm ?? '—'}
								</div>
							</div>
							<span class="w-20 shrink-0 text-right text-xs text-neutral-500">
								{point.top_weight ?? '—'} kg
							</span>
						</div>
					{/each}
					<p class="pt-2 text-xs text-neutral-500">Bars show estimated 1RM (kg) over time.</p>
				</div>
			{/if}
		{/if}
	</section>

	<section class="mt-8">
		<h2 class="font-medium">Weekly volume by muscle (last 30 days)</h2>
		{#if volume.length === 0}
			<p class="mt-2 text-sm text-neutral-500">No working sets logged in this window.</p>
		{:else}
			<div class="mt-3 grid gap-2 sm:grid-cols-2">
				{#each volume as v (v.muscle)}
					<div class="flex items-center justify-between rounded border border-neutral-800 px-3 py-2 text-sm">
						<span>{v.muscle}</span>
						<span class="text-neutral-400">{v.sets} sets · {Number(v.tonnage).toLocaleString()} kg</span>
					</div>
				{/each}
			</div>
		{/if}
	</section>

	<section class="mt-8">
		<div class="flex flex-wrap items-end justify-between gap-2">
			<h2 class="font-medium">All workouts</h2>
			<div class="flex items-end gap-2">
				<label class="flex flex-col text-xs text-neutral-500">From
					<input type="date" bind:value={from} max={to} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100" />
				</label>
				<label class="flex flex-col text-xs text-neutral-500">To
					<input type="date" bind:value={to} min={from} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100" />
				</label>
				<button class="rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500" onclick={loadSessions}>Show</button>
			</div>
		</div>
		{#if sessions.length === 0}
			<p class="mt-2 text-sm text-neutral-500">No workouts in this range.</p>
		{:else}
			<div class="mt-3 space-y-2">
				{#each sessions as s (s.id)}
					<a href={`/training/history/${s.id}`} class="block transition hover:opacity-80">
						<Card>
							<div class="flex items-center justify-between gap-2">
								<span class="font-medium">{s.name || 'Workout'}</span>
								<span class="text-right text-xs text-neutral-500">
									{new Date(s.started_at).toLocaleDateString()} · {s.exercise_count} exercise(s)
									{#if s.is_completed && s.ended_at}· ⏱ {formatHM(durationSeconds(s.started_at, s.ended_at))}{/if}
									{#if !s.is_completed}· <span class="text-amber-400">in progress</span>{/if}
									<span class="ml-1 text-neutral-600">›</span>
								</span>
							</div>
						</Card>
					</a>
				{/each}
			</div>
		{/if}
	</section>
{/if}
