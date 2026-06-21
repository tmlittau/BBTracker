<script lang="ts">
	import { onMount } from 'svelte';
	import {
		protocolsApi,
		FREQUENCIES,
		isScheduledToday,
		type Compound,
		type DoseLog,
		type Protocol,
		type ProtocolItem,
		type ProtocolRelease,
		type SiteRecency
	} from '$lib/protocols/api';
	import { SLOT_KEYS, slotLabels, timesOfDay, ensureSlotLabels } from '$lib/notifications/slots';
	import { isoDate, shiftISODate } from '$lib/date';
	import ProtocolReleaseChart from '$lib/protocols/ProtocolReleaseChart.svelte';
	import SiteSelectModal from '$lib/protocols/SiteSelectModal.svelte';

	let protocols = $state<Protocol[]>([]);
	let todayDoses = $state<DoseLog[]>([]);
	let yesterdayDoses = $state<DoseLog[]>([]);
	let compounds = $state<Compound[]>([]);
	let release = $state<ProtocolRelease | null>(null);
	let sites = $state<SiteRecency[]>([]);
	let suggestion = $state<SiteRecency | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let logging = $state<number | null>(null);

	const today = isoDate();
	const active = $derived(protocols.find((p) => p.is_active) ?? null);
	const SLOT_ORDER: Record<string, number> = Object.fromEntries(
		SLOT_KEYS.map((k, i) => [k, i])
	);
	const yesterday = shiftISODate(today, -1);
	// Template clock time per slot — used to back-log a dose missed yesterday so it
	// still counts for that day (e.g. Night → 21:00).
	const SLOT_TIME: Record<string, string> = {
		waking: '06:30', am: '10:00', noon: '15:00', pm: '19:00', night: '21:00'
	};

	// --- dose scheduling helpers (mirror the reminder/grid logic) ---
	function plannedToday(item: ProtocolItem): number {
		const n = item.times_of_day?.length ?? 0;
		return n > 0 ? n : item.frequency === '2x_day' ? 2 : 1;
	}
	function loggedToday(item: ProtocolItem): number {
		return todayDoses.filter(
			(d) =>
				(item.compound != null && d.compound === item.compound) ||
				(item.supplement != null && d.supplement === item.supplement)
		).length;
	}
	// Due at a given slot if scheduled today, the slot is in its times, and the
	// dose for this slot isn't logged yet (logging moves it to the next slot).
	function dueAtSlot(item: ProtocolItem, slotKey: string): boolean {
		const times = item.times_of_day ?? [];
		if (!times.includes(slotKey) || !isScheduledToday(item, active?.started_on ?? null)) return false;
		const cutoff = SLOT_ORDER[slotKey] ?? 0;
		const expectedBy = times.filter((t) => (SLOT_ORDER[t] ?? 0) <= cutoff).length;
		return loggedToday(item) < expectedBy;
	}
	// Untimed (daily, no slot) items still outstanding today → "Anytime".
	function dueAnytime(item: ProtocolItem): boolean {
		const times = item.times_of_day ?? [];
		if (times.length > 0 || !isScheduledToday(item, active?.started_on ?? null)) return false;
		return loggedToday(item) < plannedToday(item);
	}

	function loggedYesterday(item: ProtocolItem): number {
		return yesterdayDoses.filter(
			(d) =>
				(item.compound != null && d.compound === item.compound) ||
				(item.supplement != null && d.supplement === item.supplement)
		).length;
	}
	// Yesterday's scheduled doses that were never logged or skipped — so one missed
	// right before bed can still be recorded. Timed items list each outstanding
	// slot; untimed daily items collapse to one "Anytime". PRN is never "missed".
	const yesterdayDate = new Date(yesterday + 'T12:00:00');
	const missedYesterday = $derived(
		(active?.items ?? []).flatMap((item) => {
			if (item.frequency === 'prn' || item.frequency === 'as_needed') return [];
			if (!isScheduledToday(item, active?.started_on ?? null, yesterdayDate)) return [];
			const logged = loggedYesterday(item);
			const times = [...(item.times_of_day ?? [])].sort(
				(a, b) => (SLOT_ORDER[a] ?? 0) - (SLOT_ORDER[b] ?? 0)
			);
			if (times.length === 0) {
				const planned = item.frequency === '2x_day' ? 2 : 1;
				return logged >= planned ? [] : [{ item, slotKey: '', slotLabel: 'Anytime' }];
			}
			return times.slice(logged).map((slotKey) => ({
				item,
				slotKey,
				slotLabel: $slotLabels[slotKey] ?? slotKey
			}));
		})
	);

	const slotGroups = $derived(
		$timesOfDay
			.map((t) => ({
				key: t.key,
				label: t.label,
				items: (active?.items ?? []).filter((i) => dueAtSlot(i, t.key))
			}))
			.filter((g) => g.items.length > 0)
	);
	const anytimeItems = $derived((active?.items ?? []).filter(dueAnytime));
	const nothingDue = $derived(
		active != null && active.items.length > 0 && slotGroups.length === 0 && anytimeItems.length === 0
	);

	// --- concentration curve: manual compound selection (default: non-ancillary) ---
	let selectedCurveIds = $state<Set<number>>(new Set());
	let curveInitialized = false;
	$effect(() => {
		if (release && compounds.length && !curveInitialized) {
			curveInitialized = true;
			const classOf = new Map(compounds.map((c) => [c.id, c.compound_class]));
			const primary = release.compounds
				.filter((c) => !['ancillary', 'other'].includes(classOf.get(c.compound_id) ?? ''))
				.map((c) => c.compound_id);
			selectedCurveIds = new Set(primary.length ? primary : release.compounds.map((c) => c.compound_id));
		}
	});
	function toggleCurve(id: number) {
		const s = new Set(selectedCurveIds);
		s.has(id) ? s.delete(id) : s.add(id);
		selectedCurveIds = s;
	}
	const filteredRelease = $derived(
		release ? { ...release, compounds: release.compounds.filter((c) => selectedCurveIds.has(c.compound_id)) } : null
	);

	// --- data loading ---
	async function loadDoses() {
		[todayDoses, yesterdayDoses] = await Promise.all([
			protocolsApi.doses({ date: today }),
			protocolsApi.doses({ date: yesterday })
		]);
	}
	async function loadSites() {
		[sites, suggestion] = await Promise.all([
			protocolsApi.siteRecency(30),
			protocolsApi.suggestSite().catch(() => null as unknown as SiteRecency)
		]);
	}
	async function load() {
		[protocols, compounds] = await Promise.all([protocolsApi.protocols(), protocolsApi.compounds()]);
		await loadDoses();
		const a = protocols.find((p) => p.is_active);
		if (a) {
			release = await protocolsApi.releaseCurves(a.id).catch(() => null);
			await loadSites();
		}
	}
	onMount(async () => {
		ensureSlotLabels();
		try {
			await load();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	// --- logging (injectables prompt for a site first) ---
	const INJECTABLE = new Set(['im', 'subq']);
	// The item's own route is often blank, so fall back to the compound's default.
	const effectiveRoute = (item: ProtocolItem) => item.route || item.compound_route || '';
	const isInjectable = (item: ProtocolItem) =>
		item.compound != null && INJECTABLE.has(effectiveRoute(item));
	let pendingInjectable = $state<ProtocolItem | null>(null);
	let pendingTakenAt = $state<string | undefined>(undefined);
	let showSiteModal = $state(false);
	const pendingRoute = $derived(pendingInjectable ? effectiveRoute(pendingInjectable) : '');

	async function logItem(
		item: ProtocolItem,
		injectionSite: number | null = null,
		takenAt: string = new Date().toISOString()
	) {
		logging = item.id;
		error = null;
		try {
			await protocolsApi.logDose({
				protocol_item: item.id,
				compound: item.compound,
				supplement: item.supplement,
				taken_at: takenAt,
				amount: item.dose_amount ?? '0',
				unit: item.dose_unit,
				route: effectiveRoute(item) || undefined,
				injection_site: injectionSite
			});
			await Promise.all([loadDoses(), loadSites()]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			logging = null;
		}
	}
	function quickLog(item: ProtocolItem) {
		if (isInjectable(item)) {
			pendingInjectable = item;
			showSiteModal = true;
		} else {
			logItem(item);
		}
	}
	function onSiteChosen(siteId: number | null) {
		const item = pendingInjectable;
		const takenAt = pendingTakenAt;
		pendingInjectable = null;
		pendingTakenAt = undefined;
		if (item) logItem(item, siteId, takenAt);
	}

	// Back-log a dose missed yesterday, stamped at its slot's template time so it
	// counts for yesterday. Injectables still prompt for a site first.
	function logMissed(m: { item: ProtocolItem; slotKey: string }) {
		const time = SLOT_TIME[m.slotKey] ?? '20:00';
		const takenAt = new Date(`${yesterday}T${time}:00`).toISOString();
		if (isInjectable(m.item)) {
			pendingInjectable = m.item;
			pendingTakenAt = takenAt;
			showSiteModal = true;
		} else {
			logItem(m.item, null, takenAt);
		}
	}

	async function removeDose(id: number) {
		if (!confirm('Delete this logged dose?')) return;
		try {
			await protocolsApi.deleteDose(id);
			await loadDoses();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	// Skip = record a "not taken" decision (e.g. a sick day). It clears the item
	// from today's quick-log without feeding nutrition / release / adherence.
	async function skipItem(item: ProtocolItem) {
		logging = item.id;
		error = null;
		try {
			await protocolsApi.skipDose({
				protocol_item: item.id,
				compound: item.compound,
				supplement: item.supplement,
				taken_at: new Date().toISOString(),
				amount: item.dose_amount ?? '0',
				unit: item.dose_unit,
				route: item.route || undefined
			});
			await loadDoses();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			logging = null;
		}
	}

	const freqLabel = (k: string) => FREQUENCIES.find((f) => f.key === k)?.label ?? k;
</script>

<SiteSelectModal
	bind:open={showSiteModal}
	{sites}
	{suggestion}
	route={pendingRoute}
	compound={pendingInjectable?.item_name ?? ''}
	onconfirm={onSiteChosen}
/>

<div class="flex items-center justify-between">
	<h1 class="text-xl font-semibold">Protocols</h1>
	<div class="flex flex-wrap gap-2">
		<a
			href="/protocols/manage"
			class="rounded-full border border-neutral-700 px-4 py-2 text-sm hover:border-neutral-500"
		>
			Manage
		</a>
		<a
			href="/protocols/schedule"
			class="rounded-full border border-neutral-700 px-4 py-2 text-sm hover:border-neutral-500"
		>
			Dose table
		</a>
		<a
			href="/protocols/log"
			class="rounded-full bg-brand px-4 py-2 text-sm font-medium text-white hover:brightness-110"
		>
			Log a dose
		</a>
	</div>
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if !active}
	<p class="mt-6 text-sm text-neutral-500">
		No active protocol.
		<a class="text-orange-400 hover:text-orange-300" href="/protocols/manage">Activate or create one</a>
	</p>
{:else}
	<div class="mt-6 flex items-center justify-between">
		<h2 class="font-medium">
			{active.name}
			<span class="ml-1 rounded bg-green-900 px-2 py-0.5 text-xs text-green-300">Active</span>
		</h2>
		<a class="arrow-link" href={`/protocols/manage/${active.id}`}>Edit</a>
	</div>

	{#if missedYesterday.length > 0}
		<section class="mt-4 rounded-lg border border-amber-800/60 bg-amber-950/20 p-3">
			<h3 class="text-xs font-medium uppercase tracking-wide text-amber-400">Yesterday — not logged</h3>
			<div class="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
				{#each missedYesterday as m (m.item.id + ':' + m.slotKey)}
					<button
						class="rounded-lg border border-amber-900/50 px-3 py-2 text-left text-sm hover:border-amber-600 disabled:opacity-50"
						disabled={logging === m.item.id}
						onclick={() => logMissed(m)}
					>
						<span class="block truncate font-medium">{m.item.item_name}</span>
						<span class="text-xs text-neutral-500">
							{m.item.dose_amount ?? '—'}{m.item.dose_unit} · {m.slotLabel}
							{#if isInjectable(m.item)}· 💉{/if}
						</span>
					</button>
				{/each}
			</div>
			<p class="mt-2 text-[11px] text-neutral-500">Logs against yesterday at the slot's usual time.</p>
		</section>
	{/if}

	<!-- Quick log, grouped by time of day. Logging a multi-dose item moves it to its next slot. -->
	<section class="mt-4">
		{#if active.items.length === 0}
			<p class="text-sm text-neutral-500">
				No items yet. <a class="text-orange-400 hover:text-orange-300" href={`/protocols/manage/${active.id}`}>Add some</a>
			</p>
		{:else if nothingDue}
			<p class="rounded border border-green-900/60 bg-green-950/30 px-3 py-2 text-sm text-green-300">
				✓ All of today's doses are logged.
			</p>
		{:else}
			<div class="space-y-4">
				{#each slotGroups as group (group.key)}
					<div>
						<h3 class="text-xs font-medium uppercase tracking-wide text-neutral-500">{group.label}</h3>
						<div class="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
							{#each group.items as item (item.id)}
								<div class="overflow-hidden rounded-lg border border-neutral-800 text-sm hover:border-indigo-600">
									<button
										class="block w-full px-3 py-2 text-left disabled:opacity-50"
										disabled={logging === item.id}
										onclick={() => quickLog(item)}
									>
										<span class="block truncate font-medium">{item.item_name}</span>
										<span class="text-xs text-neutral-500">
											{item.dose_amount ?? '—'}{item.dose_unit}
											{#if isInjectable(item)}· 💉{/if}
											{logging === item.id ? '· …' : ''}
										</span>
									</button>
									<button
										class="block w-full border-t border-neutral-800 px-3 py-1 text-right text-xs text-neutral-500 hover:bg-neutral-900 hover:text-amber-300 disabled:opacity-50"
										disabled={logging === item.id}
										onclick={() => skipItem(item)}
									>
										Skip
									</button>
								</div>
							{/each}
						</div>
					</div>
				{/each}

				{#if anytimeItems.length}
					<div>
						<h3 class="text-xs font-medium uppercase tracking-wide text-neutral-500">Anytime</h3>
						<div class="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
							{#each anytimeItems as item (item.id)}
								<div class="overflow-hidden rounded-lg border border-neutral-800 text-sm hover:border-indigo-600">
									<button
										class="block w-full px-3 py-2 text-left disabled:opacity-50"
										disabled={logging === item.id}
										onclick={() => quickLog(item)}
									>
										<span class="block truncate font-medium">{item.item_name}</span>
										<span class="text-xs text-neutral-500">{item.dose_amount ?? '—'}{item.dose_unit} · {freqLabel(item.frequency)}</span>
									</button>
									<button
										class="block w-full border-t border-neutral-800 px-3 py-1 text-right text-xs text-neutral-500 hover:bg-neutral-900 hover:text-amber-300 disabled:opacity-50"
										disabled={logging === item.id}
										onclick={() => skipItem(item)}
									>
										Skip
									</button>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</section>

	<!-- Concentration curve: choose which compounds to plot. -->
	{#if release && release.compounds.length}
		<section class="mt-8 rounded-lg border border-neutral-800 p-4">
			<h2 class="font-medium">Concentration</h2>
			<p class="mt-0.5 text-xs text-neutral-500">
				Select compounds to plot (active release: solid = logged, dashed = projected).
			</p>
			<div class="mt-2 flex flex-wrap gap-2">
				{#each release.compounds as c (c.compound_id)}
					<button
						class="rounded-full border px-3 py-1 text-xs {selectedCurveIds.has(c.compound_id)
							? 'border-indigo-500 bg-indigo-950 text-indigo-200'
							: 'border-neutral-700 text-neutral-400 hover:border-neutral-500'}"
						onclick={() => toggleCurve(c.compound_id)}
					>
						{c.name}
					</button>
				{/each}
			</div>
			{#if filteredRelease && filteredRelease.compounds.length}
				<div class="mt-3"><ProtocolReleaseChart data={filteredRelease} /></div>
			{:else}
				<p class="mt-3 text-sm text-neutral-500">Pick at least one compound to plot.</p>
			{/if}
		</section>
	{/if}

	<!-- Today's loggings -->
	<section class="mt-8">
		<div class="flex items-center justify-between gap-2">
			<h2 class="font-medium">Today's doses</h2>
			<a class="arrow-link" href="/protocols/history">History</a>
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
