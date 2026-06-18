<script lang="ts">
	import SubTabs from '$lib/components/ui/SubTabs.svelte';
	import MeasurementModal from '$lib/analysis/MeasurementModal.svelte';
	import { measurementsVersion } from '$lib/analysis/store';

	let { children } = $props();
	let showAdd = $state(false);

	const tabs = [
		{ href: '/analysis', label: 'Body', match: (p: string) => p === '/analysis' },
		{ href: '/analysis/compounds', label: 'Compounds' }
	];
</script>

<div class="mb-3 flex items-center justify-between gap-3">
	<h1 class="text-xl font-semibold">Analysis</h1>
	<button
		class="shrink-0 rounded-md bg-rose-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-500"
		onclick={() => (showAdd = true)}
	>
		+ Add measurement
	</button>
</div>

<SubTabs {tabs} activeClass="border-rose-500 text-rose-300" />
{@render children()}

<MeasurementModal bind:open={showAdd} onsaved={() => measurementsVersion.update((n) => n + 1)} />
