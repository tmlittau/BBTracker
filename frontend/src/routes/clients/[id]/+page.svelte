<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { coachingApi, type ClientOverview } from '$lib/coaching/api';

	const clientId = $derived(Number($page.params.id));
	let ov = $state<ClientOverview | null>(null);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			ov = await coachingApi.overview(clientId);
		} catch (e) {
			error = (e as Error).message;
		}
	});

	const n = (v: number | null | undefined, d = 1) =>
		v == null ? '—' : Number(v).toFixed(d);
</script>

<div class="p-6">
	{#if error}
		<p class="text-sm text-red-400">{error}</p>
	{:else if !ov}
		<p class="text-neutral-400">Loading…</p>
	{:else}
		{@const comp = ov.body.composition}
		{@const energy = ov.body.energy}
		<div class="grid gap-4 md:grid-cols-3">
			<div class="rounded-lg border border-neutral-800 p-4">
				<h2 class="text-sm font-medium text-neutral-300">Composition</h2>
				<div class="mt-3 grid grid-cols-2 gap-y-2 text-sm">
					<span class="text-neutral-500">Weight</span><span class="text-right tabular-nums">{n(comp.weight_kg)} kg</span>
					<span class="text-neutral-500">Body fat</span><span class="text-right tabular-nums">{n(comp.body_fat_pct)} %</span>
					<span class="text-neutral-500">Lean mass</span><span class="text-right tabular-nums">{n(comp.lean_mass_kg)} kg</span>
					<span class="text-neutral-500">Fat mass</span><span class="text-right tabular-nums">{n(comp.fat_mass_kg)} kg</span>
					<span class="text-neutral-500">FFMI</span><span class="text-right tabular-nums">{n(comp.ffmi)}</span>
				</div>
			</div>

			<div class="rounded-lg border border-neutral-800 p-4">
				<h2 class="text-sm font-medium text-neutral-300">Energy</h2>
				<div class="mt-3 grid grid-cols-2 gap-y-2 text-sm">
					<span class="text-neutral-500">BMR</span><span class="text-right tabular-nums">{n(energy.bmr, 0)} kcal</span>
					<span class="text-neutral-500">TDEE (adaptive)</span><span class="text-right tabular-nums">{n(energy.tdee, 0)} kcal</span>
				</div>
			</div>

			<div class="rounded-lg border border-neutral-800 p-4">
				<h2 class="text-sm font-medium text-neutral-300">Current plan</h2>
				<div class="mt-3 space-y-1 text-sm">
					<div>
						<span class="text-neutral-500">Phase:</span>
						{ov.dashboard.phase ? `${ov.dashboard.phase.name} (${ov.dashboard.phase.phase_type})` : '—'}
					</div>
					<div>
						<span class="text-neutral-500">Target:</span>
						{ov.dashboard.nutrition.target_name ?? '—'}
						· {Math.round(Number(ov.dashboard.nutrition.calories))} kcal
						/ {Math.round(Number(ov.dashboard.nutrition.protein_g))}g P
					</div>
					<div class="pt-1">
						<a href={`/clients/${clientId}/nutrition`} class="text-xs text-orange-400 hover:text-orange-300">Adjust nutrition →</a>
					</div>
				</div>
			</div>
		</div>

		{#if ov.body.insights?.length}
			<div class="mt-4 rounded-lg border border-neutral-800 p-4">
				<h2 class="text-sm font-medium text-neutral-300">Insights</h2>
				<ul class="mt-2 space-y-1.5 text-sm">
					{#each ov.body.insights as ins (ins.label)}
						<li class="flex gap-2">
							<span class="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full {ins.severity === 'risk'
								? 'bg-red-500'
								: ins.severity === 'watch'
									? 'bg-amber-500'
									: 'bg-emerald-500'}"></span>
							<span><span class="font-medium">{ins.label}:</span> <span class="text-neutral-400">{ins.detail}</span></span>
						</li>
					{/each}
				</ul>
			</div>
		{/if}
	{/if}
</div>
