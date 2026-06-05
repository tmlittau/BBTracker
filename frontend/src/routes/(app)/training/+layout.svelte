<script lang="ts">
	import SubTabs from '$lib/components/ui/SubTabs.svelte';
	let { children } = $props();

	const tabs = [
		{ href: '/training', label: 'Training', match: (p: string) => p === '/training' || p.startsWith('/training/log') },
		{ href: '/training/programs', label: 'Programs' },
		{ href: '/training/exercises', label: 'Exercises' },
		{ href: '/training/history', label: 'History' }
	];
</script>

<SubTabs {tabs} activeClass="border-indigo-500 text-indigo-300" />
{@render children()}
