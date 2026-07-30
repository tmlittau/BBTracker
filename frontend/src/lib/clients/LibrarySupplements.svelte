<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { clientPlan, writeError, type Supplement } from './plan';
	import { CLIENT_CTX, type ClientContext } from './context';

	let { clientId }: { clientId: number } = $props();
	const plan = $derived(clientPlan(clientId));
	const ctx = getContext<ClientContext>(CLIENT_CTX);
	const canEdit = $derived(ctx?.canEdit ?? false);

	let all = $state<Supplement[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let busy = $state(false);
	let search = $state('');

	const custom = $derived(
		all.filter((s) => !s.is_global).filter((s) => s.name.toLowerCase().includes(search.trim().toLowerCase()))
	);
	const globalCount = $derived(all.filter((s) => s.is_global).length);

	type Draft = { name: string; brand: string; serving_label: string; target_benefit: string; notes: string };
	const emptyDraft = (): Draft => ({ name: '', brand: '', serving_label: '', target_benefit: '', notes: '' });
	const fromItem = (s: Supplement): Draft => ({
		name: s.name,
		brand: s.brand,
		serving_label: s.serving_label,
		target_benefit: s.target_benefit,
		notes: s.notes
	});

	let adding = $state(false);
	let editingId = $state<number | null>(null);
	let draft = $state<Draft>(emptyDraft());

	async function load() {
		loading = true;
		error = null;
		try {
			all = await plan.supplements();
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
	function openEdit(s: Supplement) {
		adding = false;
		editingId = s.id;
		draft = fromItem(s);
	}
	function cancel() {
		adding = false;
		editingId = null;
	}

	async function save() {
		if (!draft.name.trim()) return;
		busy = true;
		error = null;
		try {
			const body = {
				name: draft.name.trim(),
				brand: draft.brand.trim(),
				serving_label: draft.serving_label.trim(),
				target_benefit: draft.target_benefit.trim(),
				notes: draft.notes.trim()
			};
			if (editingId != null) await plan.updateSupplement(editingId, body);
			else await plan.createSupplement(body);
			cancel();
			await load();
		} catch (e) {
			error = writeError(e);
		} finally {
			busy = false;
		}
	}

	async function remove(s: Supplement) {
		if (!confirm(`Delete supplement “${s.name}”?`)) return;
		error = null;
		try {
			await plan.deleteSupplement(s.id);
			await load();
		} catch (e) {
			error = writeError(e);
		}
	}
</script>

{#snippet fields()}
	<div class="mt-2 space-y-3 rounded-md border border-neutral-800 bg-neutral-950 p-3">
		<input placeholder="Name (e.g. Creatine Monohydrate)" bind:value={draft.name} class="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100" />
		<div class="flex flex-wrap gap-2">
			<label class="flex flex-1 flex-col text-xs text-neutral-500">
				Brand
				<input bind:value={draft.brand} placeholder="optional" class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100" />
			</label>
			<label class="flex flex-1 flex-col text-xs text-neutral-500">
				Serving label
				<input bind:value={draft.serving_label} placeholder="e.g. 1 scoop (5 g)" class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100" />
			</label>
		</div>
		<input bind:value={draft.target_benefit} placeholder="Target benefit (optional)" class="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100" />
		<textarea bind:value={draft.notes} rows="2" placeholder="Notes (optional)" class="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"></textarea>
		<div class="flex items-center gap-2">
			<button onclick={save} disabled={busy || !draft.name.trim()} class="rounded-full bg-brand px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-40">
				{editingId != null ? 'Save supplement' : 'Create supplement'}
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
		<input placeholder="Filter custom supplements…" bind:value={search} class="w-64 rounded border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-100" />
		<span class="text-xs text-neutral-600">{globalCount} global supplements available in the builder</span>
	</div>

	<div class="mt-3 max-w-2xl space-y-2">
		{#each custom as s (s.id)}
			<div class="rounded-lg border border-neutral-800">
				<div class="flex items-center justify-between px-3 py-2">
					<div>
						<span class="font-medium">{s.name}</span>
						<div class="mt-0.5 text-xs text-neutral-500">
							{[s.brand, s.serving_label, s.target_benefit].filter(Boolean).join(' · ') || '—'}
						</div>
					</div>
					{#if canEdit}
						<div class="flex shrink-0 items-center gap-2 text-xs">
							<button onclick={() => openEdit(s)} class="text-orange-400 hover:text-orange-300">Edit</button>
							<button onclick={() => remove(s)} class="text-neutral-600 hover:text-red-300">✕</button>
						</div>
					{/if}
				</div>
				{#if editingId === s.id}<div class="px-3 pb-3">{@render fields()}</div>{/if}
			</div>
		{:else}
			<p class="text-sm text-neutral-500">No custom supplements yet.</p>
		{/each}
	</div>

	{#if canEdit}
		{#if adding}
			<div class="mt-3 max-w-2xl">{@render fields()}</div>
		{:else}
			<button onclick={openAdd} class="mt-3 rounded-full border border-neutral-700 px-4 py-1.5 text-sm text-neutral-200 hover:bg-neutral-900">＋ New supplement</button>
		{/if}
	{/if}
{/if}
