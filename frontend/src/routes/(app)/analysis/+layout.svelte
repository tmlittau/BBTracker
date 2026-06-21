<script lang="ts">
	import SubTabs from '$lib/components/ui/SubTabs.svelte';

	let { children } = $props();

	const tabs = [
		{ href: '/analysis', label: 'Body', match: (p: string) => p === '/analysis' },
		{ href: '/analysis/compounds', label: 'Compounds' }
	];
</script>



<SubTabs {tabs} activeClass="border-rose-500 text-rose-300" />
{@render children()}


