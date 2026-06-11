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

	// Undo a mis-logged dose (refresh site recency too, for injections).
	async function removeDose(id: number) {
		if (!confirm('Delete this logged dose?')) return;
		try {
			await protocolsApi.deleteDose(id);
			await Promise.all([loadToday(), loadSites()]);
		} catch (e) {
			error = (e as Error).message;
		}
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
				unit: kind === 'supplement' ? 'serving' : unit,
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

			{#if kind === 'supplement'}
				<label class="block text-xs text-neutral-500">
					Servings
					<input
						name="amount"
						type="number"
						step="0.5"
						min="0"
						inputmode="decimal"
						placeholder="e.g. 2 (capsules) or 0.5 (half a tablet)"
						bind:value={amount}
						class="mt-1 w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-2 text-sm text-neutral-100"
					/>
					<span class="mt-1 block text-neutral-600">Nutrients = this × the per-serving values set on the supplement.</span>
				</label>
			{:else}
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
			{/if}

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
					<div class="flex items-center justify-between gap-2 rounded border px-3 py-2 text-sm {d.status === 'skipped' ? 'border-red-900/50 bg-red-950/20' : 'border-neutral-800'}">
						<span>
							{d.item_name}
							{#if d.status === 'skipped'}<span class="ml-1 rounded bg-red-900/60 px-1.5 py-0.5 text-xs text-red-300">skipped</span>{/if}
						</span>
						<div class="flex items-center gap-3">
							<span class="text-xs text-neutral-500 {d.status === 'skipped' ? 'line-through' : ''}">
								{d.amount}{d.unit}{#if d.site_name} · {d.site_name}{/if}
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
