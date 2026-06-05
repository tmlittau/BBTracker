<script lang="ts">
	import SubTabs from '$lib/components/ui/SubTabs.svelte';
	let { children } = $props();

	const tabs = [
		{ href: '/protocols', label: 'Protocols', match: (p: string) => p === '/protocols' || p.startsWith('/protocols/manage') || p.startsWith('/protocols/log') },
		{ href: '/protocols/bloodwork', label: 'Bloodwork' },
		{ href: '/protocols/compounds', label: 'Compounds' },
		{ href: '/protocols/supplements', label: 'Supplements' }
	];
</script>

<SubTabs {tabs} activeClass="border-violet-500 text-violet-300" />
{@render children()}
