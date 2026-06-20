<script lang="ts">
	import { onMount } from 'svelte';
	import {
		protocolsApi,
		isScheduledToday,
		TIMES_OF_DAY,
		WEEKDAYS,
		type Protocol,
		type ProtocolItem
	} from '$lib/protocols/api';
	import { num } from '$lib/protocols/calc';
	import { coachingApi, type Phase } from '$lib/coaching/api';
	import { isoDate } from '$lib/date';

	let protocols = $state<Protocol[]>([]);
	let phases = $state<Phase[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	// Sunday prep → default to the upcoming week; otherwise the current week.
	let weekOffset = $state(0);

	onMount(async () => {
		if (new Date().getDay() === 0) weekOffset = 1;
		try {
			[protocols, phases] = await Promise.all([protocolsApi.protocols(), coachingApi.phases()]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	// The protocol in force on a date = the latest phase adjustment (across phases)
	// on/before that date that sets a protocol; it carries forward until the next
	// such change. Falls back to the active protocol when no adjustment applies.
	// This is what makes a phase adjustment actually drive the plan for its week.
	function resolveProtocol(date: Date): Protocol | null {
		const ds = isoDate(date);
		let best: { date: string; pid: number } | null = null;
		for (const ph of phases) {
			for (const a of ph.adjustments) {
				if (a.protocol == null) continue;
				if (a.effective_date <= ds && (!best || a.effective_date > best.date)) {
					best = { date: a.effective_date, pid: a.protocol };
				}
			}
		}
		if (best) {
			const p = protocols.find((x) => x.id === best!.pid);
			if (p) return p;
		}
		return protocols.find((p) => p.is_active) ?? null;
	}

	// Pillbox items = oral compounds + all supplements; injectables and as-needed
	// meds are excluded (you don't pre-portion those into daily boxes).
	const effectiveRoute = (i: ProtocolItem) => i.route || i.compound_route || '';
	const isPillbox = (i: ProtocolItem) =>
		i.frequency !== 'prn' &&
		i.frequency !== 'as_needed' &&
		(i.supplement != null || effectiveRoute(i) === 'oral');

	function mondayOf(d: Date): Date {
		const wd = (d.getDay() + 6) % 7; // Mon=0 … Sun=6
		return new Date(d.getFullYear(), d.getMonth(), d.getDate() - wd);
	}
	function addDays(d: Date, n: number): Date {
		return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
	}
	const weekStart = $derived(addDays(mondayOf(new Date()), weekOffset * 7));

	// Time-of-day compartments, plus a catch-all for untimed daily items.
	const SLOTS = [...TIMES_OF_DAY, { key: 'anytime', label: 'Anytime' }];

	type Entry = { amount: string; name: string; kind: 'compound' | 'supplement' };
	const COUNT_UNITS = new Set(['capsule', 'tablet', 'softgel', 'serving', 'scoop', 'gummy']);
	function entryFor(i: ProtocolItem): Entry {
		const qty = num(i.dose_amount);
		const unit = i.dose_unit || '';
		let amount: string;
		if (i.supplement != null) {
			const u = COUNT_UNITS.has(unit) ? `${unit}${qty === 1 ? '' : 's'}` : unit;
			amount = u ? `${qty} ${u}` : `${qty}×`;
		} else {
			amount = `${qty} ${unit}`.trim();
		}
		return { amount, name: i.item_name, kind: i.supplement != null ? 'supplement' : 'compound' };
	}

	type DaySlot = { key: string; label: string; entries: Entry[] };
	type DayPlan = {
		label: string;
		date: Date;
		isToday: boolean;
		protocol: Protocol | null;
		slots: DaySlot[];
	};
	const week = $derived.by<DayPlan[]>(() => {
		const todayKey = new Date().toDateString();
		return WEEKDAYS.map((wd, i) => {
			const date = addDays(weekStart, i);
			const proto = resolveProtocol(date);
			const due = (proto?.items ?? [])
				.filter(isPillbox)
				.filter((it) => isScheduledToday(it, proto?.started_on ?? null, date));
			const slots = SLOTS.map((s) => ({
				key: s.key,
				label: s.label,
				entries: due
					.filter((it) =>
						it.times_of_day?.length ? it.times_of_day.includes(s.key) : s.key === 'anytime'
					)
					.map(entryFor)
			})).filter((s) => s.entries.length > 0);
			return { label: wd.label, date, isToday: date.toDateString() === todayKey, protocol: proto, slots };
		});
	});

	// Distinct protocols across the visible week (to show switches in the header).
	const weekProtocols = $derived.by(() => {
		const seen = new Map<number, string>();
		for (const d of week) if (d.protocol) seen.set(d.protocol.id, d.protocol.name);
		return [...seen.values()];
	});
	const multiProto = $derived(weekProtocols.length > 1);
	const weekHasItems = $derived(week.some((d) => d.slots.length > 0));

	const fmt = (d: Date) => d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
	const rangeLabel = $derived(`${fmt(weekStart)} – ${fmt(addDays(weekStart, 6))}`);
	const pill =
		'inline-flex items-center justify-center rounded-full border border-neutral-700 px-3.5 py-1.5 text-sm text-neutral-200 transition hover:border-neutral-500 hover:text-white';
</script>

<a class="text-sm text-neutral-400 hover:text-white" href="/dashboard">← Dashboard</a>
<div class="mt-1 flex flex-wrap items-start justify-between gap-3">
	<div>
		<h1 class="text-xl font-semibold">Week prep</h1>
		<p class="text-sm text-neutral-400">
			Oral compounds &amp; supplements to portion into your daily pill boxes.
		</p>
	</div>
	{#if weekHasItems}
		<button class={pill} onclick={() => window.print()}>Print</button>
	{/if}
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if protocols.length === 0}
	<p class="mt-6 text-sm text-neutral-400">
		No protocols yet.
		<a class="text-orange-400 hover:text-orange-300" href="/protocols/manage">Create one →</a>
	</p>
{:else}
	<div class="mt-4 flex items-center justify-between gap-3">
		<button class={pill} onclick={() => weekOffset--} aria-label="Previous week">←</button>
		<div class="text-center">
			<p class="text-sm font-medium">{rangeLabel}</p>
			<p class="text-xs text-neutral-500">
				{#if weekProtocols.length}{weekProtocols.join(' → ')}{:else}No protocol scheduled{/if}{#if weekOffset === 0} · this week{:else if weekOffset === 1} · next week{/if}
			</p>
		</div>
		<button class={pill} onclick={() => weekOffset++} aria-label="Next week">→</button>
	</div>

	{#if !weekHasItems}
		<p class="mt-6 text-sm text-neutral-400">
			Nothing to portion this week — no protocol with oral compounds or supplements is in force.
			Set one in <a class="text-orange-400 hover:text-orange-300" href="/phases">Phases</a> or
			<a class="text-orange-400 hover:text-orange-300" href="/protocols/manage">Protocols</a>.
		</p>
	{:else}
		<div class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
			{#each week as day (day.label)}
				<div
					class="rounded-lg border p-3 {day.isToday
						? 'border-orange-500/60 bg-orange-500/5'
						: 'border-neutral-800'}"
				>
					<div class="flex items-baseline justify-between gap-2">
						<h2 class="font-semibold">{day.label}</h2>
						<span class="text-xs text-neutral-500"
							>{fmt(day.date)}{day.isToday ? ' · today' : ''}</span
						>
					</div>
					{#if multiProto && day.protocol}
						<p class="mt-0.5 text-[10px] uppercase tracking-wide text-violet-300/80">
							{day.protocol.name}
						</p>
					{/if}
					{#if day.slots.length === 0}
						<p class="mt-2 text-xs text-neutral-600">No orals</p>
					{:else}
						<div class="mt-2 space-y-2">
							{#each day.slots as slot (slot.key)}
								<div>
									<p class="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
										{slot.label}
									</p>
									<ul class="mt-0.5 space-y-0.5">
										{#each slot.entries as e (e.name + e.amount)}
											<li class="flex items-baseline gap-2 text-sm">
												<span
													class="shrink-0 font-semibold {e.kind === 'compound'
														? 'text-orange-300'
														: 'text-emerald-300'}">{e.amount}</span
												>
												<span class="text-neutral-300">{e.name}</span>
											</li>
										{/each}
									</ul>
								</div>
							{/each}
						</div>
					{/if}
				</div>
			{/each}
		</div>

		<p class="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-600">
			<span><span class="font-semibold text-orange-300">orange</span> = compound dose</span>
			<span><span class="font-semibold text-emerald-300">green</span> = supplement servings</span>
			<span>Reflects the protocol in force each day (per your phase adjustments).</span>
		</p>
	{/if}
{/if}
