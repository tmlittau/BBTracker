<script lang="ts">
	import { onMount } from 'svelte';
	import {
		protocolsApi,
		ROUTES,
		type Compound,
		type DoseLog,
		type SiteRecency,
		type Supplement
	} from '$lib/protocols/api';
	import { num } from '$lib/protocols/calc';
	import BodyMap from '$lib/protocols/BodyMap.svelte';
	import Button from '$lib/components/ui/Button.svelte';

	let compounds = $state<Compound[]>([]);
	let supplements = $state<Supplement[]>([]);
	let sites = $state<SiteRecency[]>([]);
	let suggestion = $state<SiteRecency | null>(null);
	let today = $state<DoseLog[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	// Form state
	let kind = $state<'compound' | 'supplement'>('compound');
	let compoundId = $state<number | null>(null);
	let supplementId = $state<number | null>(null);
	let amount = $state('');
	let unit = $state('mg');
	let route = $state('im');
	let siteId = $state<number | null>(null);
	let notes = $state('');
	let sideEffects = $state('');
	let saving = $state(false);

	const isInjection = $derived(route === 'im' || route === 'subq');
	const todayISO = new Date().toISOString().slice(0, 10);

	async function loadSites() {
		[sites, suggestion] = await Promise.all([
			protocolsApi.siteRecency(30),
			protocolsApi.suggestSite().catch(() => null as unknown as SiteRecency)
		]);
	}

	async function loadToday() {
		today = await protocolsApi.doses({ date: todayISO });
	}

	onMount(async () => {
		try {
			[compounds, supplements] = await Promise.all([
				protocolsApi.compounds(),
				protocolsApi.supplements()
			]);
			await Promise.all([loadSites(), loadToday()]);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	});

	// Selecting a compound records it (read from the event — robust under both
	// real use and automated `selectOption`) and prefills unit/route.
	function onCompoundChange(e: Event & { currentTarget: HTMLSelectElement }) {
		compoundId = e.currentTarget.value ? Number(e.currentTarget.value) : null;
		const c = compounds.find((x) => x.id === compoundId);
		if (c) {
			unit = c.default_unit;
			route = c.default_route;
		}
	}

	function onSupplementChange(e: Event & { currentTarget: HTMLSelectElement }) {
		supplementId = e.currentTarget.value ? Number(e.currentTarget.value) : null;
	}

	function pickSuggested() {
		if (suggestion?.id) siteId = suggestion.id;
	}

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		error = null;
		if (kind === 'compound' && !compoundId) {
			error = 'Choose a compound.';
			return;
		}
		if (kind === 'supplement' && !supplementId) {
			error = 'Choose a supplement.';
			return;
		}
		saving = true;
		try {
			await protocolsApi.logDose({
				compound: kind === 'compound' ? compoundId : null,
				supplement: kind === 'supplement' ? supplementId : null,
				taken_at: new Date().toISOString(),
				amount: String(num(amount)),
				unit,
				route: kind === 'compound' ? route : '',
				injection_site: isInjection ? siteId : null,
				notes,
				side_effects: sideEffects
			});
			amount = '';
			notes = '';
			sideEffects = '';
			await Promise.all([loadSites(), loadToday()]);
		} catch (err) {
			error = (err as Error).message;
		} finally {
			saving = false;
		}
	}
</script>

<h1 class="text-xl font-semibold">Log a dose</h1>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error && compounds.length === 0}
	<p class="mt-6 text-red-400">{error}</p>
{:else}
	<div class="mt-6 grid gap-6 lg:grid-cols-2">
		<!-- Form -->
		<form class="space-y-3" onsubmit={submit}>
			<div class="flex gap-2 text-sm">
				<button
					type="button"
					class="rounded-md px-3 py-1.5 {kind === 'compound' ? 'bg-indigo-600 text-white' : 'border border-neutral-700'}"
					onclick={() => (kind = 'compound')}
				>
					Medication / PED
				</button>
				<button
					type="button"
					class="rounded-md px-3 py-1.5 {kind === 'supplement' ? 'bg-indigo-600 text-white' : 'border border-neutral-700'}"
					onclick={() => (kind = 'supplement')}
				>
					Supplement
				</button>
			</div>

			{#if kind === 'compound'}
				<label class="block text-xs text-neutral-500">
					Compound
					<select
						onchange={onCompoundChange}
						class="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100"
					>
						<option value="">Choose…</option>
						{#each compounds as c (c.id)}
							<option value={c.id}>{c.name}</option>
						{/each}
					</select>
				</label>
			{:else}
				<label class="block text-xs text-neutral-500">
					Supplement
					<select
						onchange={onSupplementChange}
						class="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100"
					>
						<option value="">Choose…</option>
						{#each supplements as s (s.id)}
							<option value={s.id}>{s.name}</option>
						{/each}
					</select>
				</label>
			{/if}

			<div class="flex gap-2">
				<label class="flex flex-1 flex-col text-xs text-neutral-500">
					Amount
					<input
						name="amount"
						type="number"
						step="0.001"
						inputmode="decimal"
						bind:value={amount}
						class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100"
					/>
				</label>
				<label class="flex flex-1 flex-col text-xs text-neutral-500">
					Unit
					<select
						bind:value={unit}
						class="mt-1 rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100"
					>
						{#each ['mg', 'mcg', 'iu', 'ml', 'tablet', 'capsule'] as u (u)}
							<option value={u}>{u}</option>
						{/each}
					</select>
				</label>
			</div>

			{#if kind === 'compound'}
				<label class="block text-xs text-neutral-500">
					Route
					<select
						bind:value={route}
						class="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100"
					>
						{#each ROUTES as r (r.key)}
							<option value={r.key}>{r.label}</option>
						{/each}
					</select>
				</label>
			{/if}

			{#if isInjection && kind === 'compound'}
				<div class="rounded border border-neutral-800 p-2">
					<div class="flex items-center justify-between">
						<span class="text-xs text-neutral-500">Injection site</span>
						{#if suggestion?.name}
							<button type="button" class="text-xs text-indigo-400 hover:text-indigo-300" onclick={pickSuggested}>
								Use suggested: {suggestion.name}
							</button>
						{/if}
					</div>
					<p class="mt-1 text-sm">
						{sites.find((s) => s.id === siteId)?.name ?? 'Pick a site below →'}
					</p>
				</div>
			{/if}

			<label class="block text-xs text-neutral-500">
				Notes
				<input bind:value={notes} class="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100" />
			</label>
			<label class="block text-xs text-neutral-500">
				Side effects
				<input bind:value={sideEffects} class="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100" />
			</label>

			{#if error}<p class="text-sm text-red-400">{error}</p>{/if}
			<Button type="submit" disabled={saving}>{saving ? 'Logging…' : 'Log dose'}</Button>
		</form>

		<!-- Body map (injections only) -->
		<div>
			{#if isInjection && kind === 'compound'}
				<BodyMap {sites} bind:selected={siteId} />
			{:else}
				<p class="text-sm text-neutral-500">
					The injection-site map appears for intramuscular / subcutaneous routes.
				</p>
			{/if}
		</div>
	</div>

	<section class="mt-8">
		<h2 class="font-medium">Today's doses</h2>
		{#if today.length === 0}
			<p class="mt-2 text-sm text-neutral-500">Nothing logged today yet.</p>
		{:else}
			<div class="mt-3 space-y-2">
				{#each today as d (d.id)}
					<div class="flex items-center justify-between rounded border border-neutral-800 px-3 py-2 text-sm">
						<span>{d.item_name}</span>
						<span class="text-xs text-neutral-500">
							{d.amount}{d.unit}{#if d.site_name} · {d.site_name}{/if}
							· {new Date(d.taken_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
						</span>
					</div>
				{/each}
			</div>
		{/if}
	</section>
{/if}
