<script lang="ts">
	import { onMount } from 'svelte';
	import { protocolsApi, type Compound, type ConcentrationPoint } from '$lib/protocols/api';
	import ConcentrationChart from '$lib/protocols/ConcentrationChart.svelte';
	import CompoundCreateModal from '$lib/protocols/CompoundCreateModal.svelte';

	let compounds = $state<Compound[]>([]);
	let query = $state('');
	let loading = $state(true);
	let error = $state<string | null>(null);
	let showModal = $state(false);

	function onCreated(c: Compound) {
		compounds = [c, ...compounds];
	}

	let selected = $state<number | null>(null);
	let curve = $state<ConcentrationPoint[]>([]);
	let curveLoading = $state(false);

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

	async function showCurve(c: Compound) {
		selected = c.id;
		curveLoading = true;
		try {
			curve = await protocolsApi.concentration(c.id, 30);
		} finally {
			curveLoading = false;
		}
	}

	const selectedCompound = $derived(compounds.find((c) => c.id === selected));
</script>

<CompoundCreateModal bind:open={showModal} oncreated={onCreated} />

<div class="flex items-center justify-between">
	<h1 class="text-xl font-semibold">Compound library</h1>
	<button
		class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
		onclick={() => (showModal = true)}
	>
		New compound
	</button>
</div>
<p class="mt-1 text-xs text-neutral-500">
	Reference half-lives and ester active fractions are factual constants for visualising your own
	logged doses — not dosing guidance.
</p>

<div class="mt-4">
	<input
		placeholder="Search compounds…"
		bind:value={query}
		oninput={onSearch}
		class="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100 outline-none focus:border-indigo-500"
	/>
</div>

{#if selected && selectedCompound}
	<section class="mt-6 rounded-lg border border-neutral-800 p-4">
		<h2 class="font-medium">{selectedCompound.name} — active amount (30 days)</h2>
		{#if curveLoading}
			<p class="mt-2 text-sm text-neutral-400">Loading curve…</p>
		{:else}
			<ConcentrationChart points={curve} unit={selectedCompound.default_unit} />
		{/if}
	</section>
{/if}

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else}
	<ul class="mt-4 divide-y divide-neutral-800">
		{#each compounds as c (c.id)}
			<li class="flex items-center justify-between py-3">
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
				<button class="text-xs text-indigo-400 hover:text-indigo-300" onclick={() => showCurve(c)}>
					Curve
				</button>
			</li>
		{/each}
	</ul>
{/if}
