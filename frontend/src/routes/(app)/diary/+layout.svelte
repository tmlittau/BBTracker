<script lang="ts">
	import SubTabs from '$lib/components/ui/SubTabs.svelte';
	let { children } = $props();

	const tabs = [
		{ href: '/diary', label: 'Diary', match: (p: string) => p === '/diary' || p.startsWith('/diary/check-in') },
		{ href: '/diary/photos', label: 'Photos' }
	];
</script>

<SubTabs {tabs} activeClass="border-sky-500 text-sky-300" />
{@render children()}
