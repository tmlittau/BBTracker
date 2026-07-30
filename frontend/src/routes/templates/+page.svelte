<script lang="ts">
	import { coachPlan } from '$lib/clients/plan';
	import { coachingApi, type ClientBrief } from '$lib/coaching/api';
	import ProgramBuilder from '$lib/clients/ProgramBuilder.svelte';
	import ProtocolBuilder from '$lib/clients/ProtocolBuilder.svelte';
	import MealPlanBuilder from '$lib/clients/MealPlanBuilder.svelte';

	// The coach's own programs/protocols/meal-plans ARE the template library.
	const plan = coachPlan();

	type Kind = 'program' | 'protocol' | 'meal_plan';
	const sections: { key: Kind; label: string }[] = [
		{ key: 'program', label: 'Programs' },
		{ key: 'protocol', label: 'Protocols' },
		{ key: 'meal_plan', label: 'Meal plans' }
	];
	let section = $state<Kind>('program');

	// --- apply-to-client modal ---
	let applyId = $state<number | null>(null);
	let applyName = $state('');
	let clients = $state<ClientBrief[]>([]);
	let clientsLoaded = $state(false);
	let applying = $state(false);
	let result = $state<{ ok: boolean; text: string } | null>(null);

	const editable = $derived(clients.filter((c) => c.can_edit_prescriptions));

	async function ensureClients() {
		if (clientsLoaded) return;
		try {
			clients = await coachingApi.clients();
			clientsLoaded = true;
		} catch (e) {
			result = { ok: false, text: (e as Error).message };
		}
	}

	function startApply(id: number, name: string) {
		applyId = id;
		applyName = name;
		result = null;
		ensureClients();
	}
	function closeApply() {
		applyId = null;
	}

	async function applyTo(client: ClientBrief) {
		if (applyId == null) return;
		applying = true;
		result = null;
		try {
			await coachingApi.applyTemplate(section, applyId, client.client_id);
			result = { ok: true, text: `Applied “${applyName}” to ${client.name || client.email}.` };
			applyId = null;
		} catch (e) {
			result = { ok: false, text: (e as Error).message };
		} finally {
			applying = false;
		}
	}
</script>

<div class="p-6">
	<h1 class="text-lg font-semibold">Templates</h1>
	<p class="mt-0.5 max-w-2xl text-xs text-neutral-500">
		Build reusable programs, protocols and meal plans here, then apply one to a client — it's
		copied into their plan (inactive) so you can review before activating.
	</p>

	<div class="mt-3 flex gap-1 text-sm">
		{#each sections as s (s.key)}
			<button
				onclick={() => (section = s.key)}
				class="rounded-full px-3 py-1 {section === s.key ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:text-white'}"
			>
				{s.label}
			</button>
		{/each}
	</div>

	{#if result}
		<p class="mt-3 text-sm {result.ok ? 'text-emerald-400' : 'text-red-400'}">{result.text}</p>
	{/if}

	<div class="mt-4">
		{#if section === 'program'}
			<ProgramBuilder {plan} canEdit onApply={startApply} />
		{:else if section === 'protocol'}
			<ProtocolBuilder {plan} canEdit onApply={startApply} />
		{:else}
			<MealPlanBuilder {plan} canEdit onApply={startApply} />
		{/if}
	</div>
</div>

<!-- Apply-to-client modal -->
{#if applyId != null}
	<div class="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
		<div class="w-full max-w-sm rounded-lg border border-neutral-800 bg-neutral-900 p-4 shadow-xl">
			<h2 class="text-sm font-semibold text-neutral-100">Apply “{applyName}”</h2>
			<p class="mt-0.5 text-xs text-neutral-500">Choose a client to copy this template into.</p>

			<div class="mt-3 max-h-72 space-y-1 overflow-y-auto">
				{#if !clientsLoaded}
					<p class="px-1 py-2 text-sm text-neutral-500">Loading clients…</p>
				{:else if editable.length === 0}
					<p class="px-1 py-2 text-sm text-neutral-500">No clients you can edit.</p>
				{:else}
					{#each editable as c (c.client_id)}
						<button
							onclick={() => applyTo(c)}
							disabled={applying}
							class="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm text-neutral-200 hover:bg-neutral-800 disabled:opacity-50"
						>
							<span class="truncate">{c.name || c.email}</span>
							{#if c.phase}<span class="ml-2 shrink-0 text-[10px] text-neutral-500">{c.phase}</span>{/if}
						</button>
					{/each}
				{/if}
			</div>

			<div class="mt-3 flex justify-end">
				<button onclick={closeApply} class="text-sm text-neutral-400 hover:text-neutral-200">Cancel</button>
			</div>
		</div>
	</div>
{/if}
