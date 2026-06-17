<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { dndzone } from 'svelte-dnd-action';
	import {
		trainingApi,
		EXERCISE_CATEGORIES,
		type Exercise,
		type ExerciseSlot,
		type PlannedSet,
		type Program,
		type TrainingDay
	} from '$lib/training/api';
	import ExerciseCreateModal from '$lib/training/ExerciseCreateModal.svelte';
	import SearchSelect from '$lib/components/ui/SearchSelect.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Card from '$lib/components/ui/Card.svelte';

	const programId = Number($page.params.id);

	let program = $state<Program | null>(null);
	let exercises = $state<Exercise[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let newDayName = $state('');
	let collapsed = $state<Record<number, boolean>>({});
	const toggleDay = (id: number) => (collapsed[id] = !collapsed[id]);

	// "＋ New exercise" modal — remember which day to drop the result into.
	let showExerciseModal = $state(false);
	let pendingDayId = $state<number | null>(null);

	const SET_TYPES = [
		'working', 'warmup', 'top_set', 'backoff', 'drop', 'amrap', 'failure', 'rest_pause', 'myo_rep', 'cluster'
	];

	// Options for the searchable exercise picker (label + equipment-category chip).
	const exOptions = $derived(
		exercises.map((ex) => ({ id: ex.id, label: ex.name, group: ex.category }))
	);

	async function load() {
		program = await trainingApi.program(programId);
		// Days start collapsed by default; preserve the user's toggles across reloads.
		for (const d of program.days) if (!(d.id in collapsed)) collapsed[d.id] = true;
	}

	onMount(async () => {
		try {
			[, exercises] = await Promise.all([load(), trainingApi.exercises()]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	async function addDay(e: SubmitEvent) {
		e.preventDefault();
		if (!newDayName.trim() || !program) return;
		const day = await trainingApi.createDay({ program: programId, name: newDayName.trim(), order: program.days.length });
		newDayName = '';
		await load();
		collapsed[day.id] = false; // a just-added day opens so you can fill it
	}

	async function removeDay(id: number) {
		if (!confirm('Remove this day and its exercises?')) return;
		await trainingApi.deleteDay(id);
		await load();
	}

	async function addSlot(day: TrainingDay, exerciseId: number) {
		if (!exerciseId) return;
		const slot = await trainingApi.createSlot({ day: day.id, exercise: exerciseId, order: day.slots.length });
		// Seed 3 working sets so a new slot is immediately useful.
		for (let i = 0; i < 3; i++) {
			await trainingApi.createPlannedSet({
				slot: slot.id, order: i, set_type: 'working', target_reps_low: 8, target_reps_high: 12
			});
		}
		await load();
	}

	async function onExerciseCreated(ex: Exercise) {
		exercises = [...exercises, ex].sort((a, b) => a.name.localeCompare(b.name));
		const day = program?.days.find((d) => d.id === pendingDayId);
		if (day) await addSlot(day, ex.id);
		pendingDayId = null;
	}

	async function removeSlot(id: number) {
		await trainingApi.deleteSlot(id);
		await load();
	}

	// --- planned set editing (PATCH per field; mutate locally for snappy inputs) ---
	async function addSet(slot: ExerciseSlot) {
		const last = slot.planned_sets[slot.planned_sets.length - 1];
		await trainingApi.createPlannedSet({
			slot: slot.id,
			order: slot.planned_sets.length,
			set_type: last?.set_type ?? 'working',
			target_reps_low: last?.target_reps_low ?? 8,
			target_reps_high: last?.target_reps_high ?? 12,
			target_weight: last?.target_weight ?? null,
			rest_seconds: last?.rest_seconds ?? null
		});
		await load();
	}

	async function removeSet(id: number) {
		await trainingApi.deletePlannedSet(id);
		await load();
	}

	function setField(ps: PlannedSet, field: keyof PlannedSet, raw: string, kind: 'int' | 'dec' | 'str') {
		let val: number | string | null;
		if (raw === '') val = null;
		else if (kind === 'int') val = Math.round(Number(raw));
		else if (kind === 'dec') val = String(Number(raw));
		else val = raw;
		(ps as unknown as Record<string, unknown>)[field] = val;
		trainingApi.updatePlannedSet(ps.id, { [field]: val } as Partial<PlannedSet>).catch((e) => {
			error = (e as Error).message;
		});
	}

	// --- slot reordering: drag (svelte-dnd-action) + arrow fallback ---
	function persistSlotOrder(day: TrainingDay) {
		return trainingApi.reorderSlots(day.slots.map((s, i) => ({ id: s.id, order: i })));
	}
	function dndConsider(day: TrainingDay, e: CustomEvent<{ items: ExerciseSlot[] }>) {
		day.slots = e.detail.items;
	}
	async function dndFinalize(day: TrainingDay, e: CustomEvent<{ items: ExerciseSlot[] }>) {
		day.slots = e.detail.items;
		await persistSlotOrder(day);
	}
	async function moveSlot(day: TrainingDay, index: number, dir: -1 | 1) {
		const j = index + dir;
		if (j < 0 || j >= day.slots.length) return;
		const arr = [...day.slots];
		[arr[index], arr[j]] = [arr[j], arr[index]];
		day.slots = arr;
		await persistSlotOrder(day);
	}

	const fieldClass = 'rounded border border-neutral-700 bg-neutral-900 px-1.5 py-1 text-sm text-neutral-100';
</script>

<ExerciseCreateModal bind:open={showExerciseModal} oncreated={onExerciseCreated} onclose={() => (pendingDayId = null)} />

{#if loading}
	<p class="text-neutral-400">Loading…</p>
{:else if error}
	<p class="text-red-400">{error}</p>
{:else if program}
	<div class="flex items-center justify-between">
		<div>
			<a class="text-sm text-neutral-400 hover:text-white" href="/training/programs">← Programs</a>
			<h1 class="text-xl font-semibold">{program.name}</h1>
		</div>
		{#if program.is_active}
			<span class="rounded bg-green-900 px-2 py-0.5 text-xs text-green-300">Active</span>
		{/if}
	</div>

	<form class="mt-4 flex gap-2" onsubmit={addDay}>
		<Input placeholder="Add a training day (e.g. Push)" bind:value={newDayName} />
		<div class="w-32 shrink-0"><Button type="submit">Add day</Button></div>
	</form>

	{#if program.days.length === 0}
		<p class="mt-6 text-neutral-500">No days yet. Add your first training day above.</p>
	{:else}
		<div class="mt-6 space-y-6">
			{#each program.days as day (day.id)}
				<Card>
					<div class="flex items-center justify-between">
						<button class="flex items-center gap-2 text-left" onclick={() => toggleDay(day.id)}>
							<span class="w-3 text-neutral-500">{collapsed[day.id] ? '▸' : '▾'}</span>
							<h2 class="font-medium">{day.name}</h2>
							<span class="text-xs text-neutral-600">· {day.slots.length} exercise(s)</span>
						</button>
						<button class="text-xs text-red-400 hover:text-red-300" onclick={() => removeDay(day.id)}>
							Remove day
						</button>
					</div>

					{#if !collapsed[day.id]}
					{#if day.slots.length === 0}
						<p class="mt-2 text-sm text-neutral-500">No exercises yet.</p>
					{:else}
						<div
							class="mt-3 space-y-3"
							use:dndzone={{ items: day.slots, flipDurationMs: 150, dropTargetStyle: {} }}
							onconsider={(e) => dndConsider(day, e)}
							onfinalize={(e) => dndFinalize(day, e)}
						>
							{#each day.slots as slot, si (slot.id)}
								<div class="rounded border border-neutral-800 p-3">
									<div class="flex items-center justify-between">
										<div class="flex items-center gap-2">
											<span class="cursor-grab select-none text-neutral-600" aria-hidden="true">⠿</span>
											<span class="text-sm font-medium">{slot.exercise_name}</span>
										</div>
										<div class="flex items-center gap-2 text-xs text-neutral-500">
											<button class="hover:text-white disabled:opacity-30" aria-label="Move up" disabled={si === 0} onclick={() => moveSlot(day, si, -1)}>↑</button>
											<button class="hover:text-white disabled:opacity-30" aria-label="Move down" disabled={si === day.slots.length - 1} onclick={() => moveSlot(day, si, 1)}>↓</button>
											<button class="text-red-400 hover:text-red-300" onclick={() => removeSlot(slot.id)}>Remove</button>
										</div>
									</div>

									<!-- Planned sets -->
									<div class="mt-2 overflow-x-auto"><table class="w-full min-w-[30rem] text-sm">
										<thead class="text-xs text-neutral-500">
											<tr>
												<th class="text-left font-normal">#</th>
												<th class="text-left font-normal">Type</th>
												<th class="text-left font-normal">Reps</th>
												<th class="text-left font-normal">Weight</th>
												<th class="text-left font-normal">Rest s</th>
												<th></th>
											</tr>
										</thead>
										<tbody>
											{#each slot.planned_sets as ps, pi (ps.id)}
												<tr>
													<td class="py-1 pr-2 text-neutral-500">{pi + 1}</td>
													<td class="py-1 pr-2">
														<select
															class={fieldClass}
															value={ps.set_type}
															onchange={(e) => setField(ps, 'set_type', e.currentTarget.value, 'str')}
														>
															{#each SET_TYPES as t (t)}<option value={t}>{t}</option>{/each}
														</select>
													</td>
													<td class="py-1 pr-2">
														<span class="inline-flex items-center gap-1">
															<input class="w-12 {fieldClass}" type="number" min="0" value={ps.target_reps_low ?? ''} onchange={(e) => setField(ps, 'target_reps_low', e.currentTarget.value, 'int')} />
															<span class="text-neutral-600">–</span>
															<input class="w-12 {fieldClass}" type="number" min="0" value={ps.target_reps_high ?? ''} onchange={(e) => setField(ps, 'target_reps_high', e.currentTarget.value, 'int')} />
														</span>
													</td>
													<td class="py-1 pr-2">
														<input class="w-16 {fieldClass}" type="number" step="0.5" value={ps.target_weight ?? ''} onchange={(e) => setField(ps, 'target_weight', e.currentTarget.value, 'dec')} />
													</td>
													<td class="py-1 pr-2">
														<input class="w-14 {fieldClass}" type="number" min="0" step="5" value={ps.rest_seconds ?? ''} onchange={(e) => setField(ps, 'rest_seconds', e.currentTarget.value, 'int')} />
													</td>
													<td class="py-1 text-right">
														<button class="text-xs text-neutral-600 hover:text-red-400" aria-label="Remove set" onclick={() => removeSet(ps.id)}>✕</button>
													</td>
												</tr>
											{/each}
										</tbody>
									</table></div>
									<button class="mt-2 text-xs text-indigo-400 hover:text-indigo-300" onclick={() => addSet(slot)}>
										+ Add set
									</button>
								</div>
							{/each}
						</div>
					{/if}

					<div class="mt-3 flex items-center gap-2">
						<div class="flex-1">
							<SearchSelect
								options={exOptions}
								groups={EXERCISE_CATEGORIES}
								placeholder="+ Add exercise…"
								resetOnSelect
								onchange={(id) => addSlot(day, id)}
							/>
						</div>
						<button
							type="button"
							class="shrink-0 rounded-md border border-neutral-700 px-3 py-2 text-sm text-indigo-300 hover:border-neutral-500"
							onclick={() => {
								pendingDayId = day.id;
								showExerciseModal = true;
							}}
						>
							＋ New
						</button>
					</div>
					{/if}
				</Card>
			{/each}
		</div>
	{/if}
{/if}
