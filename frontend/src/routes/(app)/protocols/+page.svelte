<script lang="ts">
	import { onMount } from 'svelte';
	import {
		protocolsApi,
		FREQUENCIES,
		isScheduledToday,
		type DoseLog,
		type Protocol,
		type ProtocolItem
	} from '$lib/protocols/api';

	let protocols = $state<Protocol[]>([]);
	let recentDoses = $state<DoseLog[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let logging = $state<number | null>(null);
	let showAllItems = $state(false);

	const active = $derived(protocols.find((p) => p.is_active) ?? null);
	// Quick-log only what's actually due today (e.g. a Sunday-only compound won't
	// appear on a Tuesday) — with an escape hatch to show the whole protocol.
	const todaysItems = $derived(
		active ? active.items.filter((i) => isScheduledToday(i, active.started_on)) : []
	);
	const shownItems = $derived(showAllItems ? (active?.items ?? []) : todaysItems);

	async function load() {
		[protocols, recentDoses] = await Promise.all([protocolsApi.protocols(), protocolsApi.doses()]);
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

	// One-tap log of an item's planned dose against the active protocol.
	async function quickLog(item: ProtocolItem) {
		logging = item.id;
		error = null;
		try {
			await protocolsApi.logDose({
				protocol_item: item.id,
				compound: item.compound,
				supplement: item.supplement,
				taken_at: new Date().toISOString(),
				amount: item.dose_amount ?? '0',
				unit: item.dose_unit,
				route: item.route || undefined
			});
			recentDoses = await protocolsApi.doses();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			logging = null;
		}
	}

	// Undo a mis-logged dose.
	async function removeDose(id: number) {
		if (!confirm('Delete this logged dose?')) return;
		try {
			await protocolsApi.deleteDose(id);
			recentDoses = await protocolsApi.doses();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	const freqLabel = (k: string) => FREQUENCIES.find((f) => f.key === k)?.label ?? k;
</script>

<div class="flex items-center justify-between">
	<h1 class="text-xl font-semibold">Protocols</h1>
	<a
		href="/protocols/log"
		class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
	>
		Log a dose
	</a>
</div>

<p class="mt-2 rounded-md border border-amber-900/60 bg-amber-950/40 px-3 py-2 text-xs text-amber-300">
	⚠️ Personal tracking only — not medical advice. BBTracker does not recommend any substance, dose,
	or protocol. Monitor your health with a qualified professional and regular bloodwork.
</p>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else}
	<!-- Active protocol only (full list lives under Manage) -->
	<section class="mt-6">
		{#if active}
			<div class="flex items-center justify-between">
				<h2 class="font-medium">
					{active.name}
					<span class="ml-1 rounded bg-green-900 px-2 py-0.5 text-xs text-green-300">Active</span>
				</h2>
				<a class="text-sm text-indigo-400 hover:text-indigo-300" href={`/protocols/manage/${active.id}`}>Edit →</a>
			</div>
			{#if active.items.length === 0}
				<p class="mt-2 text-sm text-neutral-500">
					No items yet. <a class="text-indigo-400" href={`/protocols/manage/${active.id}`}>Add some →</a>
				</p>
			{:else}
				<div class="mt-2 flex items-center justify-between">
					<p class="text-xs text-neutral-500">{showAllItems ? 'All protocol items' : 'Scheduled for today'}</p>
					<button class="text-xs text-indigo-400 hover:text-indigo-300" onclick={() => (showAllItems = !showAllItems)}>{showAllItems ? 'Show today only' : 'Show all'}</button>
				</div>
				{#if shownItems.length === 0}
					<p class="mt-2 text-sm text-neutral-500">Nothing scheduled for today. <button class="text-indigo-400 hover:text-indigo-300" onclick={() => (showAllItems = true)}>Show all items</button></p>
				{:else}
				<div class="mt-3 space-y-2">
					{#each shownItems as item (item.id)}
						<div class="flex items-center justify-between rounded border border-neutral-800 px-3 py-2 text-sm">
							<div>
								<span class="font-medium">{item.item_name}</span>
								<span class="text-xs text-neutral-500">
									· {item.dose_amount ?? '—'}{item.dose_unit} · {freqLabel(item.frequency)}
									{#if item.times_of_day?.length}· {item.times_of_day.join(', ')}{/if}
								</span>
							</div>
							<button
								class="rounded bg-indigo-600 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
								disabled={logging === item.id}
								onclick={() => quickLog(item)}
							>
								{logging === item.id ? '…' : 'Log now'}
							</button>
						</div>
					{/each}
				</div>
				{/if}
			{/if}
		{:else}
			<p class="text-sm text-neutral-500">
				No active protocol.
				<a class="text-indigo-400" href="/protocols/manage">Activate or create one →</a>
			</p>
		{/if}
	</section>

	<!-- Recent loggings + management entry point -->
	<section class="mt-8">
		<div class="flex items-center justify-between">
			<h2 class="font-medium">Recent loggings</h2>
			<a class="text-sm text-indigo-400 hover:text-indigo-300" href="/protocols/manage">Manage protocols →</a>
		</div>
		{#if recentDoses.length === 0}
			<p class="mt-2 text-sm text-neutral-500">No doses logged yet.</p>
		{:else}
			<div class="mt-3 space-y-2">
				{#each recentDoses.slice(0, 8) as d (d.id)}
					<div class="flex items-center justify-between gap-2 rounded border border-neutral-800 px-3 py-2 text-sm">
						<span>{d.item_name}</span>
						<div class="flex items-center gap-3">
							<span class="text-xs text-neutral-500">
								{d.amount}{d.unit}
								{#if d.site_name}· {d.site_name}{/if}
								· {new Date(d.taken_at).toLocaleDateString()}
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
		{/if}
	</section>
{/if}
