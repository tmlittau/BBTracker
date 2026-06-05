<script lang="ts">
	import SubTabs from '$lib/components/ui/SubTabs.svelte';
	let { children } = $props();

	const tabs = [
		{ href: '/nutrition', label: 'Nutrition', match: (p: string) => p === '/nutrition' },
		{ href: '/nutrition/foods', label: 'Foods' },
		{ href: '/nutrition/targets', label: 'Targets' }
	];
</script>

<SubTabs {tabs} activeClass="border-emerald-500 text-emerald-300" />
{@render children()}
