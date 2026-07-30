<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import {
		clientPlan,
		writeError,
		SET_TYPES,
		type ClientPlan,
		type ProgramBrief,
		type Program,
		type TrainingDay,
		type ExerciseSlot,
		type PlannedSet,
		type ExerciseRef
	} from './plan';
	import { CLIENT_CTX, type ClientContext } from './context';

	let {
		clientId,
		plan: planProp,
		canEdit: canEditProp,
		onApply
	}: {
		clientId?: number;
		plan?: ClientPlan;
		canEdit?: boolean;
		onApply?: (id: number, name: string) => void;
	} = $props();
	const plan = $derived(planProp ?? clientPlan(clientId!));
	const ctx = getContext<ClientContext>(CLIENT_CTX);
	const canEdit = $derived(canEditProp ?? ctx?.canEdit ?? false);
	const isTemplate = $derived(onApply != null);

	let programs = $state<ProgramBrief[]>([]);
	let selectedId = $state<number | null>(null);
	let program = $state<Program | null>(null);
	let loading = $state(true);
	let loadingDetail = $state(false);
	let error = $state<string | null>(null);
	let newProgramName = $state('');
	let busy = $state(false);
	// Day ids that are collapsed. All days start collapsed when a program is first
	// opened (4-day plans get long); in-program edits preserve the current open/closed state.
	let collapsedDays = $state<Set<number>>(new Set());

	function toggleDay(id: number) {
		const next = new Set(collapsedDays);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		collapsedDays = next;
	}
	function setAllCollapsed(collapsed: boolean) {
		collapsedDays = collapsed ? new Set(program?.days.map((d) => d.id)) : new Set();
	}
	const setCount = (day: TrainingDay) => day.slots.reduce((n, s) => n + s.planned_sets.length, 0);

	async function loadList(select?: number) {
		loading = true;
		error = null;
		try {
			programs = await plan.programs();
			const pick = select ?? selectedId ?? programs.find((p) => p.is_active)?.id ?? programs[0]?.id ?? null;
			if (pick != null) await selectProgram(pick);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	// resetCollapse=true (opening/switching a program) collapses every day; in-program
	// reloads pass false so the day the coach is editing stays open.
	async function selectProgram(id: number, resetCollapse = true) {
		selectedId = id;
		loadingDetail = true;
		try {
			program = await plan.program(id);
			if (resetCollapse) collapsedDays = new Set(program.days.map((d) => d.id));
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loadingDetail = false;
		}
	}

	onMount(() => loadList());

	async function createProgram() {
		if (!newProgramName.trim()) return;
		busy = true;
		error = null;
		try {
			const p = await plan.createProgram({ name: newProgramName.trim() });
			newProgramName = '';
			await loadList(p.id);
		} catch (e) {
			error = writeError(e);
		} finally {
			busy = false;
		}
	}

	async function activate() {
		if (!program) return;
		try {
			await plan.activateProgram(program.id);
			await loadList(program.id);
		} catch (e) {
			error = writeError(e);
		}
	}

	async function removeProgram() {
		if (!program || !confirm(`Delete program “${program.name}” and all its days?`)) return;
		try {
			await plan.deleteProgram(program.id);
			selectedId = null;
			program = null;
			await loadList();
		} catch (e) {
			error = writeError(e);
		}
	}

	async function addDay() {
		if (!program) return;
		try {
			const created = await plan.createDay({
				program: program.id,
				name: `Day ${program.days.length + 1}`,
				order: program.days.length
			});
			await selectProgram(program.id, false);
			// Leave the new day expanded so it can be filled in right away.
			const next = new Set(collapsedDays);
			next.delete(created.id);
			collapsedDays = next;
		} catch (e) {
			error = writeError(e);
		}
	}

	async function renameDay(day: TrainingDay, name: string) {
		if (name.trim() === day.name || !name.trim()) return;
		try {
			await plan.updateDay(day.id, { name: name.trim() });
			day.name = name.trim();
		} catch (e) {
			error = writeError(e);
		}
	}

	async function removeDay(day: TrainingDay) {
		if (!confirm(`Delete “${day.name}”?`)) return;
		try {
			await plan.deleteDay(day.id);
			if (program) await selectProgram(program.id, false);
		} catch (e) {
			error = writeError(e);
		}
	}

	// --- exercise picker (one open at a time) ---
	let pickerDayId = $state<number | null>(null);
	let exQuery = $state('');
	let exResults = $state<ExerciseRef[]>([]);
	let exLoading = $state(false);
	let exTimer: ReturnType<typeof setTimeout> | undefined;

	function openPicker(dayId: number) {
		pickerDayId = pickerDayId === dayId ? null : dayId;
		exQuery = '';
		exResults = [];
		if (pickerDayId != null) searchExercises();
	}

	function onExInput() {
		clearTimeout(exTimer);
		exTimer = setTimeout(searchExercises, 250);
	}

	async function searchExercises() {
		exLoading = true;
		try {
			exResults = (await plan.exercises(exQuery)).slice(0, 25);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			exLoading = false;
		}
	}

	async function addSlot(day: TrainingDay, ex: ExerciseRef) {
		try {
			await plan.createSlot({ day: day.id, exercise: ex.id, order: day.slots.length });
			pickerDayId = null;
			if (program) await selectProgram(program.id, false);
		} catch (e) {
			error = writeError(e);
		}
	}

	async function removeSlot(slot: ExerciseSlot) {
		if (!confirm(`Remove ${slot.exercise_name}?`)) return;
		try {
			await plan.deleteSlot(slot.id);
			if (program) await selectProgram(program.id, false);
		} catch (e) {
			error = writeError(e);
		}
	}

	async function addSet(slot: ExerciseSlot) {
		try {
			const created = await plan.createSet({
				slot: slot.id,
				set_type: 'working',
				target_reps_low: 8,
				target_reps_high: 12,
				rest_seconds: 120,
				order: slot.planned_sets.length
			});
			slot.planned_sets.push(created);
		} catch (e) {
			error = writeError(e);
		}
	}

	// PATCH the editable fields after an inline edit (bind mutated `set` in place).
	async function patchSet(set: PlannedSet) {
		try {
			await plan.updateSet(set.id, {
				set_type: set.set_type,
				target_reps_low: set.target_reps_low,
				target_reps_high: set.target_reps_high,
				target_weight: set.target_weight || null,
				rest_seconds: set.rest_seconds
			});
		} catch (e) {
			error = writeError(e);
			if (program) await selectProgram(program.id, false);
		}
	}

	async function removeSet(slot: ExerciseSlot, set: PlannedSet) {
		try {
			await plan.deleteSet(set.id);
			slot.planned_sets = slot.planned_sets.filter((s) => s.id !== set.id);
		} catch (e) {
			error = writeError(e);
		}
	}
</script>

<div class="flex gap-6">
	<!-- Program list -->
	<aside class="w-56 shrink-0">
		<h2 class="text-sm font-semibold text-neutral-300">Programs</h2>
		{#if loading}
			<p class="mt-3 text-sm text-neutral-400">Loading…</p>
		{:else}
			<div class="mt-3 space-y-1">
				{#each programs as p (p.id)}
					<button
						onclick={() => selectProgram(p.id)}
						class="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm {selectedId === p.id
							? 'bg-neutral-800 text-white'
							: 'text-neutral-300 hover:bg-neutral-900'}"
					>
						<span class="truncate">{p.name}</span>
						{#if p.is_active}<span class="ml-2 rounded bg-emerald-950 px-1.5 py-0.5 text-[10px] text-emerald-300">ACTIVE</span>{/if}
					</button>
				{:else}
					<p class="text-sm text-neutral-500">No programs yet.</p>
				{/each}
			</div>
			{#if canEdit}
				<div class="mt-3 space-y-2">
					<input
						placeholder="New program name…"
						bind:value={newProgramName}
						onkeydown={(e) => e.key === 'Enter' && createProgram()}
						class="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100"
					/>
					<button
						onclick={createProgram}
						disabled={busy || !newProgramName.trim()}
						class="w-full rounded-full bg-brand px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
					>
						＋ Program
					</button>
				</div>
			{/if}
		{/if}
	</aside>

	<!-- Program editor -->
	<section class="min-w-0 flex-1">
		{#if error}<p class="mb-3 text-sm text-red-400">{error}</p>{/if}
		{#if !program}
			<p class="text-sm text-neutral-500">Select or create a program.</p>
		{:else}
			<div class="flex items-center justify-between">
				<div>
					<h1 class="text-lg font-semibold">{program.name}</h1>
					<p class="text-xs text-neutral-500">
						{program.days.length} day{program.days.length === 1 ? '' : 's'}
						{!isTemplate && program.is_active ? '· active' : ''}
					</p>
				</div>
				{#if canEdit}
					<div class="flex items-center gap-2 text-sm">
						{#if isTemplate}
							<button onclick={() => onApply?.(program!.id, program!.name)} class="rounded-full bg-brand px-3 py-1 font-medium text-white">Apply to client…</button>
						{:else if !program.is_active}
							<button onclick={activate} class="rounded-full border border-emerald-800 px-3 py-1 text-emerald-300 hover:bg-emerald-950">Set active</button>
						{/if}
						<button onclick={removeProgram} class="rounded-full border border-neutral-800 px-3 py-1 text-neutral-400 hover:text-red-300">Delete</button>
					</div>
				{/if}
			</div>

			{#if loadingDetail}
				<p class="mt-4 text-sm text-neutral-400">Loading…</p>
			{/if}

			{#if program.days.length > 1}
				<div class="mb-3 mt-4 flex items-center gap-3 text-xs text-neutral-500">
					<button onclick={() => setAllCollapsed(false)} class="hover:text-neutral-200">Expand all</button>
					<span class="text-neutral-700">·</span>
					<button onclick={() => setAllCollapsed(true)} class="hover:text-neutral-200">Collapse all</button>
				</div>
			{/if}

			<div class="mt-3 space-y-3">
				{#each program.days as day (day.id)}
					{@const collapsed = collapsedDays.has(day.id)}
					<div class="rounded-lg border border-neutral-800">
						<div class="flex items-center gap-2 px-3 py-2 {collapsed ? '' : 'border-b border-neutral-800'}">
							<button
								onclick={() => toggleDay(day.id)}
								aria-expanded={!collapsed}
								aria-label={collapsed ? `Expand ${day.name}` : `Collapse ${day.name}`}
								class="flex h-5 w-5 shrink-0 items-center justify-center rounded text-neutral-400 hover:bg-neutral-800 hover:text-neutral-100"
							>
								<span class="text-[10px] transition-transform {collapsed ? '' : 'rotate-90'}">▶</span>
							</button>
							{#if canEdit}
								<input
									value={day.name}
									onblur={(e) => renameDay(day, e.currentTarget.value)}
									onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
									class="min-w-0 flex-1 rounded bg-transparent px-1 py-0.5 text-sm font-medium text-neutral-100 hover:bg-neutral-900 focus:bg-neutral-900"
								/>
							{:else}
								<button onclick={() => toggleDay(day.id)} class="min-w-0 flex-1 text-left text-sm font-medium">{day.name}</button>
							{/if}
							<span class="shrink-0 text-xs text-neutral-500">{day.slots.length} ex · {setCount(day)} sets</span>
							{#if canEdit}
								<button onclick={() => removeDay(day)} class="shrink-0 text-xs text-neutral-500 hover:text-red-300">Delete day</button>
							{/if}
						</div>

						{#if !collapsed}
						<div class="divide-y divide-neutral-900">
							{#each day.slots as slot (slot.id)}
								<div class="px-3 py-2">
									<div class="flex items-center justify-between">
										<div class="text-sm font-medium text-neutral-100">{slot.exercise_name}</div>
										{#if canEdit}
											<button onclick={() => removeSlot(slot)} class="text-xs text-neutral-600 hover:text-red-300">✕</button>
										{/if}
									</div>

									<!-- planned sets -->
									<div class="mt-1.5 space-y-1">
										{#if slot.planned_sets.length}
											<div class="grid grid-cols-[1.4fr_1fr_1fr_1fr_auto] gap-1.5 text-[10px] uppercase tracking-wide text-neutral-600">
												<span>Type</span><span>Reps</span><span>–</span><span>Weight</span><span>Rest</span>
											</div>
										{/if}
										{#each slot.planned_sets as set (set.id)}
											<div class="grid grid-cols-[1.4fr_1fr_1fr_1fr_auto] items-center gap-1.5">
												{#if canEdit}
													<select bind:value={set.set_type} onchange={() => patchSet(set)} class="rounded border border-neutral-800 bg-neutral-900 px-1 py-1 text-xs text-neutral-100">
														{#each SET_TYPES as t (t.value)}<option value={t.value}>{t.label}</option>{/each}
													</select>
													<input type="number" min="0" placeholder="low" bind:value={set.target_reps_low} onchange={() => patchSet(set)} class="w-full rounded border border-neutral-800 bg-neutral-900 px-1 py-1 text-xs text-neutral-100" />
													<input type="number" min="0" placeholder="high" bind:value={set.target_reps_high} onchange={() => patchSet(set)} class="w-full rounded border border-neutral-800 bg-neutral-900 px-1 py-1 text-xs text-neutral-100" />
													<input type="text" placeholder="kg / %" bind:value={set.target_weight} onchange={() => patchSet(set)} class="w-full rounded border border-neutral-800 bg-neutral-900 px-1 py-1 text-xs text-neutral-100" />
													<div class="flex items-center gap-1">
														<input type="number" min="0" step="15" placeholder="s" bind:value={set.rest_seconds} onchange={() => patchSet(set)} class="w-14 rounded border border-neutral-800 bg-neutral-900 px-1 py-1 text-xs text-neutral-100" />
														<button onclick={() => removeSet(slot, set)} class="text-xs text-neutral-600 hover:text-red-300">✕</button>
													</div>
												{:else}
													<span class="text-xs text-neutral-400">{SET_TYPES.find((t) => t.value === set.set_type)?.label ?? set.set_type}</span>
													<span class="col-span-2 text-xs text-neutral-400">{set.target_reps_low ?? '?'}–{set.target_reps_high ?? '?'} reps</span>
													<span class="text-xs text-neutral-400">{set.target_weight ?? '—'}</span>
													<span class="text-xs text-neutral-500">{set.rest_seconds ?? '—'}s</span>
												{/if}
											</div>
										{/each}
										{#if canEdit}
											<button onclick={() => addSet(slot)} class="mt-1 text-xs text-orange-400 hover:text-orange-300">＋ Add set</button>
										{/if}
									</div>
								</div>
							{:else}
								<div class="px-3 py-2 text-sm text-neutral-600">No exercises yet.</div>
							{/each}
						</div>

						{#if canEdit}
							<div class="border-t border-neutral-800 px-3 py-2">
								<button onclick={() => openPicker(day.id)} class="text-xs text-orange-400 hover:text-orange-300">
									{pickerDayId === day.id ? 'Close' : '＋ Add exercise'}
								</button>
								{#if pickerDayId === day.id}
									<div class="mt-2 rounded-md border border-neutral-800 bg-neutral-950 p-2">
										<input
											placeholder="Search exercises…"
											bind:value={exQuery}
											oninput={onExInput}
											class="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100"
										/>
										<div class="mt-2 max-h-56 space-y-0.5 overflow-y-auto">
											{#if exLoading}
												<p class="px-1 py-2 text-xs text-neutral-500">Searching…</p>
											{:else}
												{#each exResults as ex (ex.id)}
													<button onclick={() => addSlot(day, ex)} class="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm text-neutral-200 hover:bg-neutral-800">
														<span>{ex.name}</span>
														<span class="ml-2 truncate text-[10px] text-neutral-500">{ex.primary_muscle_names?.join(', ')}</span>
													</button>
												{:else}
													<p class="px-1 py-2 text-xs text-neutral-500">No matches.</p>
												{/each}
											{/if}
										</div>
									</div>
								{/if}
							</div>
						{/if}
						{/if}
					</div>
				{/each}
			</div>

			{#if canEdit}
				<button onclick={addDay} class="mt-4 rounded-full border border-neutral-700 px-4 py-1.5 text-sm text-neutral-200 hover:bg-neutral-900">＋ Add day</button>
			{/if}
		{/if}
	</section>
</div>
