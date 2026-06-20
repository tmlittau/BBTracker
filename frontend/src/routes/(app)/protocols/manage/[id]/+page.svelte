<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import {
		protocolsApi,
		COMPOUND_CLASSES,
		FREQUENCIES,
		WEEKDAYS,
		TIMES_OF_DAY,
		type AdherenceRow,
		type Compound,
		type Protocol,
		type Supplement
	} from '$lib/protocols/api';
	import { num } from '$lib/protocols/calc';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import CompoundCreateModal from '$lib/protocols/CompoundCreateModal.svelte';
	import SupplementCreateModal from '$lib/protocols/SupplementCreateModal.svelte';
	import SearchSelect from '$lib/components/ui/SearchSelect.svelte';

	const protocolId = Number($page.params.id);

	let protocol = $state<Protocol | null>(null);
	let compounds = $state<Compound[]>([]);
	let supplements = $state<Supplement[]>([]);
	let adherence = $state<AdherenceRow[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	// add-item form
	let kind = $state<'compound' | 'supplement'>('compound');
	let refId = $state<number | null>(null);
	let dose = $state('');
	let unit = $state('mg');
	let frequency = $state('daily');
	let daysOfWeek = $state<number[]>([]);
	let timesOfDay = $state<string[]>([]);
	let showCompoundModal = $state(false);
	let showSupplementModal = $state(false);

	const selectClass = 'rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100';

	// Options for the searchable picker — compounds carry a class (chip filter) +
	// ester hint; supplements are a plain searchable list.
	const pickerOptions = $derived(
		kind === 'compound'
			? compounds.map((c) => ({
					id: c.id,
					label: c.name,
					group: c.compound_class,
					badge: c.ester || undefined
				}))
			: supplements.map((s) => ({ id: s.id, label: s.name }))
	);
	const pickerGroups = $derived(kind === 'compound' ? COMPOUND_CLASSES : []);

	async function load() {
		protocol = await protocolsApi.protocol(protocolId);
		adherence = await protocolsApi.adherence(protocolId).catch(() => []);
	}

	onMount(async () => {
		try {
			[, compounds, supplements] = await Promise.all([
				load(),
				protocolsApi.compounds(),
				protocolsApi.supplements()
			]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	function toggleDay(d: number) {
		daysOfWeek = daysOfWeek.includes(d) ? daysOfWeek.filter((x) => x !== d) : [...daysOfWeek, d];
	}
	function toggleTime(t: string) {
		timesOfDay = timesOfDay.includes(t) ? timesOfDay.filter((x) => x !== t) : [...timesOfDay, t];
	}

	async function addItem(e: SubmitEvent) {
		e.preventDefault();
		if (refId == null) return;
		try {
			await protocolsApi.createItem({
				protocol: protocolId,
				compound: kind === 'compound' ? refId : null,
				supplement: kind === 'supplement' ? refId : null,
				dose_amount: dose === '' ? null : String(num(dose)),
				dose_unit: unit,
				frequency,
				days_of_week: frequency === 'specific_days' ? [...daysOfWeek].sort() : [],
				times_of_day: timesOfDay
			});
			dose = '';
			refId = null;
			daysOfWeek = [];
			timesOfDay = [];
			await load();
		} catch (err) {
			error = (err as Error).message;
		}
	}

	function onCompoundCreated(c: Compound) {
		compounds = [...compounds, c].sort((a, b) => a.name.localeCompare(b.name));
		kind = 'compound';
		refId = c.id;
	}
	function onSupplementCreated(s: Supplement) {
		supplements = [...supplements, s].sort((a, b) => a.name.localeCompare(b.name));
		kind = 'supplement';
		refId = s.id;
	}

	async function removeItem(id: number) {
		await protocolsApi.deleteItem(id);
		await load();
	}

	const adherenceFor = (itemId: number) => adherence.find((a) => a.item_id === itemId);
	const freqLabel = (k: string) => FREQUENCIES.find((f) => f.key === k)?.label ?? k;
	const dayLabel = (n: number) => WEEKDAYS.find((w) => w.key === n)?.label ?? String(n);
	const timeLabel = (t: string) => TIMES_OF_DAY.find((x) => x.key === t)?.label ?? t;
</script>

<CompoundCreateModal bind:open={showCompoundModal} oncreated={onCompoundCreated} />
<SupplementCreateModal bind:open={showSupplementModal} oncreated={onSupplementCreated} />

{#if loading}
	<p class="text-neutral-400">Loading…</p>
{:else if error}
	<p class="text-red-400">{error}</p>
{:else if protocol}
	<div class="flex items-center justify-between">
		<div>
			<a class="text-sm text-neutral-400 hover:text-white" href="/protocols/manage">← Protocols</a>
			<h1 class="text-xl font-semibold">{protocol.name}</h1>
		</div>
		{#if protocol.is_active}
			<span class="rounded bg-green-900 px-2 py-0.5 text-xs text-green-300">Active</span>
		{/if}
	</div>

	<!-- Add item with schedule -->
	<form class="mt-4 space-y-3 rounded-lg border border-neutral-800 p-4" onsubmit={addItem}>
		<div class="flex flex-wrap items-center gap-2">
			<div class="flex gap-2 text-sm">
				<button type="button" class="rounded-md px-3 py-1.5 {kind === 'compound' ? 'bg-brand text-white' : 'border border-neutral-700'}" onclick={() => { kind = 'compound'; refId = null; unit = 'mg'; }}>Compound</button>
				<button type="button" class="rounded-md px-3 py-1.5 {kind === 'supplement' ? 'bg-brand text-white' : 'border border-neutral-700'}" onclick={() => { kind = 'supplement'; refId = null; unit = 'serving'; }}>Supplement</button>
			</div>
			<div class="min-w-56 flex-1">
				{#key kind}
					<SearchSelect
						options={pickerOptions}
						bind:value={refId}
						groups={pickerGroups}
						placeholder={`Search ${kind}…`}
					/>
				{/key}
			</div>
			<button
				type="button"
				class="rounded-md border border-neutral-700 px-2 py-1.5 text-sm text-indigo-300 hover:border-neutral-500"
				onclick={() => (kind === 'compound' ? (showCompoundModal = true) : (showSupplementModal = true))}
			>
				＋ New
			</button>
		</div>

		<div class="flex flex-wrap items-center gap-2">
			<input type="number" step={kind === 'supplement' ? '0.5' : '0.001'} placeholder={kind === 'supplement' ? 'servings' : 'dose'} bind:value={dose} class="w-24 {selectClass}" />
			{#if kind === 'supplement'}
				<span class="text-sm text-neutral-400">servings</span>
			{:else}
				<select bind:value={unit} class={selectClass}>
					{#each ['mg', 'mcg', 'iu', 'ml', 'tablet', 'capsule'] as u (u)}<option value={u}>{u}</option>{/each}
				</select>
			{/if}
			<select bind:value={frequency} class={selectClass}>
				{#each FREQUENCIES as f (f.key)}<option value={f.key}>{f.label}</option>{/each}
			</select>
		</div>

		{#if frequency === 'specific_days'}
			<div class="flex flex-wrap items-center gap-1">
				<span class="mr-1 text-xs text-neutral-500">Days:</span>
				{#each WEEKDAYS as d (d.key)}
					<button type="button" class="rounded px-2 py-1 text-xs {daysOfWeek.includes(d.key) ? 'bg-brand text-white' : 'border border-neutral-700 text-neutral-300'}" onclick={() => toggleDay(d.key)}>{d.label}</button>
				{/each}
			</div>
		{/if}

		<div class="flex flex-wrap items-center gap-1">
			<span class="mr-1 text-xs text-neutral-500">Times:</span>
			{#each TIMES_OF_DAY as t (t.key)}
				<button type="button" class="rounded-full px-2.5 py-0.5 text-xs {timesOfDay.includes(t.key) ? 'bg-brand text-white' : 'border border-neutral-700 text-neutral-300'}" onclick={() => toggleTime(t.key)}>{t.label}</button>
			{/each}
		</div>

		<div class="w-40"><Button type="submit">Add item</Button></div>
	</form>

	{#if protocol.items.length === 0}
		<p class="mt-6 text-neutral-500">No items yet. Add a compound or supplement above.</p>
	{:else}
		<div class="mt-6 space-y-2">
			{#each protocol.items as item (item.id)}
				{@const adh = adherenceFor(item.id)}
				<Card>
					<div class="flex items-center justify-between">
						<div>
							<span class="font-medium">{item.item_name}</span>
							<div class="text-xs text-neutral-500">
								{item.dose_amount ?? '—'}{item.dose_unit} · {freqLabel(item.frequency)}
								{#if item.frequency === 'specific_days' && item.days_of_week?.length}
									({item.days_of_week.map(dayLabel).join(', ')})
								{/if}
								{#if item.times_of_day?.length}· {item.times_of_day.map(timeLabel).join(', ')}{/if}
								{#if item.route}· {item.route}{/if}
							</div>
						</div>
						<div class="flex items-center gap-3 text-sm">
							{#if adh && adh.adherence != null}
								<span class="text-xs {adh.adherence >= 80 ? 'text-green-400' : adh.adherence >= 50 ? 'text-amber-400' : 'text-red-400'}">
									{adh.adherence}% <span class="text-neutral-600">({adh.actual}/{adh.expected})</span>
								</span>
							{/if}
							<button class="text-xs text-red-400 hover:text-red-300" onclick={() => removeItem(item.id)}>Remove</button>
						</div>
					</div>
				</Card>
			{/each}
		</div>
		<p class="mt-2 text-xs text-neutral-500">Adherence is over the trailing 28 days, based on logged doses.</p>
	{/if}
{/if}
