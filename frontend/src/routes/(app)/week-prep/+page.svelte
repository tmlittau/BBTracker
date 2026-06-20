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

	let protocols = $state<Protocol[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	// Sunday prep → default to the upcoming week; otherwise the current week.
	let weekOffset = $state(0);

	onMount(async () => {
		if (new Date().getDay() === 0) weekOffset = 1;
		try {
			protocols = await protocolsApi.protocols();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	const active = $derived(protocols.find((p) => p.is_active) ?? null);

	// Pillbox items = oral compounds + all supplements; injectables and as-needed
	// meds are excluded (you don't pre-portion those into daily boxes).
	const effectiveRoute = (i: ProtocolItem) => i.route || i.compound_route || '';
	const isPillbox = (i: ProtocolItem) =>
		i.frequency !== 'prn' &&
		i.frequency !== 'as_needed' &&
		(i.supplement != null || effectiveRoute(i) === 'oral');
	const pillItems = $derived((active?.items ?? []).filter(isPillbox));

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
	type DayPlan = { label: string; date: Date; isToday: boolean; slots: DaySlot[] };
	const week = $derived.by<DayPlan[]>(() => {
		if (!active) return [];
		const todayKey = new Date().toDateString();
		return WEEKDAYS.map((wd, i) => {
			const date = addDays(weekStart, i);
			const due = pillItems.filter((it) => isScheduledToday(it, active.started_on, date));
			const slots = SLOTS.map((s) => ({
				key: s.key,
				label: s.label,
				entries: due
					.filter((it) =>
						it.times_of_day?.length ? it.times_of_day.includes(s.key) : s.key === 'anytime'
					)
					.map(entryFor)
			})).filter((s) => s.entries.length > 0);
			return { label: wd.label, date, isToday: date.toDateString() === todayKey, slots };
		});
	});

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
	{#if active && pillItems.length}
		<button class={pill} onclick={() => window.print()}>Print</button>
	{/if}
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if !active}
	<p class="mt-6 text-sm text-neutral-400">
		No active protocol.
		<a class="text-orange-400 hover:text-orange-300" href="/protocols/manage">Activate or create one →</a>
	</p>
{:else if pillItems.length === 0}
	<p class="mt-6 text-sm text-neutral-400">
		No oral compounds or supplements in <span class="text-neutral-200">{active.name}</span> —
		nothing to portion.
	</p>
{:else}
	<div class="mt-4 flex items-center justify-between gap-3">
		<button class={pill} onclick={() => weekOffset--} aria-label="Previous week">←</button>
		<div class="text-center">
			<p class="text-sm font-medium">{rangeLabel}</p>
			<p class="text-xs text-neutral-500">
				{active.name}{#if weekOffset === 0} · this week{:else if weekOffset === 1} · next week{/if}
			</p>
		</div>
		<button class={pill} onclick={() => weekOffset++} aria-label="Next week">→</button>
	</div>

	<div class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
		{#each week as day (day.label)}
			<div
				class="rounded-lg border p-3 {day.isToday
					? 'border-orange-500/60 bg-orange-500/5'
					: 'border-neutral-800'}"
			>
				<div class="flex items-baseline justify-between">
					<h2 class="font-semibold">{day.label}</h2>
					<span class="text-xs text-neutral-500">{fmt(day.date)}{day.isToday ? ' · today' : ''}</span>
				</div>
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
		<span>Injectables &amp; as-needed items are excluded.</span>
	</p>
{/if}
