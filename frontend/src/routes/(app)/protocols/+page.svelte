<script lang="ts">
	import { onMount } from 'svelte';
	import {
		protocolsApi,
		FREQUENCIES,
		TIMES_OF_DAY,
		isScheduledToday,
		type DoseLog,
		type Protocol,
		type ProtocolItem
	} from '$lib/protocols/api';
	import { isoDate } from '$lib/date';

	let protocols = $state<Protocol[]>([]);
	let todayDoses = $state<DoseLog[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let logging = $state<number | null>(null);
	let showAllItems = $state(false);

	const today = isoDate();
	const active = $derived(protocols.find((p) => p.is_active) ?? null);

	// Administrations expected today (multi-select times, or 1 / legacy 2×/day).
	function plannedToday(item: ProtocolItem): number {
		const n = item.times_of_day?.length ?? 0;
		if (n > 0) return n;
		return item.frequency === '2x_day' ? 2 : 1;
	}
	// Doses of this item's compound/supplement already logged today.
	function loggedToday(item: ProtocolItem): number {
		return todayDoses.filter(
			(d) =>
				(item.compound != null && d.compound === item.compound) ||
				(item.supplement != null && d.supplement === item.supplement)
		).length;
	}
	// Earliest scheduled time-of-day → sort key (untimed items sort last).
	function timeOrder(item: ProtocolItem): number {
		const idxs = (item.times_of_day ?? [])
			.map((t) => TIMES_OF_DAY.findIndex((x) => x.key === t))
			.filter((i) => i >= 0);
		return idxs.length ? Math.min(...idxs) : 99;
	}

	const dueToday = $derived(
		active
			? [...active.items]
					.filter((i) => isScheduledToday(i, active.started_on))
					.sort((a, b) => timeOrder(a) - timeOrder(b))
			: []
	);
	// Default: today's items that still have a dose outstanding (earliest time on
	// top). "Show all" reveals every item — incl. done / not-due — for manual logs.
	const pending = $derived(dueToday.filter((i) => loggedToday(i) < plannedToday(i)));
	const shownItems = $derived(
		showAllItems ? [...(active?.items ?? [])].sort((a, b) => timeOrder(a) - timeOrder(b)) : pending
	);

	async function load() {
		[protocols, todayDoses] = await Promise.all([
			protocolsApi.protocols(),
			protocolsApi.doses({ date: today })
		]);
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
			todayDoses = await protocolsApi.doses({ date: today });
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
			todayDoses = await protocolsApi.doses({ date: today });
		} catch (e) {
			error = (e as Error).message;
		}
	}

	const freqLabel = (k: string) => FREQUENCIES.find((f) => f.key === k)?.label ?? k;
	const timeLabel = (t: string) => TIMES_OF_DAY.find((x) => x.key === t)?.label ?? t;
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
	<!-- Active protocol — today's schedule (full list lives under Manage) -->
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
					<p class="text-xs text-neutral-500">{showAllItems ? 'All protocol items' : "Today's schedule"}</p>
					<button class="text-xs text-indigo-400 hover:text-indigo-300" onclick={() => (showAllItems = !showAllItems)}>
						{showAllItems ? 'Show today only' : 'Show all'}
					</button>
				</div>
				{#if shownItems.length === 0}
					<p class="mt-3 rounded border border-green-900/60 bg-green-950/30 px-3 py-2 text-sm text-green-300">
						✓ All of today's doses are logged.
						<button class="text-indigo-400 hover:text-indigo-300" onclick={() => (showAllItems = true)}>Show all items</button>
					</p>
				{:else}
					<div class="mt-3 space-y-2">
						{#each shownItems as item (item.id)}
							{@const planned = plannedToday(item)}
							{@const done = loggedToday(item)}
							<div class="flex items-center justify-between gap-2 rounded border border-neutral-800 px-3 py-2 text-sm">
								<div>
									<span class="font-medium">{item.item_name}</span>
									<span class="text-xs text-neutral-500">
										· {item.dose_amount ?? '—'}{item.dose_unit} · {freqLabel(item.frequency)}
										{#if item.times_of_day?.length}· {item.times_of_day.map(timeLabel).join(', ')}{/if}
									</span>
								</div>
								<div class="flex shrink-0 items-center gap-2">
									{#if done > 0}
										<span class="text-xs {done >= planned ? 'text-green-400' : 'text-amber-400'}" title="Logged today">{done}/{planned}</span>
									{/if}
									{#if done < planned}
										<button
											class="rounded bg-indigo-600 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
											disabled={logging === item.id}
											onclick={() => quickLog(item)}
										>
											{logging === item.id ? '…' : done > 0 ? 'Log next' : 'Log now'}
										</button>
									{:else}
										<span class="text-xs text-green-400" title="Done for today">✓</span>
									{/if}
								</div>
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

	<!-- Today's loggings (older entries live on the History page) -->
	<section class="mt-8">
		<div class="flex items-center justify-between gap-2">
			<h2 class="font-medium">Today's doses</h2>
			<div class="flex items-center gap-4 text-sm">
				<a class="text-indigo-400 hover:text-indigo-300" href="/protocols/history">History →</a>
				<a class="text-indigo-400 hover:text-indigo-300" href="/protocols/manage">Manage →</a>
			</div>
		</div>
		{#if todayDoses.length === 0}
			<p class="mt-2 text-sm text-neutral-500">Nothing logged today yet.</p>
		{:else}
			<div class="mt-3 space-y-2">
				{#each todayDoses as d (d.id)}
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
		{/if}
	</section>
{/if}
