<script lang="ts">
	import { onMount } from 'svelte';
	import {
		trainingApi,
		EXERCISE_CATEGORIES,
		type Exercise,
		type ExercisePerformance,
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
	import SearchSelect from '$lib/components/ui/SearchSelect.svelte';
	import { notificationsApi } from '$lib/notifications/api';

	let session = $state<WorkoutSession | null>(null);
	let exercises = $state<Exercise[]>([]);
	let programs = $state<Program[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let showExerciseModal = $state(false);
	let platesForSet = $state<number | null>(null);
	let replaceFor = $state<number | null>(null);

	const activeProgram = $derived(programs.find((p) => p.is_active) ?? null);
	const exOptions = $derived(
		exercises.map((ex) => ({ id: ex.id, label: ex.name, group: ex.category }))
	);

	interface Draft {
		weight: string;
		reps: string;
		set_type: string;
	}
	let pendingDraft = $state<Record<number, Draft>>({});

	const SET_TYPES = ['working', 'warmup', 'drop', 'top_set', 'backoff', 'amrap', 'failure'];

	// Seed an editable draft for each not-yet-logged set, pre-filled from the set
	// itself (a planned target weight carries over; an added set copies the
	// previous set's weight + type).
	$effect(() => {
		for (const le of session?.logged_exercises ?? []) {
			for (const s of le.sets) {
				if (!s.is_completed && !pendingDraft[s.id]) {
					pendingDraft[s.id] = {
						weight: s.weight ?? '',
						reps: s.reps != null ? String(s.reps) : '',
						set_type: s.set_type
					};
				}
			}
		}
	});

	// Per-exercise best-ever + last-time stats, for the at-a-glance line and to
	// pre-fill the next workout. Loaded lazily for whatever exercises are in the
	// session; a failure degrades to no stats (and no pre-fill).
	let perf = $state<Record<number, ExercisePerformance>>({});
	async function ensurePerf(ids: number[]) {
		const missing = [...new Set(ids)].filter((id) => !(id in perf));
		if (!missing.length) return;
		const results = await Promise.all(
			missing.map((id) =>
				trainingApi
					.lastPerformance(id)
					.catch(() => ({ best: null, last: null }) as ExercisePerformance)
			)
		);
		missing.forEach((id, i) => (perf[id] = results[i]));
	}
	$effect(() => {
		ensurePerf((session?.logged_exercises ?? []).map((le) => le.exercise));
	});

	// Pre-fill an untouched pending set from the matching set (by position) last
	// time — never clobbers what you've already typed or a planned weight.
	$effect(() => {
		for (const le of session?.logged_exercises ?? []) {
			const lastSets = perf[le.exercise]?.last?.sets;
			if (!lastSets) continue;
			le.sets.forEach((s, i) => {
				if (s.is_completed) return;
				const d = pendingDraft[s.id];
				const prior = lastSets[i];
				if (d && prior && s.weight == null && d.weight === '' && d.reps === '') {
					if (prior.weight != null) d.weight = prior.weight;
					if (prior.reps != null) d.reps = String(prior.reps);
				}
			});
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
			// Resume an existing (usually in-progress) session, or start from a day.
			const sessionParam = $page.url.searchParams.get('session');
			const dayParam = $page.url.searchParams.get('day');
			if (sessionParam) session = await trainingApi.session(Number(sessionParam));
			else if (dayParam) await startDay(Number(dayParam));
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

	// Start the rest countdown + schedule a backend "Rest over" notification (so it
	// fires even if the phone is locked). Ending the rest cancels the pending one.
	function startRest(seconds: number) {
		restTimer.start(seconds, { countdown: true });
		notificationsApi.scheduleRest(seconds);
	}
	function endRest() {
		restTimer.reset();
		notificationsApi.cancelRest();
	}

	async function logPending(s: LoggedSet) {
		const d = pendingDraft[s.id];
		if (!d) return;
		await trainingApi.updateLoggedSet(s.id, {
			set_type: d.set_type,
			reps: d.reps === '' ? null : Number(d.reps),
			weight: d.weight === '' ? null : String(Number(d.weight)),
			is_completed: true
		});
		startRest(s.rest_seconds ?? 90);
		await refresh();
	}

	// "+ Add set" — append another editable row, defaulting to the previous set's
	// type + weight ("one more like the last"). is_completed:false so it renders
	// as a pending row (the model defaults new sets to completed).
	async function addSet(le: LoggedExercise) {
		const last = le.sets[le.sets.length - 1];
		await trainingApi.createLoggedSet({
			logged_exercise: le.id,
			order: le.sets.length,
			set_type: last?.set_type ?? 'working',
			weight: last?.weight ?? null,
			reps: null,
			is_completed: false
		});
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
	async function onExerciseCreated(ex: Exercise) {
		exercises = [...exercises, ex].sort((a, b) => a.name.localeCompare(b.name));
		await addExercise(ex.id);
	}
	// Swap an exercise mid-workout (e.g. the machine is taken) — keeps the same
	// sets and set types attached to the logged exercise.
	async function replaceExercise(leId: number, exerciseId: number) {
		await trainingApi.updateLoggedExercise(leId, { exercise: exerciseId });
		replaceFor = null;
		await refresh();
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
		endRest();
	}

	// Abort = delete the session (cascades its exercises + sets) — no trace left.
	async function abortWorkout() {
		if (!session) return;
		if (!confirm('Discard this workout? It will be deleted with all its sets — this cannot be undone.'))
			return;
		try {
			await trainingApi.deleteSession(session.id);
			endRest();
			session = null;
			pendingDraft = {};
			perf = {};
			replaceFor = null;
			platesForSet = null;
		} catch (e) {
			error = (e as Error).message;
		}
	}

	function pendingE1rm(setId: number): number | null {
		const d = pendingDraft[setId];
		if (!d) return null;
		return estimated1rm(d.weight === '' ? null : Number(d.weight), d.reps === '' ? null : Number(d.reps));
	}
	const plateResult = $derived.by(() => {
		if (platesForSet == null) return null;
		const d = pendingDraft[platesForSet];
		if (!d || d.weight === '') return null;
		return platesPerSide(Number(d.weight));
	});
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
		class="mt-6 w-full rounded-full bg-brand px-4 py-3 font-medium text-white hover:brightness-110 sm:w-auto sm:px-6"
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
							class="shrink-0 rounded-full bg-brand px-4 py-2 text-sm font-medium text-white hover:brightness-110"
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
			No active program. <a class="text-orange-400 hover:text-orange-300" href="/training/programs">Build one</a> to start workouts from a plan.
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
			{@const best = perf[le.exercise]?.best}
			<div class="rounded-lg border border-neutral-800 p-3 sm:p-4">
				<div class="flex items-start justify-between gap-2">
					<div>
						<h2 class="font-medium">{le.exercise_name}</h2>
						{#if best}
							<p class="text-xs text-neutral-500">PR {best.weight} kg × {best.reps}{#if best.e1rm} · e1RM {best.e1rm}{/if}</p>
						{/if}
					</div>
					{#if !session.is_completed}
						<div class="flex shrink-0 items-center gap-3 text-xs text-neutral-500">
							<button class="text-base hover:text-white disabled:opacity-30" aria-label="Move up" disabled={ei === 0} onclick={() => moveExercise(ei, -1)}>↑</button>
							<button class="text-base hover:text-white disabled:opacity-30" aria-label="Move down" disabled={ei === session.logged_exercises.length - 1} onclick={() => moveExercise(ei, 1)}>↓</button>
							<button class="hover:text-white {replaceFor === le.id ? 'text-white' : ''}" onclick={() => (replaceFor = replaceFor === le.id ? null : le.id)}>Replace</button>
							<button class="text-red-400 hover:text-red-300" onclick={() => removeExercise(le.id)}>Remove</button>
						</div>
					{/if}
				</div>

				{#if !session.is_completed && replaceFor === le.id}
					<div class="mt-2 rounded-md border border-neutral-800 bg-neutral-900/50 p-2">
						<SearchSelect
							options={exOptions}
							groups={EXERCISE_CATEGORIES}
							placeholder="Replace with…"
							resetOnSelect
							onchange={(id) => replaceExercise(le.id, id)}
						/>
						<p class="mt-1 text-xs text-neutral-500">Swaps the exercise, keeping these sets and their types.</p>
					</div>
				{/if}

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
									<div class="flex items-center gap-2">
										<span class="text-xs text-neutral-500">Set {i + 1}</span>
										<select bind:value={pendingDraft[s.id].set_type} aria-label="Set type" class="rounded border border-neutral-700 bg-neutral-900 px-1.5 py-1 text-xs text-neutral-100">
											{#each SET_TYPES as t (t)}<option value={t}>{t}</option>{/each}
										</select>
										<button class="ml-auto text-xs text-neutral-500 hover:text-neutral-300" onclick={() => (platesForSet = platesForSet === s.id ? null : s.id)}>Plates</button>
										<button class="text-neutral-600 hover:text-red-400" aria-label="Remove set" onclick={() => deleteSet(s.id)}>✕</button>
									</div>
									<div class="mt-2 grid grid-cols-2 gap-2">
										<StepperInput label="Weight" step={2.5} bind:value={pendingDraft[s.id].weight} placeholder="kg" />
										<StepperInput label="Reps" step={1} inputmode="numeric" bind:value={pendingDraft[s.id].reps} placeholder="reps" />
									</div>
									<button class="mt-2 w-full rounded-full bg-brand px-3 py-2.5 text-sm font-medium text-white hover:brightness-110" onclick={() => logPending(s)}>Log</button>
									{#if pendingE1rm(s.id) !== null}
										<p class="mt-1 text-xs text-neutral-500">Est. 1RM: {pendingE1rm(s.id)} kg</p>
									{/if}
									{#if platesForSet === s.id && plateResult}
										<p class="mt-1 text-xs text-neutral-400">
											Per side (20 kg bar): {plateResult.perSide.length ? plateResult.perSide.join(' + ') + ' kg' : 'just the bar'}
											{#if plateResult.remainder > 0}· {plateResult.remainder} kg not loadable{/if}
										</p>
									{/if}
								</div>
							{/if}
						{/each}
					</div>
				{/if}

				{#if !session.is_completed}
					<button
						class="mt-3 w-full rounded-md border border-dashed border-neutral-700 px-3 py-2 text-sm text-neutral-300 hover:border-neutral-500 hover:text-white"
						onclick={() => addSet(le)}
					>
						+ Add set
					</button>
				{/if}
			</div>
		{/each}
	</div>

	{#if !session.is_completed}
		<div class="mt-5 flex items-center gap-2">
			<div class="flex-1">
				<SearchSelect
					options={exOptions}
					groups={EXERCISE_CATEGORIES}
					placeholder="+ Add exercise to workout…"
					resetOnSelect
					onchange={(id) => addExercise(id)}
				/>
			</div>
			<button
				type="button"
				class="shrink-0 rounded-md border border-neutral-700 px-3 py-2.5 text-sm text-indigo-300 hover:border-neutral-500"
				onclick={() => (showExerciseModal = true)}
			>
				＋ New
			</button>
		</div>

		<!-- Primary action lives at the bottom so it's reachable right after the last set. -->
		<div class="mt-6">
			<button
				class="w-full rounded-full bg-brand px-4 py-3 text-base font-medium text-white hover:brightness-110"
				onclick={finish}
			>
				Finish workout
			</button>
		</div>
		<div class="mt-3">
			<button
				class="w-full rounded-md border border-red-900/60 px-4 py-2.5 text-sm text-red-400 hover:bg-red-950/40"
				onclick={abortWorkout}
			>
				Cancel workout
			</button>
		</div>
	{/if}

	<p class="mt-6 text-sm">
		<a class="arrow-link" href="/training/history">View history</a>
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
			<button class="rounded-md border border-neutral-500/40 px-3 py-1 text-sm hover:bg-white/10" onclick={endRest}>
				{restTimer.overTarget ? 'Done' : 'Skip'}
			</button>
		</div>
	{/if}
{/if}
