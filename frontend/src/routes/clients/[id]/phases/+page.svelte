<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { page } from '$app/stores';
	import { clientPlan, writeError, type Phase, PHASE_TYPES } from '$lib/clients/plan';
	import { CLIENT_CTX, type ClientContext } from '$lib/clients/context';

	const clientId = $derived(Number($page.params.id));
	const plan = $derived(clientPlan(clientId));
	const ctx = getContext<ClientContext>(CLIENT_CTX);
	const canEdit = $derived(ctx?.canEdit ?? false);

	let phases = $state<Phase[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let busy = $state(false);

	let selectedId = $state<number | null>(null);
	let creating = $state(false);

	const today = new Date().toISOString().slice(0, 10);
	type Draft = { name: string; phase_type: string; start_date: string; end_date: string; notes: string };
	const emptyDraft = (): Draft => ({ name: '', phase_type: 'bulk', start_date: today, end_date: '', notes: '' });
	const fromPhase = (p: Phase): Draft => ({
		name: p.name,
		phase_type: p.phase_type,
		start_date: p.start_date,
		end_date: p.end_date ?? '',
		notes: p.notes ?? ''
	});
	let draft = $state<Draft>(emptyDraft());

	const selected = $derived(phases.find((p) => p.id === selectedId) ?? null);
	const typeLabel = (v: string) => PHASE_TYPES.find((t) => t.value === v)?.label ?? v;

	async function load(select?: number) {
		loading = true;
		error = null;
		try {
			phases = await plan.phases();
			const pick = select ?? selectedId ?? phases.find((p) => p.is_ongoing)?.id ?? phases[0]?.id ?? null;
			if (!creating && pick != null) selectPhase(pick);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}
	onMount(() => load());

	function selectPhase(id: number) {
		creating = false;
		selectedId = id;
		const p = phases.find((x) => x.id === id);
		if (p) draft = fromPhase(p);
	}
	function startNew() {
		creating = true;
		selectedId = null;
		draft = emptyDraft();
	}

	async function save() {
		if (!draft.name.trim()) return;
		busy = true;
		error = null;
		try {
			if (creating) {
				const created = await plan.createPhase({
					name: draft.name.trim(),
					phase_type: draft.phase_type,
					start_date: draft.start_date,
					notes: draft.notes || undefined
				});
				creating = false;
				await load(created.id);
			} else if (selectedId != null) {
				await plan.updatePhase(selectedId, {
					name: draft.name.trim(),
					phase_type: draft.phase_type,
					start_date: draft.start_date,
					end_date: draft.end_date.trim() === '' ? null : draft.end_date,
					notes: draft.notes
				});
				await load(selectedId);
			}
		} catch (e) {
			error = writeError(e);
		} finally {
			busy = false;
		}
	}

	async function remove() {
		if (!selected || !confirm(`Delete phase “${selected.name}”? Its adjustment history is removed too.`)) return;
		error = null;
		try {
			await plan.deletePhase(selected.id);
			selectedId = null;
			await load();
		} catch (e) {
			error = writeError(e);
		}
	}
</script>

<div class="flex gap-6 p-6">
	<!-- Phase list -->
	<aside class="w-56 shrink-0">
		<h2 class="text-sm font-semibold text-neutral-300">Periodization</h2>
		{#if loading}
			<p class="mt-3 text-sm text-neutral-400">Loading…</p>
		{:else}
			<div class="mt-3 space-y-1">
				{#each phases as p (p.id)}
					<button
						onclick={() => selectPhase(p.id)}
						class="flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm {selectedId === p.id
							? 'bg-neutral-800 text-white'
							: 'text-neutral-300 hover:bg-neutral-900'}"
					>
						<span class="min-w-0 truncate">{p.name}</span>
						{#if p.is_ongoing}<span class="shrink-0 rounded bg-emerald-950 px-1.5 py-0.5 text-[10px] text-emerald-300">ONGOING</span>{/if}
					</button>
				{:else}
					<p class="text-sm text-neutral-500">No phases yet.</p>
				{/each}
			</div>
			{#if canEdit}
				<button
					onclick={startNew}
					class="mt-3 w-full rounded-full bg-brand px-3 py-1.5 text-sm font-medium text-white {creating ? 'ring-2 ring-brand/50' : ''}"
				>
					＋ New phase
				</button>
			{/if}
		{/if}
	</aside>

	<!-- Phase editor -->
	<section class="min-w-0 flex-1">
		{#if error}<p class="mb-3 text-sm text-red-400">{error}</p>{/if}
		{#if !creating && selectedId == null}
			<p class="text-sm text-neutral-500">Select a phase on the left{canEdit ? ', or create a new one' : ''}.</p>
		{:else}
			<div class="flex items-center justify-between">
				<div>
					<h1 class="text-lg font-semibold">{creating ? 'New phase' : selected?.name || 'Phase'}</h1>
					{#if !creating && selected}
						<p class="text-xs text-neutral-500">
							{typeLabel(selected.phase_type)} · {selected.start_date} → {selected.end_date ?? 'present'}
							{#if selected.adjustments?.length}· {selected.adjustments.length} adjustment{selected.adjustments.length > 1 ? 's' : ''}{/if}
						</p>
					{/if}
				</div>
				{#if !creating && canEdit && selected}
					<div class="flex items-center gap-2 text-sm">
						<button onclick={remove} class="rounded-full border border-neutral-800 px-3 py-1 text-neutral-400 hover:text-red-300">Delete</button>
					</div>
				{/if}
			</div>

			<div class="mt-4 max-w-xl space-y-3">
				<input
					placeholder="Name (e.g. Off-season block 2)"
					bind:value={draft.name}
					disabled={!canEdit}
					class="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 disabled:opacity-60"
				/>
				<div class="flex flex-wrap gap-2">
					<label class="flex flex-1 flex-col text-xs text-neutral-500">
						Type
						<select bind:value={draft.phase_type} disabled={!canEdit} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100 disabled:opacity-60">
							{#each PHASE_TYPES as pt (pt.value)}<option value={pt.value}>{pt.label}</option>{/each}
						</select>
					</label>
					<label class="flex flex-1 flex-col text-xs text-neutral-500">
						Start date
						<input type="date" bind:value={draft.start_date} disabled={!canEdit} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100 disabled:opacity-60" />
					</label>
					{#if !creating}
						<label class="flex flex-1 flex-col text-xs text-neutral-500">
							End date <span class="text-neutral-600">(blank = ongoing)</span>
							<input type="date" bind:value={draft.end_date} disabled={!canEdit} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100 disabled:opacity-60" />
						</label>
					{/if}
				</div>
				<textarea
					placeholder="Notes (optional)"
					bind:value={draft.notes}
					disabled={!canEdit}
					rows="2"
					class="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 disabled:opacity-60"
				></textarea>
				{#if creating}
					<p class="text-xs text-neutral-600">
						Creating an ongoing phase (no end date) makes it the client's active phase; the server seeds its
						initial adjustment from the current plan.
					</p>
				{/if}
				{#if canEdit}
					<button
						onclick={save}
						disabled={busy || !draft.name.trim()}
						class="rounded-full bg-brand px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-40"
					>
						{creating ? 'Create phase' : 'Save changes'}
					</button>
				{/if}
			</div>
		{/if}
	</section>
</div>
