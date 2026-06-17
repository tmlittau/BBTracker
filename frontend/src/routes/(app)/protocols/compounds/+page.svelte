<script lang="ts">
	import { onMount } from 'svelte';
	import {
		protocolsApi,
		COMPOUND_CLASSES,
		compoundClassLabel,
		type Compound
	} from '$lib/protocols/api';
	import CompoundCreateModal from '$lib/protocols/CompoundCreateModal.svelte';

	let compounds = $state<Compound[]>([]);
	let query = $state('');
	let activeClass = $state<string | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let showModal = $state(false);
	let editing = $state<Compound | null>(null);

	// The whole reference list loads once; filtering by class + name is instant
	// client-side (the API returns every compound, no 50-row page cap).
	const filtered = $derived(
		compounds.filter(
			(c) =>
				(activeClass == null || c.compound_class === activeClass) &&
				c.name.toLowerCase().includes(query.trim().toLowerCase())
		)
	);

	function onCreated(c: Compound) {
		compounds = [c, ...compounds];
	}
	function onUpdated(c: Compound) {
		compounds = compounds.map((x) => (x.id === c.id ? c : x));
	}
	async function remove(c: Compound) {
		if (!confirm(`Delete "${c.name}"?`)) return;
		await protocolsApi.deleteCompound(c.id);
		compounds = compounds.filter((x) => x.id !== c.id);
	}

	async function load() {
		loading = true;
		try {
			compounds = await protocolsApi.compounds();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<CompoundCreateModal
	bind:open={showModal}
	oncreated={onCreated}
	onupdated={onUpdated}
	edit={editing}
	onclose={() => (editing = null)}
/>

<div class="flex items-center justify-between">
	<h1 class="text-xl font-semibold">Compound library</h1>
	<button
		class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
		onclick={() => { editing = null; showModal = true; }}
	>
		New compound
	</button>
</div>
<p class="mt-1 text-xs text-neutral-500">
	Reference half-lives and ester active fractions are factual constants. To see release curves over
	time, open a protocol under <a class="text-indigo-400 hover:text-indigo-300" href="/protocols/manage">Manage</a> — the
	curve combines a compound's logged and scheduled doses.
</p>

<div class="mt-4 space-y-3">
	<input
		placeholder="Search compounds…"
		bind:value={query}
		class="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100 outline-none focus:border-indigo-500"
	/>
	<div class="flex flex-wrap gap-1.5">
		<button
			type="button"
			class="rounded-full px-3 py-1 text-xs {activeClass == null
				? 'bg-indigo-600 text-white'
				: 'border border-neutral-700 text-neutral-300'}"
			onclick={() => (activeClass = null)}>All</button
		>
		{#each COMPOUND_CLASSES as g (g.key)}
			<button
				type="button"
				class="rounded-full px-3 py-1 text-xs {activeClass === g.key
					? 'bg-indigo-600 text-white'
					: 'border border-neutral-700 text-neutral-300'}"
				onclick={() => (activeClass = g.key)}>{g.label}</button
			>
		{/each}
	</div>
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else}
	<p class="mt-3 text-xs text-neutral-500">{filtered.length} of {compounds.length} compounds</p>
	<ul class="mt-2 divide-y divide-neutral-800">
		{#each filtered as c (c.id)}
			<li class="flex items-start justify-between gap-2 py-3">
				<div>
					<span class="font-medium">{c.name}</span>
				{#if !c.is_global}
					<span class="ml-2 rounded bg-indigo-900 px-1.5 py-0.5 text-xs text-indigo-300">Custom</span>
				{/if}
				<div class="text-xs text-neutral-500">
					{compoundClassLabel(c.compound_class)}{c.ester ? ` · ${c.ester}` : ''}
					{#if c.half_life_hours}· t½ {Number(c.half_life_hours)} h{/if}
					· active {(Number(c.active_fraction) * 100).toFixed(0)}%
				</div>
				</div>
				{#if !c.is_global}
					<div class="flex shrink-0 items-center gap-3 text-xs">
						<button class="text-indigo-400 hover:text-indigo-300" onclick={() => { editing = c; showModal = true; }}>Edit</button>
						<button class="text-red-400 hover:text-red-300" onclick={() => remove(c)}>Delete</button>
					</div>
				{/if}
			</li>
		{/each}
	</ul>
	{#if filtered.length === 0}
		<p class="mt-4 text-sm text-neutral-500">No compounds match this filter.</p>
	{/if}
{/if}
