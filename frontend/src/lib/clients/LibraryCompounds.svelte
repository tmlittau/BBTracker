<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import {
		clientPlan,
		writeError,
		COMPOUND_CLASSES,
		DOSE_UNITS,
		ROUTES,
		type Compound
	} from './plan';
	import { CLIENT_CTX, type ClientContext } from './context';

	let { clientId }: { clientId: number } = $props();
	const plan = $derived(clientPlan(clientId));
	const ctx = getContext<ClientContext>(CLIENT_CTX);
	const canEdit = $derived(ctx?.canEdit ?? false);

	let all = $state<Compound[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let busy = $state(false);
	let search = $state('');

	const custom = $derived(
		all.filter((c) => !c.is_global).filter((c) => c.name.toLowerCase().includes(search.trim().toLowerCase()))
	);
	const globalCount = $derived(all.filter((c) => c.is_global).length);

	type Draft = {
		name: string;
		compound_class: string;
		default_unit: string;
		default_route: string;
		half_life_hours: string;
		ester: string;
		notes: string;
	};
	const emptyDraft = (): Draft => ({
		name: '',
		compound_class: 'anabolic',
		default_unit: 'mg',
		default_route: 'im',
		half_life_hours: '',
		ester: '',
		notes: ''
	});
	const fromItem = (c: Compound): Draft => ({
		name: c.name,
		compound_class: c.compound_class,
		default_unit: c.default_unit,
		default_route: c.default_route,
		half_life_hours: c.half_life_hours ?? '',
		ester: c.ester,
		notes: c.notes
	});

	let adding = $state(false);
	let editingId = $state<number | null>(null);
	let draft = $state<Draft>(emptyDraft());

	async function load() {
		loading = true;
		error = null;
		try {
			all = await plan.compounds();
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
	function openEdit(c: Compound) {
		adding = false;
		editingId = c.id;
		draft = fromItem(c);
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
				compound_class: draft.compound_class,
				default_unit: draft.default_unit,
				default_route: draft.default_route,
				half_life_hours: draft.half_life_hours.trim() || null,
				ester: draft.ester.trim(),
				notes: draft.notes.trim()
			};
			if (editingId != null) await plan.updateCompound(editingId, body);
			else await plan.createCompound(body);
			cancel();
			await load();
		} catch (e) {
			error = writeError(e);
		} finally {
			busy = false;
		}
	}

	async function remove(c: Compound) {
		if (!confirm(`Delete compound “${c.name}”?`)) return;
		error = null;
		try {
			await plan.deleteCompound(c.id);
			await load();
		} catch (e) {
			error = writeError(e);
		}
	}

	const classLabel = (v: string) => COMPOUND_CLASSES.find((o) => o.value === v)?.label ?? v;
	const routeLabel = (v: string) => ROUTES.find((o) => o.value === v)?.label ?? v;
</script>

{#snippet fields()}
	<div class="mt-2 space-y-3 rounded-md border border-neutral-800 bg-neutral-950 p-3">
		<input placeholder="Name (e.g. Testosterone Enanthate)" bind:value={draft.name} class="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100" />
		<div class="flex flex-wrap gap-2">
			<label class="flex flex-1 flex-col text-xs text-neutral-500">
				Class
				<select bind:value={draft.compound_class} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100">
					{#each COMPOUND_CLASSES as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
				</select>
			</label>
			<label class="flex flex-1 flex-col text-xs text-neutral-500">
				Default unit
				<select bind:value={draft.default_unit} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100">
					{#each DOSE_UNITS as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
				</select>
			</label>
			<label class="flex flex-1 flex-col text-xs text-neutral-500">
				Default route
				<select bind:value={draft.default_route} class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100">
					{#each ROUTES as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
				</select>
			</label>
		</div>
		<div class="flex flex-wrap gap-2">
			<label class="flex flex-1 flex-col text-xs text-neutral-500">
				Half-life (hours)
				<input type="number" step="0.1" bind:value={draft.half_life_hours} placeholder="optional — powers the release curve" class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100" />
			</label>
			<label class="flex flex-1 flex-col text-xs text-neutral-500">
				Ester
				<input bind:value={draft.ester} placeholder="optional (e.g. enanthate)" class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100" />
			</label>
		</div>
		<textarea bind:value={draft.notes} rows="2" placeholder="Notes (optional)" class="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"></textarea>
		<div class="flex items-center gap-2">
			<button onclick={save} disabled={busy || !draft.name.trim()} class="rounded-full bg-brand px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-40">
				{editingId != null ? 'Save compound' : 'Create compound'}
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
		<input placeholder="Filter custom compounds…" bind:value={search} class="w-64 rounded border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-100" />
		<span class="text-xs text-neutral-600">{globalCount} global compounds available in the builder</span>
	</div>

	<div class="mt-3 max-w-2xl space-y-2">
		{#each custom as c (c.id)}
			<div class="rounded-lg border border-neutral-800">
				<div class="flex items-center justify-between px-3 py-2">
					<div>
						<span class="font-medium">{c.name}</span>
						<div class="mt-0.5 text-xs text-neutral-500">
							{classLabel(c.compound_class)} · {c.default_unit} · {routeLabel(c.default_route)}{c.half_life_hours ? ` · t½ ${c.half_life_hours}h` : ''}
						</div>
					</div>
					{#if canEdit}
						<div class="flex shrink-0 items-center gap-2 text-xs">
							<button onclick={() => openEdit(c)} class="text-orange-400 hover:text-orange-300">Edit</button>
							<button onclick={() => remove(c)} class="text-neutral-600 hover:text-red-300">✕</button>
						</div>
					{/if}
				</div>
				{#if editingId === c.id}<div class="px-3 pb-3">{@render fields()}</div>{/if}
			</div>
		{:else}
			<p class="text-sm text-neutral-500">No custom compounds yet.</p>
		{/each}
	</div>

	{#if canEdit}
		{#if adding}
			<div class="mt-3 max-w-2xl">{@render fields()}</div>
		{:else}
			<button onclick={openAdd} class="mt-3 rounded-full border border-neutral-700 px-4 py-1.5 text-sm text-neutral-200 hover:bg-neutral-900">＋ New compound</button>
		{/if}
	{/if}
{/if}
