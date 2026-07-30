<script lang="ts">
	import { page } from '$app/stores';
	import LibraryExercises from '$lib/clients/LibraryExercises.svelte';
	import LibraryCompounds from '$lib/clients/LibraryCompounds.svelte';
	import LibrarySupplements from '$lib/clients/LibrarySupplements.svelte';
	import LibraryFoods from '$lib/clients/LibraryFoods.svelte';

	const clientId = $derived(Number($page.params.id));

	const sections = [
		{ key: 'exercises', label: 'Exercises' },
		{ key: 'compounds', label: 'Compounds' },
		{ key: 'supplements', label: 'Supplements' },
		{ key: 'foods', label: 'Foods' }
	] as const;
	let section = $state<(typeof sections)[number]['key']>('exercises');
</script>

<div class="p-6">
	<h2 class="text-sm font-semibold text-neutral-300">Library</h2>
	<p class="mt-0.5 text-xs text-neutral-500">
		Custom exercises, compounds, supplements and foods you add here become available in this client's
		builders alongside the global seeds.
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

	<div class="mt-4">
		{#key clientId}
			{#if section === 'exercises'}
				<LibraryExercises {clientId} />
			{:else if section === 'compounds'}
				<LibraryCompounds {clientId} />
			{:else if section === 'supplements'}
				<LibrarySupplements {clientId} />
			{:else}
				<LibraryFoods {clientId} />
			{/if}
		{/key}
	</div>
</div>
