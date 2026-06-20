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
	import LineChart from '$lib/components/ui/LineChart.svelte';
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

	async function removeSession(id: number) {
		if (!confirm('Delete this workout and all its logged sets? This cannot be undone.')) return;
		try {
			await trainingApi.deleteSession(id);
			await loadSessions();
		} catch (e) {
			error = (e as Error).message;
		}
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

	const weightSeries = $derived([
		{ points: history.map((h) => ({ x: h.date, y: Number(h.top_weight ?? 0) })), color: '#6366f1', dots: true }
	]);
	const volumeSeries = $derived([
		{ points: history.map((h) => ({ x: h.date, y: Number(h.volume) })), color: '#10b981', dots: true }
	]);
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
				<div class="mt-4 grid gap-4 sm:grid-cols-2">
					<div>
						<p class="mb-1 text-xs font-medium text-neutral-400">Max weight per session (kg)</p>
						<LineChart series={weightSeries} unit="kg" baselineZero />
					</div>
					<div>
						<p class="mb-1 text-xs font-medium text-neutral-400">Total volume per session (kg)</p>
						<LineChart series={volumeSeries} unit="kg" baselineZero />
					</div>
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
				<button class="rounded-full bg-brand px-3 py-2 text-sm font-medium text-white hover:brightness-110" onclick={loadSessions}>Show</button>
			</div>
		</div>
		{#if sessions.length === 0}
			<p class="mt-2 text-sm text-neutral-500">No workouts in this range.</p>
		{:else}
			<div class="mt-3 space-y-2">
				{#each sessions as s (s.id)}
					<div class="flex items-stretch gap-2">
						<a href={`/training/history/${s.id}`} class="block flex-1 transition hover:opacity-80">
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
						<button
							class="shrink-0 rounded-lg border border-neutral-800 px-3 text-sm text-neutral-500 hover:border-red-800 hover:text-red-400"
							onclick={() => removeSession(s.id)}
							aria-label="Delete workout"
						>
							✕
						</button>
					</div>
				{/each}
			</div>
		{/if}
	</section>
{/if}
