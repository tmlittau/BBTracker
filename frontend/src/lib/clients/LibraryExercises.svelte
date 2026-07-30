<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import {
		clientPlan,
		writeError,
		EXERCISE_CATEGORIES,
		LOAD_TYPES,
		type Exercise,
		type Muscle
	} from './plan';
	import { CLIENT_CTX, type ClientContext } from './context';

	let { clientId }: { clientId: number } = $props();
	const plan = $derived(clientPlan(clientId));
	const ctx = getContext<ClientContext>(CLIENT_CTX);
	const canEdit = $derived(ctx?.canEdit ?? false);

	let all = $state<Exercise[]>([]);
	let muscles = $state<Muscle[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let busy = $state(false);
	let search = $state('');

	const custom = $derived(
		all
			.filter((e) => !e.is_global)
			.filter((e) => e.name.toLowerCase().includes(search.trim().toLowerCase()))
	);
	const globalCount = $derived(all.filter((e) => e.is_global).length);

	type Draft = {
		name: string;
		category: string;
		load_type: string;
		equipment: string;
		is_unilateral: boolean;
		primary_muscles: number[];
		instructions: string;
	};
	const emptyDraft = (): Draft => ({
		name: '',
		category: 'barbell',
		load_type: 'weight_reps',
		equipment: '',
		is_unilateral: false,
		primary_muscles: [],
		instructions: ''
	});
	const fromItem = (e: Exercise): Draft => ({
		name: e.name,
		category: e.category,
		load_type: e.load_type,
		equipment: e.equipment,
		is_unilateral: e.is_unilateral,
		primary_muscles: [...(e.primary_muscles ?? [])],
		instructions: e.instructions
	});

	let adding = $state(false);
	let editingId = $state<number | null>(null);
	let draft = $state<Draft>(emptyDraft());

	async function load() {
		loading = true;
		error = null;
		try {
			[all, muscles] = await Promise.all([plan.exercises(), muscles.length ? Promise.resolve(muscles) : plan.muscles()]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}
	onMount(load);

	function openAdd() {
		editingId = null;
		draft = emptyDraft();
		adding = true;
	}
	function openEdit(e: Exercise) {
		adding = false;
		editingId = e.id;
		draft = fromItem(e);
	}
	function cancel() {
		adding = false;
		editingId = null;
	}
	function toggleMuscle(id: number) {
		draft.primary_muscles = draft.primary_muscles.includes(id)
			? draft.primary_muscles.filter((m) => m !== id)
			: [...draft.primary_muscles, id];
	}

	async function save() {
		if (!draft.name.trim()) return;
		busy = true;
		error = null;
		try {
			const body = {
				name: draft.name.trim(),
				category: draft.category,
				load_type: draft.load_type,
				equipment: draft.equipment.trim(),
				is_unilateral: draft.is_unilateral,
				primary_muscles: draft.primary_muscles,
				instructions: draft.instructions.trim()
			};
			if (editingId != null) await plan.updateExercise(editingId, body);
			else await plan.createExercise(body);
			cancel();
			await load();
		} catch (e) {
			error = writeError(e);
		} finally {
			busy = false;
		}
	}

	async function remove(e: Exercise) {
		if (!confirm(`Delete exercise “${e.name}”?`)) return;
		error = null;
		try {
			await plan.deleteExercise(e.id);
			await load();
		} catch (e2) {
			error = writeError(e2);
		}
	}

	const catLabel = (v: string) => EXERCISE_CATEGORIES.find((c) => c.value === v)?.label ?? v;
</script>

{#snippet fields()}
	<div class="mt-2 space-y-3 rounded-md border border-neutral-800 bg-neutral-950 p-3">
		<input placeholder="Name (e.g. Cable Y-raise)" bind:value={draft.name} class="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100" />
		<div class="flex flex-wrap gap-2">
			<label class="flex flex-1 flex-col text-xs text-neutral-500">
				Category
				<select bind:value={draft.category} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100">
					{#each EXERCISE_CATEGORIES as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
				</select>
			</label>
			<label class="flex flex-1 flex-col text-xs text-neutral-500">
				Load type
				<select bind:value={draft.load_type} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100">
					{#each LOAD_TYPES as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
				</select>
			</label>
			<label class="flex flex-1 flex-col text-xs text-neutral-500">
				Equipment
				<input bind:value={draft.equipment} placeholder="optional" class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100" />
			</label>
		</div>
		<div>
			<span class="text-xs text-neutral-500">Primary muscles</span>
			<div class="mt-1 flex flex-wrap gap-1">
				{#each muscles as m (m.id)}
					<button
						onclick={() => toggleMuscle(m.id)}
						class="rounded-full px-2 py-0.5 text-xs {draft.primary_muscles.includes(m.id) ? 'bg-brand text-white' : 'border border-neutral-700 text-neutral-400'}"
					>
						{m.name}
					</button>
				{/each}
			</div>
		</div>
		<label class="flex items-center gap-2 text-xs text-neutral-400">
			<input type="checkbox" bind:checked={draft.is_unilateral} /> Unilateral (one side at a time)
		</label>
		<textarea bind:value={draft.instructions} rows="2" placeholder="Cues / instructions (optional)" class="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"></textarea>
		<div class="flex items-center gap-2">
			<button onclick={save} disabled={busy || !draft.name.trim()} class="rounded-full bg-brand px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-40">
				{editingId != null ? 'Save exercise' : 'Create exercise'}
			</button>
			<button onclick={cancel} class="text-sm text-neutral-400 hover:text-neutral-200">Cancel</button>
		</div>
	</div>
{/snippet}

{#if error}<p class="text-sm text-red-400">{error}</p>{/if}
{#if loading}
	<p class="text-sm text-neutral-400">Loading…</p>
{:else}
	<div class="flex items-center justify-between gap-3">
		<input placeholder="Filter custom exercises…" bind:value={search} class="w-64 rounded border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-100" />
		<span class="text-xs text-neutral-600">{globalCount} global exercises available in the builder</span>
	</div>

	<div class="mt-3 max-w-2xl space-y-2">
		{#each custom as e (e.id)}
			<div class="rounded-lg border border-neutral-800">
				<div class="flex items-center justify-between px-3 py-2">
					<div>
						<span class="font-medium">{e.name}</span>
						<div class="mt-0.5 text-xs text-neutral-500">
							{catLabel(e.category)}{e.primary_muscle_names?.length ? ` · ${e.primary_muscle_names.join(', ')}` : ''}
						</div>
					</div>
					{#if canEdit}
						<div class="flex shrink-0 items-center gap-2 text-xs">
							<button onclick={() => openEdit(e)} class="text-orange-400 hover:text-orange-300">Edit</button>
							<button onclick={() => remove(e)} class="text-neutral-600 hover:text-red-300">✕</button>
						</div>
					{/if}
				</div>
				{#if editingId === e.id}<div class="px-3 pb-3">{@render fields()}</div>{/if}
			</div>
		{:else}
			<p class="text-sm text-neutral-500">No custom exercises yet.</p>
		{/each}
	</div>

	{#if canEdit}
		{#if adding}
			<div class="mt-3 max-w-2xl">{@render fields()}</div>
		{:else}
			<button onclick={openAdd} class="mt-3 rounded-full border border-neutral-700 px-4 py-1.5 text-sm text-neutral-200 hover:bg-neutral-900">＋ New exercise</button>
		{/if}
	{/if}
{/if}
