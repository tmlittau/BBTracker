<script lang="ts">
	import { onMount } from 'svelte';
	import {
		trainingApi,
		type Exercise,
		type LoggedExercise,
		type LoggedSet,
		type Program,
		type WorkoutSession
	} from '$lib/training/api';
	import { page } from '$app/stores';
	import { restTimer } from '$lib/training/restTimer.svelte';
	import { estimated1rm, formatClock, formatDuration, formatHM, platesPerSide } from '$lib/training/calc';
	import ExerciseCreateModal from '$lib/training/ExerciseCreateModal.svelte';
	import StepperInput from '$lib/training/StepperInput.svelte';

	let session = $state<WorkoutSession | null>(null);
	let exercises = $state<Exercise[]>([]);
	let programs = $state<Program[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let showExerciseModal = $state(false);
	let showPlatesFor = $state<number | null>(null);

	const activeProgram = $derived(programs.find((p) => p.is_active) ?? null);

	interface Draft {
		weight: string;
		reps: string;
	}
	let pendingDraft = $state<Record<number, Draft>>({});
	let exDraft = $state<Record<number, Draft & { set_type: string }>>({});

	const SET_TYPES = ['working', 'warmup', 'drop', 'top_set', 'backoff', 'amrap', 'failure'];
	const NEW_EXERCISE = '__new__';

	$effect(() => {
		for (const le of session?.logged_exercises ?? []) {
			if (!exDraft[le.id]) exDraft[le.id] = { weight: '', reps: '', set_type: 'working' };
			for (const s of le.sets) {
				if (!s.is_completed && !pendingDraft[s.id]) pendingDraft[s.id] = { weight: '', reps: '' };
			}
		}
	});

	// Live workout clock — ticks each second while in progress so you can keep an
	// eye on total time (e.g. staying under 90 minutes). Frozen at the duration
	// once finished.
	let now = $state(Date.now());
	$effect(() => {
		if (!session || session.is_completed) return;
		const id = setInterval(() => (now = Date.now()), 1000);
		return () => clearInterval(id);
	});
	const elapsedSeconds = $derived.by(() => {
		if (!session) return 0;
		const end = session.is_completed && session.ended_at ? new Date(session.ended_at).getTime() : now;
		return Math.max(0, Math.floor((end - new Date(session.started_at).getTime()) / 1000));
	});

	onMount(async () => {
		try {
			[exercises, programs] = await Promise.all([trainingApi.exercises(), trainingApi.programs()]);
			const dayParam = $page.url.searchParams.get('day');
			if (dayParam) await startDay(Number(dayParam));
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	async function refresh() {
		if (session) session = await trainingApi.session(session.id);
	}

	async function startEmpty() {
		session = await trainingApi.createSession({ name: 'Workout', started_at: new Date().toISOString() });
	}
	async function startDay(dayId: number) {
		session = await trainingApi.startFromDay(dayId);
	}

	function restForExercise(le: LoggedExercise): number {
		const withRest = le.sets.filter((s) => s.rest_seconds != null);
		return withRest.length ? (withRest[withRest.length - 1].rest_seconds as number) : 90;
	}

	async function logPending(s: LoggedSet) {
		const d = pendingDraft[s.id];
		if (!d) return;
		await trainingApi.updateLoggedSet(s.id, {
			reps: d.reps === '' ? null : Number(d.reps),
			weight: d.weight === '' ? null : String(Number(d.weight)),
			is_completed: true
		});
		restTimer.start(s.rest_seconds ?? 90, { countdown: true });
		await refresh();
	}

	async function logNew(le: LoggedExercise) {
		const d = exDraft[le.id];
		if (!d) return;
		await trainingApi.createLoggedSet({
			logged_exercise: le.id,
			order: le.sets.length,
			set_type: d.set_type,
			weight: d.weight === '' ? null : String(Number(d.weight)),
			reps: d.reps === '' ? null : Number(d.reps)
		});
		d.reps = '';
		restTimer.start(restForExercise(le), { countdown: true });
		await refresh();
	}

	async function deleteSet(id: number) {
		await trainingApi.deleteLoggedSet(id);
		await refresh();
	}

	async function addExercise(exerciseId: number) {
		if (!session || !exerciseId) return;
		await trainingApi.createLoggedExercise({
			session: session.id,
			exercise: exerciseId,
			order: session.logged_exercises.length
		});
		await refresh();
	}
	function onPick(value: string) {
		if (value === NEW_EXERCISE) showExerciseModal = true;
		else if (value) addExercise(Number(value));
	}
	async function onExerciseCreated(ex: Exercise) {
		exercises = [...exercises, ex].sort((a, b) => a.name.localeCompare(b.name));
		await addExercise(ex.id);
	}
	async function removeExercise(id: number) {
		await trainingApi.deleteLoggedExercise(id);
		await refresh();
	}
	async function moveExercise(index: number, dir: -1 | 1) {
		if (!session) return;
		const arr = [...session.logged_exercises];
		const j = index + dir;
		if (j < 0 || j >= arr.length) return;
		[arr[index], arr[j]] = [arr[j], arr[index]];
		session.logged_exercises = arr;
		await trainingApi.reorderLoggedExercises(arr.map((le, i) => ({ id: le.id, order: i })));
		await refresh();
	}

	const incompleteCount = $derived(
		session?.logged_exercises.flatMap((le) => le.sets).filter((s) => !s.is_completed).length ?? 0
	);

	async function finish() {
		if (!session) return;
		if (incompleteCount > 0) {
			if (!confirm(`${incompleteCount} set(s) not completed — finish anyway and log only the completed ones?`)) return;
			session = await trainingApi.finishSession(session.id, true);
		} else {
			session = await trainingApi.finishSession(session.id, false);
		}
		restTimer.reset();
	}

	function liveE1rm(leId: number): number | null {
		const d = exDraft[leId];
		if (!d) return null;
		return estimated1rm(d.weight === '' ? null : Number(d.weight), d.reps === '' ? null : Number(d.reps));
	}
	const plateResult = $derived.by(() => {
		if (showPlatesFor == null) return null;
		const d = exDraft[showPlatesFor];
		if (!d || d.weight === '') return null;
		return platesPerSide(Number(d.weight));
	});

	const fieldClass = 'rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100';
</script>

<ExerciseCreateModal bind:open={showExerciseModal} oncreated={onExerciseCreated} />

<div class="flex items-center justify-between gap-3">
	<h1 class="text-xl font-semibold">Workout logger</h1>
	{#if session}
		<span
			data-testid="workout-clock"
			class="shrink-0 font-mono text-sm tabular-nums {elapsedSeconds >= 5400
				? 'text-red-400'
				: elapsedSeconds >= 4500
					? 'text-amber-400'
					: 'text-neutral-400'}"
			title="Total workout time"
		>
			⏱ {session.is_completed ? formatHM(elapsedSeconds) : formatClock(elapsedSeconds)}
		</span>
	{/if}
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if !session}
	<!-- Entry screen: empty workout + the active program's days -->
	<button
		class="mt-6 w-full rounded-md bg-indigo-600 px-4 py-3 font-medium text-white hover:bg-indigo-500 sm:w-auto sm:px-6"
		onclick={startEmpty}
	>
		Start empty workout
	</button>

	{#if activeProgram && activeProgram.days.length}
		<section class="mt-8">
			<h2 class="font-medium">{activeProgram.name} — start a day</h2>
			<p class="mt-1 text-xs text-neutral-500">Pre-loads the day's exercises and planned sets.</p>
			<div class="mt-3 grid gap-3 sm:grid-cols-2">
				{#each activeProgram.days as day (day.id)}
					<div class="flex items-center justify-between gap-3 rounded-lg border border-neutral-800 p-4">
						<div>
							<span class="font-medium">{day.name}</span>
							<p class="text-xs text-neutral-500">{day.slots.length} exercise(s)</p>
						</div>
						<button
							class="shrink-0 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
							onclick={() => startDay(day.id)}
						>
							Start
						</button>
					</div>
				{/each}
			</div>
		</section>
	{:else}
		<p class="mt-6 text-sm text-neutral-500">
			No active program. <a class="text-indigo-400" href="/training/programs">Build one →</a> to start workouts from a plan.
		</p>
	{/if}
{:else}
	{#if session.is_completed}
		<p class="mt-4 rounded bg-green-950 px-3 py-2 text-sm text-green-300">
			Workout finished — {session.logged_exercises.length} exercise(s) logged in {formatHM(elapsedSeconds)}.
		</p>
	{/if}

	<div class="mt-5 space-y-5">
		{#each session.logged_exercises as le, ei (le.id)}
			<div class="rounded-lg border border-neutral-800 p-3 sm:p-4">
				<div class="flex items-center justify-between gap-2">
					<h2 class="font-medium">{le.exercise_name}</h2>
					{#if !session.is_completed}
						<div class="flex items-center gap-3 text-xs text-neutral-500">
							<button class="text-base hover:text-white disabled:opacity-30" aria-label="Move up" disabled={ei === 0} onclick={() => moveExercise(ei, -1)}>↑</button>
							<button class="text-base hover:text-white disabled:opacity-30" aria-label="Move down" disabled={ei === session.logged_exercises.length - 1} onclick={() => moveExercise(ei, 1)}>↓</button>
							<button class="text-red-400 hover:text-red-300" onclick={() => removeExercise(le.id)}>Remove</button>
						</div>
					{/if}
				</div>

				{#if le.sets.length > 0}
					<div class="mt-3 space-y-2">
						{#each le.sets as s, i (s.id)}
							{#if s.is_completed}
								<div data-testid="set-completed" class="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-green-800/50 bg-green-950/40 px-3 py-2 text-sm">
									<span class="w-5 shrink-0 text-neutral-500">{i + 1}</span>
									<span class="text-neutral-300">{s.set_type}</span>
									{#if s.is_pr}<span class="rounded bg-yellow-900 px-1 text-xs text-yellow-300">PR</span>{/if}
									<span class="ml-auto font-medium tabular-nums">{s.weight ?? '—'} × {s.reps ?? '—'}</span>
									<span class="text-xs text-neutral-500">e1RM {s.e1rm ?? '—'}</span>
									{#if !session.is_completed}
										<button class="text-neutral-600 hover:text-red-400" aria-label="Remove set" onclick={() => deleteSet(s.id)}>✕</button>
									{/if}
								</div>
							{:else if !session.is_completed && pendingDraft[s.id]}
								<div data-testid="set-pending" class="rounded-md border border-neutral-800 p-3">
									<div class="text-xs text-neutral-400">Set {i + 1} · {s.set_type}</div>
									<div class="mt-2 grid grid-cols-2 gap-2">
										<StepperInput label="Weight" step={2.5} bind:value={pendingDraft[s.id].weight} placeholder="kg" />
										<StepperInput label="Reps" step={1} inputmode="numeric" bind:value={pendingDraft[s.id].reps} placeholder="reps" />
									</div>
									<div class="mt-2">
										<button class="w-full rounded-md bg-indigo-600 px-3 py-2.5 text-sm font-medium text-white hover:bg-indigo-500" onclick={() => logPending(s)}>Log</button>
									</div>
								</div>
							{/if}
						{/each}
					</div>
				{/if}

				{#if !session.is_completed && exDraft[le.id]}
					<!-- Add an extra / freeform set -->
					<div class="mt-3 space-y-2 border-t border-neutral-800 pt-3">
						<div class="flex gap-2">
							<label class="flex flex-1 flex-col text-xs text-neutral-500">Type
								<select bind:value={exDraft[le.id].set_type} class="mt-1 {fieldClass}">
									{#each SET_TYPES as t (t)}<option value={t}>{t}</option>{/each}
								</select>
							</label>
						</div>
						<div class="grid grid-cols-2 gap-2">
							<StepperInput label="Weight" step={2.5} bind:value={exDraft[le.id].weight} placeholder="kg" />
							<StepperInput label="Reps" step={1} inputmode="numeric" bind:value={exDraft[le.id].reps} placeholder="reps" />
						</div>
						<div class="flex gap-2">
							<button class="flex-1 rounded-md bg-indigo-600 px-3 py-2.5 text-sm font-medium text-white hover:bg-indigo-500" onclick={() => logNew(le)}>Log set</button>
							<button class="rounded-md border border-neutral-700 px-3 py-2.5 text-sm hover:border-neutral-500" onclick={() => (showPlatesFor = showPlatesFor === le.id ? null : le.id)}>Plates</button>
						</div>
						{#if liveE1rm(le.id) !== null}
							<p class="text-xs text-neutral-500">Estimated 1RM for this set: {liveE1rm(le.id)} kg</p>
						{/if}
						{#if showPlatesFor === le.id && plateResult}
							<p class="text-xs text-neutral-400">
								Per side (20 kg bar): {plateResult.perSide.length ? plateResult.perSide.join(' + ') + ' kg' : 'just the bar'}
								{#if plateResult.remainder > 0}· {plateResult.remainder} kg not loadable{/if}
							</p>
						{/if}
					</div>
				{/if}
			</div>
		{/each}
	</div>

	{#if !session.is_completed}
		<div class="mt-5">
			<select
				value=""
				onchange={(e) => {
					onPick(e.currentTarget.value);
					e.currentTarget.value = '';
				}}
				class="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2.5 text-sm text-neutral-100"
			>
				<option value="">+ Add exercise to workout…</option>
				<option value={NEW_EXERCISE}>＋ New custom exercise…</option>
				{#each exercises as ex (ex.id)}
					<option value={ex.id}>{ex.name}</option>
				{/each}
			</select>
		</div>

		<!-- Primary action lives at the bottom so it's reachable right after the last set. -->
		<div class="mt-6">
			<button
				class="w-full rounded-md bg-indigo-600 px-4 py-3 text-base font-medium text-white hover:bg-indigo-500"
				onclick={finish}
			>
				Finish workout
			</button>
		</div>
	{/if}

	<p class="mt-6 text-sm">
		<a class="text-indigo-400 hover:text-indigo-300" href="/training/history">View history →</a>
	</p>

	<!-- Sticky floating rest countdown (above the mobile tab bar). -->
	{#if restTimer.running}
		<div
			data-testid="rest-timer"
			class="fixed inset-x-3 bottom-20 z-40 mx-auto flex max-w-md items-center justify-between gap-3 rounded-xl border px-4 py-3 shadow-xl backdrop-blur md:bottom-6 {restTimer.overTarget
				? 'border-green-600 bg-green-950/90 text-green-200'
				: 'border-indigo-600 bg-indigo-950/90 text-indigo-100'}"
		>
			<span class="text-sm">{restTimer.overTarget ? 'Rest complete' : 'Rest'}</span>
			<span class="font-mono text-2xl tabular-nums">{formatDuration(restTimer.display)}</span>
			<button class="rounded-md border border-neutral-500/40 px-3 py-1 text-sm hover:bg-white/10" onclick={() => restTimer.reset()}>
				{restTimer.overTarget ? 'Done' : 'Skip'}
			</button>
		</div>
	{/if}
{/if}
