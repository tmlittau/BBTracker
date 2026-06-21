<script lang="ts">
	import { onMount } from 'svelte';
	import { protocolsApi, type WeekPrepPlan, type WeekPrepSlot } from '$lib/protocols/api';
	import { isoDate } from '$lib/date';

	let plan = $state<WeekPrepPlan | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let weekOffset = $state(0);

	function mondayISO(offset: number): string {
		const t = new Date();
		const wd = (t.getDay() + 6) % 7; // Mon=0 … Sun=6
		return isoDate(new Date(t.getFullYear(), t.getMonth(), t.getDate() - wd + offset * 7));
	}

	async function load(off: number) {
		loading = true;
		error = null;
		try {
			plan = await protocolsApi.weekPrep(mondayISO(off));
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		weekOffset = new Date().getDay() === 0 ? 1 : 0; // Sunday → prep next week
		load(weekOffset);
	});

	function go(delta: number) {
		weekOffset += delta;
		load(weekOffset);
	}

	const todayISO = isoDate();
	const fmt = (iso: string) =>
		new Date(iso + 'T00:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
	const exceptions = $derived(
		(plan?.days ?? []).filter((d) => d.added.length > 0 || d.removed.length > 0)
	);
	const hasPlan = $derived(!!plan && (plan.everyday.length > 0 || exceptions.length > 0));
	const pill =
		'inline-flex items-center justify-center rounded-full border border-neutral-700 px-3.5 py-1.5 text-sm text-neutral-200 transition hover:border-neutral-500 hover:text-white';
</script>

{#snippet slotBlock(slots: WeekPrepSlot[], mode: 'base' | 'added' | 'removed')}
	{#each slots as s (s.slot)}
		<div>
			<p class="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
				{s.slot_label}
			</p>
			<ul class="mt-0.5 space-y-0.5">
				{#each s.entries as e (e.name + e.amount)}
					<li class="flex items-baseline gap-2 text-sm {mode === 'removed' ? 'opacity-70' : ''}">
						{#if mode === 'added'}<span class="font-semibold text-emerald-400">+</span>
						{:else if mode === 'removed'}<span class="font-semibold text-red-400">−</span>{/if}
						<span
							class="shrink-0 font-semibold {e.kind === 'compound'
								? 'text-orange-300'
								: 'text-emerald-300'} {mode === 'removed' ? 'line-through' : ''}">{e.amount}</span
						>
						<span class="text-neutral-300 {mode === 'removed' ? 'line-through' : ''}">{e.name}</span>
					</li>
				{/each}
			</ul>
		</div>
	{/each}
{/snippet}

<a class="text-sm text-neutral-400 hover:text-white" href="/dashboard">← Dashboard</a>
<div class="mt-1 flex flex-wrap items-start justify-between gap-3">
	<div>
		<h1 class="text-xl font-semibold">Week prep</h1>
		<p class="text-sm text-neutral-400">
			Oral compounds &amp; supplements to portion into your daily pill boxes.
		</p>
	</div>
	{#if hasPlan}
		<button class={pill} onclick={() => window.print()}>Print</button>
	{/if}
</div>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if plan}
	<div class="mt-4 flex items-center justify-between gap-3">
		<button class={pill} onclick={() => go(-1)} aria-label="Previous week">←</button>
		<div class="text-center">
			<p class="text-sm font-medium">{fmt(plan.start)} – {fmt(plan.end)}</p>
			<p class="text-xs text-neutral-500">
				{#if plan.protocols.length}{plan.protocols.join(' → ')}{:else}No protocol scheduled{/if}{#if weekOffset === 0}
					· this week{:else if weekOffset === 1} · next week{/if}
			</p>
		</div>
		<button class={pill} onclick={() => go(1)} aria-label="Next week">→</button>
	</div>

	{#if !hasPlan}
		<p class="mt-6 text-sm text-neutral-400">
			Nothing to portion this week — no protocol with oral compounds or supplements is in force.
			Set one in <a class="text-orange-400 hover:text-orange-300" href="/phases">Phases</a> or
			<a class="text-orange-400 hover:text-orange-300" href="/protocols/manage">Protocols</a>.
		</p>
	{:else}
		<div class="mt-4 grid gap-3 lg:grid-cols-3">
			<!-- Every day baseline -->
			<div class="rounded-lg border border-orange-500/50 bg-orange-500/5 p-3 lg:row-span-2">
				<h2 class="text-sm font-semibold uppercase tracking-wide text-orange-300">Every day</h2>
				{#if plan.everyday.length === 0}
					<p class="mt-2 text-xs text-neutral-500">Nothing taken every day this week.</p>
				{:else}
					<div class="mt-2 space-y-2">{@render slotBlock(plan.everyday, 'base')}</div>
				{/if}
			</div>

			<!-- Exceptions -->
			{#if exceptions.length === 0}
				<div class="rounded-lg border border-neutral-800 p-3 text-sm text-neutral-400 lg:col-span-2">
					No exceptions — every day is the same this week. 🎉
				</div>
			{:else}
				{#each exceptions as day (day.date)}
					<div
						class="rounded-lg border p-3 {day.date === todayISO
							? 'border-orange-500/60 bg-orange-500/5'
							: 'border-neutral-800'}"
					>
						<div class="flex items-baseline justify-between gap-2">
							<h2 class="font-semibold">{day.label}</h2>
							<span class="text-xs text-neutral-500"
								>{fmt(day.date)}{day.date === todayISO ? ' · today' : ''}</span
							>
						</div>
						<div class="mt-2 space-y-2">
							{@render slotBlock(day.removed, 'removed')}
							{@render slotBlock(day.added, 'added')}
						</div>
					</div>
				{/each}
			{/if}
		</div>

		<p class="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-600">
			<span><span class="font-semibold text-orange-300">orange</span> = compound dose</span>
			<span><span class="font-semibold text-emerald-300">green</span> = supplement servings</span>
			<span><span class="text-emerald-400">+</span> extra that day · <span class="text-red-400">−</span> skipped that day</span>
			<span>Days not shown follow “Every day”.</span>
		</p>
	{/if}
{/if}
