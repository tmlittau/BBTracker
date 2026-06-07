<script lang="ts">
	import { onMount } from 'svelte';
	import { protocolsApi, type Compound } from '$lib/protocols/api';
	import CompoundCreateModal from '$lib/protocols/CompoundCreateModal.svelte';

	let compounds = $state<Compound[]>([]);
	let query = $state('');
	let loading = $state(true);
	let error = $state<string | null>(null);
	let showModal = $state(false);
	let editing = $state<Compound | null>(null);

	function onCreated(c: Compound) {
		compounds = [c, ...compounds];
	}
	function onUpdated(c: Compound) {
		compounds = compounds.map((x) => (x.id === c.id ? c : x));
	}

	async function load() {
		loading = true;
		try {
			compounds = await protocolsApi.compounds(query.trim());
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	onMount(load);

	let timer: ReturnType<typeof setTimeout>;
	function onSearch() {
		clearTimeout(timer);
		timer = setTimeout(load, 200);
	}
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

<div class="mt-4">
	<input
		placeholder="Search compounds…"
		bind:value={query}
		oninput={onSearch}
		class="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100 outline-none focus:border-indigo-500"
	/>
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else}
	<ul class="mt-4 divide-y divide-neutral-800">
		{#each compounds as c (c.id)}
			<li class="flex items-start justify-between gap-2 py-3">
				<div>
					<span class="font-medium">{c.name}</span>
				{#if !c.is_global}
					<span class="ml-2 rounded bg-indigo-900 px-1.5 py-0.5 text-xs text-indigo-300">Custom</span>
				{/if}
				<div class="text-xs text-neutral-500">
					{c.compound_class}{c.ester ? ` · ${c.ester}` : ''}
					{#if c.half_life_hours}· t½ {Number(c.half_life_hours)} h{/if}
					· active {(Number(c.active_fraction) * 100).toFixed(0)}%
				</div>
				</div>
				{#if !c.is_global}
					<button class="shrink-0 text-xs text-indigo-400 hover:text-indigo-300" onclick={() => { editing = c; showModal = true; }}>Edit</button>
				{/if}
			</li>
		{/each}
	</ul>
{/if}
