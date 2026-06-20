<script lang="ts">
	import { onMount } from 'svelte';
	import { protocolsApi, type Supplement } from '$lib/protocols/api';
	import { apiErrorMessage } from '$lib/api/errors';
	import { num } from '$lib/protocols/calc';
	import Button from '$lib/components/ui/Button.svelte';
	import SupplementCreateModal from '$lib/protocols/SupplementCreateModal.svelte';

	let supplements = $state<Supplement[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let showModal = $state(false);
	let editing = $state<Supplement | null>(null);

	async function load() {
		supplements = await protocolsApi.supplements();
	}

	onMount(async () => {
		try {
			await load();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	function onCreated(s: Supplement) {
		supplements = [...supplements, s].sort((a, b) => a.name.localeCompare(b.name));
	}
	function onUpdated(s: Supplement) {
		supplements = supplements
			.map((x) => (x.id === s.id ? s : x))
			.sort((a, b) => a.name.localeCompare(b.name));
	}

	async function remove(id: number) {
		if (!confirm('Delete this supplement?')) return;
		try {
			await protocolsApi.deleteSupplement(id);
			await load();
		} catch (e) {
			error = apiErrorMessage(e);
		}
	}
</script>

<SupplementCreateModal
	bind:open={showModal}
	oncreated={onCreated}
	onupdated={onUpdated}
	edit={editing}
	onclose={() => (editing = null)}
/>

<div class="flex items-center justify-between">
	<h1 class="text-xl font-semibold">Supplements</h1>
	<button
		class="rounded-full bg-brand px-4 py-2 text-sm font-medium text-white hover:brightness-110"
		onclick={() => { editing = null; showModal = true; }}
	>
		New supplement
	</button>
</div>
<p class="mt-1 text-xs text-neutral-500">
	A supplement's per-serving nutrients are added to your daily nutrition totals when you log a dose.
</p>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if supplements.length === 0}
	<p class="mt-6 text-neutral-500">No supplements yet — add your first above.</p>
{:else}
	<ul class="mt-6 divide-y divide-neutral-800">
		{#each supplements as s (s.id)}
			<li class="flex items-center justify-between py-3">
				<div>
					<span class="font-medium">{s.name}</span>
					{#if s.brand}<span class="text-neutral-500"> · {s.brand}</span>{/if}
					<div class="text-xs text-neutral-500">
						{#if s.target_benefit}{s.target_benefit} · {/if}
						{s.supplement_nutrients.length} nutrient(s)
						{#if s.supplement_nutrients.length}
							: {s.supplement_nutrients
								.map((n) => `${n.nutrient_name ?? ''} ${num(n.amount_per_serving)}${n.unit ?? ''}`)
								.join(', ')}
						{/if}
					</div>
				</div>
				<div class="flex shrink-0 items-center gap-3">
					<button class="text-xs text-orange-400 hover:text-orange-300" onclick={() => { editing = s; showModal = true; }}>Edit</button>
					<button class="text-xs text-red-400 hover:text-red-300" onclick={() => remove(s.id)}>Delete</button>
				</div>
			</li>
		{/each}
	</ul>
{/if}
