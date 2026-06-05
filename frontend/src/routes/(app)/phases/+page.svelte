<script lang="ts">
	import { onMount } from 'svelte';
	import { coachingApi, PHASE_TYPES, type Phase } from '$lib/coaching/api';
	import { nutritionApi, type NutritionTarget } from '$lib/nutrition/api';
	import { trainingApi, type Program } from '$lib/training/api';
	import { protocolsApi, type Protocol } from '$lib/protocols/api';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Card from '$lib/components/ui/Card.svelte';

	function todayISO() {
		return new Date().toISOString().slice(0, 10);
	}

	let phases = $state<Phase[]>([]);
	let targets = $state<NutritionTarget[]>([]);
	let programs = $state<Program[]>([]);
	let protocols = $state<Protocol[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	// Phase editor
	let editing = $state<Phase | null>(null);
	let name = $state('');
	let phaseType = $state('bulk');
	let startDate = $state(todayISO());
	let endDate = $state('');
	let notes = $state('');
	let saving = $state(false);

	// Adjustment editor (per phase)
	let adjOpenFor = $state<number | null>(null);
	let adjDate = $state(todayISO());
	let adjReason = $state('');
	let adjTarget = $state<number | null>(null);
	let adjProgram = $state<number | null>(null);
	let adjProtocol = $state<number | null>(null);
	let adjSaving = $state(false);

	const selectClass = 'rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100';

	async function loadPhases() {
		phases = await coachingApi.phases();
	}

	onMount(async () => {
		try {
			[, targets, programs, protocols] = await Promise.all([
				loadPhases(),
				nutritionApi.targets(),
				trainingApi.programs(),
				protocolsApi.protocols()
			]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	function reset() {
		editing = null;
		name = '';
		phaseType = 'bulk';
		startDate = todayISO();
		endDate = '';
		notes = '';
	}
	function edit(p: Phase) {
		editing = p;
		name = p.name;
		phaseType = p.phase_type;
		startDate = p.start_date;
		endDate = p.end_date ?? '';
		notes = p.notes;
	}

	async function save(e: SubmitEvent) {
		e.preventDefault();
		if (!name.trim()) return;
		saving = true;
		error = null;
		const payload = {
			name: name.trim(),
			phase_type: phaseType,
			start_date: startDate,
			end_date: endDate === '' ? null : endDate,
			notes
		};
		try {
			if (editing) await coachingApi.updatePhase(editing.id, payload);
			else await coachingApi.createPhase(payload);
			reset();
			await loadPhases();
		} catch (err) {
			error = (err as Error).message;
		} finally {
			saving = false;
		}
	}

	async function remove(id: number) {
		if (!confirm('Delete this phase and its adjustments?')) return;
		await coachingApi.deletePhase(id);
		await loadPhases();
	}

	function openAdj(phaseId: number) {
		adjOpenFor = adjOpenFor === phaseId ? null : phaseId;
		adjDate = todayISO();
		adjReason = '';
		adjTarget = adjProgram = adjProtocol = null;
	}

	async function addAdjustment(phaseId: number) {
		adjSaving = true;
		error = null;
		try {
			await coachingApi.createAdjustment({
				phase: phaseId,
				effective_date: adjDate,
				reason: adjReason.trim(),
				nutrition_target: adjTarget,
				program: adjProgram,
				protocol: adjProtocol
			});
			adjOpenFor = null;
			await loadPhases();
		} catch (err) {
			error = (err as Error).message;
		} finally {
			adjSaving = false;
		}
	}

	async function removeAdjustment(id: number) {
		await coachingApi.deleteAdjustment(id);
		await loadPhases();
	}

	const typeLabel = (k: string) => PHASE_TYPES.find((p) => p.key === k)?.label ?? k;

	// Adjustment in force today (highlight it). Adjustments arrive sorted ascending.
	function currentAdjId(p: Phase): number | null {
		const t = todayISO();
		const eligible = p.adjustments.filter((a) => a.effective_date <= t);
		return eligible.length ? eligible[eligible.length - 1].id : null;
	}
</script>

<h1 class="text-xl font-semibold">Phases timeline</h1>
<p class="mt-1 text-sm text-neutral-400">
	A phase spans a date range; within it, dated <em>adjustments</em> record how the prescription
	(nutrition target, program, protocol) evolves. The dashboard resolves whichever adjustment is in
	force today.
</p>

<form class="mt-6 max-w-2xl space-y-3 rounded-lg border border-neutral-800 p-4" onsubmit={save}>
	<h2 class="text-sm font-medium">{editing ? `Edit "${editing.name}"` : 'New phase'}</h2>
	<div class="flex gap-2">
		<Input placeholder="Name (e.g. Summer prep)" bind:value={name} />
		<select bind:value={phaseType} class="rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100">
			{#each PHASE_TYPES as t (t.key)}<option value={t.key}>{t.label}</option>{/each}
		</select>
	</div>
	<div class="flex gap-2">
		<label class="flex flex-1 flex-col text-xs text-neutral-500">Start<input type="date" name="start_date" bind:value={startDate} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100" /></label>
		<label class="flex flex-1 flex-col text-xs text-neutral-500">End (blank = ongoing)<input type="date" name="end_date" bind:value={endDate} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100" /></label>
	</div>
	<Input placeholder="Notes" bind:value={notes} />
	{#if error}<p class="text-sm text-red-400">{error}</p>{/if}
	<div class="flex gap-2">
		<Button type="submit" disabled={saving}>{saving ? 'Saving…' : editing ? 'Save changes' : 'Create phase'}</Button>
		{#if editing}<button type="button" class="rounded-md border border-neutral-700 px-4 py-2 text-sm hover:border-neutral-500" onclick={reset}>Cancel edit</button>{/if}
	</div>
</form>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if phases.length === 0}
	<p class="mt-6 text-neutral-500">No phases yet — create your first above.</p>
{:else}
	<div class="mt-6 space-y-3">
		{#each phases as p (p.id)}
			{@const currentId = currentAdjId(p)}
			<Card>
				<div class="flex items-center justify-between">
					<div>
						<span class="font-medium">{p.name}</span>
						<span class="ml-2 rounded bg-neutral-800 px-2 py-0.5 text-xs text-neutral-300">{typeLabel(p.phase_type)}</span>
						{#if p.is_ongoing}<span class="ml-1 rounded bg-green-900 px-2 py-0.5 text-xs text-green-300">Ongoing</span>{/if}
						<div class="mt-1 text-xs text-neutral-500">{p.start_date} → {p.end_date ?? 'ongoing'}</div>
					</div>
					<div class="flex items-center gap-3 text-sm">
						<button class="text-indigo-400 hover:text-indigo-300" onclick={() => edit(p)}>Edit</button>
						<button class="text-red-400 hover:text-red-300" onclick={() => remove(p.id)}>Delete</button>
					</div>
				</div>

				<!-- Adjustment timeline -->
				<div class="mt-3 border-t border-neutral-800 pt-3">
					<div class="flex items-center justify-between">
						<span class="text-xs font-medium uppercase tracking-wide text-neutral-500">Adjustments</span>
						<button class="text-xs text-indigo-400 hover:text-indigo-300" onclick={() => openAdj(p.id)}>
							{adjOpenFor === p.id ? 'Cancel' : '＋ Add adjustment'}
						</button>
					</div>

					{#if p.adjustments.length === 0}
						<p class="mt-2 text-xs text-neutral-500">No adjustments — add one to set the prescription.</p>
					{:else}
						<ul class="mt-2 space-y-1">
							{#each p.adjustments as a (a.id)}
								<li class="flex items-center justify-between rounded px-2 py-1 text-xs {a.id === currentId ? 'bg-indigo-950/50 text-indigo-200' : 'text-neutral-400'}">
									<span>
										<span class="font-mono">{a.effective_date}</span>
										{#if a.id === currentId}<span class="ml-1 rounded bg-indigo-800 px-1 text-[10px] text-indigo-200">current</span>{/if}
										{#if a.nutrition_target_name}· 🍽 {a.nutrition_target_name}{/if}
										{#if a.program_name}· 🏋 {a.program_name}{/if}
										{#if a.protocol_name}· 💉 {a.protocol_name}{/if}
										{#if a.reason}<span class="text-neutral-600"> — {a.reason}</span>{/if}
									</span>
									<button class="text-neutral-600 hover:text-red-400" aria-label="Remove adjustment" onclick={() => removeAdjustment(a.id)}>✕</button>
								</li>
							{/each}
						</ul>
					{/if}

					{#if adjOpenFor === p.id}
						<div class="mt-3 space-y-2 rounded border border-neutral-800 p-3">
							<div class="flex flex-wrap gap-2">
								<label class="flex flex-col text-xs text-neutral-500">Effective<input type="date" bind:value={adjDate} class="mt-1 {selectClass}" /></label>
								<label class="flex flex-col text-xs text-neutral-500">Nutrition target
									<select onchange={(e) => (adjTarget = e.currentTarget.value ? Number(e.currentTarget.value) : null)} class="mt-1 {selectClass}">
										<option value="">—</option>
										{#each targets as t (t.id)}<option value={t.id} selected={adjTarget === t.id}>{t.name}</option>{/each}
									</select>
								</label>
								<label class="flex flex-col text-xs text-neutral-500">Program
									<select onchange={(e) => (adjProgram = e.currentTarget.value ? Number(e.currentTarget.value) : null)} class="mt-1 {selectClass}">
										<option value="">—</option>
										{#each programs as pr (pr.id)}<option value={pr.id} selected={adjProgram === pr.id}>{pr.name}</option>{/each}
									</select>
								</label>
								<label class="flex flex-col text-xs text-neutral-500">Protocol
									<select onchange={(e) => (adjProtocol = e.currentTarget.value ? Number(e.currentTarget.value) : null)} class="mt-1 {selectClass}">
										<option value="">—</option>
										{#each protocols as pc (pc.id)}<option value={pc.id} selected={adjProtocol === pc.id}>{pc.name}</option>{/each}
									</select>
								</label>
							</div>
							<input placeholder="Reason (e.g. weight stalled → −150 kcal)" bind:value={adjReason} class="w-full {selectClass}" />
							<button class="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50" disabled={adjSaving} onclick={() => addAdjustment(p.id)}>
								{adjSaving ? 'Saving…' : 'Add adjustment'}
							</button>
						</div>
					{/if}
				</div>
			</Card>
		{/each}
	</div>
{/if}
