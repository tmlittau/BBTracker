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
	import { estimated1rm, formatDuration, platesPerSide } from '$lib/training/calc';
	import ExerciseCreateModal from '$lib/training/ExerciseCreateModal.svelte';
	import Button from '$lib/components/ui/Button.svelte';

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
		rpe: string;
	}
	// Inline inputs for completing a pre-loaded (pending) set, keyed by set id.
	let pendingDraft = $state<Record<number, Draft>>({});
	// "Next set" entry row for ad-hoc/extra sets, keyed by logged-exercise id.
	let exDraft = $state<Record<number, Draft & { set_type: string }>>({});

	const SET_TYPES = ['working', 'warmup', 'drop', 'top_set', 'backoff', 'amrap', 'failure'];
	const NEW_EXERCISE = '__new__';

	// Make sure every exercise/pending set has a draft so the template can bind.
	$effect(() => {
		for (const le of session?.logged_exercises ?? []) {
			if (!exDraft[le.id]) exDraft[le.id] = { weight: '', reps: '', rpe: '', set_type: 'working' };
			for (const s of le.sets) {
				if (!s.is_completed && !pendingDraft[s.id]) pendingDraft[s.id] = { weight: '', reps: '', rpe: '' };
			}
		}
	});

	onMount(async () => {
		try {
			[exercises, programs] = await Promise.all([trainingApi.exercises(), trainingApi.programs()]);
			// Quick-start: /training/log?day=N pre-loads that program day.
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
			rpe: d.rpe === '' ? null : String(Number(d.rpe)),
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
			reps: d.reps === '' ? null : Number(d.reps),
			rpe: d.rpe === '' ? null : String(Number(d.rpe))
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

	const fieldClass = 'rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100';
</script>

<ExerciseCreateModal bind:open={showExerciseModal} oncreated={onExerciseCreated} />

<div class="flex items-center justify-between">
	<h1 class="text-xl font-semibold">Workout logger</h1>
	{#if session && !session.is_completed}
		<Button onclick={finish}>Finish workout</Button>
	{/if}
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if !session}
	<!-- Entry screen: empty workout + the active program's days -->
	<div class="mt-6">
		<div class="mx-auto w-48"><Button onclick={startEmpty}>Start empty workout</Button></div>
	</div>

	{#if activeProgram && activeProgram.days.length}
		<section class="mt-8">
			<h2 class="font-medium">{activeProgram.name} — start a day</h2>
			<p class="mt-1 text-xs text-neutral-500">Pre-loads the day's exercises and planned sets.</p>
			<div class="mt-3 grid gap-3 sm:grid-cols-2">
				{#each activeProgram.days as day (day.id)}
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
		</section>
	{:else}
		<p class="mt-6 text-sm text-neutral-500">
			No active program. <a class="text-indigo-400" href="/training/programs">Build one →</a> to start workouts from a plan.
		</p>
	{/if}
{:else}
	<!-- Rest timer (counts down from the logged set's rest) -->
	{#if restTimer.running}
		<div
			class="mt-4 flex items-center justify-between rounded-lg border px-4 py-2 {restTimer.overTarget
				? 'border-green-600 text-green-300'
				: 'border-indigo-600 text-indigo-200'}"
			data-testid="rest-timer"
		>
			<span class="text-sm">{restTimer.overTarget ? 'Rest complete' : 'Rest'}</span>
			<span class="font-mono text-lg">{formatDuration(restTimer.display)}</span>
			<button class="text-sm text-neutral-400 hover:text-white" onclick={() => restTimer.reset()}>Stop</button>
		</div>
	{/if}

	{#if session.is_completed}
		<p class="mt-4 rounded bg-green-950 px-3 py-2 text-sm text-green-300">
			Workout finished — {session.logged_exercises.length} exercise(s) logged.
		</p>
	{/if}

	<div class="mt-6 space-y-6">
		{#each session.logged_exercises as le, ei (le.id)}
			<div class="rounded-lg border border-neutral-800 p-4">
				<div class="flex items-center justify-between">
					<h2 class="font-medium">{le.exercise_name}</h2>
					{#if !session.is_completed}
						<div class="flex items-center gap-2 text-xs text-neutral-500">
							<button class="hover:text-white disabled:opacity-30" aria-label="Move up" disabled={ei === 0} onclick={() => moveExercise(ei, -1)}>↑</button>
							<button class="hover:text-white disabled:opacity-30" aria-label="Move down" disabled={ei === session.logged_exercises.length - 1} onclick={() => moveExercise(ei, 1)}>↓</button>
							<button class="text-red-400 hover:text-red-300" onclick={() => removeExercise(le.id)}>Remove</button>
						</div>
					{/if}
				</div>

				{#if le.sets.length > 0}
					<table class="mt-3 w-full text-sm">
						<thead class="text-xs text-neutral-500">
							<tr>
								<th class="text-left font-normal">#</th>
								<th class="text-left font-normal">Type</th>
								<th class="text-right font-normal">Weight</th>
								<th class="text-right font-normal">Reps</th>
								<th class="text-right font-normal">e1RM</th>
								<th></th>
							</tr>
						</thead>
						<tbody>
							{#each le.sets as s, i (s.id)}
								{#if s.is_completed}
									<tr class="border-t border-neutral-800 bg-green-950/40" data-testid="set-completed">
										<td class="py-1 text-neutral-500">{i + 1}</td>
										<td class="py-1">
											{s.set_type}
											{#if s.is_pr}<span class="ml-1 rounded bg-yellow-900 px-1 text-xs text-yellow-300">PR</span>{/if}
										</td>
										<td class="py-1 text-right">{s.weight ?? '—'}</td>
										<td class="py-1 text-right">{s.reps ?? '—'}</td>
										<td class="py-1 text-right text-neutral-400">{s.e1rm ?? '—'}</td>
										<td class="py-1 text-right">
											{#if !session.is_completed}
												<button class="text-xs text-neutral-600 hover:text-red-400" aria-label="Remove set" onclick={() => deleteSet(s.id)}>✕</button>
											{/if}
										</td>
									</tr>
								{:else if !session.is_completed && pendingDraft[s.id]}
									<!-- Pending (planned) set — fill + Log turns it green -->
									<tr class="border-t border-neutral-800" data-testid="set-pending">
										<td class="py-1 text-neutral-500">{i + 1}</td>
										<td class="py-1 text-neutral-400">{s.set_type}</td>
										<td class="py-1 text-right"><input class="w-20 text-right {fieldClass}" type="number" step="0.5" inputmode="decimal" placeholder="kg" bind:value={pendingDraft[s.id].weight} /></td>
										<td class="py-1 text-right"><input class="w-16 text-right {fieldClass}" type="number" inputmode="numeric" placeholder="reps" bind:value={pendingDraft[s.id].reps} /></td>
										<td class="py-1 text-right"><input class="w-14 text-right {fieldClass}" type="number" step="0.5" min="1" max="10" placeholder="RPE" bind:value={pendingDraft[s.id].rpe} /></td>
										<td class="py-1 text-right">
											<button class="rounded bg-indigo-600 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-500" onclick={() => logPending(s)}>Log</button>
										</td>
									</tr>
								{/if}
							{/each}
						</tbody>
					</table>
				{/if}

				{#if !session.is_completed && exDraft[le.id]}
					<!-- Add an extra / freeform set -->
					<div class="mt-3 flex flex-wrap items-end gap-2">
						<label class="flex flex-col text-xs text-neutral-500">
							Type
							<select bind:value={exDraft[le.id].set_type} class="mt-1 {fieldClass}">
								{#each SET_TYPES as t (t)}<option value={t}>{t}</option>{/each}
							</select>
						</label>
						<label class="flex flex-col text-xs text-neutral-500">
							Weight
							<input type="number" step="0.5" inputmode="decimal" bind:value={exDraft[le.id].weight} class="mt-1 w-24 {fieldClass}" />
						</label>
						<label class="flex flex-col text-xs text-neutral-500">
							Reps
							<input type="number" inputmode="numeric" bind:value={exDraft[le.id].reps} class="mt-1 w-20 {fieldClass}" />
						</label>
						<label class="flex flex-col text-xs text-neutral-500">
							RPE
							<input type="number" step="0.5" min="1" max="10" bind:value={exDraft[le.id].rpe} class="mt-1 w-16 {fieldClass}" />
						</label>
						<button class="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500" onclick={() => logNew(le)}>Log set</button>
						<button class="rounded-md border border-neutral-700 px-3 py-1.5 text-sm hover:border-neutral-500" onclick={() => (showPlatesFor = showPlatesFor === le.id ? null : le.id)}>Plates</button>
					</div>
					{#if liveE1rm(le.id) !== null}
						<p class="mt-2 text-xs text-neutral-500">Estimated 1RM for this set: {liveE1rm(le.id)} kg</p>
					{/if}
					{#if showPlatesFor === le.id && plateResult}
						<p class="mt-1 text-xs text-neutral-400">
							Per side (20 kg bar): {plateResult.perSide.length ? plateResult.perSide.join(' + ') + ' kg' : 'just the bar'}
							{#if plateResult.remainder > 0}· {plateResult.remainder} kg not loadable{/if}
						</p>
					{/if}
				{/if}
			</div>
		{/each}
	</div>

	{#if !session.is_completed}
		<div class="mt-6">
			<select
				value=""
				onchange={(e) => {
					onPick(e.currentTarget.value);
					e.currentTarget.value = '';
				}}
				class="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
			>
				<option value="">+ Add exercise to workout…</option>
				<option value={NEW_EXERCISE}>＋ New custom exercise…</option>
				{#each exercises as ex (ex.id)}
					<option value={ex.id}>{ex.name}</option>
				{/each}
			</select>
		</div>
	{/if}

	<p class="mt-6 text-sm">
		<a class="text-indigo-400 hover:text-indigo-300" href="/training/history">View history →</a>
	</p>
{/if}
