<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { clientPlan, writeError, type NutritionTarget } from './plan';
	import { CLIENT_CTX, type ClientContext } from './context';

	let { clientId }: { clientId: number } = $props();
	const plan = $derived(clientPlan(clientId));
	const ctx = getContext<ClientContext>(CLIENT_CTX);
	const canEdit = $derived(ctx?.canEdit ?? false);

	let targets = $state<NutritionTarget[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let busy = $state(false);

	let selectedId = $state<number | null>(null);
	let creating = $state(false);
	let setActiveOnCreate = $state(true);

	type Draft = {
		name: string;
		calories: string;
		protein_g: string;
		carb_g: string;
		fat_g: string;
		fiber_g: string;
	};
	const emptyDraft = (): Draft => ({ name: '', calories: '', protein_g: '', carb_g: '', fat_g: '', fiber_g: '' });
	const fromTarget = (t: NutritionTarget): Draft => ({
		name: t.name,
		calories: t.calories ?? '',
		protein_g: t.protein_g ?? '',
		carb_g: t.carb_g ?? '',
		fat_g: t.fat_g ?? '',
		fiber_g: t.fiber_g ?? ''
	});
	const orNull = (s: string) => (s.trim() === '' ? null : s.trim());
	const buildPayload = (d: Draft) => ({
		name: d.name.trim(),
		calories: orNull(d.calories),
		protein_g: orNull(d.protein_g),
		carb_g: orNull(d.carb_g),
		fat_g: orNull(d.fat_g),
		fiber_g: orNull(d.fiber_g)
	});
	let draft = $state<Draft>(emptyDraft());

	const selected = $derived(targets.find((t) => t.id === selectedId) ?? null);
	const num = (s: string) => (s.trim() === '' ? 0 : Number(s) || 0);
	const macroKcal = $derived(Math.round(num(draft.protein_g) * 4 + num(draft.carb_g) * 4 + num(draft.fat_g) * 9));
	const mismatch = $derived(draft.calories.trim() !== '' && Math.abs(macroKcal - num(draft.calories)) > 50);

	async function load(select?: number) {
		loading = true;
		error = null;
		try {
			targets = await plan.targets();
			const pick = select ?? selectedId ?? targets.find((t) => t.is_active)?.id ?? targets[0]?.id ?? null;
			if (!creating && pick != null) selectTarget(pick);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}
	onMount(() => load());

	function selectTarget(id: number) {
		creating = false;
		selectedId = id;
		const t = targets.find((x) => x.id === id);
		if (t) draft = fromTarget(t);
	}
	function startNew() {
		creating = true;
		selectedId = null;
		draft = emptyDraft();
		setActiveOnCreate = targets.length === 0;
	}

	async function save() {
		if (!draft.name.trim()) return;
		busy = true;
		error = null;
		try {
			if (creating) {
				const created = await plan.createTarget(buildPayload(draft));
				if (setActiveOnCreate) await plan.activateTarget(created.id);
				creating = false;
				await load(created.id);
			} else if (selectedId != null) {
				await plan.updateTarget(selectedId, buildPayload(draft));
				await load(selectedId);
			}
		} catch (e) {
			error = writeError(e);
		} finally {
			busy = false;
		}
	}

	async function activate() {
		if (selectedId == null) return;
		error = null;
		try {
			await plan.activateTarget(selectedId);
			await load(selectedId);
		} catch (e) {
			error = writeError(e);
		}
	}

	async function remove() {
		if (!selected || !confirm(`Delete target “${selected.name}”?`)) return;
		error = null;
		try {
			await plan.deleteTarget(selected.id);
			selectedId = null;
			await load();
		} catch (e) {
			error = writeError(e);
		}
	}

	const macroLine = (t: NutritionTarget) =>
		`${Math.round(Number(t.calories ?? 0))} kcal · ${Math.round(Number(t.protein_g ?? 0))}P / ${Math.round(Number(t.carb_g ?? 0))}C / ${Math.round(Number(t.fat_g ?? 0))}F`;
</script>

<div class="flex gap-6">
	<!-- Target list -->
	<aside class="w-56 shrink-0">
		<h2 class="text-sm font-semibold text-neutral-300">Targets</h2>
		{#if loading}
			<p class="mt-3 text-sm text-neutral-400">Loading…</p>
		{:else}
			<div class="mt-3 space-y-1">
				{#each targets as t (t.id)}
					<button
						onclick={() => selectTarget(t.id)}
						class="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm {selectedId === t.id
							? 'bg-neutral-800 text-white'
							: 'text-neutral-300 hover:bg-neutral-900'}"
					>
						<span class="truncate">{t.name}</span>
						{#if t.is_active}<span class="ml-2 rounded bg-emerald-950 px-1.5 py-0.5 text-[10px] text-emerald-300">ACTIVE</span>{/if}
					</button>
				{:else}
					<p class="text-sm text-neutral-500">No targets yet.</p>
				{/each}
			</div>
			{#if canEdit}
				<button
					onclick={startNew}
					class="mt-3 w-full rounded-full bg-brand px-3 py-1.5 text-sm font-medium text-white {creating ? 'ring-2 ring-brand/50' : ''}"
				>
					＋ New target
				</button>
			{/if}
		{/if}
	</aside>

	<!-- Target editor -->
	<section class="min-w-0 flex-1">
		{#if error}<p class="mb-3 text-sm text-red-400">{error}</p>{/if}
		{#if !creating && selectedId == null}
			<p class="text-sm text-neutral-500">Select a target on the left{canEdit ? ', or create a new one' : ''}.</p>
		{:else}
			<div class="flex items-center justify-between">
				<div>
					<h1 class="text-lg font-semibold">{creating ? 'New target' : selected?.name || 'Target'}</h1>
					{#if !creating && selected?.is_active}<p class="text-xs text-emerald-400">Active target</p>{/if}
				</div>
				{#if !creating && canEdit && selected}
					<div class="flex items-center gap-2 text-sm">
						{#if !selected.is_active}
							<button onclick={activate} class="rounded-full border border-emerald-800 px-3 py-1 text-emerald-300 hover:bg-emerald-950">Set active</button>
						{/if}
						<button onclick={remove} class="rounded-full border border-neutral-800 px-3 py-1 text-neutral-400 hover:text-red-300">Delete</button>
					</div>
				{/if}
			</div>

			<div class="mt-4 max-w-xl space-y-3">
				<input
					placeholder="Name (e.g. Prep wk 7)"
					bind:value={draft.name}
					disabled={!canEdit}
					class="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 disabled:opacity-60"
				/>
				<div class="grid grid-cols-2 gap-2 sm:grid-cols-5">
					{#each [['calories', 'Calories'], ['protein_g', 'Protein'], ['carb_g', 'Carbs'], ['fat_g', 'Fat'], ['fiber_g', 'Fiber']] as [key, label] (key)}
						<label class="flex flex-col text-xs text-neutral-500">
							{label}
							<input
								type="number"
								step="1"
								bind:value={draft[key as keyof Draft]}
								disabled={!canEdit}
								class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100 disabled:opacity-60"
							/>
						</label>
					{/each}
				</div>
				<p class="text-xs {mismatch ? 'text-amber-400' : 'text-neutral-500'}">
					Macros ≈ {macroKcal} kcal{mismatch ? ` — differs from ${num(draft.calories)} kcal target` : ''}
				</p>
				{#if canEdit}
					{#if creating}
						<label class="flex items-center gap-2 text-xs text-neutral-400">
							<input type="checkbox" bind:checked={setActiveOnCreate} /> Set as the client's active target
						</label>
					{/if}
					<button
						onclick={save}
						disabled={busy || !draft.name.trim()}
						class="rounded-full bg-brand px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-40"
					>
						{creating ? (setActiveOnCreate ? 'Create & set active' : 'Create target') : 'Save changes'}
					</button>
				{/if}
			</div>
		{/if}
	</section>
</div>
