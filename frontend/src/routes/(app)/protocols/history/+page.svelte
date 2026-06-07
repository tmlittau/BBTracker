<script lang="ts">
	import { onMount } from 'svelte';
	import { protocolsApi, type DoseLog } from '$lib/protocols/api';
	import { isoDate, shiftISODate } from '$lib/date';

	// Date-bounded dose history so we never pull the entire log. Defaults to the
	// last week; widen the range as needed.
	let from = $state(shiftISODate(isoDate(), -7));
	let to = $state(isoDate());
	let doses = $state<DoseLog[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	async function load() {
		loading = true;
		error = null;
		try {
			doses = await protocolsApi.doses({ from, to });
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}
	onMount(load);

	async function removeDose(id: number) {
		if (!confirm('Delete this logged dose?')) return;
		try {
			await protocolsApi.deleteDose(id);
			doses = doses.filter((d) => d.id !== id);
		} catch (e) {
			error = (e as Error).message;
		}
	}

	// Group by calendar date, newest first.
	const grouped = $derived.by(() => {
		const map = new Map<string, DoseLog[]>();
		for (const d of doses) {
			const key = d.taken_at.slice(0, 10);
			(map.get(key) ?? map.set(key, []).get(key)!).push(d);
		}
		return [...map.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1));
	});

	const inputClass =
		'rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm text-neutral-100';
	const dayLabel = (iso: string) =>
		new Date(iso + 'T00:00:00').toLocaleDateString(undefined, {
			weekday: 'short',
			year: 'numeric',
			month: 'short',
			day: 'numeric'
		});
</script>

<h1 class="text-xl font-semibold">Dose history</h1>
<p class="mt-1 text-xs text-neutral-500">Review and clean up past loggings. Pick a date range to pull.</p>

<div class="mt-4 flex flex-wrap items-end gap-2">
	<label class="flex flex-col text-xs text-neutral-500">From
		<input type="date" bind:value={from} max={to} class="mt-1 {inputClass}" />
	</label>
	<label class="flex flex-col text-xs text-neutral-500">To
		<input type="date" bind:value={to} min={from} class="mt-1 {inputClass}" />
	</label>
	<button
		class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
		onclick={load}
	>
		Show
	</button>
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if doses.length === 0}
	<p class="mt-6 text-sm text-neutral-500">No doses logged in this range.</p>
{:else}
	<p class="mt-4 text-xs text-neutral-500">{doses.length} dose(s)</p>
	<div class="mt-2 space-y-4">
		{#each grouped as [day, list] (day)}
			<div>
				<h2 class="text-sm font-medium text-neutral-300">{dayLabel(day)}</h2>
				<div class="mt-2 space-y-2">
					{#each list as d (d.id)}
						<div class="flex items-center justify-between gap-2 rounded border border-neutral-800 px-3 py-2 text-sm">
							<span>{d.item_name}</span>
							<div class="flex items-center gap-3">
								<span class="text-xs text-neutral-500">
									{d.amount}{d.unit}
									{#if d.site_name}· {d.site_name}{/if}
									· {new Date(d.taken_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
								</span>
								<button
									class="shrink-0 text-neutral-600 hover:text-red-400"
									aria-label="Delete logged dose"
									title="Delete this logged dose"
									onclick={() => removeDose(d.id)}
								>
									✕
								</button>
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/each}
	</div>
{/if}
