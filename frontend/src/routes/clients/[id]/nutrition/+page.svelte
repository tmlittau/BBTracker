<script lang="ts">
	import { page } from '$app/stores';
	import NutritionTargets from '$lib/clients/NutritionTargets.svelte';
	import MealPlanBuilder from '$lib/clients/MealPlanBuilder.svelte';

	const clientId = $derived(Number($page.params.id));

	const views = [
		{ key: 'targets', label: 'Targets' },
		{ key: 'plans', label: 'Meal plans' }
	] as const;
	let view = $state<(typeof views)[number]['key']>('targets');
</script>

<div class="p-6">
	<div class="flex gap-1 text-sm">
		{#each views as v (v.key)}
			<button
				onclick={() => (view = v.key)}
				class="rounded-full px-3 py-1 {view === v.key ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:text-white'}"
			>
				{v.label}
			</button>
		{/each}
	</div>

	<div class="mt-4">
		{#key clientId}
			{#if view === 'targets'}
				<NutritionTargets {clientId} />
			{:else}
				<MealPlanBuilder {clientId} />
			{/if}
		{/key}
	</div>
</div>
