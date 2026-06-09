<script lang="ts">
	import { onMount } from 'svelte';
	import {
		protocolsApi,
		FREQUENCIES,
		TIMES_OF_DAY,
		isScheduledToday,
		type Compound,
		type DoseLog,
		type Protocol,
		type ProtocolItem,
		type ProtocolRelease,
		type SiteRecency
	} from '$lib/protocols/api';
	import { isoDate } from '$lib/date';
	import ProtocolReleaseChart from '$lib/protocols/ProtocolReleaseChart.svelte';
	import SiteSelectModal from '$lib/protocols/SiteSelectModal.svelte';

	let protocols = $state<Protocol[]>([]);
	let todayDoses = $state<DoseLog[]>([]);
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
		TIMES_OF_DAY.map((t, i) => [t.key, i])
	);

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

	const slotGroups = $derived(
		TIMES_OF_DAY.map((t) => ({
			key: t.key,
			label: t.label,
			items: (active?.items ?? []).filter((i) => dueAtSlot(i, t.key))
		})).filter((g) => g.items.length > 0)
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
		todayDoses = await protocolsApi.doses({ date: today });
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
	let pendingInjectable = $state<ProtocolItem | null>(null);
	let showSiteModal = $state(false);

	async function logItem(item: ProtocolItem, injectionSite: number | null = null) {
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
				route: item.route || undefined,
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
		if (item.compound != null && item.route && INJECTABLE.has(item.route)) {
			pendingInjectable = item;
			showSiteModal = true;
		} else {
			logItem(item);
		}
	}
	function onSiteChosen(siteId: number | null) {
		const item = pendingInjectable;
		pendingInjectable = null;
		if (item) logItem(item, siteId);
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

	const freqLabel = (k: string) => FREQUENCIES.find((f) => f.key === k)?.label ?? k;
</script>

<SiteSelectModal bind:open={showSiteModal} {sites} {suggestion} onconfirm={onSiteChosen} />

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
{:else if !active}
	<p class="mt-6 text-sm text-neutral-500">
		No active protocol.
		<a class="text-indigo-400" href="/protocols/manage">Activate or create one →</a>
	</p>
{:else}
	<div class="mt-6 flex items-center justify-between">
		<h2 class="font-medium">
			{active.name}
			<span class="ml-1 rounded bg-green-900 px-2 py-0.5 text-xs text-green-300">Active</span>
		</h2>
		<a class="text-sm text-indigo-400 hover:text-indigo-300" href={`/protocols/manage/${active.id}`}>Edit →</a>
	</div>

	<!-- Quick log, grouped by time of day. Logging a multi-dose item moves it to its next slot. -->
	<section class="mt-4">
		{#if active.items.length === 0}
			<p class="text-sm text-neutral-500">
				No items yet. <a class="text-indigo-400" href={`/protocols/manage/${active.id}`}>Add some →</a>
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
								<button
									class="rounded-lg border border-neutral-800 px-3 py-2 text-left text-sm hover:border-indigo-600 disabled:opacity-50"
									disabled={logging === item.id}
									onclick={() => quickLog(item)}
								>
									<span class="block truncate font-medium">{item.item_name}</span>
									<span class="text-xs text-neutral-500">
										{item.dose_amount ?? '—'}{item.dose_unit}
										{#if item.compound != null && (item.route === 'im' || item.route === 'subq')}· 💉{/if}
										{logging === item.id ? '· …' : ''}
									</span>
								</button>
							{/each}
						</div>
					</div>
				{/each}

				{#if anytimeItems.length}
					<div>
						<h3 class="text-xs font-medium uppercase tracking-wide text-neutral-500">Anytime</h3>
						<div class="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
							{#each anytimeItems as item (item.id)}
								<button
									class="rounded-lg border border-neutral-800 px-3 py-2 text-left text-sm hover:border-indigo-600 disabled:opacity-50"
									disabled={logging === item.id}
									onclick={() => quickLog(item)}
								>
									<span class="block truncate font-medium">{item.item_name}</span>
									<span class="text-xs text-neutral-500">{item.dose_amount ?? '—'}{item.dose_unit} · {freqLabel(item.frequency)}</span>
								</button>
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
