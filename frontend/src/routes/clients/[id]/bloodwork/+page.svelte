<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { clientPlan } from '$lib/clients/plan';
	import type { BloodMarkerRow } from '$lib/coaching/api';

	const clientId = $derived(Number($page.params.id));
	const plan = $derived(clientPlan(clientId));
	let markers = $state<BloodMarkerRow[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			const body = await plan.body();
			markers = (body.bloodwork?.markers ?? []) as BloodMarkerRow[];
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	const flagColor = (f?: string) =>
		f === 'high' || f === 'low' ? 'text-red-400' : f === 'in_range' ? 'text-emerald-400' : 'text-neutral-400';
</script>

<div class="p-6">
	<h2 class="text-sm font-semibold text-neutral-300">Bloodwork</h2>
	{#if error}<p class="mt-2 text-sm text-red-400">{error}</p>{/if}
	{#if loading}
		<p class="mt-3 text-neutral-400">Loading…</p>
	{:else if markers.length === 0}
		<p class="mt-3 text-sm text-neutral-500">No bloodwork on file for this client.</p>
	{:else}
		<table class="mt-3 w-full max-w-2xl text-sm">
			<thead class="text-left text-xs uppercase tracking-wide text-neutral-500">
				<tr class="border-b border-neutral-800"><th class="py-2">Marker</th><th class="py-2 text-right">Value</th><th class="py-2 text-right">Flag</th></tr>
			</thead>
			<tbody>
				{#each markers as m (m.name)}
					<tr class="border-b border-neutral-800/60">
						<td class="py-2">{m.name}</td>
						<td class="py-2 text-right tabular-nums">{m.value} {m.unit}</td>
						<td class="py-2 text-right {flagColor(m.flag)}">{m.flag ?? '—'}</td>
					</tr>
				{/each}
			</tbody>
		</table>
		<p class="mt-3 text-xs text-neutral-600">Marker-vs-protocol trend charts + out-of-range safety alerts are Phase 5.</p>
	{/if}
</div>
