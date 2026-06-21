<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { isoDate } from '$lib/date';
	import type { Phase } from '$lib/coaching/api';
	import {
		coachApi,
		clientPlan,
		type ClientBrief,
		type ClientTarget,
		type PlanOption
	} from '$lib/coaching/clients';

	const clientId = $derived(Number($page.params.id));

	let brief = $state<ClientBrief | null>(null);
	let phases = $state<Phase[]>([]);
	let programs = $state<PlanOption[]>([]);
	let protocols = $state<PlanOption[]>([]);
	let targets = $state<ClientTarget[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	const canEdit = $derived(brief?.can_edit_prescriptions ?? false);
	const activeTarget = $derived(targets.find((t) => t.is_active) ?? null);

	function cleanErr(err: unknown): string {
		const m = (err as Error).message ?? '';
		if (m.includes('→ 403')) return "You have read-only access to this client's plan.";
		return m.replace(/^\w+ \S+ → \d+\s*/, '') || 'Something went wrong.';
	}

	async function load() {
		loading = true;
		error = null;
		try {
			const clients = await coachApi.clients();
			brief = clients.find((c) => c.client_id === clientId) ?? null;
			if (!brief) throw new Error('This is not one of your clients.');
			[phases, programs, protocols, targets] = await Promise.all([
				clientPlan.phases(clientId),
				clientPlan.programs(clientId),
				clientPlan.protocols(clientId),
				clientPlan.targets(clientId)
			]);
		} catch (e) {
			error = cleanErr(e);
		} finally {
			loading = false;
		}
	}
	onMount(load);

	// --- nutrition target ---
	const blankNt = { name: '', calories: '', protein_g: '', carb_g: '', fat_g: '' };
	let nt = $state({ ...blankNt });
	let savingNt = $state(false);
	let ntMsg = $state<string | null>(null);
	async function saveTarget(e: SubmitEvent) {
		e.preventDefault();
		savingNt = true;
		ntMsg = null;
		try {
			const created = await clientPlan.createTarget(clientId, { ...nt });
			await clientPlan.activateTarget(clientId, created.id);
			nt = { ...blankNt };
			targets = await clientPlan.targets(clientId);
			ntMsg = 'Saved and set as the active target.';
		} catch (err) {
			ntMsg = cleanErr(err);
		} finally {
			savingNt = false;
		}
	}

	// --- phase adjustment (swap prescription) ---
	let adjPhase = $state<number | null>(null);
	let adj = $state({ effective_date: isoDate(), reason: '', program: '', protocol: '', nutrition_target: '' });
	let savingAdj = $state(false);
	let adjMsg = $state<string | null>(null);
	const selectedPhase = $derived(phases.find((p) => p.id === adjPhase) ?? null);
	const currentAdj = $derived(selectedPhase?.adjustments?.at(-1) ?? null);

	$effect(() => {
		if (adjPhase === null && phases.length) adjPhase = phases[0].id;
	});

	async function saveAdjustment(e: SubmitEvent) {
		e.preventDefault();
		if (!adjPhase) return;
		savingAdj = true;
		adjMsg = null;
		try {
			await clientPlan.createAdjustment(clientId, {
				phase: adjPhase,
				effective_date: adj.effective_date,
				reason: adj.reason,
				program: adj.program ? Number(adj.program) : null,
				protocol: adj.protocol ? Number(adj.protocol) : null,
				nutrition_target: adj.nutrition_target ? Number(adj.nutrition_target) : null
			});
			adj = { effective_date: isoDate(), reason: '', program: '', protocol: '', nutrition_target: '' };
			phases = await clientPlan.phases(clientId);
			adjMsg = 'Adjustment added to the timeline.';
		} catch (err) {
			adjMsg = cleanErr(err);
		} finally {
			savingAdj = false;
		}
	}

	// --- build new program / protocol (then open the builder) ---
	let newProgramName = $state('');
	let newProtocolName = $state('');
	let creatingProgram = $state(false);
	let creatingProtocol = $state(false);

	async function createProgram(e: SubmitEvent) {
		e.preventDefault();
		if (!newProgramName.trim()) return;
		creatingProgram = true;
		try {
			const p = await clientPlan.createProgram(clientId, newProgramName.trim());
			await goto(`/coach/clients/${clientId}/programs/${p.id}`);
		} catch (err) {
			adjMsg = cleanErr(err);
			creatingProgram = false;
		}
	}
	async function createProtocol(e: SubmitEvent) {
		e.preventDefault();
		if (!newProtocolName.trim()) return;
		creatingProtocol = true;
		try {
			const p = await clientPlan.createProtocol(clientId, newProtocolName.trim());
			await goto(`/coach/clients/${clientId}/protocols/${p.id}`);
		} catch (err) {
			adjMsg = cleanErr(err);
			creatingProtocol = false;
		}
	}

	const fieldCls =
		'mt-1 w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100';
</script>

<a href={`/coach/clients/${clientId}`} class="text-sm text-neutral-400 hover:text-neutral-200">
	← Back to overview
</a>

{#if loading}
	<p class="mt-6 text-neutral-400">Loading…</p>
{:else if error}
	<p class="mt-6 text-red-400">{error}</p>
{:else if brief}
	<h1 class="mt-2 text-xl font-semibold">Adjust plan — {brief.name}</h1>

	{#if !canEdit}
		<p class="mt-4 rounded-lg border border-amber-800/60 bg-amber-950/20 p-4 text-sm text-amber-300">
			You have read-only access to this client. They can grant plan-editing from their settings.
		</p>
	{:else}
		<!-- Nutrition target -->
		<section class="mt-6 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
			<h2 class="font-medium">Nutrition target</h2>
			<p class="mt-1 text-sm text-neutral-400">
				Active:
				{#if activeTarget}
					<span class="text-neutral-200">{activeTarget.name}</span> — {activeTarget.calories ?? '—'} kcal,
					{activeTarget.protein_g ?? '—'}P / {activeTarget.carb_g ?? '—'}C / {activeTarget.fat_g ?? '—'}F
				{:else}none set{/if}
			</p>
			<form class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5" onsubmit={saveTarget}>
				<label class="col-span-2 text-xs text-neutral-500 sm:col-span-1">
					Name<input class={fieldCls} bind:value={nt.name} placeholder="Cut" required />
				</label>
				<label class="text-xs text-neutral-500">
					kcal<input class={fieldCls} type="number" bind:value={nt.calories} required />
				</label>
				<label class="text-xs text-neutral-500">
					Protein<input class={fieldCls} type="number" bind:value={nt.protein_g} />
				</label>
				<label class="text-xs text-neutral-500">
					Carbs<input class={fieldCls} type="number" bind:value={nt.carb_g} />
				</label>
				<label class="text-xs text-neutral-500">
					Fat<input class={fieldCls} type="number" bind:value={nt.fat_g} />
				</label>
				<div class="col-span-2 flex items-center gap-3 sm:col-span-5">
					<button
						type="submit"
						disabled={savingNt}
						class="rounded-full bg-brand px-4 py-2 text-sm font-medium text-white hover:brightness-110 disabled:opacity-50"
					>
						{savingNt ? 'Saving…' : 'Save & activate'}
					</button>
					{#if ntMsg}<span class="text-sm text-neutral-300">{ntMsg}</span>{/if}
				</div>
			</form>
		</section>

		<!-- Phase adjustment -->
		<section class="mt-4 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
			<h2 class="font-medium">Prescription timeline</h2>
			{#if phases.length === 0}
				<p class="mt-2 text-sm text-neutral-500">This client has no phases yet.</p>
			{:else}
				<label class="mt-2 block text-xs text-neutral-500">
					Phase
					<select class={fieldCls} bind:value={adjPhase}>
						{#each phases as p (p.id)}<option value={p.id}>{p.name}</option>{/each}
					</select>
				</label>
				{#if currentAdj}
					<p class="mt-2 text-sm text-neutral-400">
						Current: program <span class="text-neutral-200">{currentAdj.program_name ?? '—'}</span>,
						protocol <span class="text-neutral-200">{currentAdj.protocol_name ?? '—'}</span>, target
						<span class="text-neutral-200">{currentAdj.nutrition_target_name ?? '—'}</span>
					</p>
				{/if}
				<form class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4" onsubmit={saveAdjustment}>
					<label class="text-xs text-neutral-500">
						Effective<input class={fieldCls} type="date" bind:value={adj.effective_date} required />
					</label>
					<label class="text-xs text-neutral-500">
						Program
						<select class={fieldCls} bind:value={adj.program}>
							<option value="">— keep —</option>
							{#each programs as p (p.id)}<option value={String(p.id)}>{p.name}</option>{/each}
						</select>
					</label>
					<label class="text-xs text-neutral-500">
						Protocol
						<select class={fieldCls} bind:value={adj.protocol}>
							<option value="">— keep —</option>
							{#each protocols as p (p.id)}<option value={String(p.id)}>{p.name}</option>{/each}
						</select>
					</label>
					<label class="text-xs text-neutral-500">
						Target
						<select class={fieldCls} bind:value={adj.nutrition_target}>
							<option value="">— keep —</option>
							{#each targets as t (t.id)}<option value={String(t.id)}>{t.name}</option>{/each}
						</select>
					</label>
					<label class="col-span-2 text-xs text-neutral-500 sm:col-span-4">
						Reason (optional)
						<input class={fieldCls} bind:value={adj.reason} placeholder="e.g. start of prep" />
					</label>
					<div class="col-span-2 flex items-center gap-3 sm:col-span-4">
						<button
							type="submit"
							disabled={savingAdj}
							class="rounded-full bg-brand px-4 py-2 text-sm font-medium text-white hover:brightness-110 disabled:opacity-50"
						>
							{savingAdj ? 'Adding…' : 'Add adjustment'}
						</button>
						{#if adjMsg}<span class="text-sm text-neutral-300">{adjMsg}</span>{/if}
					</div>
				</form>

				{#if selectedPhase && selectedPhase.adjustments.length > 0}
					<ul class="mt-4 space-y-1 border-t border-neutral-800 pt-3 text-xs text-neutral-400">
						{#each selectedPhase.adjustments as a (a.id)}
							<li>
								<span class="text-neutral-300">{a.effective_date}</span> —
								{a.program_name ?? '—'} / {a.protocol_name ?? '—'} / {a.nutrition_target_name ?? '—'}
								{#if a.reason}<span class="text-neutral-500"> · {a.reason}</span>{/if}
							</li>
						{/each}
					</ul>
				{/if}
			{/if}
		</section>

		<!-- Training programs -->
		<section class="mt-4 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
			<h2 class="font-medium">Training programs</h2>
			{#if programs.length > 0}
				<ul class="mt-2 divide-y divide-neutral-800/60">
					{#each programs as p (p.id)}
						<li class="flex items-center justify-between py-2 text-sm">
							<span class="text-neutral-200">
								{p.name}{#if p.is_active}<span class="ml-2 rounded bg-green-900 px-1.5 py-0.5 text-[10px] text-green-300">active</span>{/if}
							</span>
							<a class="text-xs text-orange-400 hover:text-orange-300" href={`/coach/clients/${clientId}/programs/${p.id}`}>Edit →</a>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="mt-2 text-sm text-neutral-500">No programs yet.</p>
			{/if}
			<form class="mt-3 flex flex-wrap items-center gap-2" onsubmit={createProgram}>
				<input
					class="min-w-[12rem] flex-1 rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
					bind:value={newProgramName}
					placeholder="New program name (e.g. Upper/Lower)"
				/>
				<button
					type="submit"
					disabled={creatingProgram}
					class="rounded-full bg-brand px-4 py-2 text-sm font-medium text-white hover:brightness-110 disabled:opacity-50"
				>
					{creatingProgram ? 'Creating…' : 'Build new program'}
				</button>
			</form>
		</section>

		<!-- Protocols -->
		<section class="mt-4 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
			<h2 class="font-medium">Protocols</h2>
			{#if protocols.length > 0}
				<ul class="mt-2 divide-y divide-neutral-800/60">
					{#each protocols as p (p.id)}
						<li class="flex items-center justify-between py-2 text-sm">
							<span class="text-neutral-200">
								{p.name}{#if p.is_active}<span class="ml-2 rounded bg-green-900 px-1.5 py-0.5 text-[10px] text-green-300">active</span>{/if}
							</span>
							<a class="text-xs text-orange-400 hover:text-orange-300" href={`/coach/clients/${clientId}/protocols/${p.id}`}>Edit →</a>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="mt-2 text-sm text-neutral-500">No protocols yet.</p>
			{/if}
			<form class="mt-3 flex flex-wrap items-center gap-2" onsubmit={createProtocol}>
				<input
					class="min-w-[12rem] flex-1 rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100"
					bind:value={newProtocolName}
					placeholder="New protocol name (e.g. Off-season)"
				/>
				<button
					type="submit"
					disabled={creatingProtocol}
					class="rounded-full bg-brand px-4 py-2 text-sm font-medium text-white hover:brightness-110 disabled:opacity-50"
				>
					{creatingProtocol ? 'Creating…' : 'Build new protocol'}
				</button>
			</form>
		</section>
	{/if}
{/if}
